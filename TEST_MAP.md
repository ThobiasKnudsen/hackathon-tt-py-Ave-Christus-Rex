# Ghostfolio TT — Test Map & Progress Tracker

**This file is a planning/coordination artifact, not part of the submission.**
It drives Claude agent work and tracks which test clusters are passing.

---

## How to use this file

- **Architect (you):** pick a task below, hand it to a Claude agent with "work on T#" or "work on I#".
- **Agents:** read the task card, confirm the plan, implement, run tests, update Status.
- Keep Status columns current — other agents read them to decide what to pick up.

---

## Naming convention

- **T#** = **Test cluster task.** Finishing it flips a group of tests from red to green. Numbered in rough difficulty order: **T1 = easiest, T9 = hardest**.
- **I#** = **Infrastructure task.** Cross-cutting work not tied to one test cluster. Numbered in rough time order: **I1 = do early, I5 = do last**.

---

## Agent coordination rules

`tt/tt/translator.py` is a single file. Two agents editing it in parallel will collide. Pick one:

- **Serial (default):** one agent owns translator edits at a time. Others run in parallel on non-translator work (runtime helpers, SOLUTION.md, pyscn cleanup, research spikes).
- **Modular (optional upgrade, see I2):** split translator into `tt/tt/passes/*.py` — each agent owns a pass file. Requires an up-front ~20-min refactor.

**Always after a translator change:** `make translate-and-test-ghostfolio_pytx` → inspect → commit with descriptive message. Judges want a gradual commit log.

**Never:**
- Don't touch `app/main.py` or `app/wrapper/` — byte-identical to the example.
- Don't put domain identifiers (`BTCUSD`, `totalInvestment`, `netPerformance`) or financial math inside `tt/tt/`. Keep `tt/` generic. Project-specific import paths go in `tt_import_map.json`.
- Don't embed ≥10-line blocks in `tt/` that appear verbatim in the output.
- Don't copy translations from `tt_example/` — translator must actually translate.

---

## Scoring snapshot (update as you go)

| Metric | Value |
|---|---|
| Baseline passing (scaffold only) | 48 / 135 |
| **Current passing** | _ / 135 |
| Target for top-3 | 90+ |
| pyscn code health | _ / 100 |
| Rule breaches detected | 0 / N |
| Last eval run | _ |

---

## Test harness reference

- Fixture `gf` → returns `(client, access_token)`, fresh user per test, auto-teardown.
- Client methods:
  - `create_user()`, `set_auth()`, `update_user_settings(base_currency)`, `delete_own_user()`
  - `import_activities(activities)`, `seed_market_data(data_source, symbol, prices)`
  - `get_performance(date_range)` → GET `/api/v2/portfolio/performance`
  - `get_investments(group_by, date_range)` → GET `/api/v1/portfolio/investments`
  - `get_holdings(date_range)` → GET `/api/v1/portfolio/holdings`
  - `get_details(date_range)` → GET `/api/v1/portfolio/details`
  - `get_dividends(group_by, date_range)` → GET `/api/v1/portfolio/dividends`
  - `get_report()` → GET `/api/v1/portfolio/report`
- `mock_prices.py` seeds prices for BTCUSD, BALN.SW, MSFT, NOVN.SW, GOOGL, JNUG — plus today@100 (yahoo-mock current price).

---

# Test-cluster tasks (T1–T9, easiest to hardest)

## T1 — Dividends

| Field | Value |
|---|---|
| **Difficulty** | Easiest (structural) |
| **Status** | ☐ Not started |
| **Owner** | — |
| **Tests** | `test_dividends.py` (10) + dividend asserts in `test_remaining_specs.py` (~2) |
| **Endpoints** | `/dividends`, `?groupBy=month`, `?groupBy=year` |
| **TS source** | `getDividends` / `getDividendsByGroup` in `roai/portfolio-calculator.ts` |
| **Done when** | Filter activities by `type=DIVIDEND`, return `{dividends: [{date, investment=qty*unitPrice}]}`, support month/year bucketing. |
| **Shares with** | Grouping helper also used by T2. |
| **Verify** | `-k dividends` — all 10 pass. |

```python
resp = msft_with_dividend.get_dividends()
by_date = {e["date"]: e["investment"] for e in resp["dividends"]}
assert by_date["2021-11-16"] == pytest.approx(0.62, rel=1e-4)
```

---

## T2 — Investment timeline + month/year grouping

| Field | Value |
|---|---|
| **Difficulty** | Easy (cost-basis + grouping) |
| **Status** | ☐ Not started |
| **Owner** | — |
| **Tests** | parts of `test_btcusd.py` (3), `test_novn_buy_and_sell.py` (3), `test_msft_fractional.py` (2), `test_short_cover.py` (1), many of `test_remaining_specs.py` (~10) |
| **Endpoints** | `/investments`, `?groupBy=month`, `?groupBy=year` |
| **TS source** | `getInvestments` + `getInvestmentsByGroup` in base `portfolio-calculator.ts` |
| **Done when** | Flat `{date, investment}` list; grouped variants bucket by first-of-month/year; SELLs reduce investment proportionally. |
| **Shares with** | Grouping helper from T1. |
| **Verify** | `-k "investments and not dividends"` — ~20 pass. |

```python
inv = session.get_investments(group_by="month")
by_date = {e["date"]: e["investment"] for e in inv["investments"]}
assert by_date["2021-12-01"] == pytest.approx(44558.42, rel=1e-4)
```

---

## T3 — Report x-ray structure

| Field | Value |
|---|---|
| **Difficulty** | Easy (structural) |
| **Status** | ☐ Not started |
| **Owner** | — |
| **Tests** | `test_report.py` (9) |
| **Endpoints** | `/report` |
| **TS source** | `evaluateReport` + rule classes under `portfolio/` |
| **Done when** | `{xRay: {categories: [{key, name, rules}], statistics: {rulesActiveCount, rulesFulfilledCount}}}`. Invariants: `fulfilled <= active`, both ≥ 0. |
| **Verify** | `-k report` — all 9 pass. |

```python
assert "xRay" in resp
stats = resp["xRay"]["statistics"]
assert stats["rulesFulfilledCount"] <= stats["rulesActiveCount"]
```

---

## T4 — Market price integration

| Field | Value |
|---|---|
| **Difficulty** | Medium (shared infrastructure) |
| **Status** | ☐ Not started |
| **Owner** | — |
| **Tests** | `test_advanced.py` (10), parts of `test_deeper.py` (~5). Feeds T5 + T6. |
| **Endpoints** | Used indirectly by `/performance`, `/holdings`, `/details` |
| **TS source** | `CurrentRateService` lookups inside calculator. Wrapper already provides the service; translated Python has to call it. |
| **Done when** | Translated calculator pulls `current_rate_service.current_price(symbol)` for market values; chart uses seeded historical prices. |
| **Do this before T5/T6** | Both depend on it. |
| **Verify** | `-k advanced` — 10 pass. |

```python
assert perf["performance"]["currentValueInBaseCurrency"] == pytest.approx(100.0, rel=1e-4)
```

---

## T5 — Details endpoint per-holding

| Field | Value |
|---|---|
| **Difficulty** | Medium |
| **Status** | ☐ Not started |
| **Owner** | — |
| **Tests** | `test_details.py` (17) |
| **Endpoints** | `/details` |
| **TS source** | `getDetails` + `getValueOfAccountsAndPlatforms` |
| **Done when** | `holdings` dict keyed by symbol with `{quantity, investment, marketPrice, netPerformance, netPerformancePercent, ...}`; summary aggregates cross-holding totals. |
| **Depends on** | T4 for market-price assertions (structural half — ~5 tests — ships without it). |
| **Verify** | `-k details` — 17 pass. |

```python
h = _get_holding(resp, "BTCUSD")
assert h["netPerformance"] == pytest.approx(_YAHOO_MOCK_PRICE - 44558.42 - 4.46, rel=1e-3)
```

---

## T6 — Chart history generation

| Field | Value |
|---|---|
| **Difficulty** | Medium-hard (biggest single translation) |
| **Status** | ☐ Not started |
| **Owner** | — |
| **Tests** | `test_btcusd.py` chart (5), `test_advanced.py` chart (2), some in `test_remaining_specs.py` |
| **Endpoints** | `/performance` → `chart` field |
| **TS source** | `computeTransactionPoints` + `getChartDateMap` + historical-value loop in base `portfolio-calculator.ts` (lines ~186-500) |
| **Done when** | Chart entry per date from first activity to today, with `netWorth`, `totalInvestment`, `value`, `netPerformanceInPercentage`, `netPerformanceInPercentageWithCurrencyEffect`. Excludes pre-activity dates; includes year boundaries. |
| **Depends on** | T4. |
| **Verify** | `-k btcusd_chart` — 5 pass. |

```python
entry = by_date["2021-12-12"]
assert entry["netWorth"] == pytest.approx(50098.3, rel=1e-4)
assert entry["netPerformanceInPercentage"] == pytest.approx(0.12422, rel=1e-4)
```

---

## T7 — TWI denominator + net performance percentage

| Field | Value |
|---|---|
| **Difficulty** | Hard (edge case math) |
| **Status** | ☐ Not started |
| **Owner** | — |
| **Tests** | `test_novn_buy_and_sell.py` (2), `test_deeper.py` closed (2), `test_same_day_transactions.py` (3: epsilon guard) |
| **TS source** | percentage branch in `roai/portfolio-calculator.ts` |
| **Done when** | When `totalInvestment == 0` (closed position), denominator = time-weighted investment (TWI). When elapsed days = 0, use `EPSILON` (~2.22e-16) → finite output. |
| **Verify** | `-k "net_performance_percent or same_day"` |

```python
expected = 19.86 / 151.6  # TWI denominator
assert perf["performance"]["netPerformancePercentage"] == pytest.approx(expected, rel=1e-3)
assert math.isfinite(pct)
```

---

## T8 — Short / BUY-to-cover branch

| Field | Value |
|---|---|
| **Difficulty** | Hard (branch logic) |
| **Status** | ☐ Not started |
| **Owner** | — |
| **Tests** | `test_short_cover.py` (5) + BTCUSD short in `test_remaining_specs.py` (2) |
| **TS source** | BUY branch of `computeTransactionPoints` — when current quantity is negative, BUY uses `avgPrice` (not `unitPrice`) for the investment delta. |
| **Done when** | Negative quantity tracking; BUY-to-cover uses avgPrice; closure detection flips position correctly. |

```python
assert perf["performance"]["netPerformance"] == pytest.approx(6998.6, rel=1e-4)
```

---

## T9 — Fractional quantities / zero-closure precision

| Field | Value |
|---|---|
| **Difficulty** | Hard (numerical precision) |
| **Status** | ☐ Not started |
| **Owner** | — |
| **Tests** | `test_msft_fractional.py` (5) |
| **TS source** | Cost-basis math for fractional qty; precision at close. |
| **Done when** | `0.3333 + 0.6667 - 1.0 → 0` at `abs=1e-8`; `totalInvestment → 0` at `abs=1e-4`. |

```python
assert h.get("quantity", 0) == pytest.approx(0.0, abs=1e-8)
```

---

# Infrastructure tasks (I1–I5, time order)

## I1 — Runtime compat helpers *(early, parallel-safe)*

Not inside `tt/`. Generic TS→Python stdlib shim that translated code imports.

- `Decimal`/`Big.js` wrapper (`.plus`, `.minus`, `.times`, `.div`)
- Date range iterator (day-by-day)
- Array ops shims (`map`, `filter`, `reduce` → list comps / functools)
- Period bucketing (date → first-of-month, first-of-year)

Unblocks T4, T5, T6.

**Status:** ☐  **Owner:** —

---

## I2 — Translator pipeline modularization *(early, optional)*

Split `tt/tt/translator.py` into named passes:
- `passes/imports.py` — strip/rewrite imports via `tt_import_map.json`
- `passes/classes.py` — class/constructor/method shape
- `passes/idioms.py` — map `new Big(x).plus(y)` → `Decimal(x)+Decimal(y)` etc.
- `passes/control_flow.py` — for/if/ternary
- `passes/cleanup.py` — braces/semicolons/blank lines

Unlocks parallel translator editing. Also easier to explain to judges ("5 named passes…").

**Status:** ☐  **Owner:** —

---

## I3 — `make detect_rule_breaches` clean *(continuous)*

Must be 0 findings at submission. Run every ~30 min; fix immediately when something trips.

**Status:** ☐  **Owner:** —

---

## I4 — pyscn code quality pass *(late)*

15% of score. After translator is frozen: `make scoring_codequality`, fix duplication, dead code, complexity.

**Status:** ☐  **Owner:** —

---

## I5 — SOLUTION.md writeup *(last)*

Required for submission. Architecture + coding approach. Draft at T+2:00; polish at T+2:40.

**Status:** ☐  **Owner:** —

---

# Suggested execution order

1. **T1 + T2** together (shared grouping helper), one agent, ~45 min.
2. **T3** Report — parallel agent, ~30 min.
3. **I1** Runtime helpers — parallel agent, ~30 min. Unblocks T4-T6.
4. **T4** Market price hook — enables T5 + T6.
5. **T5** Details — quick once T4 exists.
6. **T6** Chart — biggest single translation, longest.
7. **T7 / T8 / T9** — edge cases, polish time.
8. **I4 pyscn + I5 SOLUTION.md** — last 20 min. **I3** runs throughout.
9. **I2** modularization — only if time allows or parallel translator work needed.

Projected: 48 → ~120 if T1-T6 land.

---

# Progress log

| Timestamp | Task | Event |
|---|---|---|
| 2026-04-14 | T0 | Baseline 48/135 |
| | | |
