"""
Google Search Console API client.
Enables automated daily data extraction directly from the GSC API
using OAuth2 credentials or a Google Cloud Service Account.
"""

from __future__ import annotations
import os
from datetime import datetime, timedelta
from pathlib import Path
from typing import Any
import pandas as pd

from rankpulse.ingestion.csv_loader import normalize_gsc_dataframe

# Optional imports for Google API client
try:
    from google.oauth2 import service_account
    from googleapiclient.discovery import build
    GOOGLE_API_AVAILABLE = True
except ImportError:
    GOOGLE_API_AVAILABLE = False


class GSCClient:
    """Client for pulling daily page-level metrics from Google Search Console API."""

    def __init__(self, credentials_path: str | Path | None = None, site_url: str | None = None):
        self.site_url = site_url or os.environ.get("GSC_SITE_URL")
        self.credentials_path = credentials_path or os.environ.get("GOOGLE_APPLICATION_CREDENTIALS")
        self.service = None

        if self.credentials_path and Path(self.credentials_path).exists():
            self._authenticate()

    def _authenticate(self) -> None:
        """Authenticate with Google Search Console using a Service Account JSON."""
        if not GOOGLE_API_AVAILABLE:
            raise ImportError("Google API client packages not installed. Run 'pip install google-api-python-client google-auth'.")

        scopes = ["https://www.googleapis.com/auth/webmasters.readonly"]
        creds = service_account.Credentials.from_service_account_file(
            str(self.credentials_path), scopes=scopes
        )
        self.service = build("searchconsole", "v1", credentials=creds)

    def fetch_daily_performance(
        self,
        start_date: str,
        end_date: str,
        site_url: str | None = None,
        row_limit: int = 25000,
    ) -> pd.DataFrame:
        """
        Query Search Console API for daily page metrics.
        Returns a normalized DataFrame with ['report_date', 'page_url', 'impressions', 'clicks', 'ctr', 'avg_position'].
        """
        target_site = site_url or self.site_url
        if not target_site:
            raise ValueError("site_url must be provided or configured in GSC_SITE_URL environment variable.")

        if not self.service:
            raise RuntimeError("GSC service is not authenticated. Provide valid credentials_path.")

        request_body = {
            "startDate": start_date,
            "endDate": end_date,
            "dimensions": ["date", "page"],
            "rowLimit": row_limit,
            "startRow": 0,
        }

        response = (
            self.service.searchanalytics()
            .query(siteUrl=target_site, body=request_body)
            .execute()
        )

        rows = response.get("rows", [])
        if not rows:
            return pd.DataFrame(columns=["report_date", "page_url", "impressions", "clicks", "ctr", "avg_position"])

        records = []
        for row in rows:
            keys = row.get("keys", ["", ""])
            records.append({
                "report_date": keys[0],
                "page_url": keys[1],
                "clicks": row.get("clicks", 0),
                "impressions": row.get("impressions", 0),
                "ctr": row.get("ctr", 0.0),
                "avg_position": row.get("position", 0.0),
            })

        df = pd.DataFrame(records)
        return normalize_gsc_dataframe(df)

    def is_configured(self) -> bool:
        """Check if API client is authenticated and ready."""
        return self.service is not None and bool(self.site_url)
