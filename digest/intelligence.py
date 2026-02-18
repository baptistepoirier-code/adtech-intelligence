"""
Content intelligence module — decision-support layer for ad tech leaders.

Provides:
  1. Anti-noise filtering (removes generic marketing fluff)
  2. Relevance scoring 0–100 per item
  3. Topic tags + impact type classification
  4. Badge categorisation (Privacy, Supply, Demand, Identity)
  5. Today's Key Signals (top 3–5 with why-it-matters + suggested action)
  6. Strategic Themes detection
  7. Key Learnings (10-bullet synthesis)
  8. Must-Read expert picks

Works in two modes:
  - With LLM API key  → deep, contextual analysis
  - Without API key    → smart heuristic scoring + extraction
"""

import re
from collections import Counter
from datetime import datetime, timezone
from typing import Optional


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 1. ANTI-NOISE FILTER
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

NOISE_KEYWORDS = [
    "content marketing", "social media strategy", "seo tips",
    "influencer marketing", "brand awareness", "copywriting",
    "how to grow your blog", "email marketing tips",
    "social media tips", "instagram strategy",
]


def filter_noise(items: list[dict]) -> list[dict]:
    """Remove generic marketing noise — keep only ad tech signal."""
    filtered = []
    for item in items:
        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        # Only filter if the ENTIRE content is noise (title dominated by noise terms)
        title_lower = item.get("title", "").lower()
        is_noise = any(nk in title_lower for nk in NOISE_KEYWORDS)
        if not is_noise:
            filtered.append(item)
    return filtered


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 2. RELEVANCE SCORING (0–100)
#    Oriented: Performance DSP / Mobile UA / App Growth
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

# Keyword groups with point values — performance DSP focused
SCORING_RULES = [
    # Core DSP / bidding mechanics (+25)
    (25, ["bid optimization", "bid shading", "bidding algorithm", "ml bidding",
           "predictive model", "pcvr", "pltv", "pcpi", "win rate",
           "openrtb", "auction", "floor price", "bid request",
           "real-time bidding", "in-app bidding"]),
    # SKAN / ATT / mobile privacy (+25)
    (25, ["skadnetwork", "skan", "att ", "app tracking transparency",
           "idfa", "idfv", "privacy sandbox android",
           "topics api", "protected audience", "attribution api"]),
    # User acquisition / performance marketing (+20)
    (20, ["user acquisition", " ua ", "app install", "cpi", "cpa",
           "roas", "return on ad spend", "ltv", "lifetime value",
           "retargeting", "re-engagement", "reattribution",
           "campaign optimization", "performance marketing"]),
    # Competitor intelligence (+20)
    (20, ["applovin", "unity ads", "ironsource", "moloco",
           "liftoff", "vungle", "smadex", "adikteev",
           "digital turbine", "mintegral", "chartboost",
           "inmobi", "bigo ads"]),
    # MMP / measurement (+20)
    (20, ["appsflyer", "adjust", "singular", "kochava", "branch",
           "mmp", "mobile measurement", "incrementality",
           "attribution", "media mix model", "mmm",
           "multi-touch attribution"]),
    # Creative & formats (+15)
    (15, ["playable ad", "rewarded video", "interstitial",
           "creative optimization", "dco", "dynamic creative",
           "endcard", "ad creative", "ugc ad", "video ad"]),
    # Mediation & monetization (+15)
    (15, ["mediation", "ad monetization", "levelplay", "max",
           "waterfall", "hybrid monetization", "offerwall",
           "arpdau", "arppu", "ecpm", "fill rate"]),
    # AI / ML in performance (+15)
    (15, ["machine learning", "agentic", "ai agent", "automation",
           "dynamic floor", "ml model", "llm", "generative ai",
           "predictive analytics"]),
    # Mobile ecosystem (+10)
    (10, ["mobile gaming", "app store", "google play",
           "apple search ads", "asa", "app growth",
           "casual game", "hyper-casual", "midcore"]),
    # Privacy & regulation (broader) (+10)
    (10, ["privacy sandbox", "gdpr", "regulation", "antitrust",
           "cookie deprecation", "cookieless", "consent",
           "data protection", "ftc", "cma", "dma"]),
    # Supply / exchange (+10)
    (10, ["ssp", "ad exchange", "supply path", "spo",
           "header bidding", "prebid", "sdk bidding"]),
    # CTV & cross-platform (+10)
    (10, ["ctv", "connected tv", "cross-platform", "ott",
           "streaming", "multiplatform"]),
    # Ad fraud (+10)
    (10, ["ad fraud", "invalid traffic", "ivt", "click fraud",
           "install fraud", "bot traffic", "fraud detection"]),
]

# High-priority terms — extra +3 each
HIGH_PRIORITY_TERMS = [
    "skadnetwork", "skan 4", "privacy sandbox android",
    "applovin", "moloco", "unity ads", "liftoff",
    "bid optimization", "ml bidding", "pcvr", "pltv",
    "incrementality", "in-app bidding", "roas",
]

# Authority sources — performance DSP ecosystem
HIGH_AUTHORITY_SOURCES = {
    "Mobile Dev Memo": 18,         # Eric Seufert = king
    "AdExchanger": 10,
    "Stratechery": 8,
    "ExchangeWire": 6,
    "Marketecture (Blog)": 8,
    "Marketecture Podcast": 8,
    "IAB Tech Lab": 8,
    "The AdTechGod Pod": 6,
    "AppsFlyer": 12,
    "AppLovin": 12,
    "Singular": 10,
    "Liftoff": 10,
    "Adjust": 10,
}

# Eric Seufert / Mobile Dev Memo gets extra weight everywhere
SEUFERT_BOOST_KEYWORDS = [
    "seufert", "mobile dev memo", "mdm", "eric seufert",
]

# Competitor names for tracking
COMPETITORS = {
    "applovin": "AppLovin",
    "unity ads": "Unity/ironSource",
    "ironsource": "Unity/ironSource",
    "moloco": "Moloco",
    "liftoff": "Liftoff/Vungle",
    "vungle": "Liftoff/Vungle",
    "smadex": "Smadex",
    "adikteev": "Adikteev",
    "digital turbine": "Digital Turbine",
    "mintegral": "Mintegral",
    "chartboost": "Chartboost",
    "inmobi": "InMobi",
    "meta ads": "Meta",
    "facebook ads": "Meta",
    "google ads": "Google",
    "google admob": "Google",
}


def score_item(item: dict) -> dict:
    """
    Score a single item 0–100 for relevance.
    Returns the item enriched with: relevanceScore, topicTags, impactType, badges.
    """
    text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
    source = item.get("source_name", "")
    score = 0
    topic_tags = set()
    impact_types = set()

    # Rule-based keyword scoring
    for points, keywords in SCORING_RULES:
        for kw in keywords:
            if kw in text:
                score += points
                break  # only count each rule group once

    # High-authority source bonus
    score += HIGH_AUTHORITY_SOURCES.get(source, 0)

    # Published today bonus
    pub_dt = item.get("published_dt")
    if pub_dt:
        now = datetime.now(timezone.utc)
        if pub_dt.date() == now.date():
            score += 10

    # Eric Seufert global boost
    if any(sk in text or sk in source.lower() for sk in SEUFERT_BOOST_KEYWORDS):
        score += 15

    # High-priority term bonus
    for hp in HIGH_PRIORITY_TERMS:
        if hp in text:
            score += 2

    # Cap at 100
    score = min(score, 100)

    # ── Topic tags (performance DSP oriented) ─────────────
    TAG_MAP = {
        "Bid Optimization": ["bid optimization", "bidding", "bid shading", "auction", "floor", "openrtb", "in-app bidding"],
        "SKAN & ATT": ["skadnetwork", "skan", "att", "idfa", "idfv", "app tracking"],
        "User Acquisition": ["user acquisition", "ua", "app install", "cpi", "campaign", "performance marketing"],
        "ROAS & LTV": ["roas", "ltv", "lifetime value", "return on ad spend", "revenue optimization"],
        "Measurement & MMP": ["attribution", "incrementality", "appsflyer", "adjust", "singular", "mmp", "measurement"],
        "ML & Predictive": ["machine learning", "ml", "predictive", "pcvr", "pltv", "ai", "agentic", "automation"],
        "Creative & Formats": ["creative", "playable", "rewarded video", "interstitial", "dco", "endcard", "ugc"],
        "Mediation & Monetization": ["mediation", "monetization", "waterfall", "ecpm", "fill rate", "arpdau", "levelplay"],
        "Privacy & Regulation": ["privacy", "gdpr", "regulation", "antitrust", "cookie", "consent", "sandbox"],
        "Competitor Move": list(COMPETITORS.keys()),
        "Mobile Gaming": ["mobile gaming", "casual game", "hyper-casual", "midcore", "app store", "google play"],
        "Retargeting": ["retargeting", "re-engagement", "reattribution", "remarketing"],
        "Ad Fraud": ["fraud", "ivt", "invalid traffic", "click fraud", "install fraud"],
        "CTV & Cross-Platform": ["ctv", "streaming", "connected tv", "cross-platform"],
    }

    for tag, keywords in TAG_MAP.items():
        if any(kw in text for kw in keywords):
            topic_tags.add(tag)

    # ── Impact type (performance DSP) ────────────────────
    IMPACT_MAP = {
        "bidding": ["bid optimization", "bidding", "auction", "floor", "in-app bidding", "rtb"],
        "privacy": ["skan", "att", "idfa", "privacy sandbox", "privacy", "gdpr", "cookie"],
        "measurement": ["attribution", "incrementality", "appsflyer", "mmp", "measurement"],
        "ML": ["machine learning", "ml", "predictive", "pcvr", "pltv", "ai", "agentic"],
        "UA": ["user acquisition", "app install", "cpi", "roas", "ltv", "campaign"],
        "creative": ["creative", "playable", "rewarded video", "dco", "ugc"],
        "competitor": list(COMPETITORS.keys()),
        "monetization": ["mediation", "monetization", "ecpm", "arpdau", "fill rate"],
        "fraud": ["fraud", "ivt", "invalid traffic"],
        "regulation": ["regulation", "antitrust", "ftc", "cma", "doj", "dma"],
    }

    for impact, keywords in IMPACT_MAP.items():
        if any(kw in text for kw in keywords):
            impact_types.add(impact)

    # ── Detect competitor mentions ────────────────────────
    mentioned_competitors = []
    for kw, name in COMPETITORS.items():
        if kw in text:
            if name not in mentioned_competitors:
                mentioned_competitors.append(name)
    item["competitors"] = mentioned_competitors

    # ── Badges (Performance DSP categories) ──────────────
    badges = []
    BADGE_RULES = [
        {"name": "SKAN/ATT", "color": "#8b5cf6",
         "keywords": ["skan", "skadnetwork", "att", "idfa", "idfv", "app tracking", "privacy sandbox"]},
        {"name": "UA", "color": "#3b82f6",
         "keywords": ["user acquisition", "app install", "cpi", "campaign optimization", "ua "]},
        {"name": "Bidding", "color": "#ef4444",
         "keywords": ["bid optimization", "bidding", "auction", "floor", "in-app bidding", "rtb"]},
        {"name": "ML/AI", "color": "#10b981",
         "keywords": ["machine learning", "ml ", "predictive", "pcvr", "pltv", "ai ", "agentic"]},
        {"name": "Creative", "color": "#f59e0b",
         "keywords": ["creative", "playable", "rewarded video", "interstitial", "dco", "endcard"]},
        {"name": "MMP", "color": "#06b6d4",
         "keywords": ["appsflyer", "adjust", "singular", "kochava", "branch", "mmp", "attribution"]},
        {"name": "Competitor", "color": "#f43f5e",
         "keywords": list(COMPETITORS.keys())},
    ]

    for badge in BADGE_RULES:
        if any(kw in text for kw in badge["keywords"]):
            badges.append({"name": badge["name"], "color": badge["color"]})

    # ── Financial / Earnings indicator ───────────────────
    is_financial = any(kw in text for kw in [
        "earnings", "earnings call", "capex", "revenue", "q4", "q1", "q2", "q3",
        "stock", "ipo", "m&a", "acquisition",
    ])

    # ── Why it matters + Suggested action ────────────────
    why_matters, action = _generate_card_insights(item, text, topic_tags, impact_types)

    item["relevanceScore"] = score
    item["topicTags"] = sorted(topic_tags)
    item["impactTypes"] = sorted(impact_types)
    item["badges"] = badges
    item["isFinancial"] = is_financial
    item["whyMatters"] = why_matters
    item["suggestedAction"] = action

    return item


def _generate_card_insights(item: dict, text: str, tags: set, impacts: set) -> tuple[str, str]:
    """Generate 'Why it matters' and 'Suggested action' — performance DSP framing."""
    source = item.get("source_name", "")
    competitors = item.get("competitors", [])

    # Default
    why = "Relevant signal for the performance DSP ecosystem."
    action = "Skim for key takeaways relevant to your DSP roadmap."

    if "competitor" in impacts and competitors:
        comp_str = ", ".join(competitors[:3])
        why = f"Competitor intelligence: {comp_str}. Their moves directly affect your market positioning, pricing, and feature roadmap."
        action = f"Analyse {comp_str}'s strategy shift. Assess impact on your UA offering and client pitch."
    elif "bidding" in impacts:
        why = "Bidding mechanics are the core engine of your DSP. Changes here directly impact win rates, CPI, and ROAS."
        action = "Review your bid optimization models. Evaluate if your ML pipeline needs retraining or new signals."
    elif "privacy" in impacts:
        why = "SKAN/ATT changes redefine what data your DSP can access for targeting and attribution."
        action = "Audit your SKAN 4.0 implementation. Ensure your conversion models work with limited postbacks."
    elif "measurement" in impacts:
        why = "Attribution shifts change how advertisers evaluate your DSP vs competitors like Moloco or AppLovin."
        action = "Update your MMP integrations. Build incrementality testing into your reporting dashboard."
    elif "ML" in impacts:
        why = "ML is the differentiator between commodity DSPs and winners. Moloco built their entire moat on this."
        action = "Benchmark your pCVR/pLTV models. Invest in feature engineering and training data quality."
    elif "UA" in impacts:
        why = "User acquisition strategy and CPI/ROAS economics are what your advertiser clients live and die by."
        action = "Review your campaign optimization algorithms. Ensure your DSP delivers better ROAS than competitors."
    elif "creative" in impacts:
        why = "Creative is the #1 lever for performance — playables and rewarded video drive significantly higher CVR."
        action = "Build creative testing and DCO capabilities. Automate endcard generation and A/B testing."
    elif "monetization" in impacts:
        why = "Mediation and monetization trends determine your supply quality and SDK integration priorities."
        action = "Track mediation platform shifts (MAX vs LevelPlay). Optimize your exchange's fill rate and eCPM."
    elif "fraud" in impacts:
        why = "Install fraud costs the industry billions. Anti-fraud is a key selling point for performance DSPs."
        action = "Strengthen your fraud detection pipeline. Consider partnerships with Protect360, TrafficGuard."
    elif "regulation" in impacts:
        why = "DMA, GDPR, and antitrust actions reshape data access, consent flows, and competitive dynamics."
        action = "Review regulatory impact on your data collection. Ensure TCF/consent compliance in all markets."
    elif any(kw in text for kw in ["earnings", "capex", "revenue"]):
        why = "Financials reveal which platforms (AppLovin, Unity, Google) are gaining/losing ad revenue share."
        action = "Track competitor revenue trends to inform your positioning and pricing strategy."
    elif "CTV & Cross-Platform" in tags:
        why = "CTV/cross-platform is the next frontier for performance DSPs expanding beyond mobile."
        action = "Evaluate CTV SDK integration and cross-device graph capabilities for your DSP."

    # Eric Seufert: always top priority
    if any(sk in source.lower() for sk in ["mobile dev memo", "seufert"]):
        why = "Eric Seufert is the #1 analyst for mobile performance DSPs. His takes on SKAN, ATT, and platform economics are essential reading."
        action = "Read every word. Extract implications for your DSP's SKAN strategy, ML models, and competitive positioning."

    return why, action


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 3. TODAY'S KEY SIGNALS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def generate_key_signals(items: list[dict], count: int = 5) -> list[dict]:
    """
    Select the 3–5 most important items as 'Key Signals'.
    Each signal includes: title, source, why_matters, action, relevanceScore.
    """
    sorted_items = sorted(items, key=lambda x: x.get("relevanceScore", 0), reverse=True)

    signals = []
    seen_sources = set()
    seen_impacts = set()

    for item in sorted_items:
        if len(signals) >= count:
            break

        source = item.get("source_name", "")
        impacts = set(item.get("impactTypes", []))

        # Ensure diversity: max 1 per source for signals
        if source in seen_sources:
            continue

        # Prefer items that cover new impact types
        if impacts and impacts.issubset(seen_impacts) and len(signals) >= 2:
            continue

        signals.append({
            "title": item.get("title", ""),
            "source": source,
            "source_type": item.get("source_type", ""),
            "link": item.get("link", ""),
            "relevanceScore": item.get("relevanceScore", 0),
            "why_matters": item.get("whyMatters", ""),
            "action": item.get("suggestedAction", ""),
            "badges": item.get("badges", []),
            "impactTypes": item.get("impactTypes", []),
        })

        seen_sources.add(source)
        seen_impacts.update(impacts)

    return signals


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 4. STRATEGIC THEMES DETECTION
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

THEME_PATTERNS = [
    (r"(?:skadnetwork|skan|att |idfa|app tracking)", "SKAN & ATT"),
    (r"(?:privacy sandbox|cookieless|privacy|gdpr|consent)", "Privacy & Data Access"),
    (r"(?:applovin|unity ads?|ironsource|moloco|liftoff|vungle|smadex|adikteev)", "Competitor Moves"),
    (r"(?:bid optimization|bidding|auction|in-app bidding|rtb|floor)", "Bidding & Auction"),
    (r"(?:machine learning|ml |predictive|pcvr|pltv|ai |agentic)", "ML & Predictive Models"),
    (r"(?:user acquisition|app install|cpi|campaign|ua )", "User Acquisition"),
    (r"(?:roas|ltv|lifetime value|return on ad spend|revenue optim)", "ROAS & LTV"),
    (r"(?:attribution|incrementality|appsflyer|adjust|singular|mmp)", "Measurement & MMP"),
    (r"(?:creative|playable|rewarded video|dco|endcard|interstitial)", "Creative & Ad Formats"),
    (r"(?:mediation|monetization|ecpm|waterfall|fill rate|arpdau)", "Mediation & Monetization"),
    (r"(?:antitrust|regulation|ftc|cma|doj|dma)", "Regulation & Antitrust"),
    (r"(?:mobile gaming|casual game|hyper.casual|app store|google play)", "Mobile Gaming"),
    (r"(?:retargeting|re-engagement|remarketing)", "Retargeting"),
    (r"(?:fraud|ivt|invalid traffic|install fraud)", "Ad Fraud"),
    (r"(?:ctv|streaming|connected tv|cross-platform)", "CTV & Cross-Platform"),
    (r"(?:earnings|revenue|capex|q[1-4]|stock|ipo)", "Financials & Earnings"),
]


def detect_strategic_themes(items: list[dict], top_n: int = 6) -> list[dict]:
    """Detect top strategic themes from content with counts."""
    all_text = " ".join(
        f"{it.get('title', '')} {it.get('summary', '')}" for it in items
    ).lower()

    themes = []
    for pattern, label in THEME_PATTERNS:
        matches = re.findall(pattern, all_text)
        if matches:
            themes.append({"label": label, "count": len(matches)})

    themes.sort(key=lambda x: x["count"], reverse=True)
    return themes[:top_n]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 5. KEY LEARNINGS (10 bullets)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

LEARNING_CATEGORIES = [
    {
        "key": "skan",
        "keywords": ["skan", "skadnetwork", "att", "idfa", "app tracking", "privacy sandbox android"],
        "label": "SKAN & ATT",
        "insights": [
            "SKAN changes redefine what signals your DSP can use for optimization — conversion modeling is now existential.",
            "ATT opt-in rates and SKAN postback quality directly determine your DSP's ability to deliver ROAS.",
        ],
    },
    {
        "key": "competitor",
        "keywords": list(COMPETITORS.keys()),
        "label": "Competitor intel",
        "insights": [
            "competitor moves directly impact your positioning — track AppLovin, Moloco, Unity closely.",
            "the performance DSP market is consolidating — M&A and product launches reshape competitive dynamics weekly.",
        ],
    },
    {
        "key": "bidding",
        "keywords": ["bid optimization", "bidding", "auction", "in-app bidding", "floor", "bid shading"],
        "label": "Bidding & auction",
        "insights": [
            "bidding algorithms are the core moat of a performance DSP — Moloco proved ML-first bidding wins market share.",
            "in-app bidding is replacing waterfall — your DSP needs real-time optimization at sub-100ms latency.",
        ],
    },
    {
        "key": "ml",
        "keywords": ["machine learning", "ml ", "predictive", "pcvr", "pltv", "agentic", "ai agent"],
        "label": "ML & AI",
        "insights": [
            "ML is the #1 differentiator between commodity DSPs and market leaders. Invest in feature engineering and training data.",
            "agentic AI is entering campaign management — automate what humans can't optimize at scale.",
        ],
    },
    {
        "key": "measurement",
        "keywords": ["attribution", "incrementality", "appsflyer", "mmp", "measurement", "adjust", "singular"],
        "label": "Measurement & MMP",
        "insights": [
            "MMP partnerships and incrementality testing define how advertisers evaluate your DSP vs AppLovin or Moloco.",
            "multi-touch attribution and media mix models are replacing last-click — adapt your reporting.",
        ],
    },
    {
        "key": "ua",
        "keywords": ["user acquisition", "app install", "cpi", "roas", "ltv", "campaign optimization"],
        "label": "UA & performance",
        "insights": [
            "CPI and ROAS are the metrics your clients live by — every optimization improvement is a competitive advantage.",
        ],
    },
    {
        "key": "creative",
        "keywords": ["creative", "playable", "rewarded video", "dco", "endcard", "ugc"],
        "label": "Creative optimization",
        "insights": [
            "creative is the #1 performance lever — DSPs with built-in DCO and creative testing win more budgets.",
        ],
    },
    {
        "key": "regulation",
        "keywords": ["antitrust", "regulation", "doj", "ftc", "cma", "dma", "eu"],
        "label": "Regulation",
        "insights": [
            "DMA and antitrust reshape data access for DSPs — Google/Apple policy changes can break your targeting overnight.",
        ],
    },
    {
        "key": "monetization",
        "keywords": ["mediation", "monetization", "ecpm", "waterfall", "fill rate", "levelplay", "max"],
        "label": "Mediation & supply",
        "insights": [
            "mediation shifts (MAX vs LevelPlay) determine supply quality — your DSP's exchange access is at stake.",
        ],
    },
    {
        "key": "earnings",
        "keywords": ["earnings", "revenue", "capex", "stock", "ipo", "growth", "q4", "q1"],
        "label": "Market signals",
        "insights": [
            "AppLovin, Unity, and Google earnings reveal where mobile ad budgets are shifting — track closely.",
        ],
    },
]


def generate_key_learnings(items: list[dict]) -> list:
    """Generate 10 diverse key learnings as dicts with text + link."""
    themes = detect_strategic_themes(items, top_n=3)
    sorted_items = sorted(items, key=lambda x: x.get("relevanceScore", 0), reverse=True)

    learnings = []

    # Top themes overview
    if themes:
        top_labels = ", ".join(t["label"] for t in themes[:3])
        learnings.append({
            "text": f"This week's dominant themes: **{top_labels}** — these are shaping the ad tech conversation right now.",
            "link": "",
            "title": "",
        })

    seen_cats = set()
    insight_idx = {}

    for item in sorted_items:
        if len(learnings) >= 10:
            break

        title = item.get("title", "")
        source = item.get("source_name", "")
        link = item.get("link", "")
        text = f"{title} {item.get('summary', '')}".lower()

        matched = None
        for cat in LEARNING_CATEGORIES:
            if cat["key"] in seen_cats:
                continue
            if any(k in text for k in cat["keywords"]):
                matched = cat
                break

        if not matched:
            if len(learnings) >= 7:
                learnings.append({
                    "text": f"**Worth noting**: *{title}* ({source}) — relevant signal for DSP builders.",
                    "link": link,
                    "title": title,
                })
            continue

        seen_cats.add(matched["key"])
        idx = insight_idx.get(matched["key"], 0)
        insight = matched["insights"][min(idx, len(matched["insights"]) - 1)]
        insight_idx[matched["key"]] = idx + 1

        learnings.append({
            "text": f"**{matched['label']}**: *{title}* ({source}) — {insight}",
            "link": link,
            "title": title,
        })

    return learnings[:10]


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 6. MUST-READ PICKS
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

PREMIUM_SOURCES = {
    "Stratechery": 3,
    "AdExchanger": 2,
    "Marketecture Podcast": 3,
    "Marketecture (Blog)": 3,
    "Mobile Dev Memo": 5,  # Seufert boost
    "ExchangeWire": 2,
    "The AdTechGod Pod": 2,
}


def generate_must_reads(items: list[dict], count: int = 7) -> list[dict]:
    """Select must-read/listen/watch picks."""
    sorted_items = sorted(items, key=lambda x: x.get("relevanceScore", 0), reverse=True)

    picks = []
    source_count = Counter()
    type_count = Counter()

    for item in sorted_items:
        if len(picks) >= count:
            break

        source = item.get("source_name", "")
        stype = item.get("source_type", "")

        if source_count[source] >= 2:
            continue
        if type_count[stype] >= 4:
            continue

        text = f"{item.get('title', '')} {item.get('summary', '')}".lower()
        reason = _explain_pick(item, text)

        picks.append({
            **item,
            "reason": reason,
            "priority": "high" if item.get("relevanceScore", 0) >= 40 else "medium",
        })

        source_count[source] += 1
        type_count[stype] += 1

    return picks


def _explain_pick(item: dict, text: str) -> str:
    """Generate expert curator's reason — performance DSP framing."""
    source = item.get("source_name", "")
    stype = item.get("source_type", "")
    competitors = item.get("competitors", [])
    verb = {"blog": "Read", "podcast": "Listen to", "youtube": "Watch"}.get(stype, "Check out")

    # Seufert = always #1
    if any(sk in source.lower() for sk in ["mobile dev memo", "seufert"]):
        return f"{verb} everything Seufert publishes. His analysis on SKAN, ATT, and mobile DSP economics is the gold standard. Non-negotiable for DSP builders."

    # Competitor intel
    if competitors:
        comp = ", ".join(competitors[:2])
        return f"{verb} for competitor intelligence on {comp}. Their strategy directly impacts your DSP's roadmap and positioning."

    if any(k in text for k in ["skan", "skadnetwork", "att", "idfa"]):
        return f"{verb} completely — SKAN/ATT changes define what your DSP can optimize for. Miss this and your conversion models break."
    elif any(k in text for k in ["bid optimization", "bidding", "auction", "in-app bidding"]):
        return f"{verb} in full — bidding is your DSP's core engine. This directly impacts win rates and CPI."
    elif any(k in text for k in ["machine learning", "ml", "predictive", "pcvr"]):
        return f"{verb} end-to-end — ML is the moat. Moloco proved ML-first DSPs win. Your models need this intelligence."
    elif any(k in text for k in ["attribution", "incrementality", "mmp", "appsflyer"]):
        return f"{verb} fully — how advertisers measure you determines budget allocation. Attribution ≠ optional."
    elif any(k in text for k in ["creative", "playable", "rewarded video", "dco"]):
        return f"{verb} in full — creative is the #1 performance lever. This intelligence improves your DCO strategy."
    elif any(k in text for k in ["antitrust", "regulation", "privacy"]):
        return f"{verb} completely — regulatory shifts can break your targeting stack overnight. Stay ahead."
    elif any(k in text for k in ["earnings", "revenue", "capex"]):
        return f"{verb} for market intelligence — competitor financials reveal where mobile ad spend is shifting."
    elif source in PREMIUM_SOURCES:
        return f"{verb} this fully — {source} delivers depth critical for performance DSP strategy."
    elif stype == "podcast":
        return f"Full episode — long-form gives the nuance on DSP strategy that headlines miss. Perfect for commute."
    else:
        return f"{verb} in full — directly relevant to building a competitive performance DSP."


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# 7. LLM-POWERED VERSIONS (when API key available)
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def _llm_key_signals(items: list[dict], api_key: str, provider: str) -> Optional[list[dict]]:
    """Use LLM to generate key signals with why + action."""
    content = "\n".join(
        f"[{i}] [{it.get('source_name','')}] {it.get('title','')}: {it.get('summary','')[:120]}"
        for i, it in enumerate(items[:30])
    )

    prompt = f"""You are a senior ad tech strategist advising a PM building a performance DSP and exchange.

From this week's content, identify the 5 MOST IMPORTANT items. For each, provide:
INDEX|WHY_IT_MATTERS|SUGGESTED_ACTION

Rules:
- WHY_IT_MATTERS: 1 sentence on business impact for a DSP builder
- SUGGESTED_ACTION: 1 concrete action to take
- Be specific and opinionated. Think like a CTO/CPO.

Content:
{content}

Return exactly 5 lines."""

    try:
        text = _call_llm(prompt, api_key, provider)
        if not text:
            return None

        signals = []
        for line in text.strip().split("\n"):
            parts = line.strip().split("|")
            if len(parts) >= 3:
                try:
                    idx = int(re.search(r"\d+", parts[0]).group())
                    if idx < len(items):
                        it = items[idx]
                        signals.append({
                            "title": it.get("title", ""),
                            "source": it.get("source_name", ""),
                            "source_type": it.get("source_type", ""),
                            "link": it.get("link", ""),
                            "relevanceScore": it.get("relevanceScore", 0),
                            "why_matters": parts[1].strip(),
                            "action": parts[2].strip(),
                            "badges": it.get("badges", []),
                            "impactTypes": it.get("impactTypes", []),
                        })
                except (ValueError, AttributeError):
                    continue

        return signals if signals else None
    except Exception as e:
        print(f"  ⚠ LLM key signals failed: {e}")
        return None


def _call_llm(prompt: str, api_key: str, provider: str) -> Optional[str]:
    """Call LLM and return raw text."""
    try:
        if provider == "anthropic":
            import anthropic
            client = anthropic.Anthropic(api_key=api_key)
            msg = client.messages.create(
                model="claude-sonnet-4-20250514",
                max_tokens=2048,
                messages=[{"role": "user", "content": prompt}],
            )
            return msg.content[0].text
        elif provider == "openai":
            import openai
            client = openai.OpenAI(api_key=api_key)
            resp = client.chat.completions.create(
                model="gpt-4o-mini",
                messages=[{"role": "user", "content": prompt}],
                max_tokens=2048,
            )
            return resp.choices[0].message.content
    except Exception as e:
        print(f"  ⚠ LLM call failed: {e}")
    return None


# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━
# PUBLIC API
# ━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━

def analyze_content(
    items: list[dict],
    anthropic_key: str = "",
    openai_key: str = "",
) -> dict:
    """
    Full intelligence pipeline:
      1. Filter noise
      2. Score all items
      3. Generate key signals, learnings, must-reads, themes
    """
    api_key = anthropic_key or openai_key
    provider = "anthropic" if anthropic_key else "openai"

    # Step 1: Anti-noise filter
    print("  🔇 Filtering marketing noise...")
    clean_items = filter_noise(items)
    filtered_count = len(items) - len(clean_items)
    if filtered_count:
        print(f"     Removed {filtered_count} noise items")

    # Step 2: Score all items
    print("  📊 Scoring relevance (0–100)...")
    scored_items = [score_item(item) for item in clean_items]
    scored_items.sort(key=lambda x: x.get("relevanceScore", 0), reverse=True)

    # Step 3: Key Signals (top 3-5)
    key_signals = None
    if api_key:
        print("  🤖 Generating AI key signals...")
        key_signals = _llm_key_signals(scored_items, api_key, provider)
    if not key_signals:
        print("  ⚡ Extracting key signals...")
        key_signals = generate_key_signals(scored_items, count=5)

    # Step 4: Strategic Themes
    print("  🎯 Detecting strategic themes...")
    themes = detect_strategic_themes(scored_items, top_n=6)

    # Step 5: Key Learnings
    print("  💡 Generating key learnings...")
    key_learnings = generate_key_learnings(scored_items)

    # Step 6: Must-Read Picks
    print("  📌 Selecting must-read picks...")
    must_reads = generate_must_reads(scored_items, count=7)

    return {
        "items": scored_items,
        "key_signals": key_signals,
        "strategic_themes": themes,
        "key_learnings": key_learnings,
        "must_reads": must_reads,
        "stats": {
            "total": len(scored_items),
            "filtered": filtered_count,
            "avg_score": round(sum(it.get("relevanceScore", 0) for it in scored_items) / max(len(scored_items), 1)),
            "high_priority": sum(1 for it in scored_items if it.get("relevanceScore", 0) >= 50),
        },
    }
