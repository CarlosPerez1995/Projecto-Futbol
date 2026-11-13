"""Tests de ``src/futbol/betting/ev_kelly.py`` — fórmulas puras,
verificadas con casos calculados a mano."""
from __future__ import annotations

import pytest

from futbol.betting.ev_kelly import expected_value, fractional_kelly, kelly_fraction


def test_expected_value_positivo_cuando_el_modelo_le_gana_al_mercado():
    # cuota 2.50 implica probabilidad de mercado (sin margen) de 0.40;
    # si el modelo cree 0.50, hay ventaja real: EV = 0.5*2.5 - 1 = 0.25
    assert expected_value(0.50, 2.50) == pytest.approx(0.25)


def test_expected_value_negativo_cuando_el_modelo_coincide_con_el_mercado_devigged():
    """Caso central documentado en el módulo: apostar con la propia
    probabilidad implícita (sin margen) del mercado da EV negativo
    exacto igual al margen de la casa."""
    cuota_h, cuota_d, cuota_a = 2.00, 3.00, 4.00
    overround = 1 / cuota_h + 1 / cuota_d + 1 / cuota_a
    p_devigged_h = (1 / cuota_h) / overround

    ev = expected_value(p_devigged_h, cuota_h)

    assert ev == pytest.approx(1 / overround - 1)
    assert ev < 0


def test_kelly_fraction_cero_si_ev_no_es_positivo():
    assert kelly_fraction(0.40, 2.50) == 0.0  # EV = 0.40*2.50-1 = 0.0, no estrictamente positivo


def test_kelly_fraction_formula_estandar():
    # p=0.5, cuota=2.5 -> b=1.5, q=0.5 -> f* = (0.5*1.5 - 0.5)/1.5 = 0.1667
    assert kelly_fraction(0.5, 2.5) == pytest.approx((0.5 * 2.5 - 1) / (2.5 - 1))


def test_fractional_kelly_aplica_el_multiplicador():
    f_completo = kelly_fraction(0.5, 2.5)
    assert fractional_kelly(0.5, 2.5, kelly_multiplier=0.5, max_fraction=1.0) == pytest.approx(
        f_completo * 0.5
    )


def test_fractional_kelly_respeta_el_tope_maximo():
    # con una ventaja enorme, Kelly completo pediría apostar casi todo
    # el banco — el tope debe ganarle a la fórmula
    assert fractional_kelly(0.95, 10.0, kelly_multiplier=1.0, max_fraction=0.05) == pytest.approx(0.05)


def test_fractional_kelly_nunca_negativa():
    assert fractional_kelly(0.1, 1.5) == 0.0
