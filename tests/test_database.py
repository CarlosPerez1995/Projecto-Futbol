"""Tests de ``src/futbol/db/database.py`` contra una BD SQLite temporal.

No hacen ninguna llamada de red: solo usan ``sqlite3`` (stdlib) y
``db/schema_v3.sql`` del propio repo.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import pytest

from futbol.db.database import close_connection, get_connection, init_db

REPO_SCHEMA_PATH = Path(__file__).resolve().parent.parent / "db" / "schema_v3.sql"


def test_get_connection_crea_carpeta_contenedora_y_activa_foreign_keys(tmp_path: Path):
    db_path = tmp_path / "subcarpeta" / "futbol.db"

    conn = get_connection(db_path)
    try:
        assert db_path.parent.is_dir()
        assert conn.execute("PRAGMA foreign_keys;").fetchone()[0] == 1
    finally:
        close_connection(conn)


def test_close_connection_cierra_la_conexion(tmp_path: Path):
    conn = get_connection(tmp_path / "futbol.db")
    close_connection(conn)

    with pytest.raises(sqlite3.ProgrammingError):
        conn.execute("SELECT 1;")


def test_init_db_crea_todas_las_tablas_de_schema_v3(tmp_path: Path):
    db_path = tmp_path / "futbol.db"

    init_db(db_path, REPO_SCHEMA_PATH)

    conn = get_connection(db_path)
    try:
        tablas = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
    finally:
        close_connection(conn)

    assert {
        "leagues", "seasons", "teams", "team_source_ids",
        "matches", "match_source_ids", "fixtures", "odds", "pipeline_runs",
    } <= tablas


def test_init_db_segunda_corrida_es_idempotente(tmp_path: Path):
    db_path = tmp_path / "futbol.db"

    init_db(db_path, REPO_SCHEMA_PATH)
    init_db(db_path, REPO_SCHEMA_PATH)  # no debe lanzar "table already exists"

    conn = get_connection(db_path)
    try:
        cantidad = conn.execute(
            "SELECT COUNT(*) FROM sqlite_master WHERE type = 'table'"
        ).fetchone()[0]
    finally:
        close_connection(conn)

    assert cantidad >= 9


def test_init_db_aplica_integridad_referencial_de_verdad(tmp_path: Path):
    db_path = tmp_path / "futbol.db"
    init_db(db_path, REPO_SCHEMA_PATH)

    conn = get_connection(db_path)
    try:
        with pytest.raises(sqlite3.IntegrityError):
            conn.execute(
                "INSERT INTO seasons (league_id, code) VALUES (999, '2425');"
            )
            conn.commit()
    finally:
        close_connection(conn)
