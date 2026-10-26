"""Tests de ``src/futbol/db/load_data.py`` contra BD y CSV sintéticos.

No hacen ninguna llamada de red ni dependen de los CSV reales de
``data/raw/`` (esos cambian de timestamp en cada corrida real). El set
completo de equipos reales de ``config/team_aliases.json`` se valida
aparte, en ``test_resolve_team_catalogo_real_sin_errores``.
"""
from __future__ import annotations

from pathlib import Path

import pandas as pd
import pytest

from futbol.db.database import init_db, get_connection
from futbol.db.load_data import (
    _find_existing_match,
    _parse_1x2_odds,
    _timestamp_from_filename,
    load_fixtures,
    load_leagues,
    load_matches,
    load_odds_1x2,
    load_seasons,
    load_team_aliases,
    resolve_or_create_match,
    resolve_team,
    upsert_match_result,
)

REPO_ROOT = Path(__file__).resolve().parent.parent
REPO_SCHEMA_PATH = REPO_ROOT / "db" / "schema_v3.sql"
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
    assert fila == (None, None, "scheduled")  # esta fuente no traía marcador en el llamado


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


# ---------------------------------------------------------------------------
# upsert_match_result
# ---------------------------------------------------------------------------

def test_upsert_match_result_escribe_marcador_y_marca_jugado(conn):
    season_id = _season_id(conn)
    home_id = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team A")
    away_id = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team B")
    cur = conn.execute(
        "INSERT INTO matches (season_id, home_team_id, away_team_id, match_date) "
        "VALUES (?, ?, ?, '2024-08-16 19:00:00')",
        (season_id, home_id, away_id),
    )
    match_id = cur.lastrowid

    upsert_match_result(conn, match_id, 2, 1)
    conn.commit()

    fila = conn.execute(
        "SELECT home_score, away_score, status FROM matches WHERE match_id = ?", (match_id,)
    ).fetchone()
    assert fila == (2, 1, "played")


def test_upsert_match_result_sin_marcador_no_toca_nada(conn):
    season_id = _season_id(conn)
    home_id = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team A")
    away_id = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team B")
    cur = conn.execute(
        "INSERT INTO matches (season_id, home_team_id, away_team_id, match_date) "
        "VALUES (?, ?, ?, '2024-08-16 19:00:00')",
        (season_id, home_id, away_id),
    )
    match_id = cur.lastrowid
    upsert_match_result(conn, match_id, 2, 1)  # una fuente SÍ trae marcador
    conn.commit()

    upsert_match_result(conn, match_id, None, None)  # otra fuente (ej. ESPN) no trae
    conn.commit()

    fila = conn.execute(
        "SELECT home_score, away_score, status FROM matches WHERE match_id = ?", (match_id,)
    ).fetchone()
    assert fila == (2, 1, "played")  # no se "des-juega" el partido


def test_upsert_match_result_sobrescribe_con_el_valor_mas_reciente(conn):
    season_id = _season_id(conn)
    home_id = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team A")
    away_id = resolve_team(conn, _TEST_ALIASES, "TEST-League", "sofascore", "Team B")
    cur = conn.execute(
        "INSERT INTO matches (season_id, home_team_id, away_team_id, match_date) "
        "VALUES (?, ?, ?, '2024-08-16 19:00:00')",
        (season_id, home_id, away_id),
    )
    match_id = cur.lastrowid

    upsert_match_result(conn, match_id, 1, 1)  # marcador provisional/erróneo
    upsert_match_result(conn, match_id, 2, 1)  # corrección posterior
    conn.commit()

    fila = conn.execute(
        "SELECT home_score, away_score FROM matches WHERE match_id = ?", (match_id,)
    ).fetchone()
    assert fila == (2, 1)  # upsert real: queda el más reciente, no el primero


# ---------------------------------------------------------------------------
# _timestamp_from_filename
# ---------------------------------------------------------------------------

def test_timestamp_from_filename_extrae_fecha_de_la_corrida():
    resultado = _timestamp_from_filename(Path("match_history_20260808_201736.csv"))
    assert resultado == "2026-08-08 20:17:36"


def test_timestamp_from_filename_formato_invalido_lanza_valueerror():
    with pytest.raises(ValueError, match="no tiene el formato"):
        _timestamp_from_filename(Path("archivo_sin_timestamp.csv"))


# ---------------------------------------------------------------------------
# _parse_1x2_odds / load_odds_1x2
# ---------------------------------------------------------------------------

def test_parse_1x2_odds_extrae_pre_cierre_y_cierre():
    row = pd.Series({
        "b365h": 1.6, "b365d": 4.2, "b365a": 5.25,
        "b365ch": 1.67, "b365cd": 4.1, "b365ca": 5.0,
        "columna_no_relacionada": "x",
    })

    cuotas = _parse_1x2_odds(row)

    assert {"bookmaker": "b365", "is_closing": 0, "home_value": 1.6, "draw_value": 4.2, "away_value": 5.25} in cuotas
    assert {"bookmaker": "b365", "is_closing": 1, "home_value": 1.67, "draw_value": 4.1, "away_value": 5.0} in cuotas
    assert len(cuotas) == 2  # solo b365, ninguna otra casa tiene columnas en esta fila


def test_parse_1x2_odds_omite_casa_totalmente_vacia():
    row = pd.Series({"b365h": None, "b365d": None, "b365a": None})

    assert _parse_1x2_odds(row) == []


@pytest.fixture
def raw_dir_con_marcador_y_cuotas(tmp_path: Path) -> Path:
    raw_dir = tmp_path / "raw"
    (raw_dir / "sofascore").mkdir(parents=True)
    (raw_dir / "match_history").mkdir(parents=True)

    (raw_dir / "sofascore" / "leagues_20260101_000000.csv").write_text(
        "league,league_id,region\nTEST-League,1,TST\n", encoding="utf-8"
    )
    (raw_dir / "sofascore" / "seasons_20260101_000000.csv").write_text(
        "league,season,league_id,season_id\nTEST-League,2024,1,1\n", encoding="utf-8"
    )
    (raw_dir / "sofascore" / "schedule_20260101_000000.csv").write_text(
        "league,season,game,date,home_team,away_team,home_score,away_score,game_id\n"
        "TEST-League,2024,2024-08-16 Team A-Team B,2024-08-16 19:00:00,Team A,Team B,2,1,999\n",
        encoding="utf-8",
    )
    (raw_dir / "match_history" / "match_history_20260101_000000.csv").write_text(
        "league,season,game,date,home_team,away_team,fthg,ftag,b365h,b365d,b365a\n"
        "TEST-League,2024,2024-08-16 A-B,2024-08-16 20:00:00,A,B,2,1,1.6,4.2,5.25\n",
        encoding="utf-8",
    )
    return raw_dir


def test_load_matches_escribe_marcador_desde_sofascore_y_match_history(
    conn, raw_dir_con_marcador_y_cuotas
):
    load_leagues(conn, raw_dir_con_marcador_y_cuotas)
    load_seasons(conn, raw_dir_con_marcador_y_cuotas)

    load_matches(conn, _TEST_ALIASES, raw_dir_con_marcador_y_cuotas)

    fila = conn.execute("SELECT home_score, away_score, status FROM matches").fetchone()
    assert fila == (2, 1, "played")


def test_load_odds_1x2_guarda_historico_y_es_idempotente_por_corrida(
    conn, raw_dir_con_marcador_y_cuotas
):
    load_leagues(conn, raw_dir_con_marcador_y_cuotas)
    load_seasons(conn, raw_dir_con_marcador_y_cuotas)
    load_matches(conn, _TEST_ALIASES, raw_dir_con_marcador_y_cuotas)

    n_1 = load_odds_1x2(conn, raw_dir_con_marcador_y_cuotas)
    assert n_1 == 1  # un solo bookmaker (b365) con datos en el CSV de prueba
    assert conn.execute("SELECT COUNT(*) FROM odds").fetchone()[0] == 1

    # recargar la MISMA corrida (mismo captured_at) no duplica
    n_2 = load_odds_1x2(conn, raw_dir_con_marcador_y_cuotas)
    assert n_2 == 1
    assert conn.execute("SELECT COUNT(*) FROM odds").fetchone()[0] == 1

    # una corrida NUEVA (otro timestamp de archivo) sí queda como fila aparte
    nueva = raw_dir_con_marcador_y_cuotas / "match_history" / "match_history_20260215_120000.csv"
    nueva.write_text(
        (raw_dir_con_marcador_y_cuotas / "match_history" / "match_history_20260101_000000.csv")
        .read_text(encoding="utf-8")
        .replace("1.6,4.2,5.25", "1.7,4.0,5.1"),  # la cuota se movió
        encoding="utf-8",
    )
    n_3 = load_odds_1x2(conn, raw_dir_con_marcador_y_cuotas)
    assert n_3 == 1
    assert conn.execute("SELECT COUNT(*) FROM odds").fetchone()[0] == 2  # histórico, no se pisó

    valores = {r[0] for r in conn.execute("SELECT home_value FROM odds ORDER BY captured_at")}
    assert valores == {1.6, 1.7}


# ---------------------------------------------------------------------------
# load_fixtures
# ---------------------------------------------------------------------------

@pytest.fixture
def raw_dir_con_standings(tmp_path: Path) -> Path:
    raw_dir = tmp_path / "raw"
    (raw_dir / "sofascore").mkdir(parents=True)

    (raw_dir / "sofascore" / "leagues_20260101_000000.csv").write_text(
        "league,league_id,region\nTEST-League,1,TST\n", encoding="utf-8"
    )
    (raw_dir / "sofascore" / "seasons_20260101_000000.csv").write_text(
        "league,season,league_id,season_id\nTEST-League,2024,1,1\n", encoding="utf-8"
    )
    (raw_dir / "sofascore" / "standings_20260101_000000.csv").write_text(
        "league,season,team,mp,w,d,l,gf,ga,gd,pts\n"
        "TEST-League,2024,Team A,10,8,1,1,20,5,15,25\n"
        "TEST-League,2024,Team B,10,5,2,3,15,12,3,17\n",
        encoding="utf-8",
    )
    return raw_dir


def test_load_fixtures_calcula_posicion_por_orden_de_fila(conn, raw_dir_con_standings):
    load_leagues(conn, raw_dir_con_standings)
    load_seasons(conn, raw_dir_con_standings)

    n = load_fixtures(conn, _TEST_ALIASES, raw_dir_con_standings)

    assert n == 2
    filas = conn.execute(
        """
        SELECT t.canonical_name, f.position, f.points
        FROM fixtures f JOIN teams t ON t.team_id = f.team_id
        ORDER BY f.position
        """
    ).fetchall()
    assert filas == [("Team A", 1, 25), ("Team B", 2, 17)]


def test_load_fixtures_guarda_historico_y_es_idempotente_por_corrida(conn, raw_dir_con_standings):
    load_leagues(conn, raw_dir_con_standings)
    load_seasons(conn, raw_dir_con_standings)
    load_fixtures(conn, _TEST_ALIASES, raw_dir_con_standings)

    # recargar la MISMA corrida no duplica
    load_fixtures(conn, _TEST_ALIASES, raw_dir_con_standings)
    assert conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0] == 2

    # una corrida NUEVA (otro timestamp) con datos distintos sí queda aparte
    nueva = raw_dir_con_standings / "sofascore" / "standings_20260215_120000.csv"
    nueva.write_text(
        "league,season,team,mp,w,d,l,gf,ga,gd,pts\n"
        "TEST-League,2024,Team A,11,9,1,1,22,5,17,28\n"
        "TEST-League,2024,Team B,11,5,2,4,15,14,1,17\n",
        encoding="utf-8",
    )
    load_fixtures(conn, _TEST_ALIASES, raw_dir_con_standings)

    assert conn.execute("SELECT COUNT(*) FROM fixtures").fetchone()[0] == 4
    puntos_team_a = {
        r[0] for r in conn.execute(
            "SELECT f.points FROM fixtures f JOIN teams t ON t.team_id = f.team_id "
            "WHERE t.canonical_name = 'Team A'"
        )
    }
    assert puntos_team_a == {25, 28}  # las dos capturas, no se pisó la vieja
