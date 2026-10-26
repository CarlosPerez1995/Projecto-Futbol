-- Esquema v1 de la base de datos de Fútbol (Fase 2, tarea 2.1).
-- Fuente de diseño: `~/Escritorio/AuditoriaFutbol/Planes arquitectonicos/
-- Suite_Implementacion_Arquitectura/Fase_2_Modelo_de_Datos.md` (= tarea 8
-- del Excel), con dos grupos de divergencias documentadas abajo.
--
-- Este archivo se versiona: cualquier cambio futuro de esquema va en
-- schema_v2.sql, nunca editando este (decisión ya tomada en el plan
-- arquitectónico, no es punto de pausa).
--
-- ============================================================================
-- Divergencia ya decidida por el plan arquitectónico: tabla `pipeline_runs`
-- ============================================================================
-- Manifest de corridas del pipeline (usado desde la Fase 6, definido ya para
-- no migrar el esquema más adelante).
--
-- ============================================================================
-- Divergencia nueva, encontrada al diseñar este esquema (no estaba prevista
-- en el plan, escrito el 6 ago, antes de integrar MatchHistory/ESPN/Understat
-- el 6-8 ago): `team_source_ids` y `match_source_ids`
-- ============================================================================
-- El plan daba por hecho un único espacio de IDs para equipos y partidos
-- (columnas `team_id`/FK enteras directas en `matches`/`fixtures`). Verificado
-- contra los CSV reales en data/raw/ (corrida del 8 ago, 2024-25 Premier
-- League), eso no es cierto entre las 4 fuentes ya integradas:
--   - Sofascore (schedule): game_id numérico propio; equipos solo por nombre
--     ("Wolverhampton").
--   - ESPN (espn_schedule): game_id y league_id ("eng.1") propios, distintos
--     de los de Sofascore; mismo equipo como "Wolverhampton Wanderers".
--   - Understat (understat_team_match_stats): game_id, home_team_id/
--     away_team_id propios (ej. team 229), mismo equipo como "Wolverhampton
--     Wanderers" (coincide con ESPN en el nombre, no en el id).
--   - MatchHistory (match_history, football-data.co.uk): sin ningún id,
--     solo nombre, y además con su propia abreviación ("Wolves").
-- Es decir, no existe hoy una clave de equipo o de partido común entre las 4
-- fuentes — cada una trae la suya, o ninguna. `leagues`/`seasons` SÍ tienen
-- clave común real (columnas `league`/`season` de soccerdata, ej.
-- "ENG-Premier League"/"2425", verificadas idénticas en los 7 CSV de la
-- corrida del 8 ago en las 4 fuentes), así que esas dos no necesitan tabla de
-- mapeo.
-- Resolución para v1: `teams` y `matches` son catálogos canónicos con PK
-- propia (autoincremental, no tomada de ninguna fuente); `team_source_ids` y
-- `match_source_ids` guardan, por cada fuente, el id nativo (si lo tiene) y
-- el nombre/clave tal como aparece ahí, resueltos a un solo registro
-- canónico. El algoritmo de resolución (match por nombre normalizado,
-- revisión manual de los que no calcen) es trabajo de la tarea 2.3 (loader),
-- no de esta tarea — aquí solo se deja el lugar para guardarlo.
--
-- ============================================================================
-- Divergencia de alcance: `odds` no replica las columnas crudas de cada casa
-- ============================================================================
-- `docs/odds_columns_map.md` (tarea 1.4) ya documentó que MatchHistory trae
-- hasta 20+ casas de apuestas, 3 mercados (1X2, over/under 2.5, hándicap
-- asiático) y variante de cierre, CON UN ESQUEMA DE COLUMNAS QUE CAMBIA ENTRE
-- TEMPORADAS (118 vs. 130 columnas medido en 2425 vs. 2526). Modelar eso como
-- columnas fijas (`home_win_odd`/`draw_odd`/`away_win_odd`, tal cual el Excel)
-- sería incorrecto desde el diseño. `odds` queda en formato largo
-- (una fila por casa+mercado+partido), que tolera que aparezcan o
-- desaparezcan casas de apuestas sin tocar el esquema.

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
-- Tabla de posiciones (= tarea 8 Excel, "fixtures")
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
-- Cuotas, formato largo (ver divergencia de alcance arriba)
-- ----------------------------------------------------------------------------

CREATE TABLE odds (
    odd_id      INTEGER PRIMARY KEY AUTOINCREMENT,
    match_id    INTEGER NOT NULL REFERENCES matches(match_id),
    bookmaker   TEXT NOT NULL,  -- normalizado, ej. 'b365', 'bw', 'ps', 'max', 'avg' (ver docs/odds_columns_map.md)
    market      TEXT NOT NULL,  -- '1x2' | 'over_under_2.5' | 'asian_handicap'
    is_closing  INTEGER NOT NULL DEFAULT 0,  -- 0/1: cuota de cierre (sufijo 'C') vs. pre-cierre
    line        REAL,           -- tamaño del hándicap o total de O/U; NULL en 1x2
    home_value  REAL,           -- cuota home / over, según el mercado
    draw_value  REAL,           -- cuota de empate; solo aplica a 1x2
    away_value  REAL,           -- cuota away / under, según el mercado
    UNIQUE (match_id, bookmaker, market, is_closing, line)
);

CREATE INDEX idx_odds_match ON odds(match_id);

-- ----------------------------------------------------------------------------
-- Manifest de corridas del pipeline (divergencia ya decidida, ver arriba)
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
--     MATCHES ||--o{ ODDS : tiene
