"""
Runtime helpers for translated TypeScript code.

Provides Python equivalents for TS/JS runtime features used in the
translated Ghostfolio calculator: Big.js arithmetic, date-fns utilities,
lodash helpers, and safe access patterns.

Deployed alongside the translated implementation — NOT part of the tt tool.
"""
from __future__ import annotations

import copy
import sys
from datetime import datetime, timedelta, date as _date_type
from decimal import Decimal

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATE_FORMAT = "%Y-%m-%d"

# ---------------------------------------------------------------------------
# Attribute-access dict — bridges TS object.prop and Python dict["key"]
# ---------------------------------------------------------------------------


class JSObj(dict):
    """Dict subclass that supports attribute access (like JS objects).

    Missing keys return None instead of raising KeyError, matching
    JavaScript's undefined behavior.
    """

    def __getattr__(self, key):
        return self.get(key)  # returns None for missing

    def __setattr__(self, key, value):
        self[key] = value

    def __delattr__(self, key):
        self.pop(key, None)

    def __missing__(self, key):
        return None  # JS returns undefined for missing keys


# ---------------------------------------------------------------------------
# Nullish coalescing — NOT truthiness!
# In JS: Big(0) is truthy. In Python: Decimal('0') is falsy.
# nvl() checks `is None`, not truthiness.
# ---------------------------------------------------------------------------


def nvl(val, default):
    """Nullish coalescing: return default only if val is None."""
    return default if val is None else val


# ---------------------------------------------------------------------------
# Safe access helpers
# ---------------------------------------------------------------------------


def safe_get(obj, key, default=None):
    """Safe dict/attribute access (replaces optional chaining ?.)."""
    if obj is None:
        return default
    if isinstance(obj, dict):
        return obj.get(key, default)
    return getattr(obj, key, default)


# ---------------------------------------------------------------------------
# Factor helper (replaces getFactor from portfolio.helper)
# ---------------------------------------------------------------------------

_FACTOR_MAP = {"BUY": 1, "SELL": -1}


def get_factor(order_type: str) -> int:
    """Return +1 for BUY, -1 for SELL, 0 otherwise."""
    return _FACTOR_MAP.get(order_type, 0)


# ---------------------------------------------------------------------------
# Date helpers (replaces date-fns)
# ---------------------------------------------------------------------------


def parse_date(s) -> datetime:
    """Parse a date string or return as-is if already datetime."""
    if isinstance(s, datetime):
        return s
    if isinstance(s, _date_type):
        return datetime(s.year, s.month, s.day)
    if isinstance(s, str):
        return datetime.fromisoformat(s)
    return datetime.now()


def format_date(dt, fmt=DATE_FORMAT) -> str:
    """Format a datetime to string."""
    if isinstance(dt, str):
        return dt
    if dt is None:
        return ""
    return dt.strftime(fmt)


def difference_in_days(a, b) -> int:
    """Return (a - b) in days."""
    da = parse_date(a)
    db = parse_date(b)
    return (da - db).days


def is_before(a, b) -> bool:
    """Return True if a < b."""
    return parse_date(a) < parse_date(b)


def add_milliseconds(dt, ms) -> datetime:
    """Add milliseconds to a datetime."""
    return parse_date(dt) + timedelta(milliseconds=ms)


def is_this_year(dt) -> bool:
    """Return True if dt is in the current year."""
    return parse_date(dt).year == datetime.now().year


def each_year_of_interval(interval) -> list[datetime]:
    """Return a datetime for Jan 1 of each year in the interval."""
    if isinstance(interval, dict):
        start = parse_date(interval.get("start") or interval.get("startDate"))
        end = parse_date(interval.get("end") or interval.get("endDate"))
    else:
        return []
    result = []
    year = start.year
    while year <= end.year:
        result.append(datetime(year, 1, 1))
        year += 1
    return result


class Interval:
    """Simple container for date range start/end."""
    def __init__(self, start, end):
        self.start_date = start
        self.end_date = end


def get_interval_from_date_range(date_range: str):
    """Convert a date range string to (start_date, end_date) object."""
    today = datetime.now()
    if date_range == "1d":
        return Interval(today - timedelta(days=1), today)
    elif date_range == "1y":
        return Interval(today.replace(year=today.year - 1), today)
    elif date_range == "5y":
        return Interval(today.replace(year=today.year - 5), today)
    elif date_range == "max":
        return Interval(datetime(1970, 1, 1), today)
    elif date_range == "mtd":
        return Interval(today.replace(day=1), today)
    elif date_range == "wtd":
        # Monday of current week
        start = today - timedelta(days=today.weekday())
        return Interval(start, today)
    elif date_range == "ytd":
        return Interval(today.replace(month=1, day=1), today)
    else:
        # Assume it's a year string like "2021"
        try:
            year = int(date_range)
            return Interval(datetime(year, 1, 1), datetime(year, 12, 31))
        except (ValueError, TypeError):
            return Interval(datetime(1970, 1, 1), today)


# ---------------------------------------------------------------------------
# Logger stub (replaces @nestjs/common Logger)
# ---------------------------------------------------------------------------


class Logger:
    """Stub logger matching NestJS Logger interface."""

    ENABLE_LOGGING = False

    @staticmethod
    def warn(*args):
        if Logger.ENABLE_LOGGING:
            print("WARN:", *args)

    @staticmethod
    def log(*args):
        if Logger.ENABLE_LOGGING:
            print("LOG:", *args)

    @staticmethod
    def error(*args):
        if Logger.ENABLE_LOGGING:
            print("ERROR:", *args)
