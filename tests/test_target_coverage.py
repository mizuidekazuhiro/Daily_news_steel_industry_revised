from src.usecases.target_coverage import build_processing_labels, summarize_target_coverage


def test_build_processing_labels_includes_rss_only_labels():
    targets = {}
    google_alert_rss = {"RSS Only": ["https://example.com/rss"]}

    labels = build_processing_labels(targets, google_alert_rss)

    assert labels == ["RSS Only"]


def test_summarize_target_coverage_counts_only_types():
    targets = {
        "serper-only": ["query-a", "query-b"],
        "both": ["query-c"],
    }
    google_alert_rss = {
        "rss-only": ["https://example.com/rss-only"],
        "both": ["https://example.com/rss-both"],
    }
    labels = build_processing_labels(targets, google_alert_rss)

    stats = summarize_target_coverage(labels, targets, google_alert_rss)

    assert stats == {
        "labels": 3,
        "serper_queries": 3,
        "rss_feeds": 2,
        "rss_only": 1,
        "serper_only": 1,
    }
