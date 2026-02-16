import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime
from zoneinfo import ZoneInfo

JST = ZoneInfo("Asia/Tokyo")


def now_utc():
    return datetime.now(timezone.utc)


def format_dt_jst(dt):
    if not dt:
        return "不明"
    return dt.astimezone(JST).strftime("%Y-%m-%d %H:%M JST")


def ensure_aware_utc(dt):
    if not dt:
        return None
    if dt.tzinfo is None:
        return dt.replace(tzinfo=timezone.utc)
    return dt.astimezone(timezone.utc)


def parse_publish_datetime(text, reference_time):
    if not text:
        return None
    text = text.strip()

    try:
        return ensure_aware_utc(datetime.fromisoformat(text.replace("Z", "+00:00")))
    except ValueError:
        pass

    try:
        return ensure_aware_utc(parsedate_to_datetime(text))
    except (TypeError, ValueError):
        pass

    for fmt in ("%Y/%m/%d", "%Y-%m-%d", "%Y.%m.%d", "%b %d, %Y"):
        try:
            return ensure_aware_utc(datetime.strptime(text, fmt))
        except ValueError:
            pass

    m = re.search(r"(\d+)\s*(hour|day|week)s?\s*ago", text.lower())
    if m:
        hours = int(m.group(1)) * {"hour": 1, "day": 24, "week": 168}[m.group(2)]
        return ensure_aware_utc(reference_time - timedelta(hours=hours))

    m = re.search(r"(\d+)\s*(時間||週)前", text)
    if m:
        hours = int(m.group(1)) * {"時間": 1, "日": 24, "週": 168}[m.group(2)]
        return ensure_aware_utc(reference_time - timedelta(hours=hours))

    return None


def is_within_hours(dt, reference_time, hours=24):
    if not dt:
        return False
    if dt.tzinfo is None:
        dt = dt.replace(tzinfo=timezone.utc)
    else:
        dt = dt.astimezone(timezone.utc)
    if reference_time.tzinfo is None:
        reference_time = reference_time.replace(tzinfo=timezone.utc)
    else:
        reference_time = reference_time.astimezone(timezone.utc)
    return dt >= reference_time - timedelta(hours=hours)


def compute_lookback_window(now_jst):
    """Return lookback window boundaries in JST.

    Monday run targets previous Friday 00:00 JST to Sunday 23:59:59 JST.
    Tuesday-Friday runs target the most recent 24 hours.
    """
    if now_jst.tzinfo is None:
        now_jst = now_jst.replace(tzinfo=JST)
    else:
        now_jst = now_jst.astimezone(JST)

    if now_jst.weekday() == 0:
        monday_start = now_jst.replace(hour=0, minute=0, second=0, microsecond=0)
        start = monday_start - timedelta(days=3)
        end = monday_start - timedelta(seconds=1)
        return start, end

    return now_jst - timedelta(hours=24), now_jst


def is_within_window(dt, start, end):
    if not dt:
        return False
    dt_utc = ensure_aware_utc(dt)
    start_utc = ensure_aware_utc(start)
    end_utc = ensure_aware_utc(end)
    return start_utc <= dt_utc <= end_utc
