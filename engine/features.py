"""
Time-Series Feature Engineering Pipeline for Search Rank & Discoverability.
Constructs sliding-window behavioral features (volume, velocity, momentum, rank drift, volatility)
with strict temporal leakage prevention.
"""

from __future__ import annotations
from datetime import datetime, timedelta
import numpy as np
import pandas as pd

from rankpulse.core.config import (
    LOOKBACK_DAYS,
    PREV_LOOKBACK_DAYS,
    FORWARD_DAYS,
    MIN_IMPRESSIONS_FLOOR,
    DECLINE_THRESHOLD,
)

# Canonical feature list used by models
FEATURE_COLUMNS = [
    "imp_p1",
    "clk_p1",
    "ctr_p1",
    "avg_pos_p1",
    "pos_volatility_p1",
    "days_seen_p1",
    "momentum_ratio",
    "pos_delta",
    "ctr_delta",
    "pos_drift_p1",
]


def extract_features_at_cutoff(
    df: pd.DataFrame,
    cutoff_date: str,
    include_label: bool = True,
    lookback_days: int = LOOKBACK_DAYS,
    prev_lookback_days: int = PREV_LOOKBACK_DAYS,
    forward_days: int = FORWARD_DAYS,
    min_volume: int = MIN_IMPRESSIONS_FLOOR,
) -> pd.DataFrame:
    """
    Extract features as of a specific decision moment (cutoff_date).

    Window Definitions:
    - P0 (pre-lookback):  [cutoff - lookback - prev_lookback, cutoff - lookback)
    - P1 (lookback):      [cutoff - lookback, cutoff]
    - P2 (future label):  (cutoff, cutoff + forward_days]  (only if include_label=True)

    Strict Leakage Prevention:
    - ONLY dates <= cutoff are utilized in feature columns.
    - Future dates (> cutoff) are strictly isolated to compute the label 'is_declining_proxy'.
    """
    df = df.copy()
    df["report_date"] = pd.to_datetime(df["report_date"])
    cutoff_dt = pd.to_datetime(cutoff_date)

    p1_start = cutoff_dt - timedelta(days=lookback_days)
    p0_start = p1_start - timedelta(days=prev_lookback_days)
    p2_end = cutoff_dt + timedelta(days=forward_days)

    # Slice historical window
    df_history = df[(df["report_date"] > p0_start) & (df["report_date"] <= cutoff_dt)]
    if df_history.empty:
        return pd.DataFrame()

    # Slice into P0 and P1
    df_p0 = df_history[(df_history["report_date"] > p0_start) & (df_history["report_date"] <= p1_start)]
    df_p1 = df_history[(df_history["report_date"] > p1_start) & (df_history["report_date"] <= cutoff_dt)]

    if df_p1.empty:
        return pd.DataFrame()

    # Aggregate P1 features
    p1_agg = df_p1.groupby("page_url").agg(
        imp_p1=("impressions", "sum"),
        clk_p1=("clicks", "sum"),
        avg_pos_p1=("avg_position", "mean"),
        pos_volatility_p1=("avg_position", "std"),
        days_seen_p1=("report_date", "nunique"),
    ).reset_index()

    # Filter out low-volume pages in P1 (noise protection)
    p1_agg = p1_agg[p1_agg["imp_p1"] >= min_volume].copy()
    if p1_agg.empty:
        return pd.DataFrame()

    p1_agg["pos_volatility_p1"] = p1_agg["pos_volatility_p1"].fillna(0.0)
    p1_agg["ctr_p1"] = p1_agg["clk_p1"] / p1_agg["imp_p1"].replace(0, 1)

    # Calculate internal P1 rank drift (second half of P1 vs first half of P1)
    p1_mid = p1_start + timedelta(days=lookback_days // 2)
    df_p1_early = df_p1[df_p1["report_date"] <= p1_mid].groupby("page_url")["avg_position"].mean()
    df_p1_late = df_p1[df_p1["report_date"] > p1_mid].groupby("page_url")["avg_position"].mean()
    pos_drift_series = (df_p1_late - df_p1_early).fillna(0.0)
    p1_agg["pos_drift_p1"] = p1_agg["page_url"].map(pos_drift_series).fillna(0.0)

    # Aggregate P0 features (for momentum comparison)
    if not df_p0.empty:
        p0_agg = df_p0.groupby("page_url").agg(
            imp_p0=("impressions", "sum"),
            clk_p0=("clicks", "sum"),
            avg_pos_p0=("avg_position", "mean"),
        ).reset_index()
        p0_agg["ctr_p0"] = p0_agg["clk_p0"] / p0_agg["imp_p0"].replace(0, 1)
    else:
        p0_agg = pd.DataFrame(columns=["page_url", "imp_p0", "clk_p0", "avg_pos_p0", "ctr_p0"])

    # Merge P1 and P0
    features_df = p1_agg.merge(p0_agg, on="page_url", how="left")
    features_df["imp_p0"] = features_df["imp_p0"].fillna(0)
    features_df["clk_p0"] = features_df["clk_p0"].fillna(0)
    features_df["avg_pos_p0"] = features_df["avg_pos_p0"].fillna(features_df["avg_pos_p1"])
    features_df["ctr_p0"] = features_df["ctr_p0"].fillna(features_df["ctr_p1"])

    # Compute comparative momentum metrics
    # momentum_ratio: > 1.0 means growing, < 1.0 means slowing down
    features_df["momentum_ratio"] = features_df["imp_p1"] / np.maximum(features_df["imp_p0"], 10.0)
    # pos_delta: positive means position increased (i.e. slipped from rank 3 to rank 8)
    features_df["pos_delta"] = features_df["avg_pos_p1"] - features_df["avg_pos_p0"]
    # ctr_delta: negative means CTR dropped
    features_df["ctr_delta"] = features_df["ctr_p1"] - features_df["ctr_p0"]

    # Compute label if requested and data in P2 is available
    if include_label:
        df_p2 = df[(df["report_date"] > cutoff_dt) & (df["report_date"] <= p2_end)]
        if not df_p2.empty:
            p2_agg = df_p2.groupby("page_url").agg(imp_p2=("impressions", "sum")).reset_index()
            features_df = features_df.merge(p2_agg, on="page_url", how="left")
            features_df["imp_p2"] = features_df["imp_p2"].fillna(0)
            
            # Label: 1 if future impressions lose > 20% compared to P1
            threshold_ratio = 1.0 - DECLINE_THRESHOLD
            features_df["is_declining_proxy"] = (
                features_df["imp_p2"] < (threshold_ratio * features_df["imp_p1"])
            ).astype(int)
        else:
            features_df["is_declining_proxy"] = np.nan

    features_df["cutoff_date"] = cutoff_date
    return features_df
