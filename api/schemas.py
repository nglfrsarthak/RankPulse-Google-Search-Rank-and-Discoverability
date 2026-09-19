"""
Pydantic Schemas for RankPulse API endpoints.
"""

from __future__ import annotations
from typing import Any
from pydantic import BaseModel, Field


class TriageItem(BaseModel):
    page_url: str
    model_proba: float
    risk_level: str
    baseline_score: float
    reason_code: str
    reason_title: str
    reason_description: str
    reason_severity: str
    primary_action: str
    imp_p1: int
    clk_p1: int
    avg_pos_p1: float
    ctr_p1: float
    momentum_ratio: float
    pos_delta: float
    status: str = "PENDING"
    notes: str = ""
    assigned_to: str = ""


class TriageQueueResponse(BaseModel):
    total_count: int
    page: int
    page_size: int
    items: list[TriageItem]


class PortfolioOverviewResponse(BaseModel):
    total_monitored_pages: int
    critical_risk_count: int
    high_risk_count: int
    moderate_risk_count: int
    low_risk_count: int
    total_impressions_p1: int
    projected_at_risk_impressions: int
    average_risk_probability: float
    data_date_min: str | None
    data_date_max: str | None
    has_trained_model: bool
    model_auc: float | None


class DailyDataPoint(BaseModel):
    date: str
    impressions: int
    clicks: int
    ctr: float
    avg_position: float


class PageDetailResponse(BaseModel):
    page_url: str
    metrics: TriageItem
    checklist: list[str]
    time_estimate: str
    what_would_make_it_wrong: str
    history: list[DailyDataPoint]


class UpdateTriageRequest(BaseModel):
    status: str = Field(..., description="PENDING, IN_REVIEW, REFRESHED, or IGNORED")
    notes: str = ""
    assigned_to: str = ""


class StandardResponse(BaseModel):
    success: bool
    message: str
    data: dict[str, Any] | None = None


class IngestGlobalRequest(BaseModel):
    category: str = Field("all", description="Category: 'all', 'giants', 'tech', 'finance', 'trending', 'custom'")
    custom_topics: list[str] = Field(default_factory=list, description="Optional custom topics/queries to ingest")
    days: int = Field(60, description="Number of historical days to fetch (default 60)")
    max_topics: int = Field(60, description="Maximum topics to ingest")

