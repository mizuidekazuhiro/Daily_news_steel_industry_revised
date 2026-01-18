def apply_scores(articles, scorer):
    if not scorer:
        return articles

    for article in articles:
        score, reasons = scorer.score_with_reasons(article)
        article["score"] = score
        article["importance_score"] = score
        article["importance_reasons"] = "; ".join(reasons)
        article["importance"] = scorer.importance_label(score)
    return articles
