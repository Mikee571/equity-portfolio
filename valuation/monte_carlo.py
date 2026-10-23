"""Monte Carlo on the Micron and GTT DCFs: instead of three scenarios, draw 20,000 sets of assumptions and look
at the distribution of value per share. Uses the same model code as the Excel check and the dashboard (models.py).

Run from valuation/:  python monte_carlo.py      -> results/monte_carlo_summary.csv, figures/mc_*.png
"""
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

import models

HERE = Path(__file__).parent
N = 20_000
SEED = 2026


# ------------------------------------------------------------------ Micron
def sample_micron(rng, n=N, width=1.0):
    """One row per simulation. Distributions are centred on the base case; see README for the reasoning."""
    z1, z2 = rng.standard_normal(n), rng.standard_normal(n)
    d = pd.DataFrame({
        "g27": np.clip(rng.normal(1.07, 0.12, n), 0.6, 1.5),           # consensus +107%
        "g28": np.clip(rng.normal(0.16, 0.12, n), -0.2, 0.5),          # consensus +16%
        # how far revenue falls back by FY31, relative to FY28 (base case 0.47)
        "fy31_vs_fy28": np.clip(np.exp(np.log(0.47) + 0.45 * width * z1), 0.10, 2.0),
        "m27": rng.uniform(0.74, 0.84, n),
        "m28_drop": rng.uniform(0.0, 0.12, n),
        # normalised margin, positively correlated (0.6) with how much revenue holds up
        "norm_margin": np.clip(0.35 + 0.10 * width * (0.6 * z1 + 0.8 * z2), 0.05, 0.70),
        "wacc": np.clip(rng.normal(models.MicronInputs().wacc, 0.015, n), 0.10, 0.19),
        "g": rng.uniform(0.02, 0.04, n),
    })
    return d


def value_micron(row):
    base = models.MICRON_SCENARIOS["Base"]
    tail = row.fy31_vs_fy28 ** (1 / 3) - 1
    growth = [row.g27, row.g28, tail, tail, tail]
    m28 = row.m27 - row.m28_drop
    gap = row.norm_margin - m28
    margin = [row.m27, m28, m28 + gap / 2, m28 + gap * 5 / 6, row.norm_margin]
    # capex follows revenue only partly (fabs are committed years ahead): scale base capex by sqrt(revenue ratio)
    rev, base_rev, capex = models.MicronInputs().rev0, models.MicronInputs().rev0, []
    for t in range(5):
        rev *= 1 + growth[t]
        base_rev *= 1 + base.growth[t]
        capex.append(base.capex[t] * (rev / base_rev) ** 0.5)
    s = models.MicronScenario(growth, margin, capex, row.norm_margin)
    p = replace(models.MicronInputs(), wacc_override=row.wacc, g=row.g)
    return models.micron_value(s, p)[0]


# ------------------------------------------------------------------ GTT
def sample_gtt(rng, n=N, width=1.0):
    lumpy = 0.35
    d = pd.DataFrame({
        "avg_orders": np.exp(np.log(60) + 0.30 * width * rng.standard_normal(n)),   # company estimate ~60 a year
        "h2_orders": rng.uniform(15, 40, n),
        "royalty": np.clip(rng.normal(9.5, 0.75, n), 7, 12),
        "marine_growth": rng.uniform(0.03, 0.12, n),
        "wacc": np.clip(rng.normal(models.GttInputs().wacc, 0.01, n), 0.07, 0.125),
        "g": rng.uniform(0.0, 0.025, n),
    })
    # orders are lumpy: each year varies around the average (mean-preserving lognormal noise)
    d["yearly"] = list(d.avg_orders.values[:, None] *
                       np.exp(rng.normal(-lumpy ** 2 / 2, lumpy, (n, 9))))
    return d


def value_gtt(row):
    p = replace(models.GttInputs(), wacc_override=row.wacc, royalty=row.royalty)
    return models.gtt_value(row.h2_orders, row.yearly, row.marine_growth, row.g, p)[0]


# ------------------------------------------------------------------ JPMorgan
def sample_jpm(rng, n=N, width=1.0):
    """Long-run ROTE around management's 17% target; a 30% chance of a credit cycle that pushes ROTE down to
    8-14% in years 2-3; cost of equity, growth and payout drawn around the model's inputs."""
    base = models.JpmInputs()
    return pd.DataFrame({
        "lr_rote": np.clip(rng.normal(0.17, 0.025 * width, n), 0.08, 0.30),
        "y1_rote": np.clip(rng.normal(0.20, 0.01, n), 0.15, 0.24),
        "credit_cycle": rng.random(n) < 0.30,
        "trough_rote": rng.uniform(0.08, 0.14, n),
        "coe": np.clip(rng.normal(base.coe, 0.01, n), 0.08, 0.13),
        "g": rng.uniform(0.03, 0.05, n),
        "payout": rng.uniform(0.45, 0.70, n),
    })


def value_jpm(row):
    path = [row.y1_rote + (row.lr_rote - row.y1_rote) * min(t, 4) / 4 for t in range(10)]   # glide to long run by Y5
    if row.credit_cycle:
        path[1] = path[2] = row.trough_rote
    g = min(row.g, row.coe - 0.02)                                                          # keep r - g sensible
    p = replace(models.JpmInputs(), coe_override=row.coe, g=g)
    return models.jpm_value(path, row.lr_rote, row.payout, p)


# ------------------------------------------------------------------ summary
def summarise(name, values, price, base_value, inputs, currency):
    q = np.percentile(values, [5, 25, 50, 75, 95])
    drivers = inputs.drop(columns=[c for c in ("yearly",) if c in inputs]).assign(value=values) \
        .corr(method="spearman")["value"].drop("value").sort_values(key=abs, ascending=False)
    return dict(company=name, currency=currency, price=price, base_case=base_value, p5=q[0], p25=q[1],
                median=q[2], p75=q[3], p95=q[4], mean=values.mean(),
                prob_above_price=(values > price).mean(),
                top_driver=f"{drivers.index[0]} ({drivers.iloc[0]:+.2f})",
                second_driver=f"{drivers.index[1]} ({drivers.iloc[1]:+.2f})"), drivers


def histogram(values, price, base_value, title, unit, path):
    import matplotlib
    matplotlib.use("Agg")
    import matplotlib.pyplot as plt
    fig, ax = plt.subplots(figsize=(7, 3.8), facecolor="#fcfcfb")
    ax.set_facecolor("#fcfcfb")
    hi = np.percentile(values, 99.5)
    ax.hist(values[values <= hi], bins=80, color="#2a78d6", edgecolor="#fcfcfb", linewidth=0.4)
    for x, lab, col, ls in ((np.median(values), f"Median {unit}{np.median(values):,.0f}", "#104281", "-"),
                            (base_value, f"Base case {unit}{base_value:,.0f}", "#eb6834", "--"),
                            (price, f"Price {unit}{price:,.0f} ({(values > price).mean():.0%} of runs above)", "#0b0b0b", ":")):
        ax.axvline(x, color=col, lw=1.8, ls=ls, label=lab)
    ax.legend(frameon=False, loc="upper right", fontsize=9, labelcolor="#0b0b0b")
    ax.set_title(title, loc="left", fontweight="bold", color="#0b0b0b")
    ax.set_xlabel(f"Value per share ({unit})", color="#52514e")
    ax.set_yticks([])
    for s in ("top", "right", "left"):
        ax.spines[s].set_visible(False)
    ax.spines["bottom"].set_color("#c3c2b7")
    ax.tick_params(colors="#52514e")
    fig.tight_layout()
    fig.savefig(path, dpi=160)
    plt.close(fig)


def main():
    rng = np.random.default_rng(SEED)
    (HERE / "results").mkdir(exist_ok=True)
    (HERE / "figures").mkdir(exist_ok=True)
    rows, all_drivers = [], {}

    mu_in = sample_micron(rng)
    mu = mu_in.apply(value_micron, axis=1).values
    mu_base = models.micron_value(models.MICRON_SCENARIOS["Base"])[0]
    r, drv = summarise("Micron", mu, models.MicronInputs().price, mu_base, mu_in, "$")
    rows.append(r)
    all_drivers["Micron"] = drv
    histogram(mu, r["price"], mu_base, f"Micron: {N:,} simulated DCFs", "$", HERE / "figures" / "mc_micron.png")

    gt_in = sample_gtt(rng)
    gt = gt_in.apply(value_gtt, axis=1).values
    b = models.GTT_SCENARIOS["Base"]
    gt_base = models.gtt_value(b["h2"], b["orders"], b["marine"], b["g"])[0]
    r, drv = summarise("GTT", gt, models.GttInputs().price, gt_base, gt_in, "€")
    rows.append(r)
    all_drivers["GTT"] = drv
    histogram(gt, r["price"], gt_base, f"GTT: {N:,} simulated DCFs", "€", HERE / "figures" / "mc_gtt.png")

    jp_in = sample_jpm(rng)
    jp = jp_in.apply(value_jpm, axis=1).values
    b = models.JPM_SCENARIOS["Base"]
    jp_base = models.jpm_value(b["rote"], b["lr"], b["payout"])
    r, drv = summarise("JPM", jp, models.JpmInputs().price, jp_base, jp_in.assign(credit_cycle=jp_in.credit_cycle.astype(int)), "$")
    rows.append(r)
    all_drivers["JPM"] = drv
    histogram(jp, r["price"], jp_base, f"JPMorgan: {N:,} simulated residual income models", "$", HERE / "figures" / "mc_jpm.png")

    # How much does the answer depend on how wide the uncertainty is? Re-run with 1.5x wider key distributions.
    wide = []
    for name, sampler, valuer, price in (("Micron", sample_micron, value_micron, models.MicronInputs().price),
                                         ("GTT", sample_gtt, value_gtt, models.GttInputs().price),
                                         ("JPM", sample_jpm, value_jpm, models.JpmInputs().price)):
        for width in (1.0, 1.5):
            v = sampler(np.random.default_rng(SEED), 10_000, width).apply(valuer, axis=1).values
            wide.append(dict(company=name, width=width, median=np.median(v), p95=np.percentile(v, 95),
                             prob_above_price=(v > price).mean()))
    wide = pd.DataFrame(wide)
    wide.to_csv(HERE / "results" / "monte_carlo_width.csv", index=False)
    print(wide.round(3).to_string(index=False))

    out = pd.DataFrame(rows)
    out.to_csv(HERE / "results" / "monte_carlo_summary.csv", index=False)
    pd.concat(all_drivers, names=["company", "input"]).rename("spearman_with_value").to_csv(
        HERE / "results" / "monte_carlo_drivers.csv")
    pd.set_option("display.width", 200)
    print(out.round(3).to_string(index=False))
    for k, v in all_drivers.items():
        print(f"\n{k} drivers (rank correlation with value):\n{v.round(2).to_string()}")


if __name__ == "__main__":
    main()
