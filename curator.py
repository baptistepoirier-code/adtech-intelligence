#!/usr/bin/env python3
"""
Ad Tech Content Curator — Decision-Support Intelligence Tool
=============================================================
Aggregates, scores, and analyses ad tech content from blogs,
YouTube channels, and podcasts into an intelligence dashboard.

Usage:
    python curator.py                     # Generate this week's digest
    python curator.py --days 3            # Last 3 days only
    python curator.py --resolve-channels  # Find missing YouTube channel IDs
"""

import argparse
import sys
import yaml
from pathlib import Path

from sources.fetcher import fetch_blog, fetch_youtube, fetch_podcast, resolve_youtube_channel_id
from digest.intelligence import analyze_content
from digest.generator import generate_digest
from digest.web_generator import generate_web_digest


def load_config(path: str = "config.yaml") -> dict:
    with open(path, "r", encoding="utf-8") as f:
        return yaml.safe_load(f)


def resolve_channels(config: dict):
    """Resolve missing YouTube channel IDs from handles."""
    channels = config.get("youtube_channels", [])
    updated = False

    for ch in channels:
        if ch.get("channel_id"):
            print(f"  ✓ {ch['name']}: {ch['channel_id']}")
            continue
        handle = ch.get("handle")
        if not handle:
            print(f"  ✗ {ch['name']}: no handle or channel_id configured")
            continue

        print(f"  🔍 Resolving {ch['name']} ({handle})...")
        cid = resolve_youtube_channel_id(handle)
        if cid:
            ch["channel_id"] = cid
            updated = True
            print(f"  ✓ {ch['name']}: {cid}")
        else:
            print(f"  ✗ {ch['name']}: could not resolve")

    if updated:
        config_path = Path("config.yaml")
        with open(config_path, "w", encoding="utf-8") as f:
            yaml.dump(config, f, default_flow_style=False, allow_unicode=True, sort_keys=False)
        print(f"\n  💾 Updated config.yaml with resolved channel IDs.")

    return config


def run_curation(config: dict, days: int):
    """Main curation pipeline."""
    settings = config.get("settings", {})
    days_lookback = days or settings.get("days_lookback", 7)
    max_items = settings.get("max_items_per_source", 5)
    output_dir = settings.get("output_dir", "./output")

    all_items: list[dict] = []

    # ── Fetch blogs ──────────────────────────────────────────
    blogs = config.get("blogs", [])
    if blogs:
        print(f"\n📰 Fetching {len(blogs)} blogs...")
        for blog in blogs:
            print(f"  → {blog['name']}...", end=" ", flush=True)
            items = fetch_blog(blog, days_lookback=days_lookback, max_items=max_items)
            print(f"{len(items)} articles")
            all_items.extend(items)

    # ── Fetch YouTube ────────────────────────────────────────
    channels = config.get("youtube_channels", [])
    if channels:
        print(f"\n📺 Fetching {len(channels)} YouTube channels...")
        for ch in channels:
            print(f"  → {ch['name']}...", end=" ", flush=True)
            items = fetch_youtube(ch, days_lookback=days_lookback, max_items=max_items)
            print(f"{len(items)} videos")
            all_items.extend(items)

    # ── Fetch podcasts ───────────────────────────────────────
    podcasts = config.get("podcasts", [])
    if podcasts:
        print(f"\n🎧 Fetching {len(podcasts)} podcasts...")
        for pod in podcasts:
            print(f"  → {pod['name']}...", end=" ", flush=True)
            items = fetch_podcast(pod, days_lookback=days_lookback, max_items=max_items)
            print(f"{len(items)} episodes")
            all_items.extend(items)

    # ── Check we have content ────────────────────────────────
    if not all_items:
        print("\n⚠ No content found. Try increasing --days or check your config.")
        sys.exit(1)

    print(f"\n✨ Collected {len(all_items)} raw items.")

    # ── Intelligence pipeline ────────────────────────────────
    print("\n🧠 Running intelligence analysis...")
    analysis = analyze_content(
        all_items,
        anthropic_key=settings.get("anthropic_api_key", ""),
        openai_key=settings.get("openai_api_key", ""),
    )

    stats = analysis["stats"]
    print(f"\n   📊 {stats['total']} items scored (avg relevance: {stats['avg_score']})")
    print(f"   🔥 {stats['high_priority']} high-priority items")
    print(f"   🔇 {stats['filtered']} noise items filtered")
    print(f"   ⚡ {len(analysis['key_signals'])} key signals")
    print(f"   💡 {len(analysis['key_learnings'])} key learnings")
    print(f"   📌 {len(analysis['must_reads'])} must-read picks")

    # ── Generate outputs ─────────────────────────────────────
    print("\n📝 Generating outputs...")

    md_path = generate_digest(
        analysis["items"],
        output_dir=output_dir,
        anthropic_key=settings.get("anthropic_api_key", ""),
        openai_key=settings.get("openai_api_key", ""),
        key_learnings=analysis["key_learnings"],
        must_reads=analysis["must_reads"],
    )

    web_path = generate_web_digest(
        analysis["items"],
        config=config,
        output_dir=output_dir,
        analysis=analysis,
    )

    print(f"\n🎉 Intelligence dashboard ready:")
    print(f"   📄 Markdown : {md_path}")
    print(f"   🌐 Dashboard: {web_path}")
    print(f"\n   open {web_path}")


def main():
    parser = argparse.ArgumentParser(
        description="Ad Tech Intelligence — Decision-support for DSP & Exchange builders"
    )
    parser.add_argument(
        "--days", type=int, default=0,
        help="Number of days to look back (overrides config)"
    )
    parser.add_argument(
        "--resolve-channels", action="store_true",
        help="Resolve missing YouTube channel IDs from handles"
    )
    parser.add_argument(
        "--config", type=str, default="config.yaml",
        help="Path to config file (default: config.yaml)"
    )

    args = parser.parse_args()
    config = load_config(args.config)

    if args.resolve_channels:
        print("🔍 Resolving YouTube channel IDs...\n")
        resolve_channels(config)
        return

    print("=" * 60)
    print("  🧠 Ad Tech Intelligence — Decision Support Tool")
    print("=" * 60)

    run_curation(config, args.days)


if __name__ == "__main__":
    main()
