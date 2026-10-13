"""Tests de ``src/futbol/db/load_data.py`` contra BD y CSV sintéticos.

No hacen ninguna llamada de red ni dependen de los CSV reales de
``data/raw/`` (esos cambian de timestamp en cada corrida real). El set
completo de equipos reales de ``config/team_aliases.json`` se valida
aparte, en ``test_resolve_team_catalogo_real_sin_errores``.
"""
from __future__ import annotations

from pathlib import Path

import pytest

from futbol.db.database import init_db, get_connection
from futbol.db.load_data import (
    _find_existing_match,
    load_leagues,
    load_matches,
    load_seasons,
    load_team_aliases,
    resolve_or_create_match,
    resolve_team,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_SCHEMA_PATH = REPO_ROOT / "db" / "schema_v1.sql"
REPO_TEAM_ALIASES_PATH = REPO_ROOT / "config" / "team_aliases.json"

_TEST_ALIASES = {
    "TEST-League": {
        "Team A": {
            "sofascore": "Team A", "espn": "Team A FC",
            "understat": "Team A", "match_history": "A",
        },
        "Team B": {
            "sofascore": "Team B", "espn": "Team B FC",
            "understat": "Team B", "match_history": "B",
        },
    }
}


@pytest.fixture
def conn(tmp_path: Path):
    db_path = tmp_path / "futbol.db"
    init_db(db_path, REPO_SCHEMA_PATH)
    connection = get_connection(db_path)
    connection.execute("INSERT INTO leagues (code, region) VALUES ('TEST-League', 'TST')")
    connection.execute(
        "INSERT INTO seasons (league_id, code) VALUES "
        "((SELECT league_id FROM leagues WHERE code = 'TEST-League'), '2024')"
    )
    connection.commit()
    yield connection
    connection.close()


def _season_id(conn) -> int:
    return conn.execute("SELECT season_id FROM seasons").fetchone()[0]


# ---------------------------------------------------------------------------
# resolve_team
# ---------------------------------------------------------------------------

def test_resolve_team_crea_team_y_mapeo_nuevo(conn):
    team_id = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team A")

    canonical = conn.execute(
        "SELECT canonical_name FROM teams WHERE team_id = ?", (team_id,)
    ).fetchone()[0]
    assert canonical == "Team A"

    mapeo = conn.execute(
        "SELECT team_id FROM team_source_ids WHERE source = 'sofascore' AND source_team_name = 'Team A'"
    ).fetchone()[0]
    assert mapeo == team_id


def test_resolve_team_mismo_canonico_desde_dos_fuentes_distintas(conn):
    id_sofa = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team A")
    id_mh = resolve_team(conn, _TEST_ALIASES, "TEST-League", "match_history", "A")

    assert id_sofa == id_mh
    cantidad_teams = conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    assert cantidad_teams == 1  # no crea un segundo team para el mismo equipo


def test_resolve_team_segunda_llamada_reutiliza_sin_duplicar(conn):
    id_1 = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team A")
    id_2 = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team A")

    assert id_1 == id_2
    cantidad_mapeos = conn.execute("SELECT COUNT(*) FROM team_source_ids").fetchone()[0]
    assert cantidad_mapeos == 1


def test_resolve_team_equipo_desconocido_lanza_valueerror(conn):
    with pytest.raises(ValueError, match="no está en config/team_aliases.json"):
        resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Equipo Fantasma")


def test_resolve_team_liga_desconocida_lanza_valueerror(conn):
    with pytest.raises(ValueError, match="no está en team_aliases.json"):
        resolve_team(conn, _TEST_ALIASES, "LIGA-Inexistente", "sofascore", "Team A")


def test_resolve_team_catalogo_real_sin_errores(tmp_path: Path):
    """Smoke test contra el archivo real: cada equipo de cada liga debe
    poder resolverse en cada una de sus 4 fuentes sin lanzar error —
    ver docs/team_aliases_notas.md para cómo se verificó el contenido
    contra los CSV reales.
    """
    db_path = tmp_path / "futbol.db"
    init_db(db_path, REPO_SCHEMA_PATH)
    connection = get_connection(db_path)
    team_aliases = load_team_aliases(REPO_TEAM_ALIASES_PATH)

    for liga, equipos in team_aliases.items():
        connection.execute("INSERT OR IGNORE INTO leagues (code) VALUES (?)", (liga,))
        for canon, por_fuente in equipos.items():
            for source, nombre in por_fuente.items():
                team_id = resolve_team(connection, team_aliases, liga, source, nombre)
                assert team_id is not None
    connection.commit()

    cantidad_teams = connection.execute("SELECT COUNT(*) FROM teams").fetchone()[0]
    assert cantidad_teams == 110  # 23+23+21+20+23, ver docs/team_aliases_notas.md
    connection.close()


# ---------------------------------------------------------------------------
# _find_existing_match / resolve_or_create_match
# ---------------------------------------------------------------------------

def test_find_existing_match_dentro_de_la_ventana(conn):
    season_id = _season_id(conn)
    home_id = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team A")
    away_id = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team B")
    cur = conn.execute(
        "INSERT INTO matches (season_id, home_team_id, away_team_id, match_date) "
        "VALUES (?, ?, ?, '2024-08-16 19:00:00')",
        (season_id, home_id, away_id),
    )
    match_id = cur.lastrowid

    encontrado = _find_existing_match(conn, season_id, home_id, away_id, "2024-08-16 20:00:00")  # +1h

    assert encontrado == match_id


def test_find_existing_match_fuera_de_la_ventana_no_matchea(conn):
    season_id = _season_id(conn)
    home_id = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team A")
    away_id = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team B")
    conn.execute(
        "INSERT INTO matches (season_id, home_team_id, away_team_id, match_date) "
        "VALUES (?, ?, ?, '2024-08-16 19:00:00')",
        (season_id, home_id, away_id),
    )

    encontrado = _find_existing_match(conn, season_id, home_id, away_id, "2024-08-17 02:00:00")  # +7h

    assert encontrado is None


def test_resolve_or_create_match_crea_nuevo_partido(conn):
    match_id = resolve_or_create_match(
        conn, _TEST_ALIASES,
        league_code="TEST-League", season_code="2024", source="sofascore",
        source_match_id="123", source_game_key="2024-08-16 Team A-Team B",
        home_team_name="Team A", away_team_name="Team B", match_date="2024-08-16 19:00:00",
    )
    conn.commit()

    fila = conn.execute(
        "SELECT home_score, away_score, status FROM matches WHERE match_id = ?", (match_id,)
    ).fetchone()
    assert fila == (None, None, "scheduled")  # tarea 2.3 no escribe marcador todavía


def test_resolve_or_create_match_misma_fuente_segunda_vez_reutiliza(conn):
    id_1 = resolve_or_create_match(
        conn, _TEST_ALIASES,
        league_code="TEST-League", season_code="2024", source="sofascore",
        source_match_id="123", source_game_key="2024-08-16 Team A-Team B",
        home_team_name="Team A", away_team_name="Team B", match_date="2024-08-16 19:00:00",
    )
    id_2 = resolve_or_create_match(
        conn, _TEST_ALIASES,
        league_code="TEST-League", season_code="2024", source="sofascore",
        source_match_id="123", source_game_key="2024-08-16 Team A-Team B",
        home_team_name="Team A", away_team_name="Team B", match_date="2024-08-16 19:00:00",
    )
    conn.commit()

    assert id_1 == id_2
    assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 1


def test_resolve_or_create_match_otra_fuente_misma_hora_distinta_reutiliza_por_ventana(conn):
    """El caso real encontrado: MatchHistory 1h adelantado respecto a las
    otras 3 fuentes en horario de verano — no debe crear un partido
    duplicado."""
    id_sofa = resolve_or_create_match(
        conn, _TEST_ALIASES,
        league_code="TEST-League", season_code="2024", source="sofascore",
        source_match_id="123", source_game_key="2024-08-16 Team A-Team B",
        home_team_name="Team A", away_team_name="Team B", match_date="2024-08-16 19:00:00",
    )
    id_mh = resolve_or_create_match(
        conn, _TEST_ALIASES,
        league_code="TEST-League", season_code="2024", source="match_history",
        source_match_id=None, source_game_key="2024-08-16 A-B",
        home_team_name="A", away_team_name="B", match_date="2024-08-16 20:00:00",
    )
    conn.commit()

    assert id_sofa == id_mh
    assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 1
    cantidad_fuentes = conn.execute(
        "SELECT COUNT(*) FROM match_source_ids WHERE match_id = ?", (id_sofa,)
    ).fetchone()[0]
    assert cantidad_fuentes == 2


# ---------------------------------------------------------------------------
# load_leagues / load_seasons
# ---------------------------------------------------------------------------

def test_load_leagues_inserta_catalogo(tmp_path: Path):
    db_path = tmp_path / "futbol.db"
    init_db(db_path, REPO_SCHEMA_PATH)
    connection = get_connection(db_path)

    raw_dir = tmp_path / "raw"
    (raw_dir / "sofascore").mkdir(parents=True)
    (raw_dir / "sofascore" / "leagues_20260101_000000.csv").write_text(
        "league,league_id,region\nTEST-League,1,TST\n", encoding="utf-8"
    )

    n = load_leagues(connection, raw_dir)

    assert n == 1
    assert connection.execute("SELECT code, region FROM leagues").fetchone() == ("TEST-League", "TST")
    connection.close()


def test_load_seasons_omite_season_sin_liga_cargada(tmp_path: Path):
    db_path = tmp_path / "futbol.db"
    init_db(db_path, REPO_SCHEMA_PATH)
    connection = get_connection(db_path)

    raw_dir = tmp_path / "raw"
    (raw_dir / "sofascore").mkdir(parents=True)
    (raw_dir / "sofascore" / "seasons_20260101_000000.csv").write_text(
        "league,season,league_id,season_id\nLIGA-Sin-Cargar,2024,1,1\n", encoding="utf-8"
    )

    n = load_seasons(connection, raw_dir)

    assert n == 0
    assert connection.execute("SELECT COUNT(*) FROM seasons").fetchone()[0] == 0
    connection.close()


# ---------------------------------------------------------------------------
# load_matches (end-to-end con las 4 fuentes, idempotencia)
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_dir_con_4_fuentes(tmp_path: Path) -> Path:
    raw_dir = tmp_path / "raw"
    (raw_dir / "sofascore").mkdir(parents=True)
    (raw_dir / "espn").mkdir(parents=True)
    (raw_dir / "understat").mkdir(parents=True)
    (raw_dir / "match_history").mkdir(parents=True)

    (raw_dir / "sofascore" / "leagues_20260101_000000.csv").write_text(
        "league,league_id,region\nTEST-League,1,TST\n", encoding="utf-8"
    )
    (raw_dir / "sofascore" / "seasons_20260101_000000.csv").write_text(
        "league,season,league_id,season_id\nTEST-League,2024,1,1\n", encoding="utf-8"
    )
    (raw_dir / "sofascore" / "schedule_20260101_000000.csv").write_text(
        "league,season,game,date,home_team,away_team,home_score,away_score,game_id\n"
        "TEST-League,2024,2024-08-16 Team A-Team B,2024-08-16 19:00:00,Team A,Team B,,,999\n",
        encoding="utf-8",
    )
    (raw_dir / "espn" / "espn_schedule_20260101_000000.csv").write_text(
        "league,season,game,date,home_team,away_team,game_id,league_id\n"
        "TEST-League,2024,2024-08-16 Team A FC-Team B FC,2024-08-16 19:00:00,Team A FC,Team B FC,888,test.1\n",
        encoding="utf-8",
    )
    (raw_dir / "understat" / "understat_team_match_stats_20260101_000000.csv").write_text(
        "league,season,game,home_team_id,away_team_id,date,home_team,away_team\n"
        "TEST-League,2024,2024-08-16 Team A-Team B,10,20,2024-08-16 19:00:00,Team A,Team B\n",
        encoding="utf-8",
    )
    (raw_dir / "match_history" / "match_history_20260101_000000.csv").write_text(
        "league,season,game,date,home_team,away_team\n"
        "TEST-League,2024,2024-08-16 A-B,2024-08-16 20:00:00,A,B\n",
        encoding="utf-8",
    )
    return raw_dir


def test_load_matches_resuelve_las_4_fuentes_al_mismo_partido(conn, raw_dir_con_4_fuentes):
    load_leagues(conn, raw_dir_con_4_fuentes)
    load_seasons(conn, raw_dir_con_4_fuentes)

    procesados = load_matches(conn, _TEST_ALIASES, raw_dir_con_4_fuentes)

    assert procesados == {"sofascore": 1, "espn": 1, "understat": 1, "match_history": 1}
    assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM match_source_ids").fetchone()[0] == 4

    # el id nativo de equipo de Understat sí queda registrado
    fila = conn.execute(
        "SELECT source_team_id FROM team_source_ids WHERE source='understat' AND source_team_name='Team A'"
    ).fetchone()
    assert fila[0] == "10"


def test_load_matches_segunda_corrida_es_idempotente(conn, raw_dir_con_4_fuentes):
    load_leagues(conn, raw_dir_con_4_fuentes)
    load_seasons(conn, raw_dir_con_4_fuentes)
    load_matches(conn, _TEST_ALIASES, raw_dir_con_4_fuentes)

    load_leagues(conn, raw_dir_con_4_fuentes)
    load_seasons(conn, raw_dir_con_4_fuentes)
    load_matches(conn, _TEST_ALIASES, raw_dir_con_4_fuentes)

    assert conn.execute("SELECT COUNT(*) FROM matches").fetchone()[0] == 1
    assert conn.execute("SELECT COUNT(*) FROM match_source_ids").fetchone()[0] == 4
    assert conn.execute("SELECT COUNT(*) FROM teams").fetchone()[0] == 2
