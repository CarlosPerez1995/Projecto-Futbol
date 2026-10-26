"""Tests de ``src/futbol/features/matches.py`` contra una BD sintética.

No hacen ninguna llamada de red. Insertan partidos directamente en la
BD (no vía ``load_data.py``, que ya tiene sus propios tests) para
aislar el cálculo de features.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from futbol.db.database import get_connection, init_db
from futbol.features.matches import compute_match_features, save_features_matches

REPO_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema_v3.sql"


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "futbol.db"
    init_db(db_path, REPO_SCHEMA_PATH)
    connection = get_connection(db_path)
    connection.execute("INSERT INTO leagues (code) VALUES ('TEST-League')")
    connection.execute(
        "INSERT INTO seasons (league_id, code) VALUES "
        "((SELECT league_id FROM leagues WHERE code = 'TEST-League'), '2024')"
    )
    connection.execute("INSERT INTO teams (canonical_name) VALUES ('Team A')")
    connection.execute("INSERT INTO teams (canonical_name) VALUES ('Team B')")
    connection.commit()
    yield connection
    connection.close()


def _season_id(conn) -> int:
    return conn.execute("SELECT season_id FROM seasons").fetchone()[0]


def _insert_played_match(conn, match_date: str, home_score: int, away_score: int) -> int:
    season_id = _season_id(conn)
    cur = conn.execute(
        "INSERT INTO matches (season_id, home_team_id, away_team_id, match_date, "
        "home_score, away_score, status) VALUES (?, 1, 2, ?, ?, ?, 'played')",
        (season_id, match_date, home_score, away_score),
    )
    conn.commit()
    return cur.lastrowid


def _insert_scheduled_match(conn, match_date: str) -> int:
    season_id = _season_id(conn)
    cur = conn.execute(
        "INSERT INTO matches (season_id, home_team_id, away_team_id, match_date) "
        "VALUES (?, 1, 2, ?)",
        (season_id, match_date),
    )
    conn.commit()
    return cur.lastrowid


def test_compute_match_features_excluye_partidos_sin_jugar(conn):
    _insert_played_match(conn, "2024-08-16 19:00:00", 2, 1)
    _insert_scheduled_match(conn, "2024-08-23 19:00:00")

    df = compute_match_features(conn)

    assert len(df) == 1
    assert df.iloc[0]["home_score"] == 2


def test_compute_match_features_calcula_goles_y_diferencia(conn):
    _insert_played_match(conn, "2024-08-16 19:00:00", 3, 1)

    df = compute_match_features(conn)

    fila = df.iloc[0]
    assert fila["total_goals"] == 4
    assert fila["goal_difference"] == 2


@pytest.mark.parametrize(
    "home_score,away_score,esperado",
    [(2, 1, "H"), (1, 2, "A"), (1, 1, "D"), (0, 0, "D")],
)
def test_compute_match_features_result_1x2(conn, home_score, away_score, esperado):
    _insert_played_match(conn, "2024-08-16 19:00:00", home_score, away_score)

    df = compute_match_features(conn)

    assert df.iloc[0]["result_1x2"] == esperado


@pytest.mark.parametrize(
    "home_score,away_score,over_1_5,over_2_5,over_3_5",
    [
        (1, 0, False, False, False),  # 1 gol total
        (1, 1, True, False, False),   # 2 goles total
        (2, 1, True, True, False),    # 3 goles total
        (2, 2, True, True, True),     # 4 goles total
    ],
)
def test_compute_match_features_flags_over(
    conn, home_score, away_score, over_1_5, over_2_5, over_3_5
):
    _insert_played_match(conn, "2024-08-16 19:00:00", home_score, away_score)

    df = compute_match_features(conn)

    fila = df.iloc[0]
    assert bool(fila["over_1_5"]) == over_1_5
    assert bool(fila["over_2_5"]) == over_2_5
    assert bool(fila["over_3_5"]) == over_3_5


@pytest.mark.parametrize(
    "home_score,away_score,esperado",
    [(1, 1, True), (1, 0, False), (0, 1, False), (0, 0, False)],
)
def test_compute_match_features_btts(conn, home_score, away_score, esperado):
    _insert_played_match(conn, "2024-08-16 19:00:00", home_score, away_score)

    df = compute_match_features(conn)

    assert bool(df.iloc[0]["btts"]) == esperado


def test_compute_match_features_xg_pendiente_de_fuente(conn):
    _insert_played_match(conn, "2024-08-16 19:00:00", 1, 0)

    df = compute_match_features(conn)

    assert pd.isna(df.iloc[0]["home_xg"])
    assert pd.isna(df.iloc[0]["away_xg"])


def test_compute_match_features_incluye_identificacion(conn):
    _insert_played_match(conn, "2024-08-16 19:00:00", 1, 0)

    df = compute_match_features(conn)

    fila = df.iloc[0]
    assert fila["league_code"] == "TEST-League"
    assert fila["season_code"] == "2024"
    assert fila["home_team"] == "Team A"
    assert fila["away_team"] == "Team B"


def test_save_features_matches_crea_carpeta_y_escribe_csv(conn, tmp_path: Path):
    _insert_played_match(conn, "2024-08-16 19:00:00", 2, 1)
    df = compute_match_features(conn)
    destino = tmp_path / "subcarpeta" / "features_matches.csv"

    path = save_features_matches(df, destino)

    assert path == destino
    assert destino.exists()
    releido = pd.read_csv(destino)
    assert len(releido) == 1
    assert releido.iloc[0]["result_1x2"] == "H"
