# CLAUDE.md — Hackathon Context

## Task
Build a Python tool `tt` that translates TypeScript → Python. Target: one TS calculator in the Ghostfolio project. The translated Python must run as a FastAPI app and pass an API test suite.

- **Event**: Oslo Enhanced Hackathon 2026, 15:30–18:30 (3 hours).
- **Deadline**: 18:30 — all coding stops, main branch = final submission.
- **Team**: Thobias, Magnus, Jardar. Each on their own branch. Best scorer's branch merges to main near the end.
- **This branch**: `Jardar`.

## Scoring
- 85% correctness (API tests passed — weighted, harder tests count more)
- 15% Python code quality (pyscn: health, complexity, dead code, duplication, coupling)
- Plus: understanding (judges ask questions), completion time (tie breaker)

## Leaderboard
- Public board: https://thorknowit.grafana.net/public-dashboards/077f9b1465f647c1aa401b0ba3fdd321
- Push a result with `make publish_results` (needs `SUPABASE_URL`, `SUPABASE_ANON_KEY`, `TEAM_NAME` in `.env`; see `dashboards/DASHBOARDS.md`).
- **First team to push gets a goodwill token** from the judges — push the baseline (48 passed) immediately after env setup, then improve from there.

## Translator philosophy
`tt` is a compiler: TS in, Python out, derived at runtime from the TS AST. Domain terms (`BUY`, `quantity`, `investment`, etc.) must never appear as literals inside `tt/tt/`. Self-check: `grep -E "BUY|SELL|quantity|investment|netPerformance|marketPrice|dividend|holding" tt/tt/` → zero hits.

## Hard Rules (enforced by `make detect_rule_breaches`)
1. **No LLMs in `tt`'s runtime.** You may use LLMs to help write `tt`, but when tt runs it must be pure Python.
2. **No project-specific logic in `tt/`.** No hard-coded `@ghostfolio/…` paths, no pre-written finance math, no domain identifiers as string literals. Translator extracts everything from the TS AST.
3. **No node/js tools called from Python.** Translation must happen in Python.
4. **Wrapper is immutable.** `app/main.py` + `app/wrapper/` must be byte-for-byte copies from `translations/ghostfolio_pytx_example/`. Only `app/implementation/` is generated.
5. **AST libraries are allowed.** `tree-sitter`, Python's `ast`, etc. are fine — they're parsers, not translators.
6. **No off-the-shelf TS→Python translators.** (Our contact confirmed: we must write the translation logic ourselves. A parser library like tree-sitter is fine because it only parses; the translation logic is still ours. A library like `ts2python` would NOT be fine.)
7. **Frequent commits required** — git log must show gradual development.

## Baseline (confirmed on Jardar branch)
- **48 passed / 87 failed** using the existing scaffold stub that returns zero/empty shaped responses.
- Full test run takes ~4m 37s.

## Fast iteration loop
Full `spinup_and_test_ghostfolio_pytx.sh` is slow because it reinstalls deps, starts uvicorn, waits 30s for health, then runs all 135 tests.

For dev cycles:
1. **Start server once with reload** (in a separate terminal or background):
   ```bash
   cd translations/ghostfolio_pytx
   uv sync --extra dev --quiet
   PYTHONIOENCODING=utf-8 uv run python -m uvicorn app.main:app --host 127.0.0.1 --port 3335 --reload
   ```
2. **Translate** (regenerates output; uvicorn --reload picks it up):
   ```bash
   PYTHONIOENCODING=utf-8 uv run --project tt tt translate
   ```
3. **Run a targeted test file** (e.g. 9 tests in ~10s):
   ```bash
   GHOSTFOLIO_API_URL=http://localhost:3335 uv run --project tt pytest projecttests/ghostfolio_api/test_btcusd.py -v
   ```
   Add `-x` to stop on first failure, `-k name` to filter.

## Test suite quick map
- `test_no_orders.py` (4) — empty portfolio, already passes
- `test_btcusd.py` (9) — single BUY, chart + holdings + investments by month/year
- `test_btcusd_buy_and_sell_partially.py` — partial SELL cost basis
- `test_novn_buy_and_sell.py` (7) — full liquidation
- `test_msft_fractional.py` (5) — fractional shares
- `test_short_cover.py` (5) — short selling
- `test_same_day_transactions.py` (5) — same-date txns
- `test_dividends.py` (10), `test_deeper.py` (7) — dividend tracking
- `test_details.py` (17) — /details response values
- `test_advanced.py` (10) — chart math (daily net performance)
- `test_report.py` (9) — xRay structure (cheap wins?)
- `test_remaining_specs.py` (47) — broad symbol coverage

Tests that the TS source cost-basis logic covers once it translates correctly:
- `test_btcusd_holding_values`, `test_btcusd_investments_list`, `test_btcusd_investments_by_month/year`
- `test_baln_buy_*`, `test_googl_buy_*` in test_remaining_specs.py
- Most `test_details_holding_*` numeric-value tests

Tests that need the TS chart-generation and market-price-lookup paths to translate:
- All chart entry tests (test_btcusd chart, test_advanced)
- netPerformance % calculations

Note: the translator doesn't "track" or "compute" anything. It converts TS into Python. The TS source is what tracks cost basis — our job is to translate it faithfully.

## Key paths
- `tt/tt/translator.py` — WE EDIT THIS. The translator.
- `tt/tt/cli.py` — CLI entry, runs translate → scaffold setup → translator.
- `tt/tt/scaffold/ghostfolio_pytx/` — files overlaid onto output (currently empty except .keep).
- `translations/ghostfolio_pytx_example/app/implementation/portfolio/calculator/roai/portfolio_calculator.py` — the STUB we must replace with real (translated) logic.
- `translations/ghostfolio_pytx/` — `tt translate` output (gitignored).
- `projects/ghostfolio/apps/api/src/app/portfolio/calculator/roai/portfolio-calculator.ts` (1009 lines) — target TS file.
- `projects/ghostfolio/apps/api/src/app/portfolio/calculator/portfolio-calculator.ts` (1173 lines) — parent TS class (only need 3 overrides from ROAI).
- `projecttests/ghostfolio_api/` — 13 test files, 135 tests.

## Calculator interface (Python must implement)
Stub in `app/implementation/portfolio/calculator/roai/portfolio_calculator.py` defines:
- `get_performance()` → `{chart, firstOrderDate, performance: {...}}`
- `get_investments(group_by)` → `{investments: [{date, investment}]}`
- `get_holdings()` → `{holdings: {symbol: {quantity, investment, marketPrice, netPerformance, ...}}}`
- `get_details(base_currency)` → `{accounts, holdings, summary, ...}`
- `get_dividends(group_by)` → `{dividends: [{date, investment}]}`
- `evaluate_report()` → `{xRay: {categories, statistics}}`

`self.activities` is a list of dicts: `{date, symbol, type, quantity, unitPrice, fee, currency, dataSource}`.
`self.current_rate_service` provides market-price lookups (seeded by tests).
`self.sorted_activities()` returns activities sorted by (date, type-priority).

## Windows gotcha
The CLI uses `→` in a print statement which cp1252 can't encode. Always run with `PYTHONIOENCODING=utf-8`.
