"""Tests de ``src/futbol/models/split.py`` con escenarios calculados a mano.

El foco es verificar que el split es estrictamente cronológico (nunca
mezclado al azar) y sin overlap de fechas entre splits, incluso cuando
varias filas comparten exactamente la misma fecha justo en el borde
del corte.
"""
from __future__ import annotations

import pandas as pd
import pytest

from futbol.models.split import split_temporal, verificar_sin_overlap


def _df_de_fechas(fechas: list[str]) -> pd.DataFrame:
    return pd.DataFrame({
        "match_date": fechas,
        "match_id": range(1, len(fechas) + 1),
    })


def test_split_temporal_respeta_el_orden_cronologico():
    # 10 fechas en orden, mezcladas al escribirlas para confirmar que el
    # split las reordena por fecha y no usa el orden de llegada.
    fechas = [f"2024-01-{d:02d}" for d in range(1, 11)]
    df = _df_de_fechas(fechas[::-1])  # al revés a propósito

    train, val, test = split_temporal(df, train_frac=0.7, val_frac=0.15)

    # n=10: int(10*0.7)=7 filas de train, int(10*0.15)=1 fila de val, el resto a test
    assert list(train["match_date"]) == fechas[:7]
    assert list(val["match_date"]) == fechas[7:8]
    assert list(test["match_date"]) == fechas[8:]


def test_split_temporal_nunca_mezcla_al_azar():
    """Con los datos ya ordenados, train siempre debe ser el tramo más
    antiguo y test el más reciente — nunca una muestra al azar."""
    fechas = [f"2024-02-{d:02d}" for d in range(1, 21)]
    df = _df_de_fechas(fechas)

    train, val, test = split_temporal(df, train_frac=0.7, val_frac=0.15)

    assert train["match_date"].max() < val["match_date"].min()
    assert val["match_date"].max() < test["match_date"].min()


def test_split_temporal_no_parte_un_grupo_de_fechas_repetidas_en_el_corte():
    """Caso calculado a mano: 10 filas, pero las 3 que caerían justo en
    el corte 70% (posiciones 7, 8, 9) comparten la MISMA fecha. El
    corte debe moverse hacia adelante para no partir ese grupo."""
    fechas = (
        [f"2024-03-{d:02d}" for d in range(1, 8)]  # 7 fechas distintas
        + ["2024-03-08", "2024-03-08", "2024-03-08"]  # 3 filas, misma fecha
    )
    df = _df_de_fechas(fechas)

    train, val, test = split_temporal(df, train_frac=0.7, val_frac=0.15)

    # el corte deseado (posición 7) caía en medio del grupo de "2024-03-08";
    # se movió hasta pasar todo el grupo, así que train termina en 7 filas
    # (las fechas distintas) y el grupo repetido entero queda en val/test
    assert len(train) == 7
    assert set(train["match_date"]) == set(fechas[:7])
    assert "2024-03-08" not in set(train["match_date"])
    verificar_sin_overlap(train, val, test)  # no debe lanzar


def test_split_temporal_todas_las_filas_con_la_misma_fecha_no_rompe():
    """Degenerado: si TODAS las filas comparten fecha, no hay dónde
    cortar sin partir el grupo — train se queda con todo, val/test
    vacíos (no se adivina un corte a mitad de un grupo)."""
    df = _df_de_fechas(["2024-04-01"] * 5)

    train, val, test = split_temporal(df, train_frac=0.7, val_frac=0.15)

    assert len(train) == 5
    assert len(val) == 0
    assert len(test) == 0


def test_verificar_sin_overlap_detecta_overlap_real():
    train = _df_de_fechas(["2024-01-01", "2024-01-05"])
    val = _df_de_fechas(["2024-01-03", "2024-01-06"])  # 01-03 < max(train)=01-05: overlap
    test = _df_de_fechas(["2024-01-10"])

    with pytest.raises(AssertionError, match="train y val"):
        verificar_sin_overlap(train, val, test)


def test_verificar_sin_overlap_pasa_con_splits_sanos():
    train = _df_de_fechas(["2024-01-01", "2024-01-02"])
    val = _df_de_fechas(["2024-01-03"])
    test = _df_de_fechas(["2024-01-04"])

    verificar_sin_overlap(train, val, test)  # no debe lanzar
