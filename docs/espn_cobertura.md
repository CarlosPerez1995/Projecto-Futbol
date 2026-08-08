# Cobertura de ESPN sobre las 8 ligas de `LEAGUE_DICT` (tarea 1.3)

Resultado de la exploración manual pedida por el plan de robustez antes
de integrar ESPN al pipeline productivo (`run_extraction()`/`cli.py`).
Script exploratorio (no versionado, corrido contra la red real el
2026-08-08): consultó `soccerdata.ESPN.available_leagues()` y corrió
`read_schedule()` + una muestra de `read_matchsheet()`/`read_lineup()`
sobre datos reales de la temporada 2024-25.

## 1) Cobertura de ligas: 5 de 8

`ESPN.available_leagues()` (calculado por `soccerdata` a partir de qué
ligas de `LEAGUE_DICT` tienen clave `"ESPN"`) devuelve exactamente las 5
ligas domésticas ya usadas por Sofascore/MatchHistory:

| Liga | ¿Soportada por ESPN? | Código ESPN |
| --- | --- | --- |
| `ENG-Premier League` | Sí | `eng.1` |
| `ESP-La Liga` | Sí | `esp.1` |
| `FRA-Ligue 1` | Sí | `fra.1` |
| `GER-Bundesliga` | Sí | `ger.1` |
| `ITA-Serie A` | Sí | `ita.1` |
| `INT-World Cup` | **No** | — (sin clave `"ESPN"` en `LEAGUE_DICT`) |
| `INT-European Championship` | **No** | — |
| `INT-Women's World Cup` | **No** | — |

Las 3 competencias internacionales no están soportadas por esta fuente
en particular — no es un límite de este proyecto, es un dato de
`soccerdata/_config.py::LEAGUE_DICT` (las 3 solo tienen claves `FBref`
y/o `WhoScored`, ninguna trae `"ESPN"`). Como el `default_ligas` de
`config/config.yaml` ya son las 5 ligas domésticas, esto no afecta la
corrida por defecto.

## 2) `read_schedule()`: funciona correctamente

Corrida real para las 5 ligas soportadas, temporada `2425`:

| Liga | Partidos encontrados | Esperado |
| --- | --- | --- |
| `ENG-Premier League` | 380 | 380 (20 equipos, todos contra todos ida y vuelta) |
| `ESP-La Liga` | 380 | 380 |
| `ITA-Serie A` | 380 | 380 |
| `FRA-Ligue 1` | 306 | 306 (18 equipos) |
| `GER-Bundesliga` | 306 | 306 (18 equipos) |

Cobertura completa y consistente con lo esperado. Por eso
`get_espn_schedule()` es la única función de `futbol.ingestion.espn`
integrada a `run_extraction()`.

## 3) `read_matchsheet()` / `read_lineup()`: rotos en `soccerdata==1.9.1`

**Hallazgo crítico, no anticipado por el plan original.** Se probó
`read_matchsheet(match_id=...)` y `read_lineup(match_id=...)` sobre una
muestra de 15 partidos reales (3 por cada una de las 5 ligas
soportadas, temporada 2024-25). **Las 15 fallaron** con:

```
KeyError: 'form'
  File ".../soccerdata/espn.py", line 183, in read_matchsheet
    "team": data["boxscore"]["form"][i]["team"]["displayName"],
```

### Causa raíz (verificada inspeccionando el JSON real de la API)

`soccerdata/espn.py` (líneas 183 y equivalentes en `read_lineup`) espera
que la respuesta de `http://site.api.espn.com/.../summary?event=<id>`
tenga la forma `data["boxscore"]["form"][i]["team"]`. Inspeccionando
directamente uno de los JSON descargados y cacheados
(`data/cache/soccerdata/data/ESPN/Summary_*.json`):

```python
>>> list(data["boxscore"].keys())
['teams']          # no hay clave "form"
>>> list(data["boxscore"]["teams"][0].keys())
['team', 'statistics', 'displayOrder', 'homeAway']
>>> list(data["rosters"][0].keys())
['homeAway', 'winner', 'team', 'roster', 'uniform', 'formation']
```

La API de ESPN ya no devuelve la clave `"form"` dentro de `"boxscore"` —
el nombre de equipo por lado está ahora en
`data["boxscore"]["teams"][i]["team"]` o en `data["rosters"][i]["team"]`.
Es un cambio de esquema de la API de ESPN posterior a cuando se escribió
el parser de `soccerdata==1.9.1`, no un problema de cobertura por liga
ni de este proyecto — y no es corregible sin modificar el código de
`soccerdata` (fuera de alcance de esta tarea: AGENTS.md prohíbe asumir
o parchear comportamiento de librerías externas sin confirmarlo, y
tocar el código de una dependencia externa no es parte del alcance de
1.3).

### Decisión

- `get_espn_matchsheet()` y `get_espn_lineup()` quedan **implementadas**
  en `src/futbol/ingestion/espn.py`, con el mismo patrón que el resto
  de las funciones de extracción (reciben una instancia ya creada del
  lector, aplican `_normalize_columns`/`_coerce_datetime_columns`) — así
  que están listas para usarse el día que se actualice `soccerdata` y
  el problema se corrija upstream.
- **No están integradas a `run_extraction()`/`cli.py`**: wirearlas
  ahora produciría un fallo garantizado en el 100% de las corridas
  (aislado por `try/except`, no rompería el pipeline, pero tampoco
  aportaría ningún dato — solo ruido en los logs). Solo
  `get_espn_schedule()` está en el flujo productivo.
- Revisar este hallazgo si en el futuro se actualiza la versión fijada
  de `soccerdata` en `requirements.txt` (tarea 1.6.1: cualquier upgrade
  requiere revalidación manual) — puede que una versión más nueva ya
  traiga el parser corregido.

## Entregable de esta tarea

Dado el hallazgo de la sección 3, el entregable real de 1.3 es:
`espn_schedule_<ts>.csv` en `data/raw/espn/` (validado con las mismas
funciones de `normalize.py` que el resto de las fuentes) — no
`espn_matchsheet_<ts>.csv`/`espn_lineup_<ts>.csv`, que el plan original
asumía funcionando y que la exploración de esta misma tarea demostró
que no lo están, en la versión de `soccerdata` que usa este proyecto.
