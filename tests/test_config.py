"""Tests de ``src/futbol/config.py`` usando un ``config.yaml`` de prueba.

No hacen ninguna llamada de red: solo leen archivos YAML locales
(el real del repo y uno sintético creado en un directorio temporal).
"""
from __future__ import annotations

from pathlib import Path

import pytest

from futbol.config import FutbolConfig, load_config


def test_load_config_lee_config_yaml_de_prueba(tmp_path: Path):
    contenido = """
default_ligas:
  - "ENG-Premier League"
  - "ESP-La Liga"
default_temporadas:
  - "2425"
data_dir: "data/raw"
log_level: "DEBUG"
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(contenido, encoding="utf-8")

    config = load_config(config_path)

    assert isinstance(config, FutbolConfig)
    assert config.default_ligas == ["ENG-Premier League", "ESP-La Liga"]
    assert config.default_temporadas == ["2425"]
    assert config.data_dir == Path("data/raw")
    assert config.log_level == "DEBUG"


def test_load_config_coerciona_temporadas_a_string(tmp_path: Path):
    contenido = """
default_ligas:
  - "ENG-Premier League"
default_temporadas:
  - 2425
  - 2526
data_dir: "data/raw"
log_level: "INFO"
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(contenido, encoding="utf-8")

    config = load_config(config_path)

    assert config.default_temporadas == ["2425", "2526"]
    assert all(isinstance(t, str) for t in config.default_temporadas)


def test_load_config_default_path_usa_config_real_del_repo():
    config = load_config()

    assert isinstance(config, FutbolConfig)
    assert config.default_ligas
    assert config.default_temporadas
    assert isinstance(config.data_dir, Path)


def test_load_config_archivo_inexistente_lanza_error(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "no_existe.yaml")
