# Understat vs. FBref para xG/estadísticas de partido (tarea 1.7)

Comparación explícita, requerida por el plan de robustez antes de fijar
el alcance de la integración de Understat, entre lo que aporta Understat
y lo que aportaría FBref para el mismo tipo de dato (xG/estadísticas de
partido). La decisión de priorizar Understat sobre FBref ya estaba
tomada en la tarea 1.4 (ver `docs/evaluacion_proveedores_soccerdata.md`);
esta tabla la aplica en código con evidencia concreta a nivel de
métodos, inspeccionando el código instalado
(`.venv/lib/python3.13/site-packages/soccerdata/understat.py` y
`soccerdata/fbref.py`) el 2026-08-08.

## Métodos relevantes

**Understat** (`BaseRequestsReader`, sin Selenium):
- `read_team_match_stats()`: una fila por equipo×partido con `xg`,
  `np_xg` (xG sin penales), `np_xg_difference`, `ppda` (presión
  defensiva), `deep_completions`, `expected_points`, `goals`, `points` —
  ya indexado por `league/season/game`. Costo de red bajo: se arma
  internamente desde la respuesta de temporada completa (~1 request por
  liga×temporada), no itera partido por partido.
- `read_shot_events()`: una fila por tiro, con `xg`, `location_x`/
  `location_y`, `body_part`, `situation`, `result`, jugador que remata y
  que asiste — el dato más granular y diferencial (ningún otro lector ya
  integrado en este proyecto da posición de tiro). Costo de red alto sin
  `match_id`: internamente llama a `read_schedule()` y hace una request
  HTTP por partido (`_read_match`).

**FBref** (`BaseSeleniumReader`, con Selenium/Chrome):
- `read_team_match_stats(stat_type=...)` con `stat_type` en `{"schedule",
  "shooting", "keeper", "misc"}` — no existe un `stat_type` de xG
  dedicado con el mismo detalle que Understat; el dato de tiros/xG vive
  dentro de `stat_type="shooting"`, mezclado con otras columnas, y exige
  una llamada HTTP (vía Selenium) por cada `stat_type` que se quiera, no
  una sola llamada como Understat.
- No tiene un equivalente directo a `read_shot_events()` con coordenadas
  de tiro — FBref expone eventos más generales vía `read_events()`
  (goles, tarjetas, sustituciones), no remates individuales con ubicación
  en cancha.

## Tabla comparativa

| Dimensión | Understat | FBref | ¿Redundante o valor agregado? |
|---|---|---|---|
| xG por tiro con ubicación en cancha | `read_shot_events()` — método directo | No existe un método equivalente en esta librería | **Understat aporta algo que FBref no tiene.** No son redundantes entre sí en esta dimensión. |
| xG/npxG agregado por partido | `read_team_match_stats()` — un solo método, ya agregado | Disponible dentro de `stat_type="shooting"` de `read_team_match_stats()`, con columnas de contexto adicionales (p. ej. distancia promedio de tiro), pero mezclado con otras métricas de esa categoría | Parcialmente redundante — misma señal (xG de equipo por partido). Understat la da más simple y barata; FBref la da con más detalle pero a mayor costo (Selenium) y riesgo (rotura no uniforme documentada, issue `#880`, ver `docs/evaluacion_proveedores_soccerdata.md`). |
| Estadísticas de posesión/pases/duelos por partido | No disponible en Understat | Disponible en FBref (categorías de passing/defense/possession, según qué `stat_type` soporte la versión instalada) | FBref aporta algo que Understat no tiene — pero **fuera del alcance de esta tarea**: el objetivo acá es xG, no reemplazar a FBref por completo. Si en el futuro se necesitan específicamente esas estadísticas, es una tarea nueva a evaluar aparte, no una reapertura de 1.4. |
| Riesgo de infraestructura | Bajo (HTTP puro, mismo patrón que Sofascore/MatchHistory/ESPN, ya en producción) | Alto (Selenium + Chrome, rotura documentada no uniforme entre ligas) | Understat gana en costo/riesgo para el mismo tipo de señal (xG). |

**Conclusión operativa:** se integra Understat para xG. FBref **no** se
integra en esta tarea — sigue con prioridad Media según 1.4, sin
cambios.

## Cobertura de ligas verificada

`Understat.available_leagues()` devuelve exactamente las 5 ligas
domésticas ya usadas por Sofascore/MatchHistory/ESPN:

| Liga | ¿Soportada por Understat? |
| --- | --- |
| `ENG-Premier League` | Sí |
| `ESP-La Liga` | Sí |
| `FRA-Ligue 1` | Sí |
| `GER-Bundesliga` | Sí |
| `ITA-Serie A` | Sí |
| `INT-World Cup` | No |
| `INT-European Championship` | No |
| `INT-Women's World Cup` | No |

Las 3 competencias internacionales no tienen clave `"Understat"` en
`LEAGUE_DICT` — mismo patrón ya visto en ESPN (1.3). Como
`default_ligas` de `config/config.yaml` ya son las 5 ligas domésticas,
esto no afecta la corrida por defecto.

## Exploración de volumen de `read_shot_events()` (medida, no estimada)

Script suelto, no versionado como parte del pipeline, corrido contra la
red real el 2026-08-08: `Understat(leagues=<5 ligas domésticas>,
seasons=["2526"])`, la temporada más reciente completa a esa fecha (todas
sus 1752 partidos con `is_result=True`; la temporada `2627` recién
empezaba y no forma parte de `default_temporadas`).

**Fase A — `read_schedule(include_matches_without_data=False)`:**
- 12.0s, 1752 partidos con datos (`ENG-Premier League` 380,
  `ESP-La Liga` 380, `ITA-Serie A` 380, `FRA-Ligue 1` 306,
  `GER-Bundesliga` 306).

**Fase B — `read_shot_events()` sin `match_id` (instrumentando cada
request HTTP real vía `session.get`):**

| Métrica | Valor medido |
| --- | --- |
| Requests HTTP totales | 1753 (1752 partidos + 1 request de cookies inicial de sesión) |
| Tiempo total | 1565.0s (≈ 26.1 minutos) |
| Latencia por request | min 0.632s / max 10.713s (un único outlier) / promedio 0.890s |
| Requests con status ≠ 200 | 0 |
| Excepciones durante la corrida | 0 |
| Filas de tiros obtenidas | 44161 |
| Partidos cubiertos en el resultado | 1752 / 1752 (100%) |

No se observó degradación progresiva de latencia a lo largo de la
corrida (sin patrón de backoff/rate-limit) ni ningún código de error —
**no hay evidencia de bloqueo o rate-limit de understat.com a este
volumen**. Sin embargo, el volumen en sí (~26 minutos para una sola
temporada) se considera **prohibitivo para el flujo automático por
defecto**: `config/config.yaml` trae dos temporadas por defecto (`2425`
y `2526`), así que una corrida en frío de `futbol-extract` que incluyera
`read_shot_events()` sin condicionar sumaría del orden de ~52 minutos
extra la primera vez que corre (entorno nuevo, caché limpia, o una
temporada nueva agregada a la configuración). Es un costo que se paga
una sola vez por partido — `soccerdata` cachea en disco cada
`match_<id>.json`, así que las corridas siguientes son instantáneas para
partidos ya vistos — pero introduciría una demora impredecible y
desproporcionada en cualquier corrida en frío del pipeline productivo,
para un dato que hoy es opcional (el xG agregado por partido ya lo cubre
`get_understat_team_match_stats()`, que sí está integrada sin
condicionamiento por su bajo costo de red).

## Decisión de alcance

- `get_understat_team_match_stats(understat)` **integrada** sin
  condicionamiento a `run_extraction()`/`cli.py` — mismo criterio que
  `get_espn_schedule()` en 1.3 (costo de red bajo, ~1 request por
  liga×temporada).
- `get_understat_shot_events(understat)` **implementada** en
  `src/futbol/ingestion/understat.py`, con el mismo patrón que el resto
  de las funciones de extracción, pero **no integrada al pipeline
  productivo por defecto** — mismo criterio ya usado con
  `get_espn_matchsheet()`/`get_espn_lineup()` en 1.3, aunque acá la razón
  es volumen medido, no una rotura de la librería. Queda lista para
  correr un backfill manual puntual cuando se decida asumir ese costo
  (una sola vez por temporada, después queda cacheado).
