"""Extracción de datos de fútbol desde Sofascore vía soccerdata.

Script principal de extracción (en refactor). Una sola instancia de
``Sofascore`` se reutiliza para todas las llamadas, tal como exige la
regla 9 de AGENTS.md.

El guardado en ``data/raw/`` se implementation en la Tarea 5; por ahora
este script solo extrae y muestra info de los DataFrames.
"""
from __future__ import annotations

import argparse
from pathlib import Path

import pandas as pd
import soccerdata as scdat


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

    Args:
        liga: código de liga aceptado por soccerdata (p.e. "ENG-Premier League").
        temporadas: listado de códigos de temporada (p.e. ["2425", "2526"]).
        data_dir: carpeta de salida (reservada para la Tarea 5, sin uso por ahora).
    """
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

    # El guardado en data/raw/ se implementa en la Tarea 5.
    if data_dir is not None:
        print(
            f"\n(data_dir={data_dir} reservado para la Tarea 5: guardado en "
            f"data/raw/ aún no implementado)"
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
        default=None,
        help="Carpeta de salida (reservada Tarea 5).",
    )
    return parser.parse_args()


if __name__ == "__main__":
    args = parse_args()
    main(liga=args.liga, temporadas=args.temporadas, data_dir=args.data_dir)
