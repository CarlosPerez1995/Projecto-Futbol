"""Script de validación de datos (tarea 2.4, Fase 2).

Corre contra el estado actual de la BD (requiere que
``load_leagues``/``load_seasons``/``load_matches``/``load_odds_1x2``/
``load_fixtures`` ya hayan corrido — no vuelve a leer ``data/raw/``)
las 5 validaciones del plan arquitectónico: % de nulos por columna,
duplicados en ``matches``, rango lógico de fecha, scores no negativos
e integridad referencial. Genera
``data/reports/validation_<fecha>.xlsx`` con hoja ``resumen`` y hoja
``errores`` — ``openpyxl`` ya es dependencia del proyecto, no hay que
instalar nada nuevo (ver AGENTS.md).

Los checks de duplicados/fecha/score son específicos de ``matches``
(el plan arquitectónico no pide equivalentes para ``fixtures``/``odds``,
que ya tienen su propia protección contra duplicados vía ``UNIQUE`` con
``captured_at`` — ver ``db/schema_v3.sql``); el de nulos sí corre sobre
``fixtures`` porque ya tiene loader (``load_fixtures``, 14 oct).
"""
from __future__ import annotations

import sqlite3
from datetime import date
from pathlib import Path

import openpyxl

DEFAULT_REPORT_DIR = Path("data/reports")

# Tablas sobre las que se mide % de nulos por columna.
_TABLAS_PARA_NULOS = ("matches", "odds", "teams", "fixtures")


def _null_percentages(conn: sqlite3.Connection, table: str) -> dict[str, float]:
    """% de filas con ``NULL`` por columna de ``table``.

    ``table``/columnas vienen de ``PRAGMA table_info`` (nombres fijos
    del esquema versionado, no datos externos) — interpolarlos en el
    SQL es seguro acá, no es el mismo caso que interpolar un valor que
    viniera de un CSV o de un usuario.
    """
    columnas = [row[1] for row in conn.execute(f"PRAGMA table_info({table})")]
    total = conn.execute(f"SELECT COUNT(*) FROM {table}").fetchone()[0]
    if total == 0:
        return {}
    porcentajes = {}
    for col in columnas:
        nulos = conn.execute(f"SELECT COUNT(*) FROM {table} WHERE {col} IS NULL").fetchone()[0]
        porcentajes[col] = nulos / total * 100
    return porcentajes


def _duplicados_matches(conn: sqlite3.Connection) -> list[tuple]:
    """Filas de ``matches`` con la misma llave natural completa
    (season/home/away/fecha exacta) más de una vez.

    No debería pasar nunca si ``resolve_or_create_match`` funciona bien
    (ver ``load_data.py``) — es una red de seguridad, no se espera que
    encuentre nada en operación normal.
    """
    return conn.execute(
        """
        SELECT season_id, home_team_id, away_team_id, match_date, COUNT(*) AS n
        FROM matches
        GROUP BY season_id, home_team_id, away_team_id, match_date
        HAVING COUNT(*) > 1
        """
    ).fetchall()


def _fechas_fuera_de_rango(
    conn: sqlite3.Connection, year_min: int = 1920, year_max: int = 2100
) -> list[tuple]:
    return conn.execute(
        "SELECT match_id, match_date FROM matches "
        "WHERE CAST(strftime('%Y', match_date) AS INTEGER) < ? "
        "OR CAST(strftime('%Y', match_date) AS INTEGER) > ?",
        (year_min, year_max),
    ).fetchall()


def _scores_negativos(conn: sqlite3.Connection) -> list[tuple]:
    return conn.execute(
        "SELECT match_id, home_score, away_score FROM matches "
        "WHERE home_score < 0 OR away_score < 0"
    ).fetchall()


def _fks_huerfanas(conn: sqlite3.Connection) -> list[tuple]:
    """``PRAGMA foreign_key_check`` — debería venir siempre vacío porque
    las FKs están activas desde ``get_connection`` (``PRAGMA foreign_keys
    = ON``), pero el criterio de aceptación de la tarea 2.4 pide
    reportarlo explícitamente, no solo confiar en que nunca falle.
    """
    return conn.execute("PRAGMA foreign_key_check;").fetchall()


def run_validation(
    conn: sqlite3.Connection,
    report_dir: Path = DEFAULT_REPORT_DIR,
    today: date | None = None,
) -> Path:
    """Corre las 5 validaciones y genera el reporte Excel. Devuelve la
    ruta del archivo generado.
    """
    today = today or date.today()
    report_dir.mkdir(parents=True, exist_ok=True)

    duplicados = _duplicados_matches(conn)
    fuera_de_rango = _fechas_fuera_de_rango(conn)
    negativos = _scores_negativos(conn)
    huerfanas = _fks_huerfanas(conn)

    errores: list[tuple[str, str, str]] = []
    for season_id, home_id, away_id, match_date, n in duplicados:
        errores.append((
            "matches", "duplicado",
            f"season_id={season_id} home_team_id={home_id} away_team_id={away_id} "
            f"match_date={match_date} ({n} filas)",
        ))
    for match_id, match_date in fuera_de_rango:
        errores.append(("matches", "fecha_fuera_de_rango", f"match_id={match_id} match_date={match_date}"))
    for match_id, home_score, away_score in negativos:
        errores.append((
            "matches", "score_negativo",
            f"match_id={match_id} home_score={home_score} away_score={away_score}",
        ))
    for fila in huerfanas:
        errores.append((str(fila[0]), "fk_huerfana", str(fila)))

    resumen: list[tuple[str, object]] = [
        ("total_matches", conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0]),
        ("total_odds", conn.execute("SELECT COUNT(*) FROM odds").fetchone()[0]),
        ("total_teams", conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]),
        ("matches_duplicados", len(duplicados)),
        ("fechas_fuera_de_rango", len(fuera_de_rango)),
        ("scores_negativos", len(negativos)),
        ("fks_huerfanas", len(huerfanas)),
        ("total_errores", len(errores)),
    ]
    for tabla in _TABLAS_PARA_NULOS:
        for col, pct in _null_percentages(conn, tabla).items():
            resumen.append((f"pct_nulos_{tabla}.{col}", round(pct, 2)))

    wb = openpyxl.Workbook()
    ws_resumen = wb.active
    ws_resumen.title = "resumen"
    ws_resumen.append(["métrica", "valor"])
    for metrica, valor in resumen:
        ws_resumen.append([metrica, valor])

    ws_errores = wb.create_sheet("errores")
    ws_errores.append(["tabla", "check", "detalle"])
    for tabla, check, detalle in errores:
        ws_errores.append([tabla, check, detalle])

    path = report_dir / f"validation_{today.isoformat()}.xlsx"
    wb.save(path)
    return path
