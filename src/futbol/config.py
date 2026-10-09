"""Carga de configuración desde ``config/config.yaml``.

Saca los valores por defecto (ligas, temporadas, ``data_dir``,
``cache_dir``, ``log_level``) del código fuente: cambiar
``config/config.yaml`` cambia el comportamiento default de
``futbol-extract`` sin tocar ningún ``.py``.

También expone la configuración explícita del área de ``soccerdata``
regida por ``SOCCERDATA_DIR`` (tareas 1.6.3 y 1.5 del plan de
robustez): ``configure_soccerdata_cache`` fija la caché en una ruta del
repo, y ``sync_league_dict`` copia el diccionario de ligas custom
versionado (``config/league_dict.json``) hacia la ubicación real que
``soccerdata`` espera. Ambas deben llamarse antes de importar
``soccerdata`` en cualquier módulo (ver sus docstrings).
"""
from __future__ import annotations

import os
from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("config/config.yaml")
DEFAULT_LEAGUE_DICT_PATH = Path("config/league_dict.json")


@dataclass(frozen=True)
class FutbolConfig:
    default_ligas: list[str]
    default_temporadas: list[str]
    data_dir: Path
    cache_dir: Path
    log_level: str


def load_config(path: Path | None = None) -> FutbolConfig:
    """Carga un YAML de configuración y devuelve un ``FutbolConfig`` tipado.

    Args:
        path: ruta al YAML de configuración (default:
            ``config/config.yaml`` relativo al directorio de trabajo
            actual, igual convención que ``--data-dir`` en la CLI).
    """
    if path is None:
        path = DEFAULT_CONFIG_PATH
    with open(path, encoding="utf-8") as f:
        raw = yaml.safe_load(f)
    return FutbolConfig(
        default_ligas=list(raw["default_ligas"]),
        default_temporadas=[str(t) for t in raw["default_temporadas"]],
        data_dir=Path(raw["data_dir"]),
        cache_dir=Path(raw["cache_dir"]),
        log_level=str(raw["log_level"]),
    )


def configure_soccerdata_cache(cache_dir: Path) -> None:
    """Fija ``SOCCERDATA_DIR`` para que la caché de ``soccerdata`` viva en
    ``cache_dir`` en vez del default (``~/soccerdata``, fuera del repo).

    Debe llamarse antes de que ``soccerdata`` (o cualquier módulo que lo
    importe, como ``futbol.ingestion.sofascore``) se importe por primera
    vez en el proceso: ``soccerdata/_config.py`` lee ``SOCCERDATA_DIR``
    como código de nivel de módulo al momento del import (verificado en
    ``.venv/lib/python3.13/site-packages/soccerdata/_config.py`` líneas
    21-24), así que fijar la variable de entorno después de ese import
    no tendría ningún efecto.
    """
    os.environ["SOCCERDATA_DIR"] = str(cache_dir.resolve())


def sync_league_dict(source_path: Path | None = None) -> Path:
    """Copia ``config/league_dict.json`` (versionado en el repo) hacia la
    ubicación real que ``soccerdata`` espera:
    ``$SOCCERDATA_DIR/config/league_dict.json`` (default ``SOCCERDATA_DIR``:
    ``~/soccerdata``, igual lógica que ``configure_soccerdata_cache``, sin
    importar el símbolo privado ``soccerdata._config.CONFIG_DIR``).

    Debe llamarse antes de que ``soccerdata`` (o cualquier módulo que lo
    importe) se importe por primera vez en el proceso: verificado en el
    código instalado (``soccerdata/_config.py`` líneas 183-192) y de forma
    empírica que ``soccerdata`` lee y mergea ese archivo con ``LEAGUE_DICT``
    como código de nivel de módulo al momento del import — sincronizar
    después de ese import no tiene ningún efecto, porque el módulo ya
    queda cacheado en ``sys.modules`` con ``LEAGUE_DICT`` calculado.

    Idempotente: sobreescribe el archivo destino con el contenido exacto
    de ``source_path`` en cada llamada, sin error si ya existe.

    Args:
        source_path: ruta al ``league_dict.json`` versionado en el repo
            (default: ``config/league_dict.json`` relativo al directorio
            de trabajo actual).

    Returns:
        La ruta destino donde quedó escrito el archivo.
    """
    if source_path is None:
        source_path = DEFAULT_LEAGUE_DICT_PATH
    base_dir = Path(os.environ.get("SOCCERDATA_DIR", Path.home() / "soccerdata"))
    dest_path = base_dir / "config" / "league_dict.json"
    dest_path.parent.mkdir(parents=True, exist_ok=True)
    dest_path.write_text(source_path.read_text(encoding="utf-8"), encoding="utf-8")
    return dest_path
