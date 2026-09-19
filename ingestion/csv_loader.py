"""
CSV Ingestion module for Google Search Console exports.
Handles diverse export formats from GSC UI, BigQuery GSC bulk exports, and custom formats.
"""

from __future__ import annotations
import io
from pathlib import Path
import pandas as pd


STANDARD_COLUMNS = ["report_date", "page_url", "impressions", "clicks", "ctr", "avg_position"]


def normalize_gsc_dataframe(df: pd.DataFrame) -> pd.DataFrame:
    """
    Standardize varied GSC column names into canonical names:
    ['report_date', 'page_url', 'impressions', 'clicks', 'ctr', 'avg_position']
    """
    column_mapping = {
        # Dates
        "date": "report_date",
        "Date": "report_date",
        "day": "report_date",
        "data_date": "report_date",
        # Pages
        "page": "page_url",
        "Page": "page_url",
        "top_pages": "page_url",
        "Top pages": "page_url",
        "url": "page_url",
        "URL": "page_url",
        "landing_page": "page_url",
        # Impressions
        "impressions": "impressions",
        "Impressions": "impressions",
        "imps": "impressions",
        # Clicks
        "clicks": "clicks",
        "Clicks": "clicks",
        # CTR
        "ctr": "ctr",
        "CTR": "ctr",
        "Ctr": "ctr",
        # Position
        "position": "avg_position",
        "Position": "avg_position",
        "avg_position": "avg_position",
        "Average Position": "avg_position",
        "average_position": "avg_position",
    }

    # Rename existing columns
    df = df.rename(columns={c: column_mapping[c] for c in df.columns if c in column_mapping})

    # Validate required columns
    missing = [col for col in STANDARD_COLUMNS if col not in df.columns]
    if missing:
        raise ValueError(f"Missing required GSC columns: {missing}. Present: {list(df.columns)}")

    # Clean types
    df["report_date"] = pd.to_datetime(df["report_date"]).dt.strftime("%Y-%m-%d")
    df["page_url"] = df["page_url"].astype(str).str.strip()
    df["impressions"] = pd.to_numeric(df["impressions"], errors="coerce").fillna(0).astype(int)
    df["clicks"] = pd.to_numeric(df["clicks"], errors="coerce").fillna(0).astype(int)

    # Handle CTR (could be string like '3.5%' or float like 0.035)
    if df["ctr"].dtype == object:
        df["ctr"] = (
            df["ctr"]
            .astype(str)
            .str.rstrip("%")
            .str.strip()
            .pipe(pd.to_numeric, errors="coerce")
            .fillna(0.0)
            / 100.0
        )
    else:
        df["ctr"] = pd.to_numeric(df["ctr"], errors="coerce").fillna(0.0).astype(float)
        # If CTR max > 1, assume it was represented in percent (e.g. 15.2 for 15.2%)
        if (df["ctr"] > 1.0).any():
            df["ctr"] = df["ctr"] / 100.0

    df["avg_position"] = pd.to_numeric(df["avg_position"], errors="coerce").fillna(50.0).astype(float)

    # Filter out empty URLs or zero impression pages
    df = df[df["page_url"].str.len() > 0]
    df = df.sort_values(["report_date", "page_url"]).reset_index(drop=True)

    return df[STANDARD_COLUMNS]


def load_gsc_csv(file_source: str | Path | bytes | io.StringIO) -> pd.DataFrame:
    """Load and normalize a GSC CSV from file path or byte buffer."""
    if isinstance(file_source, bytes):
        df = pd.read_csv(io.BytesIO(file_source))
    else:
        df = pd.read_csv(file_source)
    return normalize_gsc_dataframe(df)
