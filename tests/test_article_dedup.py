from datetime import datetime, timezone

from src.domain.article_dedup import deduplicate_articles, filter_negative_importance_articles


def _article(**kwargs):
    base = {
        "title": "",
        "url": "",
        "body": "",
        "body_full": "",
        "score": 0,
        "importance_score": 0,
        "final_dt": datetime(2026, 1, 1, tzinfo=timezone.utc),
    }
    base.update(kwargs)
    return base


def _long_text(seed, repeat=80):
    return ((seed + " ") * repeat).strip()


def test_dedup_by_normalized_url_tracking_params():
    articles = [
        _article(title="A", url="https://example.com/news?id=1&utm_source=google", importance_score=3),
        _article(title="A copy", url="https://example.com/news?id=1&fbclid=abc", importance_score=1),
    ]

    deduped, stats = deduplicate_articles(articles)

    assert len(deduped) == 1
    assert deduped[0]["importance_score"] == 3
    assert stats["removed_by_normalized_url"] == 1


def test_dedup_by_title_same_day_with_similar_body():
    body = _long_text("steel market rebounds")
    articles = [
        _article(title="Nippon Steel output up - Reuters", url="https://a.com/1", body=body, body_full=body),
        _article(title="Nippon Steel output up | ロイター", url="https://b.com/2", body=body, body_full=body),
    ]

    deduped, stats = deduplicate_articles(articles)

    assert len(deduped) == 1
    assert stats["removed_by_normalized_title"] == 1


def test_similar_title_but_different_body_is_kept():
    articles = [
        _article(
            title="Plant restart in Chiba Q1",
            url="https://a.com/chiba",
            body=_long_text("capacity 100 mt with blast furnace maintenance"),
            body_full=_long_text("capacity 100 mt with blast furnace maintenance"),
        ),
        _article(
            title="Plant restart in Chiba Q2",
            url="https://b.com/chiba2",
            body=_long_text("new electric arc furnace and different investment"),
            body_full=_long_text("new electric arc furnace and different investment"),
        ),
    ]

    deduped, _ = deduplicate_articles(articles)

    assert len(deduped) == 2


def test_keep_highest_importance_in_duplicates():
    body = _long_text("same article")
    articles = [
        _article(title="Dup", url="https://a.com/dup", body=body, body_full=body, importance_score=1, score=10),
        _article(title="Dup", url="https://b.com/dup", body=body, body_full=body, importance_score=5, score=2),
    ]

    deduped, _ = deduplicate_articles(articles)

    assert len(deduped) == 1
    assert deduped[0]["importance_score"] == 5


def test_filter_negative_importance_for_top5_candidates():
    articles = [
        _article(title="neg", importance_score=-0.1),
        _article(title="zero", importance_score=0),
        _article(title="pos", importance_score=2),
    ]

    kept, removed = filter_negative_importance_articles(articles)

    assert [a["title"] for a in kept] == ["zero", "pos"]
    assert [a["title"] for a in removed] == ["neg"]


def test_negative_importance_can_remain_for_storage():
    articles = [
        _article(title="neg", importance_score=-1),
        _article(title="pos", importance_score=1),
    ]

    deduped, _ = deduplicate_articles(articles)
    kept, removed = filter_negative_importance_articles(deduped)

    assert len(deduped) == 2
    assert len(kept) == 1
    assert len(removed) == 1


def test_dedup_safe_when_body_empty():
    articles = [
        _article(title="A", url="https://a.com/1", body="", body_full=""),
        _article(title="B", url="https://a.com/2", body="", body_full=""),
    ]

    deduped, _ = deduplicate_articles(articles)

    assert len(deduped) == 2


def test_dedup_safe_when_final_dt_missing():
    articles = [
        _article(title="A", url="https://a.com/1", final_dt=None),
        _article(title="A", url="https://a.com/1?utm_source=mail", final_dt=None),
    ]

    deduped, stats = deduplicate_articles(articles)

    assert len(deduped) == 1
    assert stats["removed_by_normalized_url"] == 1
