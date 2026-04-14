class RoaiPortfolioCalculator:
    def calculate_overall_performance(self, positions):
        current_value_in_base_currency = _big(0)
        gross_performance = _big(0)
        gross_performance_with_currency_effect = _big(0)
        has_errors = False
        net_performance = _big(0)
        total_fees_with_currency_effect = _big(0)
        total_interest_with_currency_effect = _big(0)
        total_investment = _big(0)
        total_investment_with_currency_effect = _big(0)
        total_time_weighted_investment = _big(0)
        total_time_weighted_investment_with_currency_effect = _big(0)
        for _ in [_ for _ in positions if return include_in_total_asset_value]:
            if current_position.feeInBaseCurrency:
                total_fees_with_currency_effect = (total_fees_with_currency_effect + current_position.feeInBaseCurrency)
            if current_position.valueInBaseCurrency:
                current_value_in_base_currency = (current_value_in_base_currency + current_position.valueInBaseCurrency)
            else:
                has_errors = True
            if current_position.investment:
                total_investment = (total_investment + current_position.investment)
                total_investment_with_currency_effect = (total_investment_with_currency_effect + current_position.investmentWithCurrencyEffect)
            else:
                has_errors = True
            if current_position.grossPerformance:
                gross_performance = (gross_performance + current_position.grossPerformance)
                gross_performance_with_currency_effect = (gross_performance_with_currency_effect + current_position.grossPerformanceWithCurrencyEffect)
                net_performance = (net_performance + current_position.netPerformance)
            elif (not (current_position.quantity == 0)):
                has_errors = True
            if current_position.timeWeightedInvestment:
                total_time_weighted_investment = (total_time_weighted_investment + current_position.timeWeightedInvestment)
                total_time_weighted_investment_with_currency_effect = (total_time_weighted_investment_with_currency_effect + current_position.timeWeightedInvestmentWithCurrencyEffect)
            elif (not (current_position.quantity == 0)):
                Logger.warn(f"Missing historical market data for {current_position.symbol} ({current_position.dataSource})", "PortfolioCalculator")
                has_errors = True
        return {"currentValueInBaseCurrency": current_value_in_base_currency, "hasErrors": has_errors, "positions": positions, "totalFeesWithCurrencyEffect": total_fees_with_currency_effect, "totalInterestWithCurrencyEffect": total_interest_with_currency_effect, "totalInvestment": total_investment, "totalInvestmentWithCurrencyEffect": total_investment_with_currency_effect, "activitiesCount": [_ for _ in self.activities if return (type in ["BUY", "SELL"])].length, "createdAt": _new_date(), "errors": [], "historicalData": [], "totalLiabilitiesWithCurrencyEffect": _big(0)}

    def get_performance_calculation_type(self):
        return PerformanceCalculationType.ROAI

    def get_symbol_metrics(self, **kwargs):
        current_exchange_rate = exchange_rates[format(_new_date(), DATE_FORMAT)]
        current_values = {}
        current_values_with_currency_effect = {}
        fees = _big(0)
        fees_at_start_date = _big(0)
        fees_at_start_date_with_currency_effect = _big(0)
        fees_with_currency_effect = _big(0)
        gross_performance = _big(0)
        gross_performance_with_currency_effect = _big(0)
        gross_performance_at_start_date = _big(0)
        gross_performance_at_start_date_with_currency_effect = _big(0)
        gross_performance_from_sells = _big(0)
        gross_performance_from_sells_with_currency_effect = _big(0)
        initial_value = None
        initial_value_with_currency_effect = None
        investment_at_start_date = None
        investment_at_start_date_with_currency_effect = None
        investment_values_accumulated = {}
        investment_values_accumulated_with_currency_effect = {}
        investment_values_with_currency_effect = {}
        last_average_price = _big(0)
        last_average_price_with_currency_effect = _big(0)
        net_performance_values = {}
        net_performance_values_with_currency_effect = {}
        time_weighted_investment_values = {}
        time_weighted_investment_values_with_currency_effect = {}
        total_account_balance_in_base_currency = _big(0)
        total_dividend = _big(0)
        total_dividend_in_base_currency = _big(0)
        total_interest = _big(0)
        total_interest_in_base_currency = _big(0)
        total_investment = _big(0)
        total_investment_from_buy_transactions = _big(0)
        total_investment_from_buy_transactions_with_currency_effect = _big(0)
        total_investment_with_currency_effect = _big(0)
        total_liabilities = _big(0)
        total_liabilities_in_base_currency = _big(0)
        total_quantity_from_buy_transactions = _big(0)
        total_units = _big(0)
        value_at_start_date = None
        value_at_start_date_with_currency_effect = None
        # Clone orders to keep the original values in this.orders
        orders = clone_deep([_ for _ in self.activities if return (SymbolProfile.symbol == symbol)])
        is_cash = (orders[0].SymbolProfile.assetSubClass == "CASH")
        if (orders.length <= 0):
            return {"currentValues": {}, "currentValuesWithCurrencyEffect": {}, "feesWithCurrencyEffect": _big(0), "grossPerformance": _big(0), "grossPerformancePercentage": _big(0), "grossPerformancePercentageWithCurrencyEffect": _big(0), "grossPerformanceWithCurrencyEffect": _big(0), "hasErrors": False, "initialValue": _big(0), "initialValueWithCurrencyEffect": _big(0), "investmentValuesAccumulated": {}, "investmentValuesAccumulatedWithCurrencyEffect": {}, "investmentValuesWithCurrencyEffect": {}, "netPerformance": _big(0), "netPerformancePercentage": _big(0), "netPerformancePercentageWithCurrencyEffectMap": {}, "netPerformanceValues": {}, "netPerformanceValuesWithCurrencyEffect": {}, "netPerformanceWithCurrencyEffectMap": {}, "timeWeightedInvestment": _big(0), "timeWeightedInvestmentValues": {}, "timeWeightedInvestmentValuesWithCurrencyEffect": {}, "timeWeightedInvestmentWithCurrencyEffect": _big(0), "totalAccountBalanceInBaseCurrency": _big(0), "totalDividend": _big(0), "totalDividendInBaseCurrency": _big(0), "totalInterest": _big(0), "totalInterestInBaseCurrency": _big(0), "totalInvestment": _big(0), "totalInvestmentWithCurrencyEffect": _big(0), "totalLiabilities": _big(0), "totalLiabilitiesInBaseCurrency": _big(0)}
        date_of_first_transaction = _new_date(orders[0].date)
        end_date_string = format(end, DATE_FORMAT)
        start_date_string = format(start, DATE_FORMAT)
        unit_price_at_start_date = market_symbol_map[start_date_string][symbol]
        unit_price_at_end_date = market_symbol_map[end_date_string][symbol]
        latest_activity = orders[(-1)]
        if ((((data_source == "MANUAL") and (latest_activity.type in ["BUY", "SELL"])) and latest_activity.unitPrice) and (not unit_price_at_end_date)):
            # For BUY / SELL activities with a MANUAL data source where no historical market price is available,
            # the calculation should fall back to using the activity’s unit price.
            unit_price_at_end_date = latest_activity.unitPrice
        elif is_cash:
            unit_price_at_end_date = _big(1)
        if ((not unit_price_at_end_date) or (((not unit_price_at_start_date) and is_before(date_of_first_transaction, start)))):
            return {"currentValues": {}, "currentValuesWithCurrencyEffect": {}, "feesWithCurrencyEffect": _big(0), "grossPerformance": _big(0), "grossPerformancePercentage": _big(0), "grossPerformancePercentageWithCurrencyEffect": _big(0), "grossPerformanceWithCurrencyEffect": _big(0), "hasErrors": True, "initialValue": _big(0), "initialValueWithCurrencyEffect": _big(0), "investmentValuesAccumulated": {}, "investmentValuesAccumulatedWithCurrencyEffect": {}, "investmentValuesWithCurrencyEffect": {}, "netPerformance": _big(0), "netPerformancePercentage": _big(0), "netPerformancePercentageWithCurrencyEffectMap": {}, "netPerformanceWithCurrencyEffectMap": {}, "netPerformanceValues": {}, "netPerformanceValuesWithCurrencyEffect": {}, "timeWeightedInvestment": _big(0), "timeWeightedInvestmentValues": {}, "timeWeightedInvestmentValuesWithCurrencyEffect": {}, "timeWeightedInvestmentWithCurrencyEffect": _big(0), "totalAccountBalanceInBaseCurrency": _big(0), "totalDividend": _big(0), "totalDividendInBaseCurrency": _big(0), "totalInterest": _big(0), "totalInterestInBaseCurrency": _big(0), "totalInvestment": _big(0), "totalInvestmentWithCurrencyEffect": _big(0), "totalLiabilities": _big(0), "totalLiabilitiesInBaseCurrency": _big(0)}
        # Add a synthetic order at the start and the end date
        orders.append({"date": start_date_string, "fee": _big(0), "feeInBaseCurrency": _big(0), "itemType": "start", "quantity": _big(0), "SymbolProfile": {"dataSource": data_source, "symbol": symbol, "assetSubClass": ("CASH" if is_cash else None)}, "type": "BUY", "unitPrice": unit_price_at_start_date})
        orders.append({"date": end_date_string, "fee": _big(0), "feeInBaseCurrency": _big(0), "itemType": "end", "SymbolProfile": {"dataSource": data_source, "symbol": symbol, "assetSubClass": ("CASH" if is_cash else None)}, "quantity": _big(0), "type": "BUY", "unitPrice": unit_price_at_end_date})
        last_unit_price = None
        orders_by_date = {}
        for _ in orders:
            orders_by_date[order.date] = (orders_by_date[order.date] or [])
            orders_by_date[order.date].append(order)
        if (not self.chartDates):
            self.chartDates = Object.keys(chart_date_map).sort()
        for _ in self.chartDates:
            if (date_string < start_date_string):
                continue
            elif (date_string > end_date_string):
                break
            if (orders_by_date[date_string].length > 0):
                for _ in orders_by_date[date_string]:
                    order.unitPriceFromMarketData = (market_symbol_map[date_string][symbol] or last_unit_price)
            else:
                orders.append({"date": date_string, "fee": _big(0), "feeInBaseCurrency": _big(0), "quantity": _big(0), "SymbolProfile": {"dataSource": data_source, "symbol": symbol, "assetSubClass": ("CASH" if is_cash else None)}, "type": "BUY", "unitPrice": (market_symbol_map[date_string][symbol] or last_unit_price), "unitPriceFromMarketData": (market_symbol_map[date_string][symbol] or last_unit_price)})
            latest_activity = orders[(-1)]
            last_unit_price = (latest_activity.unitPriceFromMarketData or latest_activity.unitPrice)
        # Sort orders so that the start and end placeholder order are at the correct
        # position
        orders = sort_by(orders, (lambda _: sort_index = _new_date(date)
        if (item_type == "end"):
            sort_index = add_milliseconds(sort_index, 1)
        elif (item_type == "start"):
            sort_index = add_milliseconds(sort_index, (-1))
        return sort_index.getTime()))
        index_of_start_order = orders.findIndex((lambda _: return (item_type == "start")))
        index_of_end_order = orders.findIndex((lambda _: return (item_type == "end")))
        total_investment_days = 0
        sum_of_time_weighted_investments = _big(0)
        sum_of_time_weighted_investments_with_currency_effect = _big(0)
        i = 0
        while (i < orders.length):
            order = orders[i]
            if PortfolioCalculator.ENABLE_LOGGING:
                console.log()
                console.log()
                console.log((i + 1), order.date, order.type, (f"({order.itemType})" if order.itemType else ""))
            exchange_rate_at_order_date = exchange_rates[order.date]
            if (order.type == "DIVIDEND"):
                dividend = (order.quantity * order.unitPrice)
                total_dividend = (total_dividend + dividend)
                total_dividend_in_base_currency = (total_dividend_in_base_currency + (dividend * (exchange_rate_at_order_date or 1)))
            elif (order.type == "INTEREST"):
                interest = (order.quantity * order.unitPrice)
                total_interest = (total_interest + interest)
                total_interest_in_base_currency = (total_interest_in_base_currency + (interest * (exchange_rate_at_order_date or 1)))
            elif (order.type == "LIABILITY"):
                liabilities = (order.quantity * order.unitPrice)
                total_liabilities = (total_liabilities + liabilities)
                total_liabilities_in_base_currency = (total_liabilities_in_base_currency + (liabilities * (exchange_rate_at_order_date or 1)))
            if (order.itemType == "start"):
                # Take the unit price of the order as the market price if there are no
                # orders of this symbol before the start date
                order.unitPrice = (orders[(i + 1)].unitPrice if (index_of_start_order == 0) else unit_price_at_start_date)
            if order.fee:
                order.feeInBaseCurrency = (order.fee * (current_exchange_rate or 1))
                order.feeInBaseCurrencyWithCurrencyEffect = (order.fee * (exchange_rate_at_order_date or 1))
            unit_price = (order.unitPrice if (order.type in ["BUY", "SELL"]) else order.unitPriceFromMarketData)
            if unit_price:
                order.unitPriceInBaseCurrency = (unit_price * (current_exchange_rate or 1))
                order.unitPriceInBaseCurrencyWithCurrencyEffect = (unit_price * (exchange_rate_at_order_date or 1))
            market_price_in_base_currency = ((order.unitPriceFromMarketData * (current_exchange_rate or 1)) or _big(0))
            market_price_in_base_currency_with_currency_effect = ((order.unitPriceFromMarketData * (exchange_rate_at_order_date or 1)) or _big(0))
            value_of_investment_before_transaction = (total_units * market_price_in_base_currency)
            value_of_investment_before_transaction_with_currency_effect = (total_units * market_price_in_base_currency_with_currency_effect)
            if ((not investment_at_start_date) and (i >= index_of_start_order)):
                investment_at_start_date = (total_investment or _big(0))
                investment_at_start_date_with_currency_effect = (total_investment_with_currency_effect or _big(0))
                value_at_start_date = value_of_investment_before_transaction
                value_at_start_date_with_currency_effect = value_of_investment_before_transaction_with_currency_effect
            transaction_investment = _big(0)
            transaction_investment_with_currency_effect = _big(0)
            if (order.type == "BUY"):
                transaction_investment = ((order.quantity * order.unitPriceInBaseCurrency) * get_factor(order.type))
                transaction_investment_with_currency_effect = ((order.quantity * order.unitPriceInBaseCurrencyWithCurrencyEffect) * get_factor(order.type))
                total_quantity_from_buy_transactions = (total_quantity_from_buy_transactions + order.quantity)
                total_investment_from_buy_transactions = (total_investment_from_buy_transactions + transaction_investment)
                total_investment_from_buy_transactions_with_currency_effect = (total_investment_from_buy_transactions_with_currency_effect + transaction_investment_with_currency_effect)
            elif (order.type == "SELL"):
                if (total_units > 0):
                    transaction_investment = (((total_investment / total_units) * order.quantity) * get_factor(order.type))
                    transaction_investment_with_currency_effect = (((total_investment_with_currency_effect / total_units) * order.quantity) * get_factor(order.type))
            if PortfolioCalculator.ENABLE_LOGGING:
                console.log("order.quantity", float(order.quantity))
                console.log("transactionInvestment", float(transaction_investment))
                console.log("transactionInvestmentWithCurrencyEffect", float(transaction_investment_with_currency_effect))
            total_investment_before_transaction = total_investment
            total_investment_before_transaction_with_currency_effect = total_investment_with_currency_effect
            total_investment = (total_investment + transaction_investment)
            total_investment_with_currency_effect = (total_investment_with_currency_effect + transaction_investment_with_currency_effect)
            if ((i >= index_of_start_order) and (not initial_value)):
                if ((i == index_of_start_order) and (not (value_of_investment_before_transaction == 0))):
                    initial_value = value_of_investment_before_transaction
                    initial_value_with_currency_effect = value_of_investment_before_transaction_with_currency_effect
                elif (transaction_investment > 0):
                    initial_value = transaction_investment
                    initial_value_with_currency_effect = transaction_investment_with_currency_effect
            fees = (fees + (order.feeInBaseCurrency or 0))
            fees_with_currency_effect = (fees_with_currency_effect + (order.feeInBaseCurrencyWithCurrencyEffect or 0))
            total_units = (total_units + (order.quantity * get_factor(order.type)))
            value_of_investment = (total_units * market_price_in_base_currency)
            value_of_investment_with_currency_effect = (total_units * market_price_in_base_currency_with_currency_effect)
            gross_performance_from_sell = (((order.unitPriceInBaseCurrency - last_average_price) * order.quantity) if (order.type == "SELL") else _big(0))
            gross_performance_from_sell_with_currency_effect = (((order.unitPriceInBaseCurrencyWithCurrencyEffect - last_average_price_with_currency_effect) * order.quantity) if (order.type == "SELL") else _big(0))
            gross_performance_from_sells = (gross_performance_from_sells + gross_performance_from_sell)
            gross_performance_from_sells_with_currency_effect = (gross_performance_from_sells_with_currency_effect + gross_performance_from_sell_with_currency_effect)
            last_average_price = (_big(0) if (total_quantity_from_buy_transactions == 0) else (total_investment_from_buy_transactions / total_quantity_from_buy_transactions))
            last_average_price_with_currency_effect = (_big(0) if (total_quantity_from_buy_transactions == 0) else (total_investment_from_buy_transactions_with_currency_effect / total_quantity_from_buy_transactions))
            if (total_units == 0):
                # Reset tracking variables when position is fully closed
                total_investment_from_buy_transactions = _big(0)
                total_investment_from_buy_transactions_with_currency_effect = _big(0)
                total_quantity_from_buy_transactions = _big(0)
            if PortfolioCalculator.ENABLE_LOGGING:
                console.log("grossPerformanceFromSells", float(gross_performance_from_sells))
                console.log("grossPerformanceFromSellWithCurrencyEffect", float(gross_performance_from_sell_with_currency_effect))
            new_gross_performance = ((value_of_investment - total_investment) + gross_performance_from_sells)
            new_gross_performance_with_currency_effect = ((value_of_investment_with_currency_effect - total_investment_with_currency_effect) + gross_performance_from_sells_with_currency_effect)
            gross_performance = new_gross_performance
            gross_performance_with_currency_effect = new_gross_performance_with_currency_effect
            if (order.itemType == "start"):
                fees_at_start_date = fees
                fees_at_start_date_with_currency_effect = fees_with_currency_effect
                gross_performance_at_start_date = gross_performance
                gross_performance_at_start_date_with_currency_effect = gross_performance_with_currency_effect
            if (i > index_of_start_order):
                # Only consider periods with an investment for the calculation of
                # the time weighted investment
                if ((value_of_investment_before_transaction > 0) and (order.type in ["BUY", "SELL"])):
                    # Calculate the number of days since the previous order
                    order_date = _new_date(order.date)
                    previous_order_date = _new_date(orders[(i - 1)].date)
                    days_since_last_order = difference_in_days(order_date, previous_order_date)
                    if (days_since_last_order <= 0):
                        # The time between two activities on the same day is unknown
                        # -> Set it to the smallest floating point number greater than 0
                        days_since_last_order = Number.EPSILON
                    # Sum up the total investment days since the start date to calculate
                    # the time weighted investment
                    total_investment_days += days_since_last_order
                    sum_of_time_weighted_investments = sum_of_time_weighted_investments.add((((value_at_start_date - investment_at_start_date) + total_investment_before_transaction) * days_since_last_order))
                    sum_of_time_weighted_investments_with_currency_effect = sum_of_time_weighted_investments_with_currency_effect.add((((value_at_start_date_with_currency_effect - investment_at_start_date_with_currency_effect) + total_investment_before_transaction_with_currency_effect) * days_since_last_order))
                current_values[order.date] = value_of_investment
                current_values_with_currency_effect[order.date] = value_of_investment_with_currency_effect
                net_performance_values[order.date] = ((gross_performance - gross_performance_at_start_date) - (fees - fees_at_start_date))
                net_performance_values_with_currency_effect[order.date] = ((gross_performance_with_currency_effect - gross_performance_at_start_date_with_currency_effect) - (fees_with_currency_effect - fees_at_start_date_with_currency_effect))
                investment_values_accumulated[order.date] = total_investment
                investment_values_accumulated_with_currency_effect[order.date] = total_investment_with_currency_effect
                investment_values_with_currency_effect[order.date] = ((investment_values_with_currency_effect[order.date] or _big(0))).add(transaction_investment_with_currency_effect)
                # If duration is effectively zero (first day), use the actual investment as the base.
                # Otherwise, use the calculated time-weighted average.
                time_weighted_investment_values[order.date] = ((sum_of_time_weighted_investments / total_investment_days) if (total_investment_days > Number.EPSILON) else (total_investment if (total_investment > 0) else _big(0)))
                time_weighted_investment_values_with_currency_effect[order.date] = ((sum_of_time_weighted_investments_with_currency_effect / total_investment_days) if (total_investment_days > Number.EPSILON) else (total_investment_with_currency_effect if (total_investment_with_currency_effect > 0) else _big(0)))
            if PortfolioCalculator.ENABLE_LOGGING:
                console.log("totalInvestment", float(total_investment))
                console.log("totalInvestmentWithCurrencyEffect", float(total_investment_with_currency_effect))
                console.log("totalGrossPerformance", float((gross_performance - gross_performance_at_start_date)))
                console.log("totalGrossPerformanceWithCurrencyEffect", float((gross_performance_with_currency_effect - gross_performance_at_start_date_with_currency_effect)))
            if (i == index_of_end_order):
                break
            i += 1
        total_gross_performance = (gross_performance - gross_performance_at_start_date)
        total_gross_performance_with_currency_effect = (gross_performance_with_currency_effect - gross_performance_at_start_date_with_currency_effect)
        total_net_performance = ((gross_performance - gross_performance_at_start_date) - (fees - fees_at_start_date))
        time_weighted_average_investment_between_start_and_end_date = ((sum_of_time_weighted_investments / total_investment_days) if (total_investment_days > 0) else _big(0))
        time_weighted_average_investment_between_start_and_end_date_with_currency_effect = ((sum_of_time_weighted_investments_with_currency_effect / total_investment_days) if (total_investment_days > 0) else _big(0))
        gross_performance_percentage = ((total_gross_performance / time_weighted_average_investment_between_start_and_end_date) if (time_weighted_average_investment_between_start_and_end_date > 0) else _big(0))
        gross_performance_percentage_with_currency_effect = ((total_gross_performance_with_currency_effect / time_weighted_average_investment_between_start_and_end_date_with_currency_effect) if (time_weighted_average_investment_between_start_and_end_date_with_currency_effect > 0) else _big(0))
        fees_per_unit = (((fees - fees_at_start_date) / total_units) if (total_units > 0) else _big(0))
        fees_per_unit_with_currency_effect = (((fees_with_currency_effect - fees_at_start_date_with_currency_effect) / total_units) if (total_units > 0) else _big(0))
        net_performance_percentage = ((total_net_performance / time_weighted_average_investment_between_start_and_end_date) if (time_weighted_average_investment_between_start_and_end_date > 0) else _big(0))
        net_performance_percentage_with_currency_effect_map = {}
        net_performance_with_currency_effect_map = {}
        for _ in None  # UNTRANSLATED<as_expression>: "[       '1d',       '1y',       '5y',       'max',       'mtd',       'wtd',    ":
            date_interval = get_interval_from_date_range(date_range)
            end_date = date_interval.endDate
            start_date = date_interval.startDate
            if is_before(start_date, start):
                start_date = start
            range_end_date_string = format(end_date, DATE_FORMAT)
            range_start_date_string = format(start_date, DATE_FORMAT)
            current_values_at_date_range_start_with_currency_effect = (current_values_with_currency_effect[range_start_date_string] or _big(0))
            investment_values_accumulated_at_start_date_with_currency_effect = (investment_values_accumulated_with_currency_effect[range_start_date_string] or _big(0))
            gross_performance_at_date_range_start_with_currency_effect = (current_values_at_date_range_start_with_currency_effect - investment_values_accumulated_at_start_date_with_currency_effect)
            average = _big(0)
            day_count = 0
            i = (self.chartDates.length - 1)
            while (i >= 0):
                date = self.chartDates[i]
                if (date > range_end_date_string):
                    continue
                elif (date < range_start_date_string):
                    break
                if ((investment_values_accumulated_with_currency_effect[date] instanceof Big) and (investment_values_accumulated_with_currency_effect[date] > 0)):
                    average = average.add(investment_values_accumulated_with_currency_effect[date].add(gross_performance_at_date_range_start_with_currency_effect))
                    day_count += 1
                i -= 1
            if (day_count > 0):
                average = (average / day_count)
            net_performance_with_currency_effect_map[date_range] = ((net_performance_values_with_currency_effect[range_end_date_string] - # If the date range is 'max', take 0 as a start value. Otherwise,, # the value of the end of the day of the start date is taken which, # differs from the buying price., (_big(0) if (date_range == "max") else ((net_performance_values_with_currency_effect[range_start_date_string] or _big(0))))) or _big(0))
            net_performance_percentage_with_currency_effect_map[date_range] = ((net_performance_with_currency_effect_map[date_range] / average) if (average > 0) else _big(0))
        if PortfolioCalculator.ENABLE_LOGGING:
            console.log(f"
                    {symbol}
                    Unit price: {round(orders[index_of_start_order].unitPrice, 2)} -> {round(unit_price_at_end_date, 2)}
                    Total investment: {round(total_investment, 2)}
                    Total investment with currency effect: {round(total_investment_with_currency_effect, 2)}
                    Time weighted investment: {round(time_weighted_average_investment_between_start_and_end_date, 2)}
                    Time weighted investment with currency effect: {round(time_weighted_average_investment_between_start_and_end_date_with_currency_effect, 2)}
                    Total dividend: {round(total_dividend, 2)}
                    Gross performance: {round(total_gross_performance, 2)} / {round((gross_performance_percentage * 100), 2)}%
                    Gross performance with currency effect: {round(total_gross_performance_with_currency_effect, 2)} / {round((gross_performance_percentage_with_currency_effect * 100), 2)}%
                    Fees per unit: {round(fees_per_unit, 2)}
                    Fees per unit with currency effect: {round(fees_per_unit_with_currency_effect, 2)}
                    Net performance: {round(total_net_performance, 2)} / {round((net_performance_percentage * 100), 2)}%
                    Net performance with currency effect: {round(net_performance_percentage_with_currency_effect_map[\"max\"], 2)}%")
        return {"currentValues": current_values, "currentValuesWithCurrencyEffect": current_values_with_currency_effect, "feesWithCurrencyEffect": fees_with_currency_effect, "grossPerformancePercentage": gross_performance_percentage, "grossPerformancePercentageWithCurrencyEffect": gross_performance_percentage_with_currency_effect, "initialValue": initial_value, "initialValueWithCurrencyEffect": initial_value_with_currency_effect, "investmentValuesAccumulated": investment_values_accumulated, "investmentValuesAccumulatedWithCurrencyEffect": investment_values_accumulated_with_currency_effect, "investmentValuesWithCurrencyEffect": investment_values_with_currency_effect, "netPerformancePercentage": net_performance_percentage, "netPerformancePercentageWithCurrencyEffectMap": net_performance_percentage_with_currency_effect_map, "netPerformanceValues": net_performance_values, "netPerformanceValuesWithCurrencyEffect": net_performance_values_with_currency_effect, "netPerformanceWithCurrencyEffectMap": net_performance_with_currency_effect_map, "timeWeightedInvestmentValues": time_weighted_investment_values, "timeWeightedInvestmentValuesWithCurrencyEffect": time_weighted_investment_values_with_currency_effect, "totalAccountBalanceInBaseCurrency": total_account_balance_in_base_currency, "totalDividend": total_dividend, "totalDividendInBaseCurrency": total_dividend_in_base_currency, "totalInterest": total_interest, "totalInterestInBaseCurrency": total_interest_in_base_currency, "totalInvestment": total_investment, "totalInvestmentWithCurrencyEffect": total_investment_with_currency_effect, "totalLiabilities": total_liabilities, "totalLiabilitiesInBaseCurrency": total_liabilities_in_base_currency, "grossPerformance": total_gross_performance, "grossPerformanceWithCurrencyEffect": total_gross_performance_with_currency_effect, "hasErrors": ((total_units > 0) and (((not initial_value) or (not unit_price_at_end_date)))), "netPerformance": total_net_performance, "timeWeightedInvestment": time_weighted_average_investment_between_start_and_end_date, "timeWeightedInvestmentWithCurrencyEffect": time_weighted_average_investment_between_start_and_end_date_with_currency_effect}
