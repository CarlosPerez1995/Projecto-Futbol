"""Conexión y creación de la base de datos SQLite (tarea 2.2, Fase 2).

Aplica ``db/schema_v3.sql`` (ver ese archivo para el diseño y por qué
es v3 y no v1/v2 — histórico completo de ``odds`` y ``fixtures``, a
pedido de Carlos, 13-14 oct) sobre ``data/database/futbol.db``.
``sqlite3`` es parte de la stdlib, no hay dependencia nueva que
instalar (ver AGENTS.md).
"""
from __future__ import annotations

import logging
import sqlite3
from pathlib import Path

logger = logging.getLogger(__name__)

DEFAULT_DB_PATH = Path("data/database/futbol.db")
DEFAULT_SCHEMA_PATH = Path("db/schema_v3.sql")

# Tablas que crea schema_v3.sql (mismo set que v1, ver ese archivo) —
# usadas para decidir si init_db() ya corrió antes (idempotencia) sin
# depender de IF NOT EXISTS en el .sql versionado.
_EXPECTED_TABLES = {
    "leagues",
    "seasons",
    "teams",
    "team_source_ids",
    "matches",
    "match_source_ids",
    "fixtures",
    "odds",
    "pipeline_runs",
}


def get_connection(db_path: Path = DEFAULT_DB_PATH) -> sqlite3.Connection:
    """Abre una conexión a ``db_path``, creando la carpeta contenedora si
    hace falta (regla 10 de AGENTS.md) y con ``PRAGMA foreign_keys`` activado
    (SQLite lo trae desactivado por default; sin esto las FKs de
    ``schema_v1.sql`` no se harían cumplir).
    """
    db_path.parent.mkdir(parents=True, exist_ok=True)
    conn = sqlite3.connect(db_path)
    conn.execute("PRAGMA foreign_keys = ON;")
    return conn


def close_connection(conn: sqlite3.Connection) -> None:
    """Cierra una conexión abierta con ``get_connection``."""
    conn.close()


def init_db(
    db_path: Path = DEFAULT_DB_PATH,
    schema_path: Path = DEFAULT_SCHEMA_PATH,
) -> None:
    """Crea las tablas de ``schema_path`` en ``db_path`` si todavía no existen.

    Idempotente: si las tablas de ``_EXPECTED_TABLES`` ya están presentes,
    no vuelve a ejecutar el esquema (criterio de aceptación de la tarea
    2.2: una segunda corrida no debe lanzar error).
    """
    conn = get_connection(db_path)
    try:
        existentes = {
            row[0]
            for row in conn.execute("SELECT name FROM sqlite_master WHERE type = 'table'")
        }
        if _EXPECTED_TABLES <= existentes:
            logger.info(
                "init_db: %s ya tiene las %d tablas esperadas, no se vuelve a aplicar el esquema",
                db_path,
                len(_EXPECTED_TABLES),
            )
            return
        schema_sql = schema_path.read_text(encoding="utf-8")
        conn.executescript(schema_sql)
        conn.commit()
        logger.info("init_db: esquema de %s aplicado en %s", schema_path, db_path)
    except sqlite3.Error:
        logger.exception("init_db: fallo aplicando %s sobre %s", schema_path, db_path)
        raise
    finally:
        close_connection(conn)
