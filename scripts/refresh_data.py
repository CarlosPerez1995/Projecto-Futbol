#!/usr/bin/env python3
"""Refresco periódico de datos (tarea programada, 17 nov 2026).

Corre extracción → carga a BD → validación → reconstrucción del
dataset, en ese orden, sobre la BD real — sin borrar nada. Los
loaders de ``futbol.db.load_data`` ya son idempotentes (upsert/
``INSERT OR IGNORE``, pensados justo para volver a correr sin romper
lo que ya hay), así que no hace falta recrear la BD desde cero cada
vez, a diferencia de los scripts de un solo uso de esta sesión.

Pensado para correr sin supervisión vía systemd timer (ver
``scripts/systemd/``, decisión de Carlos de automatizar esto una vez
habilitado ``bash: allow`` en OpenCode — aunque este script en
particular NO usa OpenCode: es una secuencia determinista, no hace
falta un agente para ejecutarla). Termina con código de salida
distinto de 0 si la validación encuentra errores nuevos, para que
systemd marque la corrida como fallida y quede visible en
``journalctl``/``systemctl --user status`` — no se trata de "arreglar"
nada solo, se trata de no dejar pasar en silencio un dato roto.
"""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(REPO_ROOT / "src"))

import openpyxl

from futbol.db.database import get_connection, init_db
from futbol.db.load_data import (
    DEFAULT_TEAM_ALIASES_PATH,
    load_fixtures,
    load_leagues,
    load_matches,
    load_odds_1x2,
    load_odds_extra_markets,
    load_seasons,
    load_team_aliases,
    load_xg,
)
from futbol.db.validate_data import run_validation
from futbol.features.dataset import build_model_dataset, save_model_dataset

DB_PATH = REPO_ROOT / "data" / "database" / "futbol.db"
SCHEMA_PATH = REPO_ROOT / "db" / "schema_v4.sql"
# Ruta absoluta al binario del venv, no "futbol-extract" a secas — systemd
# corre con un PATH mínimo que no necesariamente incluye el venv activado.
FUTBOL_EXTRACT = REPO_ROOT / ".venv" / "bin" / "futbol-extract"


def _total_errores(reporte_xlsx: Path) -> int:
    wb = openpyxl.load_workbook(reporte_xlsx, read_only=True)
    ws = wb["resumen"]
    for fila in ws.iter_rows(min_row=2, values_only=True):
        if fila[0] == "total_errores":
            return int(fila[1])
    return 0


def main() -> int:
    print("== 1/4: extracción (futbol-extract) ==", flush=True)
    subprocess.run([str(FUTBOL_EXTRACT)], check=True, cwd=REPO_ROOT)

    print("== 2/4: carga a BD ==", flush=True)
    init_db(DB_PATH, SCHEMA_PATH)
    conn = get_connection(DB_PATH)
    team_aliases = load_team_aliases(DEFAULT_TEAM_ALIASES_PATH)
    print("  leagues:", load_leagues(conn))
    print("  seasons:", load_seasons(conn))
    print("  matches:", load_matches(conn, team_aliases))
    print("  odds 1x2:", load_odds_1x2(conn))
    print("  odds extra:", load_odds_extra_markets(conn))
    print("  fixtures:", load_fixtures(conn, team_aliases))
    print("  xg:", load_xg(conn))
    conn.close()

    print("== 3/4: validación ==", flush=True)
    conn = get_connection(DB_PATH)
    reporte = run_validation(conn)
    conn.close()
    n_errores = _total_errores(reporte)
    print(f"  reporte: {reporte} — {n_errores} error(es)")

    print("== 4/4: reconstrucción del dataset ==", flush=True)
    conn = get_connection(DB_PATH)
    df = build_model_dataset(conn)
    save_model_dataset(df)
    conn.close()
    print(f"  model_dataset.csv reconstruido, {len(df)} filas")

    if n_errores > 0:
        print(f"ERROR: la validación encontró {n_errores} error(es) nuevos — ver {reporte}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
