def apply_scores(articles, scorer):
    if not scorer:
        return articles

    for article in articles:
        article["score"] = scorer.score(article)
    return articles
