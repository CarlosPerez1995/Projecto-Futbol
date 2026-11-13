"""Tests de ``src/futbol/models/xgb_binary.py`` con un dataset sintético.

Mismo patrón que ``test_models_xgb_1x2.py`` — dataset sintético con una
señal real (no ruido puro) para que el modelo pueda aprender algo.
"""
from __future__ import annotations

from pathlib import Path

import numpy as np
import pandas as pd
import pytest

from futbol.features.dataset import predictor_columns
from futbol.models.xgb_binary import (
    BINARY_TARGETS,
    calibrate_binary_model,
    evaluate_binary_model,
    fit_binary_model,
    fit_calibrate_evaluate_all,
    save_binary_model,
)


def _dataset_sintetico(n: int, seed: int) -> pd.DataFrame:
    rng = np.random.default_rng(seed)
    datos = {col: rng.normal(1.5, 0.6, n) for col in predictor_columns()}
    df = pd.DataFrame(datos)
    for col in ("current_streak_result_home", "current_streak_result_away"):
        df[col] = rng.choice(["W", "D", "L", None], size=n, p=[0.35, 0.3, 0.3, 0.05])

    total_goles_estimado = (
        df["goals_scored_avg_last5_home"] + df["goals_scored_avg_last5_away"]
    )
    ruido = rng.normal(0, 0.8, n)
    df["over_1_5"] = (total_goles_estimado + ruido) > 1.5
    df["over_2_5"] = (total_goles_estimado + ruido) > 2.5
    df["btts"] = (
        (df["goals_scored_avg_last5_home"] + rng.normal(0, 0.8, n) > 0.8)
        & (df["goals_scored_avg_last5_away"] + rng.normal(0, 0.8, n) > 0.8)
    )
    return df


@pytest.fixture
def train_val_test():
    return (
        _dataset_sintetico(150, seed=1),
        _dataset_sintetico(40, seed=2),
        _dataset_sintetico(40, seed=3),
    )


def test_flujo_completo_por_objetivo(train_val_test):
    train, val, test = train_val_test

    for target in BINARY_TARGETS:
        modelo_base = fit_binary_model(train, target)
        modelo_calibrado = calibrate_binary_model(modelo_base, val, target)
        metrics = evaluate_binary_model(modelo_calibrado, test, target)

        assert metrics["target"] == target
        assert metrics["n_test"] == 40
        assert 0.0 <= metrics["auc"] <= 1.0
        assert metrics["log_loss"] > 0


def test_fit_calibrate_evaluate_all_devuelve_una_fila_por_objetivo(train_val_test):
    train, val, test = train_val_test

    resumen = fit_calibrate_evaluate_all(train, val, test)

    assert len(resumen) == len(BINARY_TARGETS)
    assert set(resumen["target"]) == set(BINARY_TARGETS)


def test_save_binary_model_usa_una_carpeta_por_objetivo(train_val_test, tmp_path: Path):
    train, val, test = train_val_test
    target = "over_2_5"

    modelo_base = fit_binary_model(train, target)
    modelo_calibrado = calibrate_binary_model(modelo_base, val, target)
    metrics = evaluate_binary_model(modelo_calibrado, test, target)

    carpeta = save_binary_model(modelo_calibrado, modelo_base, target, metrics, "abc123", models_dir=tmp_path)

    assert carpeta.parent.name == "xgb_over_2_5"
    assert (carpeta / "model.pkl").exists()
    assert (carpeta / "metrics.json").exists()

    import json
    metadata = json.loads((carpeta / "metrics.json").read_text())
    assert metadata["target"] == "over_2_5"
    assert metadata["model_dataset_hash"] == "abc123"


def test_save_binary_model_el_modelo_guardado_se_puede_recargar(train_val_test, tmp_path: Path):
    train, val, test = train_val_test
    target = "btts"

    modelo_base = fit_binary_model(train, target)
    modelo_calibrado = calibrate_binary_model(modelo_base, val, target)
    metrics = evaluate_binary_model(modelo_calibrado, test, target)
    carpeta = save_binary_model(modelo_calibrado, modelo_base, target, metrics, "abc123", models_dir=tmp_path)

    import joblib
    from futbol.models.xgb_1x2 import _features
    cargado = joblib.load(carpeta / "model.pkl")
    proba = cargado.predict_proba(_features(test))[:, 1]

    assert proba.shape == (len(test),)
    assert ((proba >= 0) & (proba <= 1)).all()
