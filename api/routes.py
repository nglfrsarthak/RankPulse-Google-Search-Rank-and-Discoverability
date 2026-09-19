"""
FastAPI Routes for RankPulse application.
"""

from __future__ import annotations
import io
from datetime import datetime
from typing import Optional
from fastapi import APIRouter, UploadFile, File, Query, HTTPException
from fastapi.responses import StreamingResponse
import pandas as pd

from rankpulse.api.schemas import (
    PortfolioOverviewResponse,
    TriageQueueResponse,
    TriageItem,
    PageDetailResponse,
    UpdateTriageRequest,
    StandardResponse,
    DailyDataPoint,
    IngestGlobalRequest,
)
from rankpulse.core.database import (
    fetch_all_daily_metrics,
    insert_daily_metrics,
    get_available_date_range,
    fetch_triage_records,
    update_triage_status,
)
from rankpulse.engine.features import extract_features_at_cutoff, FEATURE_COLUMNS
from rankpulse.engine.model import (
    load_model_artifacts,
    score_features_dataframe,
    train_momentum_model,
    save_model_artifacts,
)
from rankpulse.engine.reason_codes import assign_reason_codes_to_dataframe
from rankpulse.engine.playbook import get_playbook_for_reason, ActionPlaybook
from rankpulse.ingestion.csv_loader import load_gsc_csv
from rankpulse.ingestion.mock_generator import generate_mock_gsc_dataset

router = APIRouter(prefix="/api")

# In-memory dataframe cache for fast response times
_SCORING_CACHE: dict[str, Any] = {
    "last_updated": None,
    "scored_df": None,
}


def _get_or_compute_scored_df(force_refresh: bool = False) -> pd.DataFrame:
    """Helper to extract features and score all pages as of latest available date."""
    if not force_refresh and _SCORING_CACHE["scored_df"] is not None:
        return _SCORING_CACHE["scored_df"]

    df_daily = fetch_all_daily_metrics()
    if df_daily.empty:
        return pd.DataFrame()

    min_date, max_date, count = get_available_date_range()
    if not max_date:
        return pd.DataFrame()

    # Extract features at latest cutoff
    features_df = extract_features_at_cutoff(df_daily, cutoff_date=max_date, include_label=False)
    if features_df.empty:
        return pd.DataFrame()

    # Load model if present
    model, _ = load_model_artifacts()
    scored = score_features_dataframe(features_df, model=model)
    scored = assign_reason_codes_to_dataframe(scored)

    # Attach primary action
    actions = []
    for code in scored["reason_code"]:
        pb = get_playbook_for_reason(code)
        actions.append(pb["primary_action"])
    scored["primary_action"] = actions

    _SCORING_CACHE["scored_df"] = scored
    _SCORING_CACHE["last_updated"] = datetime.utcnow()
    return scored


@router.get("/overview", response_model=PortfolioOverviewResponse)
def get_portfolio_overview():
    """Retrieve portfolio-wide health KPIs, risk breakdown, and model status."""
    min_date, max_date, count = get_available_date_range()
    scored = _get_or_compute_scored_df()

    _, meta = load_model_artifacts()
    has_model = meta.get("roc_auc") is not None

    if scored.empty:
        return PortfolioOverviewResponse(
            total_monitored_pages=0,
            critical_risk_count=0,
            high_risk_count=0,
            moderate_risk_count=0,
            low_risk_count=0,
            total_impressions_p1=0,
            projected_at_risk_impressions=0,
            average_risk_probability=0.0,
            data_date_min=min_date,
            data_date_max=max_date,
            has_trained_model=has_model,
            model_auc=meta.get("roc_auc"),
        )

    crit = int((scored["risk_level"] == "CRITICAL").sum())
    high = int((scored["risk_level"] == "HIGH").sum())
    mod = int((scored["risk_level"] == "MODERATE").sum())
    low = int((scored["risk_level"] == "LOW").sum())

    total_imp = int(scored["imp_p1"].sum())
    # Projected impressions at risk (pages in critical or high risk * expected 20% drop)
    at_risk_df = scored[scored["risk_level"].isin(["CRITICAL", "HIGH"])]
    at_risk_imp = int((at_risk_df["imp_p1"] * at_risk_df["model_proba"] * 0.20).sum())

    avg_p = float(scored["model_proba"].mean())

    return PortfolioOverviewResponse(
        total_monitored_pages=len(scored),
        critical_risk_count=crit,
        high_risk_count=high,
        moderate_risk_count=mod,
        low_risk_count=low,
        total_impressions_p1=total_imp,
        projected_at_risk_impressions=at_risk_imp,
        average_risk_probability=round(avg_p, 3),
        data_date_min=min_date,
        data_date_max=max_date,
        has_trained_model=has_model,
        model_auc=meta.get("roc_auc"),
    )


@router.get("/queue", response_model=TriageQueueResponse)
def get_triage_queue(
    page: int = Query(1, ge=1),
    page_size: int = Query(25, ge=1, le=100),
    risk_level: Optional[str] = Query(None, description="CRITICAL, HIGH, MODERATE, LOW, or ALL"),
    status: Optional[str] = Query(None, description="PENDING, IN_REVIEW, REFRESHED, IGNORED, or ALL"),
    search: Optional[str] = Query(None, description="URL search substring"),
    sort_by: str = Query("model_proba", description="model_proba, imp_p1, avg_pos_p1, baseline_score"),
    sort_desc: bool = Query(True),
):
    """Retrieve filtered, sorted, and paginated editorial triage queue."""
    scored = _get_or_compute_scored_df()
    if scored.empty:
        return TriageQueueResponse(total_count=0, page=page, page_size=page_size, items=[])

    df = scored.copy()
    triage_map = fetch_triage_records()

    # Attach triage status, notes, assignee
    statuses = []
    notes = []
    assignees = []
    for url in df["page_url"]:
        rec = triage_map.get(url, {})
        statuses.append(rec.get("status", "PENDING"))
        notes.append(rec.get("notes", ""))
        assignees.append(rec.get("assigned_to", ""))

    df["status"] = statuses
    df["notes"] = notes
    df["assigned_to"] = assignees

    # Apply filters
    if risk_level and risk_level.upper() != "ALL":
        df = df[df["risk_level"] == risk_level.upper()]

    if status and status.upper() != "ALL":
        df = df[df["status"] == status.upper()]

    if search:
        df = df[df["page_url"].str.contains(search, case=False, na=False)]

    total_count = len(df)

    # Sort
    if sort_by in df.columns:
        df = df.sort_values(sort_by, ascending=not sort_desc)
    else:
        df = df.sort_values("model_proba", ascending=False)

    # Paginate
    start_idx = (page - 1) * page_size
    end_idx = start_idx + page_size
    page_df = df.iloc[start_idx:end_idx]

    items = []
    for _, r in page_df.iterrows():
        items.append(
            TriageItem(
                page_url=r["page_url"],
                model_proba=float(r["model_proba"]),
                risk_level=str(r["risk_level"]),
                baseline_score=float(r["baseline_score"]),
                reason_code=str(r["reason_code"]),
                reason_title=str(r["reason_title"]),
                reason_description=str(r["reason_description"]),
                reason_severity=str(r["reason_severity"]),
                primary_action=str(r["primary_action"]),
                imp_p1=int(r["imp_p1"]),
                clk_p1=int(r["clk_p1"]),
                avg_pos_p1=round(float(r["avg_pos_p1"]), 1),
                ctr_p1=round(float(r["ctr_p1"]), 4),
                momentum_ratio=round(float(r["momentum_ratio"]), 2),
                pos_delta=round(float(r["pos_delta"]), 2),
                status=str(r["status"]),
                notes=str(r["notes"]),
                assigned_to=str(r["assigned_to"]),
            )
        )

    return TriageQueueResponse(total_count=total_count, page=page, page_size=page_size, items=items)


@router.get("/page/{page_url:path}", response_model=PageDetailResponse)
def get_page_detail(page_url: str):
    """Retrieve detailed diagnostics, time-series history, and playbook for a single URL."""
    scored = _get_or_compute_scored_df()
    if scored.empty:
        raise HTTPException(status_code=404, detail="No data available in warehouse.")

    match = scored[scored["page_url"] == page_url]
    if match.empty:
        raise HTTPException(status_code=404, detail=f"Page not found in monitored set: {page_url}")

    r = match.iloc[0]
    triage_map = fetch_triage_records()
    triage_rec = triage_map.get(page_url, {})

    item = TriageItem(
        page_url=r["page_url"],
        model_proba=float(r["model_proba"]),
        risk_level=str(r["risk_level"]),
        baseline_score=float(r["baseline_score"]),
        reason_code=str(r["reason_code"]),
        reason_title=str(r["reason_title"]),
        reason_description=str(r["reason_description"]),
        reason_severity=str(r["reason_severity"]),
        primary_action=str(r["primary_action"]),
        imp_p1=int(r["imp_p1"]),
        clk_p1=int(r["clk_p1"]),
        avg_pos_p1=round(float(r["avg_pos_p1"]), 1),
        ctr_p1=round(float(r["ctr_p1"]), 4),
        momentum_ratio=round(float(r["momentum_ratio"]), 2),
        pos_delta=round(float(r["pos_delta"]), 2),
        status=str(triage_rec.get("status", "PENDING")),
        notes=str(triage_rec.get("notes", "")),
        assigned_to=str(triage_rec.get("assigned_to", "")),
    )

    playbook = get_playbook_for_reason(r["reason_code"])

    # Fetch historical daily points for charting
    df_all = fetch_all_daily_metrics()
    page_history = df_all[df_all["page_url"] == page_url].sort_values("report_date")

    history_points = [
        DailyDataPoint(
            date=row["report_date"],
            impressions=int(row["impressions"]),
            clicks=int(row["clicks"]),
            ctr=round(float(row["ctr"]), 4),
            avg_position=round(float(row["avg_position"]), 1),
        )
        for _, row in page_history.iterrows()
    ]

    return PageDetailResponse(
        page_url=page_url,
        metrics=item,
        checklist=playbook["checklist"],
        time_estimate=playbook["time_estimate"],
        what_would_make_it_wrong=playbook["what_would_make_it_wrong"],
        history=history_points,
    )


@router.post("/triage/{page_url:path}", response_model=StandardResponse)
def update_page_triage(page_url: str, payload: UpdateTriageRequest):
    """Update editorial triage workflow status and notes for a page."""
    valid_statuses = ["PENDING", "IN_REVIEW", "REFRESHED", "IGNORED"]
    if payload.status.upper() not in valid_statuses:
        raise HTTPException(status_code=400, detail=f"Invalid status. Must be one of: {valid_statuses}")

    update_triage_status(
        page_url=page_url,
        status=payload.status.upper(),
        notes=payload.notes,
        assigned_to=payload.assigned_to,
    )
    return StandardResponse(success=True, message=f"Updated triage record for {page_url}")


@router.post("/upload", response_model=StandardResponse)
async def upload_gsc_csv(file: UploadFile = File(...)):
    """Upload and ingest a Google Search Console CSV export."""
    contents = await file.read()
    try:
        df = load_gsc_csv(contents)
        rows_inserted = insert_daily_metrics(df)
        _get_or_compute_scored_df(force_refresh=True)
        return StandardResponse(
            success=True,
            message=f"Successfully ingested {rows_inserted:,} records from '{file.filename}'.",
            data={"rows_inserted": rows_inserted},
        )
    except Exception as e:
        raise HTTPException(status_code=400, detail=f"Failed to parse CSV: {str(e)}")


@router.post("/generate-demo", response_model=StandardResponse)
def generate_demo_dataset():
    """Generate authentic synthetic GSC benchmark data and run full pipeline."""
    df_mock = generate_mock_gsc_dataset(num_pages=350, num_days=60)
    rows_inserted = insert_daily_metrics(df_mock)

    # Train model automatically on this data
    # Create training features using midpoint as historical cutoff
    unique_dates = sorted(df_mock["report_date"].unique())
    cutoff = unique_dates[len(unique_dates) - 15]
    train_features = extract_features_at_cutoff(df_mock, cutoff_date=cutoff, include_label=True)

    if not train_features.empty and train_features["is_declining_proxy"].nunique() > 1:
        model, metrics = train_momentum_model(train_features)
        save_model_artifacts(model, metrics)

    _get_or_compute_scored_df(force_refresh=True)

    return StandardResponse(
        success=True,
        message=f"Generated {rows_inserted:,} synthetic GSC records across {df_mock['page_url'].nunique()} pages. Model trained and calibrated.",
        data={"pages": df_mock["page_url"].nunique(), "total_rows": rows_inserted},
    )


@router.post("/ingest-global", response_model=StandardResponse)
def ingest_global_traffic(payload: Optional[IngestGlobalRequest] = None):
    """Fetch authentic daily global traffic for top web topics, trending articles, or custom queries and retrain model."""
    from rankpulse.ingestion.global_data import fetch_global_authentic_search_data

    req = payload or IngestGlobalRequest()
    df_global = fetch_global_authentic_search_data(
        category=req.category,
        custom_topics=req.custom_topics,
        days=req.days,
        max_topics=req.max_topics,
    )
    if df_global.empty:
        raise HTTPException(status_code=502, detail="Failed to fetch global traffic data.")

    rows_inserted = insert_daily_metrics(df_global)

    # Train model on this authentic data
    dates = sorted(df_global["report_date"].unique())
    if len(dates) >= 28:
        cutoff = dates[len(dates) - 14]
        train_features = extract_features_at_cutoff(df_global, cutoff_date=cutoff, include_label=True)
        if not train_features.empty and len(train_features) >= 20 and train_features["is_declining_proxy"].nunique() > 1:
            try:
                model, metrics = train_momentum_model(train_features)
                save_model_artifacts(model, metrics)
            except Exception:
                pass

    _get_or_compute_scored_df(force_refresh=True)

    return StandardResponse(
        success=True,
        message=f"Successfully ingested {rows_inserted:,} authentic global records across {df_global['page_url'].nunique()} topics (category: {req.category}).",
        data={"topics": df_global["page_url"].nunique(), "rows_inserted": rows_inserted, "category": req.category},
    )


@router.post("/ingest-warehouse", response_model=StandardResponse)
def ingest_warehouse(payload: dict = None):
    """Stream real Google Search facts from FlyRank warehouse on Hugging Face."""
    from rankpulse.ingestion.global_data import fetch_huggingface_warehouse_data
    token = (payload or {}).get("hf_token", "")
    if not token:
        raise HTTPException(status_code=400, detail="Hugging Face read token ('hf_token') is required.")

    try:
        df_wh = fetch_huggingface_warehouse_data(hf_token=token)
        rows = insert_daily_metrics(df_wh)
        _get_or_compute_scored_df(force_refresh=True)
        return StandardResponse(
            success=True,
            message=f"Successfully streamed {rows:,} real Search Console facts from Hugging Face FlyRank warehouse.",
            data={"rows_inserted": rows},
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Warehouse stream failed: {str(e)}")


@router.post("/retrain", response_model=StandardResponse)
def retrain_model():
    """Retrain calibrated ML model on all available historical data."""
    df = fetch_all_daily_metrics()
    if df.empty:
        raise HTTPException(status_code=400, detail="Cannot train: database has no data.")

    dates = sorted(df["report_date"].unique())
    if len(dates) < 28:
        raise HTTPException(status_code=400, detail=f"Need at least 28 days of data for rolling windows, found {len(dates)}.")

    cutoff = dates[len(dates) - 14]
    features_df = extract_features_at_cutoff(df, cutoff_date=cutoff, include_label=True)

    if features_df.empty or "is_declining_proxy" not in features_df.columns:
        raise HTTPException(status_code=400, detail="Insufficient outcome data for training label.")

    try:
        model, metrics = train_momentum_model(features_df)
        save_model_artifacts(model, metrics)
        _get_or_compute_scored_df(force_refresh=True)
        return StandardResponse(
            success=True,
            message="Model successfully retrained and calibrated.",
            data=metrics,
        )
    except Exception as e:
        raise HTTPException(status_code=500, detail=f"Model training failed: {str(e)}")


@router.get("/model/metrics")
def get_model_metrics():
    """Retrieve model training evaluation metrics, ROC-AUC, lift, and feature importances."""
    _, meta = load_model_artifacts()
    if not meta:
        return {"has_model": False, "message": "No model trained yet."}
    return {"has_model": True, "metrics": meta}


@router.get("/export")
def export_triage_csv():
    """Export current prioritized triage queue as a downloadable CSV."""
    scored = _get_or_compute_scored_df()
    if scored.empty:
        raise HTTPException(status_code=400, detail="No scored data to export.")

    triage_map = fetch_triage_records()
    statuses = [triage_map.get(u, {}).get("status", "PENDING") for u in scored["page_url"]]
    scored["status"] = statuses

    cols = [
        "page_url",
        "model_proba",
        "risk_level",
        "baseline_score",
        "reason_code",
        "reason_title",
        "primary_action",
        "imp_p1",
        "clk_p1",
        "avg_pos_p1",
        "ctr_p1",
        "momentum_ratio",
        "status",
    ]
    export_df = scored[cols].sort_values("model_proba", ascending=False)

    stream = io.StringIO()
    export_df.to_csv(stream, index=False)
    response = StreamingResponse(iter([stream.getvalue()]), media_type="text/csv")
    response.headers["Content-Disposition"] = "attachment; filename=rankpulse_triage_queue.csv"
    return response
