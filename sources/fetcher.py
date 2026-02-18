"""
Unified content fetcher for RSS feeds (blogs, YouTube channels, podcasts).
All three source types expose RSS — this module handles them uniformly.
"""

import feedparser
import re
import urllib.request
from datetime import datetime, timedelta, timezone
from typing import Optional


# ── helpers ──────────────────────────────────────────────────

def _parse_date(entry) -> Optional[datetime]:
    """Extract a timezone-aware datetime from a feed entry."""
    for attr in ("published_parsed", "updated_parsed"):
        tp = getattr(entry, attr, None)
        if tp:
            try:
                from calendar import timegm
                return datetime.fromtimestamp(timegm(tp), tz=timezone.utc)
            except Exception:
                continue
    return None


def _clean_html(raw_html: str) -> str:
    """Strip HTML tags for a plain-text summary."""
    clean = re.sub(r"<[^>]+>", "", raw_html or "")
    clean = re.sub(r"\s+", " ", clean).strip()
    return clean[:500]  # cap length


FEED_TIMEOUT = 10  # seconds


class _RedirectHandler(urllib.request.HTTPRedirectHandler):
    """Follow all redirects including 308."""
    def http_error_308(self, req, fp, code, msg, headers):
        return self.http_error_302(req, fp, code, msg, headers)


def _fetch_feed_raw(url: str) -> str:
    """Download feed XML with a hard timeout and redirect handling."""
    opener = urllib.request.build_opener(_RedirectHandler)
    req = urllib.request.Request(url, headers={
        "User-Agent": "Mozilla/5.0 (AdTechCurator/1.0)"
    })
    with opener.open(req, timeout=FEED_TIMEOUT) as resp:
        return resp.read().decode("utf-8", errors="ignore")


# ── YouTube channel ID resolver ──────────────────────────────

def resolve_youtube_channel_id(handle: str) -> Optional[str]:
    """
    Given a YouTube handle like '@Prebidorg', fetch the channel page
    and extract the channel ID from the HTML meta tags.
    """
    url = f"https://www.youtube.com/{handle}"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            html = resp.read().decode("utf-8", errors="ignore")
        match = re.search(r'"externalId"\s*:\s*"(UC[^"]+)"', html)
        if match:
            return match.group(1)
        match = re.search(r'<meta\s+itemprop="channelId"\s+content="(UC[^"]+)"', html)
        if match:
            return match.group(1)
    except Exception as e:
        print(f"  ⚠ Could not resolve handle {handle}: {e}")
    return None


# ── Generic RSS fetcher ──────────────────────────────────────

def fetch_rss(
    rss_url: str,
    source_name: str,
    source_type: str,
    days_lookback: int = 7,
    max_items: int = 5,
) -> list[dict]:
    """
    Fetch and parse an RSS feed.
    Returns a list of content dicts ready for the digest.
    """
    try:
        raw_xml = _fetch_feed_raw(rss_url)
        feed = feedparser.parse(raw_xml)
    except Exception as e:
        print(f"\n  ⚠ Error fetching {source_name}: {e}")
        return []

    if feed.bozo and not feed.entries:
        print(f"\n  ⚠ Could not parse feed for {source_name}")
        return []

    cutoff = datetime.now(timezone.utc) - timedelta(days=days_lookback)
    items = []

    for entry in feed.entries:
        pub_date = _parse_date(entry)

        # If we can parse the date, filter by lookback window
        if pub_date and pub_date < cutoff:
            continue

        title = entry.get("title", "No title")
        link = entry.get("link", "")
        summary = _clean_html(
            entry.get("summary", entry.get("description", ""))
        )

        items.append({
            "source_name": source_name,
            "source_type": source_type,
            "title": title,
            "link": link,
            "summary": summary,
            "published": pub_date.isoformat() if pub_date else "Unknown",
            "published_dt": pub_date,
        })

        if len(items) >= max_items:
            break

    return items


# ── Source-specific wrappers ─────────────────────────────────

def fetch_blog(blog_cfg: dict, days_lookback: int = 7, max_items: int = 5) -> list[dict]:
    """Fetch articles from a blog RSS feed."""
    return fetch_rss(
        rss_url=blog_cfg["rss_url"],
        source_name=blog_cfg["name"],
        source_type="blog",
        days_lookback=days_lookback,
        max_items=max_items,
    )


def fetch_youtube(channel_cfg: dict, days_lookback: int = 7, max_items: int = 5) -> list[dict]:
    """Fetch recent videos from a YouTube channel RSS feed."""
    channel_id = channel_cfg.get("channel_id", "")

    # Try to resolve channel ID from handle if missing
    if not channel_id and channel_cfg.get("handle"):
        print(f"  🔍 Resolving channel ID for {channel_cfg['name']}...")
        channel_id = resolve_youtube_channel_id(channel_cfg["handle"])
        if channel_id:
            print(f"  ✓ Resolved: {channel_id}")
        else:
            print(f"  ✗ Could not resolve — skipping {channel_cfg['name']}")
            return []

    if not channel_id:
        print(f"  ⚠ No channel ID for {channel_cfg['name']} — skipping")
        return []

    rss_url = f"https://www.youtube.com/feeds/videos.xml?channel_id={channel_id}"
    return fetch_rss(
        rss_url=rss_url,
        source_name=channel_cfg["name"],
        source_type="youtube",
        days_lookback=days_lookback,
        max_items=max_items,
    )


def fetch_podcast(podcast_cfg: dict, days_lookback: int = 7, max_items: int = 5) -> list[dict]:
    """Fetch recent episodes from a podcast RSS feed."""
    items = fetch_rss(
        rss_url=podcast_cfg["rss_url"],
        source_name=podcast_cfg["name"],
        source_type="podcast",
        days_lookback=days_lookback,
        max_items=max_items,
    )
    # Override link with Spotify URL if available
    spotify_url = podcast_cfg.get("spotify_url", "")
    if spotify_url:
        for item in items:
            if not item.get("link") or "megaphone" in item.get("link", "") or "art19" in item.get("link", ""):
                item["link"] = spotify_url
            item["spotify_url"] = spotify_url
    return items
