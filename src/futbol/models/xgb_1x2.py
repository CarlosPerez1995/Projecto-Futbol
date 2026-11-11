"""Modelo de clasificación 1X2 con XGBoost (tarea 4.3, Fase 4).

Predice quién gana, empata o pierde (``H``/``D``/``A``) usando las
features de forma por equipo de la Fase 3 (``futbol.features.dataset.
predictor_columns()``) como entrada — nunca ninguna columna derivada
del propio marcador (eso es ``TARGET_COLUMNS``, la respuesta, no una
entrada).

Flujo, en 3 splits (``futbol.models.split.split_temporal``), cada uno
para una cosa distinta — no se reusa ninguno para dos fines:

1. ``train``: ajusta XGBoost con una búsqueda de hiperparámetros chica
   vía ``GridSearchCV`` + ``TimeSeriesSplit`` (nunca k-fold al azar —
   mezclar folds al azar en una serie de tiempo es otra forma de fuga
   de datos, un fold "posterior" no debe poder influir en uno
   "anterior" durante la validación cruzada).
2. ``val``: calibra las probabilidades del modelo ya ajustado con
   regresión isotónica (``CalibratedClassifierCV`` + ``FrozenEstimator``
   — API vigente en esta versión de scikit-learn, verificada contra el
   código instalado: el parámetro viejo ``cv="prefit"`` ya no existe).
   Nunca se calibra con ``train``: calibrar con los mismos datos que ya
   vio el modelo al ajustarse daría una calibración artificialmente
   optimista.
3. ``test``: solo para medir LogLoss/Brier al final, nunca para elegir
   nada (ni hiperparámetros ni la calibración).

Dos simplificaciones encontradas y resueltas al escribir esto, no
anticipadas por el plan original:

- **XGBoost (esta versión, 3.4.1) no acepta etiquetas de texto** —
  hay que codificar ``result_1x2`` (``H``/``D``/``A``) a enteros con
  ``LabelEncoder`` antes de ajustar, y decodificar de vuelta para
  interpretar ``classes_``/``feature_importances_``. Verificado
  intentando ajustar con etiquetas de texto directo: falla con
  ``ValueError``.
- ``current_streak_result_home``/``current_streak_result_away`` (de
  ``predictor_columns()``) son texto (``W``/``D``/``L``), no número —
  se codifican a escala ordinal simple (``W``=1, ``D``=0, ``L``=−1,
  ``NaN`` se mantiene ``NaN``) antes de entrenar. El resto de las
  columnas de ``predictor_columns()`` ya son numéricas y XGBoost
  acepta sus ``NaN`` nativamente (verificado), sin necesidad de
  imputar: un equipo en su primer partido de la temporada no tiene
  historia, y eso es información real, no un hueco que haya que
  rellenar con un valor inventado.

Divergencia ya anticipada por el plan arquitectónico: el modelo se
guarda versionado (``models/xgb_1x2/<version>/model.pkl`` +
``metrics.json``), no un ``.pkl`` suelto sin metadata — necesario para
cuando la Fase 6 reentrene periódicamente y haga falta comparar
versiones.
"""
from __future__ import annotations

import json
import logging
from datetime import datetime
from pathlib import Path

import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.frozen import FrozenEstimator
from sklearn.metrics import log_loss
from sklearn.model_selection import GridSearchCV, TimeSeriesSplit
from sklearn.preprocessing import LabelEncoder
from xgboost import XGBClassifier

from futbol.features.dataset import predictor_columns

logger = logging.getLogger(__name__)

DEFAULT_MODELS_DIR = Path("models/xgb_1x2")

_RESULT_ORDER = ["A", "D", "H"]  # orden alfabético: el mismo que usa LabelEncoder
_STREAK_RESULT_COLS = ["current_streak_result_home", "current_streak_result_away"]
_STREAK_RESULT_MAP = {"W": 1, "D": 0, "L": -1}

_PARAM_GRID = {
    "max_depth": [3, 4],
    "n_estimators": [100, 200],
    "learning_rate": [0.05, 0.1],
}


def _features(df: pd.DataFrame) -> pd.DataFrame:
    """Matriz de predictoras lista para XGBoost: las columnas de
    ``predictor_columns()``, con las de racha (texto) codificadas a
    escala ordinal (ver docstring del módulo). No toca ``df`` original.
    """
    X = df[predictor_columns()].copy()
    for col in _STREAK_RESULT_COLS:
        X[col] = X[col].map(_STREAK_RESULT_MAP)
    return X


def fit_xgb_1x2(train_df: pd.DataFrame) -> tuple[XGBClassifier, LabelEncoder]:
    """Ajusta un ``XGBClassifier`` para 1X2 sobre ``train_df`` con una
    búsqueda de hiperparámetros chica (``GridSearchCV`` +
    ``TimeSeriesSplit``, nunca al azar). Devuelve el modelo y el
    ``LabelEncoder`` usado (necesario para decodificar ``classes_``
    más adelante).
    """
    X = _features(train_df)
    le = LabelEncoder()
    le.fit(_RESULT_ORDER)
    y = le.transform(train_df["result_1x2"])

    base = XGBClassifier(objective="multi:softprob", eval_metric="mlogloss", random_state=42)
    tscv = TimeSeriesSplit(n_splits=3)
    busqueda = GridSearchCV(base, _PARAM_GRID, cv=tscv, scoring="neg_log_loss")
    busqueda.fit(X, y)
    logger.info("fit_xgb_1x2: mejores hiperparámetros %s", busqueda.best_params_)
    return busqueda.best_estimator_, le


def calibrate_xgb_1x2(
    modelo_base: XGBClassifier,
    val_df: pd.DataFrame,
    label_encoder: LabelEncoder,
) -> CalibratedClassifierCV:
    """Calibra ``modelo_base`` (ya ajustado con ``train``) con
    regresión isotónica usando ``val_df`` — nunca ``train_df``."""
    X_val = _features(val_df)
    y_val = label_encoder.transform(val_df["result_1x2"])
    calibrado = CalibratedClassifierCV(FrozenEstimator(modelo_base), method="isotonic")
    calibrado.fit(X_val, y_val)
    return calibrado


def evaluate_xgb_1x2(
    modelo_calibrado: CalibratedClassifierCV,
    test_df: pd.DataFrame,
    label_encoder: LabelEncoder,
) -> dict:
    """LogLoss y Brier (multiclase) sobre ``test_df`` — el único split
    que no participó ni en el ajuste ni en la calibración."""
    X_test = _features(test_df)
    y_test = label_encoder.transform(test_df["result_1x2"])
    proba = modelo_calibrado.predict_proba(X_test)

    logloss = log_loss(y_test, proba, labels=modelo_calibrado.classes_)
    y_onehot = np.eye(len(label_encoder.classes_))[y_test]
    brier = float(np.mean(np.sum((proba - y_onehot) ** 2, axis=1)))

    return {"log_loss": float(logloss), "brier": brier, "n_test": int(len(test_df))}


def _feature_importances(modelo_base: XGBClassifier) -> dict:
    return dict(zip(predictor_columns(), (float(v) for v in modelo_base.feature_importances_)))


def save_model(
    modelo_calibrado: CalibratedClassifierCV,
    label_encoder: LabelEncoder,
    modelo_base: XGBClassifier,
    metrics: dict,
    dataset_hash: str,
    models_dir: Path = DEFAULT_MODELS_DIR,
) -> Path:
    """Guarda el modelo calibrado + metadata en
    ``models_dir/<version>/`` (``model.pkl`` + ``metrics.json``), nunca
    un ``.pkl`` suelto — ``<version>`` es la fecha/hora de entrenamiento
    (``YYYYMMDD_HHMMSS``), para poder comparar versiones cuando la
    Fase 6 reentrene periódicamente.
    """
    version = datetime.now().strftime("%Y%m%d_%H%M%S")
    carpeta = models_dir / version
    carpeta.mkdir(parents=True, exist_ok=True)

    joblib.dump({"modelo": modelo_calibrado, "label_encoder": label_encoder}, carpeta / "model.pkl")

    metadata = {
        "version": version,
        "fecha_entrenamiento": datetime.now().strftime("%Y-%m-%d %H:%M:%S"),
        "model_dataset_hash": dataset_hash,
        "log_loss": metrics["log_loss"],
        "brier": metrics["brier"],
        "n_test": metrics["n_test"],
        "feature_importances": _feature_importances(modelo_base),
    }
    (carpeta / "metrics.json").write_text(json.dumps(metadata, indent=2, ensure_ascii=False), encoding="utf-8")

    logger.info("save_model: guardado en %s", carpeta)
    return carpeta
