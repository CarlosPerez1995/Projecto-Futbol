"""Tests de ``src/futbol/features/odds.py`` contra una BD sintética."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from futbol.db.database import get_connection, init_db
from futbol.features.odds import compute_odds_features

REPO_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema_v4.sql"


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
    season_id = connection.execute("SELECT season_id FROM seasons").fetchone()[0]
    connection.execute(
        "INSERT INTO matches (season_id, home_team_id, away_team_id, match_date, "
        "home_score, away_score, status) VALUES (?, 1, 2, '2024-08-16 19:00:00', 2, 1, 'played')",
        (season_id,),
    )
    connection.commit()
    yield connection
    connection.close()


def _match_id(conn) -> int:
    return conn.execute("SELECT match_id FROM matches").fetchone()[0]


def _insert_odds(conn, match_id, bookmaker, market, is_closing, home_value, draw_value, away_value):
    conn.execute(
        "INSERT INTO odds (match_id, bookmaker, market, is_closing, home_value, draw_value, "
        "away_value, captured_at) VALUES (?, ?, ?, ?, ?, ?, ?, '2024-08-15 00:00:00')",
        (match_id, bookmaker, market, is_closing, home_value, draw_value, away_value),
    )
    conn.commit()


def test_sin_cuotas_cargadas_queda_vacio(conn):
    df = compute_odds_features(conn)
    assert len(df) == 0


def test_devigging_1x2_quita_el_margen_de_la_casa(conn):
    """Cuotas 2.00/3.00/4.00 (bookmaker 'avg', cierre): probabilidad
    cruda (1/cuota) = 0.50/0.333/0.25, suma 1.0833 (overround del
    8.33%) — la probabilidad implícita final debe normalizar a que la
    suma dé exactamente 1, no 1.0833."""
    match_id = _match_id(conn)
    _insert_odds(conn, match_id, "avg", "1x2", 1, 2.00, 3.00, 4.00)

    df = compute_odds_features(conn)

    fila = df[df["match_id"] == match_id].iloc[0]
    total = fila["odds_implied_prob_home"] + fila["odds_implied_prob_draw"] + fila["odds_implied_prob_away"]
    assert total == pytest.approx(1.0)
    assert fila["odds_implied_prob_home"] == pytest.approx((1 / 2.00) / 1.0833333, rel=1e-4)
    assert fila["odds_implied_prob_home"] > fila["odds_implied_prob_draw"] > fila["odds_implied_prob_away"]


def test_devigging_over_under_quita_el_margen(conn):
    match_id = _match_id(conn)
    _insert_odds(conn, match_id, "avg", "over_under_2.5", 1, 1.80, None, 2.10)

    df = compute_odds_features(conn)

    fila = df[df["match_id"] == match_id].iloc[0]
    assert fila["odds_implied_prob_over_2_5"] == pytest.approx(
        (1 / 1.80) / (1 / 1.80 + 1 / 2.10)
    )


def test_ignora_cuotas_pre_cierre_y_de_otra_casa(conn):
    """Solo debe usarse is_closing=1 y bookmaker='avg' — una cuota
    pre-cierre o de otra casa no debe entrar en el cálculo."""
    match_id = _match_id(conn)
    _insert_odds(conn, match_id, "avg", "1x2", 0, 10.0, 10.0, 10.0)  # pre-cierre, distinta
    _insert_odds(conn, match_id, "b365", "1x2", 1, 10.0, 10.0, 10.0)  # otra casa
    _insert_odds(conn, match_id, "avg", "1x2", 1, 2.00, 3.00, 4.00)  # la que debe usarse

    df = compute_odds_features(conn)

    fila = df[df["match_id"] == match_id].iloc[0]
    assert fila["odds_implied_prob_home"] == pytest.approx((1 / 2.00) / 1.0833333, rel=1e-4)


def test_partido_sin_cuota_de_un_mercado_queda_en_na_en_esa_columna(conn):
    match_id = _match_id(conn)
    _insert_odds(conn, match_id, "avg", "1x2", 1, 2.00, 3.00, 4.00)
    # sin over/under cargado para este partido

    df = compute_odds_features(conn)

    fila = df[df["match_id"] == match_id].iloc[0]
    assert pd.notna(fila["odds_implied_prob_home"])
    assert pd.isna(fila["odds_implied_prob_over_2_5"])
