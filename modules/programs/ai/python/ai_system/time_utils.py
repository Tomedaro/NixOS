from datetime import datetime
from zoneinfo import ZoneInfo


def get_timezone(value=None, default="Europe/Paris"):
    return ZoneInfo(value or default)


def now(tz):
    return datetime.now(tz)


def now_iso(tz):
    return now(tz).isoformat(timespec="seconds")


def today(tz):
    return now(tz).strftime("%Y-%m-%d")
