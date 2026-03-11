from src.usecases.score_articles import apply_scores


def test_apply_scores_without_importance_rules_defaults_to_low_zero():
    articles = [{"title": "a", "body": "b"}]

    apply_scores(articles, notion_rules=[{"rule_type": "country", "tag_name": "JP", "keywords": "鉄鋼"}])

    assert articles[0]["score"] == 0.0
    assert articles[0]["importance"] == "Low"
    assert articles[0]["importance_reasons"] == ""


def test_apply_scores_with_importance_rules_uses_rule_engine():
    articles = [{"title": "大型投資", "body": "設備投資を実施"}]

    apply_scores(
        articles,
        notion_rules=[
            {
                "rule_type": "importance",
                "tag_name": "投資",
                "keywords": "投資",
                "negative_keywords": "",
                "match_field": "both",
                "weight": 5,
                "priority": 0,
            }
        ],
    )

    assert articles[0]["score"] == 5.0
    assert articles[0]["importance"] == "High"
    assert "投資(+5)" in articles[0]["importance_reasons"]
