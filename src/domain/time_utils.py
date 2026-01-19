import re
from datetime import datetime, timedelta, timezone
from email.utils import parsedate_to_datetime

JST = timezone(timedelta(hours=9))


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
