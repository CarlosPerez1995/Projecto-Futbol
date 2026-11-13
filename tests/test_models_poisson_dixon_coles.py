"""Tests de ``src/futbol/models/poisson_dixon_coles.py``.

Verifica las fórmulas de Dixon-Coles con casos calculados a mano
(``_tau``, ``rps``, ``brier_score``) y el ajuste del modelo con un
escenario sintético donde la dirección del resultado (quién es mejor)
está controlada a propósito, no es ruido.
"""
from __future__ import annotations

import pandas as pd
import pytest

from futbol.models.poisson_dixon_coles import (
    DixonColesModel,
    _tau,
    brier_score,
    fit_and_evaluate_by_group,
    fit_dixon_coles,
    rps,
)


# ---------------------------------------------------------------------------
# _tau — valores exactos de Dixon & Coles 1997
# ---------------------------------------------------------------------------

def test_tau_casos_especiales():
    lam, mu, rho = 1.5, 1.2, 0.1
    assert _tau(0, 0, lam, mu, rho) == pytest.approx(1 - lam * mu * rho)
    assert _tau(0, 1, lam, mu, rho) == pytest.approx(1 + lam * rho)
    assert _tau(1, 0, lam, mu, rho) == pytest.approx(1 + mu * rho)
    assert _tau(1, 1, lam, mu, rho) == pytest.approx(1 - rho)


def test_tau_cualquier_otro_marcador_es_1():
    assert _tau(2, 0, 1.5, 1.2, 0.1) == 1.0
    assert _tau(3, 3, 1.5, 1.2, 0.1) == 1.0
    assert _tau(0, 2, 1.5, 1.2, 0.1) == 1.0


# ---------------------------------------------------------------------------
# rps / brier_score — valores calculados a mano
# ---------------------------------------------------------------------------

def test_rps_prediccion_perfecta_da_cero():
    assert rps((1.0, 0.0, 0.0), "H") == pytest.approx(0.0)


def test_rps_equiprobable_contra_home():
    # cum1 = 1/3, o_cum1 = 1 -> (1/3-1)^2 = 4/9
    # cum2 = 2/3, o_cum2 = 1 -> (2/3-1)^2 = 1/9
    # (4/9 + 1/9) / 2 = 5/18
    assert rps((1 / 3, 1 / 3, 1 / 3), "H") == pytest.approx(5 / 18)


def test_rps_penaliza_mas_lejos_que_cerca():
    # predicción "fuerte local" (0.8,0.1,0.1): si gana el visitante (lejos)
    # debe doler más que si empata (cerca), para la MISMA predicción.
    rps_si_empata = rps((0.8, 0.1, 0.1), "D")
    rps_si_gana_visitante = rps((0.8, 0.1, 0.1), "A")
    assert rps_si_gana_visitante > rps_si_empata


def test_brier_score_prediccion_perfecta_da_cero():
    assert brier_score((1.0, 0.0, 0.0), "H") == pytest.approx(0.0)


def test_brier_score_equiprobable():
    # 3 * (1/3 - o_i)^2 sumado: para H, (1/3-1)^2 + (1/3-0)^2 + (1/3-0)^2
    # = 4/9 + 1/9 + 1/9 = 6/9 = 2/3
    assert brier_score((1 / 3, 1 / 3, 1 / 3), "H") == pytest.approx(2 / 3)


# ---------------------------------------------------------------------------
# fit_dixon_coles — escenario sintético con dirección controlada
# ---------------------------------------------------------------------------

@pytest.fixture
def partidos_sinteticos() -> pd.DataFrame:
    # "Strong" gana siempre con comodidad, "Weak" pierde siempre con
    # comodidad, "Mid1"/"Mid2" quedan en el medio y se reparten entre sí.
    filas = [
        ("Strong", "Weak", 4, 0), ("Weak", "Strong", 0, 3),
        ("Strong", "Mid1", 2, 1), ("Mid1", "Strong", 0, 2),
        ("Strong", "Mid2", 3, 1), ("Mid2", "Strong", 1, 2),
        ("Weak", "Mid1", 0, 2), ("Mid1", "Weak", 3, 0),
        ("Weak", "Mid2", 1, 2), ("Mid2", "Weak", 2, 0),
        ("Mid1", "Mid2", 1, 1), ("Mid2", "Mid1", 1, 1),
    ]
    return pd.DataFrame(filas, columns=["home_team", "away_team", "home_score", "away_score"])


def test_fit_dixon_coles_ordena_ataque_segun_la_senal_de_los_datos(partidos_sinteticos):
    modelo = fit_dixon_coles(partidos_sinteticos)

    idx = modelo.team_index
    ataque_strong = modelo.attack[idx["Strong"]]
    ataque_weak = modelo.attack[idx["Weak"]]
    ataque_mid1 = modelo.attack[idx["Mid1"]]
    ataque_mid2 = modelo.attack[idx["Mid2"]]

    assert ataque_strong > ataque_mid1
    assert ataque_strong > ataque_mid2
    assert ataque_mid1 > ataque_weak
    assert ataque_mid2 > ataque_weak


def test_fit_dixon_coles_ordena_defensa_segun_la_senal_de_los_datos(partidos_sinteticos):
    """defensa ALTA = mala defensa (deja marcar más al rival que la
    enfrenta) — ver docstring del módulo sobre la convención de signo."""
    modelo = fit_dixon_coles(partidos_sinteticos)

    idx = modelo.team_index
    defensa_strong = modelo.defense[idx["Strong"]]
    defensa_weak = modelo.defense[idx["Weak"]]

    assert defensa_strong < defensa_weak  # Strong defiende mejor que Weak


def test_dixon_coles_model_probabilidades_suman_uno(partidos_sinteticos):
    modelo = fit_dixon_coles(partidos_sinteticos)

    p_h, p_d, p_a = modelo.match_outcome_probs("Strong", "Weak")

    assert p_h + p_d + p_a == pytest.approx(1.0, abs=1e-6)
    assert p_h > p_a  # Strong de local contra Weak: más probable que gane el local


# ---------------------------------------------------------------------------
# fit_and_evaluate_by_group
# ---------------------------------------------------------------------------

def _con_contexto(df: pd.DataFrame, liga: str, temporada: str, dates: list[str]) -> pd.DataFrame:
    df = df.copy()
    df["league_code"] = liga
    df["season_code"] = temporada
    df["match_date"] = dates
    df["result_1x2"] = df.apply(
        lambda r: "H" if r["home_score"] > r["away_score"]
        else ("A" if r["home_score"] < r["away_score"] else "D"),
        axis=1,
    )
    return df


def test_fit_and_evaluate_by_group_con_datos_de_prueba(partidos_sinteticos):
    train = _con_contexto(
        partidos_sinteticos, "TEST-League", "2024",
        [f"2024-08-{i+1:02d}" for i in range(len(partidos_sinteticos))],
    )
    eval_df = pd.DataFrame([{
        "league_code": "TEST-League", "season_code": "2024",
        "home_team": "Strong", "away_team": "Weak", "result_1x2": "H",
    }])

    resultado = fit_and_evaluate_by_group(train, eval_df)

    assert len(resultado) == 1
    fila = resultado.iloc[0]
    assert fila["n_train"] == 12
    assert fila["n_eval"] == 1
    assert not pd.isna(fila["rps"])
    assert not pd.isna(fila["brier"])


def test_fit_and_evaluate_by_group_sin_datos_de_prueba_da_nan(partidos_sinteticos):
    """Caso real del proyecto: una temporada que cae entera en
    entrenamiento (sin partidos futuros para probar) no debe inventar
    una métrica — queda NaN, documentado, no un número falso."""
    train = _con_contexto(
        partidos_sinteticos, "TEST-League", "2024",
        [f"2024-08-{i+1:02d}" for i in range(len(partidos_sinteticos))],
    )
    eval_df = pd.DataFrame(columns=["league_code", "season_code", "home_team", "away_team", "result_1x2"])

    resultado = fit_and_evaluate_by_group(train, eval_df)

    assert len(resultado) == 1
    assert resultado.iloc[0]["n_eval"] == 0
    assert pd.isna(resultado.iloc[0]["rps"])
    assert pd.isna(resultado.iloc[0]["brier"])


def test_fit_and_evaluate_by_group_equipo_no_visto_se_omite_sin_romper(partidos_sinteticos):
    train = _con_contexto(
        partidos_sinteticos, "TEST-League", "2024",
        [f"2024-08-{i+1:02d}" for i in range(len(partidos_sinteticos))],
    )
    eval_df = pd.DataFrame([{
        "league_code": "TEST-League", "season_code": "2024",
        "home_team": "Strong", "away_team": "Equipo Fantasma", "result_1x2": "H",
    }])

    resultado = fit_and_evaluate_by_group(train, eval_df)

    assert resultado.iloc[0]["n_eval"] == 0  # se omitió, no rompió
    assert pd.isna(resultado.iloc[0]["rps"])
