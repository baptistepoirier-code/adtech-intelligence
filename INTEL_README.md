# Ad Tech Intelligence — v2 Architecture

## How it works

```
data/sources.yml          →  Source registry (35+ sources, tiered)
data/taxonomy.yml         →  Topic taxonomy + entity dictionary
config/strategy_profile.yml → Your focus weights (topics, companies)
config/thresholds.yml     →  Score thresholds for signals/noise
                              ↓
scripts/generate_daily_intel.py  →  Pipeline: fetch → normalize → dedupe → classify → score → output
                              ↓
docs/data/items.json      →  All scored items
docs/data/daily_summary.json → Aggregated data for dashboard
docs/curator.html         →  Static dashboard (reads JSON client-side)
```

## Adding a source

Edit `data/sources.yml` and add one entry:

```yaml
  - name: New Source Name
    type: blog          # blog | podcast | youtube | filing | newsletter
    tier: 2             # 1 (gold) to 4 (supplemental)
    credibility_weight: 0.75   # 0.0–1.0
    category: mobile    # finance | regulatory | programmatic | mobile | ctv | fraud | ua | measurement | privacy | general
    tags: [mobile, dsp, ua]
    rss_url: "https://example.com/feed/"
    homepage: "https://example.com"
```

For podcasts, add `spotify_url` for direct Spotify links.
For YouTube, use `channel_id` instead of `rss_url`.

Re-run the pipeline: `python3 scripts/generate_daily_intel.py`

## How scoring works

Each item gets 5 transparent sub-scores (0–100):

| Score | Logic |
|-------|-------|
| **Credibility** | Source tier × credibility_weight. Tier 1 = +20 bonus |
| **Recency** | Exponential decay: 100 × e^(-0.693 × hours / 48). Fresh = high |
| **Novelty** | 100 by default. Penalized if near-duplicate title detected (SequenceMatcher > 0.75) |
| **Relevance** | Topic matches × strategy_profile weights + entity matches × entity weights |
| **Priority** | Weighted sum: 40% relevance + 20% credibility + 20% recency + 20% novelty + hard trigger boosts |

Hard triggers (regex patterns) add flat bonuses: earnings (+20), antitrust (+18), SKAN updates (+15), M&A (+15), product launches (+12).

`is_noise = true` if priority_score ≤ 18 (configurable in `thresholds.yml`).

## Tuning thresholds

Edit `config/thresholds.yml`:

```yaml
key_signal_min: 72    # ↓ Lower = more signals shown
must_read_min: 55     # ↓ Lower = more must-reads
noise_max: 18         # ↑ Higher = more aggressive noise filtering
```

Edit `config/strategy_profile.yml` to change topic/entity weights:

```yaml
topic_weights:
  bidding: 1.5        # ↑ Higher = bidding content ranked higher
  retail_media: 0.5   # ↓ Lower = retail media deprioritized
```

## Running locally

```bash
pip install feedparser pyyaml
python3 scripts/generate_daily_intel.py --days 7
open docs/curator.html
```

## GitHub Actions

The workflow runs daily at 6:30 UTC, regenerates `docs/data/`, and commits. GitHub Pages serves the updated dashboard automatically.

To trigger manually: Actions tab → "Daily Intelligence Update" → "Run workflow".

## New sources added (v2)

| Source | Category | Tier |
|--------|----------|------|
| IAB Tech Lab | Regulatory | 2 |
| Apple Developer News | Privacy | 2 |
| Android Developers Blog | Privacy | 2 |
| Chrome Privacy Sandbox | Privacy | 2 |
| SEC EDGAR (AppLovin, Unity, TTD, DT) | Finance | 2 |
| IAS Blog | Fraud | 2 |
| DoubleVerify Blog | Fraud | 2 |
| Dr. Augustine Fou | Fraud | 2 |
| Adjust Blog | Measurement | 2 |
| The Trade Desk Blog | Programmatic | 3 |
| AdMonsters | Programmatic | 3 |
| Prebid.org Blog | Programmatic | 3 |
| Sub Club (RevenueCat) | Mobile | 3 |
