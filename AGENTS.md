# AGENTS.md

## Resumen del proyecto
Proyecto personal de predicción de apuestas de fútbol usando la librería `soccerdata`.
Flujo: Extracción -> Transformación/normalización -> Modelo de datos en BD ->
Modelos estadísticos/predictivos/prescriptivos -> Recomendaciones de apuestas.

Estado actual: **fase 1 (extracción) completa desde el 8 ago 2026** — multi-fuente
(Sofascore, MatchHistory, ESPN, Understat) con config/secrets management, caché
explícita de `soccerdata`, tests base y CI mínimo. **Fase 2 (modelo de
datos/BD SQLite) retomada el 13 oct 2026** (2.1 esquema v2 — histórico de
cuotas, ver `db/schema_v2.sql` — y 2.2 conexión hechas; 2.3 casi completa:
catálogos, identidad de equipos/partidos, upsert real de marcador y
cuotas 1x2 con histórico, todo en `src/futbol/db/load_data.py`; falta
`fixtures`, bloqueado por una pregunta pendiente a Carlos sobre si
necesita histórico o upsert real; over/under y hándicap asiático de
`odds` deferidos a propósito, no implementados. **2.4 hecha**:
`src/futbol/db/validate_data.py`, reporte en
`data/reports/validation_<fecha>.xlsx`).

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
  - `src/futbol/ingestion/match_history.py` — resultados + cuotas
    históricas de football-data.co.uk vía `MatchHistory`
    (`get_match_history`).
  - `src/futbol/ingestion/espn.py` — calendario vía ESPN
    (`get_espn_schedule`, integrada al pipeline; `get_espn_matchsheet`/
    `get_espn_lineup` implementadas pero fuera del flujo automático por
    defecto — rotas en `soccerdata==1.9.1` contra la API actual, ver
    `docs/espn_cobertura.md`).
  - `src/futbol/ingestion/understat.py` — xG por equipo/partido y por tiro
    vía Understat (`get_understat_team_match_stats`, integrada al
    pipeline; `get_understat_shot_events` implementada pero fuera del
    flujo automático por defecto — no por rotura, sino por volumen medido
    de ~1700+ requests/~26 min por temporada sin `match_id`, ver
    `docs/understat_vs_fbref.md`).
  - `src/futbol/ingestion/cli.py` — CLI delgado (`main()`/`parse_args()`),
    entry point `futbol-extract`.
  - `src/futbol/db/database.py` — conexión a la BD SQLite (tarea 2.2):
    `get_connection`, `close_connection`, `init_db` (aplica
    `db/schema_v2.sql`, idempotente — detecta tablas ya creadas en vez de
    depender de `IF NOT EXISTS` en el `.sql` versionado).
  - `src/futbol/db/load_data.py` — loader CSV→BD (tarea 2.3): catálogos
    (`load_leagues`/`load_seasons`, `INSERT OR IGNORE`), `resolve_team`
    (usa `config/team_aliases.json`), `resolve_or_create_match`/
    `load_matches` (identidad de partido por ventana de ±6h entre
    fuentes, no igualdad exacta de hora — ver docstring del módulo),
    `upsert_match_result` (marcador: upsert real, decisión de Carlos),
    `load_odds_1x2`/`_parse_1x2_odds` (cuotas 1x2: histórico completo,
    `captured_at` = timestamp de la corrida de extracción, no de
    inserción — ver `db/schema_v2.sql`). Over/under y hándicap asiático
    de `odds`, y la tabla `fixtures`, no implementados todavía (ver
    "Estado actual" arriba).
  - `src/futbol/db/validate_data.py` — validación de datos (tarea 2.4):
    `run_validation` genera `data/reports/validation_<fecha>.xlsx` (hojas
    `resumen`/`errores`) con 5 checks contra el estado actual de la BD:
    % de nulos por columna (`matches`/`odds`/`teams`), duplicados en
    `matches`, fechas fuera de rango (1920-2100), scores negativos e
    integridad referencial (`PRAGMA foreign_key_check`). No valida
    `fixtures` (sin loader todavía).
- `config/` — configuración versionada del proyecto:
  - `config/config.yaml` — ligas/temporadas por defecto, `data_dir`,
    `cache_dir`, `log_level`.
  - `config/team_aliases.json` — mapeo manual de nombres de equipo por
    liga/fuente (tarea 2.3), curado y verificado contra los CSV reales
    — ver `docs/team_aliases_notas.md`. Un equipo nuevo (ascenso/
    descenso de otra temporada) que no esté acá hace fallar la carga
    con error explícito, no se adivina.
  - `config/league_dict.json` — diccionario custom de ligas para
    `soccerdata` (arranca vacío, `{}`; agregar una liga real es una
    decisión de negocio aparte). Se sincroniza automáticamente hacia
    `$SOCCERDATA_DIR/config/league_dict.json` (la ubicación real que
    `soccerdata` espera) cada vez que arranca `futbol-extract`, sin paso
    manual — ver `sync_league_dict()` en `src/futbol/config.py`.
  - `config/league_dict.md` — esquema documentado de `league_dict.json`
    (JSON no admite comentarios, así que el ejemplo vive acá).
- `pyproject.toml` — empaquetado (`setuptools`) y entry point `futbol-extract`.
- `data/raw/<fuente>/` — CSVs generados por fuente (p.e. `data/raw/sofascore/`,
  `data/raw/match_history/`, `data/raw/espn/`, `data/raw/understat/`)
- `data/cache/soccerdata/` — caché de `soccerdata` (tarea 1.6.3), no
  versionada.
- `db/schema_v1.sql` — esquema original de la BD SQLite (tarea 2.1), **ya
  superado por `schema_v2.sql`, no editar** (versionado: queda como historial,
  nunca se toca). Catálogos `leagues`/`seasons` por clave natural común entre
  fuentes; `teams`/`matches` canónicos con tablas de mapeo
  (`team_source_ids`/`match_source_ids`) porque Sofascore/ESPN/Understat/
  MatchHistory no comparten id ni nombre de equipo o partido (ver comentario
  de divergencia al inicio del archivo).
- `db/schema_v2.sql` — esquema vigente. Única diferencia real respecto a v1:
  `odds` agrega `captured_at` a la `UNIQUE` (decisión de Carlos, 13 oct:
  guardar histórico completo de cuotas, no sobrescribir — insumo para
  modelos de fases posteriores) — `captured_at` es el timestamp de la
  corrida de extracción, no de inserción (si no, recargar el mismo CSV
  inventaría "cambios" de cuota que nunca pasaron). `odds` sigue en formato
  largo (no columnas fijas por casa, ver `docs/odds_columns_map.md`); `line`
  es `NOT NULL DEFAULT 0` (no `NULL`) — un bug real encontrado validando v2:
  SQLite trata cada `NULL` como distinto en una `UNIQUE`, así que con `line`
  en `NULL` (mercado 1x2) la restricción no bloqueaba duplicados exactos.
  Próximos cambios de esquema van en `schema_v3.sql`, nunca editando v1 ni v2.
- `.venv/` — entorno virtual (no versionar en git)
- `requirements.txt` — dependencias del proyecto
- Scripts de procesamiento de datos — por crear
- Esquema de base de datos — por definir

## OpenCode como operativo (investigación 9 oct, no activado)

Fútbol sigue en pausa (fase 2 bloqueada, ver hub). Esto es preparación para cuando
se reactive, no una integración en uso.

- Ya instalado y logueado globalmente en `punky` (`opencode` v1.18.22, credenciales
  de OpenRouter y NVIDIA NIM en `~/.local/share/opencode/auth.json`) — no hace falta
  nada nuevo específico de este proyecto para tener el operativo disponible.
- OpenCode lee `AGENTS.md` del repo automáticamente como contexto (igual que Claude
  Code), así que este archivo ya le sirve sin trabajo adicional.
- Asignación no interactiva: `opencode run "<tarea>" --dir <ruta-del-repo> --model
  <provider/model> --agent <agent>`. NO usar `--auto` (aprueba permisos solo,
  "dangerous") — las tareas deben pedir permiso igual que esta sesión, y el jefe de
  proyecto revisa el diff antes de aceptar.
- Permisos configurables por acción (`read`/`edit`/`bash`/...: `ask`/`allow`/`deny`)
  en `opencode.jsonc` — mapear a los 3 niveles de `PROTOCOLO.md` del hub (libre /
  con orden de Carlos / solo Carlos) cuando se le asigne una tarea real.
- Modelos gratis de NVIDIA NIM/OpenRouter: varios registran o entrenan con los
  prompts (ver `HERRAMIENTAS.md` del hub). Para fase 2 (esquema de BD, datos
  públicos de fútbol) el riesgo es bajo; para fases 4-5 (modelos predictivos,
  lógica de apuestas propia) revisar antes cuál modelo usar.
- Para que no choque con el trabajo del jefe de proyecto en el mismo repo: que
  OpenCode trabaje en su propia rama (`feature/opencode-<tarea>`) o un `git
  worktree` separado, nunca directo sobre `desarrollo`.

## Comandos útiles
- Activar entorno: `source .venv/bin/activate`
- Instalar dependencias: `pip install -r requirements.txt`
- Instalar el paquete en modo editable (necesario para el entry point):
  `pip install -e .`
- Ejecutar extracción (5 grandes ligas por defecto): `futbol-extract`
- Extraer ligas específicas: `futbol-extract --ligas "ENG-Premier League" "ESP-La Liga"`
- Congelar dependencias tras instalar: `pip freeze > requirements.txt`
