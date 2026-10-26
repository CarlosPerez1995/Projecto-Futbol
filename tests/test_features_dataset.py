"""Tests de ``src/futbol/features/dataset.py`` contra una BD sintética."""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from futbol.db.database import get_connection, init_db
from futbol.features.dataset import (
    IDENTIFIER_COLUMNS,
    TARGET_COLUMNS,
    build_model_dataset,
    predictor_columns,
    save_model_dataset,
    write_features_spec,
)

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


def _team_id(conn, nombre: str) -> int:
    return conn.execute(
        "SELECT team_id FROM teams WHERE canonical_name = ?", (nombre,)
    ).fetchone()[0]


def _insert_played(conn, match_date, home, away, home_score, away_score):
    season_id = conn.execute("SELECT season_id FROM seasons").fetchone()[0]
    conn.execute(
        "INSERT INTO matches (season_id, home_team_id, away_team_id, match_date, "
        "home_score, away_score, status) VALUES (?, ?, ?, ?, ?, ?, 'played')",
        (season_id, _team_id(conn, home), _team_id(conn, away), match_date, home_score, away_score),
    )
    conn.commit()


@pytest.fixture
def conn_con_3_partidos(conn):
    _insert_played(conn, "2024-08-01 15:00:00", "Team A", "Team C", 2, 0)
    _insert_played(conn, "2024-08-08 15:00:00", "Team B", "Team A", 1, 1)
    _insert_played(conn, "2024-08-15 15:00:00", "Team A", "Team B", 0, 3)
    return conn


def test_predictoras_y_objetivo_no_se_superponen():
    """Red de seguridad: si algún día alguien agrega una columna a ambas
    listas por error, este test debe fallar antes que un modelo entrene
    con fuga de datos."""
    assert set(predictor_columns()) & set(TARGET_COLUMNS) == set()
    assert set(predictor_columns()) & set(IDENTIFIER_COLUMNS) == set()
    assert set(TARGET_COLUMNS) & set(IDENTIFIER_COLUMNS) == set()


def test_build_model_dataset_una_fila_por_partido(conn_con_3_partidos):
    df = build_model_dataset(conn_con_3_partidos)

    assert len(df) == 3
    assert set(IDENTIFIER_COLUMNS) <= set(df.columns)
    assert set(predictor_columns()) <= set(df.columns)
    assert set(TARGET_COLUMNS) <= set(df.columns)


def test_build_model_dataset_predictoras_del_tercer_partido_no_tienen_fuga(conn_con_3_partidos):
    """Mismo escenario que test_features_teams.py: el partido 3 es 0-3
    para Team A. Confirma que, ya en el dataset consolidado final, la
    feature predictora no incluye ese marcador."""
    df = build_model_dataset(conn_con_3_partidos)

    tercero = df[df["match_date"] == "2024-08-15 15:00:00"].iloc[0]
    assert tercero["goals_scored_avg_last5_home"] == pytest.approx((2 + 1) / 2)
    assert tercero["home_score"] == 0  # el objetivo SÍ es el marcador real
    assert tercero["result_1x2"] == "A"  # Team B ganó como visitante


def test_save_model_dataset_escribe_csv_y_spec(conn_con_3_partidos, tmp_path: Path):
    df = build_model_dataset(conn_con_3_partidos)
    dataset_path = tmp_path / "model_dataset.csv"
    spec_path = tmp_path / "features_spec.md"

    resultado = save_model_dataset(df, dataset_path, spec_path)

    assert resultado == dataset_path
    assert dataset_path.exists()
    assert spec_path.exists()

    releido = pd.read_csv(dataset_path)
    assert len(releido) == 3

    contenido_spec = spec_path.read_text(encoding="utf-8")
    assert "Hash SHA-256" in contenido_spec
    assert "Filas: 3" in contenido_spec
    for col in predictor_columns():
        assert col in contenido_spec


def test_write_features_spec_hash_cambia_si_el_csv_cambia(tmp_path: Path):
    dataset_path = tmp_path / "model_dataset.csv"
    dataset_path.write_text("a,b\n1,2\n", encoding="utf-8")
    spec_1 = write_features_spec(dataset_path, n_rows=1, spec_path=tmp_path / "spec1.md")
    hash_1 = [l for l in spec_1.read_text().splitlines() if "Hash" in l][0]

    dataset_path.write_text("a,b\n1,3\n", encoding="utf-8")  # mismo tamaño, otro contenido
    spec_2 = write_features_spec(dataset_path, n_rows=1, spec_path=tmp_path / "spec2.md")
    hash_2 = [l for l in spec_2.read_text().splitlines() if "Hash" in l][0]

    assert hash_1 != hash_2
