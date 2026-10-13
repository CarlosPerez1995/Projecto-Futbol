"""Carga de catálogos y resolución de identidad entre fuentes (tarea 2.3,
solo la parte que NO depende de la confirmación de upsert pendiente).

Resuelve ``leagues``/``seasons`` (clave natural común a las 4 fuentes,
ver ``db/schema_v1.sql``) y ``teams``/``matches`` (catálogos canónicos
con tabla de mapeo por fuente, ``team_source_ids``/``match_source_ids``)
contra los CSV reales de ``data/raw/``.

Deliberadamente NO escribe ``home_score``/``away_score`` en ``matches``
(quedan en su default de ``schema_v1.sql``, ``NULL``/``'scheduled'``) ni
toca ``fixtures``/``odds``: esas tres tablas son justo las que cambian
de valor entre corridas (un marcador que se corrige, una cuota que se
actualiza), y la tarea 2.3 completa está bloqueada hasta que Carlos
confirme si eso debe sobreescribirse (upsert real) o ignorarse
(``INSERT OR IGNORE`` como decía el Excel original) — ver AGENTS.md.
Crear un partido nuevo que todavía no existe sí es seguro sin esa
confirmación: no hay ninguna fila previa con la que entrar en
conflicto.

La resolución de equipos usa ``config/team_aliases.json``, curado a
mano comparando los nombres reales de los 110 equipos (23+23+21+20+23,
5 ligas) que aparecen en las 4 fuentes de la corrida del 8 ago 2026
(verificado mecánicamente contra esos CSV, no inventado) — ver
``docs/team_aliases_notas.md``. Un equipo nuevo que no esté ahí (ej.
ascenso/descenso de una temporada futura) hace fallar la carga con un
error explícito en vez de adivinar una coincidencia aproximada.

La resolución de partidos NO usa igualdad exacta de ``match_date``:
verificado contra los datos reales (ej. Manchester United-Fulham,
2024-08-16) que MatchHistory trae la hora 1 hora adelantada respecto a
Sofascore/ESPN/Understat en partidos de agosto (hora local de Reino
Unido en horario de verano, BST = UTC+1) pero NO en partidos de febrero
(GMT = UTC+0, sin diferencia) — consistente con que MatchHistory usa
hora local del Reino Unido y las otras 3 fuentes ya vienen en UTC
(``_coerce_datetime_columns`` solo saca el tz-label, no convierte de
zona). Por eso ``resolve_or_create_match`` busca un partido existente
dentro de una ventana de ±6 horas, no con igualdad exacta — ver
``_MATCH_IDENTITY_WINDOW``.
"""
from __future__ import annotations

import json
import logging
import sqlite3
from datetime import datetime, timedelta
from pathlib import Path

import pandas as pd

logger = logging.getLogger(__name__)

DEFAULT_TEAM_ALIASES_PATH = Path("config/team_aliases.json")
DEFAULT_RAW_DIR = Path("data/raw")

# fuente -> subcarpeta en data/raw/, prefijo del CSV, columna de id nativo
# del partido (None si la fuente no trae, como match_history) y columnas de
# id nativo de equipo local/visitante (None si no, solo Understat las trae
# de las 4 fuentes ya integradas — ver docs/team_aliases_notas.md)
_MATCH_CSV_SPEC = {
    "sofascore": {
        "folder": "sofascore", "prefix": "schedule", "game_id_col": "game_id",
        "home_team_id_col": None, "away_team_id_col": None,
    },
    "espn": {
        "folder": "espn", "prefix": "espn_schedule", "game_id_col": "game_id",
        "home_team_id_col": None, "away_team_id_col": None,
    },
    "understat": {
        "folder": "understat", "prefix": "understat_team_match_stats", "game_id_col": "game_id",
        "home_team_id_col": "home_team_id", "away_team_id_col": "away_team_id",
    },
    "match_history": {
        "folder": "match_history", "prefix": "match_history", "game_id_col": None,
        "home_team_id_col": None, "away_team_id_col": None,
    },
}


def load_team_aliases(path: Path = DEFAULT_TEAM_ALIASES_PATH) -> dict:
    with open(path, encoding="utf-8") as f:
        return json.load(f)


def _latest_csv(folder: Path, prefix: str) -> Path | None:
    """Devuelve el CSV más reciente ``<prefix>_*.csv`` de ``folder``.

    El timestamp en el nombre (``%Y%m%d_%H%M%S``) ordena igual
    alfabética y cronológicamente, igual convención que
    ``_find_ultimo_csv`` de ``futbol.transform.normalize``.
    """
    if not folder.exists():
        return None
    candidatos = sorted(folder.glob(f"{prefix}_*.csv"))
    return candidatos[-1] if candidatos else None


def load_leagues(conn: sqlite3.Connection, raw_dir: Path = DEFAULT_RAW_DIR) -> int:
    """``INSERT OR IGNORE`` de ``leagues`` desde ``sofascore/leagues_*.csv``.

    Catálogo que no cambia entre corridas: no hay ninguna semántica de
    upsert en juego acá, a diferencia de matches/fixtures/odds.
    """
    path = _latest_csv(raw_dir / "sofascore", "leagues")
    if path is None:
        logger.warning("load_leagues: no hay CSV de leagues en %s/sofascore", raw_dir)
        return 0
    df = pd.read_csv(path)
    for _, row in df.iterrows():
        conn.execute(
            "INSERT OR IGNORE INTO leagues (code, region) VALUES (?, ?)",
            (row["league"], row.get("region")),
        )
    conn.commit()
    return len(df)


def load_seasons(conn: sqlite3.Connection, raw_dir: Path = DEFAULT_RAW_DIR) -> int:
    """``INSERT OR IGNORE`` de ``seasons`` desde ``sofascore/seasons_*.csv``.

    Requiere que ``load_leagues`` ya haya corrido (resuelve ``league_id``
    por el código de liga).
    """
    path = _latest_csv(raw_dir / "sofascore", "seasons")
    if path is None:
        logger.warning("load_seasons: no hay CSV de seasons en %s/sofascore", raw_dir)
        return 0
    df = pd.read_csv(path)
    cargadas = 0
    for _, row in df.iterrows():
        league_row = conn.execute(
            "SELECT league_id FROM leagues WHERE code = ?", (row["league"],)
        ).fetchone()
        if league_row is None:
            logger.warning(
                "load_seasons: liga %r no está en leagues (correr load_leagues primero), se omite season %r",
                row["league"], row["season"],
            )
            continue
        conn.execute(
            "INSERT OR IGNORE INTO seasons (league_id, code) VALUES (?, ?)",
            (league_row[0], str(row["season"])),
        )
        cargadas += 1
    conn.commit()
    return cargadas


def resolve_team(
    conn: sqlite3.Connection,
    team_aliases: dict,
    league_code: str,
    source: str,
    source_team_name: str,
    source_team_id: str | None = None,
) -> int:
    """Devuelve el ``team_id`` canónico para ``(source, source_team_name)``.

    Primera vez que se ve ese nombre en esa fuente: busca el nombre
    canónico en ``team_aliases`` (``config/team_aliases.json``), crea
    ``teams``/``team_source_ids`` si hace falta. Ya visto: devuelve el
    ``team_id`` existente sin tocar nada (los equipos no cambian de
    nombre entre corridas, a diferencia de matches/fixtures/odds).

    Lanza ``ValueError`` si el equipo no está en ``team_aliases`` para
    esa liga/fuente — no adivina una coincidencia aproximada.

    No hace ``commit()`` (lo hace el caller, una vez por lote — cientos
    de commits individuales con miles de filas de ``match_history``
    tardaban minutos por el fsync de cada uno).
    """
    row = conn.execute(
        "SELECT team_id FROM team_source_ids WHERE source = ? AND source_team_name = ?",
        (source, source_team_name),
    ).fetchone()
    if row is not None:
        return row[0]

    liga_aliases = team_aliases.get(league_code)
    if liga_aliases is None:
        raise ValueError(f"resolve_team: liga {league_code!r} no está en team_aliases.json")

    canonical_name = next(
        (
            canon
            for canon, por_fuente in liga_aliases.items()
            if por_fuente.get(source) == source_team_name
        ),
        None,
    )
    if canonical_name is None:
        raise ValueError(
            f"resolve_team: {source_team_name!r} (fuente {source!r}, liga {league_code!r}) no "
            "está en config/team_aliases.json — equipo nuevo (ascenso/descenso de otra "
            "temporada); agregarlo a mano antes de cargar esta corrida, no adivinar."
        )

    team_row = conn.execute(
        "SELECT team_id FROM teams WHERE canonical_name = ?", (canonical_name,)
    ).fetchone()
    if team_row is None:
        cur = conn.execute("INSERT INTO teams (canonical_name) VALUES (?)", (canonical_name,))
        team_id = cur.lastrowid
    else:
        team_id = team_row[0]

    conn.execute(
        "INSERT OR IGNORE INTO team_source_ids (team_id, source, source_team_id, source_team_name) "
        "VALUES (?, ?, ?, ?)",
        (team_id, source, source_team_id, source_team_name),
    )
    return team_id


def _get_season_id(conn: sqlite3.Connection, league_code: str, season_code: str) -> int:
    row = conn.execute(
        """
        SELECT s.season_id FROM seasons s
        JOIN leagues l ON l.league_id = s.league_id
        WHERE l.code = ? AND s.code = ?
        """,
        (league_code, str(season_code)),
    ).fetchone()
    if row is None:
        raise ValueError(
            f"_get_season_id: no existe season {season_code!r} de liga {league_code!r} "
            "— correr load_leagues/load_seasons primero"
        )
    return row[0]


# Tolerancia para considerar que dos filas de fuentes distintas son el mismo
# partido, pese a no tener la misma hora exacta de kickoff (ver docstring del
# módulo: MatchHistory viene en hora local de Reino Unido, las otras 3 ya en
# UTC — hasta 1h de diferencia en horario de verano). 6h es generoso a
# propósito: ningún partido de liga de la misma pareja local/visitante se
# repite dentro de esa ventana.
_MATCH_IDENTITY_WINDOW = timedelta(hours=6)


def _find_existing_match(
    conn: sqlite3.Connection,
    season_id: int,
    home_team_id: int,
    away_team_id: int,
    match_date: str,
) -> int | None:
    dt = datetime.fromisoformat(match_date)
    low = (dt - _MATCH_IDENTITY_WINDOW).isoformat(sep=" ")
    high = (dt + _MATCH_IDENTITY_WINDOW).isoformat(sep=" ")
    row = conn.execute(
        "SELECT match_id FROM matches "
        "WHERE season_id = ? AND home_team_id = ? AND away_team_id = ? "
        "AND match_date BETWEEN ? AND ? "
        "ORDER BY ABS(strftime('%s', match_date) - strftime('%s', ?)) LIMIT 1",
        (season_id, home_team_id, away_team_id, low, high, match_date),
    ).fetchone()
    return row[0] if row is not None else None


def resolve_or_create_match(
    conn: sqlite3.Connection,
    team_aliases: dict,
    *,
    league_code: str,
    season_code: str,
    source: str,
    source_match_id: str | None,
    source_game_key: str,
    home_team_name: str,
    away_team_name: str,
    match_date: str,
    home_team_source_id: str | None = None,
    away_team_source_id: str | None = None,
) -> int:
    """Devuelve el ``match_id`` canónico para ``(source, source_game_key)``.

    Ya visto desde esta fuente: devuelve el existente. Nuevo desde esta
    fuente pero ya creado por otra (mismo season/home/away, fecha dentro
    de ``_MATCH_IDENTITY_WINDOW``): solo agrega la fila de mapeo. Nuevo
    del todo: lo crea con ``INSERT``
    simple — sin marcador ni estado (default ``'scheduled'`` de
    ``schema_v1.sql``), porque escribir/actualizar esos valores es
    justo lo que depende de la confirmación de upsert pendiente.

    No hace ``commit()`` (lo hace el caller, una vez por lote).
    """
    row = conn.execute(
        "SELECT match_id FROM match_source_ids WHERE source = ? AND source_game_key = ?",
        (source, source_game_key),
    ).fetchone()
    if row is not None:
        return row[0]

    season_id = _get_season_id(conn, league_code, season_code)
    home_team_id = resolve_team(
        conn, team_aliases, league_code, source, home_team_name, home_team_source_id
    )
    away_team_id = resolve_team(
        conn, team_aliases, league_code, source, away_team_name, away_team_source_id
    )

    existing_match_id = _find_existing_match(conn, season_id, home_team_id, away_team_id, match_date)
    if existing_match_id is not None:
        match_id = existing_match_id
    else:
        cur = conn.execute(
            "INSERT INTO matches (season_id, home_team_id, away_team_id, match_date) "
            "VALUES (?, ?, ?, ?)",
            (season_id, home_team_id, away_team_id, match_date),
        )
        match_id = cur.lastrowid

    conn.execute(
        "INSERT OR IGNORE INTO match_source_ids "
        "(match_id, source, source_match_id, source_game_key) VALUES (?, ?, ?, ?)",
        (match_id, source, source_match_id, source_game_key),
    )
    return match_id


def _optional_str(row: pd.Series, col_name: str | None) -> str | None:
    if col_name and col_name in row.index and pd.notna(row[col_name]):
        return str(row[col_name])
    return None


def load_matches(
    conn: sqlite3.Connection,
    team_aliases: dict,
    raw_dir: Path = DEFAULT_RAW_DIR,
) -> dict[str, int]:
    """Resuelve/crea ``matches`` desde el CSV más reciente de cada fuente
    disponible en ``raw_dir``. Devuelve cuántas filas se procesaron por
    fuente. Requiere ``load_leagues``/``load_seasons`` ya corridos.
    """
    procesados: dict[str, int] = {}
    for source, spec in _MATCH_CSV_SPEC.items():
        path = _latest_csv(raw_dir / spec["folder"], spec["prefix"])
        if path is None:
            logger.info("load_matches: no hay CSV de %s en %s", source, raw_dir / spec["folder"])
            continue
        df = pd.read_csv(path)
        count = 0
        for _, row in df.iterrows():
            resolve_or_create_match(
                conn,
                team_aliases,
                league_code=row["league"],
                season_code=row["season"],
                source=source,
                source_match_id=_optional_str(row, spec["game_id_col"]),
                source_game_key=row["game"],
                home_team_name=row["home_team"],
                away_team_name=row["away_team"],
                match_date=row["date"],
                home_team_source_id=_optional_str(row, spec["home_team_id_col"]),
                away_team_source_id=_optional_str(row, spec["away_team_id_col"]),
            )
            count += 1
        conn.commit()
        procesados[source] = count
        logger.info("load_matches: %d partidos de %s procesados desde %s", count, source, path)
    return procesados
