"""Features por equipo, local y visitante (tarea 3.2, Fase 3).

Para cada partido jugado, calcula la "forma" de cada equipo (local y
visitante) **usando solo sus partidos anteriores** — nunca el partido
actual ni ninguno posterior. Es la pieza central contra la que hay que
cuidarse en esta tarea (data leakage): si una feature "de forma antes
del partido" incluyera el resultado del propio partido, el dataset
quedaría inútil para entrenar un modelo (estaría viendo el futuro).

Cómo se garantiza: se construye una tabla donde cada partido aporta dos
filas (una por equipo, desde su propia perspectiva: goles a favor/en
contra, si ganó/empató/perdió), ordenada por equipo y fecha. Todas las
features rodantes se calculan sobre esa serie **desplazada una
posición** (``shift(1)``) antes de promediar — el partido en curso
nunca entra en su propio promedio, solo los anteriores.

Ventana de forma reciente: últimos 5 partidos (``_ROLLING_WINDOW``),
igual que pedía la tarea 13 del Excel original. Un equipo con menos de
5 partidos previos usa los que tenga (``min_periods=1``); su primer
partido de todos no tiene historia y queda en blanco (``NA``) a
propósito, no es un error.
"""
from __future__ import annotations

import sqlite3

import pandas as pd

from futbol.features.matches import _QUERY_MATCHES_JUGADOS

_ROLLING_WINDOW = 5

_FEATURE_COLUMNS = [
    "goals_scored_avg_last5",
    "goals_conceded_avg_last5",
    "form_points_avg_last5",
    "clean_sheets_rate_last5",
    "current_streak_length",
    "current_streak_result",
    "matches_played_before",
]


def _resultado_equipo(row: pd.Series) -> str:
    if row["goals_for"] > row["goals_against"]:
        return "W"
    if row["goals_for"] < row["goals_against"]:
        return "L"
    return "D"


def _team_centric_matches(conn: sqlite3.Connection) -> pd.DataFrame:
    """Una fila por (partido, equipo): cada partido jugado aporta 2 filas,
    una por perspectiva (local y visitante).
    """
    df = pd.read_sql_query(_QUERY_MATCHES_JUGADOS, conn)

    local = df.rename(columns={
        "home_team": "team", "away_team": "opponent",
        "home_score": "goals_for", "away_score": "goals_against",
    })[["match_id", "match_date", "team", "opponent", "goals_for", "goals_against"]].copy()
    local["is_home"] = True

    visitante = df.rename(columns={
        "away_team": "team", "home_team": "opponent",
        "away_score": "goals_for", "home_score": "goals_against",
    })[["match_id", "match_date", "team", "opponent", "goals_for", "goals_against"]].copy()
    visitante["is_home"] = False

    equipo_partido = pd.concat([local, visitante], ignore_index=True)
    equipo_partido["result_for_team"] = equipo_partido.apply(_resultado_equipo, axis=1)
    equipo_partido["points_for_team"] = equipo_partido["result_for_team"].map(
        {"W": 3, "D": 1, "L": 0}
    )
    return equipo_partido


def _features_de_un_equipo(g: pd.DataFrame, window: int = _ROLLING_WINDOW) -> pd.DataFrame:
    """Calcula las features rodantes de un solo equipo, ya ordenado por
    fecha — todo desplazado 1 posición antes de agregar (ver docstring
    del módulo: así el partido actual nunca entra en su propio cálculo).
    """
    g = g.sort_values(["match_date", "match_id"]).copy()

    goles_previos = g["goals_for"].shift(1)
    goles_recibidos_previos = g["goals_against"].shift(1)
    puntos_previos = g["points_for_team"].shift(1)
    resultado_previo = g["result_for_team"].shift(1)

    g["goals_scored_avg_last5"] = goles_previos.rolling(window, min_periods=1).mean()
    g["goals_conceded_avg_last5"] = goles_recibidos_previos.rolling(window, min_periods=1).mean()
    g["form_points_avg_last5"] = puntos_previos.rolling(window, min_periods=1).mean()

    vallas_invictas_previas = (goles_recibidos_previos == 0).astype(float)
    vallas_invictas_previas[goles_recibidos_previos.isna()] = pd.NA
    g["clean_sheets_rate_last5"] = vallas_invictas_previas.rolling(window, min_periods=1).mean()

    # Racha: se construye sobre el resultado SIN desplazar (para agrupar
    # rachas consecutivas reales) y solo al final se desplaza 1 posición,
    # para que la racha que se adjunta a un partido describa el estado
    # ANTES de jugarlo, no después.
    bloque_de_racha = (g["result_for_team"] != g["result_for_team"].shift()).cumsum()
    racha_hasta_ese_partido = g.groupby(bloque_de_racha).cumcount() + 1
    g["current_streak_length"] = racha_hasta_ese_partido.shift(1)
    g["current_streak_result"] = resultado_previo

    g["matches_played_before"] = range(len(g))  # 0, 1, 2, ... — cuántos partidos previos tenía

    return g


def compute_team_features(conn: sqlite3.Connection, window: int = _ROLLING_WINDOW) -> pd.DataFrame:
    """Una fila por partido jugado, con las features de forma de cada
    equipo (``_home``/``_away``) calculadas solo con partidos anteriores.
    """
    equipo_partido = _team_centric_matches(conn)
    # Loop explícito en vez de groupby(...).apply(...): esta versión de
    # pandas descarta la columna de agrupación ("team") del resultado de
    # apply cuando la función devuelve un DataFrame del mismo tamaño —
    # reasignarla a mano acá es más robusto que depender de ese detalle.
    grupos_con_features = []
    for equipo, g in equipo_partido.groupby("team"):
        f = _features_de_un_equipo(g, window)
        f["team"] = equipo
        grupos_con_features.append(f)
    con_features = pd.concat(grupos_con_features, ignore_index=True)

    base_cols = ["match_id", "team", "is_home"] + _FEATURE_COLUMNS
    local = con_features[con_features["is_home"]][base_cols].drop(columns=["is_home"])
    local = local.rename(columns={"team": "home_team", **{c: f"{c}_home" for c in _FEATURE_COLUMNS}})

    visitante = con_features[~con_features["is_home"]][base_cols].drop(columns=["is_home"])
    visitante = visitante.rename(
        columns={"team": "away_team", **{c: f"{c}_away" for c in _FEATURE_COLUMNS}}
    )

    partidos = pd.read_sql_query(_QUERY_MATCHES_JUGADOS, conn)[
        ["match_id", "match_date", "league_code", "season_code", "home_team", "away_team"]
    ]

    resultado = partidos.merge(local, on=["match_id", "home_team"], how="left")
    resultado = resultado.merge(visitante, on=["match_id", "away_team"], how="left")
    return resultado
