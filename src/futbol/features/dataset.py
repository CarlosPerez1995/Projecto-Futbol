"""Dataset consolidado para modelado (tarea 3.3, Fase 3).

Une las features de partido (``compute_match_features``, tarea 3.1) y
de equipo (``compute_team_features``, tarea 3.2) en un solo
``DataFrame``, y las separa explícitamente en dos roles — porque
mezclarlas sin esa distinción es la forma más fácil de terminar
entrenando un modelo con fuga de datos sin darse cuenta:

- **Predictoras** (lo que se sabría ANTES del partido): identificación
  (liga, temporada, fecha, equipos) + todas las features de forma por
  equipo de la tarea 3.2, que ya están construidas sin mirar el propio
  partido (ver ``tests/test_features_teams.py``).
- **Objetivo** (lo que se quiere predecir, solo se conoce DESPUÉS del
  partido): todo lo que sale directo del marcador real — resultado
  1X2, total de goles, los flags de over, BTTS. Viene de
  ``compute_match_features`` (tarea 3.1) y NUNCA debe usarse como
  entrada de un modelo, solo como la respuesta que el modelo tiene que
  aprender a predecir.

Guarda, además del CSV (``model_dataset.csv``), un ``features_spec.md``
con fecha de generación y hash del archivo — divergencia menor ya
anticipada por el plan arquitectónico, para saber más adelante con qué
versión exacta de las features se entrenó cada modelo (si las features
cambian, el hash cambia).
"""
from __future__ import annotations

import hashlib
import sqlite3
from datetime import datetime
from pathlib import Path

import pandas as pd

from futbol.features.matches import compute_match_features
from futbol.features.teams import _FEATURE_COLUMNS, compute_team_features

DEFAULT_OUTPUT_PATH = Path("data/processed/model_dataset.csv")
DEFAULT_SPEC_PATH = Path("data/processed/features_spec.md")

IDENTIFIER_COLUMNS = [
    "match_id", "league_code", "season_code", "match_date", "home_team", "away_team",
]

TARGET_COLUMNS = [
    "home_score", "away_score", "total_goals", "goal_difference",
    "result_1x2", "over_1_5", "over_2_5", "over_3_5", "btts",
    "home_xg", "away_xg",
]


def predictor_columns() -> list[str]:
    return [f"{c}_home" for c in _FEATURE_COLUMNS] + [f"{c}_away" for c in _FEATURE_COLUMNS]


def build_model_dataset(conn: sqlite3.Connection) -> pd.DataFrame:
    """Devuelve el dataset consolidado: una fila por partido jugado,
    columnas de identificación + predictoras + objetivo (ver docstring
    del módulo para qué es cada grupo).
    """
    partido_feats = compute_match_features(conn)
    equipo_feats = compute_team_features(conn)

    assert len(partido_feats) == len(equipo_feats), (
        "build_model_dataset: compute_match_features y compute_team_features "
        "devolvieron distinta cantidad de filas — no debería pasar si ambas "
        "parten de la misma consulta de partidos jugados."
    )

    columnas_equipo_sin_duplicar = [
        c for c in equipo_feats.columns if c not in IDENTIFIER_COLUMNS
    ]
    df = partido_feats.merge(
        equipo_feats[["match_id"] + columnas_equipo_sin_duplicar],
        on="match_id", how="inner",
    )
    assert len(df) == len(partido_feats), (
        "build_model_dataset: el merge cambió la cantidad de filas — "
        "indicaría match_id duplicados en algún lado."
    )

    orden = IDENTIFIER_COLUMNS + predictor_columns() + TARGET_COLUMNS
    orden = [c for c in orden if c in df.columns]
    return df[orden]


def write_features_spec(
    dataset_path: Path,
    n_rows: int,
    spec_path: Path = DEFAULT_SPEC_PATH,
) -> Path:
    """Escribe ``features_spec.md`` con fecha de generación, cantidad de
    filas y hash SHA-256 del CSV ya guardado en ``dataset_path``.
    """
    hash_csv = hashlib.sha256(dataset_path.read_bytes()).hexdigest()
    ahora = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    predictoras = predictor_columns()

    lineas_predictoras = "\n".join(f"- `{c}`" for c in predictoras)
    lineas_objetivo = "\n".join(f"- `{c}`" for c in TARGET_COLUMNS)

    texto = f"""# Especificación de features — {dataset_path.name}

Generado: {ahora}
Filas: {n_rows}
Hash SHA-256 del CSV: `{hash_csv}`

Si se regenera este archivo con los mismos datos de entrada, el hash
debería salir idéntico; si cambia, significa que las features (el
código de `src/futbol/features/`) o los datos de la BD cambiaron desde
la última vez que se entrenó un modelo con esta versión.

## Columnas predictoras (lo que un modelo puede usar como entrada)

{lineas_predictoras}

## Columnas objetivo (lo que un modelo debe aprender a predecir — NUNCA como entrada)

{lineas_objetivo}

Detalle de cada columna: ver `docs/features_map.txt`.
"""
    spec_path.parent.mkdir(parents=True, exist_ok=True)
    spec_path.write_text(texto, encoding="utf-8")
    return spec_path


def save_model_dataset(
    df: pd.DataFrame,
    dataset_path: Path = DEFAULT_OUTPUT_PATH,
    spec_path: Path = DEFAULT_SPEC_PATH,
) -> Path:
    """Guarda ``df`` en ``dataset_path`` y escribe ``features_spec.md``
    junto a él (crea la carpeta contenedora si hace falta).
    """
    dataset_path.parent.mkdir(parents=True, exist_ok=True)
    df.to_csv(dataset_path, index=False)
    write_features_spec(dataset_path, len(df), spec_path)
    return dataset_path
