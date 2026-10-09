"""Extracción de datos de fútbol desde Sofascore vía soccerdata.

Una sola instancia de ``Sofascore`` se reutiliza para todas las
ligas/temporadas de la corrida, tal como exige la regla 9 de
AGENTS.md (la instanciación ocurre en el llamador, no acá).

Normalizaciones aplicadas a cada DataFrame (ver
``futbol.transform.normalize``):
- Nombres de columnas y de niveles del índice en snake_case.
- Columnas de fecha/datetime timezone-aware quedan timezone-naive.
"""
from __future__ import annotations

import logging

import pandas as pd
import soccerdata as scdat

from futbol.transform.normalize import _coerce_datetime_columns, _normalize_columns

logger = logging.getLogger(__name__)

SOFASCORE_SOURCE = "sofascore"


def _filter_available_leagues(ligas: list[str]) -> list[str]:
    """Filtra ``ligas`` a las que Sofascore realmente soporta.

    Tarea 1.1 del plan de robustez: no asumir que las 8 ligas de
    ``LEAGUE_DICT`` están disponibles para esta fuente en particular;
    se consulta ``Sofascore.available_leagues()`` (no hace llamadas de
    red, solo lee el diccionario de configuración) y se loguea un
    warning por cada liga solicitada que no esté soportada.

    Raises:
        ValueError: si ninguna de las ligas solicitadas está disponible.
    """
    disponibles = set(scdat.Sofascore.available_leagues())
    seleccionadas = [liga for liga in ligas if liga in disponibles]
    no_disponibles = [liga for liga in ligas if liga not in disponibles]
    if no_disponibles:
        logger.warning(
            "Ligas solicitadas no disponibles en Sofascore, se omiten: %s",
            no_disponibles,
        )
    if not seleccionadas:
        raise ValueError(
            f"Ninguna de las ligas solicitadas {ligas} está disponible en "
            f"Sofascore. Disponibles: {sorted(disponibles)}"
        )
    return seleccionadas


def get_leagues(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae el catálogo de ligas disponibles.

    Normaliza columnas a snake_case y fechas a timezone-naive (no hay
    columnas de fecha en este DataFrame, pero el helper es idempotente).
    """
    df = sofascore.read_leagues()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def get_seasons(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae las temporadas disponibles para las ligas configuradas."""
    df = sofascore.read_seasons()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def get_standings(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae la tabla de posiciones de las ligas/temporadas configuradas.

    Renombra columnas a snake_case: MP -> mp, W -> w, D -> d, L -> l,
    GF -> gf, GA -> ga, GD -> gd, Pts -> pts.
    """
    df = sofascore.read_league_table()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def get_schedule(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae el calendario de partidos de las ligas/temporadas configuradas.

    La columna ``date`` (datetime64 tz-aware) se normaliza a
    timezone-naive según la nota de AGENTS.md (tz_localize(None)).
    """
    df = sofascore.read_schedule()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df
