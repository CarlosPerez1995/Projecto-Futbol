"""Tests de ``src/futbol/features/teams.py`` contra una BD sintética.

El foco de estos tests es verificar, con un escenario calculado a mano,
que ninguna feature de un partido usa datos del propio partido ni de
partidos posteriores (data leakage) — no solo que el código corra.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from futbol.db.database import get_connection, init_db
from futbol.features.teams import compute_team_features

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
    for nombre in ("Team A", "Team B", "Team C"):
        connection.execute("INSERT INTO teams (canonical_name) VALUES (?)", (nombre,))
    connection.commit()
    yield connection
    connection.close()


def _season_id(conn) -> int:
    return conn.execute("SELECT season_id FROM seasons").fetchone()[0]


def _team_id(conn, nombre: str) -> int:
    return conn.execute(
        "SELECT team_id FROM teams WHERE canonical_name = ?", (nombre,)
    ).fetchone()[0]


def _insert_played(conn, match_date, home, away, home_score, away_score):
    season_id = _season_id(conn)
    conn.execute(
        "INSERT INTO matches (season_id, home_team_id, away_team_id, match_date, "
        "home_score, away_score, status) VALUES (?, ?, ?, ?, ?, ?, 'played')",
        (season_id, _team_id(conn, home), _team_id(conn, away), match_date, home_score, away_score),
    )
    conn.commit()


# Escenario de 3 partidos de Team A, calculado a mano (ver docstring del
# módulo):
#   1) 2024-08-01: Team A (local) 2-0 Team C           -> A: W, 2 a favor, 0 en contra
#   2) 2024-08-08: Team B (local) 1-1 Team A (visitante) -> A: D, 1 a favor, 1 en contra
#   3) 2024-08-15: Team A (local) 0-3 Team B (visitante) -> A: L, 0 a favor, 3 en contra
#
# Las features del partido 3, para Team A como local, deben salir SOLO de
# los partidos 1 y 2 (nunca del marcador 0-3 del propio partido 3).

@pytest.fixture
def escenario_3_partidos(conn):
    _insert_played(conn, "2024-08-01 15:00:00", "Team A", "Team C", 2, 0)
    _insert_played(conn, "2024-08-08 15:00:00", "Team B", "Team A", 1, 1)
    _insert_played(conn, "2024-08-15 15:00:00", "Team A", "Team B", 0, 3)
    return conn


def test_primer_partido_de_un_equipo_no_tiene_historia(escenario_3_partidos):
    df = compute_team_features(escenario_3_partidos)

    primero = df[df["match_date"] == "2024-08-01 15:00:00"].iloc[0]
    assert primero["matches_played_before_home"] == 0
    assert pd.isna(primero["goals_scored_avg_last5_home"])
    assert pd.isna(primero["current_streak_length_home"])


def test_features_del_tercer_partido_no_usan_su_propio_marcador(escenario_3_partidos):
    """El partido 3 es 0-3 para Team A — si hubiera fuga de datos, el
    promedio de goles a favor incluiría ese 0 y bajaría; el de goles en
    contra incluiría ese 3 y subiría. Verificamos que NO es así.
    """
    df = compute_team_features(escenario_3_partidos)

    tercero = df[df["match_date"] == "2024-08-15 15:00:00"].iloc[0]
    assert tercero["home_team"] == "Team A"

    assert tercero["matches_played_before_home"] == 2
    assert tercero["goals_scored_avg_last5_home"] == pytest.approx((2 + 1) / 2)  # NO incluye el 0 del propio partido
    assert tercero["goals_conceded_avg_last5_home"] == pytest.approx((0 + 1) / 2)  # NO incluye el 3 del propio partido
    assert tercero["form_points_avg_last5_home"] == pytest.approx((3 + 1) / 2)  # W=3, D=1
    assert tercero["clean_sheets_rate_last5_home"] == pytest.approx(0.5)  # valla invicta en el partido 1 solamente

    # racha ANTES del partido 3: el partido más reciente (2) fue empate,
    # distinto del resultado del partido 1 (victoria) -> racha de 1
    assert tercero["current_streak_length_home"] == 1
    assert tercero["current_streak_result_home"] == "D"


def test_features_del_segundo_partido_desde_la_perspectiva_visitante(escenario_3_partidos):
    """Team A visita en el partido 2 — sus features '_away' deben salir
    solo del partido 1 (su único antecedente), nunca del empate 1-1 de
    este mismo partido."""
    df = compute_team_features(escenario_3_partidos)

    segundo = df[df["match_date"] == "2024-08-08 15:00:00"].iloc[0]
    assert segundo["away_team"] == "Team A"

    assert segundo["matches_played_before_away"] == 1
    assert segundo["goals_scored_avg_last5_away"] == pytest.approx(2)
    assert segundo["goals_conceded_avg_last5_away"] == pytest.approx(0)
    assert segundo["form_points_avg_last5_away"] == pytest.approx(3)
    assert segundo["clean_sheets_rate_last5_away"] == pytest.approx(1.0)
    assert segundo["current_streak_length_away"] == 1
    assert segundo["current_streak_result_away"] == "W"


def test_equipos_distintos_no_se_contaminan_entre_si(escenario_3_partidos):
    """Las features de Team B y Team C no deben mezclarse con las de
    Team A aunque compartan partidos."""
    df = compute_team_features(escenario_3_partidos)

    primero = df[df["match_date"] == "2024-08-01 15:00:00"].iloc[0]
    assert primero["away_team"] == "Team C"
    assert primero["matches_played_before_away"] == 0  # Team C, primer partido también

    segundo = df[df["match_date"] == "2024-08-08 15:00:00"].iloc[0]
    assert segundo["home_team"] == "Team B"
    assert segundo["matches_played_before_home"] == 0  # Team B, primer partido


def test_racha_se_extiende_con_resultados_consecutivos_iguales(conn):
    """Tres victorias seguidas de Team A deben dar racha de longitud
    creciente (1, 2) ANTES del tercer partido, no 3 (que incluiría el
    propio partido en curso)."""
    _insert_played(conn, "2024-08-01 15:00:00", "Team A", "Team C", 3, 0)  # W
    _insert_played(conn, "2024-08-08 15:00:00", "Team A", "Team B", 2, 0)  # W
    _insert_played(conn, "2024-08-15 15:00:00", "Team A", "Team C", 1, 0)  # W (el tercero)

    df = compute_team_features(conn)

    tercero = df[df["match_date"] == "2024-08-15 15:00:00"].iloc[0]
    assert tercero["current_streak_length_home"] == 2  # las 2 victorias previas, no 3
    assert tercero["current_streak_result_home"] == "W"
