# 🗞 Ad Tech Content Curator

Your personal AI-powered ad tech intelligence agent. Aggregates content from your favourite blogs, YouTube channels, and podcasts into a single weekly Markdown digest.

## Quick Start

```bash
# 1. Install dependencies
pip install -r requirements.txt

# 2. Run the curator
python curator.py

# 3. Open the generated digest
open output/digest-*.md
```

## What it does

1. **Fetches** recent content from RSS feeds (blogs, YouTube, podcasts)
2. **Organises** everything by source type and recency
3. **Generates** a clean Markdown digest in `output/`
4. **Summarises** (optional) the key themes using an LLM if you add an API key

## Configuration

All sources are configured in `config.yaml`:

- **blogs** — RSS feeds from AdExchanger, Digiday, ExchangeWire, etc.
- **youtube_channels** — Channel IDs or handles
- **podcasts** — RSS feeds for AdExchanger Talks, AdTechGod Pod, Marketecture, etc.
- **people** — Reference list of thought leaders to follow
- **topics_of_interest** — Used for relevance scoring (with LLM)

### Resolve YouTube Channel IDs

Some YouTube channels use handles (e.g. `@Prebidorg`). To resolve them to channel IDs:

```bash
python curator.py --resolve-channels
```

### Enable AI Summaries

Add your API key in `config.yaml`:

```yaml
settings:
  anthropic_api_key: "sk-ant-..."   # or
  openai_api_key: "sk-..."
```

The digest will then include an executive summary highlighting key trends.

## Usage

```bash
# Default: last 7 days
python curator.py

# Custom lookback window
python curator.py --days 3

# Resolve missing YouTube channel IDs
python curator.py --resolve-channels

# Use a different config file
python curator.py --config my-config.yaml
```

## Output

Digests are saved as Markdown files in the `output/` directory:

```
output/
  digest-2026-02-16.md
  digest-2026-02-09.md
  ...
```

## Sources Included

| Type | Sources |
|------|---------|
| 📰 Blogs | AdExchanger, Digiday, ExchangeWire, Marketecture, Mobile Dev Memo, Stratechery |
| 📺 YouTube | The Trade Desk, IAB Tech Lab, Prebid.org, Google Ads Developers, Amazon Ads, AdMonsters |
| 🎧 Podcasts | AdExchanger Talks, AdTechGod Pod, Marketecture, Digiday, MadTech, Pivot, Prof G |

## Roadmap

- [ ] LLM-powered relevance scoring per article
- [ ] Email delivery (daily/weekly)
- [ ] Slack/Discord integration
- [ ] Spotify podcast transcript analysis (via Whisper)
- [ ] LinkedIn content monitoring
- [ ] Web dashboard
