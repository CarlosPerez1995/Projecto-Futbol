"""Modelos binarios de over/under y BTTS (tarea 4.4, Fase 4).

Mismo patrón que la clasificación 1X2 de la tarea 4.3
(``futbol.models.xgb_1x2``: XGBoost ajustado con ``GridSearchCV`` +
``TimeSeriesSplit`` en ``train``, calibrado con regresión isotónica en
``val``, evaluado en ``test``, guardado versionado) aplicado a 3
objetivos binarios en vez de al 1X2 de 3 clases: ``over_1_5``,
``over_2_5``, ``btts``. Un modelo separado por objetivo, no uno
multi-etiqueta — en la práctica cada mercado de apuestas se evalúa y
se ofrece por separado, no tiene sentido mezclarlos en un solo modelo.

Reusa ``_features()`` de ``xgb_1x2.py`` (la codificación de
``current_streak_result_*`` a escala ordinal es la misma, no hay
ninguna razón para duplicarla) — las columnas objetivo booleanas
(``over_1_5``/``over_2_5``/``btts``) se convierten a `0`/`1` antes de
entrenar, XGBoost las acepta así nativamente (verificado).
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import joblib
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import log_loss, roc_auc_score
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from xgboost import XGBClassifier

from futbol.features.dataset import predictor_columns
from futbol.models.xgb_1x2 import _PARAM_GRID, _features

logger = logging.getLogger(__name__)

DEFAULT_MODELS_DIR = Path("models")
BINARY_TARGETS = ["over_1_5", "over_2_5", "btts"]


def fit_binary_model(train_df: pd.DataFrame, target_col: str) -> XGBClassifier:
    """Ajusta un ``XGBClassifier`` binario para ``target_col`` sobre
    ``train_df``, con la misma búsqueda de hiperparámetros chica que
    1X2 (``TimeSeriesSplit``, nunca k-fold al azar)."""
    X = _features(train_df)
    y = train_df[target_col].astype(int).to_numpy()

    base = XGBClassifier(objective="binary:logistic", eval_metric="logloss", random_state=42)
    tscv = TimeSeriesSplit(n_splits=3)
    busqueda = GridSearchCV(base, _PARAM_GRID, cv=tscv, scoring="neg_log_loss")
    busqueda.fit(X, y)
    logger.info("fit_binary_model[%s]: mejores hiperparámetros %s", target_col, busqueda.best_params_)
    return busqueda.best_estimator_


def calibrate_binary_model(
    modelo_base: XGBClassifier,
    val_df: pd.DataFrame,
    target_col: str,
) -> CalibratedClassifierCV:
    """Calibra con ``val_df`` (nunca ``train_df``) — mismo motivo que
    en 1X2: calibrar con los datos que ya vio el modelo al ajustarse
    da una calibración artificialmente optimista.

    ``method="sigmoid"``, no isotónica: mismo hallazgo y mismo motivo
    que en ``xgb_1x2.calibrate_xgb_1x2`` (ver su docstring) — con
    ``val`` de ~528 filas, la isotónica llegó a asignar probabilidad
    0.0 a la clase verdadera en varios partidos de test (confirmado en
    ``over_1_5`` y ``btts``), lo que arruina el LogLoss sin que el
    modelo haya cambiado."""
    X_val = _features(val_df)
    y_val = val_df[target_col].astype(int).to_numpy()
    calibrado = CalibratedClassifierCV(FrozenEstimator(modelo_base), method="sigmoid")
    calibrado.fit(X_val, y_val)
    return calibrado


def evaluate_binary_model(
    modelo_calibrado: CalibratedClassifierCV,
    test_df: pd.DataFrame,
    target_col: str,
) -> dict:
    """ROC-AUC y LogLoss sobre ``test_df`` — el único split que no
    participó en ajuste ni calibración."""
    X_test = _features(test_df)
    y_test = test_df[target_col].astype(int).to_numpy()
    proba = modelo_calibrado.predict_proba(X_test)[:, 1]

    return {
        "target": target_col,
        "auc": float(roc_auc_score(y_test, proba)),
        "log_loss": float(log_loss(y_test, proba)),
        "n_test": int(len(test_df)),
    }


def _feature_importances(modelo_base: XGBClassifier) -> dict:
    return dict(zip(predictor_columns(), (float(v) for v in modelo_base.feature_importances_)))


def save_binary_model(
    modelo_calibrado: CalibratedClassifierCV,
    modelo_base: XGBClassifier,
    target_col: str,
    metrics: dict,
    dataset_hash: str,
    models_dir: Path = DEFAULT_MODELS_DIR,
) -> Path:
    """Guarda en ``models_dir/xgb_<target_col>/<version>/`` —
    ``model.pkl`` + ``metrics.json``, mismo esquema de versionado que
    1X2 (``models/`` no se versiona en git, ver ``.gitignore``)."""
    version = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta = models_dir / f"xgb_{target_col}" / version
    carpeta.mkdir(parents=True, exist_ok=True)

    joblib.dump(modelo_calibrado, carpeta / "model.pkl")

    metadata = {
        "version": version,
        "target": target_col,
        "fecha_entrenamiento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model_dataset_hash": dataset_hash,
        "auc": metrics["auc"],
        "log_loss": metrics["log_loss"],
        "n_test": metrics["n_test"],
        "feature_importances": _feature_importances(modelo_base),
    }
    (carpeta / "metrics.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("save_binary_model[%s]: guardado en %s", target_col, carpeta)
    return carpeta


def fit_calibrate_evaluate_all(
    train_df: pd.DataFrame,
    val_df: pd.DataFrame,
    test_df: pd.DataFrame,
) -> pd.DataFrame:
    """Corre el flujo completo (ajuste + calibración + evaluación) para
    los 3 objetivos de ``BINARY_TARGETS``. Devuelve un resumen, una
    fila por objetivo. No guarda nada en disco (ver ``save_binary_model``
    por separado para eso).
    """
    filas = []
    for target in BINARY_TARGETS:
        modelo_base = fit_binary_model(train_df, target)
        modelo_calibrado = calibrate_binary_model(modelo_base, val_df, target)
        filas.append(evaluate_binary_model(modelo_calibrado, test_df, target))
    return pd.DataFrame(filas)
