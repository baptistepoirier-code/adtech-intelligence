"""
Web dashboard generator — decision-support intelligence tool.
Produces a self-contained HTML file with:
  - Key Signals hero section
  - Strategic Themes chart
  - Key Learnings
  - Must-Read picks
  - Scored & badged content cards
  - People & Topics reference
"""

import os
import json
import re
from datetime import datetime, timezone
from collections import Counter


def _e(text: str) -> str:
    """HTML-escape."""
    return (text or "").replace("&", "&amp;").replace("<", "&lt;").replace(">", "&gt;").replace('"', "&quot;")


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# SECTION BUILDERS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _build_signals_html(signals: list[dict]) -> str:
    if not signals:
        return ""

    cards = ""
    for i, sig in enumerate(signals):
        badges_html = "".join(
            f'<span class="sig-badge" style="--bc:{b["color"]}">{_e(b["name"])}</span>'
            for b in sig.get("badges", [])
        )
        score = sig.get("relevanceScore", 0)
        score_class = "score-high" if score >= 50 else "score-med" if score >= 30 else "score-low"
        link = sig.get("link", "")
        tag = "a" if link else "div"
        href = f' href="{_e(link)}" target="_blank" rel="noopener"' if link else ""

        cards += f"""
        <{tag}{href} class="signal-card">
            <div class="signal-rank">{i + 1}</div>
            <div class="signal-body">
                <div class="signal-top">
                    <span class="signal-source">{_e(sig.get('source', ''))}</span>
                    {badges_html}
                    <span class="relevance-pill {score_class}">{score}</span>
                </div>
                <h3 class="signal-title">{_e(sig.get('title', ''))}</h3>
                <div class="signal-insight">
                    <div class="insight-row">
                        <i data-lucide="alert-circle" style="width:14px;height:14px;flex-shrink:0;color:var(--accent-yellow)"></i>
                        <span><strong>Why it matters:</strong> {_e(sig.get('why_matters', ''))}</span>
                    </div>
                    <div class="insight-row">
                        <i data-lucide="zap" style="width:14px;height:14px;flex-shrink:0;color:var(--accent-green)"></i>
                        <span><strong>Action:</strong> {_e(sig.get('action', ''))}</span>
                    </div>
                </div>
            </div>
        </{tag}>"""

    return f"""
    <section class="signals-section" id="section-signals">
        <div class="section-header">
            <i data-lucide="radio" class="section-icon" style="color: var(--accent-red)"></i>
            <h2>Today's Key Signals</h2>
            <span class="badge-hot">Priority Intel</span>
        </div>
        <p class="section-subtitle">The most important items for your DSP strategy this week.</p>
        <div class="signals-list">{cards}</div>
    </section>"""


def _build_learnings_html(learnings) -> str:
    if not learnings:
        return ""
    items = ""
    for i, l in enumerate(learnings):
        # Support both old str format and new dict format
        if isinstance(l, dict):
            text = l.get("text", "")
            link = l.get("link", "")
        else:
            text = l
            link = ""

        formatted = re.sub(r'\*\*(.+?)\*\*', r'<strong>\1</strong>', text)
        formatted = re.sub(r'\*(.+?)\*', r'<em>\1</em>', formatted)

        link_html = ""
        if link:
            link_html = f'<a href="{_e(link)}" target="_blank" rel="noopener" class="learning-link">Read &rarr;</a>'

        items += f"""
        <li class="learning-item">
            <span class="learning-num">{i + 1:02d}</span>
            <span class="learning-text">{formatted}</span>
            {link_html}
        </li>"""

    return f"""
    <section class="learnings-section" id="section-learnings">
        <div class="section-header">
            <i data-lucide="lightbulb" class="section-icon" style="color: var(--accent-yellow)"></i>
            <h2>Key Learnings This Week</h2>
            <span class="section-count">Top 10</span>
        </div>
        <ol class="learnings-list">{items}</ol>
    </section>"""


def _build_mustreads_html(picks: list[dict]) -> str:
    if not picks:
        return ""
    type_meta = {
        "blog": {"verb": "READ", "icon": "book-open", "color": "#6366f1"},
        "youtube": {"verb": "WATCH", "icon": "play", "color": "#ef4444"},
        "podcast": {"verb": "LISTEN", "icon": "headphones", "color": "#10b981"},
    }
    cards = ""
    for i, pick in enumerate(picks):
        meta = type_meta.get(pick.get("source_type", "blog"), type_meta["blog"])
        pclass = "priority-high" if pick.get("priority") == "high" else "priority-med"
        link = pick.get("link", "")
        tag = "a" if link else "div"
        href = f' href="{_e(link)}" target="_blank" rel="noopener"' if link else ""
        disabled = ' disabled-card' if not link else ""
        score = pick.get("relevanceScore", 0)
        score_class = "score-high" if score >= 50 else "score-med" if score >= 30 else "score-low"

        date_str = ""
        if pick.get("published_dt"):
            date_str = pick["published_dt"].strftime("%b %d")

        cards += f"""
        <{tag}{href} class="must-read-card {pclass}{disabled}">
            <div class="mr-rank">#{i + 1}</div>
            <div class="mr-body">
                <div class="mr-meta">
                    <span class="mr-type" style="--tc:{meta['color']}">
                        <i data-lucide="{meta['icon']}" style="width:14px;height:14px"></i>
                        {meta['verb']}
                    </span>
                    <span class="mr-source">{_e(pick.get('source_name', ''))}</span>
                    <span class="mr-date">{date_str}</span>
                    <span class="relevance-pill {score_class}">{score}</span>
                </div>
                <h3 class="mr-title">{_e(pick.get('title', ''))}</h3>
                <p class="mr-reason">
                    <i data-lucide="message-circle" style="width:14px;height:14px;flex-shrink:0;margin-top:2px"></i>
                    {_e(pick.get('reason', ''))}
                </p>
            </div>
        </{tag}>"""

    return f"""
    <section class="mustreads-section" id="section-mustreads">
        <div class="section-header">
            <i data-lucide="bookmark" class="section-icon" style="color: var(--accent-red)"></i>
            <h2>Must-Read / Must-Listen</h2>
            <span class="badge-hot">Expert Picks</span>
        </div>
        <p class="section-subtitle">Don't skim — consume in full. Here's why.</p>
        <div class="mustreads-list">{cards}</div>
    </section>"""


def _build_content_section(items: list[dict], stype: str) -> str:
    """Build scored content cards for a given source type."""
    type_items = [it for it in items if it.get("source_type") == stype]
    if not type_items:
        return ""

    meta = {
        "blog": {"icon": "newspaper", "label": "Blogs & Newsletters", "color": "#6366f1"},
        "youtube": {"icon": "play-circle", "label": "YouTube", "color": "#ef4444"},
        "podcast": {"icon": "headphones", "label": "Podcasts", "color": "#10b981"},
    }.get(stype, {"icon": "file", "label": stype, "color": "#6b7280"})

    type_items.sort(key=lambda x: x.get("relevanceScore", 0), reverse=True)

    cards = ""
    for it in type_items:
        score = it.get("relevanceScore", 0)
        score_class = "score-high" if score >= 50 else "score-med" if score >= 30 else "score-low"
        link = it.get("link", "")
        has_link = bool(link)

        date_str = it["published_dt"].strftime("%b %d") if it.get("published_dt") else ""

        # Badges
        badges_html = "".join(
            f'<span class="card-badge" style="--bc:{b["color"]}">{_e(b["name"])}</span>'
            for b in it.get("badges", [])
        )

        # Financial icon
        fin_icon = '<i data-lucide="trending-up" style="width:14px;height:14px;color:var(--accent-green);margin-left:4px" title="Financial / Earnings"></i>' if it.get("isFinancial") else ""

        # Competitor mentions
        comp_html = ""
        if it.get("competitors"):
            comp_names = ", ".join(it["competitors"][:3])
            comp_html = f'<div class="card-competitors"><i data-lucide="eye" style="width:12px;height:12px"></i> Mentions: {_e(comp_names)}</div>'

        # Summary
        summary = _e((it.get("summary", "") or "")[:180])
        if len(it.get("summary", "")) > 180:
            summary += "..."

        # Why it matters (compact)
        why = it.get("whyMatters", "")
        action = it.get("suggestedAction", "")

        # Spotify badge for podcasts
        spotify_badge = ""
        is_spotify = it.get("spotify_url") or ("open.spotify.com" in link)
        if stype == "podcast" and is_spotify:
            spotify_badge = '<span class="spotify-badge"><svg width="14" height="14" viewBox="0 0 24 24" fill="#1DB954"><path d="M12 0C5.4 0 0 5.4 0 12s5.4 12 12 12 12-5.4 12-12S18.66 0 12 0zm5.521 17.34c-.24.359-.66.48-1.021.24-2.82-1.74-6.36-2.101-10.561-1.141-.418.122-.779-.179-.899-.539-.12-.421.18-.78.54-.9 4.56-1.021 8.52-.6 11.64 1.32.42.18.479.659.301 1.02zm1.44-3.3c-.301.42-.841.6-1.262.3-3.239-1.98-8.159-2.58-11.939-1.38-.479.12-1.02-.12-1.14-.6-.12-.48.12-1.021.6-1.141C9.6 9.9 15 10.561 18.72 12.84c.361.181.54.78.241 1.2zm.12-3.36C15.24 8.4 8.82 8.16 5.16 9.301c-.6.179-1.2-.181-1.38-.721-.18-.601.18-1.2.72-1.381 4.26-1.26 11.28-1.02 15.721 1.621.539.3.719 1.02.419 1.56-.299.421-1.02.599-1.559.3z"/></svg> Spotify</span>'

        tag = "a" if has_link else "div"
        href = f' href="{_e(link)}" target="_blank" rel="noopener"' if has_link else ""
        disabled = " disabled-card" if not has_link else ""

        cards += f"""
        <{tag}{href} class="content-card{disabled}">
            <div class="card-top">
                <div class="card-badges">{badges_html}{spotify_badge}</div>
                <span class="relevance-pill {score_class}">{score}</span>
            </div>
            <div class="card-header">
                <span class="card-date">{date_str}{fin_icon}</span>
                <span class="card-source">{_e(it.get('source_name', ''))}</span>
            </div>
            <h3 class="card-title">{_e(it.get('title', ''))}</h3>
            <p class="card-summary">{summary}</p>
            {comp_html}
            <div class="card-insights">
                <p class="card-why"><strong>Why:</strong> {_e(why)}</p>
                <p class="card-action"><strong>Do:</strong> {_e(action)}</p>
            </div>
        </{tag}>"""

    return f"""
    <section class="content-section" id="section-{stype}">
        <div class="section-header">
            <i data-lucide="{meta['icon']}" class="section-icon" style="color: {meta['color']}"></i>
            <h2>{meta['label']}</h2>
            <span class="section-count">{len(type_items)}</span>
        </div>
        <div class="cards-grid">{cards}</div>
    </section>"""


def _build_people_html(people: list[dict]) -> str:
    if not people:
        return ""
    cards = ""
    for p in people:
        platforms = "".join(f'<span class="plat-badge">{pl.title()}</span>' for pl in p.get("platforms", []))
        cards += f"""
        <div class="person-card">
            <div class="person-avatar">{_e(p['name'][0])}</div>
            <div class="person-info">
                <h4>{_e(p['name'])}</h4>
                <p>{_e(p.get('role', ''))}</p>
                <div class="person-plats">{platforms}</div>
            </div>
        </div>"""
    return f"""
    <section class="content-section" id="section-people">
        <div class="section-header">
            <i data-lucide="users" class="section-icon" style="color: var(--accent-yellow)"></i>
            <h2>People to Follow</h2>
            <span class="section-count">{len(people)}</span>
        </div>
        <div class="people-grid">{cards}</div>
    </section>"""


def _build_topics_html(topics: list[str]) -> str:
    if not topics:
        return ""
    tags = "".join(f'<span class="topic-tag">{_e(t)}</span>' for t in topics)
    return f"""
    <section class="content-section" id="section-topics">
        <div class="section-header">
            <i data-lucide="hash" class="section-icon" style="color: var(--accent-purple)"></i>
            <h2>LinkedIn Topics to Watch</h2>
        </div>
        <div class="topics-grid">{tags}</div>
    </section>"""


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# MAIN GENERATOR
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_web_digest(
    all_items: list[dict],
    config: dict,
    output_dir: str = "./output",
    analysis: dict = None,
) -> str:
    os.makedirs(output_dir, exist_ok=True)
    now = datetime.now(timezone.utc)
    date_str = now.strftime("%Y-%m-%d")
    date_display = now.strftime("%A %B %d, %Y")
    filepath = os.path.join(output_dir, f"dashboard-{date_str}.html")

    analysis = analysis or {}
    items = analysis.get("items", all_items)
    stats = analysis.get("stats", {})
    themes = analysis.get("strategic_themes", [])

    # Build sections
    signals_html = _build_signals_html(analysis.get("key_signals", []))
    learnings_html = _build_learnings_html(analysis.get("key_learnings", []))
    mustreads_html = _build_mustreads_html(analysis.get("must_reads", []))
    blog_html = _build_content_section(items, "blog")
    yt_html = _build_content_section(items, "youtube")
    pod_html = _build_content_section(items, "podcast")
    people_html = _build_people_html(config.get("people", []))
    topics_html = _build_topics_html(config.get("linkedin_topics", []))

    # Chart data
    type_counts = Counter(it.get("source_type") for it in items)
    theme_labels = json.dumps([t["label"] for t in themes])
    theme_values = json.dumps([t["count"] for t in themes])
    source_counts = Counter(it.get("source_name") for it in items)
    top_sources = source_counts.most_common(8)
    src_labels = json.dumps([s[0] for s in top_sources])
    src_values = json.dumps([s[1] for s in top_sources])

    total = stats.get("total", len(items))
    avg_score = stats.get("avg_score", 0)
    high_pri = stats.get("high_priority", 0)
    filtered = stats.get("filtered", 0)

    html = f"""<!DOCTYPE html>
<html lang="en" data-theme="dark">
<head>
<meta charset="UTF-8">
<meta name="viewport" content="width=device-width, initial-scale=1.0">
<title>Performance DSP Intelligence — {date_str}</title>
<script src="https://cdn.jsdelivr.net/npm/chart.js@4/dist/chart.umd.min.js"></script>
<script src="https://unpkg.com/lucide@latest"></script>
<style>
*,*::before,*::after{{box-sizing:border-box;margin:0;padding:0}}
:root{{
  --bg-0:#0a0c14;--bg-1:#0f1117;--bg-2:#1a1d27;--bg-card:#1e2130;--bg-hover:#252840;
  --border:#2a2d3e;--text-1:#e8eaed;--text-2:#9ca3af;--text-3:#6b7280;
  --accent-blue:#6366f1;--accent-red:#ef4444;--accent-green:#10b981;
  --accent-yellow:#f59e0b;--accent-purple:#8b5cf6;
  --r:12px;--rs:8px;--shadow:0 4px 6px -1px rgba(0,0,0,.3);--tr:200ms ease;
}}
[data-theme="light"]{{
  --bg-0:#f1f5f9;--bg-1:#f8fafc;--bg-2:#ffffff;--bg-card:#ffffff;--bg-hover:#f1f5f9;
  --border:#e2e8f0;--text-1:#1e293b;--text-2:#64748b;--text-3:#94a3b8;
  --shadow:0 4px 6px -1px rgba(0,0,0,.07);
}}
body{{font-family:-apple-system,BlinkMacSystemFont,'Segoe UI',Inter,Roboto,sans-serif;background:var(--bg-0);color:var(--text-1);line-height:1.6;min-height:100vh}}
.container{{max-width:1320px;margin:0 auto;padding:0 24px}}

/* Header */
.header{{background:var(--bg-1);border-bottom:1px solid var(--border);padding:16px 0;position:sticky;top:0;z-index:100;backdrop-filter:blur(12px)}}
.header .container{{display:flex;align-items:center;justify-content:space-between}}
.header-left{{display:flex;align-items:center;gap:16px}}
.logo{{font-size:22px;font-weight:800;background:linear-gradient(135deg,var(--accent-blue),var(--accent-purple));-webkit-background-clip:text;-webkit-text-fill-color:transparent;background-clip:text}}
.header-date{{color:var(--text-2);font-size:13px}}
.theme-toggle{{background:var(--bg-card);border:1px solid var(--border);color:var(--text-1);padding:7px 12px;border-radius:var(--rs);cursor:pointer;font-size:13px;transition:all var(--tr);display:flex;align-items:center;gap:6px}}
.theme-toggle:hover{{background:var(--bg-hover)}}

/* Nav */
.nav{{background:var(--bg-1);border-bottom:1px solid var(--border);overflow-x:auto}}
.nav .container{{display:flex;gap:0}}
.nav-tab{{padding:12px 18px;color:var(--text-2);font-size:13px;font-weight:500;border:none;border-bottom:2px solid transparent;background:none;cursor:pointer;white-space:nowrap;display:flex;align-items:center;gap:6px;transition:all var(--tr)}}
.nav-tab:hover{{color:var(--text-1)}}
.nav-tab.active{{color:var(--accent-blue);border-bottom-color:var(--accent-blue)}}
.nav-tab .cnt{{background:var(--bg-card);padding:1px 7px;border-radius:10px;font-size:11px}}

/* Stats */
.stats-row{{display:grid;grid-template-columns:repeat(auto-fit,minmax(180px,1fr));gap:12px;margin:20px 0}}
.stat-card{{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r);padding:16px;display:flex;align-items:center;gap:14px}}
.stat-icon{{width:42px;height:42px;border-radius:10px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.stat-icon svg{{width:20px;height:20px}}
.stat-val{{font-size:26px;font-weight:700;line-height:1}}
.stat-lbl{{font-size:12px;color:var(--text-2);margin-top:2px}}

/* Sections shared */
.section-header{{display:flex;align-items:center;gap:10px;margin-bottom:16px;padding-bottom:10px;border-bottom:1px solid var(--border)}}
.section-icon{{width:22px;height:22px;flex-shrink:0}}
.section-header h2{{font-size:18px;font-weight:700}}
.section-count{{background:var(--bg-card);border:1px solid var(--border);padding:1px 9px;border-radius:10px;font-size:12px;color:var(--text-2)}}
.section-subtitle{{color:var(--text-2);font-size:13px;margin:-8px 0 16px 0}}
.badge-hot{{background:linear-gradient(135deg,var(--accent-red),#f97316);color:#fff;padding:2px 10px;border-radius:10px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.03em}}
.content-section{{margin-bottom:36px}}

/* Relevance pill */
.relevance-pill{{font-size:11px;font-weight:700;padding:2px 8px;border-radius:6px;font-variant-numeric:tabular-nums}}
.score-high{{background:rgba(16,185,129,.15);color:#10b981}}
.score-med{{background:rgba(245,158,11,.15);color:#f59e0b}}
.score-low{{background:rgba(107,114,128,.15);color:#9ca3af}}

/* Signals */
.signals-section{{margin-bottom:32px}}
.signals-list{{display:flex;flex-direction:column;gap:10px}}
.signal-card{{display:flex;gap:14px;padding:18px;background:var(--bg-card);border:1px solid var(--border);border-left:4px solid var(--accent-red);border-radius:var(--r);text-decoration:none;color:inherit;transition:all var(--tr)}}
.signal-card:hover{{background:var(--bg-hover);transform:translateY(-1px);box-shadow:var(--shadow)}}
.signal-rank{{font-size:24px;font-weight:800;color:var(--text-3);min-width:36px;display:flex;align-items:flex-start;justify-content:center;padding-top:2px}}
.signal-body{{flex:1;min-width:0}}
.signal-top{{display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap}}
.signal-source{{font-size:12px;color:var(--text-2);font-weight:600}}
.sig-badge{{font-size:10px;padding:1px 7px;border-radius:4px;background:color-mix(in srgb,var(--bc) 15%,transparent);color:var(--bc);font-weight:600}}
.signal-title{{font-size:15px;font-weight:700;line-height:1.4;margin-bottom:8px}}
.signal-insight{{display:flex;flex-direction:column;gap:4px}}
.insight-row{{display:flex;gap:8px;font-size:13px;color:var(--text-2);line-height:1.5;align-items:flex-start}}
.insight-row strong{{color:var(--text-1)}}

/* Key Learnings */
.learnings-section{{background:linear-gradient(135deg,rgba(245,158,11,.06),rgba(239,68,68,.03));border:1px solid rgba(245,158,11,.15);border-radius:var(--r);padding:24px;margin-bottom:32px}}
.learnings-list{{list-style:none;padding:0;display:flex;flex-direction:column;gap:8px}}
.learning-item{{display:flex;align-items:flex-start;gap:12px;padding:10px 14px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--rs);transition:all var(--tr)}}
.learning-item:hover{{border-color:var(--accent-yellow);transform:translateX(3px)}}
.learning-num{{font-size:12px;font-weight:800;color:var(--accent-yellow);background:rgba(245,158,11,.1);padding:3px 8px;border-radius:5px;flex-shrink:0;font-variant-numeric:tabular-nums}}
.learning-text{{font-size:13px;line-height:1.6;color:var(--text-1)}}
.learning-text strong{{color:var(--accent-yellow)}}
.learning-link{{display:inline-block;margin-left:8px;font-size:12px;font-weight:600;color:var(--accent);text-decoration:none;padding:2px 10px;border:1px solid var(--accent);border-radius:5px;white-space:nowrap;transition:all var(--tr);flex-shrink:0}}
.learning-link:hover{{background:var(--accent);color:white}}

/* Must-Reads */
.mustreads-section{{margin-bottom:36px}}
.mustreads-list{{display:flex;flex-direction:column;gap:10px}}
.must-read-card{{display:flex;gap:14px;padding:18px;background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r);text-decoration:none;color:inherit;transition:all var(--tr);border-left:4px solid var(--border)}}
.must-read-card:hover{{background:var(--bg-hover);transform:translateY(-1px);box-shadow:var(--shadow)}}
.must-read-card.priority-high{{border-left-color:var(--accent-red)}}
.must-read-card.priority-med{{border-left-color:var(--accent-yellow)}}
.mr-rank{{font-size:20px;font-weight:800;color:var(--text-3);min-width:36px;display:flex;align-items:center;justify-content:center;flex-shrink:0}}
.mr-body{{flex:1;min-width:0}}
.mr-meta{{display:flex;align-items:center;gap:8px;margin-bottom:6px;flex-wrap:wrap}}
.mr-type{{display:flex;align-items:center;gap:3px;font-size:10px;font-weight:700;text-transform:uppercase;letter-spacing:.04em;color:var(--tc);background:color-mix(in srgb,var(--tc) 12%,transparent);padding:2px 8px;border-radius:5px}}
.mr-source{{font-size:12px;color:var(--text-2);font-weight:600}}
.mr-date{{font-size:11px;color:var(--text-3)}}
.mr-title{{font-size:15px;font-weight:700;line-height:1.4;margin-bottom:6px}}
.mr-reason{{font-size:12px;color:var(--accent-yellow);line-height:1.5;display:flex;gap:6px;padding:6px 10px;background:rgba(245,158,11,.05);border-radius:var(--rs);border:1px solid rgba(245,158,11,.1)}}

/* Content Cards */
.cards-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(360px,1fr));gap:10px}}
.content-card{{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r);padding:16px;text-decoration:none;color:inherit;transition:all var(--tr);display:block}}
.content-card:hover{{background:var(--bg-hover);border-color:var(--accent-blue);transform:translateY(-2px);box-shadow:var(--shadow)}}
.content-card.disabled-card{{opacity:.55;pointer-events:none;border-style:dashed}}
.card-top{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.card-badges{{display:flex;gap:4px;flex-wrap:wrap}}
.card-badge{{font-size:9px;padding:1px 6px;border-radius:4px;background:color-mix(in srgb,var(--bc) 15%,transparent);color:var(--bc);font-weight:600;text-transform:uppercase;letter-spacing:.03em}}
.spotify-badge{{display:inline-flex;align-items:center;gap:4px;font-size:10px;font-weight:600;color:#1DB954;background:rgba(29,185,84,.1);padding:2px 8px;border-radius:4px}}
.card-header{{display:flex;justify-content:space-between;align-items:center;margin-bottom:6px}}
.card-date{{font-size:11px;color:var(--text-3);display:flex;align-items:center}}
.card-source{{font-size:11px;color:var(--text-2);font-weight:600}}
.card-title{{font-size:14px;font-weight:600;line-height:1.4;margin-bottom:6px}}
.card-summary{{font-size:12px;color:var(--text-2);line-height:1.5;display:-webkit-box;-webkit-line-clamp:2;-webkit-box-orient:vertical;overflow:hidden;margin-bottom:8px}}
.card-insights{{border-top:1px solid var(--border);padding-top:8px;display:flex;flex-direction:column;gap:2px}}
.card-why,.card-action{{font-size:11px;color:var(--text-3);line-height:1.4}}
.card-why strong,.card-action strong{{color:var(--text-2)}}
.card-competitors{{font-size:10px;color:#f43f5e;display:flex;align-items:center;gap:4px;padding:4px 0;font-weight:600;text-transform:uppercase;letter-spacing:.03em}}

/* Charts */
.charts-row{{display:grid;grid-template-columns:1fr 1fr;gap:12px;margin-bottom:28px}}
.chart-card{{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r);padding:20px}}
.chart-card h3{{font-size:14px;margin-bottom:12px;color:var(--text-1)}}
.chart-container{{position:relative;height:200px}}

/* People */
.people-grid{{display:grid;grid-template-columns:repeat(auto-fill,minmax(280px,1fr));gap:10px}}
.person-card{{background:var(--bg-card);border:1px solid var(--border);border-radius:var(--r);padding:14px;display:flex;align-items:center;gap:12px;transition:all var(--tr)}}
.person-card:hover{{background:var(--bg-hover);border-color:var(--accent-yellow)}}
.person-avatar{{width:40px;height:40px;border-radius:50%;background:linear-gradient(135deg,var(--accent-blue),var(--accent-purple));display:flex;align-items:center;justify-content:center;font-weight:700;font-size:16px;color:#fff;flex-shrink:0}}
.person-info h4{{font-size:13px;font-weight:600}}
.person-info p{{font-size:11px;color:var(--text-2);margin-top:1px}}
.person-plats{{display:flex;gap:4px;margin-top:4px}}
.plat-badge{{font-size:9px;padding:1px 6px;border-radius:3px;background:var(--bg-0);color:var(--text-3);font-weight:500}}

/* Topics */
.topics-grid{{display:flex;flex-wrap:wrap;gap:6px}}
.topic-tag{{background:var(--bg-card);border:1px solid var(--border);padding:6px 14px;border-radius:18px;font-size:12px;color:var(--text-2);transition:all var(--tr);cursor:default}}
.topic-tag:hover{{border-color:var(--accent-purple);color:var(--accent-purple)}}

/* Footer */
.footer{{border-top:1px solid var(--border);padding:20px 0;margin-top:32px;text-align:center;color:var(--text-3);font-size:12px}}

/* Responsive */
@media(max-width:768px){{
  .charts-row{{grid-template-columns:1fr}}
  .cards-grid{{grid-template-columns:1fr}}
  .people-grid{{grid-template-columns:1fr}}
  .stats-row{{grid-template-columns:repeat(2,1fr)}}
  .signal-card,.must-read-card{{flex-direction:column;gap:8px}}
  .signal-rank,.mr-rank{{min-width:auto;justify-content:flex-start;font-size:16px}}
}}
html{{scroll-behavior:smooth}}
.content-section.hidden,.signals-section.hidden,.learnings-section.hidden,.mustreads-section.hidden{{display:none}}
</style>
</head>
<body>

<header class="header">
<div class="container">
    <div class="header-left">
        <span class="logo">Performance DSP Intelligence</span>
        <span class="header-date">{date_display}</span>
    </div>
    <button class="theme-toggle" onclick="toggleTheme()">
        <i data-lucide="sun" style="width:15px;height:15px"></i>
        <span id="theme-label">Light</span>
    </button>
</div>
</header>

<nav class="nav">
<div class="container">
    <button class="nav-tab active" data-filter="all">All <span class="cnt">{total}</span></button>
    <button class="nav-tab" data-filter="signals"><i data-lucide="radio" style="width:14px;height:14px"></i> Signals</button>
    <button class="nav-tab" data-filter="learnings"><i data-lucide="lightbulb" style="width:14px;height:14px"></i> Learnings</button>
    <button class="nav-tab" data-filter="mustreads"><i data-lucide="bookmark" style="width:14px;height:14px"></i> Must-Read</button>
    <button class="nav-tab" data-filter="blog"><i data-lucide="newspaper" style="width:14px;height:14px"></i> Blogs <span class="cnt">{type_counts.get('blog',0)}</span></button>
    <button class="nav-tab" data-filter="youtube"><i data-lucide="play-circle" style="width:14px;height:14px"></i> YouTube <span class="cnt">{type_counts.get('youtube',0)}</span></button>
    <button class="nav-tab" data-filter="podcast"><i data-lucide="headphones" style="width:14px;height:14px"></i> Podcasts <span class="cnt">{type_counts.get('podcast',0)}</span></button>
    <button class="nav-tab" data-filter="people"><i data-lucide="users" style="width:14px;height:14px"></i> People</button>
    <button class="nav-tab" data-filter="topics"><i data-lucide="hash" style="width:14px;height:14px"></i> Topics</button>
</div>
</nav>

<main class="container" style="padding-top:20px;padding-bottom:32px">

<div class="stats-row" id="stats-section">
    <div class="stat-card">
        <div class="stat-icon" style="background:rgba(99,102,241,.12)"><i data-lucide="layers" style="color:var(--accent-blue)"></i></div>
        <div><div class="stat-val">{total}</div><div class="stat-lbl">Items Analyzed</div></div>
    </div>
    <div class="stat-card">
        <div class="stat-icon" style="background:rgba(16,185,129,.12)"><i data-lucide="target" style="color:var(--accent-green)"></i></div>
        <div><div class="stat-val">{avg_score}</div><div class="stat-lbl">Avg Relevance</div></div>
    </div>
    <div class="stat-card">
        <div class="stat-icon" style="background:rgba(239,68,68,.12)"><i data-lucide="flame" style="color:var(--accent-red)"></i></div>
        <div><div class="stat-val">{high_pri}</div><div class="stat-lbl">High Priority</div></div>
    </div>
    <div class="stat-card">
        <div class="stat-icon" style="background:rgba(139,92,246,.12)"><i data-lucide="filter" style="color:var(--accent-purple)"></i></div>
        <div><div class="stat-val">{filtered}</div><div class="stat-lbl">Noise Filtered</div></div>
    </div>
</div>

<div class="charts-row" id="charts-section">
    <div class="chart-card">
        <h3>Top Strategic Topics</h3>
        <div class="chart-container"><canvas id="themeChart"></canvas></div>
    </div>
    <div class="chart-card">
        <h3>Items by Source</h3>
        <div class="chart-container"><canvas id="sourceChart"></canvas></div>
    </div>
</div>

{signals_html}
{learnings_html}
{mustreads_html}
{blog_html}
{yt_html}
{pod_html}
{people_html}
{topics_html}

</main>

<footer class="footer">
<div class="container">Performance DSP Intelligence — Decision-support for mobile UA & exchange builders — {date_display}</div>
</footer>

<script>
lucide.createIcons();

function toggleTheme(){{
    const h=document.documentElement,c=h.getAttribute('data-theme'),n=c==='dark'?'light':'dark';
    h.setAttribute('data-theme',n);
    document.getElementById('theme-label').textContent=n==='dark'?'Light':'Dark';
    setTimeout(()=>{{if(tc){{tc.options.scales.x.grid.color=gbc();tc.options.scales.x.ticks.color=gtc();tc.options.scales.y.ticks.color=gtc();tc.update()}}if(sc){{sc.options.scales.x.grid.color=gbc();sc.options.scales.x.ticks.color=gtc();sc.options.scales.y.ticks.color=gtc();sc.update()}}}},50);
}}

document.querySelectorAll('.nav-tab').forEach(tab=>{{
    tab.addEventListener('click',()=>{{
        document.querySelectorAll('.nav-tab').forEach(t=>t.classList.remove('active'));
        tab.classList.add('active');
        const f=tab.dataset.filter;
        const all=['signals','learnings','mustreads','blog','youtube','podcast','people','topics'];
        const se=document.getElementById('stats-section');
        const ce=document.getElementById('charts-section');
        if(f==='all'){{se.style.display='';ce.style.display='';all.forEach(s=>{{const el=document.getElementById('section-'+s);if(el)el.classList.remove('hidden')}})}}
        else{{
            const noStats=['people','topics','learnings','mustreads','signals'].includes(f);
            se.style.display=noStats?'none':'';ce.style.display='none';
            all.forEach(s=>{{const el=document.getElementById('section-'+s);if(el){{s===f?el.classList.remove('hidden'):el.classList.add('hidden')}}}})
        }}
    }});
}});

const gtc=()=>getComputedStyle(document.documentElement).getPropertyValue('--text-2').trim()||'#9ca3af';
const gbc=()=>getComputedStyle(document.documentElement).getPropertyValue('--border').trim()||'#2a2d3e';
const tl={theme_labels},tv={theme_values},sl={src_labels},sv={src_values};
const themeColors=tl.map((_,i)=>{{const h=(i*47+200)%360;return`hsl(${{h}},60%,55%)`}});
const srcColors=sl.map((_,i)=>{{const h=(i*37+220)%360;return`hsl(${{h}},55%,50%)`}});
let tc,sc;
function initCharts(){{
    const txt=gtc(),brd=gbc();
    tc=new Chart(document.getElementById('themeChart'),{{type:'bar',data:{{labels:tl,datasets:[{{data:tv,backgroundColor:themeColors,borderRadius:6,borderSkipped:false}}]}},options:{{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{{legend:{{display:false}}}},scales:{{x:{{grid:{{color:brd}},ticks:{{color:txt,stepSize:1}}}},y:{{grid:{{display:false}},ticks:{{color:txt,font:{{size:11}}}}}}}}}}}});
    sc=new Chart(document.getElementById('sourceChart'),{{type:'bar',data:{{labels:sl,datasets:[{{data:sv,backgroundColor:srcColors,borderRadius:6,borderSkipped:false}}]}},options:{{responsive:true,maintainAspectRatio:false,indexAxis:'y',plugins:{{legend:{{display:false}}}},scales:{{x:{{grid:{{color:brd}},ticks:{{color:txt,stepSize:1}}}},y:{{grid:{{display:false}},ticks:{{color:txt,font:{{size:11}}}}}}}}}}}});
}}
initCharts();
</script>
</body>
</html>"""

    with open(filepath, "w", encoding="utf-8") as f:
        f.write(html)
    return filepath
