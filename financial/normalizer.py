"""
Normalizer: computes derived metrics from raw financial data.
- Margins (Gross, EBITDA, Operating, Net)
- YoY growth rates
- OpEx ratios (R&D %, S&M %, G&A %)
"""

from .database import (
    get_all_companies, get_periods, get_metrics, upsert_derived,
)


def _safe_pct(numerator, denominator):
    """Compute percentage, returning None if impossible."""
    if numerator is None or denominator is None or denominator == 0:
        return None
    return round((numerator / denominator) * 100, 1)


def _get_metric_value(metrics, name, variant=None):
    """Find a metric value from a list of metric rows."""
    for m in metrics:
        if m["metric_name"] == name:
            if variant is None or m["metric_variant"] == variant:
                return m["value"]
    return None


def compute_derived_metrics(conn):
    """Compute all derived metrics and store in derived_metrics table."""
    companies = get_all_companies(conn)
    total_derived = 0

    for company in companies:
        cid = company["id"]
        cname = company["name"]
        periods = get_periods(conn, cid, "annual")
        periods.sort(key=lambda p: p["fiscal_year"])

        prev_metrics_cache = {}

        for period in periods:
            pid = period["id"]
            fy = period["fiscal_year"]
            metrics = get_metrics(conn, pid)

            revenue = _get_metric_value(metrics, "Revenue")
            gross_profit = _get_metric_value(metrics, "GrossProfit")
            op_income = _get_metric_value(metrics, "OperatingIncome")
            net_income = _get_metric_value(metrics, "NetIncome")
            adj_ebitda = _get_metric_value(metrics, "AdjustedEBITDA", "Adjusted")
            fcf = _get_metric_value(metrics, "FreeCashFlow", "Adjusted")
            rnd = _get_metric_value(metrics, "RnD")
            sm = _get_metric_value(metrics, "SalesMarketing")
            ga = _get_metric_value(metrics, "GeneralAdmin")

            # Margins
            gross_margin = _safe_pct(gross_profit, revenue)
            if gross_margin is not None:
                upsert_derived(conn, pid, "GrossMargin", gross_margin)
                total_derived += 1

            op_margin = _safe_pct(op_income, revenue)
            if op_margin is not None:
                upsert_derived(conn, pid, "OperatingMargin", op_margin)
                total_derived += 1

            net_margin = _safe_pct(net_income, revenue)
            if net_margin is not None:
                upsert_derived(conn, pid, "NetMargin", net_margin)
                total_derived += 1

            ebitda_margin = _safe_pct(adj_ebitda, revenue)
            if ebitda_margin is not None:
                upsert_derived(conn, pid, "EBITDAMargin", ebitda_margin)
                total_derived += 1

            # FCF / EBITDA
            if fcf is not None and adj_ebitda is not None and adj_ebitda != 0:
                fcf_ebitda = round(fcf / adj_ebitda * 100, 1)
                upsert_derived(conn, pid, "FCF_EBITDA", fcf_ebitda)
                total_derived += 1

            # OpEx ratios
            rnd_pct = _safe_pct(rnd, revenue)
            if rnd_pct is not None:
                upsert_derived(conn, pid, "RnD_Pct", rnd_pct)
                total_derived += 1

            sm_pct = _safe_pct(sm, revenue)
            if sm_pct is not None:
                upsert_derived(conn, pid, "SM_Pct", sm_pct)
                total_derived += 1

            ga_pct = _safe_pct(ga, revenue)
            if ga_pct is not None:
                upsert_derived(conn, pid, "GA_Pct", ga_pct)
                total_derived += 1

            # YoY growth
            if fy - 1 in prev_metrics_cache:
                prev = prev_metrics_cache[fy - 1]
                prev_revenue = prev.get("Revenue")
                if revenue is not None and prev_revenue is not None and prev_revenue != 0:
                    yoy = round(((revenue - prev_revenue) / abs(prev_revenue)) * 100, 1)
                    upsert_derived(conn, pid, "YoY_Revenue", yoy)
                    total_derived += 1

                prev_ebitda = prev.get("AdjustedEBITDA")
                if adj_ebitda is not None and prev_ebitda is not None and prev_ebitda != 0:
                    yoy_ebitda = round(((adj_ebitda - prev_ebitda) / abs(prev_ebitda)) * 100, 1)
                    upsert_derived(conn, pid, "YoY_EBITDA", yoy_ebitda)
                    total_derived += 1

            # Cache for next year's YoY calculation
            prev_metrics_cache[fy] = {
                "Revenue": revenue,
                "AdjustedEBITDA": adj_ebitda,
            }

    print(f"  Computed {total_derived} derived metrics.")
