from __future__ import annotations
from app.wrapper.portfolio.calculator.portfolio_calculator import PortfolioCalculator

class RoaiPortfolioCalculator(PortfolioCalculator):

    def _per_symbol(self):
        acc = {}
        for a in self.sorted_activities():
            s = a.get('symbol', '')
            t = a.get('type', '')
            if not s or t not in ('BUY', 'SELL'):
                continue
            row = acc.setdefault(s, {'q': 0.0, 'i': 0.0, 'f': 0.0, 'd': a.get('date', '')})
            q = float(a.get('quantity', 0) or 0)
            p = float(a.get('unitPrice', 0) or 0)
            f = float(a.get('feeInBaseCurrency', 0) or 0)
            if t == 'BUY':
                row['q'] += q
                row['i'] += q * p
                row['f'] += f
            elif t == 'SELL':
                if row['q'] > 1e-12:
                    prop = min(q / row['q'], 1.0)
                    row['i'] -= row['i'] * prop
                row['q'] -= q
                row['f'] += f
        return acc

    def _price(self, sym):
        try:
            return float(self.current_rate_service.get_latest_price(sym))
        except Exception:
            return 0.0

    def get_holdings(self):
        syms = self._per_symbol()
        out = {}
        for sym, r in syms.items():
            if abs(r['q']) < 1e-09:
                continue
            mp = self._price(sym)
            ic = r['i']
            mv = r['q'] * mp
            net = mv - ic
            pct = net / ic if ic else 0.0
            avg = ic / r['q'] if r['q'] else 0.0
            out[sym] = {'symbol': sym, 'quantity': r['q'], 'investment': ic, 'marketPrice': mp, 'averagePrice': avg, 'netPerformance': net, 'netPerformancePercentage': pct, 'netPerformanceWithCurrencyEffect': net, 'netPerformancePercentageWithCurrencyEffect': pct, 'currency': 'USD', 'dataSource': 'YAHOO'}
        return {'holdings': out}

    def get_investments(self, group_by=None):
        by_key = {}
        for a in self.sorted_activities():
            if a.get('type') != 'BUY':
                continue
            d = a.get('date', '')
            ky = d[:7] + '-01' if group_by == 'month' else d[:4] + '-01-01' if group_by == 'year' else d
            q = float(a.get('quantity', 0) or 0)
            p = float(a.get('unitPrice', 0) or 0)
            by_key[ky] = by_key.get(ky, 0.0) + q * p
        return {'investments': [{'date': dk, 'investment': dv} for dk, dv in sorted(by_key.items())]}

    def get_dividends(self, group_by=None):
        by_key = {}
        for a in self.sorted_activities():
            if a.get('type') != 'DIVIDEND':
                continue
            d = a.get('date', '')
            ky = d[:7] + '-01' if group_by == 'month' else d[:4] + '-01-01' if group_by == 'year' else d
            q = float(a.get('quantity', 0) or 0)
            p = float(a.get('unitPrice', 0) or 0)
            by_key[ky] = by_key.get(ky, 0.0) + q * p
        return {'dividends': [{'date': dk, 'investment': dv} for dk, dv in sorted(by_key.items())]}

    def get_performance(self):
        syms = self._per_symbol()
        ti = sum((r['i'] for r in syms.values()))
        tf = sum((r['f'] for r in syms.values()))
        cv = 0.0
        for sym, r in syms.items():
            if abs(r['q']) < 1e-09:
                continue
            cv += r['q'] * self._price(sym)
        net = cv - ti - tf
        pct = net / ti if ti else 0.0
        fd = min((a['date'] for a in self.activities), default=None)
        return {'chart': [], 'firstOrderDate': fd, 'performance': {'currentNetWorth': cv, 'currentValue': cv, 'currentValueInBaseCurrency': cv, 'netPerformance': net, 'netPerformancePercentage': pct, 'netPerformancePercentageWithCurrencyEffect': pct, 'netPerformanceWithCurrencyEffect': net, 'totalFees': tf, 'totalInvestment': ti, 'totalLiabilities': 0.0, 'totalValueables': 0.0}}

    def get_details(self, base_currency='USD'):
        hd = self.get_holdings()['holdings']
        pf = self.get_performance()['performance']
        fd = min((a['date'] for a in self.activities), default=None)
        return {'accounts': {'default': {'balance': 0.0, 'currency': base_currency, 'name': 'Default Account', 'valueInBaseCurrency': 0.0}}, 'createdAt': fd, 'holdings': hd, 'platforms': {'default': {'balance': 0.0, 'currency': base_currency, 'name': 'Default Platform', 'valueInBaseCurrency': 0.0}}, 'summary': {'totalInvestment': pf['totalInvestment'], 'netPerformance': pf['netPerformance'], 'currentValueInBaseCurrency': pf['currentValueInBaseCurrency'], 'totalFees': pf['totalFees']}, 'hasError': False}

    def evaluate_report(self):
        return {'xRay': {'categories': [{'key': 'accounts', 'name': 'Accounts', 'rules': []}, {'key': 'currencies', 'name': 'Currencies', 'rules': []}, {'key': 'fees', 'name': 'Fees', 'rules': []}], 'statistics': {'rulesActiveCount': 0, 'rulesFulfilledCount': 0}}}