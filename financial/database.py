"""
SQLite database layer for financial data.
"""

import sqlite3
import os
from datetime import datetime
from typing import Optional

from .schema import SCHEMA_SQL

DB_PATH = os.path.join(os.path.dirname(__file__), "financial_intel.db")


def get_connection(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = sqlite3.connect(db_path)
    conn.row_factory = sqlite3.Row
    conn.execute("PRAGMA journal_mode=WAL")
    conn.execute("PRAGMA foreign_keys=ON")
    return conn


def init_db(db_path: str = DB_PATH) -> sqlite3.Connection:
    conn = get_connection(db_path)
    conn.executescript(SCHEMA_SQL)
    conn.commit()
    return conn


# ── Company CRUD ─────────────────────────────────────────────

def upsert_company(
    conn: sqlite3.Connection,
    name: str,
    ticker: str = None,
    cik: str = None,
    is_public: bool = False,
    data_quality: str = "low",
    description: str = None,
) -> int:
    cur = conn.execute(
        """INSERT INTO companies (name, ticker, cik, is_public, data_quality, description)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(name) DO UPDATE SET
             ticker=excluded.ticker, cik=excluded.cik,
             is_public=excluded.is_public, data_quality=excluded.data_quality,
             description=excluded.description""",
        (name, ticker, cik, int(is_public), data_quality, description),
    )
    conn.commit()
    row = conn.execute("SELECT id FROM companies WHERE name=?", (name,)).fetchone()
    return row["id"]


def get_company(conn: sqlite3.Connection, name: str) -> Optional[dict]:
    row = conn.execute("SELECT * FROM companies WHERE name=?", (name,)).fetchone()
    return dict(row) if row else None


def get_all_companies(conn: sqlite3.Connection) -> list[dict]:
    return [dict(r) for r in conn.execute("SELECT * FROM companies ORDER BY name").fetchall()]


# ── Period CRUD ──────────────────────────────────────────────

def upsert_period(
    conn: sqlite3.Connection,
    company_id: int,
    fiscal_year: int,
    fiscal_quarter: int = None,
    period_end_date: str = None,
    period_type: str = "annual",
) -> int:
    conn.execute(
        """INSERT INTO periods (company_id, fiscal_year, fiscal_quarter, period_end_date, period_type)
           VALUES (?, ?, ?, ?, ?)
           ON CONFLICT(company_id, fiscal_year, fiscal_quarter) DO UPDATE SET
             period_end_date=excluded.period_end_date, period_type=excluded.period_type""",
        (company_id, fiscal_year, fiscal_quarter, period_end_date, period_type),
    )
    conn.commit()
    row = conn.execute(
        "SELECT id FROM periods WHERE company_id=? AND fiscal_year=? AND fiscal_quarter IS ?",
        (company_id, fiscal_year, fiscal_quarter),
    ).fetchone()
    return row["id"]


def get_periods(conn: sqlite3.Connection, company_id: int, period_type: str = None) -> list[dict]:
    if period_type:
        rows = conn.execute(
            "SELECT * FROM periods WHERE company_id=? AND period_type=? ORDER BY fiscal_year, fiscal_quarter",
            (company_id, period_type),
        ).fetchall()
    else:
        rows = conn.execute(
            "SELECT * FROM periods WHERE company_id=? ORDER BY fiscal_year, fiscal_quarter",
            (company_id,),
        ).fetchall()
    return [dict(r) for r in rows]


# ── Metric CRUD ──────────────────────────────────────────────

def upsert_metric(
    conn: sqlite3.Connection,
    period_id: int,
    metric_name: str,
    value: float = None,
    metric_variant: str = "GAAP",
    currency: str = "USD",
    unit: str = "millions",
    source_url: str = None,
    source_description: str = None,
):
    conn.execute(
        """INSERT INTO metrics (period_id, metric_name, metric_variant, value, currency, unit, source_url, source_description, retrieved_at)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
           ON CONFLICT(period_id, metric_name, metric_variant) DO UPDATE SET
             value=excluded.value, currency=excluded.currency, unit=excluded.unit,
             source_url=excluded.source_url, source_description=excluded.source_description,
             retrieved_at=excluded.retrieved_at""",
        (period_id, metric_name, metric_variant, value, currency, unit,
         source_url, source_description, datetime.utcnow().isoformat()),
    )
    conn.commit()


def get_metrics(conn: sqlite3.Connection, period_id: int) -> list[dict]:
    return [dict(r) for r in conn.execute(
        "SELECT * FROM metrics WHERE period_id=? ORDER BY metric_name", (period_id,)
    ).fetchall()]


# ── Segment CRUD ─────────────────────────────────────────────

def upsert_segment(
    conn: sqlite3.Connection,
    period_id: int,
    segment_name: str,
    original_label: str = None,
    revenue: float = None,
    operating_income: float = None,
    source_url: str = None,
):
    conn.execute(
        """INSERT INTO segments (period_id, segment_name, original_label, revenue, operating_income, source_url)
           VALUES (?, ?, ?, ?, ?, ?)
           ON CONFLICT(period_id, segment_name) DO UPDATE SET
             original_label=excluded.original_label, revenue=excluded.revenue,
             operating_income=excluded.operating_income, source_url=excluded.source_url""",
        (period_id, segment_name, original_label, revenue, operating_income, source_url),
    )
    conn.commit()


# ── Derived Metric CRUD ─────────────────────────────────────

def upsert_derived(conn: sqlite3.Connection, period_id: int, metric_name: str, value: float):
    conn.execute(
        """INSERT INTO derived_metrics (period_id, metric_name, value)
           VALUES (?, ?, ?)
           ON CONFLICT(period_id, metric_name) DO UPDATE SET value=excluded.value""",
        (period_id, metric_name, value),
    )
    conn.commit()


# ── Query helpers for dashboard ──────────────────────────────

def get_dashboard_data(conn: sqlite3.Connection) -> dict:
    """Get all data needed for the dashboard in a single call."""
    companies = get_all_companies(conn)

    data = {"companies": companies, "financials": {}}

    for company in companies:
        cid = company["id"]
        cname = company["name"]
        periods = [dict(r) for r in conn.execute(
            "SELECT * FROM periods WHERE company_id=? ORDER BY fiscal_year, fiscal_quarter", (cid,)
        ).fetchall()]

        company_data = []
        for period in periods:
            pid = period["id"]
            metrics = {r["metric_name"] + ("_" + r["metric_variant"] if r["metric_variant"] != "GAAP" else ""): r
                       for r in conn.execute("SELECT * FROM metrics WHERE period_id=?", (pid,)).fetchall()}
            derived = {r["metric_name"]: r["value"]
                       for r in conn.execute("SELECT * FROM derived_metrics WHERE period_id=?", (pid,)).fetchall()}
            segments = [dict(r) for r in conn.execute(
                "SELECT * FROM segments WHERE period_id=?", (pid,)
            ).fetchall()]

            company_data.append({
                "period": dict(period),
                "metrics": {k: dict(v) for k, v in metrics.items()},
                "derived": derived,
                "segments": segments,
            })

        data["financials"][cname] = company_data

    return data
