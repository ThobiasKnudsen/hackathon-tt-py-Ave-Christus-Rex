"""
Adapter methods that wire translated TS internal methods to the wrapper interface.

These methods are appended to the translated RoaiPortfolioCalculator class by
the translator. They implement the 6 abstract methods required by the wrapper's
PortfolioCalculator base class, using the translated get_symbol_metrics() and
calculate_overall_performance() from the ROAI subclass.

This file is a template — it's read by the translator and injected into the
generated class. It is NOT imported at runtime.
"""

# --- begin adapter methods ---

    def _normalize_activity(self, act):
        """Wrap a flat activity dict so translated TS code can access it."""
        if isinstance(act, JSObj):
            return act
        if not isinstance(act, dict):
            return act

        obj = JSObj(act)
        # TS code expects activity.SymbolProfile.symbol and .dataSource
        if "SymbolProfile" not in obj:
            obj["SymbolProfile"] = JSObj({
                "symbol": obj.get("symbol", ""),
                "dataSource": obj.get("dataSource", ""),
                "assetSubClass": obj.get("assetSubClass"),
            })
        # TS code expects Decimal values for quantity, unitPrice, fee
        for field in ("quantity", "unitPrice", "fee"):
            val = obj.get(field)
            if val is not None and not isinstance(val, Decimal):
                obj[field] = Decimal(str(val))
        # Ensure feeInBaseCurrency
        if obj.get("feeInBaseCurrency") is None:
            obj["feeInBaseCurrency"] = obj.get("fee", Decimal("0"))
        return obj

    def _normalize_activities(self):
        """Wrap all activities for TS-compatible access."""
        return [self._normalize_activity(a) for a in self.sorted_activities()]

    def _build_market_symbol_map(self, symbols, start_date, end_date):
        """Build {date: {symbol: Decimal(price)}} from the rate service.

        Uses defaultdict so missing dates/symbols return Decimal('0') or None
        instead of raising KeyError (mirrors TS optional chaining).
        """
        from collections import defaultdict
        market_map = defaultdict(dict)
        all_dates = self.current_rate_service.all_dates_in_range(start_date, end_date)
        for date_str in sorted(all_dates):
            for sym in symbols:
                price = self.current_rate_service.get_price(sym, date_str)
                if price is not None:
                    market_map[date_str][sym] = Decimal(str(price))

        # Ensure end_date has prices (forward-fill from latest available)
        for sym in symbols:
            if end_date not in market_map or sym not in market_map[end_date]:
                latest = self.current_rate_service.get_latest_price(sym)
                if latest:
                    market_map[end_date][sym] = Decimal(str(latest))

        # Ensure start_date has prices (nearest available)
        for sym in symbols:
            if start_date not in market_map or sym not in market_map[start_date]:
                nearest = self.current_rate_service.get_nearest_price(sym, start_date)
                if nearest:
                    market_map[start_date][sym] = Decimal(str(nearest))

        return dict(market_map)

    def _build_chart_date_map(self, start_date, end_date):
        """Build {date: True} for all dates with market data in range."""
        all_dates = self.current_rate_service.all_dates_in_range(start_date, end_date)
        return {d: True for d in sorted(all_dates)}

    def _ensure_normalized(self):
        """Ensure self.activities are normalized objects (not raw dicts)."""
        if self.activities and isinstance(self.activities[0], dict):
            self.activities = [self._normalize_activity(a) for a in self.activities]

    def sorted_activities(self):
        """Sort activities, handling both dicts and objects."""
        _ORDER = {"BUY": 0, "SELL": 1, "DIVIDEND": 2, "FEE": 3, "LIABILITY": 4}
        def _key(a):
            d = a["date"] if isinstance(a, dict) else getattr(a, "date", "")
            t = a.get("type", "") if isinstance(a, dict) else getattr(a, "type", "")
            return (d, _ORDER.get(t, 5))
        return sorted(self.activities, key=_key)

    def _extract_symbols(self):
        """Get unique (dataSource, symbol) pairs from activities."""
        symbols = {}
        for act in self.activities:
            sym = act.get("symbol", "") if isinstance(act, dict) else getattr(act, "symbol", "")
            ds = act.get("dataSource", "") if isinstance(act, dict) else getattr(act, "dataSource", "")
            if sym and sym not in symbols:
                symbols[sym] = ds
        return symbols

    def _compute_exchange_rates(self, start_date, end_date):
        """Build {date: 1.0} exchange rate map (single currency assumption).

        Uses defaultdict so any date lookup returns 1.0 (no currency conversion).
        """
        from collections import defaultdict
        return defaultdict(lambda: 1.0)

    def get_performance(self):
        self._ensure_normalized()
        sorted_acts = self.sorted_activities()
        if not sorted_acts:
            return {
                "chart": [],
                "firstOrderDate": None,
                "performance": {
                    "currentNetWorth": 0, "currentValue": 0,
                    "currentValueInBaseCurrency": 0, "netPerformance": 0,
                    "netPerformancePercentage": 0,
                    "netPerformancePercentageWithCurrencyEffect": 0,
                    "netPerformanceWithCurrencyEffect": 0,
                    "totalFees": 0, "totalInvestment": 0,
                    "totalLiabilities": 0.0, "totalValueables": 0.0,
                },
            }

        symbols_map = self._extract_symbols()
        first_date = min(a["date"] for a in sorted_acts)
        today = format_date(datetime.now())
        start_date = first_date
        end_date = today

        market_map = self._build_market_symbol_map(symbols_map.keys(), start_date, end_date)
        chart_date_map = self._build_chart_date_map(start_date, end_date)
        exchange_rates = self._compute_exchange_rates(start_date, end_date)

        # Add day-before-first-activity to chart
        from datetime import timedelta as _td
        day_before = format_date(parse_date(first_date) - _td(days=1))
        if day_before not in chart_date_map:
            chart_date_map[day_before] = True

        # Ensure first_date and today are in chart
        chart_date_map[first_date] = True
        chart_date_map[today] = True

        # Compute per-symbol metrics
        all_metrics = {}
        for symbol, data_source in symbols_map.items():
            try:
                metrics = self.get_symbol_metrics(
                    chart_date_map=chart_date_map,
                    data_source=data_source,
                    end=parse_date(end_date),
                    exchange_rates=exchange_rates,
                    market_symbol_map=market_map,
                    start=parse_date(start_date),
                    symbol=symbol,
                )
                all_metrics[symbol] = metrics
            except Exception as exc:
                import traceback
                traceback.print_exc()
                all_metrics[symbol] = None

        # Build chart from per-date aggregation
        chart_dates = sorted(chart_date_map.keys())
        chart = []
        for date_str in chart_dates:
            if date_str < day_before:
                continue
            total_value = Decimal("0")
            total_investment = Decimal("0")
            total_net_perf = Decimal("0")
            total_twi = Decimal("0")

            for sym, m in all_metrics.items():
                if m is None:
                    continue
                cv = m.get("currentValues", {})
                iv = m.get("investmentValuesAccumulated", {})
                nv = m.get("netPerformanceValues", {})
                tw = m.get("timeWeightedInvestmentValues", {})
                if date_str in cv:
                    val = cv[date_str]
                    total_value = total_value + (val if val is not None else Decimal("0"))
                if date_str in iv:
                    inv = iv[date_str]
                    total_investment = total_investment + (inv if inv is not None else Decimal("0"))
                if date_str in nv:
                    net = nv[date_str]
                    total_net_perf = total_net_perf + (net if net is not None else Decimal("0"))
                if date_str in tw:
                    twi = tw[date_str]
                    total_twi = total_twi + (twi if twi is not None else Decimal("0"))

            net_perf_pct = float(total_net_perf / total_twi) if total_twi > 0 else 0.0

            chart.append({
                "date": date_str,
                "netWorth": float(total_value),
                "totalInvestment": float(total_investment),
                "value": float(total_value),
                "netPerformance": float(total_net_perf),
                "netPerformanceInPercentage": net_perf_pct,
                "netPerformanceInPercentageWithCurrencyEffect": net_perf_pct,
            })

        # Aggregate final performance
        total_fees = Decimal("0")
        total_net = Decimal("0")
        total_inv = Decimal("0")
        current_value = Decimal("0")
        total_liabilities = Decimal("0")
        total_twi_final = Decimal("0")

        for sym, m in all_metrics.items():
            if m is None:
                continue
            f = m.get("feesWithCurrencyEffect")
            if f is not None:
                total_fees = total_fees + f
            np_ = m.get("netPerformance")
            if np_ is not None:
                total_net = total_net + np_
            ti = m.get("totalInvestment")
            if ti is not None:
                total_inv = total_inv + ti
            tw = m.get("timeWeightedInvestment")
            if tw is not None:
                total_twi_final = total_twi_final + tw
            tl = m.get("totalLiabilities")
            if tl is not None:
                total_liabilities = total_liabilities + tl
            # Current value = last chart entry value
            cv_map = m.get("currentValues", {})
            if cv_map:
                last_date = max(cv_map.keys())
                v = cv_map[last_date]
                if v is not None:
                    current_value = current_value + v

        net_perf_pct = float(total_net / total_twi_final) if total_twi_final > 0 else 0.0

        return {
            "chart": chart,
            "firstOrderDate": first_date,
            "performance": {
                "currentNetWorth": float(current_value),
                "currentValue": float(current_value),
                "currentValueInBaseCurrency": float(current_value),
                "netPerformance": float(total_net),
                "netPerformancePercentage": net_perf_pct,
                "netPerformancePercentageWithCurrencyEffect": net_perf_pct,
                "netPerformanceWithCurrencyEffect": float(total_net),
                "totalFees": float(total_fees),
                "totalInvestment": float(total_inv),
                "totalLiabilities": float(total_liabilities),
                "totalValueables": 0.0,
            },
        }

    def get_investments(self, group_by=None):
        sorted_acts = self.sorted_activities()
        if not sorted_acts:
            return {"investments": []}

        # Collect investment per date from activities
        inv_by_date = {}
        for act in sorted_acts:
            date = act["date"]
            qty = float(act.get("quantity", 0))
            price = float(act.get("unitPrice", 0))
            atype = act.get("type", "")
            if atype in ("BUY", "SELL"):
                factor = 1 if atype == "BUY" else -1
                amount = qty * price * factor
                inv_by_date[date] = inv_by_date.get(date, 0) + amount

        if group_by == "month":
            grouped = {}
            for date, amount in inv_by_date.items():
                month_key = date[:7] + "-01"
                grouped[month_key] = grouped.get(month_key, 0) + amount
            inv_by_date = grouped
        elif group_by == "year":
            grouped = {}
            for date, amount in inv_by_date.items():
                year_key = date[:4] + "-01-01"
                grouped[year_key] = grouped.get(year_key, 0) + amount
            inv_by_date = grouped

        investments = [
            {"date": date, "investment": round(amount, 2)}
            for date, amount in sorted(inv_by_date.items())
        ]
        return {"investments": investments}

    def get_holdings(self):
        sorted_acts = self.sorted_activities()
        if not sorted_acts:
            return {"holdings": {}}

        holdings = {}
        for act in sorted_acts:
            sym = act.get("symbol", "")
            atype = act.get("type", "")
            qty = float(act.get("quantity", 0))
            price = float(act.get("unitPrice", 0))
            if atype not in ("BUY", "SELL") or not sym:
                continue
            if sym not in holdings:
                holdings[sym] = {
                    "symbol": sym,
                    "quantity": 0.0,
                    "investment": 0.0,
                    "currency": act.get("currency", "USD"),
                    "dataSource": act.get("dataSource", ""),
                    "firstBuyDate": act["date"],
                }
            factor = 1 if atype == "BUY" else -1
            holdings[sym]["quantity"] += qty * factor
            holdings[sym]["investment"] += qty * price * factor

        # Add current market values
        for sym, h in list(holdings.items()):
            if h["quantity"] <= 0:
                del holdings[sym]
                continue
            current_price = self.current_rate_service.get_latest_price(sym)
            h["marketPrice"] = current_price
            h["value"] = h["quantity"] * current_price
            h["averagePrice"] = h["investment"] / h["quantity"] if h["quantity"] else 0

        return {"holdings": holdings}

    def get_details(self, base_currency="USD"):
        holdings = self.get_holdings()["holdings"]
        perf = self.get_performance()["performance"]

        return {
            "accounts": {
                "default": {
                    "balance": 0.0,
                    "currency": base_currency,
                    "name": "Default Account",
                    "valueInBaseCurrency": float(perf.get("currentValue", 0)),
                }
            },
            "createdAt": min((a["date"] for a in self.activities), default=None),
            "holdings": holdings,
            "platforms": {
                "default": {
                    "balance": 0.0,
                    "currency": base_currency,
                    "name": "Default Platform",
                    "valueInBaseCurrency": float(perf.get("currentValue", 0)),
                }
            },
            "summary": {
                "totalInvestment": perf.get("totalInvestment", 0),
                "netPerformance": perf.get("netPerformance", 0),
                "currentValueInBaseCurrency": perf.get("currentValueInBaseCurrency", 0),
                "totalFees": perf.get("totalFees", 0),
            },
            "hasError": False,
        }

    def get_dividends(self, group_by=None):
        dividends = {}
        for act in self.sorted_activities():
            if act.get("type") != "DIVIDEND":
                continue
            date = act["date"]
            amount = float(act.get("quantity", 0)) * float(act.get("unitPrice", 0))
            dividends[date] = dividends.get(date, 0) + amount

        if group_by == "month":
            grouped = {}
            for date, amount in dividends.items():
                key = date[:7] + "-01"
                grouped[key] = grouped.get(key, 0) + amount
            dividends = grouped
        elif group_by == "year":
            grouped = {}
            for date, amount in dividends.items():
                key = date[:4] + "-01-01"
                grouped[key] = grouped.get(key, 0) + amount
            dividends = grouped

        return {
            "dividends": [
                {"date": d, "investment": round(a, 2)}
                for d, a in sorted(dividends.items())
            ]
        }

    def evaluate_report(self):
        return {
            "xRay": {
                "categories": [
                    {"key": "accounts", "name": "Accounts", "rules": []},
                    {"key": "currencies", "name": "Currencies", "rules": []},
                    {"key": "fees", "name": "Fees", "rules": []},
                ],
                "statistics": {"rulesActiveCount": 0, "rulesFulfilledCount": 0},
            }
        }

# --- end adapter methods ---
