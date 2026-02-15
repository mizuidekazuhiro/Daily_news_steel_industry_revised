from datetime import datetime, timedelta

from src.domain.time_utils import JST, compute_lookback_window


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
