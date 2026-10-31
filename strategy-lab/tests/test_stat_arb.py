"""
Tests del Kalman, el OU y la contabilidad del backtest walk-forward de stat
arb (sin red).

Ejecutar desde strategy-lab/:  python -m unittest discover tests -v
"""
import os
import sys
import unittest

import numpy as np

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "stat_arb"))

import backtest_walkforward as bw
from kalman_ou import calibrate_sigma_eta, fit_ou, kalman_beta, ols_alpha_beta


def synthetic_pair(beta_path, n=600, sigma_eps=0.01, seed=0):
    rng = np.random.default_rng(seed)
    x = 4 + np.cumsum(rng.normal(0, 0.01, n))
    y = 0.2 + beta_path * x + rng.normal(0, sigma_eps, n)
    return y, x


class TestKalman(unittest.TestCase):
    def test_zero_process_noise_keeps_beta(self):
        y, x = synthetic_pair(np.full(600, 1.0))
        k = kalman_beta(y, x, 0.2, 1.0, 0.01, 0.0, p0=1e-12)
        np.testing.assert_allclose(k["beta_post"], 1.0, atol=1e-6)
        np.testing.assert_allclose(k["innov"], y - 0.2 - x, atol=1e-6)

    def test_prior_beta_uses_only_past(self):
        # beta_prior[k] must not depend on y[k]
        y, x = synthetic_pair(np.full(600, 1.0))
        a = kalman_beta(y, x, 0.2, 1.0, 0.01, 1e-3)
        y2 = y.copy()
        y2[300] += 5.0
        b = kalman_beta(y2, x, 0.2, 1.0, 0.01, 1e-3)
        self.assertEqual(a["beta_prior"][300], b["beta_prior"][300])
        self.assertNotEqual(a["beta_prior"][301], b["beta_prior"][301])

    def test_tracks_a_beta_shift(self):
        path = np.r_[np.full(300, 1.0), np.full(300, 1.2)]
        y, x = synthetic_pair(path)
        k = kalman_beta(y, x, 0.2, 1.0, 0.01, 1e-3)
        self.assertAlmostEqual(k["beta_post"][-1], 1.2, delta=0.02)

    def test_mle_picks_small_noise_for_constant_beta(self):
        y, x = synthetic_pair(np.full(600, 1.0))
        a, b, s = ols_alpha_beta(y, x)
        sigma_const, _ = calibrate_sigma_eta(y, x, a, b, s)
        rng = np.random.default_rng(3)
        y2, x2 = synthetic_pair(1.0 + np.cumsum(rng.normal(0, 0.003, 600)))
        a2, b2, s2 = ols_alpha_beta(y2, x2)
        sigma_rw, _ = calibrate_sigma_eta(y2, x2, a2, b2, s2)
        self.assertLess(sigma_const, sigma_rw)


class TestOU(unittest.TestCase):
    def test_recovers_parameters(self):
        rng = np.random.default_rng(1)
        kappa, theta, sigma, n = 0.05, 0.3, 0.02, 20000
        s = np.empty(n)
        s[0] = theta
        for t in range(1, n):
            s[t] = s[t - 1] + kappa * (theta - s[t - 1]) + sigma * rng.normal()
        ou = fit_ou(s)
        self.assertAlmostEqual(ou["theta"], theta, delta=0.01)
        self.assertAlmostEqual(ou["half_life"], np.log(2) / -np.log(1 - kappa), delta=2.0)

    def test_random_walk_has_no_reversion(self):
        s = np.cumsum(np.random.default_rng(2).normal(0, 1, 5000)) + 1000
        ou = fit_ou(s)
        self.assertTrue(ou is None or ou["half_life"] > 200)


class TestSimulate(unittest.TestCase):
    def test_round_trip_costs_and_forced_close(self):
        sig = np.array([0.0, 2.0, 1.0, 1.0])          # short spread at t=1, closed at window end
        hedge = np.full(4, 1.0)
        zeros = np.zeros(4)
        rets, trades = bw.simulate(sig, hedge, zeros, zeros, 1.5, 0.5)
        borrow = 0.5 * bw.BORROW_ANNUAL / 252
        self.assertAlmostEqual(rets.sum(), -2 * bw.COST_PER_SIDE - 2 * borrow)
        self.assertEqual(len(trades), 1)
        self.assertEqual(trades[0]["side"], -1)

    def test_pnl_starts_the_day_after_the_signal(self):
        sig = np.array([-2.0, -2.0, 0.0, 0.0])        # long spread decided at close of t=0
        ry = np.array([0.10, 0.02, 0.0, 0.0])          # the 10% on t=0 happened before the decision
        rets, _ = bw.simulate(sig, np.full(4, 1.0), ry, np.zeros(4), 1.5, 0.5)
        self.assertAlmostEqual(rets[0], -bw.COST_PER_SIDE)
        self.assertAlmostEqual(rets[1], 0.5 * 0.02 - 0.5 * bw.BORROW_ANNUAL / 252)

    def test_exit_when_spread_crosses_past_zero(self):
        sig = np.array([2.0, -3.0, -3.0])             # short at t=0, reverts through zero at t=1
        _, trades = bw.simulate(sig, np.full(3, 1.0), np.zeros(3), np.zeros(3), 1.5, 0.5)
        self.assertEqual(trades[0]["days"], 1)

    def test_kalman_rehedging_is_charged(self):
        sig = np.array([-2.0, -2.0, -2.0, -2.0])
        flat = bw.simulate(sig, np.full(4, 1.0), np.zeros(4), np.zeros(4), 1.5, 0.5)[0].sum()
        moving = bw.simulate(sig, np.array([1.0, 1.2, 1.0, 1.0]), np.zeros(4), np.zeros(4), 1.5, 0.5)[0].sum()
        self.assertLess(moving, flat)


if __name__ == "__main__":
    unittest.main()


class TestJointCalibration(unittest.TestCase):
    def test_joint_mle_gives_unit_variance_innovations(self):
        rng = np.random.default_rng(5)
        y, x = synthetic_pair(1.0 + np.cumsum(rng.normal(0, 0.002, 600)), sigma_eps=0.005)
        a, b, _ = ols_alpha_beta(y, x)
        from kalman_ou import calibrate_joint
        sigma_eps, sigma_eta = calibrate_joint(y, x, a, b)
        k = kalman_beta(y, x, a, b, sigma_eps, sigma_eta)
        z = k["innov"][50:] / np.sqrt(k["S"][50:])
        self.assertAlmostEqual(z.std(), 1.0, delta=0.15)
