"""Extracción de datos de fútbol desde Sofascore vía soccerdata.

Script principal de extracción (en refactor). Una sola instancia de
``Sofascore`` se reutiliza para todas las llamadas, tal como exige la
regla 9 de AGENTS.md.

Los DataFrames extraídos se guardan como CSV en ``data/raw/`` con un
timestamp en el nombre de archivo. Por configuración de ``.gitignore``,
la carpeta ``data/`` no se versiona (son datos generados).

Normalizaciones aplicadas a cada DataFrame:
- Nombres de columnas y de niveles del índice en snake_case (sin
  mayúsculas, sin espacios).
- Columnas de fecha/datetime timezone-aware quedan timezone-naive
  (regla de AGENTS.md: ``tz_localize(None)``).
- Validaciones al final: dtypes esperados, sin columnas con espacios
  ni mayúsculas.
"""
from __future__ import annotations

import argparse
import logging
import re
from datetime import datetime
from pathlib import Path

import pandas as pd
import soccerdata as scdat

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


def _save_csv(df: pd.DataFrame, data_dir: Path, nombre: str, ts: str) -> Path:
    """Guarda ``df`` como CSV en ``data_dir`` con nombre ``<nombre>_<ts>.csv``.

    Crea ``data_dir`` si no existe (regla 10 de AGENTS.md). Conserva el
    índice (necesario para DataFrames con MultiIndex de soccerdata).

    Returns:
        Ruta del archivo CSV escrito.
    """
    data_dir.mkdir(parents=True, exist_ok=True)
    archivo = data_dir / f"{nombre}_{ts}.csv"
    df.to_csv(archivo, index=True)
    return archivo


def get_leagues(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae el catálogo de ligas disponibles.

    Normaliza columnas a snake_case y fechas a timezone-naive (no hay
    columnas de fecha en este DataFrame, pero el helper es idempotente).
    """
    df = sofascore.read_leagues()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def get_seasons(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae las temporadas disponibles para la liga configurada."""
    df = sofascore.read_seasons()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def get_standings(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae la tabla de posiciones de la liga/temporada configurada.

    Renombra columnas a snake_case: MP -> mp, W -> w, D -> d, L -> l,
    GF -> gf, GA -> ga, GD -> gd, Pts -> pts.
    """
    df = sofascore.read_league_table()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def get_schedule(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae el calendario de partidos de la liga/temporada configurada.

    La columna ``date`` (datetime64 tz-aware) se normaliza a
    timezone-naive según la nota de AGENTS.md (tz_localize(None)).
    """
    df = sofascore.read_schedule()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def main(liga: str, temporadas: list[str], data_dir: Path | None = None) -> None:
    """Punto de entrada: instancia Sofascore una vez y reutilízalo.

    Extrae ligas, temporadas, posiciones y calendario; guarda cada
    DataFrame como CSV en ``data_dir`` (por defecto ``data/raw/``) con
    un timestamp en el nombre. Al final verifica que la cantidad de
    archivos generados coincida con la cantidad de DataFrames esperados.

    Args:
        liga: código de liga aceptado por soccerdata (p.e. "ENG-Premier League").
        temporadas: listado de códigos de temporada (p.e. ["2425", "2526"]).
        data_dir: carpeta de salida para los CSV (default: data/raw/).
    """
    if data_dir is None:
        data_dir = Path("data/raw")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    # Una sola instancia para toda la sesión (regla 9 de AGENTS.md).
    sofascore = scdat.Sofascore(leagues=liga, seasons=temporadas)

    print("=== Ligas disponibles ===")
    ligas = get_leagues(sofascore)
    ligas.info()

    print("\n=== Temporadas disponibles ===")
    temporadas_df = get_seasons(sofascore)
    temporadas_df.info()

    print("\n=== Tabla de posiciones ===")
    posiciones = get_standings(sofascore)
    posiciones.info()

    print("\n=== Calendario de partidos ===")
    calendario = get_schedule(sofascore)
    calendario.info()

    # Lista única de (nombre, df) para validación + guardado.
    dataframes = [
        ("leagues", ligas),
        ("seasons", temporadas_df),
        ("standings", posiciones),
        ("schedule", calendario),
    ]

    # Validación de naming (snake_case, sin mayúsculas, sin espacios)
    # y log de dtypes esperados por DataFrame.
    for nombre, df in dataframes:
        _log_dtypes(nombre, df)
        _validate(nombre, df)
    print(
        "\nOK: validaciones de naming (snake_case) y dtypes pasaron para "
        f"{len(dataframes)} DataFrames."
    )

    # Guardado en data/raw/ como CSV con timestamp (Tarea 5).
    for nombre, df in dataframes:
        ruta = _save_csv(df, data_dir, nombre, ts)
        print(f"Guardado: {ruta}")

    # Verificación: tantos archivos CSV como DataFrames esperados.
    archivos_csv = sorted(data_dir.glob(f"*_{ts}.csv"))
    assert len(archivos_csv) == len(dataframes), (
        f"Se esperaban {len(dataframes)} CSV en {data_dir} con ts {ts}, "
        f"pero hay {len(archivos_csv)}."
    )
    print(
        f"\nOK: {len(archivos_csv)} archivos CSV generados en {data_dir} "
        f"(esperados: {len(dataframes)})."
    )


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extracción de datos de fútbol desde Sofascore."
    )
    parser.add_argument(
        "--liga",
        type=str,
        default="ENG-Premier League",
        help="Código de liga (p.e. 'ENG-Premier League').",
    )
    parser.add_argument(
        "--temporadas",
        type=str,
        nargs="+",
        default=["2425", "2526"],
        help="Códigos de temporada (p.e. 2425 2526).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=Path("data/raw"),
        help="Carpeta de salida para los CSV (default: data/raw/).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    logging.basicConfig(
        level=logging.INFO,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = parse_args()
    main(liga=args.liga, temporadas=args.temporadas, data_dir=args.data_dir)
