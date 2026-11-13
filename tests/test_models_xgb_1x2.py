"""Tests de ``src/futbol/models/xgb_1x2.py`` con un dataset sintético.

No depende de la BD ni de la Fase 3 — construye directamente un
``DataFrame`` con las columnas que ``predictor_columns()`` espera, para
aislar el código de modelado de todo lo anterior (que ya tiene sus
propios tests).
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from futbol.features.dataset import predictor_columns
from futbol.models.xgb_1x2 import (
    _features,
    calibrate_xgb_1x2,
    evaluate_xgb_1x2,
    fit_xgb_1x2,
    save_model,
)


def _dataset_sintetico(n: int, seed: int = 0) -> pd.DataFrame:
    """``n`` filas con una señal real pero simple (no ruido puro): a
    mayor ``goals_scored_avg_last5_home`` relativo al visitante, más
    probable que gane el local — suficiente para que el modelo pueda
    aprender algo, sin necesitar que sea perfecto.
    """
    rng = np.random.default_rng(seed)
    datos = {col: rng.normal(1.5, 0.6, n) for col in predictor_columns()}
    df = pd.DataFrame(datos)

    # racha: texto, con algunos NaN (como en los datos reales, primer partido
    # de la temporada) — justo lo que _features() tiene que saber manejar.
    for col in ("current_streak_result_home", "current_streak_result_away"):
        df[col] = rng.choice(["W", "D", "L", None], size=n, p=[0.35, 0.3, 0.3, 0.05])

    diferencia = df["goals_scored_avg_last5_home"] - df["goals_scored_avg_last5_away"]
    ruido = rng.normal(0, 1.0, n)
    señal = diferencia + ruido
    df["result_1x2"] = pd.cut(
        señal, bins=[-np.inf, -0.3, 0.3, np.inf], labels=["A", "D", "H"]
    ).astype(str)

    df["match_date"] = pd.date_range("2024-01-01", periods=n, freq="D").astype(str)
    return df


@pytest.fixture
def train_val_test():
    train = _dataset_sintetico(150, seed=1)
    val = _dataset_sintetico(40, seed=2)
    test = _dataset_sintetico(40, seed=3)
    return train, val, test


def test_features_codifica_racha_a_escala_ordinal():
    df = pd.DataFrame({
        **{col: [1.0] for col in predictor_columns() if col not in (
            "current_streak_result_home", "current_streak_result_away"
        )},
        "current_streak_result_home": ["W"],
        "current_streak_result_away": [None],
    })

    X = _features(df)

    assert X["current_streak_result_home"].iloc[0] == 1
    assert pd.isna(X["current_streak_result_away"].iloc[0])  # NaN se mantiene, no se inventa


def test_flujo_completo_fit_calibrate_evaluate(train_val_test):
    train, val, test = train_val_test

    modelo_base, le = fit_xgb_1x2(train)
    modelo_calibrado = calibrate_xgb_1x2(modelo_base, val, le)
    metricas = evaluate_xgb_1x2(modelo_calibrado, test, le)

    assert metricas["n_test"] == 40
    assert 0 < metricas["log_loss"] < 5  # rango sano para log_loss de 3 clases
    assert 0 <= metricas["brier"] <= 2  # rango válido del Brier multiclase (ver docstring del módulo)


def test_evaluate_usa_el_orden_alfabetico_de_clases(train_val_test):
    train, val, test = train_val_test
    modelo_base, le = fit_xgb_1x2(train)

    assert list(le.classes_) == ["A", "D", "H"]


def test_save_model_guarda_version_con_model_pkl_y_metrics_json(train_val_test, tmp_path: Path):
    train, val, test = train_val_test
    modelo_base, le = fit_xgb_1x2(train)
    modelo_calibrado = calibrate_xgb_1x2(modelo_base, val, le)
    metricas = evaluate_xgb_1x2(modelo_calibrado, test, le)

    carpeta = save_model(
        modelo_calibrado, le, modelo_base, metricas,
        dataset_hash="abc123", models_dir=tmp_path,
    )

    assert (carpeta / "model.pkl").exists()
    assert (carpeta / "metrics.json").exists()

    import json
    metadata = json.loads((carpeta / "metrics.json").read_text())
    assert metadata["model_dataset_hash"] == "abc123"
    assert metadata["log_loss"] == metricas["log_loss"]
    assert set(metadata["feature_importances"].keys()) == set(predictor_columns())


def test_save_model_el_modelo_guardado_se_puede_recargar_y_usar(train_val_test, tmp_path: Path):
    train, val, test = train_val_test
    modelo_base, le = fit_xgb_1x2(train)
    modelo_calibrado = calibrate_xgb_1x2(modelo_base, val, le)
    metricas = evaluate_xgb_1x2(modelo_calibrado, test, le)
    carpeta = save_model(modelo_calibrado, le, modelo_base, metricas, "abc123", models_dir=tmp_path)

    import joblib
    cargado = joblib.load(carpeta / "model.pkl")
    X_test = _features(test)
    proba = cargado["modelo"].predict_proba(X_test)

    assert proba.shape == (len(test), 3)
    assert np.allclose(proba.sum(axis=1), 1.0, atol=1e-6)
