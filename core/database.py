"""
Database access and schema management for RankPulse using SQLite.
Stores daily page performance metrics, editorial triage records, and cached predictions.
"""

from __future__ import annotations
import sqlite3
from contextlib import contextmanager
from datetime import datetime
from pathlib import Path
from typing import Generator, Any
import pandas as pd

from rankpulse.core.config import DB_PATH


@contextmanager
def get_db(db_path: Path = DB_PATH) -> Generator[sqlite3.Connection, None, None]:
    """Context manager for SQLite connection with row factory."""
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    try:
        yield conn
        conn.commit()
    except Exception:
        conn.rollback()
        raise
    finally:
        conn.close()


def init_db(db_path: Path = DB_PATH) -> None:
    """Initialize SQLite database tables and indexes."""
    db_path.parent.mkdir(parents=True, exist_ok=True)
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        
        # 1. Daily GSC Performance table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS gsc_daily_performance (
                id INTEGER PRIMARY KEY AUTOINCREMENT,
                report_date TEXT NOT NULL,
                page_url TEXT NOT NULL,
                query TEXT,
                impressions INTEGER NOT NULL,
                clicks INTEGER NOT NULL,
                ctr REAL NOT NULL,
                avg_position REAL NOT NULL
            );
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gsc_date_page 
            ON gsc_daily_performance (report_date, page_url);
        """)
        cursor.execute("""
            CREATE INDEX IF NOT EXISTS idx_gsc_page 
            ON gsc_daily_performance (page_url);
        """)

        # 2. Editorial Triage Status table
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS triage_records (
                page_url TEXT PRIMARY KEY,
                status TEXT NOT NULL DEFAULT 'PENDING',
                notes TEXT,
                assigned_to TEXT,
                updated_at TEXT NOT NULL
            );
        """)

        # 3. Model Predictions & Diagnostic Cache
        cursor.execute("""
            CREATE TABLE IF NOT EXISTS predictions_cache (
                page_url TEXT PRIMARY KEY,
                as_of_date TEXT NOT NULL,
                model_proba REAL NOT NULL,
                baseline_score REAL NOT NULL,
                risk_level TEXT NOT NULL,
                reason_code TEXT NOT NULL,
                reason_title TEXT NOT NULL,
                reason_description TEXT NOT NULL,
                action_playbook TEXT NOT NULL,
                imp_p1 INTEGER NOT NULL,
                clk_p1 INTEGER NOT NULL,
                avg_pos_p1 REAL NOT NULL,
                ctr_p1 REAL NOT NULL,
                momentum_ratio REAL NOT NULL,
                computed_at TEXT NOT NULL
            );
        """)


def insert_daily_metrics(df: pd.DataFrame, db_path: Path = DB_PATH) -> int:
    """
    Insert a DataFrame of daily metrics into gsc_daily_performance.
    Required columns: ['report_date', 'page_url', 'impressions', 'clicks', 'ctr', 'avg_position']
    Optional column: 'query'
    """
    if df.empty:
        return 0

    records = []
    has_query = "query" in df.columns

    for _, row in df.iterrows():
        records.append((
            str(row["report_date"]),
            str(row["page_url"]),
            str(row["query"]) if has_query and pd.notna(row["query"]) else None,
            int(row["impressions"]),
            int(row["clicks"]),
            float(row["ctr"]),
            float(row["avg_position"]),
        ))

    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.executemany("""
            INSERT INTO gsc_daily_performance 
            (report_date, page_url, query, impressions, clicks, ctr, avg_position)
            VALUES (?, ?, ?, ?, ?, ?, ?)
        """, records)
    return len(records)


def get_available_date_range(db_path: Path = DB_PATH) -> tuple[str | None, str | None, int]:
    """Returns (min_date, max_date, total_rows)."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            SELECT MIN(report_date), MAX(report_date), COUNT(*) 
            FROM gsc_daily_performance
        """)
        row = cursor.fetchone()
        if row and row[0]:
            return row[0], row[1], row[2]
        return None, None, 0


def fetch_all_daily_metrics(db_path: Path = DB_PATH) -> pd.DataFrame:
    """Load all daily performance records into a pandas DataFrame."""
    with get_db(db_path) as conn:
        df = pd.read_sql_query("""
            SELECT report_date, page_url, impressions, clicks, ctr, avg_position
            FROM gsc_daily_performance
            ORDER BY report_date ASC, page_url ASC
        """, conn)
    return df


def update_triage_status(page_url: str, status: str, notes: str = "", assigned_to: str = "", db_path: Path = DB_PATH) -> None:
    """Update or insert the editorial triage workflow status."""
    now_str = datetime.utcnow().isoformat()
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("""
            INSERT INTO triage_records (page_url, status, notes, assigned_to, updated_at)
            VALUES (?, ?, ?, ?, ?)
            ON CONFLICT(page_url) DO UPDATE SET
                status = excluded.status,
                notes = CASE WHEN excluded.notes != '' THEN excluded.notes ELSE triage_records.notes END,
                assigned_to = CASE WHEN excluded.assigned_to != '' THEN excluded.assigned_to ELSE triage_records.assigned_to END,
                updated_at = excluded.updated_at
        """, (page_url, status, notes, assigned_to, now_str))


def fetch_triage_records(db_path: Path = DB_PATH) -> dict[str, dict[str, Any]]:
    """Retrieve all triage records mapped by page_url."""
    with get_db(db_path) as conn:
        cursor = conn.cursor()
        cursor.execute("SELECT page_url, status, notes, assigned_to, updated_at FROM triage_records")
        rows = cursor.fetchall()
        return {row["page_url"]: dict(row) for row in rows}
