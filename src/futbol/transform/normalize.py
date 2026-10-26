"""Normalización genérica de DataFrames extraídos de cualquier fuente.

Funciones sin atar a ninguna fuente en particular (Sofascore, ESPN,
MatchHistory, ...): naming de columnas en snake_case, coerción de
fechas timezone-naive, validaciones de naming, guardado a CSV y
detección de rotura silenciosa comparando contra el último CSV bueno
conocido.
"""
from __future__ import annotations

import logging
import re
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)


def _to_snake_case(name: str) -> str:
    """Normaliza un nombre a snake_case.

    Reemplaza espacios y guiones por guion bajo, colapsa guiones bajos
    duplicados y pone todo en minúsculas. Ej: ``"Home Team"`` ->
    ``"home_team"``, ``"MP"`` -> ``"mp"``.
    """
    s = re.sub(r"[\s\-]+", "_", str(name)).strip("_")
    s = re.sub(r"__+", "_", s)
    return s.lower()


def _normalize_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Renombra columnas y niveles del índice a snake_case (inplace-safe)."""
    df = df.rename(columns=lambda c: _to_snake_case(c))
    # Renombrar niveles del índice (puede haber None en algunos niveles).
    nuevos_nombres = [
        (_to_snake_case(n) if n is not None else n) for n in df.index.names
    ]
    df.index.names = nuevos_nombres
    return df


def _coerce_datetime_columns(df: pd.DataFrame) -> pd.DataFrame:
    """Para cada columna datetime tz-aware, la deja timezone-naive.

    Solo actúa sobre columnas cuyo dtype sea datetime y tenga tz.
    Regla de AGENTS.md: ``pd.to_datetime(..., errors='coerce').dt.tz_localize(None)``.
    No inventa columnas: si un DataFrame no tiene fechas, no hace nada.
    """
    for col in df.columns:
        # datetime64[ns, tz] o datetime64[us, tz] -> kind incluye "datetime64"
        if pd.api.types.is_datetime64_any_dtype(df[col]):
            # Si ya es timezone-naive, tz_localize(None) lanzaría error;
            # por eso solo aplicamos si tiene tz.
            try:
                if df[col].dt.tz is not None:
                    df[col] = pd.to_datetime(
                        df[col], errors="coerce"
                    ).dt.tz_localize(None)
            except (TypeError, AttributeError):
                # Columna datetime sin tz (naive) -> dejarla tal cual.
                pass
    return df


def _log_dtypes(nombre: str, df: pd.DataFrame) -> None:
    """Log informativo de dtypes por DataFrame (para verificación)."""
    logger.info("dtypes %s:\n%s", nombre, df.dtypes.to_string())


def _validate(nombre: str, df: pd.DataFrame) -> None:
    """Valida naming: columnas en snake_case, sin mayúsculas, sin espacios.

    Raises:
        AssertionError: si alguna columna o nivel de índice tiene
            mayúsculas, espacios o no está en snake_case.
    """
    malas_cols = [
        c for c in df.columns
        if c != _to_snake_case(c) or " " in str(c) or str(c) != str(c).lower()
    ]
    assert not malas_cols, (
        f"[{nombre}] columnas fuera de snake_case / con mayúsculas "
        f"/ con espacios: {malas_cols}"
    )
    malos_idx = [
        n for n in df.index.names
        if n is not None and (
            n != _to_snake_case(n) or " " in n or n != n.lower()
        )
    ]
    assert not malos_idx, (
        f"[{nombre}] niveles de índice fuera de snake_case: {malos_idx}"
    )
    logger.info("[%s] OK: columnas e índice en snake_case", nombre)


def _save_csv(df: pd.DataFrame, data_dir: Path, source: str, nombre: str, ts: str) -> Path:
    """Guarda ``df`` como CSV en ``data_dir/source/`` con nombre ``<nombre>_<ts>.csv``.

    La subcarpeta por fuente (``source``) mantiene ``data/raw/`` ordenado
    a medida que se sumen más lectores (``MatchHistory``, ``ESPN``, ...)
    sin que sus archivos se mezclen entre sí.

    Crea ``data_dir/source`` si no existe (regla 10 de AGENTS.md). Conserva
    el índice (necesario para DataFrames con MultiIndex de soccerdata).

    Returns:
        Ruta del archivo CSV escrito.
    """
    destino = data_dir / source
    destino.mkdir(parents=True, exist_ok=True)
    archivo = destino / f"{nombre}_{ts}.csv"
    df.to_csv(archivo, index=True)
    return archivo


def _find_ultimo_csv(data_dir: Path, source: str, nombre: str, ts_actual: str) -> Path | None:
    """Devuelve el CSV más reciente de ``nombre`` en ``data_dir/source``.

    Excluye el archivo de la corrida actual (``ts_actual``). Como el
    timestamp en el nombre tiene formato ``%Y%m%d_%H%M%S``, el orden
    alfabético coincide con el orden cronológico.
    """
    carpeta = data_dir / source
    if not carpeta.exists():
        return None
    candidatos = sorted(
        p for p in carpeta.glob(f"{nombre}_*.csv") if not p.name.endswith(f"_{ts_actual}.csv")
    )
    return candidatos[-1] if candidatos else None


def _check_rotura_silenciosa(
    nombre: str, df: pd.DataFrame, data_dir: Path, source: str, ts: str
) -> None:
    """Detecta roturas silenciosas comparando ``df`` con el último CSV bueno.

    Tarea 1.6 del plan de robustez. No aborta la corrida: solo loguea un
    warning si detecta 0 filas, columnas que existían antes y ya no
    aparecen, o una caída drástica (>50%) en la cantidad de filas
    respecto del último archivo bueno conocido del mismo dataset.
    """
    if df.empty:
        logger.warning(
            "[%s/%s] DataFrame vacío (0 filas) - posible rotura de la fuente.",
            source, nombre,
        )
        return

    anterior = _find_ultimo_csv(data_dir, source, nombre, ts)
    if anterior is None:
        return

    try:
        df_anterior = pd.read_csv(anterior)
    except Exception:
        logger.warning("No se pudo leer %s para comparar rotura silenciosa.", anterior)
        return

    columnas_actuales = set(df.reset_index().columns)
    columnas_faltantes = set(df_anterior.columns) - columnas_actuales
    if columnas_faltantes:
        logger.warning(
            "[%s/%s] Columnas presentes en %s pero ausentes ahora: %s",
            source, nombre, anterior.name, sorted(columnas_faltantes),
        )

    if len(df_anterior) > 0 and len(df) < len(df_anterior) * 0.5:
        logger.warning(
            "[%s/%s] Caída drástica de filas: %d (antes: %d en %s).",
            source, nombre, len(df), len(df_anterior), anterior.name,
        )
