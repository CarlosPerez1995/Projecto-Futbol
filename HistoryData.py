"""Extracción de datos de fútbol desde Sofascore vía soccerdata.

Script principal de extracción (en refactor). Una sola instancia de
``Sofascore`` se reutiliza para todas las llamadas, tal como exige la
regla 9 de AGENTS.md.

Los DataFrames extraídos se guardan como CSV en ``data/raw/`` con un
timestamp en el nombre de archivo. Por configuración de ``.gitignore``,
la carpeta ``data/`` no se versiona (son datos generados).
"""
from __future__ import annotations

import argparse
from datetime import datetime
from pathlib import Path

import pandas as pd
import soccerdata as scdat


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
    """Extrae el catálogo de ligas disponibles."""
    return sofascore.read_leagues()


def get_seasons(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae las temporadas disponibles para la liga configurada."""
    return sofascore.read_seasons()


def get_standings(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae la tabla de posiciones de la liga/temporada configurada."""
    return sofascore.read_league_table()


def get_schedule(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae el calendario de partidos de la liga/temporada configurada.

    La columna ``date`` se normaliza a timezone-naive según la nota de
    AGENTS.md (tz_localize(None)).
    """
    calendario = sofascore.read_schedule()
    calendario["date"] = pd.to_datetime(
        calendario["date"], errors="coerce"
    ).dt.tz_localize(None)
    return calendario


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

    # Guardado en data/raw/ como CSV con timestamp (Tarea 5).
    dataframes = [
        ("leagues", ligas),
        ("seasons", temporadas_df),
        ("standings", posiciones),
        ("schedule", calendario),
    ]
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
    args = parse_args()
    main(liga=args.liga, temporadas=args.temporadas, data_dir=args.data_dir)
