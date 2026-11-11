"""Split temporal para backtesting (tarea 4.1, Fase 4).

Divide el dataset consolidado cronológicamente: 70% entrenamiento (más
antiguo) / 15% validación / 15% prueba (más reciente), por posición en
el tiempo — NUNCA mezclado al azar. En series de tiempo, un shuffle
antes de partir es otra forma de fuga de datos: el modelo terminaría
entrenándose con partidos más nuevos que algunos que después tiene que
predecir en validación/prueba, exactamente lo que ya se evitó con
cuidado en las features de la Fase 3 (``futbol.features.teams``).
"""
from __future__ import annotations

import pandas as pd

DEFAULT_DATE_COL = "match_date"


def _ajustar_corte(serie_fechas: pd.Series, corte_deseado: int) -> int:
    """Mueve ``corte_deseado`` hacia adelante hasta el primer punto donde
    la fecha cambia, para no partir entre dos splits un grupo de
    partidos con exactamente la misma fecha/hora (ej. varios partidos
    de la misma fecha a la misma hora). Así el corte real queda donde
    la fecha YA cambió, no en medio de un grupo.
    """
    n = len(serie_fechas)
    corte = max(0, min(corte_deseado, n))
    while corte < n and corte > 0 and serie_fechas.iloc[corte] == serie_fechas.iloc[corte - 1]:
        corte += 1
    return corte


def split_temporal(
    df: pd.DataFrame,
    date_col: str = DEFAULT_DATE_COL,
    train_frac: float = 0.70,
    val_frac: float = 0.15,
) -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    """Divide ``df`` en train/val/test por ``date_col``, sin shuffle.

    Los porcentajes son aproximados (no exactos): el corte se ajusta
    hacia adelante para no partir un grupo de filas con la misma fecha
    entre dos splits (ver ``_ajustar_corte``) — por eso puede haber
    algunas filas más o menos de las que darían los porcentajes
    exactos, a cambio de garantizar cero overlap de fechas entre
    splits.
    """
    ordenado = df.sort_values(date_col, kind="stable").reset_index(drop=True)
    n = len(ordenado)
    fechas = ordenado[date_col]

    corte_train = _ajustar_corte(fechas, int(n * train_frac))
    corte_val = _ajustar_corte(fechas, max(corte_train, corte_train + int(n * val_frac)))

    train = ordenado.iloc[:corte_train].reset_index(drop=True)
    val = ordenado.iloc[corte_train:corte_val].reset_index(drop=True)
    test = ordenado.iloc[corte_val:].reset_index(drop=True)
    return train, val, test


def verificar_sin_overlap(
    train: pd.DataFrame,
    val: pd.DataFrame,
    test: pd.DataFrame,
    date_col: str = DEFAULT_DATE_COL,
) -> None:
    """Lanza ``AssertionError`` si hay overlap de fechas entre splits.

    Pensada para usarse después de ``split_temporal`` (o de cualquier
    otro split temporal futuro) como chequeo explícito, no solo
    confiar en que la función que lo generó lo hizo bien.
    """
    if len(train) and len(val):
        assert train[date_col].max() < val[date_col].min(), (
            "verificar_sin_overlap: train y val se superponen en fechas"
        )
    if len(val) and len(test):
        assert val[date_col].max() < test[date_col].min(), (
            "verificar_sin_overlap: val y test se superponen en fechas"
        )
    if len(train) and len(test):
        assert train[date_col].max() < test[date_col].min(), (
            "verificar_sin_overlap: train y test se superponen en fechas"
        )
