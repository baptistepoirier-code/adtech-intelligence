"""
Loads hand-curated financial data from curated_data.yaml.
Handles private companies and supplements SEC data with earnings release numbers
(e.g. Adjusted EBITDA, FCF, segment data that isn't in XBRL).
"""

import os
import yaml
from typing import Optional

CURATED_PATH = os.path.join(os.path.dirname(__file__), "curated_data.yaml")


def load_curated_data(path: str = CURATED_PATH) -> list[dict]:
    """Load and return the curated companies list from YAML."""
    with open(path, "r") as f:
        data = yaml.safe_load(f)
    return data.get("companies", [])


def parse_curated_company(company: dict) -> dict:
    """
    Parse a single company entry from curated YAML into a normalised structure.
    Returns:
    {
        "name": str,
        "ticker": str|None,
        "cik": str|None,
        "is_public": bool,
        "data_quality": str,
        "description": str,
        "periods": [
            {
                "fiscal_year": int,
                "period_type": str,
                "period_end_date": str,
                "source_url": str,
                "source_description": str,
                "metrics": {metric_name: {"value": float|None, "is_estimate": bool, "note": str}},
                "segments": [{"name": str, "original_label": str, "revenue": float, "operating_income": float}],
            }
        ]
    }
    """
    result = {
        "name": company["name"],
        "ticker": company.get("ticker"),
        "cik": company.get("cik"),
        "is_public": company.get("is_public", False),
        "data_quality": company.get("data_quality", "low"),
        "description": company.get("description", ""),
        "periods": [],
    }

    for period in company.get("periods", []):
        parsed_period = {
            "fiscal_year": period["fiscal_year"],
            "period_type": period.get("period_type", "annual"),
            "period_end_date": period.get("period_end_date", ""),
            "source_url": period.get("source_url", ""),
            "source_description": period.get("source_description", ""),
            "metrics": {},
            "segments": [],
        }

        for mname, mval in period.get("metrics", {}).items():
            if isinstance(mval, dict):
                parsed_period["metrics"][mname] = {
                    "value": mval.get("value"),
                    "is_estimate": mval.get("is_estimate", False),
                    "note": mval.get("note", ""),
                }
            else:
                parsed_period["metrics"][mname] = {
                    "value": mval,
                    "is_estimate": False,
                    "note": "",
                }

        for seg in period.get("segments", []):
            parsed_period["segments"].append({
                "name": seg.get("name", ""),
                "original_label": seg.get("original_label", ""),
                "revenue": seg.get("revenue"),
                "operating_income": seg.get("operating_income"),
            })

        result["periods"].append(parsed_period)

    return result


def get_all_curated() -> list[dict]:
    """Load and parse all curated companies."""
    raw = load_curated_data()
    return [parse_curated_company(c) for c in raw]
