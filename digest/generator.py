"""
Digest generator — produces a Markdown file with curated content,
sorted by source type and recency.
"""

import os
from datetime import datetime, timezone
from typing import Optional


# ── Optional LLM summarisation ───────────────────────────────

def _summarize_with_llm(items: list[dict], api_key: str, provider: str = "anthropic") -> Optional[str]:
    """
    Generate an executive summary of all items using an LLM.
    Returns None if the call fails or no key is configured.
    """
    if not api_key:
        return None

    titles_text = "\n".join(
        f"- [{it['source_name']}] {it['title']}" for it in items[:30]
    )

    prompt = (
        "You are an ad tech industry analyst. Based on the following list of "
        "recent articles, videos and podcast episodes, write a concise executive "
        "summary (5-8 bullet points) of the key themes and trends this week. "
        "Focus on what matters for someone building a performance DSP.\n\n"
        f"{titles_text}\n\n"
        "Write the summary in English with bullet points."
    )

    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=1024,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        elif provider == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=1024,
            )
            return resp.choices[0].message.content
    except Exception as e:
        print(f"  ⚠ LLM summary failed: {e}")
    return None


# ── Markdown generation ──────────────────────────────────────

SOURCE_TYPE_LABELS = {
    "blog": "📰 Blogs & Newsletters",
    "youtube": "📺 YouTube",
    "podcast": "🎧 Podcasts",
}

SOURCE_TYPE_ORDER = ["blog", "youtube", "podcast"]


def generate_digest(
    all_items: list[dict],
    output_dir: str = "./output",
    anthropic_key: str = "",
    openai_key: str = "",
    key_learnings: list[str] = None,
    must_reads: list[dict] = None,
) -> str:
    """
    Generate a Markdown digest and save it to output_dir.
    Returns the path to the generated file.
    """
    os.makedirs(output_dir, exist_ok=True)

    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    filename = f"digest-{date_str}.md"
    filepath = os.path.join(output_dir, filename)

    lines: list[str] = []

    # Header
    lines.append(f"# 🗞 Ad Tech Weekly Digest — {date_str}")
    lines.append("")
    lines.append(f"*Generated on {now.strftime('%A %B %d, %Y at %H:%M UTC')}*")
    lines.append("")

    # Executive summary (if LLM key available)
    api_key = anthropic_key or openai_key
    provider = "anthropic" if anthropic_key else "openai"
    if api_key:
        print("  🤖 Generating AI executive summary...")
        summary = _summarize_with_llm(all_items, api_key, provider)
        if summary:
            lines.append("## 🧠 Executive Summary (AI-generated)")
            lines.append("")
            lines.append(summary)
            lines.append("")
            lines.append("---")
            lines.append("")

    # Key Learnings
    if key_learnings:
        lines.append("## 💡 Key Learnings This Week")
        lines.append("")
        for i, learning in enumerate(key_learnings, 1):
            if isinstance(learning, dict):
                text = learning.get("text", "")
                link = learning.get("link", "")
                if link:
                    lines.append(f"{i}. {text} [→ Read]({link})")
                else:
                    lines.append(f"{i}. {text}")
            else:
                lines.append(f"{i}. {learning}")
        lines.append("")
        lines.append("---")
        lines.append("")

    # Must-Read Picks
    if must_reads:
        type_verbs = {"blog": "📖 READ", "podcast": "🎧 LISTEN", "youtube": "📺 WATCH"}
        lines.append("## 🔖 Must-Read / Must-Listen")
        lines.append("")
        lines.append("*Don't just skim these — consume them in full.*")
        lines.append("")
        for i, pick in enumerate(must_reads, 1):
            verb = type_verbs.get(pick.get("source_type", "blog"), "📖 READ")
            title = pick.get("title", "")
            link = pick.get("link", "")
            source = pick.get("source_name", "")
            reason = pick.get("reason", "")
            lines.append(f"### {i}. {verb} — [{title}]({link})")
            lines.append(f"**Source:** {source}")
            lines.append(f"> 💬 {reason}")
            lines.append("")
        lines.append("---")
        lines.append("")

    # Stats
    total = len(all_items)
    by_type = {}
    for item in all_items:
        by_type.setdefault(item["source_type"], []).append(item)

    lines.append(f"**{total} items** collected from "
                 f"{len(by_type.get('blog', []))} blogs, "
                 f"{len(by_type.get('youtube', []))} videos, "
                 f"{len(by_type.get('podcast', []))} podcast episodes.")
    lines.append("")
    lines.append("---")
    lines.append("")

    # Content sections by type
    for stype in SOURCE_TYPE_ORDER:
        items = by_type.get(stype, [])
        if not items:
            continue

        label = SOURCE_TYPE_LABELS.get(stype, stype)
        lines.append(f"## {label}")
        lines.append("")

        # Sort by date (most recent first)
        items.sort(key=lambda x: x.get("published_dt") or datetime.min.replace(tzinfo=timezone.utc), reverse=True)

        # Group by source
        by_source: dict[str, list[dict]] = {}
        for item in items:
            by_source.setdefault(item["source_name"], []).append(item)

        for source_name, source_items in by_source.items():
            lines.append(f"### {source_name}")
            lines.append("")
            for item in source_items:
                date_display = ""
                if item.get("published_dt"):
                    date_display = item["published_dt"].strftime("%b %d")
                title = item["title"]
                link = item["link"]
                lines.append(f"- **[{title}]({link})** {f'({date_display})' if date_display else ''}")
                if item["summary"]:
                    short_summary = item["summary"][:200]
                    if len(item["summary"]) > 200:
                        short_summary += "..."
                    lines.append(f"  > {short_summary}")
            lines.append("")

    # Footer
    lines.append("---")
    lines.append("")
    lines.append("*Generated by [Ad Tech Curator](https://github.com/your-repo) — "
                 "your personal ad tech intelligence agent.*")

    content = "\n".join(lines)

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(content)

    return filepath
