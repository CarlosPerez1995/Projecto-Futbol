"""Extracción de resultados y cuotas históricas vía Soccerdata MatchHistory.

Fuente subyacente: football-data.co.uk. Se instancia por separado de
``Sofascore`` (la regla 9 de AGENTS.md de "una sola instancia" aplica por
lector, no exige una única instancia entre lectores distintos del
paquete ``soccerdata``).

Cuidado particular (tarea 2.1 / 1.2 del plan de robustez): football-data.co.uk
no documenta de forma consistente qué columnas de cuotas (``B365H``,
``PSCA``, etc.) aparecen en cada temporada/liga. Confirmado empíricamente
comparando las 5 grandes ligas: la temporada 2024-25 trae columnas de
``1XBet`` y ``William Hill`` que la 2025-26 ya no tiene, mientras que esta
última suma ``Betfred``/``BetMGM``/``Betvictor``/``Coral``/``Ladbrokes``.
Por eso este módulo loguea qué columnas de cuotas aparecieron realmente
en cada corrida (``_log_odds_columns``) en vez de asumir un esquema fijo.
El mapeo prefijo -> casa de apuestas está documentado en
``docs/odds_columns_map.md`` (tomado de http://www.football-data.co.uk/notes.txt,
la fuente oficial que cita el propio docstring de
``soccerdata.MatchHistory.read_games``).
"""
from __future__ import annotations

import logging

import pandas as pd
import soccerdata as scdat

from futbol.transform.normalize import _coerce_datetime_columns, _normalize_columns

logger = logging.getLogger(__name__)

MATCH_HISTORY_SOURCE = "match_history"

# Columnas de resultado/estadísticas de partido que devuelve
# ``read_games()`` (ver notes.txt de football-data.co.uk) - todo lo que
# no está acá se trata como columna de cuotas en ``_log_odds_columns``.
# Nombres ya en snake_case (post ``_normalize_columns``).
_NON_ODDS_COLUMNS = {
    "date", "home_team", "away_team", "referee", "attendance", "season",
    "fthg", "ftag", "ftr", "hthg", "htag", "htr",
    "hs", "as", "hst", "ast", "hhw", "ahw", "hc", "ac",
    "hf", "af", "hfkc", "afkc", "ho", "ao", "hy", "ay",
    "hr", "ar", "hbp", "abp",
}


def _log_odds_columns(df: pd.DataFrame) -> None:
    """Loguea qué columnas de cuotas trajo realmente esta corrida.

    No asume un esquema fijo de casas de apuestas (ver docstring del
    módulo): solo reporta lo que efectivamente vino en ``df.columns``,
    para que quede en el log de cada corrida y no haga falta volver a
    investigar football-data.co.uk desde cero.
    """
    columnas_cuotas = sorted(c for c in df.columns if c not in _NON_ODDS_COLUMNS)
    logger.info(
        "Columnas de cuotas encontradas en esta corrida (%d): %s",
        len(columnas_cuotas),
        columnas_cuotas,
    )


def get_match_history(match_history: scdat.MatchHistory) -> pd.DataFrame:
    """Extrae resultados + cuotas históricas de las ligas/temporadas configuradas.

    Normaliza columnas a snake_case y fechas a timezone-naive, igual que
    el resto de los lectores (``_normalize_columns``,
    ``_coerce_datetime_columns`` de ``futbol.transform.normalize``, sin
    modificarlas). Loguea las columnas de cuotas encontradas en la
    corrida (ver ``_log_odds_columns``).
    """
    df = match_history.read_games()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    _log_odds_columns(df)
    return df
