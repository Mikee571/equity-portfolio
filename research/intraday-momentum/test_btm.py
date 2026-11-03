"""Offline tests of the Beat the Market backtest.  python -m unittest test_btm -v"""
import unittest

import numpy as np
import pandas as pd

import btm


def make_day(date: str, closes, open_=100.0, vol=1000):
    idx = pd.date_range(f"{date} 09:30", periods=len(closes), freq="1h", tz=btm.TZ)
    c = np.asarray(closes, float)
    o = np.r_[open_, c[:-1]]
    return pd.DataFrame({"Open": o, "High": np.maximum(o, c), "Low": np.minimum(o, c),
                         "Close": c, "Volume": vol}, index=idx)


SIG = pd.Series(0.01, index=["09:30", "10:30", "11:30", "12:30", "13:30", "14:30", "15:30"])
P0 = btm.Params(cost_per_share=0.0)


class SimulateDay(unittest.TestCase):
    def test_flat_day_no_trades(self):
        d = make_day("2024-03-04", [100.2, 99.9, 100.1, 100.0, 99.8, 100.3, 100.1])
        self.assertEqual(btm.simulate_day(d, 100.0, SIG, 100, P0), (0.0, 0))

    def test_trend_up_long_held_to_close(self):
        d = make_day("2024-03-04", [101.5, 102, 102.5, 103, 103.5, 104, 105])
        pnl, fills = btm.simulate_day(d, 100.0, SIG, 100, P0)
        self.assertEqual(fills, 2)
        self.assertAlmostEqual(pnl, 100 * (105 - 101.5))

    def test_trend_down_short(self):
        d = make_day("2024-03-04", [98.5, 98, 97, 96, 95, 94, 93])
        pnl, fills = btm.simulate_day(d, 100.0, SIG, 100, P0)
        self.assertAlmostEqual(pnl, 100 * (98.5 - 93))

    def test_gap_down_raises_upper_band(self):
        # Opens at 100 after closing at 102: the upper band is measured from 102.
        d = make_day("2024-03-04", [101.5, 101.5, 101.5, 101.5, 101.5, 101.5, 101.5])
        self.assertEqual(btm.simulate_day(d, 102.0, SIG, 100, P0)[1], 0)
        self.assertEqual(btm.simulate_day(d, 100.0, SIG, 100, P0)[1], 2)

    def test_stop_then_flip(self):
        # Goes long, then falls below the lower band: closes and opens a short.
        d = make_day("2024-03-04", [101.5, 98.5, 98.0, 98.0, 98.0, 98.0, 98.0])
        pnl, fills = btm.simulate_day(d, 100.0, SIG, 100, P0)
        self.assertEqual(fills, 4)
        self.assertAlmostEqual(pnl, 100 * (98.5 - 101.5) + 100 * (98.5 - 98.0))

    def test_costs_per_fill(self):
        d = make_day("2024-03-04", [101.5, 102, 102.5, 103, 103.5, 104, 105])
        p = btm.Params(cost_per_share=0.01)
        pnl, _ = btm.simulate_day(d, 100.0, SIG, 100, p)
        self.assertAlmostEqual(pnl, 100 * 3.5 - 2 * 100 * 0.01)


class NoLookahead(unittest.TestCase):
    def test_sigma_uses_only_previous_days(self):
        days = [make_day(f"2024-03-{d:02d}", [100 + 0.1 * d] * 7) for d in range(1, 17)]
        s1 = btm.noise_sigma(days[:15], 14)
        days[15] = make_day("2024-03-16", [150.0] * 7)
        s2 = btm.noise_sigma(days[:15], 14)
        pd.testing.assert_series_equal(s1, s2)

    def test_sizing_ignores_same_day_return(self):
        bars = pd.concat([make_day(f"2024-03-{d:02d}", np.linspace(100.2, 101, 7)) for d in range(1, 18)])
        dates = pd.to_datetime([f"2024-02-{d:02d}" for d in range(1, 29)] + [f"2024-03-{d:02d}" for d in range(1, 18)])
        rng = np.random.default_rng(0)
        daily = pd.Series(100 * np.cumprod(1 + rng.normal(0, 0.01, len(dates))), index=dates)
        r1 = btm.backtest(bars, daily)
        daily2 = daily.copy()
        daily2.iloc[-1] *= 1.5  # changes the last day's close
        r2 = btm.backtest(bars, daily2)
        self.assertEqual(r1["lev"].iloc[-1], r2["lev"].iloc[-1])


if __name__ == "__main__":
    unittest.main()
