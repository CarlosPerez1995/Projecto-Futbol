"""Backtesting histórico de apuestas (tarea 4.5, puente hacia Fase 5).

Simula qué habría pasado apostando según valor esperado + Kelly
fraccionado (``futbol.betting.ev_kelly``) sobre el split ``test``
(nunca visto en entrenamiento ni calibración, ver
``futbol.models.split``) de cada modelo, usando las cuotas REALES de
cierre ya cargadas en la BD (no hipotéticas) — el mismo
``bookmaker='avg'``/``is_closing=1`` que ya se usa como feature en
``futbol.features.odds``.

**Limitación real encontrada al construir esto, no un bug**: este
dataset solo tiene cuotas de mercado cargadas para 1x2 y over/under
2.5 (`db/schema_v4.sql`, `docs/odds_columns_map.md`) — no existe una
cuota de over/under 1.5, aunque sí existe un modelo entrenado para ese
mercado (`xgb_over_1_5`, Fase 4) con buena métrica (AUC 0.601). Sin
una cuota real a la que apostar, ese mercado no se puede backtestear
ni operar todavía — `backtest_over_1_5` queda señalado como pendiente
de que se cargue esa cuota (no de este dataset actual), no implementado
acá por falta de datos, no por falta de código.
"""
from __future__ import annotations

import sqlite3
from pathlib import Path

import joblib
import pandas as pd

from futbol.betting.ev_kelly import expected_value, fractional_kelly
from futbol.models.xgb_1x2 import DEFAULT_MODELS_DIR as XGB_1X2_MODELS_DIR
from futbol.models.xgb_1x2 import _features

DEFAULT_KELLY_MULTIPLIER = 0.5
DEFAULT_MAX_FRACTION = 0.05
DEFAULT_EV_THRESHOLD = 0.0
DEFAULT_BANKROLL_INICIAL = 1000.0


def _latest_model_dir(models_dir) -> Path:
    models_dir = Path(models_dir)
    candidatos = sorted(p for p in models_dir.glob("*") if p.is_dir())
    if not candidatos:
        raise FileNotFoundError(f"backtest: no hay ningún modelo guardado en {models_dir}")
    return candidatos[-1]


def _odds_1x2_reales(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT match_id, home_value AS odds_h, draw_value AS odds_d, away_value AS odds_a "
        "FROM odds WHERE market = '1x2' AND is_closing = 1 AND bookmaker = 'avg'",
        conn,
    )


def _odds_over_under_25_reales(conn: sqlite3.Connection) -> pd.DataFrame:
    return pd.read_sql_query(
        "SELECT match_id, home_value AS odds_over, away_value AS odds_under "
        "FROM odds WHERE market = 'over_under_2.5' AND is_closing = 1 AND bookmaker = 'avg'",
        conn,
    )


def _max_drawdown_pct(bankroll_tras_cada_apuesta: pd.Series, bankroll_inicial: float) -> float:
    serie = pd.concat(
        [pd.Series([bankroll_inicial]), bankroll_tras_cada_apuesta], ignore_index=True
    )
    pico = serie.cummax()
    caida = (serie - pico) / pico
    return float(caida.min() * 100)


def _simular_apuestas(
    candidatos: list[dict],
    ev_threshold: float,
    kelly_multiplier: float,
    max_fraction: float,
    bankroll_inicial: float,
) -> tuple[list[dict], float]:
    """Núcleo puro de la simulación, sin BD ni modelo — testeado
    directo. ``candidatos`` es una lista de apuestas posibles, EN
    ORDEN CRONOLÓGICO (los de un mismo partido pueden ir consecutivos,
    eso no importa para el resultado, solo el orden entre partidos
    distintos), cada una con ``match_id``/``label``/``p``/``odds``/
    ``gano`` (si esa apuesta puntual habría ganado, según lo que
    realmente pasó). El banco se actualiza apuesta por apuesta, nunca
    partido por partido — si dos apuestas de un mismo partido califican
    a la vez (ej. H y D en el mismo partido, inusual pero posible), la
    segunda ya ve el banco actualizado por la primera, simplificación
    conocida (no es una optimización conjunta de apuestas mutuamente
    excluyentes).
    """
    bankroll = bankroll_inicial
    apuestas = []
    for c in candidatos:
        p, odds = c["p"], c["odds"]
        if pd.isna(odds) or pd.isna(p):
            continue
        ev = expected_value(p, odds)
        if ev <= ev_threshold:
            continue
        f = fractional_kelly(p, odds, kelly_multiplier, max_fraction)
        if f <= 0:
            continue
        stake = bankroll * f
        profit = stake * (odds - 1) if c["gano"] else -stake
        bankroll += profit
        apuestas.append({
            "match_id": c["match_id"], "resultado_apostado": c["label"],
            "prob_modelo": p, "cuota": odds, "ev": ev, "stake": stake,
            "gano": c["gano"], "profit": profit, "bankroll_despues": bankroll,
        })
    return apuestas, bankroll


def _resumen(
    apuestas: list[dict],
    bankroll_inicial: float,
    bankroll_final: float,
    n_partidos_con_cuota: int,
) -> dict:
    df_apuestas = pd.DataFrame(apuestas)
    if len(df_apuestas) == 0:
        return {
            "n_partidos_con_cuota": n_partidos_con_cuota,
            "n_apuestas": 0,
            "tasa_acierto": None,
            "total_staked": 0.0,
            "profit_total": 0.0,
            "roi": None,
            "bankroll_inicial": bankroll_inicial,
            "bankroll_final": bankroll_inicial,
            "retorno_sobre_banco_pct": 0.0,
            "max_drawdown_pct": 0.0,
        }
    return {
        "n_partidos_con_cuota": n_partidos_con_cuota,
        "n_apuestas": len(df_apuestas),
        "tasa_acierto": float(df_apuestas["gano"].mean()),
        "total_staked": float(df_apuestas["stake"].sum()),
        "profit_total": float(df_apuestas["profit"].sum()),
        "roi": float(df_apuestas["profit"].sum() / df_apuestas["stake"].sum()),
        "bankroll_inicial": bankroll_inicial,
        "bankroll_final": bankroll_final,
        "retorno_sobre_banco_pct": (bankroll_final - bankroll_inicial) / bankroll_inicial * 100,
        "max_drawdown_pct": _max_drawdown_pct(df_apuestas["bankroll_despues"], bankroll_inicial),
    }


def backtest_1x2(
    conn: sqlite3.Connection,
    test_df: pd.DataFrame,
    modelo_path=None,
    kelly_multiplier: float = DEFAULT_KELLY_MULTIPLIER,
    max_fraction: float = DEFAULT_MAX_FRACTION,
    ev_threshold: float = DEFAULT_EV_THRESHOLD,
    bankroll_inicial: float = DEFAULT_BANKROLL_INICIAL,
) -> dict:
    """Backtest del modelo 1X2 sobre ``test_df`` (debe traer
    ``match_id``/``result_1x2``/las columnas de ``predictor_columns()``
    — ej. el propio ``test`` de ``split_temporal``). Evalúa las 3
    apuestas posibles (H/D/A) de forma independiente por partido —
    simplificación conocida: en la práctica esto puede recomendar más
    de una apuesta por partido si el modelo ve valor en más de un
    resultado, lo que no es lo mismo que una optimización conjunta de
    las 3 (mutuamente excluyentes) a la vez.
    """
    if modelo_path is None:
        modelo_path = _latest_model_dir(XGB_1X2_MODELS_DIR) / "model.pkl"
    paquete = joblib.load(modelo_path)
    modelo, le = paquete["modelo"], paquete["label_encoder"]

    X_test = _features(test_df)
    proba = modelo.predict_proba(X_test)
    clases = list(le.classes_)

    df = test_df[["match_id", "result_1x2"]].copy()
    for resultado in ("A", "D", "H"):
        df[f"p_{resultado}"] = proba[:, clases.index(resultado)]
    df = df.merge(_odds_1x2_reales(conn), on="match_id", how="inner")

    candidatos = []
    for _, fila in df.iterrows():
        for resultado, col_odds in (("A", "odds_a"), ("D", "odds_d"), ("H", "odds_h")):
            candidatos.append({
                "match_id": fila["match_id"], "label": resultado,
                "p": fila[f"p_{resultado}"], "odds": fila[col_odds],
                "gano": fila["result_1x2"] == resultado,
            })

    apuestas, bankroll_final = _simular_apuestas(
        candidatos, ev_threshold, kelly_multiplier, max_fraction, bankroll_inicial
    )
    return _resumen(apuestas, bankroll_inicial, bankroll_final, len(df))


def backtest_over_2_5(
    conn: sqlite3.Connection,
    test_df: pd.DataFrame,
    modelo_path,
    kelly_multiplier: float = DEFAULT_KELLY_MULTIPLIER,
    max_fraction: float = DEFAULT_MAX_FRACTION,
    ev_threshold: float = DEFAULT_EV_THRESHOLD,
    bankroll_inicial: float = DEFAULT_BANKROLL_INICIAL,
) -> dict:
    """Backtest del modelo over/under 2.5 sobre ``test_df``. Evalúa
    "over" y "under" como apuestas independientes (mismo criterio que
    1X2 con sus 3 resultados)."""
    modelo = joblib.load(modelo_path)  # guardado directo, sin dict (ver save_binary_model)

    X_test = _features(test_df)
    p_over = modelo.predict_proba(X_test)[:, 1]

    df = test_df[["match_id", "over_2_5"]].copy()
    df["p_over"] = p_over
    df = df.merge(_odds_over_under_25_reales(conn), on="match_id", how="inner")

    candidatos = []
    for _, fila in df.iterrows():
        ocurrio_over = bool(fila["over_2_5"])
        for lado, p, col_odds in (
            ("over", fila["p_over"], "odds_over"),
            ("under", 1 - fila["p_over"], "odds_under"),
        ):
            candidatos.append({
                "match_id": fila["match_id"], "label": lado,
                "p": p, "odds": fila[col_odds],
                "gano": (lado == "over") == ocurrio_over,
            })

    apuestas, bankroll_final = _simular_apuestas(
        candidatos, ev_threshold, kelly_multiplier, max_fraction, bankroll_inicial
    )
    return _resumen(apuestas, bankroll_inicial, bankroll_final, len(df))
