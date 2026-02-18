# Ad Tech Financial Intel Dashboard

A decision-support intelligence tool for ad tech product leaders. Aggregates, normalizes, and visualizes financial data for the key public and private companies in the mobile performance DSP ecosystem.

## Quick Start

```bash
cd adtech-curator

# Full pipeline (fetches SEC EDGAR data — requires internet)
python3 -m financial.run

# Curated data only (no network needed)
python3 -m financial.run --skip-edgar
```

The dashboard is generated at `output/financial-intel-YYYYMMDD.html`. Open it in any browser.

## What It Does

1. **Loads curated financial data** from `financial/curated_data.yaml` — hand-verified numbers from earnings releases, including Adjusted EBITDA, FCF, and segment breakdowns that aren't available in SEC XBRL
2. **Fetches SEC EDGAR XBRL data** for public companies (AppLovin, Unity, Alphabet, Meta, Digital Turbine) via the free Company Facts API
3. **Merges data intelligently** — curated data takes priority; EDGAR fills gaps (e.g., COGS, R&D breakdowns)
4. **Computes derived metrics** — margins (Gross, EBITDA, Operating, Net), YoY growth, OpEx ratios (R&D %, S&M %, G&A %), FCF/EBITDA
5. **Generates a self-contained HTML dashboard** with 8 interactive panels

## Dashboard Panels

| # | Panel | Description |
|---|-------|-------------|
| 1 | Executive Summary | Side-by-side table of latest FY metrics with data quality badges |
| 2 | Revenue Comparison | Horizontal bar chart (log scale) of all companies |
| 3 | Growth Trends | Multi-line YoY revenue growth % across years |
| 4 | Profitability | Grouped bar chart of Gross / EBITDA / Operating / Net margins |
| 5 | P&L Waterfall | Per-company waterfall: Revenue → COGS → Gross Profit → OpEx → OI → NI |
| 6 | Segment Breakdown | Doughnut chart of revenue segments (switchable per company) |
| 7 | OpEx Ratios | Stacked bar chart of R&D / S&M / G&A as % of revenue |
| 8 | Document Trail | Source links for every datapoint (SEC filings, earnings releases) |

## Companies Tracked

**Public (SEC EDGAR + earnings releases):**
- AppLovin (APP) — Performance DSP, MAX mediation, Adjust MMP
- Unity (U) — Game engine, Grow Solutions (ironSource/LevelPlay)
- Alphabet / Google (GOOGL) — Google Ads, YouTube, AdMob
- Meta Platforms (META) — Facebook/Instagram ads
- Digital Turbine (APPS) — On-device media, AdColony, Fyber

**Private (curated estimates, clearly labeled):**
- Moloco — ML cloud DSP
- Liftoff / Vungle — Performance DSP + exchange
- Smadex — Independent mobile DSP
- Adikteev — Retargeting / churn prediction
- Remerge — In-app retargeting DSP
- ironSource (pre-merger) — Now part of Unity

## Project Structure

```
financial/
├── run.py                  # Main entry point
├── schema.py               # SQLite schema definitions
├── database.py             # SQLite read/write layer
├── collector_edgar.py      # SEC EDGAR XBRL API collector
├── collector_curated.py    # YAML curated data loader
├── extractor.py            # Merges EDGAR + curated into DB
├── normalizer.py           # Computes derived metrics
├── dashboard_generator.py  # HTML dashboard generator
├── curated_data.yaml       # Hand-curated financial data
├── .cache/                 # EDGAR API response cache (auto-created)
└── financial_intel.db      # SQLite database (auto-created)
```

## How to Update Data

### Adding a new quarter / year
Edit `financial/curated_data.yaml` and add a new period entry under the relevant company. Re-run the pipeline.

### Adding a new company
Add a new entry in `curated_data.yaml` with the company's financials and source URLs. If public, include the CIK number for automatic EDGAR collection.

## Limitations

- **Private companies**: Show "Not disclosed" unless credible public estimates exist. Estimates are clearly labeled.
- **Adjusted EBITDA**: Not a GAAP concept — must be sourced from earnings releases (curated data), not SEC XBRL.
- **XBRL inconsistencies**: Different companies use different US-GAAP taxonomy concepts for the same metric. The collector tries multiple concept names but may miss edge cases.
- **Segment data**: Only available for companies that report it in earnings releases (not consistently in XBRL). Curated manually.
- **FX conversion**: All values in USD as reported. No currency conversion applied.
- **No real-time updates**: Must re-run the pipeline to refresh data. EDGAR caches responses for 24 hours.
- **SEC rate limits**: EDGAR requires a User-Agent header. Rate limit is 10 req/sec. The collector is well within this.
- **Digital Turbine fiscal year**: Ends March 31 (not December 31). FY2024 = Apr 2023 – Mar 2024.

## Dependencies

- Python 3.9+
- `pyyaml` (already installed for the content curator)
- No other external dependencies — uses only stdlib (`sqlite3`, `urllib`, `json`)

## Compliance

- SEC EDGAR data is accessed via the official public API (`data.sec.gov`)
- API responses are cached locally to minimize requests
- User-Agent header is included as required by SEC
- All data sources are attributed with URLs in the Document Trail panel
