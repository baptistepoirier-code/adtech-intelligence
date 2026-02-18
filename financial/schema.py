"""
SQLite schema for the Ad Tech Financial Intel database.
"""

SCHEMA_SQL = """
CREATE TABLE IF NOT EXISTS companies (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    name        TEXT    NOT NULL UNIQUE,
    ticker      TEXT,
    cik         TEXT,
    is_public   INTEGER NOT NULL DEFAULT 0,
    data_quality TEXT   NOT NULL DEFAULT 'low',  -- high / medium / low
    description TEXT
);

CREATE TABLE IF NOT EXISTS periods (
    id              INTEGER PRIMARY KEY AUTOINCREMENT,
    company_id      INTEGER NOT NULL REFERENCES companies(id),
    fiscal_year     INTEGER NOT NULL,
    fiscal_quarter  INTEGER,          -- NULL for annual
    period_end_date TEXT,
    period_type     TEXT NOT NULL,     -- 'annual' or 'quarterly'
    UNIQUE(company_id, fiscal_year, fiscal_quarter)
);

CREATE TABLE IF NOT EXISTS metrics (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    period_id         INTEGER NOT NULL REFERENCES periods(id),
    metric_name       TEXT    NOT NULL,  -- Revenue, GrossProfit, EBITDA, ...
    metric_variant    TEXT    NOT NULL DEFAULT 'GAAP',  -- GAAP or Adjusted
    value             REAL,              -- NULL means not disclosed
    currency          TEXT    NOT NULL DEFAULT 'USD',
    unit              TEXT    NOT NULL DEFAULT 'millions',
    source_url        TEXT,
    source_description TEXT,
    retrieved_at      TEXT,
    UNIQUE(period_id, metric_name, metric_variant)
);

CREATE TABLE IF NOT EXISTS segments (
    id                INTEGER PRIMARY KEY AUTOINCREMENT,
    period_id         INTEGER NOT NULL REFERENCES periods(id),
    segment_name      TEXT    NOT NULL,   -- normalised name
    original_label    TEXT,               -- as reported
    revenue           REAL,
    operating_income  REAL,
    source_url        TEXT,
    UNIQUE(period_id, segment_name)
);

CREATE TABLE IF NOT EXISTS derived_metrics (
    id          INTEGER PRIMARY KEY AUTOINCREMENT,
    period_id   INTEGER NOT NULL REFERENCES periods(id),
    metric_name TEXT    NOT NULL,  -- GrossMargin, EBITDAMargin, YoY_Revenue, ...
    value       REAL,
    UNIQUE(period_id, metric_name)
);

CREATE INDEX IF NOT EXISTS idx_periods_company ON periods(company_id);
CREATE INDEX IF NOT EXISTS idx_metrics_period  ON metrics(period_id);
CREATE INDEX IF NOT EXISTS idx_segments_period ON segments(period_id);
CREATE INDEX IF NOT EXISTS idx_derived_period  ON derived_metrics(period_id);
"""
