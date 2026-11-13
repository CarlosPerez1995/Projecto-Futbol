"""Tests de ``src/futbol/betting/backtest.py`` — núcleo puro de la
simulación (``_simular_apuestas``/``_max_drawdown_pct``/``_resumen``),
sin BD ni modelo real (eso se valida a mano contra datos reales, ver
``docs/backtest_resultados.md``)."""
from __future__ import annotations

import pytest

from futbol.betting.backtest import _max_drawdown_pct, _resumen, _simular_apuestas
import pandas as pd


def test_simular_apuestas_ignora_candidatos_con_ev_negativo():
    candidatos = [
        {"match_id": 1, "label": "H", "p": 0.40, "odds": 2.00, "gano": True},  # EV = -0.20
    ]
    apuestas, bankroll_final = _simular_apuestas(
        candidatos, ev_threshold=0.0, kelly_multiplier=0.5, max_fraction=0.05, bankroll_inicial=1000.0
    )
    assert apuestas == []
    assert bankroll_final == 1000.0


def test_simular_apuestas_actualiza_el_banco_cuando_gana():
    # p=0.5, odds=2.5 -> EV=0.25>0; kelly completo=(0.5*2.5-1)/1.5=0.1667; *0.5=0.0833; tope 0.05 -> gana el tope
    candidatos = [{"match_id": 1, "label": "over", "p": 0.5, "odds": 2.5, "gano": True}]
    apuestas, bankroll_final = _simular_apuestas(
        candidatos, ev_threshold=0.0, kelly_multiplier=0.5, max_fraction=0.05, bankroll_inicial=1000.0
    )
    assert len(apuestas) == 1
    stake_esperado = 1000.0 * 0.05  # tope, no la fracción de Kelly completa
    assert apuestas[0]["stake"] == pytest.approx(stake_esperado)
    assert bankroll_final == pytest.approx(1000.0 + stake_esperado * (2.5 - 1))


def test_simular_apuestas_resta_el_stake_cuando_pierde():
    candidatos = [{"match_id": 1, "label": "over", "p": 0.5, "odds": 2.5, "gano": False}]
    apuestas, bankroll_final = _simular_apuestas(
        candidatos, ev_threshold=0.0, kelly_multiplier=0.5, max_fraction=0.05, bankroll_inicial=1000.0
    )
    stake_esperado = 1000.0 * 0.05
    assert bankroll_final == pytest.approx(1000.0 - stake_esperado)


def test_simular_apuestas_compone_el_banco_entre_apuestas_sucesivas():
    """La segunda apuesta debe calcular su stake sobre el banco YA
    actualizado por la primera, no sobre el banco inicial — así es
    como realmente se gestiona un banco de apuestas con el tiempo."""
    candidatos = [
        {"match_id": 1, "label": "H", "p": 0.5, "odds": 2.5, "gano": True},
        {"match_id": 2, "label": "H", "p": 0.5, "odds": 2.5, "gano": True},
    ]
    apuestas, bankroll_final = _simular_apuestas(
        candidatos, ev_threshold=0.0, kelly_multiplier=0.5, max_fraction=0.05, bankroll_inicial=1000.0
    )
    assert apuestas[1]["stake"] > apuestas[0]["stake"]  # banco creció, el 5% de un banco mayor es mayor


def test_simular_apuestas_ignora_cuota_faltante():
    candidatos = [{"match_id": 1, "label": "H", "p": 0.5, "odds": float("nan"), "gano": True}]
    apuestas, bankroll_final = _simular_apuestas(
        candidatos, ev_threshold=0.0, kelly_multiplier=0.5, max_fraction=0.05, bankroll_inicial=1000.0
    )
    assert apuestas == []
    assert bankroll_final == 1000.0


def test_max_drawdown_pct_detecta_la_mayor_caida_desde_un_pico():
    # banco: 1000 -> 1200 (pico) -> 900 (caída real de 25% desde 1200) -> 1100
    serie = pd.Series([1200.0, 900.0, 1100.0])
    dd = _max_drawdown_pct(serie, bankroll_inicial=1000.0)
    assert dd == pytest.approx(-25.0)


def test_resumen_con_cero_apuestas_no_rompe():
    r = _resumen([], bankroll_inicial=1000.0, bankroll_final=1000.0, n_partidos_con_cuota=50)
    assert r["n_apuestas"] == 0
    assert r["roi"] is None
    assert r["retorno_sobre_banco_pct"] == 0.0


def test_resumen_calcula_roi_y_tasa_de_acierto():
    apuestas = [
        {"gano": True, "stake": 100.0, "profit": 50.0, "bankroll_despues": 1050.0},
        {"gano": False, "stake": 100.0, "profit": -100.0, "bankroll_despues": 950.0},
    ]
    r = _resumen(apuestas, bankroll_inicial=1000.0, bankroll_final=950.0, n_partidos_con_cuota=10)
    assert r["n_apuestas"] == 2
    assert r["tasa_acierto"] == pytest.approx(0.5)
    assert r["total_staked"] == pytest.approx(200.0)
    assert r["profit_total"] == pytest.approx(-50.0)
    assert r["roi"] == pytest.approx(-50.0 / 200.0)
