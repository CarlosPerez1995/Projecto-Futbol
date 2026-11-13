"""Tests de ``src/futbol/config.py`` usando un ``config.yaml`` de prueba.

No hacen ninguna llamada de red: solo leen archivos YAML locales
(el real del repo y uno sintético creado en un directorio temporal).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

from futbol.config import (
    FutbolConfig,
    configure_soccerdata_cache,
    load_config,
    sync_league_dict,
)

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_load_config_lee_config_yaml_de_prueba(tmp_path: Path):
    contenido = """
default_ligas:
  - "ENG-Premier League"
  - "ESP-La Liga"
default_temporadas:
  - "2425"
data_dir: "data/raw"
cache_dir: "data/cache/soccerdata"
log_level: "DEBUG"
"""
    config_path = tmp_path / "config.yaml"
    config_path.write_text(contenido, encoding="utf-8")

    config = load_config(config_path)

    assert isinstance(config, FutbolConfig)
    assert config.default_ligas == ["ENG-Premier League", "ESP-La Liga"]
    assert config.default_temporadas == ["2425"]
    assert config.data_dir == Path("data/raw")
    assert config.cache_dir == Path("data/cache/soccerdata")
    assert config.log_level == "DEBUG"


def test_load_config_coerciona_temporadas_a_string(tmp_path: Path):
    contenido = """
default_ligas:
  - "ENG-Premier League"
default_temporadas:
  - 2425
  - 2526
data_dir: "data/raw"
cache_dir: "data/cache/soccerdata"
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
    assert isinstance(config.cache_dir, Path)


def test_load_config_archivo_inexistente_lanza_error(tmp_path: Path):
    with pytest.raises(FileNotFoundError):
        load_config(tmp_path / "no_existe.yaml")


def test_configure_soccerdata_cache_fija_env_var_absoluta(tmp_path: Path, monkeypatch):
    monkeypatch.delenv("SOCCERDATA_DIR", raising=False)
    monkeypatch.chdir(tmp_path)

    configure_soccerdata_cache(Path("data/cache/soccerdata"))

    assert os.environ["SOCCERDATA_DIR"] == str((tmp_path / "data/cache/soccerdata").resolve())


def test_sync_league_dict_copia_contenido_y_es_idempotente(tmp_path: Path, monkeypatch):
    monkeypatch.setenv("SOCCERDATA_DIR", str(tmp_path / "soccerdata_home"))
    source = tmp_path / "league_dict.json"
    contenido = json.dumps({"TEST-Liga de Prueba": {"Sofascore": "Liga de Prueba"}})
    source.write_text(contenido, encoding="utf-8")

    dest = sync_league_dict(source)

    assert dest == tmp_path / "soccerdata_home" / "config" / "league_dict.json"
    assert dest.read_text(encoding="utf-8") == contenido

    # Segunda corrida: mismo resultado, sin error (idempotente).
    dest_2 = sync_league_dict(source)
    assert dest_2 == dest
    assert dest_2.read_text(encoding="utf-8") == contenido


def test_sync_league_dict_liga_de_prueba_queda_disponible_en_soccerdata(tmp_path: Path):
    """Verifica el criterio de aceptación de la tarea 1.5: sincronizar
    ``config/league_dict.json`` antes de importar ``soccerdata`` hace que
    esa liga quede disponible en ``soccerdata._config.LEAGUE_DICT``.

    Corre en un subproceso aparte (en vez de importar ``soccerdata`` en
    el proceso de pytest) porque ``LEAGUE_DICT`` se calcula una sola vez,
    como código de nivel de módulo, al primer import de
    ``soccerdata._config`` en el proceso.
    """
    source = tmp_path / "league_dict.json"
    source.write_text(
        json.dumps({"TEST-Liga de Prueba": {"Sofascore": "Liga de Prueba"}}),
        encoding="utf-8",
    )
    soccerdata_dir = tmp_path / "soccerdata_home"

    script = (
        "import sys\n"
        "from pathlib import Path\n"
        "from futbol.config import sync_league_dict\n"
        f"sync_league_dict(Path({str(source)!r}))\n"
        "import soccerdata._config as cfg\n"
        "assert 'TEST-Liga de Prueba' in cfg.LEAGUE_DICT, sorted(cfg.LEAGUE_DICT)\n"
        "print('OK')\n"
    )
    resultado = subprocess.run(
        [sys.executable, "-c", script],
        cwd=REPO_ROOT,
        env={**os.environ, "SOCCERDATA_DIR": str(soccerdata_dir)},
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert resultado.returncode == 0, resultado.stderr
    assert "OK" in resultado.stdout
