from src.domain.rule_engine import apply_rule_engine, build_rules


def _importance_label(score, scorer=None):
    if scorer:
        return scorer.importance_label(score)
    if score >= 4.0:
        return "High"
    if score >= 2.5:
        return "Medium"
    return "Low"


def apply_scores(articles, scorer, notion_rules=None):
    engine_rules = build_rules(notion_rules) if notion_rules else []
    use_notion_importance = any(rule.rule_type == "importance" for rule in engine_rules)

    for article in articles:
        if use_notion_importance:
            result = apply_rule_engine(article, engine_rules)
            score = result["importance_score"]
            reasons = result["importance_reasons"]
        else:
            score, reasons = scorer.score_with_reasons(article) if scorer else (0.0, [])
        article["score"] = score
        article["importance_score"] = score
        article["importance_reasons"] = "; ".join(reasons)
        article["importance"] = _importance_label(score, scorer)
    return articles
