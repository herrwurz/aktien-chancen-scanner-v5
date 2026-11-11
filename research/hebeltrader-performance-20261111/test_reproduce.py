import json
import unittest
from decimal import Decimal as D
import reproduce as audit


class HistoricalAuditTests(unittest.TestCase):
    @classmethod
    def setUpClass(cls):
        cls.result = audit.build()

    def test_locale_and_subcent_budget(self):
        self.assertEqual(audit.price('1.015,80 €'), D('1015.80'))
        self.assertEqual(audit.price('346,00$'), D('346'))
        a = audit.allocation(D('0.065'), D('5'))
        self.assertEqual(a['quantity'], 7615)
        self.assertEqual(D(a['purchase_value_eur']), D('494.98'))
        self.assertGreaterEqual(D(a['cash_eur']), D('0'))

    def test_all_42_quantities_match_authorized_baseline(self):
        baseline = json.loads((audit.ROOT / 'docs/hebeltrader-500eur-hypothetical-positions-20261111.json').read_text())
        expected = {r['issue']:r['quantity'] for r in baseline['positions']}
        for r in self.result['records']:
            self.assertEqual(r['allocation_zero_fees']['quantity'], expected[r['issue']])

    def test_no_fabricated_strategy_or_real_returns(self):
        self.assertEqual(self.result['totals']['expired'],19)
        for r in self.result['records']:
            self.assertIsNone(r['wittmer_call_simulation']['pnl_eur'])
            self.assertIsNone(r['real_trades']['pnl_eur'])
            self.assertFalse(r['wittmer_call_simulation']['verified_executable'])

    def test_capital_action_and_unreliable_ohlc_do_not_create_triggers(self):
        rows = {r['issue']:r for r in self.result['records']}
        for issue in ('46/26','34/25'):
            self.assertIsNone(rows[issue]['stock_observations']['first_observed_touches'])
            self.assertEqual(rows[issue]['stock_observations']['status'],'blocked')

    def test_later_target_does_not_erase_earlier_stock_stop(self):
        row = next(r for r in self.result['records'] if r['issue']=='169/25')
        e = row['stock_observations']['first_observed_touches']
        self.assertLess(e['stop1']['date'], e['target1']['date'])
        self.assertIsNone(row['wittmer_call_simulation']['pnl_eur'])

    def test_redemptions_are_counterfactual_not_strategy(self):
        rows = {r['issue']:r for r in self.result['records']}
        for issue, expected in [('169/25',D('2346.06')),('171/25',D('5937.82'))]:
            s=rows[issue]['hold_to_redemption_scenario']
            self.assertEqual(D(s['fee_scenarios'][0]['pnl_eur']),expected)
            self.assertFalse(s['executable_purchase_verified'])
        checks=[c for r in self.result['records'] if r['expired_by_cutoff'] for c in r['stock_observations']['independent_checks']]
        self.assertEqual(len(checks),3)
        self.assertTrue(all(all(c['price_matches'].values()) for c in checks))


if __name__=='__main__': unittest.main()
