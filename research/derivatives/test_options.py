"""Checks the pricers against each other and against textbook identities.

Run from research/derivatives/: python -m unittest test_options -v
"""
import math
import unittest

import options as o

S, K, T, r, q, sig = 100.0, 105.0, 0.75, 0.04, 0.01, 0.25


class TestOptions(unittest.TestCase):
    def test_known_value(self):
        # Hull, Options, Futures and Other Derivatives: S=42, K=40, T=0.5, r=10%, sigma=20% -> call 4.76, put 0.81
        self.assertAlmostEqual(o.bs_price(42, 40, 0.5, 0.10, 0.20, "call"), 4.76, places=2)
        self.assertAlmostEqual(o.bs_price(42, 40, 0.5, 0.10, 0.20, "put"), 0.81, places=2)

    def test_put_call_parity(self):
        c, p = o.bs_price(S, K, T, r, sig, "call", q), o.bs_price(S, K, T, r, sig, "put", q)
        self.assertAlmostEqual(c - p, S * math.exp(-q * T) - K * math.exp(-r * T), places=10)

    def test_binomial_converges_to_bs(self):
        for kind in ("call", "put"):
            self.assertAlmostEqual(o.binomial_price(S, K, T, r, sig, kind, q, steps=2000),
                                   o.bs_price(S, K, T, r, sig, kind, q), delta=0.005)

    def test_american_put_worth_more(self):
        eu = o.binomial_price(S, K, T, 0.08, sig, "put", 0.0, steps=1000)
        am = o.binomial_price(S, K, T, 0.08, sig, "put", 0.0, steps=1000, american=True)
        self.assertGreater(am, eu + 0.05)
        # an American call on a non-dividend stock is never exercised early
        self.assertAlmostEqual(o.binomial_price(S, K, T, r, sig, "call", 0.0, 1000, american=True),
                               o.binomial_price(S, K, T, r, sig, "call", 0.0, 1000), places=8)

    def test_monte_carlo_within_error(self):
        for kind in ("call", "put"):
            price, se = o.mc_price(S, K, T, r, sig, kind, q, paths=400_000, seed=1)
            self.assertLess(abs(price - o.bs_price(S, K, T, r, sig, kind, q)), 4 * se)

    def test_control_variate_reduces_error(self):
        _, se_plain = o.mc_price(S, K, T, r, sig, "call", q, seed=2, control_variate=False)
        _, se_cv = o.mc_price(S, K, T, r, sig, "call", q, seed=2, control_variate=True)
        self.assertLess(se_cv, se_plain / 2)

    def test_greeks_match_finite_differences(self):
        g = o.bs_greeks(S, K, T, r, sig, "call", q)
        h = 1e-4
        f = lambda **kw: o.bs_price(kw.get("S", S), K, kw.get("T", T), kw.get("r", r), kw.get("sig", sig), "call", q)
        self.assertAlmostEqual(g["delta"], (f(S=S + h) - f(S=S - h)) / (2 * h), places=5)
        self.assertAlmostEqual(g["gamma"], (f(S=S + h) - 2 * f() + f(S=S - h)) / h ** 2, places=3)
        self.assertAlmostEqual(g["vega"], (f(sig=sig + h) - f(sig=sig - h)) / (2 * h), places=4)
        self.assertAlmostEqual(g["theta"], -(f(T=T + h) - f(T=T - h)) / (2 * h), places=4)
        self.assertAlmostEqual(g["rho"], (f(r=r + h) - f(r=r - h)) / (2 * h), places=4)

    def test_implied_vol_round_trip(self):
        for kind in ("call", "put"):
            for s in (0.08, 0.25, 0.9):
                p = o.bs_price(S, K, T, r, s, kind, q)
                self.assertAlmostEqual(o.implied_vol(p, S, K, T, r, kind, q), s, places=6)


if __name__ == "__main__":
    unittest.main()
