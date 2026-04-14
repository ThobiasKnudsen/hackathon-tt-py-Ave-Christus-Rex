"""
Runtime helpers for transpiled TypeScript → Python code.

These functions are injected into the generated Python output to handle
JavaScript/TypeScript patterns that have no direct Python equivalent.
The generated code imports from this module.

Organized by source library:
  - Safe access (optional chaining, nullish coalescing)
  - Big.js → Decimal
  - date-fns → datetime
  - lodash → native Python
  - Array/Object methods
  - Ghostfolio-specific helpers
"""
from __future__ import annotations

import copy
import math
import sys
from datetime import datetime, timedelta, date
from decimal import Decimal, ROUND_HALF_UP, InvalidOperation
from typing import Any

# ---------------------------------------------------------------------------
# Constants
# ---------------------------------------------------------------------------

DATE_FORMAT = "%Y-%m-%d"
EPSILON = sys.float_info.epsilon  # Number.EPSILON equivalent


# ===================================================================
# SAFE ACCESS HELPERS (optional chaining + nullish coalescing)
# ===================================================================

def safe_get(d: dict | None, *keys: str) -> Any:
    """Safe nested dict access. Equivalent to: d[k1]?.[k2]?.[k3]

    Returns None if any key is missing or d is None.

    TS:  marketSymbolMap[dateString]?.[symbol]
    PY:  safe_get(market_symbol_map, date_string, symbol)
    """
    for key in keys:
        if d is None or not isinstance(d, dict):
            return None
        d = d.get(key)
    return d


def safe_mul(value: Decimal | None, factor: Decimal | int | float | None,
             default: Decimal = Decimal("0")) -> Decimal:
    """Safely multiply, handling None on either side.

    TS:  order.unitPriceFromMarketData?.mul(currentExchangeRate ?? 1) ?? new Big(0)
    PY:  safe_mul(order.get("unitPriceFromMarketData"), current_exchange_rate)
    """
    if value is None:
        return default
    if factor is None:
        factor = 1
    return value * _to_decimal(factor)


def nvl(value: Any, default: Any) -> Any:
    """Nullish coalescing: value ?? default.

    Only falls back on None, NOT on falsy values (0, '', False).

    TS:  exchangeRateAtOrderDate ?? 1
    PY:  nvl(exchange_rate_at_order_date, 1)
    """
    return value if value is not None else default


# ===================================================================
# BIG.JS → DECIMAL HELPERS
# ===================================================================

def Big(value: int | float | str | Decimal | None = 0) -> Decimal:
    """Create a Decimal from any value. Equivalent to: new Big(value).

    TS:  new Big(0)
    PY:  Big(0)

    TS:  new Big("3.14")
    PY:  Big("3.14")
    """
    if value is None:
        return Decimal("0")
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def _to_decimal(value: int | float | str | Decimal) -> Decimal:
    """Convert a value to Decimal if it isn't already."""
    if isinstance(value, Decimal):
        return value
    return Decimal(str(value))


def to_number(value: Decimal | int | float | None) -> float:
    """Convert to float. Equivalent to: big.toNumber().

    TS:  x.toNumber()
    PY:  to_number(x)
    """
    if value is None:
        return 0.0
    return float(value)


def to_fixed(value: Decimal | int | float, digits: int = 0) -> str:
    """Format with fixed decimals. Equivalent to: big.toFixed(n).

    TS:  x.toFixed(2)
    PY:  to_fixed(x, 2)
    """
    if not isinstance(value, Decimal):
        value = Decimal(str(value))
    quantize_str = "1." + "0" * digits if digits > 0 else "1"
    return str(value.quantize(Decimal(quantize_str), rounding=ROUND_HALF_UP))


# ===================================================================
# DATE-FNS → DATETIME HELPERS
# ===================================================================

def parse_date(date_str: str) -> datetime:
    """Parse a date string to datetime. Equivalent to: new Date(str) / parseDate.

    TS:  new Date(order.date)
    PY:  parse_date(order["date"])
    """
    if isinstance(date_str, datetime):
        return date_str
    if isinstance(date_str, date):
        return datetime(date_str.year, date_str.month, date_str.day)
    # Handle ISO format and plain date strings
    try:
        return datetime.fromisoformat(date_str)
    except ValueError:
        return datetime.strptime(date_str, DATE_FORMAT)


def format_date(dt: datetime | date | str, fmt: str = DATE_FORMAT) -> str:
    """Format a datetime. Equivalent to: format(date, DATE_FORMAT).

    TS:  format(end, DATE_FORMAT)
    PY:  format_date(end)

    TS:  format(date, 'yyyy')
    PY:  format_date(date, '%Y')
    """
    if isinstance(dt, str):
        dt = parse_date(dt)
    return dt.strftime(fmt)


def difference_in_days(later: datetime | str, earlier: datetime | str) -> int:
    """Days between two dates. Equivalent to: differenceInDays(a, b).

    TS:  differenceInDays(orderDate, previousOrderDate)
    PY:  difference_in_days(order_date, previous_order_date)
    """
    if isinstance(later, str):
        later = parse_date(later)
    if isinstance(earlier, str):
        earlier = parse_date(earlier)
    return (later - earlier).days


def is_before(a: datetime | str, b: datetime | str) -> bool:
    """Check if a is before b. Equivalent to: isBefore(a, b)."""
    if isinstance(a, str):
        a = parse_date(a)
    if isinstance(b, str):
        b = parse_date(b)
    return a < b


def is_after(a: datetime | str, b: datetime | str) -> bool:
    """Check if a is after b. Equivalent to: isAfter(a, b)."""
    if isinstance(a, str):
        a = parse_date(a)
    if isinstance(b, str):
        b = parse_date(b)
    return a > b


def add_milliseconds(dt: datetime | str, ms: int) -> datetime:
    """Add milliseconds. Equivalent to: addMilliseconds(date, ms)."""
    if isinstance(dt, str):
        dt = parse_date(dt)
    return dt + timedelta(milliseconds=ms)


def sub_days(dt: datetime | str, days: int) -> datetime:
    """Subtract days. Equivalent to: subDays(date, n)."""
    if isinstance(dt, str):
        dt = parse_date(dt)
    return dt - timedelta(days=days)


def start_of_day(dt: datetime | str) -> datetime:
    """Start of day. Equivalent to: startOfDay(date)."""
    if isinstance(dt, str):
        dt = parse_date(dt)
    return dt.replace(hour=0, minute=0, second=0, microsecond=0)


def end_of_day(dt: datetime | str) -> datetime:
    """End of day. Equivalent to: endOfDay(date)."""
    if isinstance(dt, str):
        dt = parse_date(dt)
    return dt.replace(hour=23, minute=59, second=59, microsecond=999999)


def start_of_year(dt: datetime | str) -> datetime:
    """Start of year. Equivalent to: startOfYear(date)."""
    if isinstance(dt, str):
        dt = parse_date(dt)
    return datetime(dt.year, 1, 1)


def end_of_year(dt: datetime | str) -> datetime:
    """End of year. Equivalent to: endOfYear(date)."""
    if isinstance(dt, str):
        dt = parse_date(dt)
    return datetime(dt.year, 12, 31, 23, 59, 59, 999999)


def is_this_year(dt: datetime | str) -> bool:
    """Check if date is in current year. Equivalent to: isThisYear(date)."""
    if isinstance(dt, str):
        dt = parse_date(dt)
    return dt.year == datetime.now().year


def is_within_interval(dt: datetime | str,
                       interval: dict) -> bool:
    """Check if date is within interval. Equivalent to: isWithinInterval(date, {start, end})."""
    if isinstance(dt, str):
        dt = parse_date(dt)
    start = interval["start"] if isinstance(interval["start"], datetime) else parse_date(interval["start"])
    end = interval["end"] if isinstance(interval["end"], datetime) else parse_date(interval["end"])
    return start <= dt <= end


def each_day_of_interval(start: datetime | str, end: datetime | str) -> list[datetime]:
    """Generate all days in interval. Equivalent to: eachDayOfInterval({start, end}).

    TS:  eachDayOfInterval({ start, end })
    PY:  each_day_of_interval(start, end)
    """
    if isinstance(start, str):
        start = parse_date(start)
    if isinstance(end, str):
        end = parse_date(end)
    days = []
    current = start_of_day(start)
    end_d = start_of_day(end)
    while current <= end_d:
        days.append(current)
        current += timedelta(days=1)
    return days


def each_year_of_interval(start: datetime | str, end: datetime | str) -> list[datetime]:
    """Generate start of each year in interval. Equivalent to: eachYearOfInterval({start, end}).

    TS:  eachYearOfInterval({ end, start })
    PY:  each_year_of_interval(start, end)
    """
    if isinstance(start, str):
        start = parse_date(start)
    if isinstance(end, str):
        end = parse_date(end)
    years = []
    year = start.year
    while year <= end.year:
        years.append(datetime(year, 1, 1))
        year += 1
    return years


def reset_hours(dt: datetime | str) -> datetime:
    """Reset time to midnight. Equivalent to: resetHours(date)."""
    return start_of_day(dt)


def min_date(*dates: datetime) -> datetime:
    """Return the earliest date. Equivalent to: min(dateA, dateB)."""
    return min(dates)


# ===================================================================
# LODASH → NATIVE PYTHON
# ===================================================================

def clone_deep(obj: Any) -> Any:
    """Deep clone. Equivalent to: cloneDeep(obj).

    TS:  cloneDeep(this.activities.filter(...))
    PY:  clone_deep([a for a in self.activities if ...])
    """
    return copy.deepcopy(obj)


def sort_by(arr: list, key_fn) -> list:
    """Sort by key function. Equivalent to: sortBy(arr, fn).

    Returns a new sorted list (does not mutate).

    TS:  sortBy(orders, ({ date }) => new Date(date).getTime())
    PY:  sort_by(orders, lambda o: parse_date(o["date"]).timestamp())
    """
    return sorted(arr, key=key_fn)


def uniq_by(arr: list, key_fn) -> list:
    """Remove duplicates by key. Equivalent to: uniqBy(arr, fn)."""
    seen = set()
    result = []
    for item in arr:
        k = key_fn(item)
        if k not in seen:
            seen.add(k)
            result.append(item)
    return result


def is_number(value: Any) -> bool:
    """Check if value is a number. Equivalent to: isNumber(x)."""
    return isinstance(value, (int, float, Decimal)) and not isinstance(value, bool)


def get_sum(arr: list) -> Decimal:
    """Sum a list of Decimals. Equivalent to: getSum(arr)."""
    result = Decimal("0")
    for item in arr:
        if item is not None:
            result += _to_decimal(item)
    return result


# ===================================================================
# ARRAY METHOD EQUIVALENTS
# ===================================================================

def array_find(arr: list, predicate) -> Any:
    """Find first matching element. Equivalent to: arr.find(fn).

    TS:  arr.find(o => o.type === 'X')
    PY:  array_find(arr, lambda o: o["type"] == "X")
    """
    return next((item for item in arr if predicate(item)), None)


def array_find_index(arr: list, predicate) -> int:
    """Find index of first match. Equivalent to: arr.findIndex(fn).

    Returns -1 if not found (matching JS behavior).

    TS:  orders.findIndex(({ itemType }) => itemType === 'start')
    PY:  array_find_index(orders, lambda o: o.get("itemType") == "start")
    """
    return next((i for i, item in enumerate(arr) if predicate(item)), -1)


def array_at(arr: list, index: int) -> Any:
    """Access element by index. Equivalent to: arr.at(index).

    Returns None for out-of-bounds (matching JS behavior).

    TS:  orders.at(-1)
    PY:  array_at(orders, -1)
    """
    try:
        return arr[index]
    except IndexError:
        return None


def array_includes(arr: list, value: Any) -> bool:
    """Check if value is in array. Equivalent to: arr.includes(value).

    TS:  ['A', 'B'].includes(order.type)
    PY:  order["type"] in ["A", "B"]

    Note: the emitter should prefer `in` operator where possible.
    This function exists for complex cases.
    """
    return value in arr


# ===================================================================
# OBJECT HELPERS
# ===================================================================

def object_keys(d: dict | None) -> list[str]:
    """Get dict keys as list. Equivalent to: Object.keys(obj)."""
    if d is None:
        return []
    return list(d.keys())


def object_values(d: dict | None) -> list:
    """Get dict values as list. Equivalent to: Object.values(obj)."""
    if d is None:
        return []
    return list(d.values())


def object_entries(d: dict | None) -> list[tuple]:
    """Get dict entries as list of tuples. Equivalent to: Object.entries(obj)."""
    if d is None:
        return []
    return list(d.items())


# ===================================================================
# GENERIC HELPERS
# ===================================================================
# NOTE: Ghostfolio-specific helpers (get_factor, get_interval_from_date_range)
# must NOT live in tt/ — they are domain logic and belong in the scaffold
# or generated output. The emitter should place them in the translation output.


def make_factor_map(mapping: dict[str, int]) -> callable:
    """Create a factor lookup function from a mapping dict.

    The emitter generates the actual mapping in the output code,
    keeping domain terms out of tt/.
    """
    def get_factor(activity_type: str) -> int:
        return mapping.get(activity_type, 0)
    return get_factor


def make_interval_resolver(range_handlers: dict) -> callable:
    """Create a date range resolver from a handlers dict.

    The emitter generates the actual range logic in the output code.
    """
    def get_interval(date_range: str) -> dict:
        handler = range_handlers.get(date_range)
        if handler:
            return handler()
        # Try year string
        try:
            year = int(date_range)
            return {
                "startDate": datetime(year, 1, 1),
                "endDate": datetime(year, 12, 31, 23, 59, 59, 999999),
            }
        except ValueError:
            now = datetime.now()
            return {"startDate": datetime(1970, 1, 1), "endDate": end_of_day(now)}
    return get_interval
