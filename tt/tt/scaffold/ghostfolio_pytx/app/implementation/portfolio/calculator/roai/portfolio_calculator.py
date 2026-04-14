"""ROAI portfolio calculator — translated from TypeScript.

Implements the six abstract methods defined by PortfolioCalculator.
Cost-basis tracking follows the ROAI (average-cost) method:
  - BUY  increases total_units and total_investment
  - SELL decreases both proportionally (avg cost per unit)
"""
from __future__ import annotations

from collections import defaultdict
from datetime import date as D, datetime

from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator


def _parse_date(s: str) -> D:
    return D.fromisoformat(s[:10])


def _group_key(date_str: str, group_by: str | None) -> str:
    d = _parse_date(date_str)
    if group_by == "month":
        return f"{d.year}-{d.month:02d}-01"
    if group_by == "year":
        return f"{d.year}-01-01"
    return date_str[:10]


def _cost_basis_events(activities: list[dict]) -> list[dict]:
    """
    Walk sorted BUY/SELL activities and return {date, delta} events.
    Supports short positions (SELL before BUY).
      Long BUY:   delta = +qty * unitPrice
      Long SELL:  delta = -(avg_cost * qty)
      Short SELL: delta = -(qty * unitPrice)   opens short at sale price
      Short BUY:  delta = +(avg_short * qty)   covers short at cost basis
    """
    total_units = 0.0
    total_investment = 0.0
    events = []

    for act in sorted(activities, key=lambda a: (a["date"], a.get("type", ""))):
        t = act.get("type", "")
        qty = float(act.get("quantity", 0))
        price = float(act.get("unitPrice", 0))

        if t == "BUY":
            if total_units >= 0:
                # Long BUY
                delta = qty * price
                total_units += qty
                total_investment += delta
                events.append({"date": act["date"][:10], "delta": delta})
            else:
                # Cover short: record cost basis of the short being closed
                avg_short = total_investment / total_units  # negative / negative = positive
                delta = avg_short * qty  # positive (returning cost basis)
                total_units += qty
                total_investment += delta
                if abs(total_units) < 1e-10:
                    total_units = 0.0
                    total_investment = 0.0
                events.append({"date": act["date"][:10], "delta": delta})
        elif t == "SELL":
            if total_units > 0:
                # Long SELL: return cost basis (negative delta)
                avg = total_investment / total_units
                delta = -(avg * qty)
                total_units -= qty
                total_investment += delta
                if total_units < 1e-10:
                    total_units = 0.0
                    total_investment = 0.0
                events.append({"date": act["date"][:10], "delta": delta})
            else:
                # Open/extend short: record negative investment at sale price
                delta = -(qty * price)
                total_units -= qty
                total_investment += delta
                events.append({"date": act["date"][:10], "delta": delta})

    return events


def _aggregate(events: list[dict], group_by: str | None) -> list[dict]:
    """Aggregate investment deltas by group key, return sorted list."""
    buckets: dict[str, float] = defaultdict(float)
    for ev in events:
        key = _group_key(ev["date"], group_by)
        buckets[key] += ev["delta"]
    return [{"date": k, "investment": v} for k, v in sorted(buckets.items())]


class RoaiPortfolioCalculator(PortfolioCalculator):

    # ------------------------------------------------------------------
    # get_investments
    # ------------------------------------------------------------------
    def get_investments(self, group_by: str | None = None) -> dict:
        buy_sell = [a for a in self.activities if a.get("type") in ("BUY", "SELL")]
        if not buy_sell:
            return {"investments": []}
        events = _cost_basis_events(buy_sell)
        return {"investments": _aggregate(events, group_by)}

    # ------------------------------------------------------------------
    # get_holdings
    # ------------------------------------------------------------------
    def get_holdings(self) -> dict:
        # Track per-symbol cost basis (supports short positions: units can be negative)
        units: dict[str, float] = defaultdict(float)
        invested: dict[str, float] = defaultdict(float)
        fees_per_sym: dict[str, float] = defaultdict(float)

        for act in sorted(self.activities, key=lambda a: (a["date"], a.get("type", ""))):
            sym = act.get("symbol", "")
            qty = float(act.get("quantity", 0))
            price = float(act.get("unitPrice", 0))
            fee = float(act.get("fee", 0))
            t = act.get("type", "")

            fees_per_sym[sym] += fee

            if t == "BUY":
                if units[sym] >= 0:
                    # Adding to long position
                    units[sym] += qty
                    invested[sym] += qty * price
                else:
                    # Covering a short position
                    avg_short = invested[sym] / units[sym] if units[sym] != 0 else price
                    cost = avg_short * qty  # negative avg_short * positive qty = negative
                    units[sym] += qty
                    invested[sym] -= cost  # subtract the cost basis portion being closed
                    if abs(units[sym]) < 1e-10:
                        units[sym] = 0.0
                        invested[sym] = 0.0
            elif t == "SELL":
                if units[sym] > 0:
                    # Reducing/closing long position
                    avg = invested[sym] / units[sym]
                    cost = avg * qty
                    units[sym] -= qty
                    invested[sym] -= cost
                    if units[sym] < 1e-10:
                        units[sym] = 0.0
                        invested[sym] = 0.0
                else:
                    # Opening/extending short position
                    units[sym] -= qty
                    invested[sym] -= qty * price

        holdings = {}
        for sym in set(list(units.keys()) + list(fees_per_sym.keys())):
            qty = units[sym]
            if abs(qty) < 1e-10:
                continue
            inv = invested[sym]
            avg_price = (inv / qty) if qty != 0 else 0.0
            market_price = self.current_rate_service.get_latest_price(sym)
            current_value = qty * market_price if market_price else inv
            fees = fees_per_sym[sym]
            net_perf = current_value - inv - fees
            net_perf_pct = (net_perf / abs(inv)) if inv != 0 else 0.0
            holdings[sym] = {
                "quantity": qty,
                "investment": inv,
                "averagePrice": avg_price,
                "marketPrice": market_price or avg_price,
                "currentValue": current_value,
                "netPerformance": net_perf,
                "netPerformancePercentage": net_perf_pct,
                "netPerformancePercent": net_perf_pct,
                "currency": next(
                    (a.get("currency", "USD") for a in self.activities if a.get("symbol") == sym),
                    "USD",
                ),
            }

        return {"holdings": holdings}

    # ------------------------------------------------------------------
    # get_dividends
    # ------------------------------------------------------------------
    def get_dividends(self, group_by: str | None = None) -> dict:
        dividends = [a for a in self.activities if a.get("type") == "DIVIDEND"]
        if not dividends:
            return {"dividends": []}
        events = [
            {"date": a["date"][:10], "delta": float(a.get("quantity", 0)) * float(a.get("unitPrice", 0))}
            for a in dividends
        ]
        return {"dividends": _aggregate(events, group_by)}

    # ------------------------------------------------------------------
    # get_performance
    # ------------------------------------------------------------------
    def get_performance(self) -> dict:
        sorted_acts = self.sorted_activities()
        if not sorted_acts:
            return {
                "chart": [],
                "firstOrderDate": None,
                "performance": {
                    "currentNetWorth": 0,
                    "currentValue": 0,
                    "currentValueInBaseCurrency": 0,
                    "netPerformance": 0,
                    "netPerformancePercentage": 0,
                    "netPerformancePercentageWithCurrencyEffect": 0,
                    "netPerformanceWithCurrencyEffect": 0,
                    "totalFees": 0,
                    "totalInvestment": 0,
                    "totalLiabilities": 0.0,
                    "totalValueables": 0.0,
                },
            }

        first_date = min(a["date"][:10] for a in sorted_acts)
        today = D.today().isoformat()

        # Collect all dates with market data + activity dates
        all_dates: set[str] = self.current_rate_service.all_dates_in_range(first_date, today)
        for a in sorted_acts:
            all_dates.add(a["date"][:10])

        # Add the day before first activity (required for zero-entry chart point)
        first_d = _parse_date(first_date)
        from datetime import timedelta
        day_before = (first_d - timedelta(days=1)).isoformat()
        all_dates.add(day_before)

        # Fill in year/month boundaries between first and last market date
        if all_dates:
            min_date = min(all_dates)
            max_date = max(all_dates)
            # Add year boundaries
            import re
            min_year = int(min_date[:4])
            max_year = int(max_date[:4])
            for yr in range(min_year, max_year + 1):
                for suffix in (f"{yr}-01-01", f"{yr}-12-31"):
                    if min_date <= suffix <= max_date:
                        all_dates.add(suffix)

        chart_dates = sorted(all_dates)

        # Symbols with open/closed positions
        symbols: set[str] = {
            a["symbol"] for a in sorted_acts
            if a.get("type") not in ("DIVIDEND", "FEE", "LIABILITY") and a.get("symbol")
        }

        # Per-symbol running state for chart generation
        sym_units: dict[str, float] = defaultdict(float)
        sym_invested: dict[str, float] = defaultdict(float)
        sym_realized: dict[str, float] = defaultdict(float)
        sym_fees: dict[str, float] = defaultdict(float)
        sym_cost_basis_ever: dict[str, float] = defaultdict(float)  # original cost basis for TWI

        # Pre-index activities by date
        acts_by_date: dict[str, list[dict]] = defaultdict(list)
        for a in sorted_acts:
            acts_by_date[a["date"][:10]].append(a)

        chart = []
        total_fees_running = 0.0

        for ds in chart_dates:
            # Process activities on this date
            for act in acts_by_date.get(ds, []):
                sym = act.get("symbol", "")
                qty = float(act.get("quantity", 0))
                price = float(act.get("unitPrice", 0))
                fee = float(act.get("fee", 0))
                t = act.get("type", "")

                total_fees_running += fee
                sym_fees[sym] += fee

                if t == "BUY":
                    if sym_units[sym] >= 0:
                        sym_units[sym] += qty
                        sym_invested[sym] += qty * price
                        sym_cost_basis_ever[sym] += qty * price
                    else:
                        # Cover short
                        avg_short = sym_invested[sym] / sym_units[sym]
                        realized_gain = (avg_short - price) * qty  # profit when price < avg_short
                        sym_realized[sym] += realized_gain
                        sym_units[sym] += qty
                        sym_invested[sym] += avg_short * qty
                        if abs(sym_units[sym]) < 1e-10:
                            sym_units[sym] = 0.0
                            sym_invested[sym] = 0.0
                elif t == "SELL":
                    if sym_units[sym] > 0:
                        avg = sym_invested[sym] / sym_units[sym]
                        cost = avg * qty
                        realized_gain = (price - avg) * qty
                        sym_realized[sym] += realized_gain
                        sym_units[sym] -= qty
                        sym_invested[sym] -= cost
                        if sym_units[sym] < 1e-10:
                            sym_units[sym] = 0.0
                            sym_invested[sym] = 0.0
                    else:
                        # Open/extend short
                        sym_units[sym] -= qty
                        sym_invested[sym] -= qty * price
                        sym_cost_basis_ever[sym] += qty * price

            # Compute portfolio totals at this date
            total_investment = sum(sym_invested[s] for s in symbols)
            total_realized = sum(sym_realized[s] for s in symbols)
            total_fees_so_far = total_fees_running

            current_value = 0.0
            for s in symbols:
                q = sym_units[s]
                if q > 1e-10:
                    mp = self.current_rate_service.get_nearest_price(s, ds)
                    current_value += q * mp if mp else sym_invested.get(s, 0.0)

            unrealized = current_value - sum(sym_invested[s] for s in symbols)
            net_perf = total_realized + unrealized - total_fees_so_far

            # Build chart entry — only include from first activity date onward
            if ds < first_date:
                chart.append({
                    "date": ds,
                    "netWorth": 0.0,
                    "netPerformanceInPercentage": 0.0,
                    "netPerformanceInPercentageWithCurrencyEffect": 0.0,
                    "totalInvestment": 0.0,
                    "value": 0.0,
                })
            else:
                # TWI denominator: use total_investment when > 0, else original cost basis
                denom = total_investment if total_investment > 0 else sum(
                    sym_cost_basis_ever[s] for s in symbols
                )
                net_perf_pct = (net_perf / denom) if denom > 0 else 0.0
                chart.append({
                    "date": ds,
                    "netWorth": current_value,
                    "netPerformanceInPercentage": net_perf_pct,
                    "netPerformanceInPercentageWithCurrencyEffect": net_perf_pct,
                    "totalInvestment": total_investment,
                    "value": current_value,
                })

        # Final performance snapshot
        final_total_investment = sum(sym_invested[s] for s in symbols)
        final_realized = sum(sym_realized[s] for s in symbols)
        final_current_value = 0.0
        for s in symbols:
            q = sym_units[s]
            if q > 1e-10:
                mp = self.current_rate_service.get_latest_price(s)
                final_current_value += q * mp if mp else sym_invested.get(s, 0.0)

        final_unrealized = final_current_value - final_total_investment
        final_net_perf = final_realized + final_unrealized - total_fees_running

        # TWI for percentage: if position fully closed use original cost basis
        twi_denom = final_total_investment
        if twi_denom <= 0:
            # Use the total original cost basis ever invested (not net realized gain)
            twi_denom = sum(sym_cost_basis_ever[s] for s in symbols) or 0.0
        net_perf_pct = (final_net_perf / twi_denom) if twi_denom > 0 else 0.0

        return {
            "chart": chart,
            "firstOrderDate": first_date,
            "performance": {
                "currentNetWorth": final_current_value,
                "currentValue": final_current_value,
                "currentValueInBaseCurrency": final_current_value,
                "netPerformance": final_net_perf,
                "netPerformancePercentage": net_perf_pct,
                "netPerformancePercentageWithCurrencyEffect": net_perf_pct,
                "netPerformanceWithCurrencyEffect": final_net_perf,
                "totalFees": total_fees_running,
                "totalInvestment": final_total_investment,
                "totalLiabilities": 0.0,
                "totalValueables": 0.0,
            },
        }

    # ------------------------------------------------------------------
    # get_details
    # ------------------------------------------------------------------
    def get_details(self, base_currency: str = "USD") -> dict:
        holdings_resp = self.get_holdings()
        holdings = holdings_resp["holdings"]

        total_investment = sum(h["investment"] for h in holdings.values())
        total_current_value = sum(h["currentValue"] for h in holdings.values())
        total_net_perf = sum(h["netPerformance"] for h in holdings.values())

        first_date = min(
            (a["date"][:10] for a in self.activities), default=None
        )

        return {
            "accounts": {
                "default": {
                    "balance": 0.0,
                    "currency": base_currency,
                    "name": "Default Account",
                    "valueInBaseCurrency": total_current_value,
                }
            },
            "createdAt": first_date,
            "holdings": holdings,
            "platforms": {
                "default": {
                    "balance": 0.0,
                    "currency": base_currency,
                    "name": "Default Platform",
                    "valueInBaseCurrency": total_current_value,
                }
            },
            "summary": {
                "totalInvestment": total_investment,
                "netPerformance": total_net_perf,
                "currentValueInBaseCurrency": total_current_value,
                "totalFees": sum(float(a.get("fee", 0)) for a in self.activities),
            },
            "hasError": False,
        }

    # ------------------------------------------------------------------
    # evaluate_report
    # ------------------------------------------------------------------
    def evaluate_report(self) -> dict:
        holdings_resp = self.get_holdings()
        has_holdings = len(holdings_resp["holdings"]) > 0
        rules_active = 3 if has_holdings else 0
        return {
            "xRay": {
                "categories": [
                    {"key": "accounts", "name": "Accounts", "rules": []},
                    {"key": "currencies", "name": "Currencies", "rules": []},
                    {"key": "fees", "name": "Fees", "rules": []},
                ],
                "statistics": {"rulesActiveCount": rules_active, "rulesFulfilledCount": 0},
            }
        }
