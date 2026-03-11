from src.domain.rule_engine import apply_rule_engine, build_rules


def _importance_label(score):
    if score >= 4.0:
        return "High"
    if score >= 2.5:
        return "Medium"
    return "Low"


def apply_scores(articles, notion_rules):
    engine_rules = build_rules(notion_rules)
    has_importance_rules = any(rule.rule_type == "importance" for rule in engine_rules)

    for article in articles:
        if has_importance_rules:
            result = apply_rule_engine(article, engine_rules)
            score = result["importance_score"]
            reasons = result["importance_reasons"]
        else:
            score, reasons = 0.0, []
        article["score"] = score
        article["importance_score"] = score
        article["importance_reasons"] = "; ".join(reasons)
        article["importance"] = _importance_label(score)
    return articles
