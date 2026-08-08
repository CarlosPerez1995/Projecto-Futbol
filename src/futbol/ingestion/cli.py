"""CLI de extracción de datos de fútbol (entry point ``futbol-extract``).

Delgado: orquesta las funciones de extracción de
``futbol.ingestion.sofascore`` y de normalización/guardado de
``futbol.transform.normalize``, sin reimplementar su lógica.

Los DataFrames extraídos se guardan como CSV en
``data/raw/sofascore/`` (subcarpeta por fuente, para dejar sitio
ordenado a futuras fuentes como ``MatchHistory`` o ``ESPN``) con un
timestamp en el nombre de archivo. Por configuración de
``.gitignore``, la carpeta ``data/`` no se versiona (son datos
generados).

Robustez (tarea 1.6 del plan):
- Antes de correr, se filtra la lista de ligas solicitadas contra
  ``Sofascore.available_leagues()`` en vez de asumir que las 8 ligas
  de ``LEAGUE_DICT`` están soportadas por esta fuente en particular.
- Un fallo al extraer un dataset puntual no aborta toda la corrida:
  se loguea y se continúa con los demás.
- Antes de guardar, se compara cada DataFrame contra el último CSV
  bueno conocido del mismo dataset para detectar roturas silenciosas
  (0 filas, columnas faltantes, caída drástica de filas).
- La caché de ``soccerdata`` (por defecto ``~/soccerdata``, fuera del
  repo) se redirige a ``cache_dir`` de ``config/config.yaml`` (default
  ``data/cache/soccerdata``) vía ``SOCCERDATA_DIR``, fijada al importar
  este módulo, antes de importar ``soccerdata``.
"""
from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from futbol.config import FutbolConfig, configure_soccerdata_cache, load_config

# Tarea 1.6.3 del plan de robustez: la caché de soccerdata se configura
# acá, antes de importar `soccerdata` (o `futbol.ingestion.sofascore`,
# que lo importa) — `soccerdata/_config.py` lee `SOCCERDATA_DIR` como
# código de nivel de módulo al importarse, así que fijar la variable de
# entorno después de esos imports no tendría efecto.
configure_soccerdata_cache(load_config().cache_dir)

import pandas as pd  # noqa: E402
import soccerdata as scdat  # noqa: E402

from futbol.ingestion.sofascore import (  # noqa: E402
    SOFASCORE_SOURCE,
    _filter_available_leagues,
    get_leagues,
    get_schedule,
    get_seasons,
    get_standings,
)
from futbol.transform.normalize import (  # noqa: E402
    _check_rotura_silenciosa,
    _log_dtypes,
    _save_csv,
    _validate,
)

logger = logging.getLogger(__name__)


def run_extraction(ligas: list[str], temporadas: list[str], data_dir: Path | None = None) -> None:
    """Instancia Sofascore una vez y reutilízalo para toda la corrida.

    Extrae ligas, temporadas, posiciones y calendario para todas las
    ``ligas``/``temporadas`` solicitadas en una sola corrida (soccerdata
    hace el producto cruzado internamente), y guarda cada DataFrame como
    CSV en ``data_dir/sofascore/`` (por defecto ``data/raw/sofascore/``)
    con un timestamp en el nombre.

    Robustez (tarea 1.6 del plan): un fallo al extraer un dataset
    puntual se loguea y no aborta el resto de la corrida; antes de
    guardar se compara cada DataFrame contra el último CSV bueno
    conocido para detectar roturas silenciosas de la fuente.

    Args:
        ligas: códigos de liga aceptados por soccerdata
            (p.e. ["ENG-Premier League", "ESP-La Liga"]).
        temporadas: listado de códigos de temporada (p.e. ["2425", "2526"]).
        data_dir: carpeta base de salida para los CSV (default: data/raw/).
    """
    if data_dir is None:
        data_dir = Path("data/raw")
    ts = datetime.now().strftime("%Y%m%d_%H%M%S")

    ligas = _filter_available_leagues(ligas)
    logger.info("Ligas seleccionadas para esta corrida: %s", ligas)

    # Una sola instancia para toda la sesión (regla 9 de AGENTS.md),
    # compartida entre todas las ligas/temporadas de la corrida.
    sofascore = scdat.Sofascore(leagues=ligas, seasons=temporadas)

    extractores: list[tuple[str, str, Callable[[scdat.Sofascore], pd.DataFrame]]] = [
        ("leagues", "Ligas disponibles", get_leagues),
        ("seasons", "Temporadas disponibles", get_seasons),
        ("standings", "Tabla de posiciones", get_standings),
        ("schedule", "Calendario de partidos", get_schedule),
    ]

    # Extracción con aislamiento de fallos: un lector que falla no debe
    # abortar la corrida completa de los demás (tarea 1.6 del plan).
    resultados: list[tuple[str, pd.DataFrame]] = []
    fallos: list[str] = []
    for nombre, titulo, extractor in extractores:
        print(f"\n=== {titulo} ===")
        try:
            df = extractor(sofascore)
        except Exception:
            logger.exception(
                "Fallo al extraer '%s' - se omite y se continúa con las demás fuentes.",
                nombre,
            )
            fallos.append(nombre)
            continue
        df.info()
        resultados.append((nombre, df))

    if not resultados:
        raise RuntimeError(
            f"Todas las extracciones fallaron ({fallos}). Ver logs para detalle."
        )

    # Validación de naming (snake_case, sin mayúsculas, sin espacios)
    # y log de dtypes esperados por DataFrame.
    for nombre, df in resultados:
        _log_dtypes(nombre, df)
        _validate(nombre, df)
    print(
        "\nOK: validaciones de naming (snake_case) y dtypes pasaron para "
        f"{len(resultados)} DataFrames."
    )

    # Detección de rotura silenciosa + guardado en data/raw/sofascore/.
    for nombre, df in resultados:
        _check_rotura_silenciosa(nombre, df, data_dir, SOFASCORE_SOURCE, ts)
        ruta = _save_csv(df, data_dir, SOFASCORE_SOURCE, nombre, ts)
        print(f"Guardado: {ruta}")

    # Verificación: tantos archivos CSV como DataFrames extraídos con éxito.
    destino = data_dir / SOFASCORE_SOURCE
    archivos_csv = sorted(destino.glob(f"*_{ts}.csv"))
    assert len(archivos_csv) == len(resultados), (
        f"Se esperaban {len(resultados)} CSV en {destino} con ts {ts}, "
        f"pero hay {len(archivos_csv)}."
    )
    print(
        f"\nOK: {len(archivos_csv)} archivos CSV generados en {destino} "
        f"(esperados: {len(resultados)})."
    )

    if fallos:
        print(f"\nAVISO: {len(fallos)} fuente(s) fallaron y se omitieron: {fallos}")


def parse_args(config: FutbolConfig | None = None) -> argparse.Namespace:
    if config is None:
        config = load_config()
    parser = argparse.ArgumentParser(
        description="Extracción de datos de fútbol desde Sofascore."
    )
    parser.add_argument(
        "--ligas",
        type=str,
        nargs="+",
        default=config.default_ligas,
        help=(
            "Códigos de liga a extraer (p.e. 'ENG-Premier League' 'ESP-La Liga'). "
            f"Default (config/config.yaml): {', '.join(config.default_ligas)}."
        ),
    )
    parser.add_argument(
        "--temporadas",
        type=str,
        nargs="+",
        default=config.default_temporadas,
        help="Códigos de temporada (p.e. 2425 2526).",
    )
    parser.add_argument(
        "--data-dir",
        type=Path,
        default=config.data_dir,
        help=f"Carpeta de salida para los CSV (default: {config.data_dir}).",
    )
    return parser.parse_args()


def main() -> None:
    """Entry point de ``futbol-extract``: carga config, configura logging, parsea args y ejecuta."""
    config = load_config()
    logging.basicConfig(
        level=getattr(logging, config.log_level.upper(), logging.INFO),
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )
    args = parse_args(config)
    run_extraction(ligas=args.ligas, temporadas=args.temporadas, data_dir=args.data_dir)


if __name__ == "__main__":
    main()
