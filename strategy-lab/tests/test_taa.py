"""
Tests del backtest de TAA sectorial (sin red).

Ejecutar desde strategy-lab/:  python -m unittest discover tests -v
"""
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "taa_sectorial"))

import backtest_taa as bt


def monthly_frame(n=30, rate=None, growth=None, start="2010-01-31"):
    idx = pd.date_range(start, periods=n, freq="ME")
    growth = growth or {"XLF": 0.0, "XLE": 0.0, "XLK": 0.0, "XLB": 0.0}
    data = {s: 100 * (1 + g) ** np.arange(n) for s, g in growth.items()}
    data[bt.RATE] = rate if rate is not None else np.full(n, 2.0)
    return pd.DataFrame(data, index=idx)


class TestRegime(unittest.TestCase):
    def test_classification(self):
        rate = pd.Series(np.r_[np.full(6, 1.0), np.full(6, 2.0), np.full(6, 1.0), np.full(6, 1.1)],
                         index=pd.date_range("2010-01-31", periods=24, freq="ME"))
        reg = bt.regime(rate)
        self.assertTrue(reg.iloc[:6].isna().all())
        self.assertEqual(reg.iloc[6], "tightening")      # +1.0 pp en 6 meses
        self.assertEqual(reg.iloc[12], "easing")         # -1.0 pp
        self.assertEqual(reg.iloc[23], "neutral")        # +0.1 pp, dentro de la banda

    def test_fed_rule_maps_regimes_to_baskets(self):
        m = monthly_frame(n=24, rate=np.r_[np.full(6, 1.0), np.full(18, 3.0)])
        tw = bt.target_weights(m, "FED_REGIME")
        first = tw.iloc[0]                                # 2010-09-30: subida de 2 pp
        self.assertEqual(first["XLF"], 0.5)
        self.assertEqual(first["XLE"], 0.5)
        self.assertTrue((tw.index.month.isin([3, 6, 9, 12])).all())

    def test_momentum_picks_top_two(self):
        m = monthly_frame(n=30, growth={"XLF": 0.01, "XLE": -0.01, "XLK": 0.03, "XLB": 0.02})
        tw = bt.target_weights(m, "MOMENTUM_TOP2")
        self.assertEqual(set(tw.iloc[-1][tw.iloc[-1] > 0].index), {"XLK", "XLB"})


class TestBacktest(unittest.TestCase):
    def test_flat_prices_only_pay_entry_cost(self):
        m = monthly_frame(n=24)
        res = bt.backtest(m, bt.target_weights(m, "EQUAL"))
        self.assertAlmostEqual(res["net"].iloc[0], -bt.COST_PER_SIDE)
        self.assertAlmostEqual(res["net"].iloc[1:].sum(), 0.0)

    def test_weights_drift_between_rebalances(self):
        # XLK sube un 10% al mes: entre rebalanceos su peso crece, y al rebalancear se paga coste
        m = monthly_frame(n=24, growth={"XLF": 0.0, "XLE": 0.0, "XLK": 0.10, "XLB": 0.0})
        res = bt.backtest(m, bt.target_weights(m, "EQUAL"))
        self.assertGreater(res["net"].iloc[2], res["net"].iloc[1])   # peso de XLK mayor el 2º mes
        rebalance_months = res["turnover"] > 0
        self.assertTrue((res.index[rebalance_months].month.isin([1, 4, 7, 10])).all())


if __name__ == "__main__":
    unittest.main()
