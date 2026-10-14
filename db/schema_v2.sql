-- Esquema v2 de la base de datos de Fútbol (Fase 2, tarea 2.3).
-- Única diferencia real respecto a schema_v1.sql: la tabla `odds`.
-- Todo lo demás (leagues/seasons/teams/team_source_ids/matches/
-- match_source_ids/fixtures/pipeline_runs) es idéntico a v1 — se repite
-- completo acá porque el esquema se versiona como archivo entero, no
-- como diff (decisión ya tomada en v1, ver ese archivo).
--
-- ============================================================================
-- Por qué cambia `odds`: decisión de Carlos sobre semántica de carga (13 oct)
-- ============================================================================
-- Al confirmar la semántica de upsert para la tarea 2.3, Carlos pidió lo
-- contrario de lo que proponía el plan arquitectónico para `odds`: NO
-- sobrescribir una cuota con la más reciente (eso sí aplica a `matches`,
-- ver abajo) sino guardar el HISTÓRICO COMPLETO de cómo varía cada cuota en
-- el tiempo — insumo para modelos de fases posteriores (ej. movimiento de
-- cuota antes del partido). La `UNIQUE` de v1
-- (`match_id, bookmaker, market, is_closing, line`) no soporta esto: una
-- segunda carga con un valor de cuota distinto para la misma llave haría
-- `INSERT OR IGNORE` y la perdería, o un upsert la pisaría — ambas
-- opciones pierden el histórico.
--
-- Cambio 1: se agrega `captured_at TIMESTAMP NOT NULL` y entra a la `UNIQUE`.
-- `captured_at` es el timestamp de la CORRIDA DE EXTRACCIÓN (el mismo que ya
-- va en el nombre del CSV de `data/raw/`, ej. `match_history_20260808_201736.csv`
-- -> `2026-08-08 20:17:36`), no la hora en que el loader inserta en la BD.
-- Si fuera la hora de inserción, correr el loader dos veces sobre el mismo
-- CSV crearía "cambios" de cuota que nunca pasaron en la realidad — el
-- histórico tiene que reflejar cuándo cambió el dato, no cuándo corrió el
-- script. Con `captured_at` = timestamp de la corrida, recargar el mismo
-- CSV sigue siendo idempotente (misma llave completa -> `INSERT OR IGNORE`),
-- y cada corrida nueva de extracción sí queda como fila nueva.
--
-- Cambio 2 (bug encontrado validando v2 antes de pushear, no es parte del
-- pedido de Carlos): SQLite trata cada `NULL` como distinto de cualquier
-- otro `NULL` dentro de una `UNIQUE` — con `line` en `NULL` (como quedaba en
-- v1 para el mercado '1x2', que no tiene línea), la restricción `UNIQUE` NO
-- bloqueaba duplicados exactos (verificado insertando la misma fila dos
-- veces: la segunda entraba sin error). Se cambia `line` a
-- `NOT NULL DEFAULT 0`: para '1x2' se guarda `0` como valor "no aplica" (no
-- hay ambigüedad con hándicap asiático real porque `market` ya los separa
-- en la misma `UNIQUE`); para `over_under_2.5` la línea es siempre `2.5`, no
-- ausente, así que tampoco debería haber sido `NULL` para ese mercado.
--
-- `matches` (marcador/estado) usa upsert real (sobrescribe con el dato más
-- reciente) y `leagues`/`teams`/catálogos usan `INSERT OR IGNORE` — ambos
-- sin cambios de esquema, se implementan en el loader (`load_data.py`), no
-- acá.
--
-- `fixtures` queda sin resolver todavía (pendiente de que Carlos confirme si
-- también necesita histórico o le alcanza con upsert real como matches) —
-- no se toca su esquema en esta versión hasta esa respuesta.

PRAGMA foreign_keys = ON;

-- ----------------------------------------------------------------------------
-- Catálogos con clave natural común entre fuentes (sin tabla de mapeo)
-- ----------------------------------------------------------------------------

CREATE TABLE leagues (
    league_id INTEGER PRIMARY KEY AUTOINCREMENT,
    code      TEXT NOT NULL UNIQUE,  -- clave de soccerdata, ej. 'ENG-Premier League'
    region    TEXT                   -- ej. 'ENG' (de sofascore leagues.csv)
);

CREATE TABLE seasons (
    season_id INTEGER PRIMARY KEY AUTOINCREMENT,
    league_id INTEGER NOT NULL REFERENCES leagues(league_id),
    code      TEXT NOT NULL,  -- clave de soccerdata, ej. '2425'
    UNIQUE (league_id, code)
);

CREATE INDEX idx_seasons_league ON seasons(league_id);

-- ----------------------------------------------------------------------------
-- Catálogos canónicos SIN clave natural común: requieren tabla de mapeo
-- ----------------------------------------------------------------------------

CREATE TABLE teams (
    team_id        INTEGER PRIMARY KEY AUTOINCREMENT,
    canonical_name TEXT NOT NULL,
    country        TEXT
);

CREATE TABLE team_source_ids (
    team_id          INTEGER NOT NULL REFERENCES teams(team_id),
    source           TEXT NOT NULL,  -- 'sofascore' | 'espn' | 'understat' | 'match_history'
    source_team_id   TEXT,           -- id nativo si la fuente lo trae; NULL si no (match_history)
    source_team_name TEXT NOT NULL,  -- nombre exacto tal como aparece en esa fuente
    PRIMARY KEY (source, source_team_name)
);

CREATE INDEX idx_team_source_ids_team ON team_source_ids(team_id);

CREATE TABLE matches (
    match_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id    INTEGER NOT NULL REFERENCES seasons(season_id),
    home_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    match_date   TIMESTAMP NOT NULL,
    home_score   INTEGER,
    away_score   INTEGER,
    status       TEXT NOT NULL DEFAULT 'scheduled'  -- 'scheduled' | 'played' | ...
);

CREATE INDEX idx_matches_season ON matches(season_id);
CREATE INDEX idx_matches_home_team ON matches(home_team_id);
CREATE INDEX idx_matches_away_team ON matches(away_team_id);

CREATE TABLE match_source_ids (
    match_id        INTEGER NOT NULL REFERENCES matches(match_id),
    source          TEXT NOT NULL,  -- 'sofascore' | 'espn' | 'understat' | 'match_history'
    source_match_id TEXT,           -- id nativo si la fuente lo trae; NULL si no (match_history)
    source_game_key TEXT NOT NULL,  -- clave "game" de soccerdata (fecha + equipos) tal como aparece ahí
    PRIMARY KEY (source, source_game_key)
);

CREATE INDEX idx_match_source_ids_match ON match_source_ids(match_id);

-- ----------------------------------------------------------------------------
-- Tabla de posiciones (= tarea 8 Excel, "fixtures") — sin cambios en v2,
-- semántica de carga todavía sin confirmar con Carlos.
-- ----------------------------------------------------------------------------

CREATE TABLE fixtures (
    fixture_id       INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id        INTEGER NOT NULL REFERENCES seasons(season_id),
    team_id          INTEGER NOT NULL REFERENCES teams(team_id),
    position         INTEGER,
    played           INTEGER,  -- mp
    won              INTEGER,  -- w
    drawn            INTEGER,  -- d
    lost             INTEGER,  -- l
    goals_for        INTEGER,  -- gf
    goals_against    INTEGER,  -- ga
    goal_difference  INTEGER,  -- gd
    points           INTEGER,  -- pts
    UNIQUE (season_id, team_id)
);

CREATE INDEX idx_fixtures_season ON fixtures(season_id);
CREATE INDEX idx_fixtures_team ON fixtures(team_id);

-- ----------------------------------------------------------------------------
-- Cuotas, formato largo + histórico (cambio real de v2, ver arriba)
-- ----------------------------------------------------------------------------

CREATE TABLE odds (
    odd_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL REFERENCES matches(match_id),
    bookmaker   TEXT NOT NULL,  -- normalizado, ej. 'b365', 'bw', 'ps', 'max', 'avg' (ver docs/odds_columns_map.md)
    market      TEXT NOT NULL,  -- '1x2' | 'over_under_2.5' | 'asian_handicap'
    is_closing  INTEGER NOT NULL DEFAULT 0,  -- 0/1: cuota de cierre (sufijo 'C') vs. pre-cierre
    line        REAL NOT NULL DEFAULT 0,  -- tamaño del hándicap/total O/U; 0 = no aplica (1x2) — ver "Cambio 2" arriba
    home_value  REAL,           -- cuota home / over, según el mercado
    draw_value  REAL,           -- cuota de empate; solo aplica a 1x2
    away_value  REAL,           -- cuota away / under, según el mercado
    captured_at TIMESTAMP NOT NULL,  -- timestamp de la corrida de extracción, NO de inserción en BD
    UNIQUE (match_id, bookmaker, market, is_closing, line, captured_at)
);

CREATE INDEX idx_odds_match ON odds(match_id);

-- ----------------------------------------------------------------------------
-- Manifest de corridas del pipeline (sin cambios en v2)
-- ----------------------------------------------------------------------------

CREATE TABLE pipeline_runs (
    run_id         INTEGER PRIMARY KEY AUTOINCREMENT,
    started_at     TIMESTAMP NOT NULL,
    finished_at    TIMESTAMP,
    stage          TEXT NOT NULL,
    status         TEXT NOT NULL,  -- 'running' | 'success' | 'failed'
    rows_written   INTEGER,
    error_message  TEXT
);

-- ============================================================================
-- Diagrama ER (Mermaid)
-- ============================================================================
-- erDiagram
--     LEAGUES ||--o{ SEASONS : tiene
--     SEASONS ||--o{ MATCHES : tiene
--     SEASONS ||--o{ FIXTURES : tiene
--     TEAMS ||--o{ MATCHES : "juega como local"
--     TEAMS ||--o{ MATCHES : "juega como visitante"
--     TEAMS ||--o{ FIXTURES : tiene
--     TEAMS ||--o{ TEAM_SOURCE_IDS : "se mapea a"
--     MATCHES ||--o{ MATCH_SOURCE_IDS : "se mapea a"
--     MATCHES ||--o{ ODDS : "tiene (histórico, varias filas por captura)"
