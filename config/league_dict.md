# Esquema de `config/league_dict.json`

`config/league_dict.json` es un diccionario custom de ligas para `soccerdata`,
versionado en este repo (tarea 1.5 de la Suite de Implementación de
Robustez). Arranca vacío (`{}`): agregar una liga acá es una decisión de
negocio aparte, fuera del alcance de la tarea que introdujo el mecanismo.

## Por qué existe este archivo

`soccerdata==1.9.1` busca un diccionario custom en
`$SOCCERDATA_DIR/config/league_dict.json` (por defecto
`~/soccerdata/config/league_dict.json`, fuera de cualquier repo) y lo
mergea sobre las ligas incorporadas de fábrica
(`soccerdata/_config.py::LEAGUE_DICT`). Ese archivo vive fuera del repo por
definición de la librería, así que editarlo a mano no es reproducible: un
clon nuevo del proyecto en otra máquina no lo tendría.

`config/league_dict.json` es la fuente versionada; `sync_league_dict()`
(en `src/futbol/config.py`) lo copia automáticamente hacia la ubicación
real que `soccerdata` espera, cada vez que arranca `futbol-extract` —
sin ningún paso manual.

## Esquema esperado

Cada clave de nivel superior es un código de liga propio (mismo formato
que `LEAGUE_DICT` de `soccerdata`, p. ej. `"ENG-Premier League"`). El
valor es un diccionario con el código específico de esa liga en cada
fuente de datos que la soporte, más metadatos opcionales de temporada.

JSON no admite comentarios, así que el ejemplo de referencia queda acá
en vez de en el `.json`. Ejemplo (formato tomado literalmente de
`soccerdata/_config.py::LEAGUE_DICT`, no inventado):

```json
{
  "ENG-Premier League": {
    "ClubElo": "ENG_1",
    "MatchHistory": "E0",
    "FiveThirtyEight": "premier-league",
    "FBref": "Premier League",
    "ESPN": "eng.1",
    "Sofascore": "Premier League",
    "SoFIFA": "[England] Premier League",
    "Understat": "EPL",
    "WhoScored": "England - Premier League",
    "season_start": "Aug",
    "season_end": "May"
  }
}
```

Campos:
- Cada clave dentro del valor (`ClubElo`, `MatchHistory`, `FBref`, `ESPN`,
  `Sofascore`, `SoFIFA`, `Understat`, `WhoScored`, ...) es el nombre de una
  fuente que soporta `soccerdata` — solo hace falta incluir las fuentes
  que efectivamente cubren esa liga, no todas.
- `season_start` / `season_end`: mes de inicio/fin de temporada (p. ej.
  `"Aug"` / `"May"`), usados por `soccerdata` para resolver temporadas.
- `season_code` (opcional): p. ej. `"single-year"` para competencias que no
  cruzan años calendario (mundiales, Eurocopa).

## Importante: el merge es superficial (shallow), no por campo

`soccerdata` mergea así (`soccerdata/_config.py` líneas 183-192,
verificado en el código instalado):

```python
LEAGUE_DICT = {**LEAGUE_DICT, **json.load(json_file)}
```

Es un merge a nivel de las claves de liga, no de los campos internos. Dos
casos:
- **Clave nueva** (no existe en las 8 ligas de fábrica): agrega una liga
  nueva con exactamente los campos que se le pongan.
- **Clave existente** (p. ej. reescribir `"ENG-Premier League"`): **reemplaza
  el diccionario completo de esa liga**, no lo combina campo por campo. Si
  solo se quiere agregar/corregir una fuente para una liga ya incorporada,
  hay que copiar también las demás claves que se quieran conservar — de lo
  contrario esa liga pierde el resto de sus mapeos de fuente.

## Sincronización

`sync_league_dict()` (`src/futbol/config.py`) se invoca automáticamente al
importar `futbol.ingestion.cli` (entry point `futbol-extract`), **antes**
de que se importe `soccerdata` en cualquier módulo. Es necesario en ese
orden porque `soccerdata/_config.py` lee y mergea
`$SOCCERDATA_DIR/config/league_dict.json` como código de nivel de módulo
al momento del import (verificado leyendo el código fuente instalado y
de forma empírica); sincronizar después de ese import no tiene ningún
efecto, ya que el módulo queda cacheado en `sys.modules` con el
`LEAGUE_DICT` ya calculado.

La sincronización es idempotente: sobreescribe el archivo destino con el
contenido exacto de `config/league_dict.json` en cada corrida.
