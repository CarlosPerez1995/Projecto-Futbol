# AGENTS.md

## Resumen del proyecto
Proyecto personal de predicción de apuestas de fútbol usando la librería `soccerdata`.
Flujo: Extracción -> Transformación/normalización -> Modelo de datos en BD ->
Modelos estadísticos/predictivos/prescriptivos -> Recomendaciones de apuestas.

Estado actual: **fase 1 (extracción) completa desde el 8 ago 2026** — multi-fuente
(Sofascore, MatchHistory, ESPN, Understat) con config/secrets management, caché
explícita de `soccerdata`, tests base y CI mínimo. **Fase 2 (modelo de
datos/BD SQLite) retomada el 13-14 oct 2026** — **2.1-2.4 completas**:
esquema v3 (`db/schema_v3.sql`: histórico completo de `odds` y `fixtures`,
no upsert — decisión de Carlos), conexión (`database.py`), loader
(`load_data.py`: catálogos, identidad de equipos/partidos, upsert real de
marcador, histórico de cuotas 1x2, over/under 2.5 y hándicap asiático, y de
la tabla de posiciones) y validación
(`validate_data.py`). **Fase 3 (features) completa (26 oct 2026)**, autorizada por
Carlos: 3.1 (features por partido), 3.2 (features por equipo, sin data
leakage verificado con tests dedicados) y 3.3 (dataset consolidado,
`src/futbol/features/dataset.py` — separa explícitamente columnas
predictoras de columnas objetivo, con `features_spec.md` versionado por
hash). **Fase 4 (modelos predictivos) arrancada el 11 nov 2026** (F9
autorizada por Carlos): `scikit-learn`/`scipy`/`xgboost`/`joblib`
instalados y congelados en `requirements.txt`; 4.1 (split temporal,
`src/futbol/models/split.py`) y 4.2 (Poisson/Dixon-Coles,
`src/futbol/models/poisson_dixon_coles.py` — un modelo por liga/
temporada, RPS < 0.25 en test en las 5 ligas, ver
`docs/dixon_coles_resultados.md`), 4.3 (clasificación 1X2 con XGBoost,
`src/futbol/models/xgb_1x2.py`) y 4.4 (over/under y BTTS con XGBoost,
`src/futbol/models/xgb_binary.py`) hechas — código y pipeline de las 3
verificados con tests y contra datos reales, pero **ninguna de las 3
le gana con claridad a una línea base trivial** (predecir siempre la
tasa histórica de train) al comparar en test — hallazgo real
encontrado el 11 nov al construir 4.4, que obligó a revisar también
4.2/4.3 (no se habían comparado contra ninguna línea base al
reportarlos la primera vez, corregido). Detalle completo y
recomendación antes de seguir a Fase 5 en `docs/xgb_binary_resultados.md`.
4.5 (backtesting) en pausa hasta resolver esto — no tiene sentido medir
rentabilidad de apostar con modelos sin edge demostrado todavía.
4 documentos no técnicos para Carlos en la raíz del repo, mantenerlos al
día en cada fase cerrada, no solo este archivo: `INFORME_PROYECTO.md`
(avance), `INFORME_PENDIENTES.md` (qué falta y de quién depende),
`INFORME_ARQUITECTURA.md` (diseño del sistema) y `PLAN_DE_TRABAJO.md`
(qué sigue y en qué orden). **OpenCode activado como operativo (10 nov)**,
ver sección dedicada más abajo — primera tarea real delegada y verificada
(mercados de cuotas over/under 2.5 y hándicap asiático).

## Entorno técnico
- Python 3.x, entorno virtual en `.venv/`
- SO: Debian 13
- Base de datos planeada: SQLite (vía `sqlite3`, incluido en la stdlib)

## Dependencias principales
- `soccerdata` (fuente: https://github.com/probberechts/soccerdata)
- `pandas`
- `openpyxl` (necesario para exportar a `.xlsx`)
- `scikit-learn`/`scipy`/`xgboost`/`joblib` (Fase 4, F9 autorizada por
  Carlos 11 nov 2026). Nota: `xgboost==3.4.1` en Linux x86_64 instala
  `nvidia-nccl-cu13` como dependencia declarada (~207 MB) aunque este
  proyecto no usa GPU ni entrenamiento distribuido — confirmado que
  `XGBClassifier` entrena y predice normal en CPU sin tocarla; es peso
  del paquete, no una dependencia que haya que configurar.

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
    `db/schema_v3.sql`, idempotente — detecta tablas ya creadas en vez de
    depender de `IF NOT EXISTS` en el `.sql` versionado).
  - `src/futbol/db/load_data.py` — loader CSV→BD (tarea 2.3, completa):
    catálogos (`load_leagues`/`load_seasons`, `INSERT OR IGNORE`),
    `resolve_team` (usa `config/team_aliases.json`), `resolve_or_create_match`/
    `load_matches` (identidad de partido por ventana de ±6h entre
    fuentes, no igualdad exacta de hora — ver docstring del módulo),
    `upsert_match_result` (marcador: upsert real, decisión de Carlos),
    `load_odds_1x2`/`_parse_1x2_odds` (cuotas 1x2: histórico completo),
    `load_odds_extra_markets`/`_parse_over_under_odds`/
    `_parse_asian_handicap_odds` (cuotas over/under 2.5 y hándicap
    asiático: mismo histórico completo, línea 2.5 fija en over/under y
    línea compartida `ahh`/`ahch` entre casas en hándicap asiático) y
    `load_fixtures` (tabla de posiciones: histórico completo, posición
    calculada por orden de fila del CSV de `standings`, no recalculada).
    `captured_at` de ambas = timestamp de la corrida de extracción, no de
    inserción — ver `db/schema_v3.sql`.
  - `src/futbol/db/validate_data.py` — validación de datos (tarea 2.4):
    `run_validation` genera `data/reports/validation_<fecha>.xlsx` (hojas
    `resumen`/`errores`) con 5 checks contra el estado actual de la BD:
    % de nulos por columna (`matches`/`odds`/`teams`/`fixtures`),
    duplicados en `matches`, fechas fuera de rango (1920-2100), scores
    negativos e integridad referencial (`PRAGMA foreign_key_check`).
  - `src/futbol/features/matches.py` — features por partido (tarea 3.1,
    Fase 3): `compute_match_features` lee `matches` ya cargados (solo
    `status='played'`) y calcula `total_goals`/`goal_difference`/
    `result_1x2`/`over_1_5`/`over_2_5`/`over_3_5`/`btts`; `home_xg`/
    `away_xg` quedan `NA` ("pendiente de fuente": Understat trae xG,
    pero Fase 2 no lo cargó a la BD, solo usó Understat para identidad
    de equipos/partidos — ver `docs/features_map.txt`).
    `save_features_matches` escribe `data/processed/features_matches.csv`.
  - `src/futbol/features/teams.py` — features de forma por equipo
    (tarea 3.2, Fase 3): `compute_team_features` calcula, por equipo
    local/visitante, promedios de goles/puntos/vallas invictas de sus
    últimos 5 partidos y racha actual — **todo desplazado 1 posición
    antes de agregar (`shift(1)` + `rolling`)** para que el partido en
    curso nunca entre en su propio cálculo (sin data leakage,
    verificado con un escenario de 3 partidos calculado a mano en
    `tests/test_features_teams.py`). Ver `docs/features_map.txt` para
    el detalle de cada columna `_home`/`_away`.
  - `src/futbol/features/dataset.py` — dataset consolidado (tarea 3.3,
    Fase 3): `build_model_dataset` une 3.1+3.2 por `match_id` y separa
    columnas en `predictor_columns()` (features de equipo, lo que un
    modelo puede usar de entrada) vs. `TARGET_COLUMNS` (resultado real
    del partido — NUNCA como entrada, es lo que el modelo debe
    predecir); `save_model_dataset` escribe
    `data/processed/model_dataset.csv` + `features_spec.md` (fecha y
    hash SHA-256 del CSV, para saber con qué versión exacta de
    features se entrenó cada modelo más adelante).
  - `src/futbol/models/split.py` — split temporal (tarea 4.1, Fase 4):
    `split_temporal` divide el dataset consolidado 70/15/15 por fecha
    (nunca shuffle), ajustando el corte hacia adelante para no partir
    un grupo de partidos con la misma fecha/hora entre dos splits —
    así el overlap de fechas entre splits queda en cero garantizado,
    no solo "normalmente cero". `verificar_sin_overlap` es el chequeo
    explícito reusable (lanza `AssertionError` si hay overlap real).
  - `src/futbol/models/poisson_dixon_coles.py` — modelo Poisson/
    Dixon-Coles (tarea 4.2, Fase 4): `fit_dixon_coles` ajusta por MLE
    (fórmulas verificadas contra Dixon & Coles 1997, no inventadas) un
    modelo por `(league_code, season_code)` — nunca uno global, los
    equipos de distinta liga no juegan entre sí en este dataset.
    `DixonColesModel.match_outcome_probs` integra la conjunta de
    marcadores para dar P(H)/P(D)/P(A); `rps`/`brier_score` son las
    métricas de evaluación; `fit_and_evaluate_by_group` encadena todo
    por grupo y deja `NaN` (no inventa) cuando un grupo no tiene
    partidos de prueba — pasa de verdad con la temporada 2425 en este
    dataset (cae entera en entrenamiento). **Importante sobre
    rendimiento:** la verosimilitud está vectorizada con NumPy (sin
    loop en Python por partido) — la primera versión con loop tardaba
    minutos por ajuste, medido contra los datos reales; si se toca
    esta función, no reintroducir un loop fila por fila. Resultados
    completos y el ejemplo real (ratings de la Premier League 2024-25
    coinciden con los 3 descendidos reales) en
    `docs/dixon_coles_resultados.md`.
  - `src/futbol/models/xgb_1x2.py` — clasificación 1X2 con XGBoost
    (tarea 4.3, Fase 4): `fit_xgb_1x2` (train + `GridSearchCV` con
    `TimeSeriesSplit`, nunca k-fold al azar) → `calibrate_xgb_1x2`
    (val, regresión isotónica vía `CalibratedClassifierCV(
    FrozenEstimator(...))` — API vigente en scikit-learn 1.9.1, el
    `cv="prefit"` viejo ya no existe, verificado contra el código
    instalado antes de usarlo) → `evaluate_xgb_1x2` (test, LogLoss +
    Brier) → `save_model` (versionado por fecha,
    `models/xgb_1x2/<version>/model.pkl` + `metrics.json` con feature
    importances y el hash del dataset de entrenamiento — `models/` no
    se versiona, mismo criterio que `data/`, ver `.gitignore`).
    `result_1x2` se codifica con `LabelEncoder` (XGBoost 3.4.1 rechaza
    texto directo, verificado) y `current_streak_result_*` (texto) se
    codifica a escala ordinal simple antes de entrenar — el resto de
    `predictor_columns()` ya es numérico y XGBoost acepta sus `NaN`
    nativamente, sin imputar. Resultados completos, con una nota
    honesta sobre una posible ambigüedad de convención en la métrica
    Brier del plan original, en `docs/xgb_1x2_resultados.md`.
  - `src/futbol/models/xgb_binary.py` — over/under y BTTS con XGBoost
    (tarea 4.4, Fase 4): mismo patrón exacto que `xgb_1x2.py`
    (reusa su `_features()`), aplicado a 3 objetivos binarios
    (`BINARY_TARGETS = ["over_1_5", "over_2_5", "btts"]`) con un
    modelo separado por objetivo, no multi-etiqueta.
    `fit_calibrate_evaluate_all()` corre el flujo completo para los 3
    de una. **Resultado real: ningún AUC pasa de 0.55** (criterio del
    plan era >0.6) — diagnóstico completo (no es un bug de
    calibración, descartado comparando isotónica/sigmoide/sin
    calibrar; el modelo no generaliza de train a val/test) y la
    corrección retroactiva de 4.2/4.3 contra línea base trivial en
    `docs/xgb_binary_resultados.md`.
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
- `data/processed/features_matches.csv` — salida de la tarea 3.1 (Fase 3),
  no versionada (se regenera desde la BD).
- `data/processed/model_dataset.csv`, `data/processed/features_spec.md` —
  salida de la tarea 3.3 (Fase 3), no versionados (se regeneran desde la
  BD; `features_spec.md` trae el hash SHA-256 del CSV generado).
- `db/schema_v1.sql`, `db/schema_v2.sql` — versiones superadas, **no
  editar, quedan como historial** (versionado: decisión ya tomada en v1).
  v1: diseño original (tarea 2.1) — catálogos `leagues`/`seasons` por clave
  natural común entre fuentes; `teams`/`matches` canónicos con tablas de
  mapeo (`team_source_ids`/`match_source_ids`) porque Sofascore/ESPN/
  Understat/MatchHistory no comparten id ni nombre de equipo o partido. v2
  (13 oct): `odds` agrega `captured_at` a la `UNIQUE` (decisión de Carlos:
  histórico completo de cuotas, no sobrescribir); `line` pasa a
  `NOT NULL DEFAULT 0` (bug real: SQLite trata cada `NULL` como distinto en
  una `UNIQUE`, con `line` en `NULL` para 1x2 la restricción no bloqueaba
  duplicados exactos).
- `db/schema_v3.sql` — esquema vigente (14 oct). Única diferencia real
  respecto a v2: `fixtures` recibe el mismo tratamiento que `odds` en v2 —
  agrega `captured_at` a su `UNIQUE` (pasa de `(season_id, team_id)` a
  `(season_id, team_id, captured_at)`), misma decisión de Carlos de
  histórico completo, misma razón (insumo para modelos de fases
  posteriores, ej. posición del equipo antes de un partido dado).
  `captured_at` = timestamp de la corrida de extracción en ambas tablas,
  nunca de inserción. A diferencia de `odds.line` en v1, ninguna columna de
  la nueva `UNIQUE` de `fixtures` podía ser `NULL` (ya eran `NOT NULL` por
  FK) — no hizo falta ningún valor sentinela acá. Próximos cambios de
  esquema van en `schema_v4.sql`, nunca editando v1, v2 ni v3.
- `.venv/` — entorno virtual (no versionar en git)
- `requirements.txt` — dependencias del proyecto
- Scripts de procesamiento de datos — por crear
- Esquema de base de datos — por definir

## OpenCode como operativo (activado 10 nov 2026)

Decisión de Carlos: bajar el consumo de tokens de Claude Code delegando
implementación rutinaria ya especificada (sin decisiones de diseño propias)
a OpenCode. El jefe de proyecto sigue diseñando/decidiendo/verificando.

- Instalado y logueado globalmente en `punky` (`opencode` v1.18.22).
  **Reconfigurado el 4 nov**: ya NO usa OpenRouter/NVIDIA NIM — Carlos los
  quitó; proveedor único ahora es OpenCode Zen, modelo por defecto
  `opencode/glm-5.3-flash-free` (gratis). Sin verificar todavía si este
  modelo entrena con los prompts enviados — revisar antes de usarlo para
  fases 4-5 (lógica de apuestas propia), igual precaución que se tenía
  anotada para NVIDIA/OpenRouter.
- OpenCode lee `AGENTS.md` del repo automáticamente como contexto (igual que
  Claude Code).
- Asignación no interactiva: `opencode run "<tarea>" --agent build`, corrido
  desde dentro del repo (no hace falta `--dir` si ya estás parado ahí). NO
  usar `--auto`. El spec de la tarea no se puede pasar como ruta fuera del
  repo (`external_directory` se auto-rechaza en modo no interactivo) — copiar
  el archivo de spec DENTRO del repo/worktree antes de invocar, borrarlo
  después.
- **Flujo real usado y verificado** (primera tarea: mercados de cuotas
  over/under 2.5 y hándicap asiático, 10 nov): `git worktree add -b
  feature/opencode-<tarea> ../<repo>-opencode-<tarea> desarrollo` (no rama
  directo en el working dir del jefe, para no chocar); correr `opencode run`
  ahí con el spec detallado en un archivo dentro del worktree; revisar
  `git diff` completo; para correr los tests del worktree sin reinstalar el
  paquete editable, usar `PYTHONPATH="<ruta-worktree>/src:$PYTHONPATH"` con
  el python del venv del repo principal (el install editable apunta al repo
  principal, no al worktree, y pisarlo rompería el propio trabajo del jefe);
  validar a mano contra datos reales (`data/raw/` no está en el worktree,
  gitignored — apuntar `raw_dir` al del repo principal); si todo cierra,
  commitear en la rama del worktree, mergear `--ff-only` a `desarrollo` desde
  el repo principal, pushear, y recién ahí `git worktree remove` + `git
  branch -d`.
- Permisos ya configurados globalmente en `~/.config/opencode/opencode.jsonc`
  (`edit: allow`, `bash: ask`, `webfetch: ask`) — agente `build` es el
  correcto para implementación (no `plan`/`explore`/etc.). No instruir tareas
  que necesiten correr bash (pytest, git): con `bash: ask`, en modo no
  interactivo esa aprobación no tiene quién la responda — no se probó qué
  pasa exactamente (si se cuelga o se auto-rechaza, igual que sí se
  confirmó para `external_directory`), así que mejor evitarlo: decirle
  explícitamente que no corra bash, y que la verificación la hace el jefe
  de proyecto después.

## Comandos útiles
- Activar entorno: `source .venv/bin/activate`
- Instalar dependencias: `pip install -r requirements.txt`
- Instalar el paquete en modo editable (necesario para el entry point):
  `pip install -e .`
- Ejecutar extracción (5 grandes ligas por defecto): `futbol-extract`
- Extraer ligas específicas: `futbol-extract --ligas "ENG-Premier League" "ESP-La Liga"`
- Congelar dependencias tras instalar: `pip freeze > requirements.txt`
