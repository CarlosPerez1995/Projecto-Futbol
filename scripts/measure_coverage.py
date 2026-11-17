#!/usr/bin/env python3
"""Medición periódica de cobertura de tests (tarea programada, 17 nov
2026) — tarea 6.3 del plan ("Cobertura de tests ≥40%"), para saber qué
falta sin tener que arrancar de cero cuando llegue el momento de
cerrarla.

Secuencia determinista (correr pytest con --cov), no necesita un
agente — igual criterio que ``refresh_data.py``. Guarda un reporte
fechado en ``data/reports/`` (JSON crudo de coverage.py + un resumen en
texto) y termina con código de salida 0 siempre (bajar cobertura no es
un "error" del pipeline como sí lo es un dato roto en
``refresh_data.py`` — es información para que el jefe de proyecto
decida qué priorizar, no algo que deba marcar la corrida como
fallida).
"""
from __future__ import annotations

import json
import subprocess
import sys
from datetime import date
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
REPORT_DIR = REPO_ROOT / "data" / "reports"
UMBRAL_OBJETIVO_PCT = 40.0


def main() -> int:
    REPORT_DIR.mkdir(parents=True, exist_ok=True)
    hoy = date.today().isoformat()
    json_path = REPORT_DIR / f"coverage_{hoy}.json"
    resumen_path = REPORT_DIR / f"coverage_{hoy}.txt"

    print("== Corriendo pytest --cov ==", flush=True)
    resultado = subprocess.run(
        [
            str(REPO_ROOT / ".venv" / "bin" / "python3"), "-m", "pytest",
            str(REPO_ROOT / "tests"),
            "--cov=futbol",
            "--cov-report=term-missing",
            f"--cov-report=json:{json_path}",
            "-q",
        ],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    print(resultado.stdout)
    if resultado.returncode != 0:
        print(resultado.stderr, file=sys.stderr)
        print("ERROR: la suite de tests no pasó — no tiene sentido confiar "
              "en la cobertura de una corrida con tests rotos.", file=sys.stderr)
        return 1

    data = json.loads(json_path.read_text(encoding="utf-8"))
    total_pct = data["totals"]["percent_covered"]

    bajo_umbral = []
    for archivo, info in data["files"].items():
        pct = info["summary"]["percent_covered"]
        if pct < UMBRAL_OBJETIVO_PCT:
            bajo_umbral.append((archivo, pct, info["summary"]["missing_lines"]))
    bajo_umbral.sort(key=lambda fila: fila[1])

    lineas = [
        f"Cobertura total: {total_pct:.1f}% (objetivo del plan: >= {UMBRAL_OBJETIVO_PCT:.0f}%)",
        f"¿Cumple el objetivo?: {'Sí' if total_pct >= UMBRAL_OBJETIVO_PCT else 'No'}",
        "",
        f"Archivos bajo el {UMBRAL_OBJETIVO_PCT:.0f}% ({len(bajo_umbral)}):",
    ]
    for archivo, pct, missing in bajo_umbral:
        lineas.append(f"  {pct:5.1f}%  {archivo}  ({missing} líneas sin cubrir)")
    if not bajo_umbral:
        lineas.append("  (ninguno)")

    resumen = "\n".join(lineas)
    resumen_path.write_text(resumen + "\n", encoding="utf-8")
    print("\n" + resumen)
    print(f"\nReporte completo: {json_path}")
    print(f"Resumen: {resumen_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
