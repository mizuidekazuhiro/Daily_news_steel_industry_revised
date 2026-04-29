from datetime import datetime, timedelta, timezone

from src.domain.time_utils import JST, compute_lookback_window, parse_publish_datetime, parse_publish_datetime_from_url


def test_compute_lookback_window_on_monday_weekend_mode():
    now_jst = datetime(2026, 1, 5, 6, 49, tzinfo=JST)  # Monday

    start, end = compute_lookback_window(now_jst)

    assert start == datetime(2026, 1, 2, 0, 0, 0, tzinfo=JST)  # Friday 00:00
    assert end == datetime(2026, 1, 4, 23, 59, 59, tzinfo=JST)  # Sunday 23:59:59


def test_compute_lookback_window_on_tuesday_is_24_hours():
    now_jst = datetime(2026, 1, 6, 6, 49, 30, tzinfo=JST)  # Tuesday

    start, end = compute_lookback_window(now_jst)

    assert end == now_jst
    assert end - start == timedelta(hours=24)


def test_compute_lookback_window_uses_jst_weekday_even_if_input_is_utc():
    now_utc = datetime(2026, 1, 4, 21, 49, tzinfo=timezone.utc)

    start, end = compute_lookback_window(now_utc)

    assert start == datetime(2026, 1, 2, 0, 0, 0, tzinfo=JST)
    assert end == datetime(2026, 1, 4, 23, 59, 59, tzinfo=JST)


def test_compute_lookback_window_on_sunday_is_normal_mode():
    now_jst = datetime(2026, 1, 4, 6, 49, tzinfo=JST)

    start, end = compute_lookback_window(now_jst)

    assert end == now_jst
    assert end - start == timedelta(hours=24)


def test_parse_publish_datetime_from_url_patterns():
    ref = datetime(2026, 4, 29, tzinfo=timezone.utc)
    assert parse_publish_datetime_from_url("https://example.com/2026/04/29/article", ref) == datetime(2026, 4, 29, tzinfo=timezone.utc)
    assert parse_publish_datetime_from_url("https://example.com/news/2026-04-29/article", ref) == datetime(2026, 4, 29, tzinfo=timezone.utc)
    assert parse_publish_datetime_from_url("https://www.reuters.com/world/india/example-2026-03-16/", ref) == datetime(2026, 3, 16, tzinfo=timezone.utc)
    assert parse_publish_datetime_from_url("https://www.japanmetal.com/news-t20260325148191.html", ref) == datetime(2026, 3, 25, tzinfo=timezone.utc)


def test_parse_publish_datetime_from_url_none_and_invalid():
    ref = datetime(2026, 4, 29, tzinfo=timezone.utc)
    assert parse_publish_datetime_from_url("https://example.com/no-date", ref) is None
    assert parse_publish_datetime_from_url("https://example.com/2026-13-40/article", ref) is None


def test_parse_publish_datetime_japanese_relative_dates():
    ref = datetime(2026, 4, 29, 12, 0, tzinfo=timezone.utc)
    assert parse_publish_datetime("3時間前", ref) == datetime(2026, 4, 29, 9, 0, tzinfo=timezone.utc)
    assert parse_publish_datetime("2日前", ref) == datetime(2026, 4, 27, 12, 0, tzinfo=timezone.utc)
    assert parse_publish_datetime("1週前", ref) == datetime(2026, 4, 22, 12, 0, tzinfo=timezone.utc)
