#!/usr/bin/env python3
"""
Ad Tech Financial Intel — Main Pipeline
========================================
Usage:
    python -m financial.run [--skip-edgar] [--db PATH] [--output DIR]

Steps:
    1. Init SQLite database
    2. Load curated data (YAML)
    3. Fetch SEC EDGAR data for public companies (optional)
    4. Compute derived metrics (margins, YoY, etc.)
    5. Generate HTML dashboard
"""

import argparse
import os
import sys

# Add parent dir to path so we can run from adtech-curator/
sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from financial.database import init_db, DB_PATH
from financial.extractor import load_curated_into_db, load_edgar_into_db
from financial.normalizer import compute_derived_metrics
from financial.dashboard_generator import generate_financial_dashboard


def main():
    parser = argparse.ArgumentParser(description="Ad Tech Financial Intel Pipeline")
    parser.add_argument("--skip-edgar", action="store_true",
                        help="Skip SEC EDGAR API calls (use curated data only)")
    parser.add_argument("--db", default=DB_PATH, help="Path to SQLite database")
    parser.add_argument("--output", default=os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "output"),
                        help="Output directory for dashboard HTML")
    args = parser.parse_args()

    print("=" * 60)
    print("  Ad Tech Financial Intel — Pipeline")
    print("=" * 60)

    # Step 1: Init DB
    print("\n[1/5] Initializing database...")
    db_path = args.db
    # Remove old DB for clean rebuild
    if os.path.exists(db_path):
        os.remove(db_path)
        print(f"  Removed existing DB: {db_path}")
    conn = init_db(db_path)
    print(f"  Database ready: {db_path}")

    # Step 2: Load curated data
    print("\n[2/5] Loading curated financial data...")
    load_curated_into_db(conn)

    # Step 3: SEC EDGAR
    if args.skip_edgar:
        print("\n[3/5] Skipping SEC EDGAR (--skip-edgar flag)")
    else:
        print("\n[3/5] Fetching SEC EDGAR data for public companies...")
        try:
            load_edgar_into_db(conn)
        except Exception as e:
            print(f"  [WARNING] EDGAR collection failed: {e}")
            print("  Continuing with curated data only.")

    # Step 4: Compute derived metrics
    print("\n[4/5] Computing derived metrics...")
    compute_derived_metrics(conn)

    # Step 5: Generate dashboard
    print("\n[5/5] Generating HTML dashboard...")
    conn.close()  # Close before generator opens its own connection
    out_path = generate_financial_dashboard(db_path, args.output)

    print("\n" + "=" * 60)
    print(f"  Dashboard generated: {out_path}")
    print(f"  Database: {db_path}")
    print("=" * 60)
    print(f"\n  open {out_path}")


if __name__ == "__main__":
    main()
