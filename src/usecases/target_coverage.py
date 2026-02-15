def build_processing_labels(targets, google_alert_rss):
    """Build sorted processing labels from Serper targets and RSS targets."""
    return sorted(set(targets.keys()) | set(google_alert_rss.keys()))


def summarize_target_coverage(labels, targets, google_alert_rss):
    """Return counts used for diagnostics about loaded targets."""
    serper_queries = sum(len(queries) for queries in targets.values())
    rss_feeds = sum(len(feeds) for feeds in google_alert_rss.values())

    rss_only = 0
    serper_only = 0
    for label in labels:
        has_serper = bool(targets.get(label, []))
        has_rss = bool(google_alert_rss.get(label, []))
        if has_rss and not has_serper:
            rss_only += 1
        if has_serper and not has_rss:
            serper_only += 1

    return {
        "labels": len(labels),
        "serper_queries": serper_queries,
        "rss_feeds": rss_feeds,
        "rss_only": rss_only,
        "serper_only": serper_only,
    }
