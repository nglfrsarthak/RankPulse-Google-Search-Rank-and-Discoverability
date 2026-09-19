"""
Machine Learning Model Pipeline for Growth & Momentum Decay Prediction.
Implements calibrated ensemble modeling (RandomForest / GradientBoosting)
with probability calibration, honest metric auditing, and artifact persistence.
"""

from __future__ import annotations
import json
from pathlib import Path
from typing import Any
import joblib
import numpy as np
import pandas as pd
from sklearn.calibration import CalibratedClassifierCV
from sklearn.ensemble import RandomForestClassifier, GradientBoostingClassifier
from sklearn.metrics import roc_auc_score, average_precision_score, brier_score_loss
from sklearn.model_selection import train_test_split

from rankpulse.core.config import MODEL_PATH, METADATA_PATH
from rankpulse.engine.baseline import evaluate_precision_at_k
from rankpulse.engine.features import FEATURE_COLUMNS


def train_momentum_model(
    train_df: pd.DataFrame,
    target_col: str = "is_declining_proxy",
    test_size: float = 0.25,
    random_state: int = 42,
    model_type: str = "rf",
) -> tuple[Any, dict[str, Any]]:
    """
    Train a calibrated classifier to predict P(momentum decline > 20%).

    Returns:
        calibrated_model: Trained model with calibrated probabilities
        metrics: Dictionary of test set metrics and feature importances
    """
    clean_df = train_df[train_df[target_col].notna()].copy()
    if len(clean_df) < 20:
        raise ValueError(f"Insufficient training samples: {len(clean_df)}. Need at least 20.")

    X = clean_df[FEATURE_COLUMNS].fillna(0.0)
    y = clean_df[target_col].astype(int)

    # Stratified split to preserve class ratio
    X_train, X_test, y_train, y_test = train_test_split(
        X, y, test_size=test_size, random_state=random_state, stratify=y
    )

    # Base estimator
    if model_type == "gb":
        base_clf = GradientBoostingClassifier(
            n_estimators=150, max_depth=4, learning_rate=0.05, random_state=random_state
        )
    else:
        base_clf = RandomForestClassifier(
            n_estimators=200, max_depth=6, min_samples_leaf=3, random_state=random_state
        )

    # Determine appropriate cv folds based on minority class count
    min_class_count = int(y_train.value_counts().min())
    cv_folds = max(2, min(3, min_class_count))

    calibrated_clf = CalibratedClassifierCV(
        estimator=base_clf, method="sigmoid", cv=cv_folds
    )
    calibrated_clf.fit(X_train, y_train)

    # Evaluate on test set
    y_proba_test = calibrated_clf.predict_proba(X_test)[:, 1]
    
    auc_score = float(roc_auc_score(y_test, y_proba_test))
    pr_auc = float(average_precision_score(y_test, y_proba_test))
    brier = float(brier_score_loss(y_test, y_proba_test))

    # Evaluate Precision@K on test split
    test_eval_df = X_test.copy()
    test_eval_df[target_col] = y_test
    test_eval_df["model_proba"] = y_proba_test
    p_at_k = evaluate_precision_at_k(test_eval_df, score_col="model_proba", target_col=target_col)

    # Extract feature importances from calibrated classifier folds
    feature_importances = {}
    try:
        sub_imps = [c.estimator.feature_importances_ for c in calibrated_clf.calibrated_classifiers_ if hasattr(c.estimator, "feature_importances_")]
        if sub_imps:
            avg_imp = np.mean(sub_imps, axis=0)
            for feat, imp in zip(FEATURE_COLUMNS, avg_imp):
                feature_importances[feat] = round(float(imp), 4)
            feature_importances = dict(sorted(feature_importances.items(), key=lambda x: x[1], reverse=True))
    except Exception:
        pass

    metrics = {
        "n_samples": len(clean_df),
        "n_train": len(X_train),
        "n_test": len(X_test),
        "base_rate": round(float(y.mean()), 4),
        "roc_auc": round(auc_score, 4),
        "pr_auc": round(pr_auc, 4),
        "brier_score": round(brier, 4),
        "precision_at_k": {k: round(v, 4) for k, v in p_at_k.items()},
        "feature_importances": feature_importances,
    }

    return calibrated_clf, metrics


def save_model_artifacts(model: Any, metrics: dict[str, Any], model_path: Path = MODEL_PATH, meta_path: Path = METADATA_PATH) -> None:
    """Serialize model and evaluation metadata."""
    model_path.parent.mkdir(parents=True, exist_ok=True)
    meta_path.parent.mkdir(parents=True, exist_ok=True)
    joblib.dump(model, model_path)
    with open(meta_path, "w", encoding="utf-8") as f:
        json.dump(metrics, f, indent=2)


def load_model_artifacts(model_path: Path = MODEL_PATH, meta_path: Path = METADATA_PATH) -> tuple[Any | None, dict[str, Any]]:
    """Load serialized model and metadata."""
    model = None
    metrics = {}
    if model_path.exists():
        model = joblib.load(model_path)
    if meta_path.exists():
        with open(meta_path, "r", encoding="utf-8") as f:
            metrics = json.load(f)
    return model, metrics


def score_features_dataframe(df: pd.DataFrame, model: Any | None = None) -> pd.DataFrame:
    """
    Score a features dataframe with both ML model probability and heuristic baseline.
    Adds 'model_proba', 'risk_level', and 'baseline_score'.
    """
    res = df.copy()

    # Calculate baseline heuristic score
    from rankpulse.engine.baseline import compute_baseline_score
    res = compute_baseline_score(res)

    # ML Model scoring
    if model is not None:
        X = res[FEATURE_COLUMNS].fillna(0.0)
        probas = model.predict_proba(X)[:, 1]
        res["model_proba"] = np.round(probas, 4)
    else:
        # Fallback to normalized baseline score if model not yet trained
        max_score = res["baseline_score"].max() or 1.0
        res["model_proba"] = np.round(res["baseline_score"] / max_score, 4)

    # Assign risk tier
    def assign_risk(p: float) -> str:
        if p >= 0.70:
            return "CRITICAL"
        elif p >= 0.50:
            return "HIGH"
        elif p >= 0.30:
            return "MODERATE"
        return "LOW"

    res["risk_level"] = res["model_proba"].apply(assign_risk)
    return res
