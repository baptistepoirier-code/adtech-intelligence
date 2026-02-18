#!/usr/bin/env python3
"""Tests for scoring and dedupe stability."""

import os
import sys
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from generate_daily_intel import (
    stable_id,
    deduplicate,
    score_credibility,
    score_recency,
    score_relevance,
    score_priority,
    classify_topics,
    extract_entities,
    normalize_item,
    generate_insights,
    _title_similarity,
)

TAXONOMY = {
    "topics": {
        "bidding": {
            "label": "Bidding & Auctions",
            "signal_type": "Market Structure",
            "weight": 1.0,
            "keywords": ["bid optimization", "rtb", "auction", "bid shading"],
        },
        "skan_att": {
            "label": "SKAN / ATT",
            "signal_type": "Policy",
            "weight": 1.0,
            "keywords": ["skadnetwork", "skan", "att", "idfa"],
        },
    },
    "entities": {
        "companies": [
            {"name": "AppLovin", "aliases": ["applovin", "axon"], "type": "competitor", "watchlist": True},
            {"name": "Google", "aliases": ["google", "admob"], "type": "platform", "watchlist": True},
        ]
    }
}

STRATEGY = {
    "topic_weights": {"bidding": 1.5, "skan_att": 1.4},
    "entity_weights": {"AppLovin": 1.5, "Google": 1.1},
    "content_type_weights": {"blog": 1.0, "filing": 1.3},
    "hard_triggers": [
        {"pattern": "earnings|10-k", "boost": 20, "signal": "Earnings"},
    ],
}


def test_stable_id_deterministic():
    """Same inputs always produce same ID."""
    id1 = stable_id("AppLovin Q4 Earnings", "https://example.com/applovin")
    id2 = stable_id("AppLovin Q4 Earnings", "https://example.com/applovin")
    assert id1 == id2, f"IDs differ: {id1} vs {id2}"
    id3 = stable_id("Different Title", "https://example.com/applovin")
    assert id1 != id3, "Different titles should produce different IDs"
    print("  [PASS] stable_id is deterministic")


def test_dedupe_url():
    """Duplicate URLs are removed."""
    items = [
        {"id": "a", "title": "AppLovin Reports Record Q4 Earnings Beating All Estimates", "url": "https://example.com/a"},
        {"id": "b", "title": "Unity Announces Major SDK Overhaul For Gaming Developers", "url": "https://example.com/a"},
        {"id": "c", "title": "Google Announces New Privacy Sandbox Features For Chrome Browsers", "url": "https://example.com/c"},
    ]
    result = deduplicate(items)
    assert len(result) == 2, f"Expected 2, got {len(result)}"
    print("  [PASS] URL dedup works")


def test_dedupe_title_similarity():
    """Near-duplicate titles are caught."""
    items = [
        {"id": "a", "title": "AppLovin Reports Record Q4 2024 Earnings", "url": "https://a.com/1"},
        {"id": "b", "title": "AppLovin Reports Record Q4 2024 Earnings Results", "url": "https://b.com/2"},
        {"id": "c", "title": "Completely Different Article", "url": "https://c.com/3"},
    ]
    result = deduplicate(items, threshold=0.75)
    assert len(result) == 2, f"Expected 2, got {len(result)}"
    print("  [PASS] Title similarity dedup works")


def test_title_similarity_score():
    """Verify similarity metric."""
    sim = _title_similarity("AppLovin Q4 2024 Earnings", "AppLovin Q4 2024 Earnings Report")
    assert sim > 0.75, f"Expected >0.75, got {sim}"
    sim2 = _title_similarity("AppLovin Q4 2024 Earnings", "Unity announces new SDK")
    assert sim2 < 0.3, f"Expected <0.3, got {sim2}"
    print("  [PASS] Title similarity scoring")


def test_credibility_scoring():
    """Tier 1 + high weight = high score."""
    item_t1 = {"credibility_weight": 0.95, "source_tier": 1}
    item_t3 = {"credibility_weight": 0.50, "source_tier": 3}
    s1 = score_credibility(item_t1)
    s3 = score_credibility(item_t3)
    assert s1 > s3, f"T1 ({s1}) should beat T3 ({s3})"
    assert 0 <= s1 <= 100
    assert 0 <= s3 <= 100
    print(f"  [PASS] Credibility: T1={s1}, T3={s3}")


def test_relevance_scoring():
    """More topic matches + strategy weight = higher relevance."""
    item_relevant = normalize_item({
        "title": "Bid optimization in RTB auction",
        "source": "AdExchanger", "source_type": "blog", "source_tier": 1,
        "credibility_weight": 0.95, "source_tags": [],
    })
    classify_topics(item_relevant, TAXONOMY)
    extract_entities(item_relevant, TAXONOMY)

    item_irrelevant = normalize_item({
        "title": "New coffee shop opens downtown",
        "source": "Random", "source_type": "blog", "source_tier": 4,
        "credibility_weight": 0.3, "source_tags": [],
    })
    classify_topics(item_irrelevant, TAXONOMY)
    extract_entities(item_irrelevant, TAXONOMY)

    r1 = score_relevance(item_relevant, STRATEGY)
    r2 = score_relevance(item_irrelevant, STRATEGY)
    assert r1 > r2, f"Relevant ({r1}) should beat irrelevant ({r2})"
    print(f"  [PASS] Relevance: relevant={r1}, irrelevant={r2}")


def test_hard_triggers():
    """Earnings trigger adds boost."""
    item = normalize_item({
        "title": "AppLovin 10-K Filing",
        "source": "SEC", "source_type": "filing", "source_tier": 2,
        "credibility_weight": 0.98, "source_tags": ["earnings"],
    })
    classify_topics(item, TAXONOMY)
    item["credibility_score"] = score_credibility(item)
    item["recency_score"] = 50
    item["relevance_score"] = score_relevance(item, STRATEGY)
    p = score_priority(item, STRATEGY)
    assert p > 40, f"Hard trigger should boost priority: {p}"
    print(f"  [PASS] Hard trigger: priority={p}")


def test_topic_classification():
    """Keywords in title match taxonomy topics."""
    item = normalize_item({
        "title": "New SKAN 5 update changes IDFA policy",
        "source": "Apple", "source_type": "blog",
        "source_tags": [], "source_tier": 1, "credibility_weight": 0.95,
    })
    classify_topics(item, TAXONOMY)
    topic_keys = {t["key"] for t in item["topics"]}
    assert "skan_att" in topic_keys, f"Should match skan_att, got {topic_keys}"
    print(f"  [PASS] Classification: {topic_keys}")


def test_entity_extraction():
    """Entity aliases match correctly."""
    item = normalize_item({
        "title": "AppLovin's AXON engine outperforms Google AdMob",
        "source": "AdExchanger", "source_type": "blog",
        "source_tags": [], "source_tier": 1, "credibility_weight": 0.95,
    })
    extract_entities(item, TAXONOMY)
    names = {e["name"] for e in item["entities"]}
    assert "AppLovin" in names, f"Should find AppLovin, got {names}"
    assert "Google" in names, f"Should find Google, got {names}"
    print(f"  [PASS] Entities: {names}")


def test_insight_generation():
    """Insights are non-empty and vary by topic."""
    item = normalize_item({
        "title": "RTB auction changes",
        "source": "Test", "source_type": "blog",
        "source_tags": [], "source_tier": 2, "credibility_weight": 0.7,
    })
    classify_topics(item, TAXONOMY)
    generate_insights(item)
    assert item["why_it_matters"], "why_it_matters should be populated"
    assert item["recommended_action"], "recommended_action should be populated"
    assert "news list" not in item["why_it_matters"].lower()
    print(f"  [PASS] Insights generated: '{item['why_it_matters'][:60]}...'")


def test_scoring_stability():
    """Same item scored twice produces same result."""
    raw = {
        "title": "AppLovin AXON bid optimization update",
        "url": "https://example.com/test",
        "source": "AdExchanger", "source_type": "blog", "source_tier": 1,
        "credibility_weight": 0.95, "source_tags": [], "published_at": "2026-02-15T12:00:00+00:00",
    }
    item1 = normalize_item(raw)
    classify_topics(item1, TAXONOMY)
    extract_entities(item1, TAXONOMY)
    item1["credibility_score"] = score_credibility(item1)
    item1["recency_score"] = score_recency(item1)
    item1["relevance_score"] = score_relevance(item1, STRATEGY)
    p1 = score_priority(item1, STRATEGY)

    item2 = normalize_item(raw)
    classify_topics(item2, TAXONOMY)
    extract_entities(item2, TAXONOMY)
    item2["credibility_score"] = score_credibility(item2)
    item2["recency_score"] = score_recency(item2)
    item2["relevance_score"] = score_relevance(item2, STRATEGY)
    p2 = score_priority(item2, STRATEGY)

    assert p1 == p2, f"Scores differ: {p1} vs {p2}"
    print(f"  [PASS] Scoring is deterministic: {p1} == {p2}")


if __name__ == "__main__":
    print("Running pipeline tests...\n")
    test_stable_id_deterministic()
    test_dedupe_url()
    test_dedupe_title_similarity()
    test_title_similarity_score()
    test_credibility_scoring()
    test_relevance_scoring()
    test_hard_triggers()
    test_topic_classification()
    test_entity_extraction()
    test_insight_generation()
    test_scoring_stability()
    print("\nAll tests passed.")
