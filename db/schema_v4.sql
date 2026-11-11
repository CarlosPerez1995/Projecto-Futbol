-- Esquema v4 de la base de datos de Fútbol (Fase 2, cargar xG — decisión
-- de Carlos, 11 nov, para volver a medir los modelos de Fase 4).
-- Única diferencia real respecto a schema_v3.sql: la tabla `matches`.
-- Todo lo demás es idéntico a v3 — se repite completo porque el esquema
-- se versiona como archivo entero, no como diff (decisión ya tomada en v1).
--
-- ============================================================================
-- Por qué cambia `matches`: agregar home_xg/away_xg (gol esperado, Understat)
-- ============================================================================
-- El modelo de 1X2 y los de over/under/BTTS (tareas 4.3/4.4) no mostraron
-- ventaja clara sobre una línea base trivial (ver docs/xgb_binary_resultados.md)
-- — Carlos decidió cargar el xG de Understat como feature nueva para volver a
-- medir. Understat ya se usaba para identidad de equipos/partidos
-- (team_source_ids/match_source_ids) desde la Fase 2 original, pero sus
-- columnas de xG (home_xg/away_xg en understat_team_match_stats_*.csv) nunca
-- se cargaron — quedaban documentadas como "pendiente de fuente" en
-- docs/features_map.txt.
--
-- Decisión de diseño: xG es un HECHO sobre un partido ya jugado (como el
-- marcador), no algo que cambie con el tiempo como una cuota o una posición
-- en la tabla — por eso va como columnas directas en `matches`
-- (`home_xg`/`away_xg`, upsert real igual que `home_score`/`away_score`), NO
-- como histórico con `captured_at` (eso sería la decisión correcta si el xG
-- se recalculara con el tiempo, que no es el caso: el xG de un partido ya
-- jugado es un número fijo).
--
-- `leagues`/`seasons`/`teams`/`team_source_ids`/`match_source_ids`/
-- `fixtures`/`odds`/`pipeline_runs` no cambian, se implementa en el loader
-- (`load_data.py`), no acá.

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

-- ----------------------------------------------------------------------------
-- matches: cambio real de v4, ver arriba (home_xg/away_xg nuevas)
-- ----------------------------------------------------------------------------

CREATE TABLE matches (
    match_id     INTEGER PRIMARY KEY AUTOINCREMENT,
    season_id    INTEGER NOT NULL REFERENCES seasons(season_id),
    home_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    away_team_id INTEGER NOT NULL REFERENCES teams(team_id),
    match_date   TIMESTAMP NOT NULL,
    home_score   INTEGER,
    away_score   INTEGER,
    home_xg      REAL,  -- gol esperado (Understat) — upsert real, mismo trato que el marcador
    away_xg      REAL,
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
-- Tabla de posiciones, formato histórico (sin cambios en v4)
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
    captured_at      TIMESTAMP NOT NULL,  -- timestamp de la corrida de extracción, NO de inserción en BD
    UNIQUE (season_id, team_id, captured_at)
);

CREATE INDEX idx_fixtures_season ON fixtures(season_id);
CREATE INDEX idx_fixtures_team ON fixtures(team_id);

-- ----------------------------------------------------------------------------
-- Cuotas, formato largo + histórico (sin cambios en v4)
-- ----------------------------------------------------------------------------

CREATE TABLE odds (
    odd_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL REFERENCES matches(match_id),
    bookmaker   TEXT NOT NULL,  -- normalizado, ej. 'b365', 'bw', 'ps', 'max', 'avg' (ver docs/odds_columns_map.md)
    market      TEXT NOT NULL,  -- '1x2' | 'over_under_2.5' | 'asian_handicap'
    is_closing  INTEGER NOT NULL DEFAULT 0,  -- 0/1: cuota de cierre (sufijo 'C') vs. pre-cierre
    line        REAL NOT NULL DEFAULT 0,  -- tamaño del hándicap/total O/U; 0 = no aplica (1x2)
    home_value  REAL,           -- cuota home / over, según el mercado
    draw_value  REAL,           -- cuota de empate; solo aplica a 1x2
    away_value  REAL,           -- cuota away / under, según el mercado
    captured_at TIMESTAMP NOT NULL,  -- timestamp de la corrida de extracción, NO de inserción en BD
    UNIQUE (match_id, bookmaker, market, is_closing, line, captured_at)
);

CREATE INDEX idx_odds_match ON odds(match_id);

-- ----------------------------------------------------------------------------
-- Manifest de corridas del pipeline (sin cambios en v4)
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
--     SEASONS ||--o{ FIXTURES : "tiene (histórico, varias filas por captura)"
--     TEAMS ||--o{ MATCHES : "juega como local"
--     TEAMS ||--o{ MATCHES : "juega como visitante"
--     TEAMS ||--o{ FIXTURES : "tiene (histórico, varias filas por captura)"
--     TEAMS ||--o{ TEAM_SOURCE_IDS : "se mapea a"
--     MATCHES ||--o{ MATCH_SOURCE_IDS : "se mapea a"
--     MATCHES ||--o{ ODDS : "tiene (histórico, varias filas por captura)"
