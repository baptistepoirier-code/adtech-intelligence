"""
SEC EDGAR XBRL Company Facts API collector.

Uses the free endpoint: https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json
SEC requires a User-Agent header with company name and contact email.
Rate limit: 10 requests/second.
"""

import json
import os
import time
import urllib.request
from typing import Optional

EDGAR_BASE = "https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json"
CACHE_DIR = os.path.join(os.path.dirname(__file__), ".cache")
USER_AGENT = "AdTechFinancialIntel research@example.com"

# XBRL US-GAAP concepts we want to extract
METRIC_CONCEPTS = {
    "Revenue": [
        "us-gaap:Revenues",
        "us-gaap:RevenueFromContractWithCustomerExcludingAssessedTax",
        "us-gaap:SalesRevenueNet",
        "us-gaap:RevenueFromContractWithCustomerIncludingAssessedTax",
    ],
    "GrossProfit": [
        "us-gaap:GrossProfit",
    ],
    "OperatingIncome": [
        "us-gaap:OperatingIncomeLoss",
    ],
    "NetIncome": [
        "us-gaap:NetIncomeLoss",
        "us-gaap:ProfitLoss",
    ],
    "COGS": [
        "us-gaap:CostOfRevenue",
        "us-gaap:CostOfGoodsAndServicesSold",
    ],
    "RnD": [
        "us-gaap:ResearchAndDevelopmentExpense",
    ],
    "SalesMarketing": [
        "us-gaap:SellingAndMarketingExpense",
        "us-gaap:SellingGeneralAndAdministrativeExpense",
    ],
    "GeneralAdmin": [
        "us-gaap:GeneralAndAdministrativeExpense",
    ],
    "TotalOpEx": [
        "us-gaap:OperatingExpenses",
        "us-gaap:CostsAndExpenses",
    ],
}

FORM_TYPES_ANNUAL = {"10-K", "10-K/A"}
FORM_TYPES_QUARTERLY = {"10-Q", "10-Q/A"}


def _ensure_cache_dir():
    os.makedirs(CACHE_DIR, exist_ok=True)


def fetch_company_facts(cik: str, use_cache: bool = True) -> Optional[dict]:
    """Fetch all XBRL facts for a company from SEC EDGAR."""
    _ensure_cache_dir()
    padded_cik = cik.zfill(10)
    cache_file = os.path.join(CACHE_DIR, f"edgar_{padded_cik}.json")

    if use_cache and os.path.exists(cache_file):
        age_hours = (time.time() - os.path.getmtime(cache_file)) / 3600
        if age_hours < 24:
            with open(cache_file, "r") as f:
                return json.load(f)

    url = EDGAR_BASE.format(cik=padded_cik)
    req = urllib.request.Request(url, headers={"User-Agent": USER_AGENT})

    try:
        with urllib.request.urlopen(req, timeout=15) as resp:
            data = json.loads(resp.read().decode("utf-8"))
            with open(cache_file, "w") as f:
                json.dump(data, f)
            return data
    except Exception as e:
        print(f"  [EDGAR] Error fetching CIK {cik}: {e}")
        return None


def _find_concept(facts: dict, concept_key: str) -> Optional[dict]:
    """Look up a concept in the XBRL facts structure."""
    taxonomy, concept = concept_key.split(":", 1)
    tax_key = taxonomy.replace("-", "")
    tax_data = facts.get("facts", {}).get(tax_key, facts.get("facts", {}).get(taxonomy, {}))
    return tax_data.get(concept)


def _extract_annual_value(concept_data: dict) -> list[dict]:
    """Extract annual values from a concept's units."""
    results = []
    units = concept_data.get("units", {})

    for unit_type, entries in units.items():
        for entry in entries:
            form = entry.get("form", "")
            if form not in FORM_TYPES_ANNUAL:
                continue
            fp = entry.get("fp", "")
            if fp != "FY":
                continue
            end_date = entry.get("end", "")
            start_date = entry.get("start", "")

            if not end_date:
                continue
            year = int(end_date[:4])

            # Only keep entries with ~12 month duration for income/expense items
            if start_date:
                from datetime import datetime
                try:
                    d_start = datetime.strptime(start_date, "%Y-%m-%d")
                    d_end = datetime.strptime(end_date, "%Y-%m-%d")
                    days = (d_end - d_start).days
                    if days < 300 or days > 400:
                        continue
                except ValueError:
                    pass

            value = entry.get("val")
            if value is not None:
                results.append({
                    "year": year,
                    "value": value,
                    "end_date": end_date,
                    "form": form,
                    "filed": entry.get("filed", ""),
                    "accn": entry.get("accn", ""),
                })

    # Deduplicate: keep the latest filing per year
    by_year = {}
    for r in results:
        y = r["year"]
        if y not in by_year or r["filed"] > by_year[y]["filed"]:
            by_year[y] = r
    return list(by_year.values())


def extract_metrics_from_facts(facts: dict, company_name: str) -> dict:
    """
    Extract structured financial metrics from XBRL company facts.
    Returns: {year: {metric_name: {value, end_date, source_url}}}
    """
    extracted = {}

    for metric_name, concept_keys in METRIC_CONCEPTS.items():
        for concept_key in concept_keys:
            concept_data = _find_concept(facts, concept_key)
            if not concept_data:
                continue

            annual_values = _extract_annual_value(concept_data)
            for item in annual_values:
                year = item["year"]
                if year not in extracted:
                    extracted[year] = {}
                if metric_name not in extracted[year]:
                    # Convert from raw (typically USD) to millions
                    val_millions = item["value"] / 1_000_000
                    accn = item.get("accn", "").replace("-", "")
                    source_url = f"https://www.sec.gov/Archives/edgar/data/{facts.get('cik', '')}/{accn}" if accn else ""
                    extracted[year][metric_name] = {
                        "value": round(val_millions, 1),
                        "end_date": item["end_date"],
                        "source_url": source_url,
                        "source_description": f"SEC EDGAR XBRL ({concept_key}) - {company_name} 10-K FY{year}",
                    }
            if any(year in extracted and metric_name in extracted[year] for year in extracted):
                break  # Found data with this concept, skip alternatives

    return extracted


def collect_edgar_data(cik: str, company_name: str) -> Optional[dict]:
    """Main entry point: fetch + extract for one company."""
    print(f"  [EDGAR] Collecting data for {company_name} (CIK: {cik})...")
    facts = fetch_company_facts(cik)
    if not facts:
        return None

    metrics = extract_metrics_from_facts(facts, company_name)
    years = sorted(metrics.keys())
    print(f"  [EDGAR] Found data for years: {years}")
    for y in years:
        mnames = list(metrics[y].keys())
        print(f"    FY{y}: {', '.join(mnames)}")
    return metrics
