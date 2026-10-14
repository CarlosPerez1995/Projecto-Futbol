"""Extracción de datos de fútbol desde ESPN vía soccerdata.ESPN.

Sigue el mismo patrón que ``sofascore.py``: cada función recibe una
instancia ya creada de ``scdat.ESPN`` (instanciada por el llamador, no
acá) y le aplica la misma normalización genérica que al resto de las
fuentes (``_normalize_columns``, ``_coerce_datetime_columns`` de
``futbol.transform.normalize``, sin modificarlas).

Cobertura verificada (tarea 1.3 del plan de robustez) — ver
``docs/espn_cobertura.md`` para el detalle completo de la exploración:

- ESPN solo cubre 5 de las 8 ligas de ``LEAGUE_DICT`` (las 5 ligas
  domésticas: Premier League, La Liga, Serie A, Bundesliga, Ligue 1).
  Las 3 competencias internacionales (``INT-World Cup``,
  ``INT-European Championship``, ``INT-Women's World Cup``) no tienen
  clave ``"ESPN"`` en ``LEAGUE_DICT`` -- no están soportadas por esta
  fuente en particular.
- ``read_schedule()`` funciona correctamente para las 5 ligas
  soportadas (verificado con datos reales de la temporada 2024-25:
  cantidad de partidos por liga coincide con lo esperado).
- **``read_matchsheet()`` y ``read_lineup()`` están rotos en
  ``soccerdata==1.9.1`` contra la API actual de ESPN**: fallan con
  ``KeyError: 'form'`` en el 100% de una muestra de 15 partidos (3 por
  cada una de las 5 ligas soportadas). Verificado inspeccionando
  directamente el JSON de respuesta de la API
  (``http://site.api.espn.com/.../summary?event=<id>``): el código
  instalado espera ``data["boxscore"]["form"][i]["team"]``, pero la
  respuesta actual de ESPN ya no trae la clave ``"form"`` dentro de
  ``"boxscore"`` (solo trae ``"teams"``; el nombre de equipo por lado
  está en ``data["boxscore"]["teams"][i]["team"]`` o en
  ``data["rosters"][i]["team"]``). Es una incompatibilidad entre la
  versión de la librería fijada en ``requirements.txt`` y la API real
  de ESPN, no un problema de este proyecto ni algo corregible sin
  tocar el código de ``soccerdata`` -- fuera de alcance de esta tarea.

Por ese motivo, **solo ``get_espn_schedule()`` está integrada al flujo
productivo** (``cli.py::run_extraction()``). ``get_espn_matchsheet()``
y ``get_espn_lineup()`` quedan implementadas -- mismo patrón que el
resto, listas para usarse el día que se actualice ``soccerdata`` y el
problema se corrija upstream -- pero no se invocan desde el pipeline
para no acumular fallos garantizados en cada corrida.
"""
from __future__ import annotations

import pandas as pd
import soccerdata as scdat

from futbol.transform.normalize import _coerce_datetime_columns, _normalize_columns

ESPN_SOURCE = "espn"


def get_espn_schedule(espn: scdat.ESPN) -> pd.DataFrame:
    """Extrae el calendario de partidos de las ligas/temporadas configuradas.

    Única función de este módulo integrada a ``run_extraction()`` (ver
    docstring del módulo): es la única que se verificó funcionando
    contra datos reales.
    """
    df = espn.read_schedule()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def get_espn_matchsheet(espn: scdat.ESPN) -> pd.DataFrame:
    """Extrae la ficha de partido (estadísticas por equipo) vía ESPN.

    No integrada al pipeline productivo: ``soccerdata==1.9.1`` rompe con
    ``KeyError: 'form'`` contra la API actual de ESPN (ver docstring del
    módulo). Queda implementada con el mismo patrón que el resto para
    cuando se corrija upstream.
    """
    df = espn.read_matchsheet()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def get_espn_lineup(espn: scdat.ESPN) -> pd.DataFrame:
    """Extrae las alineaciones de partido vía ESPN.

    No integrada al pipeline productivo: ``soccerdata==1.9.1`` rompe con
    ``KeyError: 'form'`` contra la API actual de ESPN (ver docstring del
    módulo). Queda implementada con el mismo patrón que el resto para
    cuando se corrija upstream.
    """
    df = espn.read_lineup()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df
