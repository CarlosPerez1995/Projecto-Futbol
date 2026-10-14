"""Extracción de datos de fútbol desde Understat vía soccerdata.Understat.

Sigue el mismo patrón que ``sofascore.py``/``match_history.py``/``espn.py``:
cada función recibe una instancia ya creada de ``scdat.Understat``
(instanciada por el llamador, no acá) y le aplica la misma normalización
genérica que al resto de las fuentes (``_normalize_columns``,
``_coerce_datetime_columns`` de ``futbol.transform.normalize``, sin
modificarlas).

Cobertura de ligas verificada (tarea 1.7 del plan de robustez,
``Understat.available_leagues()``): las 5 ligas domésticas
(``ENG-Premier League``, ``ESP-La Liga``, ``ITA-Serie A``,
``GER-Bundesliga``, ``FRA-Ligue 1``) tienen clave ``"Understat"`` en
``LEAGUE_DICT`` -- misma cobertura que Sofascore/MatchHistory/ESPN. Las 3
competencias internacionales no están soportadas (mismo patrón ya visto
en ESPN, 1.3).

Comparación explícita Understat vs. FBref para xG/estadísticas de
partido: ver ``docs/understat_vs_fbref.md``.

**Solo ``get_understat_team_match_stats()`` está integrada al flujo
productivo** (``cli.py::run_extraction()``). ``get_understat_shot_events()``
queda implementada -- mismo patrón que el resto -- pero **fuera del
pipeline automático por defecto**, a diferencia de ESPN (1.3) no porque
esté rota, sino por volumen: sin ``match_id``, internamente llama a
``read_schedule()`` y hace una request HTTP por partido (``_read_match``).
Exploración manual real (tarea 1.7, script suelto no versionado) para las
5 ligas domésticas x temporada 2526 (2025-26, la más reciente completa al
2026-08-08, 1752 partidos con datos):

- 1753 requests HTTP totales (1752 partidos + 1 request de cookies inicial
  de sesión), 0 con status distinto de 200, 0 excepciones.
- Tiempo total real: 1565.0s (~26.1 minutos) para esa única temporada.
- Latencia por request: min 0.632s, max 10.713s (un único outlier),
  promedio 0.890s -- sin degradación progresiva a lo largo de la corrida
  (sin patrón de backoff/rate-limit).
- Cobertura: 1752/1752 partidos representados en el resultado (44161
  filas de tiros), sin partidos faltantes.

No hay evidencia de bloqueo o rate-limit de understat.com a este volumen
(todas las requests devolvieron 200 sin reintentos), pero **el volumen en
sí (~26 min para una sola temporada; ~52 min para las 2 temporadas
default de ``config/config.yaml``, la primera vez que se corre con caché
fría) se considera prohibitivo para el flujo automático por defecto**: es
un costo que se paga una sola vez por partido (después queda cacheado en
disco y las corridas siguientes son instantáneas para partidos ya
vistos), pero introduciría una demora de decenas de minutos en cualquier
corrida en frío de ``futbol-extract`` (entorno nuevo, caché limpia, o
temporada nueva agregada a ``config/config.yaml``) para un dato que hoy
es opcional (el xG agregado por partido ya lo cubre
``get_understat_team_match_stats()``, integrada sin condicionamiento).
Queda lista para invocarse manualmente (mismo patrón que
``get_espn_matchsheet()``/``get_espn_lineup()`` en 1.3) el día que se
decida correr un backfill puntual de tiros con ubicación en cancha.
"""
from __future__ import annotations

import pandas as pd
import soccerdata as scdat

from futbol.transform.normalize import _coerce_datetime_columns, _normalize_columns

UNDERSTAT_SOURCE = "understat"


def get_understat_team_match_stats(understat: scdat.Understat) -> pd.DataFrame:
    """Extrae estadísticas de xG por equipo y partido de las ligas/temporadas configuradas.

    Única función de este módulo integrada a ``run_extraction()`` (ver
    docstring del módulo): costo de red bajo, se arma internamente desde
    la respuesta de temporada completa (~1 request por liga x temporada),
    no itera partido por partido. Incluye ``xg``, ``np_xg``
    (xG sin penales), ``np_xg_difference``, ``ppda`` (presión defensiva),
    ``deep_completions``, ``expected_points``, ``goals`` y ``points`` por
    lado (``home_``/``away_``).
    """
    df = understat.read_team_match_stats()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df


def get_understat_shot_events(understat: scdat.Understat) -> pd.DataFrame:
    """Extrae eventos de tiro (xG por tiro, con ubicación en cancha) por partido.

    No integrada al pipeline productivo por defecto: sin ``match_id``,
    hace una request HTTP por partido (del orden de 1700+ para 5 ligas x
    1 temporada, ~26 minutos medidos en la exploración manual de la tarea
    1.7 -- ver docstring del módulo y ``docs/understat_vs_fbref.md``).
    Queda implementada con el mismo patrón que el resto para correr un
    backfill puntual cuando se decida asumir ese costo (una sola vez por
    partido, después queda cacheado).
    """
    df = understat.read_shot_events()
    df = _normalize_columns(df)
    df = _coerce_datetime_columns(df)
    return df
