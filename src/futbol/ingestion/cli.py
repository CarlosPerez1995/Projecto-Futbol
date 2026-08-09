"""CLI de extracción de datos de fútbol (entry point ``futbol-extract``).

Delgado: orquesta las funciones de extracción de
``futbol.ingestion.sofascore``/``futbol.ingestion.match_history``/
``futbol.ingestion.espn`` y de normalización/guardado de
``futbol.transform.normalize``, sin reimplementar su lógica.

Los DataFrames extraídos se guardan como CSV en ``data/raw/<fuente>/``
(subcarpeta por fuente: ``data/raw/sofascore/``, ``data/raw/match_history/``,
``data/raw/espn/``) con un timestamp en el nombre de archivo, común a
todas las fuentes de la misma corrida. Por configuración de
``.gitignore``, la carpeta ``data/`` no se versiona (son datos
generados).

Robustez (tarea 1.6 del plan):
- Antes de correr, se filtra la lista de ligas solicitadas contra
  ``Sofascore.available_leagues()`` en vez de asumir que las 8 ligas
  de ``LEAGUE_DICT`` están soportadas por esta fuente en particular.
- Un fallo al extraer un dataset puntual (o una fuente entera, como
  MatchHistory) no aborta toda la corrida: se loguea y se continúa con
  los demás.
- Antes de guardar, se compara cada DataFrame contra el último CSV
  bueno conocido del mismo dataset para detectar roturas silenciosas
  (0 filas, columnas faltantes, caída drástica de filas).
- La caché de ``soccerdata`` (por defecto ``~/soccerdata``, fuera del
  repo) se redirige a ``cache_dir`` de ``config/config.yaml`` (default
  ``data/cache/soccerdata``) vía ``SOCCERDATA_DIR``, fijada al importar
  este módulo, antes de importar ``soccerdata``.
- El diccionario de ligas custom versionado (``config/league_dict.json``,
  esquema en ``config/league_dict.md``) se sincroniza hacia
  ``$SOCCERDATA_DIR/config/league_dict.json`` al importar este módulo,
  también antes de importar ``soccerdata`` (tarea 1.5 del plan).

Fuentes (tarea 2.1 / 1.2 del plan): además de ``Sofascore``, se extrae
``MatchHistory`` (resultados + cuotas históricas de football-data.co.uk)
en la misma corrida y con el mismo timestamp. Es una instancia separada
de ``Sofascore`` -- son lectores distintos del paquete ``soccerdata``,
la regla 9 de AGENTS.md ("una sola instancia por sesión") aplica por
lector, no exige una única instancia entre lectores.

Fuentes (tarea 1.3 del plan): también se extrae el calendario de ESPN
(``get_espn_schedule``), instancia separada, misma corrida/timestamp.
Solo el calendario está integrado acá -- la exploración manual previa
(ver ``docs/espn_cobertura.md``) confirmó que ``read_matchsheet()`` y
``read_lineup()`` de ``soccerdata==1.9.1`` están rotos contra la API
actual de ESPN (``KeyError: 'form'`` en el 100% de una muestra real),
así que esas dos funciones quedan implementadas en
``futbol.ingestion.espn`` pero fuera del pipeline productivo hasta que
se corrija upstream.

Fuentes (tarea 1.7 del plan): también se extrae xG por equipo y partido
de Understat (``get_understat_team_match_stats``), instancia separada,
misma corrida/timestamp. Solo esta función está integrada acá -- la
exploración manual previa (ver ``docs/understat_vs_fbref.md``) midió
~26 minutos y 1753 requests HTTP para que
``get_understat_shot_events()`` cubra una sola temporada de las 5 ligas
(sin errores ni señales de rate-limit, pero volumen prohibitivo para el
flujo automático por defecto), así que esa función queda implementada
en ``futbol.ingestion.understat`` pero fuera del pipeline productivo,
disponible para un backfill manual puntual.
"""
from __future__ import annotations

import argparse
import logging
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

from futbol.config import (
    FutbolConfig,
    configure_soccerdata_cache,
    load_config,
    sync_league_dict,
)

# Tareas 1.6.3 y 1.5 del plan de robustez: la caché y el diccionario de
# ligas custom de soccerdata se configuran acá, antes de importar
# `soccerdata` (o `futbol.ingestion.sofascore`, que lo importa) —
# `soccerdata/_config.py` lee `SOCCERDATA_DIR` y mergea
# `league_dict.json` como código de nivel de módulo al importarse
# (verificado en el código instalado y de forma empírica: ver
# docstrings de ambas funciones en `futbol.config`), así que hacer esto
# después de esos imports no tendría ningún efecto. Nota: esto difiere
# de "invocar sync_league_dict() al inicio de main()" tal como lo
# describe el plan original — se verificó que para esta base de código
# (donde `import soccerdata` ya ocurre a nivel de módulo, antes de que
# `main()` se ejecute) esa ubicación sería tarde.
configure_soccerdata_cache(load_config().cache_dir)
sync_league_dict()

import pandas as pd  # noqa: E402
import soccerdata as scdat  # noqa: E402

from futbol.ingestion.espn import (  # noqa: E402
    ESPN_SOURCE,
    get_espn_schedule,
)
from futbol.ingestion.match_history import (  # noqa: E402
    MATCH_HISTORY_SOURCE,
    get_match_history,
)
from futbol.ingestion.sofascore import (  # noqa: E402
    SOFASCORE_SOURCE,
    _filter_available_leagues,
    get_leagues,
    get_schedule,
    get_seasons,
    get_standings,
)
from futbol.ingestion.understat import (  # noqa: E402
    UNDERSTAT_SOURCE,
    get_understat_team_match_stats,
)
from futbol.transform.normalize import (  # noqa: E402
    _check_rotura_silenciosa,
    _log_dtypes,
    _save_csv,
    _validate,
)

logger = logging.getLogger(__name__)


def run_extraction(ligas: list[str], temporadas: list[str], data_dir: Path | None = None) -> None:
    """Instancia Sofascore, MatchHistory, ESPN y Understat (por separado) y extrae todo en la misma corrida.

    Extrae ligas, temporadas, posiciones y calendario de Sofascore,
    resultados + cuotas históricas de MatchHistory (football-data.co.uk,
    tarea 2.1 / 1.2 del plan), calendario de ESPN (tarea 1.3 del plan) y
    xG por equipo y partido de Understat (tarea 1.7 del plan), para las
    mismas ``ligas``/``temporadas`` solicitadas, en una sola corrida con
    un timestamp común. Cada DataFrame se guarda como CSV en
    ``data_dir/<fuente>/`` (por defecto ``data/raw/sofascore/``,
    ``data/raw/match_history/``, ``data/raw/espn/`` y
    ``data/raw/understat/``).

    Robustez (tarea 1.6 del plan, extendida a MatchHistory en 2.1, a
    ESPN en 1.3 y a Understat en 1.7): un fallo al extraer un dataset
    puntual (o una fuente entera) se loguea y no aborta el resto de la
    corrida; antes de guardar se compara cada DataFrame contra el último
    CSV bueno conocido del mismo dataset para detectar roturas
    silenciosas de la fuente.

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

    # Una sola instancia de Sofascore para toda la sesión (regla 9 de
    # AGENTS.md), compartida entre todas las ligas/temporadas de la
    # corrida.
    sofascore = scdat.Sofascore(leagues=ligas, seasons=temporadas)

    extractores: list[tuple[str, str, Callable[[scdat.Sofascore], pd.DataFrame]]] = [
        ("leagues", "Ligas disponibles", get_leagues),
        ("seasons", "Temporadas disponibles", get_seasons),
        ("standings", "Tabla de posiciones", get_standings),
        ("schedule", "Calendario de partidos", get_schedule),
    ]

    # Extracción con aislamiento de fallos: un lector que falla no debe
    # abortar la corrida completa de los demás (tarea 1.6 del plan).
    # Cada resultado guarda también su fuente, para poder guardarlo en
    # `data/raw/<fuente>/` más abajo sin asumir una única fuente.
    resultados: list[tuple[str, str, pd.DataFrame]] = []  # (source, nombre, df)
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
        resultados.append((SOFASCORE_SOURCE, nombre, df))

    # MatchHistory (tarea 2.1 / 1.2 del plan): instancia separada de
    # Sofascore -- son lectores distintos, la regla 9 de AGENTS.md de
    # instancia única aplica por lector, no entre lectores -- pero misma
    # corrida y mismo timestamp `ts`. Aislada en su propio try/except
    # (mismo patrón de la tarea 1.6.4): un fallo acá no afecta lo ya
    # extraído de Sofascore arriba.
    print("\n=== Resultados y cuotas históricas (MatchHistory) ===")
    try:
        match_history = scdat.MatchHistory(leagues=ligas, seasons=temporadas)
        df_match_history = get_match_history(match_history)
    except Exception:
        logger.exception(
            "Fallo al extraer 'match_history' - se omite y se continúa con "
            "las demás fuentes."
        )
        fallos.append("match_history")
    else:
        df_match_history.info()
        resultados.append((MATCH_HISTORY_SOURCE, "match_history", df_match_history))

    # ESPN (tarea 1.3 del plan): instancia separada, misma corrida y
    # mismo timestamp `ts`, aislada en su propio try/except. Solo el
    # calendario (`get_espn_schedule`) -- la exploración manual previa
    # confirmó que `read_matchsheet()`/`read_lineup()` están rotos en
    # soccerdata==1.9.1 contra la API actual de ESPN (ver
    # docs/espn_cobertura.md y el docstring de futbol.ingestion.espn),
    # así que no se invocan acá para no acumular fallos garantizados.
    print("\n=== Calendario de partidos (ESPN) ===")
    try:
        espn = scdat.ESPN(leagues=ligas, seasons=temporadas)
        df_espn_schedule = get_espn_schedule(espn)
    except Exception:
        logger.exception(
            "Fallo al extraer 'espn_schedule' - se omite y se continúa con "
            "las demás fuentes."
        )
        fallos.append("espn_schedule")
    else:
        df_espn_schedule.info()
        resultados.append((ESPN_SOURCE, "espn_schedule", df_espn_schedule))

    # Understat (tarea 1.7 del plan): instancia separada, misma corrida y
    # mismo timestamp `ts`, aislada en su propio try/except. Solo xG por
    # equipo y partido (`get_understat_team_match_stats`) -- la
    # exploración manual previa (ver docs/understat_vs_fbref.md y el
    # docstring de futbol.ingestion.understat) midió ~26 minutos y 1753
    # requests HTTP para que `get_understat_shot_events()` cubra una sola
    # temporada, así que esa función no se invoca acá para no inflar la
    # duración de cada corrida del pipeline productivo.
    print("\n=== xG por equipo y partido (Understat) ===")
    try:
        understat = scdat.Understat(leagues=ligas, seasons=temporadas)
        df_understat_team_match_stats = get_understat_team_match_stats(understat)
    except Exception:
        logger.exception(
            "Fallo al extraer 'understat_team_match_stats' - se omite y se "
            "continúa con las demás fuentes."
        )
        fallos.append("understat_team_match_stats")
    else:
        df_understat_team_match_stats.info()
        resultados.append(
            (UNDERSTAT_SOURCE, "understat_team_match_stats", df_understat_team_match_stats)
        )

    if not resultados:
        raise RuntimeError(
            f"Todas las extracciones fallaron ({fallos}). Ver logs para detalle."
        )

    # Validación de naming (snake_case, sin mayúsculas, sin espacios)
    # y log de dtypes esperados por DataFrame.
    for _source, nombre, df in resultados:
        _log_dtypes(nombre, df)
        _validate(nombre, df)
    print(
        "\nOK: validaciones de naming (snake_case) y dtypes pasaron para "
        f"{len(resultados)} DataFrames."
    )

    # Detección de rotura silenciosa + guardado en data/raw/<fuente>/.
    for source, nombre, df in resultados:
        _check_rotura_silenciosa(nombre, df, data_dir, source, ts)
        ruta = _save_csv(df, data_dir, source, nombre, ts)
        print(f"Guardado: {ruta}")

    # Verificación: tantos archivos CSV como DataFrames extraídos con
    # éxito, por fuente (cada fuente se guarda en su propia subcarpeta,
    # así que se verifican por separado).
    fuentes = sorted({source for source, _nombre, _df in resultados})
    for source in fuentes:
        destino = data_dir / source
        esperados = sum(1 for s, _n, _d in resultados if s == source)
        archivos_csv = sorted(destino.glob(f"*_{ts}.csv"))
        assert len(archivos_csv) == esperados, (
            f"Se esperaban {esperados} CSV en {destino} con ts {ts}, "
            f"pero hay {len(archivos_csv)}."
        )
        print(
            f"\nOK: {len(archivos_csv)} archivos CSV generados en {destino} "
            f"(esperados: {esperados})."
        )

    if fallos:
        print(f"\nAVISO: {len(fallos)} fuente(s) fallaron y se omitieron: {fallos}")


def parse_args(config: FutbolConfig | None = None) -> argparse.Namespace:
    if config is None:
        config = load_config()
    parser = argparse.ArgumentParser(
        description="Extracción de datos de fútbol desde Sofascore, MatchHistory, ESPN y Understat."
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
