# AGENTS.md

## Resumen del proyecto
Proyecto personal de predicción de apuestas de fútbol usando la librería `soccerdata`.
Flujo: Extracción -> Transformación/normalización -> Modelo de datos en BD ->
Modelos estadísticos/predictivos/prescriptivos -> Recomendaciones de apuestas.

Estado actual: **etapa inicial (solo extracción de datos)**.

## Entorno técnico
- Python 3.x, entorno virtual en `.venv/`
- SO: Debian 13
- Base de datos planeada: SQLite (vía `sqlite3`, incluido en la stdlib)

## Dependencias principales
- `soccerdata` (fuente: https://github.com/probberechts/soccerdata)
- `pandas`
- `openpyxl` (necesario para exportar a `.xlsx`)

## Reglas estrictas para el agente (anti-alucinación)

1. NUNCA inventes métodos, parámetros o clases de `soccerdata` (u otra librería)
   que no hayas verificado. Si no estás seguro de que algo existe, inspecciona
   el paquete instalado en `.venv/lib/python*/site-packages/soccerdata/` o dilo
   explícitamente en vez de asumirlo.
2. Antes de usar un método nuevo de una librería externa, confírmalo revisando
   el código fuente instalado o pidiendo confirmación al usuario.
3. No agregues dependencias nuevas al proyecto sin preguntar primero.
4. Usa siempre rutas compatibles con Linux (`pathlib.Path`), nunca rutas de
   Windows tipo `C:\...`.
5. Sigue PEP8. Usa type hints donde aporte claridad.
6. Cambios de código mínimos y quirúrgicos: no reescribas archivos completos
   si solo se pidió modificar una función o sección.
7. Si una tarea es ambigua, pregunta antes de asumir.
8. Sé conciso en las respuestas salvo que se pida una explicación detallada.
9. Evita crear múltiples instancias de `Sofascore()` si se puede reutilizar
   una sola instancia — cada instanciación puede implicar llamadas a la API.
10. Todo script que escriba archivos debe crear las carpetas de salida si no
    existen (`Path(...).mkdir(parents=True, exist_ok=True)`).
11. Al finalizar cualquier tarea que modifique archivos del repo, SIEMPRE hacer
    `git add`, commit descriptivo, y `git push origin desarrollo`. Nunca dejar
    cambios solo en local. Nunca pushear directo a main.

## Estrategia de ramas
- Rama estable/release: `main`
- Rama de desarrollo activo: `desarrollo`
- Convención de nombres para ramas futuras: `feature/<nombre>`,
  `fix/<nombre>`, `release/<version>`
- Nota: las ramas CAPG, Helmuth-A y NicoMartinico mencionadas en la planeación
  original ya no existen en el remoto (se mergearon a main el 2026-02-12 vía
  PR #1 de NicoMartinico). No hay ramas obsoletas pendientes de limpiar.

## Flujo de extracción de datos
1. Instanciar `soccerdata.Sofascore(leagues=[...], seasons=[...])` una sola
   vez por corrida, con la lista completa de ligas/temporadas (soccerdata
   hace el producto cruzado internamente) — nunca una instancia por liga.
2. Antes de extraer, filtrar las ligas solicitadas contra
   `Sofascore.available_leagues()` (no asumir que las 8 ligas de
   `LEAGUE_DICT` están soportadas por esta fuente en particular).
3. Extraer ligas con `read_leagues()`, temporadas con `read_seasons()`,
   tabla de posiciones con `read_league_table()` y calendario con
   `read_schedule()`. Cada extracción va en su propio `try/except`: un
   fallo puntual se loguea y no aborta las demás.
4. Antes de guardar, comparar cada DataFrame contra el último CSV bueno
   conocido del mismo dataset (misma carpeta) para detectar roturas
   silenciosas (0 filas, columnas faltantes, caída drástica de filas).
5. Guardar en `data/raw/<fuente>/` (p.e. `data/raw/sofascore/`) con
   nombre `<dataset>_<timestamp>.csv` — subcarpeta por fuente para que
   `data/raw/` quede ordenado a medida que se sumen más lectores
   (`MatchHistory`, `ESPN`, ...).

Referencia detallada: `/home/carlosperez/Escritorio/AuditoriaFutbol/Planes de Robustez/`
(`00_Resumen_Ejecutivo.md`, `01_Investigacion_Fuentes_de_Datos.md`,
`02_Plan_de_Robustez_Fase1_Extraccion.md`), fuera de este repo.

## Notas importantes
- Fuente de datos: Sofascore
- Todas las columnas de fecha requieren manejo de zona horaria
  (`pd.to_datetime(..., errors="coerce").dt.tz_localize(None)`)
- Archivos Excel se usan como almacenamiento intermedio (por ahora)
- Integración con base de datos: planeada, no implementada aún

## Estructura del proyecto
- `src/futbol/` — paquete instalable (`pip install -e .`):
  - `src/futbol/config.py` — carga de `config/config.yaml` (`load_config`) y
    configuración explícita del área de `soccerdata` regida por
    `SOCCERDATA_DIR`: `configure_soccerdata_cache` (tarea 1.6.3, redirige la
    caché) y `sync_league_dict` (tarea 1.5, sincroniza el diccionario de
    ligas custom). Ambas deben llamarse antes de importar `soccerdata` en
    cualquier módulo — se invocan al importar `futbol.ingestion.cli`.
  - `src/futbol/transform/normalize.py` — normalización genérica (snake_case,
    fechas tz-naive, validaciones, guardado a CSV, detección de rotura
    silenciosa), sin atar a ninguna fuente en particular.
  - `src/futbol/ingestion/sofascore.py` — extracción específica de Sofascore
    (`get_leagues`, `get_seasons`, `get_standings`, `get_schedule`,
    `_filter_available_leagues`).
  - `src/futbol/ingestion/cli.py` — CLI delgado (`main()`/`parse_args()`),
    entry point `futbol-extract`.
- `config/` — configuración versionada del proyecto:
  - `config/config.yaml` — ligas/temporadas por defecto, `data_dir`,
    `cache_dir`, `log_level`.
  - `config/league_dict.json` — diccionario custom de ligas para
    `soccerdata` (arranca vacío, `{}`; agregar una liga real es una
    decisión de negocio aparte). Se sincroniza automáticamente hacia
    `$SOCCERDATA_DIR/config/league_dict.json` (la ubicación real que
    `soccerdata` espera) cada vez que arranca `futbol-extract`, sin paso
    manual — ver `sync_league_dict()` en `src/futbol/config.py`.
  - `config/league_dict.md` — esquema documentado de `league_dict.json`
    (JSON no admite comentarios, así que el ejemplo vive acá).
- `pyproject.toml` — empaquetado (`setuptools`) y entry point `futbol-extract`.
- `data/raw/<fuente>/` — CSVs generados por fuente (p.e. `data/raw/sofascore/`)
- `data/cache/soccerdata/` — caché de `soccerdata` (tarea 1.6.3), no
  versionada.
- `.venv/` — entorno virtual (no versionar en git)
- `requirements.txt` — dependencias del proyecto
- Scripts de procesamiento de datos — por crear
- Esquema de base de datos — por definir

## Comandos útiles
- Activar entorno: `source .venv/bin/activate`
- Instalar dependencias: `pip install -r requirements.txt`
- Instalar el paquete en modo editable (necesario para el entry point):
  `pip install -e .`
- Ejecutar extracción (5 grandes ligas por defecto): `futbol-extract`
- Extraer ligas específicas: `futbol-extract --ligas "ENG-Premier League" "ESP-La Liga"`
- Congelar dependencias tras instalar: `pip freeze > requirements.txt`
