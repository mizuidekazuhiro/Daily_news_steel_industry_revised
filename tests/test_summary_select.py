from src.usecases.summary_select import select_summary_articles


def test_excludes_non_positive_importance():
    articles = [
        {"title": "A", "importance_score": -5},
        {"title": "B", "importance_score": 0},
        {"title": "C", "importance_score": 1},
    ]

    selected = select_summary_articles(articles)

    assert [article["title"] for article in selected] == ["C"]


def test_allows_positive_importance_after_adjustments():
    articles = [
        {"title": "Investment + Stock", "importance_score": 2},
        {"title": "Neutral", "importance_score": 0},
    ]

    selected = select_summary_articles(articles)

    assert [article["title"] for article in selected] == ["Investment + Stock"]


def test_excludes_types_when_requested():
    articles = [
        {"title": "Stock item", "importance_score": 5, "type": "STOCK"},
        {"title": "Business item", "importance_score": 5, "type": "BUSINESS"},
    ]

    selected = select_summary_articles(articles, exclude_types=["stock"])

    assert [article["title"] for article in selected] == ["Business item"]
