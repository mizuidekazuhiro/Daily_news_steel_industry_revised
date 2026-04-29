from datetime import datetime, timezone

from src.domain.rule_engine import Rule
from src.usecases.summary_select import (
    apply_hard_exclusion,
    select_summary_articles,
    sort_for_summary,
)


def test_negative_importance_not_excluded():
    articles = [
        {"title": "A", "importance_score": -3},
        {"title": "B", "importance_score": 0},
        {"title": "C", "importance_score": 1},
    ]
    selected = select_summary_articles(articles)
    assert [a["title"] for a in selected] == ["A", "B", "C"]


def test_sorted_by_importance_then_datetime():
    now = datetime.now(timezone.utc)
    articles = [
        {"title": "low-new", "importance_score": -1, "final_dt": now},
        {"title": "high-old", "importance_score": 5, "final_dt": now.replace(hour=0)},
        {"title": "high-new", "importance_score": 5, "final_dt": now},
    ]
    sorted_items = sort_for_summary(articles)
    assert [a["title"] for a in sorted_items] == ["high-new", "high-old", "low-new"]


def test_exclude_hard_exclusion_rules():
    rules = [
        Rule("hard_exclusion", "求人", ("recruit",), tuple(), "both", 0.0, 0.0),
    ]
    kept, excluded = apply_hard_exclusion([
        {"title": "steel recruit info", "body": "x"},
        {"title": "steel market", "body": "x"},
    ], rules)
    assert len(kept) == 1 and kept[0]["title"] == "steel market"
    assert len(excluded) == 1


def test_excludes_types_when_requested():
    articles = [
        {"title": "Stock item", "importance_score": 5, "type": "STOCK"},
        {"title": "Business item", "importance_score": 5, "type": "BUSINESS"},
    ]
    selected = select_summary_articles(articles, exclude_types=["stock"])
    assert [article["title"] for article in selected] == ["Business item"]
