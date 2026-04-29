from src.domain.rule_engine import _match_rule, Rule


def importance_value(article):
    value = article.get("importance_score")
    if value is None:
        value = article.get("score")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def extract_hard_exclusion_rules(engine_rules):
    return [rule for rule in (engine_rules or []) if rule.rule_type in {"hard_exclusion", "exclude"}]


def apply_hard_exclusion(articles, hard_exclusion_rules):
    if not hard_exclusion_rules:
        return list(articles), []

    kept, excluded = [], []
    for article in articles:
        title_text = str(article.get("title", "")).lower()
        body_text = str(article.get("body_full") or article.get("body") or "").lower()
        matched = []
        for rule in hard_exclusion_rules:
            if _match_rule(rule, title_text, body_text):
                matched.append(f"{rule.tag_name}({rule.rule_type})")
        if matched:
            cloned = dict(article)
            cloned["hard_exclusion_reasons"] = matched
            excluded.append(cloned)
        else:
            kept.append(article)
    return kept, excluded


def sort_for_summary(articles):
    return sorted(articles, key=lambda x: (importance_value(x), x.get("final_dt")), reverse=True)


def select_summary_articles(articles, *, exclude_types=None):
    exclude_types = {t.lower() for t in (exclude_types or [])}
    selected = []
    for article in articles:
        if exclude_types and (article.get("type") or "").lower() in exclude_types:
            continue
        selected.append(article)
    return selected
