"""
Diagnostic Reason Codes Engine for Search Discoverability.
Maps behavioral feature signals into human-readable, explainable diagnostic reason codes
for content editors and SEO growth teams.
"""

from __future__ import annotations
from typing import TypedDict
import pandas as pd


class ReasonCodeInfo(TypedDict):
    code: str
    title: str
    description: str
    severity: str  # 'critical', 'warning', 'info'


REASON_DEFINITIONS: dict[str, ReasonCodeInfo] = {
    "POSITION_EROSION_DANGER": {
        "code": "POSITION_EROSION_DANGER",
        "title": "Rank Slippage into Second Tier",
        "description": "Average position has steadily drifted downward (>2.5 spots) into positions 10-25, causing severe click cliffing.",
        "severity": "critical",
    },
    "CTR_DECAY_SERP_CROWDING": {
        "code": "CTR_DECAY_SERP_CROWDING",
        "title": "CTR Collapse on Stable Rank",
        "description": "Page maintains Page 1 ranking, but click-through rate dropped sharply (>25%), signaling SERP feature cannibalization or stale snippets.",
        "severity": "warning",
    },
    "MOMENTUM_DECELERATION": {
        "code": "MOMENTUM_DECELERATION",
        "title": "Impression Velocity Deceleration",
        "description": "Impression volume dropped >25% half-over-half, indicating fading search demand or progressive algorithmic demotion.",
        "severity": "warning",
    },
    "HIGH_VOLATILITY_TURBULENCE": {
        "code": "HIGH_VOLATILITY_TURBULENCE",
        "title": "Extreme Rank Volatility",
        "description": "Daily position is bouncing erratically (std dev > 4.5), indicating Google algorithm re-indexing or search intent conflict.",
        "severity": "critical",
    },
    "STALE_HIGH_IMPACT_PILLAR": {
        "code": "STALE_HIGH_IMPACT_PILLAR",
        "title": "Key Pillar Asset Decay",
        "description": "High-volume flagship page (1,000+ impressions) exhibiting early decay indicators. A drop here will significantly impact overall site organic traffic.",
        "severity": "critical",
    },
    "HEALTHY_MOMENTUM": {
        "code": "HEALTHY_MOMENTUM",
        "title": "Healthy Organic Momentum",
        "description": "Traffic and rankings are holding firm or climbing. No urgent editorial action needed.",
        "severity": "info",
    },
}


def diagnose_page_reason(row: pd.Series | dict) -> ReasonCodeInfo:
    """Evaluate feature row and assign the most urgent diagnostic reason code."""
    model_proba = float(row.get("model_proba", 0.0))
    imp_p1 = float(row.get("imp_p1", 0.0))
    avg_pos = float(row.get("avg_pos_p1", 20.0))
    pos_vol = float(row.get("pos_volatility_p1", 0.0))
    pos_drift = float(row.get("pos_drift_p1", 0.0))
    pos_delta = float(row.get("pos_delta", 0.0))
    ctr_delta = float(row.get("ctr_delta", 0.0))
    momentum_ratio = float(row.get("momentum_ratio", 1.0))

    # Priority 1: Stale High-Impact Pillar
    if imp_p1 >= 1000 and model_proba >= 0.50:
        return REASON_DEFINITIONS["STALE_HIGH_IMPACT_PILLAR"]

    # Priority 2: Position Erosion
    if (avg_pos > 9.0 and avg_pos <= 25.0) and (pos_drift >= 2.0 or pos_delta >= 2.5 or model_proba >= 0.55):
        return REASON_DEFINITIONS["POSITION_EROSION_DANGER"]

    # Priority 3: Severe Volatility
    if pos_vol >= 4.5 and model_proba >= 0.45:
        return REASON_DEFINITIONS["HIGH_VOLATILITY_TURBULENCE"]

    # Priority 4: CTR Decay
    if (ctr_delta <= -0.015 or (row.get("ctr_p1", 0.05) < 0.02 and avg_pos <= 6.0)) and model_proba >= 0.40:
        return REASON_DEFINITIONS["CTR_DECAY_SERP_CROWDING"]

    # Priority 5: Momentum Deceleration
    if momentum_ratio <= 0.75 and model_proba >= 0.45:
        return REASON_DEFINITIONS["MOMENTUM_DECELERATION"]

    if model_proba >= 0.40:
        return REASON_DEFINITIONS["POSITION_EROSION_DANGER"]

    return REASON_DEFINITIONS["HEALTHY_MOMENTUM"]


def assign_reason_codes_to_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """Enrich scored dataframe with reason codes, titles, and explanations."""
    res = df.copy()
    reason_codes = []
    reason_titles = []
    reason_descriptions = []
    reason_severities = []

    for _, row in res.iterrows():
        diag = diagnose_page_reason(row)
        reason_codes.append(diag["code"])
        reason_titles.append(diag["title"])
        reason_descriptions.append(diag["description"])
        reason_severities.append(diag["severity"])

    res["reason_code"] = reason_codes
    res["reason_title"] = reason_titles
    res["reason_description"] = reason_descriptions
    res["reason_severity"] = reason_severities
    return res
