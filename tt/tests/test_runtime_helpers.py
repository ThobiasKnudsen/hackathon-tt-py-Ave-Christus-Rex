"""Tests for runtime helpers — verifying JS/TS → Python equivalence."""
from __future__ import annotations

import pytest
from datetime import datetime, timedelta
from decimal import Decimal

from tt.runtime_helpers import (
    # Safe access
    safe_get, safe_mul, nvl,
    # Big.js
    Big, to_number, to_fixed,
    # date-fns
    parse_date, format_date, difference_in_days,
    is_before, is_after, add_milliseconds, sub_days,
    start_of_day, end_of_day, start_of_year, end_of_year,
    is_this_year, is_within_interval,
    each_day_of_interval, each_year_of_interval, reset_hours, min_date,
    # lodash
    clone_deep, sort_by, uniq_by, is_number, get_sum,
    # Array methods
    array_find, array_find_index, array_at, array_includes,
    # Object methods
    object_keys, object_values, object_entries,
    # Generic helpers
    make_factor_map, make_interval_resolver,
    # Constants
    DATE_FORMAT, EPSILON,
)


# ── Safe access helpers ───────────────────────────────────────

class TestSafeGet:
    def test_single_key(self):
        assert safe_get({"a": 1}, "a") == 1

    def test_nested_keys(self):
        d = {"2021-12-12": {"BTCUSD": Decimal("50098.3")}}
        assert safe_get(d, "2021-12-12", "BTCUSD") == Decimal("50098.3")

    def test_missing_first_key(self):
        d = {"2021-12-12": {"BTCUSD": Decimal("50098.3")}}
        assert safe_get(d, "2099-01-01", "BTCUSD") is None

    def test_missing_second_key(self):
        d = {"2021-12-12": {"BTCUSD": Decimal("50098.3")}}
        assert safe_get(d, "2021-12-12", "GOOGL") is None

    def test_none_input(self):
        assert safe_get(None, "key") is None

    def test_non_dict_intermediate(self):
        d = {"a": "not a dict"}
        assert safe_get(d, "a", "b") is None

    def test_empty_keys(self):
        d = {"a": 1}
        assert safe_get(d) == d


class TestSafeMul:
    def test_normal(self):
        assert safe_mul(Decimal("50"), Decimal("1.1")) == Decimal("55.0")

    def test_none_value(self):
        assert safe_mul(None, Decimal("1.1")) == Decimal("0")

    def test_none_factor(self):
        assert safe_mul(Decimal("50"), None) == Decimal("50")

    def test_both_none(self):
        assert safe_mul(None, None) == Decimal("0")

    def test_custom_default(self):
        assert safe_mul(None, Decimal("1"), default=Decimal("99")) == Decimal("99")

    def test_int_factor(self):
        assert safe_mul(Decimal("10"), 3) == Decimal("30")


class TestNvl:
    def test_non_none(self):
        assert nvl(42, 0) == 42

    def test_none(self):
        assert nvl(None, 0) == 0

    def test_zero_is_not_null(self):
        """Unlike || in JS, ?? only falls back on null/undefined, not 0."""
        assert nvl(0, 99) == 0

    def test_empty_string_is_not_null(self):
        assert nvl("", "default") == ""

    def test_false_is_not_null(self):
        assert nvl(False, True) is False


# ── Big.js → Decimal ──────────────────────────────────────────

class TestBig:
    def test_from_int(self):
        assert Big(0) == Decimal("0")
        assert Big(42) == Decimal("42")

    def test_from_float(self):
        assert Big(3.14) == Decimal("3.14")

    def test_from_string(self):
        assert Big("100.5") == Decimal("100.5")

    def test_from_decimal(self):
        d = Decimal("7")
        assert Big(d) is d  # no copy

    def test_from_none(self):
        assert Big(None) == Decimal("0")

    def test_arithmetic(self):
        a = Big(10)
        b = Big(3)
        assert a + b == Big(13)
        assert a - b == Big(7)
        assert a * b == Big(30)
        assert a / b == pytest.approx(Decimal("3.333333"), abs=Decimal("0.001"))

    def test_comparison(self):
        assert Big(10) > Big(5)
        assert Big(5) == Big(5)
        assert not (Big(0) > Big(0))


class TestToNumber:
    def test_decimal(self):
        assert to_number(Decimal("3.14")) == pytest.approx(3.14)

    def test_none(self):
        assert to_number(None) == 0.0

    def test_int(self):
        assert to_number(42) == 42.0


class TestToFixed:
    def test_two_decimals(self):
        assert to_fixed(Decimal("3.14159"), 2) == "3.14"

    def test_zero_decimals(self):
        assert to_fixed(Decimal("3.7"), 0) == "4"

    def test_rounding(self):
        assert to_fixed(Decimal("2.555"), 2) == "2.56"


# ── date-fns → datetime ──────────────────────────────────────

class TestParseDate:
    def test_iso_string(self):
        dt = parse_date("2021-12-12")
        assert dt.year == 2021 and dt.month == 12 and dt.day == 12

    def test_passthrough_datetime(self):
        dt = datetime(2021, 1, 1)
        assert parse_date(dt) is dt

    def test_date_object(self):
        from datetime import date
        d = date(2021, 6, 15)
        result = parse_date(d)
        assert isinstance(result, datetime)
        assert result.year == 2021

class TestFormatDate:
    def test_default_format(self):
        dt = datetime(2021, 12, 12)
        assert format_date(dt) == "2021-12-12"

    def test_year_format(self):
        dt = datetime(2023, 6, 15)
        assert format_date(dt, "%Y") == "2023"

    def test_from_string(self):
        assert format_date("2021-12-12") == "2021-12-12"


class TestDifferenceInDays:
    def test_positive(self):
        assert difference_in_days("2021-12-15", "2021-12-12") == 3

    def test_zero(self):
        assert difference_in_days("2021-12-12", "2021-12-12") == 0

    def test_negative(self):
        assert difference_in_days("2021-12-10", "2021-12-12") == -2

    def test_datetime_objects(self):
        a = datetime(2021, 12, 15)
        b = datetime(2021, 12, 12)
        assert difference_in_days(a, b) == 3


class TestDateComparisons:
    def test_is_before(self):
        assert is_before("2021-01-01", "2021-12-31")
        assert not is_before("2021-12-31", "2021-01-01")

    def test_is_after(self):
        assert is_after("2021-12-31", "2021-01-01")
        assert not is_after("2021-01-01", "2021-12-31")


class TestDateArithmetic:
    def test_add_milliseconds(self):
        dt = datetime(2021, 12, 12, 0, 0, 0)
        result = add_milliseconds(dt, 1)
        assert result > dt
        assert (result - dt).total_seconds() == pytest.approx(0.001)

    def test_sub_days(self):
        dt = datetime(2021, 12, 12)
        result = sub_days(dt, 3)
        assert result == datetime(2021, 12, 9)

    def test_start_of_day(self):
        dt = datetime(2021, 12, 12, 15, 30, 45)
        result = start_of_day(dt)
        assert result == datetime(2021, 12, 12, 0, 0, 0)

    def test_end_of_day(self):
        dt = datetime(2021, 12, 12, 0, 0, 0)
        result = end_of_day(dt)
        assert result.hour == 23 and result.minute == 59

    def test_start_of_year(self):
        assert start_of_year("2021-06-15") == datetime(2021, 1, 1)

    def test_end_of_year(self):
        result = end_of_year("2021-06-15")
        assert result.month == 12 and result.day == 31

    def test_is_within_interval(self):
        assert is_within_interval("2021-06-15", {
            "start": "2021-01-01", "end": "2021-12-31"
        })
        assert not is_within_interval("2022-01-01", {
            "start": "2021-01-01", "end": "2021-12-31"
        })


class TestDateIntervals:
    def test_each_day_of_interval(self):
        days = each_day_of_interval("2021-12-10", "2021-12-12")
        assert len(days) == 3
        assert days[0].day == 10
        assert days[2].day == 12

    def test_each_year_of_interval(self):
        years = each_year_of_interval("2020-06-01", "2023-03-01")
        assert len(years) == 4  # 2020, 2021, 2022, 2023
        assert years[0].year == 2020
        assert years[-1].year == 2023

    def test_reset_hours(self):
        dt = datetime(2021, 12, 12, 15, 30, 45)
        result = reset_hours(dt)
        assert result.hour == 0 and result.minute == 0

    def test_min_date(self):
        a = datetime(2021, 1, 1)
        b = datetime(2020, 6, 15)
        assert min_date(a, b) == b


# ── lodash → native Python ────────────────────────────────────

class TestCloneDeep:
    def test_deep_copy(self):
        original = {"a": [1, 2, {"b": 3}]}
        cloned = clone_deep(original)
        cloned["a"][2]["b"] = 99
        assert original["a"][2]["b"] == 3  # original unchanged


class TestSortBy:
    def test_sort_by_key(self):
        items = [{"x": 3}, {"x": 1}, {"x": 2}]
        result = sort_by(items, lambda i: i["x"])
        assert [i["x"] for i in result] == [1, 2, 3]

    def test_original_unchanged(self):
        items = [{"x": 3}, {"x": 1}]
        sort_by(items, lambda i: i["x"])
        assert items[0]["x"] == 3  # not mutated


class TestUniqBy:
    def test_dedup(self):
        items = [{"s": "A"}, {"s": "B"}, {"s": "A"}, {"s": "C"}]
        result = uniq_by(items, lambda i: i["s"])
        assert len(result) == 3
        assert [i["s"] for i in result] == ["A", "B", "C"]


class TestIsNumber:
    def test_int(self):
        assert is_number(42)

    def test_float(self):
        assert is_number(3.14)

    def test_decimal(self):
        assert is_number(Decimal("10"))

    def test_bool_is_not_number(self):
        assert not is_number(True)
        assert not is_number(False)

    def test_string_is_not_number(self):
        assert not is_number("42")

    def test_none_is_not_number(self):
        assert not is_number(None)


class TestGetSum:
    def test_sum_decimals(self):
        assert get_sum([Decimal("1"), Decimal("2"), Decimal("3")]) == Decimal("6")

    def test_sum_with_none(self):
        assert get_sum([Decimal("1"), None, Decimal("2")]) == Decimal("3")

    def test_empty(self):
        assert get_sum([]) == Decimal("0")


# ── Array method equivalents ──────────────────────────────────

class TestArrayMethods:
    def test_find(self):
        items = [{"t": "A"}, {"t": "B"}, {"t": "C"}]
        assert array_find(items, lambda i: i["t"] == "B") == {"t": "B"}
        assert array_find(items, lambda i: i["t"] == "Z") is None

    def test_find_index(self):
        items = [{"t": "A"}, {"t": "B"}, {"t": "C"}]
        assert array_find_index(items, lambda i: i["t"] == "B") == 1
        assert array_find_index(items, lambda i: i["t"] == "Z") == -1

    def test_at(self):
        items = [10, 20, 30]
        assert array_at(items, 0) == 10
        assert array_at(items, -1) == 30
        assert array_at(items, 99) is None
        assert array_at([], 0) is None

    def test_includes(self):
        assert array_includes(["BUY", "SELL"], "BUY")
        assert not array_includes(["BUY", "SELL"], "DIVIDEND")


# ── Object helpers ────────────────────────────────────────────

class TestObjectHelpers:
    def test_keys(self):
        assert object_keys({"a": 1, "b": 2}) == ["a", "b"]
        assert object_keys(None) == []

    def test_values(self):
        assert object_values({"a": 1, "b": 2}) == [1, 2]
        assert object_values(None) == []

    def test_entries(self):
        assert object_entries({"a": 1}) == [("a", 1)]
        assert object_entries(None) == []


# ── Ghostfolio-specific helpers ───────────────────────────────

class TestMakeFactorMap:
    """Tests for the generic factor map factory (domain terms stay in output code)."""

    def test_basic_mapping(self):
        get_factor = make_factor_map({"A": 1, "B": -1, "C": 0})
        assert get_factor("A") == 1
        assert get_factor("B") == -1
        assert get_factor("C") == 0

    def test_unknown_returns_zero(self):
        get_factor = make_factor_map({"X": 1})
        assert get_factor("UNKNOWN") == 0


class TestMakeIntervalResolver:
    """Tests for the generic interval resolver factory."""

    def test_year_string(self):
        resolver = make_interval_resolver({})
        result = resolver("2023")
        assert result["startDate"] == datetime(2023, 1, 1)
        assert result["endDate"].year == 2023 and result["endDate"].month == 12

    def test_custom_handler(self):
        resolver = make_interval_resolver({
            "custom": lambda: {"startDate": datetime(2020, 1, 1), "endDate": datetime(2020, 12, 31)},
        })
        result = resolver("custom")
        assert result["startDate"].year == 2020


# ── The truthiness trap ───────────────────────────────────────

class TestTruthinessTraps:
    """These tests document the Big(0) vs Decimal('0') truthiness difference."""

    def test_decimal_zero_is_falsy(self):
        """In Python, Decimal('0') is falsy — unlike Big(0) in JS which is truthy."""
        assert not Decimal("0")
        assert not bool(Decimal("0"))

    def test_is_not_none_for_truthiness(self):
        """The emitter must use 'is not None' instead of truthiness for Big values."""
        value = Decimal("0")  # set but zero
        assert (value is not None) == True   # correct: it IS set
        assert bool(value) == False           # WRONG if used as truthiness check

    def test_none_vs_zero(self):
        """Demonstrate the correct pattern for checking 'is it set?'."""
        set_to_zero = Decimal("0")
        not_set = None

        # Correct: 'is not None' — matches JS truthiness for objects
        assert (set_to_zero is not None) == True
        assert (not_set is not None) == False

        # Wrong: bool() — differs from JS for zero
        assert bool(set_to_zero) == False  # JS: true
        assert bool(not_set) == False       # JS: false (same, but for wrong reason)


# ── Constants ─────────────────────────────────────────────────

class TestConstants:
    def test_date_format(self):
        assert DATE_FORMAT == "%Y-%m-%d"

    def test_epsilon(self):
        assert EPSILON > 0
        assert EPSILON < 0.001
