#!/usr/bin/env python3
"""
Ad Tech Intelligence — Daily Intel Pipeline
=============================================
Fetches, normalizes, deduplicates, classifies, scores, and outputs
items.json + daily_summary.json for the static dashboard.

Usage:
    python3 scripts/generate_daily_intel.py [--days 7] [--output docs/data]
"""

import argparse
import hashlib
import html as html_module
import json
import math
import os
import re
import sys
import time
import urllib.request
from collections import Counter, defaultdict
from datetime import datetime, timedelta, timezone
from difflib import SequenceMatcher

import feedparser
import yaml

ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
sys.path.insert(0, ROOT)

FEED_TIMEOUT = 12
UA = "Mozilla/5.0 (AdTechIntel/2.0)"


# ── Load config ──────────────────────────────────────────────

def load_yaml(path):
    with open(os.path.join(ROOT, path), "r") as f:
        return yaml.safe_load(f)


def load_sources():
    return load_yaml("data/sources.yml")["sources"]


def load_taxonomy():
    return load_yaml("data/taxonomy.yml")


def load_strategy():
    return load_yaml("config/strategy_profile.yml")


def load_thresholds():
    return load_yaml("config/thresholds.yml")


# ── Fetch ────────────────────────────────────────────────────

class _RedirectHandler(urllib.request.HTTPRedirectHandler):
    def http_error_301(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)

    def http_error_307(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)

    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)


def _fetch_raw(url):
    opener = urllib.request.build_opener(_RedirectHandler)
    req = urllib.request.Request(url, headers={
        "User-Agent": UA,
        "Accept": "application/rss+xml, application/xml, text/xml, application/atom+xml, */*",
    })
    with opener.open(req, timeout=FEED_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="ignore")


def _clean_html(text):
    text = re.sub(r"<[^>]+>", " ", text)
    text = re.sub(r"\s+", " ", text).strip()
    return text[:500]


def _parse_date(entry):
    for field in ("published_parsed", "updated_parsed"):
        t = entry.get(field)
        if t:
            try:
                return datetime(*t[:6], tzinfo=timezone.utc)
            except Exception:
                pass
    return None


def fetch_rss_source(source, days_lookback=7, max_items=5):
    """Fetch items from a single RSS source."""
    rss_url = source.get("rss_url", "")
    if not rss_url:
        return []

    try:
        raw = _fetch_raw(rss_url)
        feed = feedparser.parse(raw)
    except Exception as e:
        print(f"  [!] {source['name']}: {e}")
        return []

    if feed.bozo and not feed.entries:
        print(f"  [!] {source['name']}: parse error")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_lookback)
    items = []

    for entry in feed.entries:
        pub = _parse_date(entry)
        if pub and pub < cutoff:
            continue

        title = entry.get("title", "").strip()
        if not title:
            continue

        link = entry.get("link", "")
        summary = _clean_html(entry.get("summary", entry.get("description", "")))

        # Spotify override for podcasts
        spotify = source.get("spotify_url", "")
        if spotify and source.get("type") == "podcast":
            if not link or "megaphone" in link or "art19" in link:
                link = spotify

        items.append({
            "title": title,
            "url": link,
            "source": source["name"],
            "source_type": source.get("type", "blog"),
            "source_tier": source.get("tier", 3),
            "source_category": source.get("category", "general"),
            "source_tags": source.get("tags", []),
            "credibility_weight": source.get("credibility_weight", 0.5),
            "published_at": pub.isoformat() if pub else None,
            "published_dt": pub,
            "summary": summary,
            "spotify_url": spotify,
        })

        if len(items) >= max_items:
            break

    return items


def fetch_edgar_source(source, days_lookback=30, max_items=3):
    """Fetch recent filings from SEC EDGAR EFTS API."""
    cik = source.get("edgar_cik", "").lstrip("0")
    if not cik:
        return []
    url = f"https://efts.sec.gov/LATEST/search-index?q=*&dateRange=custom&forms=10-K,10-Q,8-K&startdt=2025-01-01&enddt=2026-12-31"
    try:
        req = urllib.request.Request(url, headers={
            "User-Agent": "AdTechIntel research@example.com",
            "Accept": "application/json",
        })
        with urllib.request.urlopen(req, timeout=FEED_TIMEOUT) as resp:
            data = json.loads(resp.read().decode("utf-8", errors="ignore"))
    except Exception as e:
        print(f" [!] EDGAR {source['name']}: {e}", end="")
        return []

    items = []
    for hit in (data.get("hits", {}).get("hits", []))[:max_items]:
        src = hit.get("_source", {})
        title = src.get("file_description", src.get("display_names", [""])[0])
        filed = src.get("file_date", "")
        form = src.get("form_type", "")
        accession = src.get("file_num", "")

        items.append({
            "title": f"{source['name'].replace('SEC EDGAR ', '').strip('()')}: {form} — {title}" if title else f"{source['name']}: {form} filing",
            "url": source.get("homepage", ""),
            "source": source["name"],
            "source_type": "filing",
            "source_tier": source.get("tier", 2),
            "source_category": "finance",
            "source_tags": source.get("tags", []),
            "credibility_weight": source.get("credibility_weight", 0.98),
            "published_at": f"{filed}T00:00:00+00:00" if filed else None,
            "published_dt": datetime.strptime(filed, "%Y-%m-%d").replace(tzinfo=timezone.utc) if filed else None,
            "summary": f"SEC {form} filing for {source['name'].replace('SEC EDGAR ', '').strip('()')}. {title}",
            "spotify_url": "",
        })

    return items


def fetch_youtube_source(source, days_lookback=7, max_items=5):
    """Fetch items from a YouTube channel — tries RSS first, falls back to page scraping."""
    cid = source.get("channel_id", "")
    if not cid:
        return []
    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={cid}"
    yt_source = {**source, "rss_url": rss_url}
    items = fetch_rss_source(yt_source, days_lookback, max_items)
    if items:
        for it in items:
            it["source_type"] = "youtube"
        return items

    # Fallback: scrape the channel /videos page
    handle = source.get("homepage", "").rstrip("/").split("/")[-1]
    if not handle.startswith("@"):
        handle = f"@{handle.replace('https://youtube.com/', '').replace('https://www.youtube.com/', '')}"
    page_url = f"https://www.youtube.com/{handle}/videos"
    try:
        yt_headers = {
            "User-Agent": "Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36",
            "Accept-Language": "en-US,en;q=0.9",
            "Cookie": "CONSENT=YES+; SOCS=CAISNQgDEitib3FfaWRlbnRpdHlmcm9udGVuZHVpc2VydmVyXzIwMjMwODE1LjA3X3AxGgJlbiADGgYIgJnPpwY",
        }
        req = urllib.request.Request(page_url, headers=yt_headers)
        with urllib.request.urlopen(req, timeout=12) as r:
            page_html = r.read().decode("utf-8", errors="replace")

        m = re.search(r'var ytInitialData = ({.*?});</script>', page_html, re.DOTALL)
        if not m:
            m = re.search(r'ytInitialData\s*=\s*({.*?});</script>', page_html, re.DOTALL)
        if not m:
            return []

        raw_json = m.group(1)
        video_matches = re.findall(
            r'"videoId":"([^"]+)".*?"text":"([^"]{10,})"',
            raw_json
        )
        seen = set()
        scraped = []
        for vid, title in video_matches:
            if vid in seen or len(scraped) >= max_items:
                continue
            seen.add(vid)
            scraped.append({
                "title": title,
                "url": f"https://www.youtube.com/watch?v={vid}",
                "published_at": datetime.now(timezone.utc).isoformat(),
                "summary": f"YouTube video from {source['name']}.",
                "source": source["name"],
                "source_type": "youtube",
                "source_tier": source.get("tier", 3),
                "source_category": source.get("category", "general"),
                "source_tags": source.get("tags", []),
                "credibility_weight": source.get("credibility_weight", 0.5),
            })
        return scraped
    except Exception as e:
        print(f" [!] {source['name']}: YT scrape failed: {e}")
        return []


def fetch_wp_api_source(source, days_lookback=7, max_items=10):
    """Fetch posts from a WordPress REST API when RSS is dead."""
    homepage = source.get("homepage", "").rstrip("/")
    if not homepage:
        return []
    api_url = f"{homepage}/wp-json/wp/v2/posts?per_page={max_items}&_fields=id,title,link,date,excerpt"
    try:
        raw = _fetch_raw(api_url)
        if not raw:
            return []
        posts = json.loads(raw)
        if not isinstance(posts, list):
            return []
    except Exception as e:
        print(f"  [!] {source['name']}: WP API error: {e}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_lookback)
    items = []
    for p in posts:
        try:
            pub = datetime.fromisoformat(p["date"].replace("Z", "+00:00"))
            if pub.tzinfo is None:
                pub = pub.replace(tzinfo=timezone.utc)
        except Exception:
            pub = datetime.now(timezone.utc)
        if pub < cutoff:
            continue
        title = html_module.unescape(p.get("title", {}).get("rendered", "")).strip()
        excerpt = html_module.unescape(p.get("excerpt", {}).get("rendered", "")).strip()
        excerpt = re.sub(r"<[^>]+>", "", excerpt).strip()[:500]
        items.append({
            "title": title,
            "url": p.get("link", ""),
            "published_at": pub.isoformat(),
            "summary": excerpt,
            "source": source["name"],
            "source_type": source.get("type", "blog"),
            "source_tier": source.get("tier", 3),
            "source_category": source.get("category", "general"),
            "source_tags": source.get("tags", []),
            "credibility_weight": source.get("credibility_weight", 0.5),
        })
    return items


def fetch_scrape_source(source, days_lookback=7, max_items=5):
    """Scrape blog pages for article links when no RSS/API exists."""
    homepage = source.get("homepage", "").rstrip("/")
    pattern = source.get("scrape_pattern", "blog")
    blog_url = f"{homepage}/{pattern}" if not homepage.endswith(f"/{pattern}") else homepage

    try:
        raw = _fetch_raw(blog_url)
        if not raw:
            return []
    except Exception as e:
        print(f"  [!] {source['name']}: scrape error: {e}")
        return []

    links = re.findall(rf'href="(/{pattern}/([a-z0-9][a-z0-9-]+))"', raw)
    unique_slugs = list(dict.fromkeys([l[0] for l in links]))[:max_items]

    items = []
    for slug in unique_slugs:
        full_url = f"{homepage}{slug}"
        try:
            page_raw = _fetch_raw(full_url)
            if not page_raw:
                continue
            m = re.search(r'<title>([^<]+)</title>', page_raw)
            title = m.group(1).strip() if m else slug.split("/")[-1].replace("-", " ").title()
            title = re.sub(r'\s*[|–-]\s*.*$', '', title).strip()

            m_desc = re.search(r'<meta[^>]*name="description"[^>]*content="([^"]+)"', page_raw)
            summary = m_desc.group(1).strip()[:500] if m_desc else ""
        except Exception:
            title = slug.split("/")[-1].replace("-", " ").title()
            summary = ""

        items.append({
            "title": title,
            "url": full_url,
            "published_at": datetime.now(timezone.utc).isoformat(),
            "summary": summary,
            "source": source["name"],
            "source_type": source.get("type", "blog"),
            "source_tier": source.get("tier", 3),
            "source_category": source.get("category", "general"),
            "source_tags": source.get("tags", []),
            "credibility_weight": source.get("credibility_weight", 0.5),
        })
    return items


def fetch_all(sources, days_lookback=7):
    """Fetch from all sources."""
    all_items = []
    disabled_count = 0
    for src in sources:
        if src.get("disabled"):
            disabled_count += 1
            continue

        stype = src.get("type", "blog")
        name = src["name"]
        print(f"  → {name}...", end="", flush=True)

        if stype == "youtube":
            items = fetch_youtube_source(src, days_lookback)
        elif src.get("use_edgar_rss"):
            items = fetch_edgar_source(src, days_lookback)
        elif src.get("use_wp_api"):
            items = fetch_wp_api_source(src, days_lookback)
        elif src.get("use_scrape"):
            items = fetch_scrape_source(src, days_lookback)
        else:
            items = fetch_rss_source(src, days_lookback)

        print(f" {len(items)} items")
        all_items.extend(items)
        time.sleep(0.3)

    if disabled_count:
        print(f"  ({disabled_count} sources disabled — no RSS/API)")
    return all_items


# ── Normalize ────────────────────────────────────────────────

def stable_id(title, url):
    raw = f"{title.lower().strip()}|{url.lower().strip()}"
    return hashlib.sha256(raw.encode()).hexdigest()[:16]


def normalize_item(item):
    """Normalize to canonical schema."""
    return {
        "id": stable_id(item["title"], item.get("url", "")),
        "title": item["title"],
        "url": item.get("url", ""),
        "source": item["source"],
        "source_type": item.get("source_type", "blog"),
        "source_tier": item.get("source_tier", 3),
        "source_category": item.get("source_category", "general"),
        "credibility_weight": item.get("credibility_weight", 0.5),
        "published_at": item.get("published_at"),
        "type": item.get("source_type", "blog"),
        "tags": item.get("source_tags", []),
        "topics": [],
        "entities": [],
        "summary": item.get("summary", ""),
        "why_it_matters": "",
        "recommended_action": "",
        "signal_type": "",
        "credibility_score": 0,
        "recency_score": 0,
        "novelty_score": 100,
        "relevance_score": 0,
        "priority_score": 0,
        "is_noise": False,
        "confidence": "medium",
        "spotify_url": item.get("spotify_url", ""),
        "business_tags": [],
        "is_hsi": False,
    }


# ── Deduplicate ──────────────────────────────────────────────

def _title_similarity(a, b):
    a_clean = re.sub(r"[^a-z0-9 ]", "", a.lower())
    b_clean = re.sub(r"[^a-z0-9 ]", "", b.lower())
    return SequenceMatcher(None, a_clean, b_clean).ratio()


def deduplicate(items, threshold=0.75):
    """Remove duplicates by URL and near-duplicate title similarity."""
    seen_urls = set()
    seen_titles = []
    unique = []

    for item in items:
        url = item["url"].split("?")[0].rstrip("/").lower()
        if url and url in seen_urls:
            continue

        is_dup = False
        for prev_title in seen_titles:
            if _title_similarity(item["title"], prev_title) > threshold:
                is_dup = True
                break

        if is_dup:
            continue

        if url:
            seen_urls.add(url)
        seen_titles.append(item["title"])
        unique.append(item)

    removed = len(items) - len(unique)
    if removed:
        print(f"  Deduplicated: {removed} items removed")
    return unique


# ── Classify ─────────────────────────────────────────────────

def classify_topics(item, taxonomy):
    """Match item against taxonomy topics."""
    text = f"{item['title']} {item['summary']}".lower()
    matched = []

    for topic_key, topic in taxonomy.get("topics", {}).items():
        for kw in topic.get("keywords", []):
            if kw.lower() in text:
                matched.append({
                    "key": topic_key,
                    "label": topic["label"],
                    "signal_type": topic.get("signal_type", ""),
                    "weight": topic.get("weight", 0.5),
                })
                break

    item["topics"] = matched
    if matched:
        # Use the highest-weight topic's signal type
        best = max(matched, key=lambda t: t["weight"])
        item["signal_type"] = best["signal_type"]

    return item


def extract_entities(item, taxonomy):
    """Extract mentioned entities from text."""
    text = f"{item['title']} {item['summary']}".lower()
    matched = []

    for entity in taxonomy.get("entities", {}).get("companies", []):
        for alias in entity.get("aliases", []):
            if alias.lower() in text:
                matched.append({
                    "name": entity["name"],
                    "type": entity.get("type", "unknown"),
                    "watchlist": entity.get("watchlist", False),
                })
                break

    item["entities"] = matched
    return item


# ── Score ────────────────────────────────────────────────────

def score_credibility(item):
    """Score 0–100 based on source tier and credibility weight."""
    weight = item.get("credibility_weight", 0.5)
    tier = item.get("source_tier", 3)
    tier_bonus = {1: 20, 2: 10, 3: 0, 4: -10}.get(tier, 0)
    return min(100, max(0, int(weight * 80 + tier_bonus)))


def score_recency(item, half_life_hours=48):
    """Exponential decay score based on age."""
    pub = item.get("published_at")
    if not pub:
        return 30
    try:
        pub_dt = datetime.fromisoformat(pub)
        age_hours = (datetime.now(timezone.utc) - pub_dt).total_seconds() / 3600
        score = 100 * math.exp(-0.693 * age_hours / half_life_hours)
        return min(100, max(0, int(score)))
    except Exception:
        return 30


def score_relevance(item, strategy):
    """Score based on topic/entity match with strategy profile."""
    topic_weights = strategy.get("topic_weights", {})
    entity_weights = strategy.get("entity_weights", {})
    type_weights = strategy.get("content_type_weights", {})

    score = 0.0

    for topic in item.get("topics", []):
        key = topic["key"]
        base = topic["weight"] * 25
        multiplier = topic_weights.get(key, 1.0)
        score += base * multiplier

    for entity in item.get("entities", []):
        name = entity["name"]
        multiplier = entity_weights.get(name, 1.0)
        score += 8 * multiplier

    type_mult = type_weights.get(item.get("type", "blog"), 1.0)
    score *= type_mult

    return min(100, max(0, int(score)))


HSI_PATTERNS = [
    r"\bearnings\b.*\b(report|call|beat|miss|guidance|results)\b",
    r"\b(10-k|10-q|8-k)\b",
    r"\b(quarterly results|annual report|revenue guidance)\b",
    r"\b(antitrust|doj\b|divestiture|eu commission|enforcement action)",
    r"\b(dma\s+(?:fine|ruling|compliance|violation|designated))",
    r"\b(ftc\s+(?:sue|fine|block|order|ruling|settle))",
    r"\b(skan\s?[5-9]|skan\s+update|att\s+change|idfa\s+deprecat)",
    r"\b(privacy sandbox\s+(?:launch|deprecat|delay|update|change))",
    r"\b(protected audience\s+(?:api|launch|update))",
    r"\b(acquir(?:es|ed)|merger\b|(?:goes|went)\s+public|\bipo\b)",
]

HSI_EXCLUDED_TYPES = {"podcast", "youtube"}

def compute_hsi(item):
    """HSI = truly structural events only. Must match a specific pattern in text.
    Podcasts/YouTube are excluded unless they explicitly discuss platform policy,
    regulation/enforcement, earnings guidance, major M&A, or measurement shifts."""
    text = f"{item['title']} {item['summary']}".lower()

    if item.get("type") == "filing":
        return True

    matched = False
    for pat in HSI_PATTERNS:
        if re.search(pat, text):
            matched = True
            break

    if not matched:
        return False

    if item.get("type") in HSI_EXCLUDED_TYPES or item.get("source_type") in HSI_EXCLUDED_TYPES:
        platform_terms = r"\b(google|meta|apple|amazon|tiktok|unity|applovin|the trade desk|dsp|ssp|exchange|platform policy|ad market|programmatic)\b"
        if not re.search(platform_terms, text):
            return False

    return True


def score_priority(item, strategy):
    """Composite priority with hard triggers and tier weighting."""
    cred = item.get("credibility_score", 0)
    recency = item.get("recency_score", 0)
    novelty = item.get("novelty_score", 100)
    relevance = item.get("relevance_score", 0)

    base = (relevance * 0.40 + cred * 0.20 + recency * 0.20 + novelty * 0.20)

    # Tier bonus: tier 1 gets a boost, tier 3+ gets a penalty
    tier = item.get("source_tier", 3)
    tier_boost = {1: 8, 2: 3, 3: 0, 4: -5}.get(tier, 0)
    base += tier_boost

    # Hard triggers
    text = f"{item['title']} {item['summary']}".lower()
    for trigger in strategy.get("hard_triggers", []):
        pattern = trigger.get("pattern", "")
        if re.search(pattern, text):
            base += trigger.get("boost", 0)
            if not item.get("signal_type"):
                item["signal_type"] = trigger.get("signal", "")

    # HSI bonus
    is_hsi = compute_hsi(item)
    item["is_hsi"] = is_hsi
    if is_hsi:
        base += 6

    return min(100, max(0, int(base)))


def compute_all_scores(items, strategy, thresholds):
    """Run the full scoring pipeline."""
    half_life = thresholds.get("recency_half_life_hours", 48)
    noise_max = thresholds.get("noise_max", 18)

    for item in items:
        item["credibility_score"] = score_credibility(item)
        item["recency_score"] = score_recency(item, half_life)
        item["relevance_score"] = score_relevance(item, strategy)
        item["priority_score"] = score_priority(item, strategy)
        item["is_noise"] = item["priority_score"] <= noise_max

        # Confidence heuristic
        n_topics = len(item.get("topics", []))
        n_entities = len(item.get("entities", []))
        if n_topics >= 2 and n_entities >= 1 and item["credibility_score"] >= 60:
            item["confidence"] = "high"
        elif n_topics >= 1 or item["credibility_score"] >= 50:
            item["confidence"] = "medium"
        else:
            item["confidence"] = "low"

    items.sort(key=lambda x: x["priority_score"], reverse=True)

    # Source capping: no single source can have more than max_per_source items in top positions
    max_per_source = thresholds.get("max_per_source", 5)
    source_counts_cap = Counter()
    capped = []
    overflow = []
    for item in items:
        src = item["source"]
        if source_counts_cap[src] < max_per_source:
            capped.append(item)
            source_counts_cap[src] += 1
        else:
            overflow.append(item)
    items = capped + overflow

    return items


# ── Templates ────────────────────────────────────────────────

WHY_TEMPLATES = {
    "bidding": [
        "Auction mechanics directly impact your DSP's win rates and CPI. Changes here affect your core revenue engine.",
        "Bid optimization is the #1 lever for DSP profitability. This signal could shift your bidding strategy.",
    ],
    "skan_att": [
        "SKAN/ATT defines what your DSP can measure on iOS. Every change here impacts your conversion models.",
        "iOS privacy changes reshape the entire mobile UA funnel. This directly affects campaign optimization.",
    ],
    "privacy_sandbox": [
        "Privacy Sandbox will reshape targeting on Android — your DSP's second-largest platform.",
        "Chrome/Android privacy changes determine the future of cross-platform attribution and targeting.",
    ],
    "ua_growth": [
        "User acquisition economics are shifting. This affects how advertisers allocate budgets across DSPs.",
        "Mobile growth strategies directly impact demand for your DSP. Budget shifts here are leading indicators.",
    ],
    "ml_ai": [
        "ML capability is the primary differentiator between winning and losing DSPs in 2025.",
        "AI-driven ad optimization is redefining performance — staying current here is existential for DSP builders.",
    ],
    "measurement": [
        "Attribution methodology determines which DSP gets credit — and budget. This is core to your value prop.",
        "Measurement shifts change how advertisers evaluate DSP performance. Your reporting strategy may need updating.",
    ],
    "mediation": [
        "Mediation controls supply access and data flow. Changes here affect your DSP's bid landscape.",
        "The mediation layer sits between your DSP and supply. Shifts here impact fill rates and data access.",
    ],
    "ctv": [
        "CTV is the next scale opportunity for performance DSPs. Early positioning matters.",
        "Connected TV supply is opening to programmatic — a potential new channel for your exchange.",
    ],
    "creative": [
        "Creative performance is increasingly ML-driven. This intersects with your DSP's optimization layer.",
        "Ad format innovation affects fill rates and eCPMs across your exchange.",
    ],
    "fraud": [
        "Supply quality directly affects advertiser trust in your exchange. Fraud signals require immediate attention.",
        "Invalid traffic erodes advertiser confidence. This impacts your DSP's reputation and retention.",
    ],
    "regulatory": [
        "Regulatory actions can restructure the competitive landscape overnight. Must-monitor for strategic planning.",
        "Policy and regulation reshape which data you can use and how your DSP operates. High business impact.",
    ],
    "retail_media": [
        "Retail media is pulling budget from open programmatic. Monitor for demand-side impact on your DSP.",
        "Commerce media growth may redirect UA budgets. Watch for impact on your demand pipeline.",
    ],
    "identity": [
        "Identity infrastructure determines targeting capability post-cookie. Your DSP's reach depends on this.",
        "Addressability is eroding. How your DSP handles identity will determine win rates in the new paradigm.",
    ],
    "earnings": [
        "Financial results reveal competitors' strategic bets and resource allocation. Essential competitive intel.",
        "Earnings data exposes margin structure and investment priorities of key players in your market.",
    ],
    "macro": [
        "Macro ad spend trends determine the size of the pie your DSP competes for. Shifts here impact pipeline.",
        "Economic indicators are leading signals for ad budget decisions. Budget contractions hit performance channels first.",
    ],
    "ma_funding": [
        "M&A activity reshapes competitive dynamics. Consolidation reduces competition; funding signals new entrants.",
        "Funding and acquisitions reveal where capital sees value in ad tech. This affects your competitive positioning.",
    ],
    "hiring": [
        "Hiring signals reveal where competitors are investing. ML/privacy hires indicate strategic direction.",
        "Talent movement between ad tech companies often precedes product pivots. Track carefully.",
    ],
    "mobile_gaming": [
        "Mobile gaming drives the largest share of in-app ad inventory. Monetization shifts here directly affect your exchange supply.",
        "Gaming monetization trends determine ad format demand and eCPM benchmarks across your supply stack.",
    ],
}

ACTION_TEMPLATES = {
    "bidding": "Review your bidding algorithms and auction participation strategy. Assess impact on win rates.",
    "skan_att": "Check your SKAN integration. Update conversion value schemas if Apple changed the spec.",
    "privacy_sandbox": "Brief your engineering team. Evaluate timeline impact on your targeting and measurement stack.",
    "ua_growth": "Share with your demand team. Adjust positioning to capture shifting advertiser budgets.",
    "ml_ai": "Evaluate against your ML roadmap. Identify capability gaps vs. competitors.",
    "measurement": "Review your attribution reporting. Ensure your methodology stays competitive.",
    "mediation": "Assess impact on your supply partnerships and bid request volume.",
    "ctv": "Evaluate CTV supply integration opportunity. Size the addressable market for your DSP.",
    "creative": "Share with creative ops. Assess whether your ad serving supports emerging formats.",
    "fraud": "Audit your supply quality filters. Proactively communicate quality standards to advertisers.",
    "regulatory": "Brief leadership and legal. Model scenario impact on your product roadmap.",
    "retail_media": "Monitor demand reallocation. Adjust growth forecasts if budgets shift away from open programmatic.",
    "identity": "Assess your identity strategy. Ensure your DSP can operate in reduced-signal environments.",
    "earnings": "Update your competitive analysis. Extract implications for your pricing and go-to-market.",
    "macro": "Factor into quarterly planning. Adjust growth forecasts and budget assumptions.",
    "ma_funding": "Brief leadership. Assess whether the deal changes your competitive landscape or partnership strategy.",
    "hiring": "Track the hiring pattern. Map which companies are building which capabilities ahead of your roadmap.",
    "mobile_gaming": "Share with supply and publishing teams. Assess impact on ad inventory quality and format adoption.",
}

ENTITY_WHY = {
    "AppLovin": "AppLovin is your primary competitor. Every move they make reshapes the performance DSP landscape.",
    "Unity": "Unity controls a major mediation stack (LevelPlay) and game engine. Their strategy directly impacts supply dynamics.",
    "Moloco": "Moloco is the fastest-growing independent DSP. Their ML-first approach is the benchmark you're measured against.",
    "Google": "Google controls Android, AdMob, and the largest share of ad budgets. Platform policy changes here are existential.",
    "Meta": "Meta is the #1 destination for mobile UA spend. Advantage+ automation is reducing the need for external DSPs.",
    "Apple": "Apple controls iOS privacy policy. ATT/SKAN updates directly determine what your DSP can optimize for.",
}


def tag_business_units(item, strategy):
    """Tag item with relevant internal business units."""
    bus = strategy.get("business_units", [])
    if not bus:
        return item

    text = f"{item['title']} {item['summary']}".lower()
    topic_keys = {t["key"] for t in item.get("topics", [])}
    matched = []

    for bu in bus:
        hit = False
        # Check topic overlap
        for mt in bu.get("match_topics", []):
            if mt in topic_keys:
                hit = True
                break
        # Check keyword matches
        if not hit:
            for kw in bu.get("match_keywords", []):
                if kw.lower() in text:
                    hit = True
                    break
        if hit:
            matched.append({
                "tag": bu["tag"],
                "color": bu.get("color", "#6b7280"),
                "url": bu.get("url", ""),
            })

    item["business_tags"] = matched
    return item


def generate_insights(item):
    """Generate unique why_it_matters and recommended_action per item."""
    topics = item.get("topics", [])
    entities = item.get("entities", [])

    # Entity-specific insight takes priority for watchlist companies
    for ent in entities:
        if ent["name"] in ENTITY_WHY and ent.get("watchlist"):
            item["why_it_matters"] = ENTITY_WHY[ent["name"]]
            item["recommended_action"] = f"Track {ent['name']} closely. Update your competitive positioning and roadmap."
            return item

    # Topic-based insight
    if topics:
        primary = max(topics, key=lambda t: t["weight"])
        key = primary["key"]
        templates = WHY_TEMPLATES.get(key, ["This signal is relevant to your ad tech strategy."])
        idx = hash(item["id"]) % len(templates)
        item["why_it_matters"] = templates[idx]
        item["recommended_action"] = ACTION_TEMPLATES.get(key, "Review and assess relevance to your roadmap.")
    else:
        item["why_it_matters"] = "General industry signal. May contain relevant insights for DSP operators."
        item["recommended_action"] = "Skim for relevant takeaways. Flag if it touches your product area."

    return item


# ── Summary generation ───────────────────────────────────────

def build_daily_summary(items, thresholds):
    """Build aggregated summary for dashboard tiles and sections."""
    now = datetime.now(timezone.utc)
    active = [i for i in items if not i["is_noise"]]
    noise = [i for i in items if i["is_noise"]]

    key_signal_min = thresholds.get("key_signal_min", 72)
    must_read_min = thresholds.get("must_read_min", 55)

    # Key signals (highest priority)
    key_signals = [i for i in active if i["priority_score"] >= key_signal_min][:thresholds.get("max_key_signals", 5)]
    used_ids = {i["id"] for i in key_signals}

    # Must-reads: exclude items already in key_signals
    must_reads = []
    for i in active:
        if i["id"] in used_ids:
            continue
        if i["priority_score"] >= must_read_min:
            must_reads.append(i)
            used_ids.add(i["id"])
        if len(must_reads) >= thresholds.get("max_must_reads", 7):
            break

    # Key learnings: exclude items already in key_signals or must_reads, diversify by topic
    seen_topics_set = set()
    learnings = []
    for item in active:
        if item["id"] in used_ids:
            continue
        if len(learnings) >= thresholds.get("max_key_learnings", 10):
            break
        topic_keys = {t["key"] for t in item.get("topics", [])}
        if topic_keys & seen_topics_set and len(learnings) > 2:
            continue
        seen_topics_set |= topic_keys
        learnings.append({
            "title": item["title"],
            "url": item["url"],
            "source": item["source"],
            "source_type": item.get("type", "blog"),
            "signal_type": item.get("signal_type", ""),
            "why_it_matters": item.get("why_it_matters", ""),
            "priority_score": item["priority_score"],
            "spotify_url": item.get("spotify_url", ""),
            "business_tags": item.get("business_tags", []),
            "is_hsi": item.get("is_hsi", False),
        })
        used_ids.add(item["id"])

    # YouTube section: all youtube items not already used
    youtube_items = [i for i in active if i.get("type") == "youtube" and i["id"] not in used_ids]

    # Podcast section: all podcast items not already used
    podcast_items = [i for i in active if i.get("type") == "podcast" and i["id"] not in used_ids]

    # Topic momentum (count weighted by priority)
    topic_counts = Counter()
    topic_momentum = Counter()
    for item in active:
        for t in item.get("topics", []):
            topic_counts[t["label"]] += 1
            topic_momentum[t["label"]] += item["priority_score"]

    # Source distribution
    source_counts = Counter()
    for item in active:
        source_counts[item["source"]] += 1

    # Watchlist
    watchlist = defaultdict(lambda: {"count": 0, "top_signal": None, "max_priority": 0})
    for item in active:
        for ent in item.get("entities", []):
            if ent.get("watchlist"):
                name = ent["name"]
                watchlist[name]["count"] += 1
                if item["priority_score"] > watchlist[name]["max_priority"]:
                    watchlist[name]["max_priority"] = item["priority_score"]
                    watchlist[name]["top_signal"] = {
                        "title": item["title"],
                        "url": item["url"],
                        "priority_score": item["priority_score"],
                        "signal_type": item.get("signal_type", ""),
                    }

    # Category distribution
    cat_counts = Counter()
    for item in active:
        cat_counts[item.get("source_category", "general")] += 1

    scores = [i["priority_score"] for i in active]
    avg_score = round(sum(scores) / len(scores), 1) if scores else 0
    hsi_count = sum(1 for i in active if i.get("is_hsi"))

    return {
        "generated_at": now.isoformat(),
        "tiles": {
            "total_items": len(items),
            "active_items": len(active),
            "noise_filtered": len(noise),
            "avg_priority": avg_score,
            "high_priority": len([s for s in scores if s >= key_signal_min]),
            "sources_active": len(source_counts),
            "hsi_count": hsi_count,
            "duplicates_removed": 0,
        },
        "key_signals": key_signals,
        "must_reads": must_reads,
        "key_learnings": learnings,
        "youtube_items": youtube_items,
        "podcast_items": podcast_items,
        "topic_momentum": [{"label": k, "score": v, "count": topic_counts[k]}
                           for k, v in topic_momentum.most_common(12)],
        "source_distribution": [{"name": k, "count": v}
                                for k, v in source_counts.most_common(20)],
        "watchlist": {k: v for k, v in sorted(watchlist.items(), key=lambda x: -x[1]["count"])},
        "category_distribution": [{"name": k, "count": v}
                                   for k, v in cat_counts.most_common(20)],
    }


# ── Main pipeline ────────────────────────────────────────────

def main():
    parser = argparse.ArgumentParser(description="Ad Tech Intelligence Pipeline")
    parser.add_argument("--days", type=int, default=7, help="Days lookback for feeds")
    parser.add_argument("--output", default=os.path.join(ROOT, "docs", "data"), help="Output directory")
    args = parser.parse_args()

    print("=" * 60)
    print("  Ad Tech Intelligence — Daily Pipeline v2")
    print("=" * 60)

    # Load config
    sources = load_sources()
    taxonomy = load_taxonomy()
    strategy = load_strategy()
    thresholds = load_thresholds()

    # 1. Fetch
    print(f"\n[1/6] Fetching from {len(sources)} sources...")
    raw_items = fetch_all(sources, args.days)
    print(f"  Total: {len(raw_items)} raw items")

    # 2. Normalize
    print("\n[2/6] Normalizing...")
    items = [normalize_item(i) for i in raw_items]

    # 3. Dedupe
    print("\n[3/6] Deduplicating...")
    before = len(items)
    items = deduplicate(items, thresholds.get("dedupe_similarity", 0.75))
    dupes_removed = before - len(items)

    # 4. Classify
    print("\n[4/6] Classifying topics & entities...")
    for item in items:
        classify_topics(item, taxonomy)
        extract_entities(item, taxonomy)

    topics_found = sum(1 for i in items if i["topics"])
    entities_found = sum(1 for i in items if i["entities"])
    print(f"  {topics_found}/{len(items)} items matched topics")
    print(f"  {entities_found}/{len(items)} items have entity mentions")

    # 5. Score & generate insights
    print("\n[5/6] Scoring & generating insights...")
    items = compute_all_scores(items, strategy, thresholds)
    for item in items:
        generate_insights(item)
        tag_business_units(item, strategy)

    tagged = sum(1 for i in items if i.get("business_tags"))
    print(f"  {tagged}/{len(items)} items tagged with business units")

    active = [i for i in items if not i["is_noise"]]
    noise = [i for i in items if i["is_noise"]]
    print(f"  {len(active)} active items, {len(noise)} noise filtered")
    if active:
        print(f"  Top score: {active[0]['priority_score']} — {active[0]['title'][:60]}")

    # 6. Output
    print("\n[6/6] Writing output...")
    os.makedirs(args.output, exist_ok=True)

    # Clean items for JSON (remove non-serializable fields)
    for item in items:
        item.pop("published_dt", None)

    summary = build_daily_summary(items, thresholds)
    summary["tiles"]["duplicates_removed"] = dupes_removed

    items_path = os.path.join(args.output, "items.json")
    summary_path = os.path.join(args.output, "daily_summary.json")
    archive_path = os.path.join(args.output, "archive.json")

    with open(items_path, "w") as f:
        json.dump(items, f, indent=2, default=str)
    with open(summary_path, "w") as f:
        json.dump(summary, f, indent=2, default=str)

    # Archive: persist the best articles across runs
    archive_min_score = thresholds.get("archive_min_score", 75)
    archive_max_items = thresholds.get("archive_max_items", 300)
    new_stars = [i for i in active if i["priority_score"] >= archive_min_score]

    existing_archive = []
    if os.path.exists(archive_path):
        try:
            with open(archive_path, "r") as f:
                existing_archive = json.load(f)
        except Exception:
            existing_archive = []

    existing_ids = {a["id"] for a in existing_archive}
    added = 0
    for item in new_stars:
        if item["id"] not in existing_ids:
            existing_archive.append({
                "id": item["id"],
                "title": item["title"],
                "url": item["url"],
                "source": item["source"],
                "source_type": item.get("type", "blog"),
                "source_category": item.get("source_category", ""),
                "source_tier": item.get("source_tier", 3),
                "published_at": item.get("published_at"),
                "archived_at": datetime.now(timezone.utc).isoformat(),
                "priority_score": item["priority_score"],
                "signal_type": item.get("signal_type", ""),
                "why_it_matters": item.get("why_it_matters", ""),
                "topics": item.get("topics", []),
                "entities": item.get("entities", []),
                "business_tags": item.get("business_tags", []),
                "is_hsi": item.get("is_hsi", False),
                "spotify_url": item.get("spotify_url", ""),
            })
            existing_ids.add(item["id"])
            added += 1

    existing_archive.sort(key=lambda x: x.get("priority_score", 0), reverse=True)
    existing_archive = existing_archive[:archive_max_items]

    with open(archive_path, "w") as f:
        json.dump(existing_archive, f, indent=2, default=str)

    print(f"  → {items_path} ({len(items)} items)")
    print(f"  → {summary_path}")
    print(f"  → {archive_path} ({len(existing_archive)} total, +{added} new)")

    print("\n" + "=" * 60)
    print(f"  {len(active)} active | {len(noise)} noise | {dupes_removed} deduped")
    print(f"  {summary['tiles']['high_priority']} key signals | {len(summary['must_reads'])} must-reads")
    print(f"  {len(existing_archive)} archived best articles (score ≥ {archive_min_score})")
    print("=" * 60)


if __name__ == "__main__":
    main()
