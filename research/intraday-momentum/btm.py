"""
Beat the Market (Zarattini, Aziz and Barbon, 2024): replication and post-publication test
========================================================================================
Design fixed on 2026-10-30, before seeing any result.

Rules, as the paper gives them (SFI 24-97, section 3 and table 3, final version
"Curr.Band + VWAP Dyn."):

- Noise area. For each time of day HH:MM, sigma = mean of |Close(HH:MM) /
  Open(9:30) - 1| over the previous 14 days.
  UB = max(Open_t, Close_t-1) * (1 + sigma), LB = min(Open_t, Close_t-1) * (1 - sigma).
- Entry. At each check, if flat: long if price > UB, short if price < LB.
- Exit. A long exits if price < max(UB, VWAP); a short exits if price >
  min(LB, VWAP). If on exit the price is already beyond the opposite band,
  the opposite position is opened at the same check. Everything closes at the close.
- Size. Shares = floor(AUM_t-1 * min(4, 2% / sigma_SPY) / Open_t), with
  sigma_SPY the standard deviation of the previous 14 daily returns.
- Costs: $0.0035 commission + $0.001 slippage per share per trade.
- Starting capital $100,000.

The only difference forced by the data: the paper uses 1-minute bars and
checks every 30 minutes (HH:00 and HH:30). yfinance only has 1-hour bars
since Dec 2023, so I check every hour (10:30, 11:30, ..., 15:30) and VWAP
comes from the hourly bars ((H+L+C)/3 weighted by volume). To measure what that
approximation costs:

1. I compare my monthly returns with the ones the authors publish for
   Jan 2024 to Jan 2025 (table in Q24 of the paper's FAQ).
2. Over the last ~60 days, with 5-minute bars, I compare hourly checks with
   checks every 30 minutes.

Periods I report, decided now:
- Jan 2024 to Apr 2024: inside the paper's sample.
- May 2024 to today: post-publication (the paper came out in May 2024).
Benchmark: buying and holding SPY on the same days. Sharpe with a zero risk-free rate.
Single cost sensitivity: 1 bp per side on notional, roughly the cost of a retail
CFD on the S&P 500.

Usage:  python btm.py
"""
from __future__ import annotations

import math
import warnings
from dataclasses import dataclass
from pathlib import Path

import numpy as np
import pandas as pd

warnings.filterwarnings("ignore")

DATA = Path(__file__).resolve().parent / "data"
TZ = "America/New_York"


@dataclass(frozen=True)
class Params:
    lookback: int = 14
    vol_mult: float = 1.0
    target_vol: float = 0.02
    max_lev: float = 4.0
    cost_per_share: float = 0.0045
    cost_bps: float = 0.0  # extra cost in bp of notional, per side
    aum0: float = 100_000.0


# ---------------------------------------------------------------- data

def load_intraday(interval: str = "1h", period: str = "730d", refresh: bool = False) -> pd.DataFrame:
    """SPY bars in regular hours, New York time. Cached in data/."""
    DATA.mkdir(exist_ok=True)
    f = DATA / f"spy_{interval}.csv"
    if f.exists() and not refresh:
        df = pd.read_csv(f, index_col=0)
        df.index = pd.to_datetime(df.index, utc=True).tz_convert(TZ)
        return df
    import yfinance as yf
    df = yf.download("SPY", period=period, interval=interval, progress=False,
                     auto_adjust=False, prepost=False, multi_level_index=False)
    df.index = df.index.tz_convert(TZ)
    df = df[["Open", "High", "Low", "Close", "Volume"]]
    df.to_csv(f)
    return df


def load_daily(start: str, refresh: bool = False) -> pd.Series:
    DATA.mkdir(exist_ok=True)
    f = DATA / "spy_daily.csv"
    if f.exists() and not refresh:
        s = pd.read_csv(f, index_col=0, parse_dates=True).iloc[:, 0]
        return s
    import yfinance as yf
    df = yf.download("SPY", start=start, interval="1d", progress=False,
                     auto_adjust=True, multi_level_index=False)
    s = df["Close"].rename("close")
    s.to_csv(f)
    return s


def to_30min(df5: pd.DataFrame) -> pd.DataFrame:
    """Aggregates 5-minute bars into 30-minute bars starting at 9:30, 10:00..."""
    out = []
    for _, g in df5.groupby(df5.index.date):
        r = g.resample("30min", origin="start").agg(
            {"Open": "first", "High": "max", "Low": "min", "Close": "last", "Volume": "sum"})
        out.append(r.dropna())
    return pd.concat(out)


# ---------------------------------------------------------------- core

def split_days(bars: pd.DataFrame) -> list[pd.DataFrame]:
    return [g for _, g in bars.groupby(bars.index.date)]


def day_moves(day: pd.DataFrame) -> pd.Series:
    """|Close(bar) / Open(9:30) - 1| indexed by the bar's start time."""
    o = day["Open"].iloc[0]
    m = (day["Close"] / o - 1).abs()
    m.index = day.index.strftime("%H:%M")
    return m


def noise_sigma(prev_days: list[pd.DataFrame], lookback: int) -> pd.Series:
    """Mean move by time of day over the previous `lookback` days."""
    moves = pd.concat([day_moves(d) for d in prev_days[-lookback:]], axis=1)
    return moves.mean(axis=1, skipna=True)


def simulate_day(day: pd.DataFrame, prev_close: float, sigma: pd.Series,
                 shares: int, p: Params) -> tuple[float, int]:
    """One day's PnL in dollars and number of trades (fills).

    The check happens at the close of every bar except the last; the last one is
    used to close at the market close. Trades execute at the price of the check.
    """
    o = day["Open"].iloc[0]
    hi_ref, lo_ref = max(o, prev_close), min(o, prev_close)
    keys = day.index.strftime("%H:%M")
    closes = day["Close"].to_numpy()
    tp = ((day["High"] + day["Low"] + day["Close"]) / 3).to_numpy()
    vol = day["Volume"].to_numpy().astype(float)
    vwap = np.cumsum(tp * vol) / np.maximum(np.cumsum(vol), 1.0)
    if "VWAP" in day:  # session VWAP computed from finer bars (run_1min.py)
        vwap = day["VWAP"].to_numpy()

    pos, entry, pnl, fills = 0, 0.0, 0.0, 0

    def fill(price: float) -> float:
        return shares * (p.cost_per_share + price * p.cost_bps / 1e4)

    n = len(day)
    for i in range(n - 1):
        s = sigma.get(keys[i], np.nan) * p.vol_mult
        if not np.isfinite(s):
            continue
        ub, lb, px = hi_ref * (1 + s), lo_ref * (1 - s), closes[i]
        stopped = 0
        if pos == 1 and px < max(ub, vwap[i]):
            pnl += shares * (px - entry) - fill(px); fills += 1; pos, stopped = 0, 1
        elif pos == -1 and px > min(lb, vwap[i]):
            pnl += shares * (entry - px) - fill(px); fills += 1; pos, stopped = 0, -1
        if pos == 0:
            # After a stop, don't reopen in the same direction at the same check.
            if px > ub and stopped != 1:
                pos, entry = 1, px
            elif px < lb and stopped != -1:
                pos, entry = -1, px
            if pos != 0:
                pnl -= fill(px); fills += 1
    if pos != 0:
        px = closes[-1]
        pnl += shares * pos * (px - entry) - fill(px); fills += 1
    return pnl, fills


def backtest(bars: pd.DataFrame, daily: pd.Series, p: Params = Params()) -> pd.DataFrame:
    """One row per trading day: return, exposure and trades."""
    days = split_days(bars)
    dret = daily.pct_change()
    aum = p.aum0
    rows = []
    for k in range(p.lookback, len(days)):
        day = days[k]
        date = pd.Timestamp(day.index[0].date())
        past = dret[dret.index < date].dropna().iloc[-p.lookback:]
        if len(past) < p.lookback:
            continue
        sig_spy = past.std(ddof=1)
        lev = min(p.max_lev, p.target_vol / sig_spy)
        o = day["Open"].iloc[0]
        shares = int(math.floor(aum * lev / o))
        sigma = noise_sigma(days[:k], p.lookback)
        prev_close = days[k - 1]["Close"].iloc[-1]
        pnl, fills = simulate_day(day, prev_close, sigma, shares, p)
        rows.append({"date": date, "ret": pnl / aum, "lev": lev, "fills": fills})
        aum += pnl
    return pd.DataFrame(rows).set_index("date")


# ---------------------------------------------------------------- metrics

def stats(r: pd.Series) -> dict:
    r = r.dropna()
    eq = (1 + r).cumprod()
    yrs = len(r) / 252
    cagr = eq.iloc[-1] ** (1 / yrs) - 1
    vol = r.std() * math.sqrt(252)
    sharpe = r.mean() / r.std() * math.sqrt(252) if r.std() > 0 else np.nan
    mdd = (eq / eq.cummax() - 1).min()
    return {"days": len(r), "total": eq.iloc[-1] - 1, "cagr": cagr, "vol": vol,
            "sharpe": sharpe, "mdd": mdd, "hit": (r[r != 0] > 0).mean()}


def sharpe_ci(r: pd.Series, block: int = 21, n: int = 5000, seed: int = 0) -> tuple[float, float]:
    """90% CI of the annualised Sharpe from a block bootstrap."""
    x = r.dropna().to_numpy()
    rng = np.random.default_rng(seed)
    nb = math.ceil(len(x) / block)
    out = []
    for _ in range(n):
        starts = rng.integers(0, len(x) - block + 1, nb)
        s = np.concatenate([x[a:a + block] for a in starts])[:len(x)]
        out.append(s.mean() / s.std() * math.sqrt(252))
    return float(np.percentile(out, 5)), float(np.percentile(out, 95))


# Monthly returns published by the authors (FAQ Q24 of the Feb 2026 version
# on concretumgroup.com, which runs to Aug 2025), in %.
PAPER_MONTHLY = {
    "2024-01": 8.8, "2024-02": -1.5, "2024-03": -0.4, "2024-04": 5.8,
    "2024-05": -4.3, "2024-06": 1.6, "2024-07": 8.2, "2024-08": -2.8,
    "2024-09": 4.1, "2024-10": 6.7, "2024-11": -2.6, "2024-12": 5.7,
    "2025-01": -1.2, "2025-02": 7.6, "2025-03": -0.2, "2025-04": 4.3,
    "2025-05": -2.1, "2025-06": -2.0, "2025-07": -2.0, "2025-08": -2.9,
}


def monthly(r: pd.Series) -> pd.Series:
    m = (1 + r).groupby(r.index.to_period("M")).prod() - 1
    m.index = m.index.astype(str)
    return m * 100


def fmt(d: dict) -> str:
    return (f"days {d['days']:4d} | total {d['total']:+7.1%} | annual {d['cagr']:+6.1%} | "
            f"vol {d['vol']:5.1%} | Sharpe {d['sharpe']:5.2f} | MDD {d['mdd']:6.1%} | "
            f"hit rate {d['hit']:.0%}")


def main() -> None:
    h = load_intraday("1h", "730d")
    today = pd.Timestamp.now(tz=TZ).date()
    h = h[h.index.date < today]
    daily = load_daily("2023-10-01")
    daily = daily[daily.index.date < today]

    res = backtest(h, daily)
    res_cost = backtest(h, daily, Params(cost_bps=1.0))
    spy = daily.pct_change().reindex(res.index)
    res.to_csv(DATA / "btm_daily_1h.csv")

    print("\n== Validation: my monthly returns against the published ones (Jan 2024 to Aug 2025) ==")
    mine = monthly(res["ret"])
    comp = pd.DataFrame({"mine": mine, "paper": pd.Series(PAPER_MONTHLY)}).dropna()
    print(comp.round(1).to_string())
    gap = comp.paper.mean() - comp.mine.mean()
    print(f"correlation {comp.corr().iloc[0, 1]:.2f} | my mean {comp.mine.mean():+.2f}% | "
          f"paper mean {comp.paper.mean():+.2f}% a month | gap {gap:+.2f} pp/month")
    for a, b in [("2024-05", "2024-12"), ("2025-01", "2025-08")]:
        c = comp.loc[a:b] / 100
        print(f"  {a} to {b}: authors {(1 + c.paper).prod() - 1:+.1%} | mine {(1 + c.mine).prod() - 1:+.1%}")

    periods = {
        "Inside the paper's sample (Jan–Apr 2024)": ("2024-01-01", "2024-04-30"),
        "Post-publication (May 2024 – today)": ("2024-05-01", str(today)),
        "  of which May–Dec 2024": ("2024-05-01", "2024-12-31"),
        "  of which 2025": ("2025-01-01", "2025-12-31"),
        "  of which 2026 to today": ("2026-01-01", str(today)),
    }
    for name, (a, b) in periods.items():
        sl = slice(a, b)
        print(f"\n== {name} ==")
        print("strategy        ", fmt(stats(res["ret"][sl])))
        print("with 1 bp/side  ", fmt(stats(res_cost["ret"][sl])))
        print("SPY buy & hold  ", fmt(stats(spy[sl])))
        if "today" in name and not name.startswith("  "):
            lo, hi = sharpe_ci(res["ret"][sl])
            lo2, hi2 = sharpe_ci(res_cost["ret"][sl])
            print(f"90% CI Sharpe: {lo:.2f} to {hi:.2f} | with 1 bp/side: {lo2:.2f} to {hi2:.2f}")
            print(f"average leverage {res['lev'][sl].mean():.2f}x | "
                  f"trades/day {res['fills'][sl].mean() / 2:.2f} | "
                  f"daily corr. with SPY {res['ret'][sl].corr(spy[sl]):.2f}")

    print("\n== Robustness: hourly checks against every 30 min (5-minute bars, ~60 days) ==")
    m5 = load_intraday("5m", "60d")
    m5 = m5[m5.index.date < today]
    m30 = to_30min(m5)
    h60 = h[h.index >= m30.index[0]]
    r30 = backtest(m30, daily)["ret"]
    r60 = backtest(h60, daily)["ret"]
    both = pd.DataFrame({"every_30": r30, "every_60": r60}).dropna()
    print(f"days {len(both)} | daily corr. {both.corr().iloc[0, 1]:.2f} | "
          f"total 30 min {(1 + both.every_30).prod() - 1:+.1%} | "
          f"total 60 min {(1 + both.every_60).prod() - 1:+.1%}")


if __name__ == "__main__":
    main()
