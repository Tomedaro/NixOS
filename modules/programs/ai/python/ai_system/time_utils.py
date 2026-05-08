import os
from datetime import datetime
from zoneinfo import ZoneInfo


def get_timezone(value=None, default=None):
    fallback = default or os.environ.get("AI_TIMEZONE", "Europe/Paris")
    return ZoneInfo(value or fallback)


def now(tz):
    return datetime.now(tz)


def now_iso(tz):
    return now(tz).isoformat(timespec="seconds")


def today(tz):
    return now(tz).strftime("%Y-%m-%d")
