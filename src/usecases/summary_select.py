def importance_value(article):
    value = article.get("importance_score")
    if value is None:
        value = article.get("score")
    try:
        return float(value)
    except (TypeError, ValueError):
        return 0.0


def select_summary_articles(articles, *, min_importance=0, exclude_types=None):
    exclude_types = {t.lower() for t in (exclude_types or [])}
    selected = []
    for article in articles:
        if exclude_types and (article.get("type") or "").lower() in exclude_types:
            continue
        if importance_value(article) <= min_importance:
            continue
        selected.append(article)
    return selected
