# Mapeo de columnas de cuotas de `MatchHistory` (football-data.co.uk)

Documenta el significado de las columnas de cuotas que trae
`soccerdata.MatchHistory.read_games()` (fuente: football-data.co.uk),
para que la Fase 3 (features) del plan arquitectónico no tenga que
volver a investigar football-data.co.uk desde cero.

**Fuente oficial:** <https://www.football-data.co.uk/notes.txt>
(citada en el propio docstring de `soccerdata.MatchHistory.read_games`).
Este documento resume esa fuente y agrega una advertencia empírica
propia de este proyecto (ver más abajo).

## Advertencia: el esquema de columnas NO es fijo entre temporadas

Comprobado extrayendo las 5 grandes ligas configuradas por defecto
(`config/config.yaml`) para las temporadas `2425` y `2526` con la misma
corrida: **118 columnas en 2425 vs. 130 en 2526**, con 27 columnas que
solo aparecen en una u otra. Ejemplos:
- Solo en `2425`: `1XBH`/`1XBD`/`1XBA` (1XBet) y sus variantes de
  cierre (`1XBCH`, ...), `WHH`/`WHD`/`WHA` (William Hill) y sus
  variantes de cierre, `BFH`/`BFD`/`BFA` (Betfair) y sus variantes.
- Solo en `2526`: `BFDH`/`BFDD`/`BFDA` (Betfred), `BMGMH`/`BMGMD`/`BMGMA`
  (BetMGM), `BVH`/`BVD`/`BVA` (Betvictor), `CLH`/`CLD`/`CLA` (Coral),
  `LBH`/`LBD`/`LBA` (Ladbrokes).

Por eso `get_match_history()` en `src/futbol/ingestion/match_history.py`
loguea (`_log_odds_columns`) qué columnas de cuotas aparecieron
**realmente** en cada corrida, en vez de que el código asuma un esquema
fijo. Cualquier trabajo de features (Fase 3) que dependa de una casa de
apuestas puntual debe verificar contra ese log (o el CSV generado) que
la columna exista en la corrida que esté usando, no asumir que siempre
está.

## Sufijos: resultado (H/D/A)

Cada prefijo de casa de apuestas trae 3 columnas para el resultado 1X2:

| Sufijo | Significado |
| --- | --- |
| `H` | Cuota de victoria del equipo local (home win) |
| `D` | Cuota de empate (draw) |
| `A` | Cuota de victoria del equipo visitante (away win) |

## Prefijos: casa de apuestas (cuotas de cierre pre-cierre / resultado 1X2)

| Prefijo | Casa de apuestas |
| --- | --- |
| `1XB` | 1XBet |
| `B365` | Bet365 |
| `BF` | Betfair |
| `BFD` | Betfred |
| `BMGM` | BetMGM |
| `BV` | Betvictor |
| `BS` | Blue Square |
| `BW` | Bet&Win |
| `CL` | Coral |
| `GB` | Gamebookers |
| `IW` | Interwetten |
| `LB` | Ladbrokes |
| `PP` | Paddy Power |
| `PS` / `P` | Pinnacle |
| `SK` | Skybet |
| `SO` | Sporting Odds |
| `SB` | Sportingbet |
| `SJ` | Stan James |
| `SY` | Stanleybet |
| `VC` | VC Bet (ahora BetVictor) |
| `WH` | William Hill |
| `BFE` | Betfair Exchange |

Agregados de mercado (no son una casa de apuestas puntual):

| Prefijo | Significado |
| --- | --- |
| `Max` | Cuota máxima del mercado (entre todas las casas relevadas) |
| `Avg` | Cuota promedio del mercado |
| `Bb1X2` | Cantidad de casas de apuestas usadas por Betbrain para calcular `BbMx*`/`BbAv*` (histórico, dataset antiguo) |
| `BbMx` / `BbAv` | Máximo / promedio calculado por Betbrain (histórico) |

## Sufijo `C`: cuotas de cierre (closing odds)

Agregar una `C` después del prefijo de la casa (o de `Max`/`Avg`) indica
que es la cuota de **cierre**, en vez de la cuota pre-cierre por
defecto. Ejemplo: `B365H` = cuota pre-cierre de Bet365 para victoria
local; `B365CH` = cuota de **cierre** de Bet365 para victoria local.

## Mercado de goles totales (over/under 2.5)

| Columna | Significado |
| --- | --- |
| `B365>2.5` / `B365<2.5` | Bet365: over / under 2.5 goles |
| `P>2.5` / `P<2.5` | Pinnacle: over / under 2.5 goles |
| `Max>2.5` / `Max<2.5` | Máximo de mercado: over / under 2.5 goles |
| `Avg>2.5` / `Avg<2.5` | Promedio de mercado: over / under 2.5 goles |
| `BbOU` | Cantidad de casas usadas por Betbrain para este mercado (histórico) |
| `BbMx>2.5` / `BbMx<2.5` | Máximo Betbrain: over / under 2.5 goles (histórico) |
| `BbAv>2.5` / `BbAv<2.5` | Promedio Betbrain: over / under 2.5 goles (histórico) |

Igual que en el mercado 1X2, agregar `C` indica cuota de cierre
(`B365C>2.5`, `MaxC>2.5`, etc.).

## Mercado de hándicap asiático

| Columna | Significado |
| --- | --- |
| `AHh` | Tamaño del hándicap de mercado (equipo local), desde 2019/2020 |
| `B365AHH` / `B365AHA` | Bet365: cuota de hándicap asiático local / visitante |
| `B365AH` | Bet365: tamaño del hándicap (equipo local) |
| `PAHH` / `PAHA` | Pinnacle: cuota de hándicap asiático local / visitante |
| `MaxAHH` / `MaxAHA` | Máximo de mercado: hándicap asiático local / visitante |
| `AvgAHH` / `AvgAHA` | Promedio de mercado: hándicap asiático local / visitante |
| `BbAH` | Cantidad de casas usadas por Betbrain para este mercado (histórico) |
| `BbAHh` | Tamaño del hándicap Betbrain (histórico) |
| `BbMxAHH` / `BbMxAHA` | Máximo Betbrain: hándicap local / visitante (histórico) |
| `BbAvAHH` / `BbAvAHA` | Promedio Betbrain: hándicap local / visitante (histórico) |
| `GBAHH` / `GBAHA` / `GBAH` | Gamebookers: hándicap local / visitante / tamaño (histórico) |
| `LBAHH` / `LBAHA` / `LBAH` | Ladbrokes: hándicap local / visitante / tamaño (histórico) |

Igual que los demás mercados, agregar `C` indica cierre (`B365CAHH`,
`MaxCAHH`, etc.).

## Columnas que NO son de cuotas (resultado / estadísticas de partido)

Para referencia, estas columnas de `read_games()` no son cuotas (usadas
en `_NON_ODDS_COLUMNS` de `match_history.py` para no confundirlas al
loguear qué cuotas aparecieron):

| Columna (post `_normalize_columns`, snake_case) | Significado |
| --- | --- |
| `date`, `home_team`, `away_team`, `referee` | Identificación del partido |
| `fthg`, `ftag`, `ftr` | Goles/resultado a tiempo completo (Home/Away/Result) |
| `hthg`, `htag`, `htr` | Goles/resultado al entretiempo |
| `hs`, `as`, `hst`, `ast` | Remates / remates al arco (local/visitante) |
| `hc`, `ac` | Córners (local/visitante) |
| `hf`, `af` | Faltas cometidas (local/visitante) |
| `hy`, `ay`, `hr`, `ar` | Tarjetas amarillas/rojas (local/visitante) |
| `attendance` | Asistencia de público |
| `season` | Temporada (agregada por `soccerdata`, no viene del CSV original) |

Nota: `read_games()` deja `league`, `season` y `game` como niveles del
índice (`MultiIndex`), no como columnas — ver `_normalize_columns` en
`src/futbol/transform/normalize.py`, que también les aplica snake_case.
