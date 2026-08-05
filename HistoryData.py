"""Extracción de datos de fútbol desde Sofascore vía soccerdata.

Flujo de extracción multi-liga (Frente 1, tareas 1.1 y 1.6 de
``02_Plan_de_Robustez_Fase1_Extraccion.md``). Una sola instancia de
``Sofascore`` se reutiliza para todas las ligas/temporadas de la
corrida, tal como exige la regla 9 de AGENTS.md.

Los DataFrames extraídos se guardan como CSV en
``data/raw/sofascore/`` (subcarpeta por fuente, para dejar sitio
ordenado a futuras fuentes como ``MatchHistory`` o ``ESPN``) con un
timestamp en el nombre de archivo. Por configuración de
``.gitignore``, la carpeta ``data/`` no se versiona (son datos
generados).

Normalizaciones aplicadas a cada DataFrame:
- Nombres de columnas y de niveles del índice en snake_case (sin
  mayúsculas, sin espacios).
- Columnas de fecha/datetime timezone-aware quedan timezone-naive
  (regla de AGENTS.md: ``tz_localize(None)``).
- Validaciones al final: dtypes esperados, sin columnas con espacios
  ni mayúsculas.

Robustez (tarea 1.6 del plan):
- Antes de correr, se filtra la lista de ligas solicitadas contra
  ``Sofascore.available_leagues()`` en vez de asumir que las 8 ligas
  de ``LEAGUE_DICT`` están todas disponibles en esta fuente.
- Un fallo al extraer un dataset puntual no aborta toda la corrida:
  se loguea y se continúa con los demás.
- Antes de guardar, se compara cada DataFrame contra el último CSV
  bueno conocido del mismo dataset para detectar roturas silenciosas
  (0 filas, columnas faltantes, caída drástica de filas).
"""
from __future__ import annotations

import argparse
import logging
import re
from collections.abc import Callable
from datetime import datetime
from pathlib import Path

import pandas as pd
import soccerdata as scdat

logger = logging.getLogger(__name__)

SOFASCORE_SOURCE = "sofascore"

# 5 grandes ligas domésticas (validadas contra Sofascore.available_leagues()
# en tiempo de ejecución por _filter_available_leagues, no asumidas).
DEFAULT_LIGAS = [
    "ENG-Premier League",
    "ESP-La Liga",
    "ITA-Serie A",
    "GER-Bundesliga",
    "FRA-Ligue 1",
]


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


def _filter_available_leagues(ligas: list[str]) -> list[str]:
    """Filtra ``ligas`` a las que Sofascore realmente soporta.

    Tarea 1.1 del plan de robustez: no asumir que las 8 ligas de
    ``LEAGUE_DICT`` están disponibles para esta fuente en particular;
    se consulta ``Sofascore.available_leagues()`` (no hace llamadas de
    red, solo lee el diccionario de configuración) y se loguea un
    warning por cada liga solicitada que no esté soportada.

    Raises:
        ValueError: si ninguna de las ligas solicitadas está disponible.
    """
    disponibles = set(scdat.Sofascore.available_leagues())
    seleccionadas = [liga for liga in ligas if liga in disponibles]
    no_disponibles = [liga for liga in ligas if liga not in disponibles]
    if no_disponibles:
        logger.warning(
            "Ligas solicitadas no disponibles en Sofascore, se omiten: %s",
            no_disponibles,
        )
    if not seleccionadas:
        raise ValueError(
            f"Ninguna de las ligas solicitadas {ligas} está disponible en "
            f"Sofascore. Disponibles: {sorted(disponibles)}"
        )
    return seleccionadas


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
    """Extrae las temporadas disponibles para las ligas configuradas."""
    df = sofascore.read_seasons()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def get_standings(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae la tabla de posiciones de las ligas/temporadas configuradas.

    Renombra columnas a snake_case: MP -> mp, W -> w, D -> d, L -> l,
    GF -> gf, GA -> ga, GD -> gd, Pts -> pts.
    """
    df = sofascore.read_league_table()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def get_schedule(sofascore: scdat.Sofascore) -> pd.DataFrame:
    """Extrae el calendario de partidos de las ligas/temporadas configuradas.

    La columna ``date`` (datetime64 tz-aware) se normaliza a
    timezone-naive según la nota de AGENTS.md (tz_localize(None)).
    """
    df = sofascore.read_schedule()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def main(ligas: list[str], temporadas: list[str], data_dir: Path | None = None) -> None:
    """Punto de entrada: instancia Sofascore una vez y reutilízalo.

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


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Extracción de datos de fútbol desde Sofascore."
    )
    parser.add_argument(
        "--ligas",
        type=str,
        nargs="+",
        default=DEFAULT_LIGAS,
        help=(
            "Códigos de liga a extraer (p.e. 'ENG-Premier League' 'ESP-La Liga'). "
            f"Default: las 5 grandes ligas domésticas ({', '.join(DEFAULT_LIGAS)})."
        ),
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
    main(ligas=args.ligas, temporadas=args.temporadas, data_dir=args.data_dir)
