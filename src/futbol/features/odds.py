"""Features de cuotas de mercado como predictoras (decisión de Carlos,
11 nov 2026, tras el hallazgo de que el xG tampoco resolvía Fase 4 —
ver ``docs/xgb_binary_resultados.md``).

Usa la cuota de **cierre** (``is_closing=1``) promedio entre casas de
apuestas (``bookmaker='avg'``, la columna ``AvgC*`` de
football-data.co.uk, ya cargada por ``load_odds_1x2``/
``load_odds_extra_markets``) — es la cuota más informativa disponible
y, al ser de cierre, se fija ANTES del partido (no hay fuga de datos:
"antes del partido" no significa "mucho antes", significa que no usa
ninguna información posterior al resultado).

Por qué "avg" y no una casa puntual: `docs/odds_columns_map.md` ya
documentó que el esquema de columnas por casa de apuestas cambia entre
temporadas (118 vs. 130 columnas en temporadas distintas) — la columna
promedio es la única con cobertura estable en todo el dataset,
verificado contra los datos reales (3.504 de 3.515 partidos).

Las cuotas crudas no son probabilidades: traen el margen de la casa de
apuestas (overround). Se convierten con la técnica estándar de
"devigging": probabilidad implícita cruda = 1/cuota para cada
resultado, normalizada para que la suma dé 1 (reparte el margen
proporcionalmente, no lo descarta).
"""
from __future__ import annotations

import sqlite3

import pandas as pd

ODDS_FEATURE_COLUMNS = [
    "odds_implied_prob_home",
    "odds_implied_prob_draw",
    "odds_implied_prob_away",
    "odds_implied_prob_over_2_5",
]

_QUERY_ODDS_1X2_CIERRE_AVG = """
SELECT match_id, home_value AS odds_home, draw_value AS odds_draw, away_value AS odds_away
FROM odds
WHERE market = '1x2' AND is_closing = 1 AND bookmaker = 'avg'
"""

_QUERY_ODDS_OU25_CIERRE_AVG = """
SELECT match_id, home_value AS odds_over, away_value AS odds_under
FROM odds
WHERE market = 'over_under_2.5' AND is_closing = 1 AND bookmaker = 'avg'
"""


def _devig_1x2(df: pd.DataFrame) -> pd.DataFrame:
    raw_h = 1.0 / df["odds_home"]
    raw_d = 1.0 / df["odds_draw"]
    raw_a = 1.0 / df["odds_away"]
    overround = raw_h + raw_d + raw_a
    df["odds_implied_prob_home"] = raw_h / overround
    df["odds_implied_prob_draw"] = raw_d / overround
    df["odds_implied_prob_away"] = raw_a / overround
    return df


def _devig_over_under(df: pd.DataFrame) -> pd.DataFrame:
    raw_over = 1.0 / df["odds_over"]
    raw_under = 1.0 / df["odds_under"]
    overround = raw_over + raw_under
    df["odds_implied_prob_over_2_5"] = raw_over / overround
    return df


def compute_odds_features(conn: sqlite3.Connection) -> pd.DataFrame:
    """Una fila por ``match_id`` con las probabilidades implícitas de
    mercado (cuota de cierre promedio, sin margen). Un partido sin
    cuota cargada para un mercado queda en ``NA`` en esa columna, no se
    inventa un valor.
    """
    odds_1x2 = pd.read_sql_query(_QUERY_ODDS_1X2_CIERRE_AVG, conn)
    odds_1x2 = _devig_1x2(odds_1x2)[["match_id", *ODDS_FEATURE_COLUMNS[:3]]]

    odds_ou25 = pd.read_sql_query(_QUERY_ODDS_OU25_CIERRE_AVG, conn)
    odds_ou25 = _devig_over_under(odds_ou25)[["match_id", "odds_implied_prob_over_2_5"]]

    return odds_1x2.merge(odds_ou25, on="match_id", how="outer")
