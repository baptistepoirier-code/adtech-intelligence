"""
Metric extractor: merges EDGAR XBRL data with curated data and loads into SQLite.
Curated data takes priority for Adjusted metrics (EBITDA, FCF) and segment data,
since these typically come from earnings releases, not XBRL.
"""

from .database import (
    upsert_company, upsert_period, upsert_metric, upsert_segment, init_db,
)
from .collector_curated import get_all_curated
from .collector_edgar import collect_edgar_data


def load_curated_into_db(conn):
    """Load all curated data into the database."""
    companies = get_all_curated()
    print(f"\n  Loading {len(companies)} companies from curated data...")

    for company in companies:
        cid = upsert_company(
            conn,
            name=company["name"],
            ticker=company["ticker"],
            cik=company["cik"],
            is_public=company["is_public"],
            data_quality=company["data_quality"],
            description=company["description"],
        )

        for period in company["periods"]:
            pid = upsert_period(
                conn,
                company_id=cid,
                fiscal_year=period["fiscal_year"],
                fiscal_quarter=None,
                period_end_date=period["period_end_date"],
                period_type=period["period_type"],
            )

            for mname, mdata in period["metrics"].items():
                value = mdata["value"]
                variant = "Adjusted" if mname in ("AdjustedEBITDA", "FreeCashFlow") else "GAAP"
                source_desc = period["source_description"]
                if mdata.get("is_estimate"):
                    source_desc += " [ESTIMATE]"
                if mdata.get("note"):
                    source_desc += f" — {mdata['note']}"

                upsert_metric(
                    conn,
                    period_id=pid,
                    metric_name=mname,
                    value=value,
                    metric_variant=variant,
                    source_url=period["source_url"],
                    source_description=source_desc,
                )

            for seg in period["segments"]:
                upsert_segment(
                    conn,
                    period_id=pid,
                    segment_name=seg["name"],
                    original_label=seg["original_label"],
                    revenue=seg["revenue"],
                    operating_income=seg["operating_income"],
                    source_url=period["source_url"],
                )

    print(f"  Curated data loaded.")


def load_edgar_into_db(conn):
    """Fetch EDGAR data for public companies and merge into DB.
    Only fills gaps — curated data is not overwritten."""
    from .database import get_all_companies, get_periods, get_metrics

    companies = get_all_companies(conn)
    public_companies = [c for c in companies if c["is_public"] and c["cik"]]

    for company in public_companies:
        cik = company["cik"]
        name = company["name"]
        cid = company["id"]

        edgar_data = collect_edgar_data(cik, name)
        if not edgar_data:
            print(f"  [EDGAR] No data returned for {name}")
            continue

        for year, metrics in edgar_data.items():
            # Skip years outside our window
            if year < 2022:
                continue

            # Get or create period
            existing_periods = get_periods(conn, cid, "annual")
            pid = None
            for p in existing_periods:
                if p["fiscal_year"] == year:
                    pid = p["id"]
                    break

            if pid is None:
                end_date = metrics.get("Revenue", {}).get("end_date", f"{year}-12-31")
                pid = upsert_period(
                    conn, company_id=cid, fiscal_year=year,
                    period_end_date=end_date, period_type="annual",
                )

            # Check existing metrics for this period
            existing_metrics = get_metrics(conn, pid)
            existing_names = {m["metric_name"] for m in existing_metrics}

            for mname, mdata in metrics.items():
                # Only fill gaps — don't overwrite curated data
                if mname in existing_names:
                    continue
                upsert_metric(
                    conn,
                    period_id=pid,
                    metric_name=mname,
                    value=mdata["value"],
                    metric_variant="GAAP",
                    source_url=mdata.get("source_url", ""),
                    source_description=mdata.get("source_description", ""),
                )

    print("  EDGAR data merged.")
