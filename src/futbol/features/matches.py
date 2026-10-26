"""Features por partido (tarea 3.1, Fase 3).

Calcula features derivadas directamente del resultado de cada partido
ya cargado en la BD (tabla ``matches``, Fase 2) — no lee ``data/raw/``
de nuevo, solo lo que ya está en la base.

Alcance: solo partidos con marcador conocido (``status = 'played'``) —
un partido todavía no jugado no tiene de dónde sacar estas features.

No incluye xG (gol esperado, de Understat): esa estadística no se
cargó al modelo relacional en la Fase 2 (ahí Understat solo se usó para
resolver identidad de equipos/partidos — ``home_team_id``/
``away_team_id`` en ``load_data.py`` — no sus métricas de xG). La
columna queda documentada como "pendiente de fuente" (``NA``), tal
como permite explícitamente el plan arquitectónico para esta tarea: no
es un dato perdido, es una decisión de alcance para no mezclar una
tarea de Fase 2 (cargar xG a la BD) con esta de Fase 3 (calcular
features) en un mismo commit. Cargar xG queda para una iteración
futura — ver ``docs/features_map.txt``.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pandas as pd

DEFAULT_OUTPUT_PATH = Path("data/processed/features_matches.csv")

_QUERY_MATCHES_JUGADOS = """
    SELECT
        m.match_id,
        l.code AS league_code,
        s.code AS season_code,
        m.match_date,
        ht.canonical_name AS home_team,
        at.canonical_name AS away_team,
        m.home_score,
        m.away_score
    FROM matches m
    JOIN seasons s ON s.season_id = m.season_id
    JOIN leagues l ON l.league_id = s.league_id
    JOIN teams ht ON ht.team_id = m.home_team_id
    JOIN teams at ON at.team_id = m.away_team_id
    WHERE m.status = 'played'
      AND m.home_score IS NOT NULL
      AND m.away_score IS NOT NULL
"""


def _resultado_1x2(row: pd.Series) -> str:
    if row["home_score"] > row["away_score"]:
        return "H"
    if row["home_score"] < row["away_score"]:
        return "A"
    return "D"


def compute_match_features(conn: sqlite3.Connection) -> pd.DataFrame:
    """Una fila por partido jugado, con sus features derivadas del marcador.

    Columnas: ``match_id``, ``league_code``, ``season_code``,
    ``match_date``, ``home_team``, ``away_team``, ``home_score``,
    ``away_score``, ``total_goals``, ``goal_difference``,
    ``result_1x2`` (``H``/``D``/``A``), ``over_1_5``/``over_2_5``/
    ``over_3_5`` (bool), ``btts`` (bool), ``home_xg``/``away_xg``
    (``NA``, pendiente de fuente — ver docstring del módulo).
    """
    df = pd.read_sql_query(_QUERY_MATCHES_JUGADOS, conn)

    df["total_goals"] = df["home_score"] + df["away_score"]
    df["goal_difference"] = df["home_score"] - df["away_score"]
    df["result_1x2"] = df.apply(_resultado_1x2, axis=1)
    df["over_1_5"] = df["total_goals"] > 1.5
    df["over_2_5"] = df["total_goals"] > 2.5
    df["over_3_5"] = df["total_goals"] > 3.5
    df["btts"] = (df["home_score"] > 0) & (df["away_score"] > 0)
    df["home_xg"] = pd.NA
    df["away_xg"] = pd.NA

    return df


def save_features_matches(df: pd.DataFrame, path: Path = DEFAULT_OUTPUT_PATH) -> Path:
    """Guarda ``df`` en ``path`` (crea la carpeta contenedora si hace falta)."""
    path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(path, index=False)
    return path
