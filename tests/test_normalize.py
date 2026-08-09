"""Tests de ``src/futbol/transform/normalize.py`` con DataFrames sintéticos.

No hacen ninguna llamada de red: corren enteramente sobre datos en memoria.
"""
from __future__ import annotations

import pandas as pd
import pytest

from futbol.transform.normalize import (
    _coerce_datetime_columns,
    _normalize_columns,
    _to_snake_case,
    _validate,
)


# ---------------------------------------------------------------------------
# _to_snake_case
# ---------------------------------------------------------------------------

@pytest.mark.parametrize(
    "entrada,esperado",
    [
        ("Home Team", "home_team"),
        ("MP", "mp"),
        ("Away-Team", "away_team"),
        ("  Goals Scored  ", "goals_scored"),
        ("Multiple   Spaces", "multiple_spaces"),
        ("already_snake", "already_snake"),
        ("Mixed_Case-Name", "mixed_case_name"),
    ],
)
def test_to_snake_case(entrada, esperado):
    assert _to_snake_case(entrada) == esperado


# ---------------------------------------------------------------------------
# _normalize_columns
# ---------------------------------------------------------------------------

def test_normalize_columns_renombra_columnas():
    df = pd.DataFrame({"Home Team": ["A"], "MP": [1]})
    resultado = _normalize_columns(df)
    assert list(resultado.columns) == ["home_team", "mp"]


def test_normalize_columns_renombra_niveles_de_indice():
    df = pd.DataFrame({"valor": [1, 2]})
    df.index = pd.MultiIndex.from_tuples(
        [("A", 1), ("B", 2)], names=["Home Team", "Season"]
    )
    resultado = _normalize_columns(df)
    assert list(resultado.index.names) == ["home_team", "season"]


def test_normalize_columns_preserva_nivel_de_indice_none():
    df = pd.DataFrame({"Col": [1, 2]})
    assert df.index.names == [None]
    resultado = _normalize_columns(df)
    assert resultado.index.names == [None]


# ---------------------------------------------------------------------------
# _coerce_datetime_columns
# ---------------------------------------------------------------------------

def test_coerce_datetime_columns_quita_timezone():
    df = pd.DataFrame(
        {"fecha": pd.to_datetime(["2026-01-01", "2026-01-02"]).tz_localize("UTC")}
    )
    assert df["fecha"].dt.tz is not None
    resultado = _coerce_datetime_columns(df)
    assert resultado["fecha"].dt.tz is None


def test_coerce_datetime_columns_sin_timezone_no_falla():
    df = pd.DataFrame({"fecha": pd.to_datetime(["2026-01-01", "2026-01-02"])})
    assert df["fecha"].dt.tz is None
    resultado = _coerce_datetime_columns(df)
    assert resultado["fecha"].dt.tz is None
    pd.testing.assert_series_equal(resultado["fecha"], df["fecha"])


def test_coerce_datetime_columns_no_toca_columnas_no_datetime():
    df = pd.DataFrame({"nombre": ["A", "B"], "valor": [1, 2]})
    resultado = _coerce_datetime_columns(df)
    pd.testing.assert_frame_equal(resultado, df)


# ---------------------------------------------------------------------------
# _validate
# ---------------------------------------------------------------------------

def test_validate_pasa_con_columnas_en_snake_case():
    df = pd.DataFrame({"home_team": ["A"], "mp": [1]})
    _validate("dataset_ok", df)  # no debe lanzar


def test_validate_falla_con_columnas_con_mayusculas_o_espacios():
    df = pd.DataFrame({"Home Team": ["A"], "mp": [1]})
    with pytest.raises(AssertionError):
        _validate("dataset_malo", df)


def test_validate_falla_con_nivel_de_indice_fuera_de_snake_case():
    df = pd.DataFrame({"valor": [1, 2]})
    df.index = pd.Index(["x", "y"], name="Home Team")
    with pytest.raises(AssertionError):
        _validate("dataset_indice_malo", df)
