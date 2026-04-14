from __future__ import annotations

from decimal import Decimal
from datetime import datetime, timedelta
import copy
import sys

from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator
from .runtime_helpers import get_factor
from .runtime_helpers import get_interval_from_date_range
from .runtime_helpers import DATE_FORMAT
from .runtime_helpers import Logger
from .runtime_helpers import (
    add_milliseconds, difference_in_days, each_year_of_interval,
    format_date, is_before, is_this_year, parse_date, JSObj,
)

class RoaiPortfolioCalculator(PortfolioCalculator):
    chart_dates = None

    def calculate_overall_performance(self, positions):
        current_value_in_base_currency = Decimal(str(0))
        gross_performance = Decimal(str(0))
        gross_performance_with_currency_effect = Decimal(str(0))
        has_errors = False
        net_performance = Decimal(str(0))
        total_fees_with_currency_effect = Decimal(str(0))
        total_interest_with_currency_effect = Decimal(str(0))
        total_investment = Decimal(str(0))
        total_investment_with_currency_effect = Decimal(str(0))
        total_time_weighted_investment = Decimal(str(0))
        total_time_weighted_investment_with_currency_effect = Decimal(str(0))
        for current_position in [_x for _x in positions if _x["includeInTotalAssetValue"]]:
            if current_position.fee_in_base_currency:
                total_fees_with_currency_effect = (total_fees_with_currency_effect + current_position.fee_in_base_currency)
            if current_position.value_in_base_currency:
                current_value_in_base_currency = (current_value_in_base_currency + current_position.value_in_base_currency)
            else:
                has_errors = True
            if current_position.investment:
                total_investment = (total_investment + current_position.investment)
                total_investment_with_currency_effect = (total_investment_with_currency_effect + current_position.investment_with_currency_effect)
            else:
                has_errors = True
            if current_position.gross_performance:
                gross_performance = (gross_performance + current_position.gross_performance)
                gross_performance_with_currency_effect = (gross_performance_with_currency_effect + current_position.gross_performance_with_currency_effect)
                net_performance = (net_performance + current_position.net_performance)
            elif not (current_position.quantity == 0):
                has_errors = True
            if current_position.time_weighted_investment:
                total_time_weighted_investment = (total_time_weighted_investment + current_position.time_weighted_investment)
                total_time_weighted_investment_with_currency_effect = (total_time_weighted_investment_with_currency_effect + current_position.time_weighted_investment_with_currency_effect)
            elif not (current_position.quantity == 0):
                Logger.warn(f"Missing historical market data for {current_position.symbol} ({current_position.data_source})", 'PortfolioCalculator')
                has_errors = True
        return JSObj({
            "currentValueInBaseCurrency": current_value_in_base_currency,
            "hasErrors": has_errors,
            "positions": positions,
            "totalFeesWithCurrencyEffect": total_fees_with_currency_effect,
            "totalInterestWithCurrencyEffect": total_interest_with_currency_effect,
            "totalInvestment": total_investment,
            "totalInvestmentWithCurrencyEffect": total_investment_with_currency_effect,
            "activitiesCount": len([_x for _x in self.activities if (_x["type"] in ['BUY', 'SELL'])] or []),
            "createdAt": datetime.now(),
            "errors": [],
            "historicalData": [],
            "totalLiabilitiesWithCurrencyEffect": Decimal(str(0)),
        })

    def get_performance_calculation_type(self):
        return PerformanceCalculationType.ROAI

    def get_symbol_metrics(self, chart_date_map, data_source, end, exchange_rates, market_symbol_map, start, symbol):
        current_exchange_rate = exchange_rates[datetime.now().strftime(DATE_FORMAT)]
        current_values = JSObj({})
        current_values_with_currency_effect = JSObj({})
        fees = Decimal(str(0))
        fees_at_start_date = Decimal(str(0))
        fees_at_start_date_with_currency_effect = Decimal(str(0))
        fees_with_currency_effect = Decimal(str(0))
        gross_performance = Decimal(str(0))
        gross_performance_with_currency_effect = Decimal(str(0))
        gross_performance_at_start_date = Decimal(str(0))
        gross_performance_at_start_date_with_currency_effect = Decimal(str(0))
        gross_performance_from_sells = Decimal(str(0))
        gross_performance_from_sells_with_currency_effect = Decimal(str(0))
        initial_value = None
        initial_value_with_currency_effect = None
        investment_at_start_date = None
        investment_at_start_date_with_currency_effect = None
        investment_values_accumulated = JSObj({})
        investment_values_accumulated_with_currency_effect = JSObj({})
        investment_values_with_currency_effect = JSObj({})
        last_average_price = Decimal(str(0))
        last_average_price_with_currency_effect = Decimal(str(0))
        net_performance_values = JSObj({})
        net_performance_values_with_currency_effect = JSObj({})
        time_weighted_investment_values = JSObj({})
        time_weighted_investment_values_with_currency_effect = JSObj({})
        total_account_balance_in_base_currency = Decimal(str(0))
        total_dividend = Decimal(str(0))
        total_dividend_in_base_currency = Decimal(str(0))
        total_interest = Decimal(str(0))
        total_interest_in_base_currency = Decimal(str(0))
        total_investment = Decimal(str(0))
        total_investment_from_buy_transactions = Decimal(str(0))
        total_investment_from_buy_transactions_with_currency_effect = Decimal(str(0))
        total_investment_with_currency_effect = Decimal(str(0))
        total_liabilities = Decimal(str(0))
        total_liabilities_in_base_currency = Decimal(str(0))
        total_quantity_from_buy_transactions = Decimal(str(0))
        total_units = Decimal(str(0))
        value_at_start_date = None
        value_at_start_date_with_currency_effect = None
        # Clone orders to keep the original values in this.orders
        orders = copy.deepcopy([_x for _x in self.activities if (_x["SymbolProfile"].symbol == symbol)])
        is_cash = (getattr(getattr(orders[0], 'SymbolProfile', None), 'asset_sub_class', None) == 'CASH')
        if (len(orders or []) <= 0):
            return JSObj({
                "currentValues": JSObj({}),
                "currentValuesWithCurrencyEffect": JSObj({}),
                "feesWithCurrencyEffect": Decimal(str(0)),
                "grossPerformance": Decimal(str(0)),
                "grossPerformancePercentage": Decimal(str(0)),
                "grossPerformancePercentageWithCurrencyEffect": Decimal(str(0)),
                "grossPerformanceWithCurrencyEffect": Decimal(str(0)),
                "hasErrors": False,
                "initialValue": Decimal(str(0)),
                "initialValueWithCurrencyEffect": Decimal(str(0)),
                "investmentValuesAccumulated": JSObj({}),
                "investmentValuesAccumulatedWithCurrencyEffect": JSObj({}),
                "investmentValuesWithCurrencyEffect": JSObj({}),
                "netPerformance": Decimal(str(0)),
                "netPerformancePercentage": Decimal(str(0)),
                "netPerformancePercentageWithCurrencyEffectMap": JSObj({}),
                "netPerformanceValues": JSObj({}),
                "netPerformanceValuesWithCurrencyEffect": JSObj({}),
                "netPerformanceWithCurrencyEffectMap": JSObj({}),
                "timeWeightedInvestment": Decimal(str(0)),
                "timeWeightedInvestmentValues": JSObj({}),
                "timeWeightedInvestmentValuesWithCurrencyEffect": JSObj({}),
                "timeWeightedInvestmentWithCurrencyEffect": Decimal(str(0)),
                "totalAccountBalanceInBaseCurrency": Decimal(str(0)),
                "totalDividend": Decimal(str(0)),
                "totalDividendInBaseCurrency": Decimal(str(0)),
                "totalInterest": Decimal(str(0)),
                "totalInterestInBaseCurrency": Decimal(str(0)),
                "totalInvestment": Decimal(str(0)),
                "totalInvestmentWithCurrencyEffect": Decimal(str(0)),
                "totalLiabilities": Decimal(str(0)),
                "totalLiabilitiesInBaseCurrency": Decimal(str(0)),
            })
        date_of_first_transaction = datetime.fromisoformat(orders[0].date)
        end_date_string = end.strftime(DATE_FORMAT)
        start_date_string = start.strftime(DATE_FORMAT)
        unit_price_at_start_date = market_symbol_map[start_date_string][symbol]
        unit_price_at_end_date = market_symbol_map[end_date_string][symbol]
        latest_activity = orders[-1]
        if ((((data_source == 'MANUAL') and (getattr(latest_activity, 'type', None) in ['BUY', 'SELL'])) and getattr(latest_activity, 'unit_price', None)) and not unit_price_at_end_date):
            # For BUY / SELL activities with a MANUAL data source where no historical market price is available,
            # the calculation should fall back to using the activity’s unit price.
            unit_price_at_end_date = latest_activity.unit_price
        elif is_cash:
            unit_price_at_end_date = Decimal(str(1))
        if (not unit_price_at_end_date or ((not unit_price_at_start_date and (date_of_first_transaction < start)))):
            return JSObj({
                "currentValues": JSObj({}),
                "currentValuesWithCurrencyEffect": JSObj({}),
                "feesWithCurrencyEffect": Decimal(str(0)),
                "grossPerformance": Decimal(str(0)),
                "grossPerformancePercentage": Decimal(str(0)),
                "grossPerformancePercentageWithCurrencyEffect": Decimal(str(0)),
                "grossPerformanceWithCurrencyEffect": Decimal(str(0)),
                "hasErrors": True,
                "initialValue": Decimal(str(0)),
                "initialValueWithCurrencyEffect": Decimal(str(0)),
                "investmentValuesAccumulated": JSObj({}),
                "investmentValuesAccumulatedWithCurrencyEffect": JSObj({}),
                "investmentValuesWithCurrencyEffect": JSObj({}),
                "netPerformance": Decimal(str(0)),
                "netPerformancePercentage": Decimal(str(0)),
                "netPerformancePercentageWithCurrencyEffectMap": JSObj({}),
                "netPerformanceWithCurrencyEffectMap": JSObj({}),
                "netPerformanceValues": JSObj({}),
                "netPerformanceValuesWithCurrencyEffect": JSObj({}),
                "timeWeightedInvestment": Decimal(str(0)),
                "timeWeightedInvestmentValues": JSObj({}),
                "timeWeightedInvestmentValuesWithCurrencyEffect": JSObj({}),
                "timeWeightedInvestmentWithCurrencyEffect": Decimal(str(0)),
                "totalAccountBalanceInBaseCurrency": Decimal(str(0)),
                "totalDividend": Decimal(str(0)),
                "totalDividendInBaseCurrency": Decimal(str(0)),
                "totalInterest": Decimal(str(0)),
                "totalInterestInBaseCurrency": Decimal(str(0)),
                "totalInvestment": Decimal(str(0)),
                "totalInvestmentWithCurrencyEffect": Decimal(str(0)),
                "totalLiabilities": Decimal(str(0)),
                "totalLiabilitiesInBaseCurrency": Decimal(str(0)),
            })
        # Add a synthetic order at the start and the end date
        orders.append(JSObj({
            "date": start_date_string,
            "fee": Decimal(str(0)),
            "feeInBaseCurrency": Decimal(str(0)),
            "itemType": 'start',
            "quantity": Decimal(str(0)),
            "SymbolProfile": JSObj({"dataSource": data_source, "symbol": symbol, "assetSubClass": ('CASH' if is_cash else None)}),
            "type": 'BUY',
            "unitPrice": unit_price_at_start_date,
        }))
        orders.append(JSObj({
            "date": end_date_string,
            "fee": Decimal(str(0)),
            "feeInBaseCurrency": Decimal(str(0)),
            "itemType": 'end',
            "SymbolProfile": JSObj({"dataSource": data_source, "symbol": symbol, "assetSubClass": ('CASH' if is_cash else None)}),
            "quantity": Decimal(str(0)),
            "type": 'BUY',
            "unitPrice": unit_price_at_end_date,
        }))
        last_unit_price = None
        orders_by_date = JSObj({})
        for order in orders:
            orders_by_date[order.date] = orders_by_date.get(order.date, [])
            orders_by_date[order.date].append(order)
        if not self.chart_dates:
            self.chart_dates = sorted(list(chart_date_map))
        for date_string in self.chart_dates:
            if (date_string < start_date_string):
                continue
            elif (date_string > end_date_string):
                break
            if (len(orders_by_date[date_string] or []) > 0):
                for order in orders_by_date[date_string]:
                    order.unit_price_from_market_data = market_symbol_map[date_string].get(symbol, last_unit_price)
            else:
                orders.append(JSObj({
                    "date": date_string,
                    "fee": Decimal(str(0)),
                    "feeInBaseCurrency": Decimal(str(0)),
                    "quantity": Decimal(str(0)),
                    "SymbolProfile": JSObj({"dataSource": data_source, "symbol": symbol, "assetSubClass": ('CASH' if is_cash else None)}),
                    "type": 'BUY',
                    "unitPrice": market_symbol_map[date_string].get(symbol, last_unit_price),
                    "unitPriceFromMarketData": market_symbol_map[date_string].get(symbol, last_unit_price),
                }))
            latest_activity = orders[-1]
            last_unit_price = (latest_activity.unit_price_from_market_data if latest_activity.unit_price_from_market_data is not None else latest_activity.unit_price)
        # Sort orders so that the start and end placeholder order are at the correct
        # position
        def _sort_key_385(_item):
            date = _item["date"]
            item_type = _item["itemType"]
            sort_index = datetime.fromisoformat(date)
            if (item_type == 'end'):
                sort_index = (sort_index + timedelta(milliseconds=1))
            elif (item_type == 'start'):
                sort_index = (sort_index + timedelta(milliseconds=-1))
            return sort_index.timestamp()
        orders = sorted(orders, key=_sort_key_385)
        index_of_start_order = next((_i for _i, _x in enumerate(orders) if (_x["itemType"] == 'start')), -1)
        index_of_end_order = next((_i for _i, _x in enumerate(orders) if (_x["itemType"] == 'end')), -1)
        total_investment_days = 0
        sum_of_time_weighted_investments = Decimal(str(0))
        sum_of_time_weighted_investments_with_currency_effect = Decimal(str(0))
        i = 0
        while (i < len(orders or [])):
            order = orders[i]
            if PortfolioCalculator.ENABLE_LOGGING:
                print()
                print()
                print((i + 1), order.date, order.type, (f"({order.item_type})" if order.item_type else ''))
            exchange_rate_at_order_date = exchange_rates[order.date]
            if (order.type == 'DIVIDEND'):
                dividend = (order.quantity * order.unit_price)
                total_dividend = (total_dividend + dividend)
                total_dividend_in_base_currency = (total_dividend_in_base_currency + (dividend * (exchange_rate_at_order_date if exchange_rate_at_order_date is not None else 1)))
            elif (order.type == 'INTEREST'):
                interest = (order.quantity * order.unit_price)
                total_interest = (total_interest + interest)
                total_interest_in_base_currency = (total_interest_in_base_currency + (interest * (exchange_rate_at_order_date if exchange_rate_at_order_date is not None else 1)))
            elif (order.type == 'LIABILITY'):
                liabilities = (order.quantity * order.unit_price)
                total_liabilities = (total_liabilities + liabilities)
                total_liabilities_in_base_currency = (total_liabilities_in_base_currency + (liabilities * (exchange_rate_at_order_date if exchange_rate_at_order_date is not None else 1)))
            if (order.item_type == 'start'):
                # Take the unit price of the order as the market price if there are no
                # orders of this symbol before the start date
                order.unit_price = (getattr(orders[(i + 1)], 'unit_price', None) if (index_of_start_order == 0) else unit_price_at_start_date)
            if order.fee:
                order.fee_in_base_currency = (order.fee * (current_exchange_rate if current_exchange_rate is not None else 1))
                order.fee_in_base_currency_with_currency_effect = (order.fee * (exchange_rate_at_order_date if exchange_rate_at_order_date is not None else 1))
            unit_price = (order.unit_price if (order.type in ['BUY', 'SELL']) else order.unit_price_from_market_data)
            if unit_price:
                order.unit_price_in_base_currency = (unit_price * (current_exchange_rate if current_exchange_rate is not None else 1))
                order.unit_price_in_base_currency_with_currency_effect = (unit_price * (exchange_rate_at_order_date if exchange_rate_at_order_date is not None else 1))
            market_price_in_base_currency = ((order.unit_price_from_market_data * (current_exchange_rate if current_exchange_rate is not None else 1)) if (order.unit_price_from_market_data * (current_exchange_rate if current_exchange_rate is not None else 1)) is not None else Decimal(str(0)))
            market_price_in_base_currency_with_currency_effect = ((order.unit_price_from_market_data * (exchange_rate_at_order_date if exchange_rate_at_order_date is not None else 1)) if (order.unit_price_from_market_data * (exchange_rate_at_order_date if exchange_rate_at_order_date is not None else 1)) is not None else Decimal(str(0)))
            value_of_investment_before_transaction = (total_units * market_price_in_base_currency)
            value_of_investment_before_transaction_with_currency_effect = (total_units * market_price_in_base_currency_with_currency_effect)
            if (not investment_at_start_date and (i >= index_of_start_order)):
                investment_at_start_date = (total_investment if total_investment is not None else Decimal(str(0)))
                investment_at_start_date_with_currency_effect = (total_investment_with_currency_effect if total_investment_with_currency_effect is not None else Decimal(str(0)))
                value_at_start_date = value_of_investment_before_transaction
                value_at_start_date_with_currency_effect = value_of_investment_before_transaction_with_currency_effect
            transaction_investment = Decimal(str(0))
            transaction_investment_with_currency_effect = Decimal(str(0))
            if (order.type == 'BUY'):
                transaction_investment = ((order.quantity * order.unit_price_in_base_currency) * get_factor(order.type))
                transaction_investment_with_currency_effect = ((order.quantity * order.unit_price_in_base_currency_with_currency_effect) * get_factor(order.type))
                total_quantity_from_buy_transactions = (total_quantity_from_buy_transactions + order.quantity)
                total_investment_from_buy_transactions = (total_investment_from_buy_transactions + transaction_investment)
                total_investment_from_buy_transactions_with_currency_effect = (total_investment_from_buy_transactions_with_currency_effect + transaction_investment_with_currency_effect)
            elif (order.type == 'SELL'):
                if (total_units > 0):
                    transaction_investment = (((total_investment / total_units) * order.quantity) * get_factor(order.type))
                    transaction_investment_with_currency_effect = (((total_investment_with_currency_effect / total_units) * order.quantity) * get_factor(order.type))
            if PortfolioCalculator.ENABLE_LOGGING:
                print('order.quantity', float(order.quantity))
                print('transactionInvestment', float(transaction_investment))
                print('transactionInvestmentWithCurrencyEffect', float(transaction_investment_with_currency_effect))
            total_investment_before_transaction = total_investment
            total_investment_before_transaction_with_currency_effect = total_investment_with_currency_effect
            total_investment = (total_investment + transaction_investment)
            total_investment_with_currency_effect = (total_investment_with_currency_effect + transaction_investment_with_currency_effect)
            if ((i >= index_of_start_order) and not initial_value):
                if ((i == index_of_start_order) and not (value_of_investment_before_transaction == 0)):
                    initial_value = value_of_investment_before_transaction
                    initial_value_with_currency_effect = value_of_investment_before_transaction_with_currency_effect
                elif (transaction_investment > 0):
                    initial_value = transaction_investment
                    initial_value_with_currency_effect = transaction_investment_with_currency_effect
            fees = (fees + (order.fee_in_base_currency if order.fee_in_base_currency is not None else 0))
            fees_with_currency_effect = (fees_with_currency_effect + (order.fee_in_base_currency_with_currency_effect if order.fee_in_base_currency_with_currency_effect is not None else 0))
            total_units = (total_units + (order.quantity * get_factor(order.type)))
            value_of_investment = (total_units * market_price_in_base_currency)
            value_of_investment_with_currency_effect = (total_units * market_price_in_base_currency_with_currency_effect)
            gross_performance_from_sell = (((order.unit_price_in_base_currency - last_average_price) * order.quantity) if (order.type == 'SELL') else Decimal(str(0)))
            gross_performance_from_sell_with_currency_effect = (((order.unit_price_in_base_currency_with_currency_effect - last_average_price_with_currency_effect) * order.quantity) if (order.type == 'SELL') else Decimal(str(0)))
            gross_performance_from_sells = (gross_performance_from_sells + gross_performance_from_sell)
            gross_performance_from_sells_with_currency_effect = (gross_performance_from_sells_with_currency_effect + gross_performance_from_sell_with_currency_effect)
            last_average_price = (Decimal(str(0)) if (total_quantity_from_buy_transactions == 0) else (total_investment_from_buy_transactions / total_quantity_from_buy_transactions))
            last_average_price_with_currency_effect = (Decimal(str(0)) if (total_quantity_from_buy_transactions == 0) else (total_investment_from_buy_transactions_with_currency_effect / total_quantity_from_buy_transactions))
            if (total_units == 0):
                # Reset tracking variables when position is fully closed
                total_investment_from_buy_transactions = Decimal(str(0))
                total_investment_from_buy_transactions_with_currency_effect = Decimal(str(0))
                total_quantity_from_buy_transactions = Decimal(str(0))
            if PortfolioCalculator.ENABLE_LOGGING:
                print('grossPerformanceFromSells', float(gross_performance_from_sells))
                print('grossPerformanceFromSellWithCurrencyEffect', float(gross_performance_from_sell_with_currency_effect))
            new_gross_performance = ((value_of_investment - total_investment) + gross_performance_from_sells)
            new_gross_performance_with_currency_effect = ((value_of_investment_with_currency_effect - total_investment_with_currency_effect) + gross_performance_from_sells_with_currency_effect)
            gross_performance = new_gross_performance
            gross_performance_with_currency_effect = new_gross_performance_with_currency_effect
            if (order.item_type == 'start'):
                fees_at_start_date = fees
                fees_at_start_date_with_currency_effect = fees_with_currency_effect
                gross_performance_at_start_date = gross_performance
                gross_performance_at_start_date_with_currency_effect = gross_performance_with_currency_effect
            if (i > index_of_start_order):
                # Only consider periods with an investment for the calculation of
                # the time weighted investment
                if ((value_of_investment_before_transaction > 0) and (order.type in ['BUY', 'SELL'])):
                    # Calculate the number of days since the previous order
                    order_date = datetime.fromisoformat(order.date)
                    previous_order_date = datetime.fromisoformat(orders[(i - 1)].date)
                    days_since_last_order = (order_date - previous_order_date).days
                    if (days_since_last_order <= 0):
                        # The time between two activities on the same day is unknown
                        # -> Set it to the smallest floating point number greater than 0
                        days_since_last_order = sys.float_info.epsilon
                    # Sum up the total investment days since the start date to calculate
                    # the time weighted investment
                    total_investment_days += days_since_last_order
                    sum_of_time_weighted_investments = (sum_of_time_weighted_investments + (((value_at_start_date - investment_at_start_date) + total_investment_before_transaction) * days_since_last_order))
                    sum_of_time_weighted_investments_with_currency_effect = (sum_of_time_weighted_investments_with_currency_effect + (((value_at_start_date_with_currency_effect - investment_at_start_date_with_currency_effect) + total_investment_before_transaction_with_currency_effect) * days_since_last_order))
                current_values[order.date] = value_of_investment
                current_values_with_currency_effect[order.date] = value_of_investment_with_currency_effect
                net_performance_values[order.date] = ((gross_performance - gross_performance_at_start_date) - (fees - fees_at_start_date))
                net_performance_values_with_currency_effect[order.date] = ((gross_performance_with_currency_effect - gross_performance_at_start_date_with_currency_effect) - (fees_with_currency_effect - fees_at_start_date_with_currency_effect))
                investment_values_accumulated[order.date] = total_investment
                investment_values_accumulated_with_currency_effect[order.date] = total_investment_with_currency_effect
                investment_values_with_currency_effect[order.date] = ((investment_values_with_currency_effect.get(order.date, Decimal(str(0)))) + transaction_investment_with_currency_effect)
                # If duration is effectively zero (first day), use the actual investment as the base.
                # Otherwise, use the calculated time-weighted average.
                time_weighted_investment_values[order.date] = ((sum_of_time_weighted_investments / total_investment_days) if (total_investment_days > sys.float_info.epsilon) else (total_investment if (total_investment > 0) else Decimal(str(0))))
                time_weighted_investment_values_with_currency_effect[order.date] = ((sum_of_time_weighted_investments_with_currency_effect / total_investment_days) if (total_investment_days > sys.float_info.epsilon) else (total_investment_with_currency_effect if (total_investment_with_currency_effect > 0) else Decimal(str(0))))
            if PortfolioCalculator.ENABLE_LOGGING:
                print('totalInvestment', float(total_investment))
                print('totalInvestmentWithCurrencyEffect', float(total_investment_with_currency_effect))
                print('totalGrossPerformance', float((gross_performance - gross_performance_at_start_date)))
                print('totalGrossPerformanceWithCurrencyEffect', float((gross_performance_with_currency_effect - gross_performance_at_start_date_with_currency_effect)))
            if (i == index_of_end_order):
                break
            i += 1
        total_gross_performance = (gross_performance - gross_performance_at_start_date)
        total_gross_performance_with_currency_effect = (gross_performance_with_currency_effect - gross_performance_at_start_date_with_currency_effect)
        total_net_performance = ((gross_performance - gross_performance_at_start_date) - (fees - fees_at_start_date))
        time_weighted_average_investment_between_start_and_end_date = ((sum_of_time_weighted_investments / total_investment_days) if (total_investment_days > 0) else Decimal(str(0)))
        time_weighted_average_investment_between_start_and_end_date_with_currency_effect = ((sum_of_time_weighted_investments_with_currency_effect / total_investment_days) if (total_investment_days > 0) else Decimal(str(0)))
        gross_performance_percentage = ((total_gross_performance / time_weighted_average_investment_between_start_and_end_date) if (time_weighted_average_investment_between_start_and_end_date > 0) else Decimal(str(0)))
        gross_performance_percentage_with_currency_effect = ((total_gross_performance_with_currency_effect / time_weighted_average_investment_between_start_and_end_date_with_currency_effect) if (time_weighted_average_investment_between_start_and_end_date_with_currency_effect > 0) else Decimal(str(0)))
        fees_per_unit = (((fees - fees_at_start_date) / total_units) if (total_units > 0) else Decimal(str(0)))
        fees_per_unit_with_currency_effect = (((fees_with_currency_effect - fees_at_start_date_with_currency_effect) / total_units) if (total_units > 0) else Decimal(str(0)))
        net_performance_percentage = ((total_net_performance / time_weighted_average_investment_between_start_and_end_date) if (time_weighted_average_investment_between_start_and_end_date > 0) else Decimal(str(0)))
        net_performance_percentage_with_currency_effect_map = JSObj({})
        net_performance_with_currency_effect_map = JSObj({})
        for date_range in ['1d', '1y', '5y', 'max', 'mtd', 'wtd', 'ytd', *[_x.strftime('yyyy') for _x in [_x for _x in _each_year_of_interval(JSObj({"end": end, "start": start})) if not (_x.year == datetime.now().year)]]]:
            date_interval = _get_interval_from_date_range(date_range)
            end_date = date_interval.end_date
            start_date = date_interval.start_date
            if (start_date < start):
                start_date = start
            range_end_date_string = end_date.strftime(DATE_FORMAT)
            range_start_date_string = start_date.strftime(DATE_FORMAT)
            current_values_at_date_range_start_with_currency_effect = current_values_with_currency_effect.get(range_start_date_string, Decimal(str(0)))
            investment_values_accumulated_at_start_date_with_currency_effect = investment_values_accumulated_with_currency_effect.get(range_start_date_string, Decimal(str(0)))
            gross_performance_at_date_range_start_with_currency_effect = (current_values_at_date_range_start_with_currency_effect - investment_values_accumulated_at_start_date_with_currency_effect)
            average = Decimal(str(0))
            day_count = 0
            i = (len(self.chart_dates or []) - 1)
            while (i >= 0):
                date = self.chart_dates[i]
                if (date > range_end_date_string):
                    continue
                elif (date < range_start_date_string):
                    break
                if (isinstance(investment_values_accumulated_with_currency_effect[date], Big) and (investment_values_accumulated_with_currency_effect[date] > 0)):
                    average = (average + (investment_values_accumulated_with_currency_effect[date] + gross_performance_at_date_range_start_with_currency_effect))
                    day_count += 1
                i -= 1
            if (day_count > 0):
                average = (average / day_count)
            net_performance_with_currency_effect_map[date_range] = ((net_performance_values_with_currency_effect[range_end_date_string] - (Decimal(str(0)) if (date_range == 'max') else (net_performance_values_with_currency_effect.get(range_start_date_string, Decimal(str(0)))))) if (net_performance_values_with_currency_effect[range_end_date_string] - (Decimal(str(0)) if (date_range == 'max') else (net_performance_values_with_currency_effect.get(range_start_date_string, Decimal(str(0)))))) is not None else Decimal(str(0)))
            net_performance_percentage_with_currency_effect_map[date_range] = ((net_performance_with_currency_effect_map[date_range] / average) if (average > 0) else Decimal(str(0)))
        if PortfolioCalculator.ENABLE_LOGGING:
            print(f"""
        {symbol}
        Unit price: {round(float(orders[index_of_start_order].unit_price), 2)} -> {round(float(unit_price_at_end_date), 2)}
        Total investment: {round(float(total_investment), 2)}
        Total investment with currency effect: {round(float(total_investment_with_currency_effect), 2)}
        Time weighted investment: {round(float(time_weighted_average_investment_between_start_and_end_date), 2)}
        Time weighted investment with currency effect: {round(float(time_weighted_average_investment_between_start_and_end_date_with_currency_effect), 2)}
        Total dividend: {round(float(total_dividend), 2)}
        Gross performance: {round(float(total_gross_performance), 2)} / {round(float((gross_performance_percentage * 100)), 2)}%
        Gross performance with currency effect: {round(float(total_gross_performance_with_currency_effect), 2)} / {round(float((gross_performance_percentage_with_currency_effect * 100)), 2)}%
        Fees per unit: {round(float(fees_per_unit), 2)}
        Fees per unit with currency effect: {round(float(fees_per_unit_with_currency_effect), 2)}
        Net performance: {round(float(total_net_performance), 2)} / {round(float((net_performance_percentage * 100)), 2)}%
        Net performance with currency effect: {round(float(net_performance_percentage_with_currency_effect_map['max']), 2)}%""")
        return JSObj({
            "currentValues": current_values,
            "currentValuesWithCurrencyEffect": current_values_with_currency_effect,
            "feesWithCurrencyEffect": fees_with_currency_effect,
            "grossPerformancePercentage": gross_performance_percentage,
            "grossPerformancePercentageWithCurrencyEffect": gross_performance_percentage_with_currency_effect,
            "initialValue": initial_value,
            "initialValueWithCurrencyEffect": initial_value_with_currency_effect,
            "investmentValuesAccumulated": investment_values_accumulated,
            "investmentValuesAccumulatedWithCurrencyEffect": investment_values_accumulated_with_currency_effect,
            "investmentValuesWithCurrencyEffect": investment_values_with_currency_effect,
            "netPerformancePercentage": net_performance_percentage,
            "netPerformancePercentageWithCurrencyEffectMap": net_performance_percentage_with_currency_effect_map,
            "netPerformanceValues": net_performance_values,
            "netPerformanceValuesWithCurrencyEffect": net_performance_values_with_currency_effect,
            "netPerformanceWithCurrencyEffectMap": net_performance_with_currency_effect_map,
            "timeWeightedInvestmentValues": time_weighted_investment_values,
            "timeWeightedInvestmentValuesWithCurrencyEffect": time_weighted_investment_values_with_currency_effect,
            "totalAccountBalanceInBaseCurrency": total_account_balance_in_base_currency,
            "totalDividend": total_dividend,
            "totalDividendInBaseCurrency": total_dividend_in_base_currency,
            "totalInterest": total_interest,
            "totalInterestInBaseCurrency": total_interest_in_base_currency,
            "totalInvestment": total_investment,
            "totalInvestmentWithCurrencyEffect": total_investment_with_currency_effect,
            "totalLiabilities": total_liabilities,
            "totalLiabilitiesInBaseCurrency": total_liabilities_in_base_currency,
            "grossPerformance": total_gross_performance,
            "grossPerformanceWithCurrencyEffect": total_gross_performance_with_currency_effect,
            "hasErrors": ((total_units > 0) and ((not initial_value or not unit_price_at_end_date))),
            "netPerformance": total_net_performance,
            "timeWeightedInvestment": time_weighted_average_investment_between_start_and_end_date,
            "timeWeightedInvestmentWithCurrencyEffect": time_weighted_average_investment_between_start_and_end_date_with_currency_effect,
        })


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
