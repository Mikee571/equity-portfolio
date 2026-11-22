"""Micron update, 22 November 2026: the October model re-run with the new price, risk-free rate and beta,
plus a NAND price sensitivity. The company has not filed anything since the 10-K, so balance sheet, share
count and scenario paths stay as in build_model.py; consensus for FY27-28 has not moved either.

Run from valuation/:  python micron/update_2026_11.py
"""
import sys
from dataclasses import replace
from pathlib import Path

import numpy as np

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
import models  # noqa: E402
import monte_carlo  # noqa: E402

OLD = models.MicronInputs()                         # close of 2026-10-16
NEW = replace(OLD, price=594.51,                    # close of 2026-11-20 (Yahoo Finance)
              rf=0.0491,                            # ^TNX close 2026-11-20
              raw_beta=2.40)                        # Yahoo 5y monthly 2.398; own 5y monthly regression 2.39
WEIGHTS = {"Bear": 0.30, "Base": 0.50, "Bull": 0.20}

# Consensus (Yahoo Finance, 2026-11-22) vs the model's anchor (2026-10-16): FY27 revenue $276.0bn vs $275.5bn,
# FY28 $320.8bn vs $318.9bn; FY27 EPS $176.67 vs $176.55, FY28 $208.83 vs $206.89. No reason to re-anchor.
# NAND was 23.9% of FY26 revenue ($31,785mm of $133,188mm, 10-K FY26, revenue by technology).
NAND_SHARE = 0.24


def weighted(p):
    vals = {k: models.micron_value(s, p)[0] for k, s in models.MICRON_SCENARIOS.items()}
    return vals, sum(WEIGHTS[k] * v for k, v in vals.items())


def nand_case(cut, persistent, p=NEW):
    """Base case with FY28 NAND prices `cut` below plan. The lost revenue drops straight to operating income
    (same bits, same costs). persistent=True keeps the lower revenue base for FY29-31 and the terminal year."""
    b = models.MICRON_SCENARIOS["Base"]
    rev27 = p.rev0 * (1 + b.growth[0])
    rev28 = rev27 * (1 + b.growth[1])
    lost = NAND_SHARE * cut * rev28
    m28 = (b.margin[1] * rev28 - lost) / (rev28 - lost)
    growth = [b.growth[0], (rev28 - lost) / rev27 - 1] + b.growth[2:]
    if not persistent:                              # FY29 grows back to the original FY29 revenue
        growth[2] = rev28 * (1 + b.growth[2]) / (rev28 - lost) - 1
    s = replace(b, growth=growth, margin=[b.margin[0], m28] + b.margin[2:])
    return models.micron_value(s, p)[0], m28


if __name__ == "__main__":
    print(f"WACC {OLD.wacc:.2%} -> {NEW.wacc:.2%}")
    old_v, old_w = weighted(OLD)
    new_v, new_w = weighted(NEW)
    price_only = weighted(replace(OLD, price=NEW.price))[1]
    for k in WEIGHTS:
        print(f"{k:5s} {old_v[k]:8.0f} -> {new_v[k]:8.0f}   vs price {new_v[k] / NEW.price - 1:+.0%}")
    print(f"Weighted {old_w:.0f} -> {new_w:.0f} ({new_w / NEW.price - 1:+.0%} vs ${NEW.price}); "
          f"price change alone: {price_only:.0f}")

    im_old, im_new = models.micron_implied_margin(OLD), models.micron_implied_margin(NEW)
    print(f"Reverse DCF, margin from FY29 on base revenue: {im_old:.0%} at ${OLD.price} -> {im_new:.0%} at ${NEW.price}")
    pos = (NEW.price - new_v["Base"]) / (new_v["Bull"] - new_v["Base"])
    print(f"The price sits {pos:.0%} of the way from base to bull (was "
          f"{(OLD.price - old_v['Base']) / (old_v['Bull'] - old_v['Base']):.0%})")

    print("\nNAND sensitivity on the base case (FY28 NAND price vs plan):")
    for cut in (0.10, 0.20, 0.30):
        v1, m1 = nand_case(cut, False)
        v2, _ = nand_case(cut, True)
        print(f"  -{cut:.0%}: FY28 margin {m1:.1%}; one year {v1:.0f} ({v1 - new_v['Base']:+.0f}); "
              f"persistent {v2:.0f} ({v2 - new_v['Base']:+.0f})")

    # Monte Carlo: same draws as monte_carlo.py, WACC centre moved to the new WACC
    rng = np.random.default_rng(monte_carlo.SEED)
    d = monte_carlo.sample_micron(rng)
    d["wacc"] = np.clip(d.wacc + NEW.wacc - OLD.wacc, 0.10, 0.19)
    vals = d.apply(monte_carlo.value_micron, axis=1).values
    print(f"\nMonte Carlo (20,000 runs): median {np.median(vals):.0f}, above ${NEW.price}: {(vals > NEW.price).mean():.1%}, "
          f"above ${OLD.price}: {(vals > OLD.price).mean():.1%}")

    # what the market move explains: MU -32.4% vs S&P 500 -9.6% and SOXX -25.0% from 2026-10-16 to 2026-11-20
    print(f"\nBeta {NEW.raw_beta} x S&P 500 -9.6% = {NEW.raw_beta * -0.096:.1%} of MU's -32.4%; semis (SOXX) -25.0%")
