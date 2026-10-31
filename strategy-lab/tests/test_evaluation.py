"""
Tests de la purga del walk-forward y de las métricas de evaluation.py (sin red).

Ejecutar desde strategy-lab/:  python -m unittest discover tests -v
(también funcionan con pytest).
"""
import os
import sys
import unittest

import numpy as np
import pandas as pd
from sklearn.metrics import f1_score

sys.path.insert(0, os.path.join(os.path.dirname(os.path.dirname(os.path.abspath(__file__))), "signal_lab"))

from evaluation import (block_bootstrap_ci, brier_skill_score, check_promotion, f1_always_up,
                        resolve_live_signals, selection_period, tranche_strategy_returns)
from ml_pipeline import run_walk_forward_model, walk_forward_split_indices
from targets_and_benchmark import build_binary_target


class TestPurge(unittest.TestCase):
    def test_gap_between_train_and_test(self):
        for train_end, test_start, _ in walk_forward_split_indices(500, 252, 21, purge_gap=10):
            self.assertEqual(test_start - train_end, 10)

    def test_first_fold_keeps_min_train_size(self):
        train_end, test_start, _ = walk_forward_split_indices(500, 252, 21, purge_gap=10)[0]
        self.assertEqual(train_end, 252)
        self.assertEqual(test_start, 262)

    def test_no_gap_reproduces_old_split(self):
        folds = walk_forward_split_indices(300, 252, 21)
        self.assertEqual(folds, [(252, 252, 273), (273, 273, 294), (294, 294, 300)])

    def test_purged_train_labels_never_see_test_prices(self):
        # La etiqueta de la fila t usa el cierre de t + horizon.
        horizon = 10
        for train_end, test_start, _ in walk_forward_split_indices(800, 252, 21, purge_gap=horizon):
            last_price_used_by_train = (train_end - 1) + horizon
            self.assertLess(last_price_used_by_train, test_start)


def _synthetic(n=420, seed=0):
    rng = np.random.default_rng(seed)
    dates = pd.bdate_range("2020-01-01", periods=n)
    close = pd.Series(100 * np.exp(np.cumsum(rng.normal(0, 0.01, n))), index=dates)
    X = pd.DataFrame({"r1": close.pct_change(), "r5": close.pct_change(5)}, index=dates)
    y = build_binary_target(close, horizon=10, threshold=0.0)
    return X, y


class TestWalkForwardModel(unittest.TestCase):
    params = {"n_estimators": 5, "max_depth": 2}

    def test_first_test_date_shifts_by_gap_and_records_base_rate(self):
        X, y = _synthetic()
        valid_dates = y.dropna().index
        res = run_walk_forward_model(X, y, "xgboost", min_train_size=200, retrain_every=21,
                                     model_params=self.params, purge_gap=10)
        self.assertEqual(res["date"].iloc[0], valid_dates[210])
        self.assertTrue(res["base_rate_train"].between(0, 1).all())

    def test_rolling_window_matches_expanding_on_first_fold(self):
        X, y = _synthetic()
        kwargs = dict(min_train_size=200, retrain_every=21, model_params=self.params, purge_gap=10)
        expanding = run_walk_forward_model(X, y, "xgboost", **kwargs)
        rolling = run_walk_forward_model(X, y, "xgboost", max_train_size=200, **kwargs)
        first = expanding["date"] < expanding["date"].iloc[21]
        pd.testing.assert_frame_equal(expanding[first], rolling[first])
        self.assertFalse(np.allclose(expanding["y_proba"], rolling["y_proba"]))

    def test_calibrated_run_completes_with_purge(self):
        X, y = _synthetic()
        res = run_walk_forward_model(X, y, "xgboost", min_train_size=200, retrain_every=21,
                                     model_params=self.params, purge_gap=10, calibrate=True)
        self.assertFalse(res.empty)


class TestMetrics(unittest.TestCase):
    def test_f1_always_up_matches_sklearn(self):
        y = np.array([1, 0, 1, 1, 0, 0, 0, 1, 0, 0])
        self.assertAlmostEqual(f1_always_up(y.mean()), f1_score(y, np.ones_like(y)))

    def test_brier_skill_score(self):
        y = np.array([1, 0, 1, 0])
        self.assertAlmostEqual(brier_skill_score(y, y, 0.5), 1.0)
        self.assertAlmostEqual(brier_skill_score(y, [0.5] * 4, 0.5), 0.0)
        self.assertLess(brier_skill_score(y, [0.1, 0.9, 0.1, 0.9], 0.5), 0)

    def test_bootstrap_ci_random_scores_contain_half(self):
        rng = np.random.default_rng(1)
        y = rng.integers(0, 2, 600)
        low, high = block_bootstrap_ci(y, rng.random(600))
        self.assertLess(low, 0.5)
        self.assertGreater(high, 0.5)

    def test_bootstrap_ci_perfect_scores(self):
        y = np.random.default_rng(2).integers(0, 2, 600)
        low, _ = block_bootstrap_ci(y, y + 0.0)
        self.assertGreater(low, 0.99)

    def test_bootstrap_ci_short_sample_is_nan(self):
        self.assertTrue(np.isnan(block_bootstrap_ci([0, 1] * 10, [0.5] * 20)[0]))


class TestTrancheStrategy(unittest.TestCase):
    close = pd.Series(np.linspace(100, 130, 31), index=pd.bdate_range("2024-01-01", periods=31))

    def test_always_long_equals_buy_hold_after_ramp(self):
        signals = pd.Series(1, index=self.close.index[:20])
        out = tranche_strategy_returns(signals, self.close, horizon=5, cost_pct=0.0)
        np.testing.assert_allclose(out["strategy"].iloc[4:], out["buy_hold"].iloc[4:])
        self.assertAlmostEqual(out["exposure"].iloc[0], 0.2)

    def test_single_signal_is_held_horizon_days(self):
        signals = pd.Series(0, index=self.close.index[:20])
        signals.iloc[3] = 1
        out = tranche_strategy_returns(signals, self.close, horizon=5, cost_pct=0.0)
        self.assertEqual((out["exposure"] > 0).sum(), 5)
        np.testing.assert_allclose(out["exposure"].iloc[3:8], 0.2)

    def test_each_day_counted_once(self):
        # Antes: cada día con señal encadenaba el retorno a `horizon` días.
        signals = pd.Series(1, index=self.close.index[:26])
        out = tranche_strategy_returns(signals, self.close, horizon=5, cost_pct=0.0)
        strategy_total = (1 + out["strategy"]).prod() - 1
        self.assertLess(strategy_total, self.close.iloc[26] / self.close.iloc[0] - 1)

    def test_costs_charged_on_exposure_changes(self):
        signals = pd.Series(1, index=self.close.index[:20])
        gross = tranche_strategy_returns(signals, self.close, 5, cost_pct=0.0)["strategy"].sum()
        net = tranche_strategy_returns(signals, self.close, 5, cost_pct=0.01)["strategy"].sum()
        self.assertAlmostEqual(gross - net, 1.0 * 0.01 / 2)


class TestLiveAndPeriods(unittest.TestCase):
    def test_resolve_live_signals(self):
        close = pd.Series([100, 101, 103, 102, 99], index=pd.bdate_range("2026-06-01", periods=5),
                          dtype=float)
        history = pd.DataFrame({
            "date": ["2026-06-01", "2026-06-02", "2026-06-04"],
            "ticker": "GDX", "signal": [1, 0, 1], "probability": [0.7, 0.3, 0.6],
            "horizon_days": 2, "threshold": 0.01,
        })
        out = resolve_live_signals(history, {"GDX": close})
        self.assertEqual(out["y_true"].iloc[0], 1.0)   # 103 / 100 - 1 = 3% > 1%
        self.assertEqual(out["y_true"].iloc[1], 0.0)   # 102 / 101 - 1 < 1%
        self.assertTrue(np.isnan(out["y_true"].iloc[2]))  # horizonte sin vencer

    def test_selection_period_labels(self):
        labels = selection_period(["2023-01-02", "2025-01-02", "2026-09-01"])
        self.assertEqual(list(labels), ["pre_seleccion", "seleccion", "post_seleccion"])

    def test_promotion_requires_every_condition(self):
        good = {"n": 200, "auc_ci_low": 0.55, "sharpe_signal": 1.0, "sharpe_buy_hold": 0.5, "bss": 0.05}
        self.assertTrue(check_promotion(good, calibrated=True)["promociona"])
        self.assertFalse(check_promotion({**good, "auc_ci_low": 0.48}, calibrated=True)["promociona"])
        self.assertFalse(check_promotion({**good, "bss": -0.1}, calibrated=True)["promociona"])
        self.assertTrue(check_promotion({**good, "bss": -0.1}, calibrated=False)["promociona"])
        self.assertFalse(check_promotion({**good, "n": 50}, calibrated=False)["promociona"])


if __name__ == "__main__":
    unittest.main()
