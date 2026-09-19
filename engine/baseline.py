"""
Heuristic Rule Baseline for Google Search Triage.
Implements the transparent hand-written 'visible & slipping' decision rule
to establish an honest performance benchmark before introducing machine learning.
"""

from __future__ import annotations
import numpy as np
import pandas as pd


def compute_baseline_score(df: pd.DataFrame) -> pd.DataFrame:
    """
    Compute hand-written heuristic baseline score for search triage.

    Rule Formulation:
    - visible: imp_p1 >= 100
    - slipping: avg_pos_p1 in (10, 25] OR pos_drift_p1 >= 2.0 OR momentum_ratio < 0.8
    - baseline_score: volume-weighted slipping severity
    """
    res = df.copy()

    # Determine slipping condition
    pos_slipping = (res["avg_pos_p1"] > 10.0) & (res["avg_pos_p1"] <= 25.0)
    drift_slipping = res.get("pos_drift_p1", pd.Series(0, index=res.index)) >= 2.0
    momentum_slipping = res.get("momentum_ratio", pd.Series(1.0, index=res.index)) < 0.80

    is_slipping = pos_slipping | drift_slipping | momentum_slipping

    # Visible & Slipping score
    res["is_slipping_rule"] = is_slipping.astype(int)
    res["baseline_score"] = res["imp_p1"] * res["is_slipping_rule"]

    # Baseline reason code
    res["baseline_reason"] = np.where(
        is_slipping,
        "visible_and_slipping",
        "healthy_or_unranked"
    )

    return res


def evaluate_precision_at_k(df: pd.DataFrame, score_col: str, target_col: str = "is_declining_proxy", k_list: list[int] = [10, 20, 50, 100]) -> dict[str, float]:
    """
    Calculate Precision@K for a ranked score column.
    Only evaluates rows where target_col is non-null.
    """
    valid = df[df[target_col].notna()].sort_values(score_col, ascending=False).reset_index(drop=True)
    if valid.empty:
        return {}

    base_rate = float(valid[target_col].mean())
    results = {"base_rate": base_rate}

    for k in k_list:
        k_val = min(k, len(valid))
        if k_val == 0:
            results[f"p@{k}"] = 0.0
            results[f"lift@{k}"] = 0.0
        else:
            top_k = valid.head(k_val)
            precision = float(top_k[target_col].mean())
            lift = precision / base_rate if base_rate > 0 else 0.0
            results[f"p@{k}"] = precision
            results[f"lift@{k}"] = lift

    return results
