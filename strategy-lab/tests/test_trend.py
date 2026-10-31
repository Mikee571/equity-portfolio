"""
Tests del backtest de trend following (sin red).

Ejecutar desde strategy-lab/:  python -m unittest discover tests -v
"""
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "trend_following"))

import backtest_trend as bt


def monthly_prices(values, start="2010-01-31"):
    idx = pd.date_range(start, periods=len(values), freq="ME")
    return pd.DataFrame({"A": values}, index=idx, dtype=float)


class TestSignals(unittest.TestCase):
    def test_sma10_long_above_average(self):
        p = monthly_prices(list(range(1, 21)))               # subida continua
        s = bt.signals(p, "SMA10")
        self.assertTrue((s["A"].dropna() == 1).all())
        self.assertTrue(s["A"].iloc[:12].isna().all())       # sin 13 meses de historia

    def test_tsmom_flat_after_a_fall(self):
        p = monthly_prices([100.0] * 13 + [90.0] * 3)
        s = bt.signals(p, "TSMOM12")
        self.assertEqual(s["A"].iloc[-1], 0.0)

    def test_signal_uses_only_the_past(self):
        base = list(np.linspace(100, 120, 20))
        a = bt.signals(monthly_prices(base), "SMA10")
        b = bt.signals(monthly_prices(base[:15] + [10.0] * 5), "SMA10")
        pd.testing.assert_series_equal(a["A"].iloc[:15], b["A"].iloc[:15])


class TestBacktest(unittest.TestCase):
    def test_all_cash_earns_the_bill(self):
        p = monthly_prices([100.0 - i for i in range(30)])   # caída continua -> siempre fuera
        cash = pd.Series(6.0, index=p.index)                  # 6% anual
        res = bt.backtest(p, cash, "SMA10")
        np.testing.assert_allclose(res["net"], 0.005)
        self.assertTrue((res["invested"] == 0).all())

    def test_buy_hold_matches_asset_minus_entry_cost(self):
        vals = [100 * 1.01 ** i for i in range(30)]
        p = monthly_prices(vals)
        res = bt.backtest(p, pd.Series(0.0, index=p.index), "BUY_HOLD")
        self.assertAlmostEqual(res["net"].iloc[0], 0.01 - bt.COST_PER_SIDE)
        np.testing.assert_allclose(res["net"].iloc[1:], 0.01)

    def test_return_is_booked_the_month_after_the_signal(self):
        vals = [100.0] * 14 + [110.0, 121.0]
        p = monthly_prices(vals)
        res = bt.backtest(p, pd.Series(0.0, index=p.index), "BUY_HOLD")
        # Primera posición al cierre del mes de índice 12 (13 meses de historia): su
        # retorno (plano) se apunta en el mes 13; el +10% llega al mes siguiente
        self.assertEqual(res.index[0], p.index[13])
        self.assertAlmostEqual(res["net"].iloc[0], 0.0 - bt.COST_PER_SIDE)
        self.assertAlmostEqual(res["net"].iloc[1], 0.10)


class TestStats(unittest.TestCase):
    def test_sharpe_diff_of_identical_series_is_zero(self):
        idx = pd.date_range("2010-01-31", periods=120, freq="ME")
        r = np.random.default_rng(0).normal(0.005, 0.03, 120)
        df = pd.DataFrame({"net": r, "cash": 0.001}, index=idx)
        point, lo, hi = bt.sharpe_diff_ci(df, df)
        self.assertAlmostEqual(point, 0.0)
        self.assertAlmostEqual(lo, 0.0)
        self.assertAlmostEqual(hi, 0.0)


if __name__ == "__main__":
    unittest.main()
