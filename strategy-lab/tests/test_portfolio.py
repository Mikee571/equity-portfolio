"""
Tests del estudio de construcción de cartera (sin red).

Ejecutar desde strategy-lab/:  python -m unittest discover tests -v
"""
import os
import sys
import unittest

import numpy as np
import pandas as pd

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "portfolio_construction"))

import portfolio_mix as pm


class TestPortfolioMix(unittest.TestCase):
    def test_usd_to_eur_when_euro_rises(self):
        idx = pd.date_range("2020-01-31", periods=2, freq="ME")
        eurusd = pd.Series([1.00, 1.10], index=idx)        # el euro sube un 10%
        r = pd.Series([np.nan, 0.0], index=idx)             # el activo en USD no se mueve
        self.assertAlmostEqual(pm.to_eur(r, eurusd).iloc[1], 1 / 1.10 - 1)

    def test_mix_returns_weights_sum(self):
        s = pd.DataFrame({"core": [0.01], "value": [0.02], "tactical": [0.03]})
        r = pm.mix_returns(s, pm.MIXES["BASE_70_20_10"])
        self.assertAlmostEqual(r.iloc[0], 0.7 * 0.01 + 0.2 * 0.02 + 0.1 * 0.03)
        for w in pm.MIXES.values():
            self.assertAlmostEqual(sum(w.values()), 1.0)

    def test_sharpe_diff_of_identical_series(self):
        r = pd.Series(np.random.default_rng(1).normal(0.01, 0.04, 120))
        d, lo, hi = pm.sharpe_diff_ci(r, r)
        self.assertEqual((d, lo, hi), (0.0, 0.0, 0.0))


if __name__ == "__main__":
    unittest.main()
