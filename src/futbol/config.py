"""Carga de configuración desde ``config/config.yaml``.

Saca los valores por defecto (ligas, temporadas, ``data_dir``,
``log_level``) del código fuente: cambiar ``config/config.yaml`` cambia
el comportamiento default de ``futbol-extract`` sin tocar ningún ``.py``.
"""
from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path

import yaml

DEFAULT_CONFIG_PATH = Path("config/config.yaml")


@dataclass(frozen=True)
class FutbolConfig:
    default_ligas: list[str]
    default_temporadas: list[str]
    data_dir: Path
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
        log_level=str(raw["log_level"]),
    )
