# Five-Factor Equity Screener

Systematic equity screener applying a classical **five-factor value/quality framework**
(P/E, ROE, Debt/Equity, PEG, FCF yield) over a combined US + Europe universe
(~2,150 primary listings above $1B after cleaning),
using the official TradingView data endpoint.

Built as part of a broader equity research lab focused on disciplined,
process-driven long-term investing.

## Methodology

**Factor set** (Damodaran/Piotroski-inspired):

| Factor | Rationale | Direction |
|---|---|---|
| P/E (TTM) | Valuation | Lower is better |
| ROE (FQ) | Quality / capital efficiency | Higher is better |
| Debt/Equity | Balance sheet strength | Lower is better |
| PEG (trailing: P/E ÷ TTM EPS growth) | Growth relative to price; neutral when implied growth > 100% | Lower is better |
| FCF yield (FCF TTM ÷ market cap) | Cash generation relative to price | Higher is better; FCF > 0 required |

**Pipeline**:

1. **Universe fetch** — pulls all tickers with market cap > $1B listed on the
   domestic exchanges of the US, Germany, France, Italy, Spain, Netherlands,
   Switzerland and the UK (paginated, see *Universe coverage*).
2. **Cleaning** — removes financials (D/E and FCF not comparable),
   preferred shares, listed debt, non-common stock, SIX temporary trading
   lines, and duplicated share classes (one line per company, the most traded).
3. **Data validation** — cross-checks fields that must agree by
   construction and flags rows that don't (see below).
4. **Hard filters** — every ticker must clear all five thresholds
   (configurable in `src/config.py`).
5. **Quarantine** — survivors with a data error are held back and reported,
   not ranked.
6. **Composite score** — winsorise each factor at the 5th/95th percentiles,
   z-score it across the clean survivors, invert lower-is-better factors, and
   combine with weights `[PE: 20%, ROE: 30%, D/E: 15%, PEG: 20%,
   FCF yield: 15%]`. Higher = better. See *Scoring model* below.
7. **Ranked output** — top-N to console and Telegram, full ranking and
   quarantine to Excel.
8. **Weekly history** — each scheduled run is appended to
   `data/screener_history.csv`; streaks and score trends are computed from it.

## Scoring model

For each factor *f* and survivor *i*:

```
x'  = clip(x, P5, P95)              winsorise across survivors
z   = (x' - mean(x')) / std(x')     population std (ddof=0)
z   = -z  for P/E, D/E, PEG         higher = better for every factor
score = Σ w_f · z_f
```

Three choices, made in v0.7 after measuring the alternatives on the
2026-10-06 universe and the 8 weekly snapshots since 2026-08-02 (the first
two before the coverage fix below, the PEG one after it):

- **FCF yield instead of absolute FCF.** Absolute FCF behaved as a size
  factor and mixed currencies: Alphabet ($53B, 1.3% yield) scored z = +4.2
  while CF Industries (10.9% yield) scored below average. The yield is
  currency-free and adds information independent of P/E (correlation
  between earnings yield and FCF yield among survivors: −0.01).
- **Winsorisation at 5/95** (CFA Level I, winsorised mean). Without it, one
  extreme value stretches the scale for everyone: GTT's ROE z fell from 4.3
  to 2.5 between August and October with its ROE unchanged, because WDC
  (131% ROE) entered the screen. Weekly top-10 turnover over the 8 snapshots
  fell from 3.0 to 2.6 names (2.4 with all three changes).
- **Neutral PEG on base effects.** TradingView's PEG is trailing (P/E ÷ TTM
  YoY EPS growth, verified on 968 tickers), so growth off a depressed base
  (MU 864%, VLO 909% implied) makes it collapse towards zero. Its raw value
  was the largest single contributor at the top of the ranking. When the
  implied growth exceeds 100%, the PEG counts as not measurable: it is left
  out of the PEG mean and std and scores z = 0. The `PEG_BASE_EFFECT` warning
  stays on the row.
  *Rejected first attempt:* a floor at P/E ÷ 100. On the truncated universe
  it looked fine. On the full one, the floored PEG of the 34 affected names
  had a 0.99 z-correlation with their P/E, so it credited a low P/E twice.

Result: on the pre-fix universe, these changes had a 0.91 rank correlation
with the old model. GOOGL fell from 3rd to 14th, its FCF yield being 1.3%.
MU's lead shrank from 2.02 to 1.18 and now rests on ROE, not on PEG or size.

These choices rest on comparability and robustness, not on performance:
with 8 weeks of live history, no backtest was possible when they were made.
The point-in-time backtest (see *Backtest*) tested the model afterwards.

## Universe coverage

Until v0.7 the fetch asked TradingView for the top 2,000 rows per market by
market cap, with no exchange filter. OTC listings (2,318 foreign ADRs) filled
the US query and foreign companies cross-listed on German venues filled the
German one. The primary-listing filter then removed them, *after* the slots
were spent:

| | Before | After |
|---|---|---|
| Rows matching (US / Germany) | 5,289 / 22,098, only 2,000 returned | 2,860 / 2,859, all returned |
| Smallest US / German company screened | $12.5B / $124B | $1.0B / $1.0B |
| Clean universe | 956 | 2,152 |
| Ranked survivors | 53 | 126 |

The query now asks only for each market's domestic exchanges and paginates
until it reaches TradingView's reported count. An incomplete or failed fetch
is written to the weekly log.

With the floor really at $1B, the top of the ranking is mostly deep-value
small and mid caps (2026-10-07: TDC, BLBD, NUTX, VH2, CENX, CF, MU, ACAD,
HOC, PEGA), several of them cyclical or special situations. The screen was
always meant to work this way; the truncation had hidden it.

Of the 2,152 tickers, 1,237 lack a five-factor field. Most of these gaps
are economic, and the funnel reports them as such: 486 have falling EPS (a
trailing PEG does not exist), 448 are loss-making (P/E undefined), and 303
are true data gaps. Only one company with a genuinely missing PEG would
have passed the other four thresholds.

To see where any ticker drops out:

```
python -m src.diagnose MU VRT PLTR CAT
```

```
 name       ticker     stage    detail
   MU    NASDAQ:MU    ranked    #7 of 126, score +0.85 (warning: PEG_BASE_EFFECT)
  VRT     NYSE:VRT threshold    P/E < 20 (is 57.28)
 PLTR  NASDAQ:PLTR threshold    P/E < 20 (is 163.7)
  CAT     NYSE:CAT threshold    P/E < 20 (is 37.14); D/E < 1 (is 2.328); 0 < PEG < 1.5 (is 2.003)
```

VRT, PLTR and CAT were never a coverage problem: a value screen with P/E
< 20 excludes them by design.

## Data validation

A bad input does more damage than one false positive: the composite score
z-scores every factor across survivors, so a single wrong P/E shifts the mean
and standard deviation every other ticker is scored against. Suspect rows are
therefore removed *before* scoring and listed in a `quarantine` sheet.

| Flag | Severity | Check |
|---|---|---|
| `OOB_<factor>` | error | Value outside `SANITY_BOUNDS` |
| `PE_VS_EARNINGS` | error | Market cap / P/E must reproduce TTM net income (ratio outside 0.5–2.0) |
| `ROE_SIGN` | error | Reported ROE and TTM net income have opposite signs |
| `ROE_VS_EQUITY` | warning | Reported ROE vs net income / closing equity, gross gaps only |
| `PEG_BASE_EFFECT` | warning | P/E ÷ PEG implies > 100% EPS growth: PEG measured off a depressed base (scored as neutral) |

Errors are quarantined; warnings stay in the ranking, marked `*` in console
and Telegram and listed in the `data_warnings` column.

Thresholds were calibrated on the cleaned universe of 2026-10-06 (965
tickers, before the coverage fix): for clean data, market cap / P/E ÷ net income has a median of
0.99 and 98% of tickers fall within 0.82–1.06.

Cases that motivated it:

- **SIX:LISPE (Lindt, temporary line)** showed a P/E of 2.4x. TradingView
  paired the registered share's EPS (3,179 CHF) with a participation
  certificate's price; the regular LISP line shows 23.6x. The check flags
  it at 10.0x, and temporary lines are now also removed during cleaning.
- **LSE:HOC (Hochschild)** looked inconsistent: ROE 37.4% vs 26.9% from net
  income / total equity. Verified against the reported statements, 37.4% is
  correct (net income / *average* equity, the CFA definition; equity grew 47%
  year on year, and TradingView's total equity includes minorities). This is
  why the ROE check is a warning with a wide band, not an error.

## Weekly history and persistence

A z-score ranks a stock against *this week's* survivors, so a falling score
can mean the stock got worse or that its peers changed. `src/history.py`
stores one snapshot per week (`data/screener_history.csv`, append-only) and
computes, for every ranked ticker:

| Metric | Meaning |
|---|---|
| `streak`, `streak_since` | Consecutive weekly runs in the top 10, ending now |
| `score_delta`, `score_slope` | Score change over the last 4 runs, and its OLS slope per week |
| `d_pe` … `d_fcf` | Score change attributed to each factor: `w_f · Δz_f` |
| `d_own`, `d_peers` | Change from the stock's own data (peer mean and std held at the start of the window) vs from the peer distribution |
| `price_chg_pct`, `eps_chg_pct` | Price vs implied EPS change (EPS = price ÷ P/E) |

Weeks run Sunday to Saturday; a Monday-morning retry counts for the Sunday
it replaces, and a week with no run neither extends nor breaks a streak.
Each row carries `model_version`. Scores from different models are on
different scales, so the trend window only uses snapshots from the current
model (it restarts at 1 after a model change); streaks span models and are
flagged `streak_mixed_models`. The own-vs-peers split refits the start
week's standardisation (winsorisation bounds, mean, std) from the stored
survivors, using that week's model.

Example (GTT, 2026-08-02 → 2026-10-04, 8 runs, pre-0.7 model): score
1.14 → 0.48. Its own data explains −0.09 (price +7.7% with TTM EPS
unchanged, no new report). The other −0.57 comes from peers, almost entirely
through ROE: GTT's ROE stayed at 79.7%, but higher-ROE entrants (WDC at
131%) widened the ROE dispersion and cut its z-score from 4.3 to 2.5. This
is what motivated winsorisation.

```powershell
python -m src.history backfill   # once: load pre-v0.7 Excel outputs
python -m src.history report     # persistence table for the latest week
```

Only `run_weekly.py` writes to the history. Manual `run_screener.py` runs
don't, so a mid-week test can't replace the Sunday snapshot.

## Backtest (point-in-time, US)

`run_backtest.py` runs the live screener at every month-end from February
2012 to September 2026, on fundamentals as they were known at the time.
Thresholds, validation, quarantine and scoring are the live ones, unchanged.

**Data**

- **Fundamentals** come from SEC EDGAR XBRL company facts
  (`companyfacts.zip`).
  - Each value is the one first reported, dated by the day the SEC
    received the filing. Restatements are ignored.
  - TTM figures are built from year-to-date ones: YTD + last fiscal year −
    YTD a year earlier.
  - Per-share data and share counts are put on today's share basis using
    yfinance split dates.
- **Prices** come from yfinance. The month-end close drives P/E and market
  cap. The adjusted close (dividends reinvested) drives returns.
- **Universe**: US companies listed today on NYSE, Nasdaq or AMEX, cleaned
  exactly like the live universe. At each month-end, only those above $1B
  market cap count: about 600 in 2012 and about 1,450 in 2026.
- **Factors** are rebuilt with TradingView's definitions. Debt includes
  operating leases, as TradingView's does: with them, the median ratio to
  TradingView is 1.00; without them, 0.76.

**Calibration against TradingView (2026-10-07)**: the reconstructed factors
for today, compared with TradingView's.

| Factor | Rank correlation | Same side of the threshold |
|---|---|---|
| Market cap | 0.99 | 99% |
| P/E | 0.98 | 98% |
| ROE | 0.96 | 98% |
| D/E | 0.88 | 95% |
| PEG | 0.97 | 98% |
| FCF | 0.97 | 98% |

Running the whole screener on both data sets:

- 82% of TradingView's US survivors also survive on the reconstructed data.
- Their scores have a 0.96 rank correlation, and 7 of the top 10 are the
  same.
- D/E disagreements sit almost entirely in companies that fail another
  threshold anyway: 1 of the 167 companies that pass the other four.
- The main systematic difference is timing. XBRL data arrive with the 10-Q
  or 10-K, days to weeks after the earnings release that TradingView uses.
  For example, MU's August quarter is in TradingView but not yet in EDGAR.
  The backtest can therefore act late, but never early.

**Results**: February 2012 to September 2026, 176 months, monthly
rebalance, equal weights, net of 10 bp per side.

| Portfolio | CAGR | Volatility | Sharpe (rf = 0) | Max drawdown | Excess vs universe | t-stat |
|---|---|---|---|---|---|---|
| Top 10 by score | 15.7% | 21.5% | 0.79 | −35% | +3.2% / yr | 0.99 |
| All ranked survivors (~74) | 12.5% | 17.7% | 0.76 | −30% | −0.4% / yr | −0.22 |
| Universe, equal-weighted (~970) | 12.9% | 17.2% | 0.80 | −29% | — | — |
| SPY (reference) | 14.7% | 13.9% | 1.06 | −24% | +1.1% / yr | 0.58 |

The top 10's excess return over the universe changes sign by sub-period:
+5.2% a year in 2012–16, −1.8% in 2017–21, and +6.4% from December 2021 to
September 2026. Its monthly one-way turnover is 27%.

Rank IC of each factor with the next month's and next 12 months' return
(Newey-West t in brackets):

| Factor | Whole universe, 1m | Whole universe, 12m | Among survivors (z-score), 1m |
|---|---|---|---|
| P/E (as earnings yield) | 0.009 (0.9) | 0.021 (0.9) | 0.023 (2.0) |
| ROE | 0.015 (2.2) | 0.042 (2.7) | −0.007 (−0.6) |
| Low D/E | −0.013 (−1.9) | −0.042 (−2.1) | −0.004 (−0.4) |
| Low PEG | 0.002 (0.3) | −0.005 (−0.2) | 0.007 (0.7) |
| FCF yield | 0.019 (2.3) | 0.046 (1.8) | 0.006 (0.5) |
| Composite score | | | 0.015 (1.5) |

What this says:

- **The filters alone did not add value.** Passing the five thresholds did
  not beat the universe the survivors came from: −0.4% a year.
- **The top 10 did better, but not reliably.** It beat the universe by 3.2%
  a year, but with a 13% tracking error that is only one standard error. It
  cannot be told apart from luck, and it was negative in 2017–21. The
  score's IC among survivors (0.015, t = 1.5) tells the same story.
- **Two factors carried information across the universe: ROE and FCF
  yield.** P/E carried little and PEG none. Low debt went the wrong way:
  more leveraged companies did better over 2012–26.
- **Inside the screen, only P/E's z-score had a signal, and a marginal one.**
  A linear IC across all survivors says little about the top 10, though:
  see *Weights* below. The tables hold 33 ICs, so one or two results with
  |t| ≈ 2 are expected by chance.

**Weights** (`python -m src.backtest.weights`). The survivors and their
z-scores do not depend on the weights, so any weighting can be evaluated by
re-ranking the same survivors each month. Gross returns of the top 10:

| Weights | Rank corr. with current score | Top 10 names in common | Excess vs universe | vs current (t) | Smallest detectable difference |
|---|---|---|---|---|---|
| Current (20/30/15/20/15) | 1.00 | 10 | +3.7% / yr | — | — |
| Equal (20 each) | 0.97 | 8.0 | +2.5% / yr | −1.3% (−0.8) | 3.1% / yr |
| Without ROE (pro rata) | 0.82 | 5.9 | −0.3% / yr | −4.1% (−1.7) | 4.8% / yr |

Three findings argue against changing the weights:

- **The backtest cannot tell plausible weightings apart.** Two top-10
  portfolios this close would need to differ by 3–5% a year before a t of 2
  could separate them.
- **Weights chosen on past returns did not persist.** Out of 2,000 random
  weightings, those with the best top 10 in 2012–18 did worse than the
  median in 2019–26: +1.8% a year against +5.2%. The rank correlation
  between the two halves is −0.29. Re-fitting the weights on this sample
  would most likely have made the screen worse.
- **Dropping ROE, the change the IC table suggests, did not help.** Without
  ROE, the monthly top 10 lost 4.1% a year against the current weights, with
  the same sign in all three sub-periods. The names it picked had a lower
  ROE (median 26% against 43%) and a higher average 12-month return (15.7%
  against 13.7%), so the evidence conflicts across horizons as well.

The current weights were set before this data existed. They rank in the
94th percentile of the 2,000 random weightings, which is luck as much as
design. They stay unchanged.

**Quality factor** (`python -m src.backtest.quality`). Does buying quality
pay, independently of this screener? Two standard definitions were fixed
before looking at the results:

- **MSCI-style**: z-scores of high ROE, low debt/equity and low variability
  of EPS growth over 5 years.
- **Gross profitability**: gross profit / total assets (Novy-Marx, 2013).

The test is the top quintile of each, equal-weighted, on the same universe,
months and costs as above.

| Signal | CAGR | Volatility | Sharpe | Max drawdown | Excess vs universe (t) | By sub-period |
|---|---|---|---|---|---|---|
| MSCI-style (~140 names) | 13.5% | 15.8% | 0.89 | −27% | +0.3% / yr (0.2) | −3.2 / +1.9 / +2.2 |
| Gross profitability (~136) | 13.6% | 17.5% | 0.82 | −32% | +0.6% / yr (0.3) | −0.4 / +6.0 / −3.8 |
| Universe, equal-weighted | 12.9% | 17.2% | 0.80 | −29% | — | — |

SPY returned 14.7% a year over the same months. Neither definition beat the
universe in a way distinguishable from luck, and both lagged SPY. The
MSCI-style portfolio was less volatile, with a smaller drawdown, which is
the defensive side of quality. Its 0.89 Sharpe against 0.80 was not tested
for significance.

Two more findings:

- Among the components, only ROE has a rank IC with t > 2 (0.015 to 0.042),
  as in the screener's own IC table. Low debt/equity again went the wrong
  way, and it drags the MSCI-style composite.
- Financials are excluded, as in the rest of this backtest. The published
  quality premium (e.g. AQR's quality-minus-junk) is long-short and comes
  largely from shorting junk, which a long-only top quintile does not
  capture.

**Limitations**

- **Survivorship.** Only companies listed today have prices. Of the
  companies whose 2012 filings showed a public float above $1B, 58% are
  still listed today; the share is 78% for 2020 and 90% for 2024. The rest
  were acquired, went private or failed. Screen and universe share this
  bias, so it partly cancels in the excess return, but its sign cannot be
  determined from this data. The sub-period from December 2021 is the least
  affected.
- **US only.** Europe has no free point-in-time source with comparable
  coverage.
- **Simplifications.** Rebalancing is monthly, not weekly. There are no
  taxes, and costs are assumed at 10 bp per side.
- **Data construction.** Restatements are ignored (first-reported values
  only), and debt has to be rebuilt from many XBRL tags.

```powershell
pip install -r requirements-backtest.txt
python run_backtest.py --calibrate   # factors vs TradingView today
python run_backtest.py               # full run, about 20 min the first time
```

The SEC asks for a User-Agent with a contact email, so set `SEC_USER_AGENT`
in `.env`. Downloads (1.4 GB from the SEC, prices from yfinance) are cached
in `data/sec/` and `data/backtest/`; `--refresh` rebuilds them. Results go
to `output/backtest_YYYYMMDD_HHMM.xlsx`.

## Known limitations

- Validation catches *inconsistencies*. An error that is consistent across
  every field (e.g. all fundamentals a year stale) passes.
- The ROE check cannot reproduce average equity (TradingView exposes
  closing equity only), so it only flags gross gaps.
- The screen is not cycle-aware. Peak-cycle ROE and P/E (MU, WDC, CF in
  2026) score well; telling peak earnings from durable earnings is left to
  the analyst.
- With FCF yield, three of the five factors measure price (P/E, PEG, FCF
  yield; 55% of the weight). The weights are unchanged: the backtest cannot
  separate plausible alternatives, and weights chosen on past returns did
  not persist (see *Weights* under *Backtest*).
- Validation against forward returns is US-only and survivorship-biased
  (see *Backtest*).
- History before v0.7 only holds ranked survivors, rebuilt from the Excel
  outputs. Tickers dropped by the old sanity bounds left no trace, so
  there is no way to tell why a name (e.g. MU before 2026-10-04) was absent.
  It was also scored on a truncated universe (large caps only), so pre-0.7
  ranks and streaks are not comparable with v0.7 ones.
- PEG is trailing, not based on forecast growth (Lynch's original), because
  TradingView exposes no consensus growth for the whole universe.

**Design decisions worth noting**:

- Financials excluded by design. Not a bug — bank FCF and leverage
  metrics require a separate framework (P/TBV, CET1, ROTE).
- Micro-caps excluded ($1B floor). Below that, data quality on
  TradingView's fundamentals degrades noticeably.
- The five-factor filter is *deliberately restrictive*: about 130 survivors
  from ~2,150 tickers with default thresholds (126 on 2026-10-07).

## Repository layout

```
equity-screener/
├── src/
│   ├── config.py          # thresholds, weights, universe settings
│   ├── universe.py        # TradingView fetch + cleaning
│   ├── validation.py      # cross-field data checks (quarantine flags)
│   ├── screener.py        # hard filters + quarantine + composite scoring
│   ├── report.py          # Excel export + console summary
│   ├── history.py         # weekly snapshots, streaks, score decomposition
│   ├── diagnose.py        # where a given ticker drops out, or its rank
│   ├── telegram_alerts.py # weekly Telegram message
│   └── backtest/          # point-in-time backtest (US)
│       ├── sec.py         # SEC ticker map + companyfacts.zip extraction
│       ├── universe.py    # today's US listings, cleaned, mapped to CIKs
│       ├── prices.py      # yfinance prices, split factors
│       ├── fundamentals.py# first-reported facts -> TTM snapshots, as-of lookup
│       ├── panel.py       # monthly cross-sections in TradingView's columns
│       ├── analysis.py    # monthly screen, ICs, portfolios, survivorship
│       ├── weights.py     # are the score weights worth changing?
│       └── quality.py     # does a standard quality factor pay?
├── tests/
│   ├── test_screener.py   # filters, z-score, winsorisation, FCF yield, PEG
│   ├── test_validation.py # data checks and quarantine, on real 2026 cases
│   ├── test_universe.py   # cleaning rules, pagination (no network)
│   ├── test_history.py    # week convention, streaks, decomposition
│   ├── test_diagnose.py   # stage attribution (no network)
│   ├── test_backtest_fundamentals.py  # TTM, point-in-time, splits, debt
│   ├── test_backtest_analysis.py      # ICs, Newey-West, portfolios, weights
│   └── test_backtest_quality.py       # quality signals, point in time
├── data/
│   ├── screener_history.csv  # weekly snapshots (gitignored, local state)
│   ├── sec/               # SEC downloads (gitignored, ~1.4 GB)
│   └── backtest/          # backtest caches (gitignored)
├── output/                # timestamped Excel exports (gitignored)
├── run_screener.py        # main entrypoint
├── run_backtest.py        # point-in-time backtest
├── requirements.txt
├── requirements-backtest.txt
└── README.md
```

## Setup

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
```

## Usage

```powershell
python run_screener.py
```

Console prints the top-10 with per-factor values and composite score, plus
any quarantined tickers. Full ranking is written to
`output/five_factor_screener_YYYYMMDD_HHMM.xlsx` with three sheets: `top_n`,
`full_ranking` and `quarantine` (flag codes plus the check ratios behind them).

## Research notebook

For a fully visual walkthrough of methodology and results, open
`five_factor_screener.ipynb`:

```powershell
jupyter notebook five_factor_screener.ipynb
```

The notebook runs a live fetch, visualizes the universe → funnel → top-10
end to end, and includes a stock-pitch template to fill in after the
evidence is reviewed.

## Configuration

All tunable parameters live in `src/config.py`. Three reference
threshold profiles are documented in the file header:

- **Value classic** (Graham deep-value): P/E<15, ROE>15%, D/E<0.5, PEG<1
- **Quality+Value** (Buffett-style, default): P/E<20, ROE>12%, D/E<1, PEG<1.5
- **GARP** (Lynch/Fisher): P/E<25, ROE>15%, D/E<1, PEG<1.2

## Tests

```powershell
pip install pytest
python -m pytest tests/ -v
```

## Changelog

**Backtest (2026-10-07)**
- Point-in-time backtest of the live screener on US data since 2012
  (`run_backtest.py`, `src/backtest/`). Fundamentals come from SEC XBRL,
  first-reported and dated by filing. The reconstructed factors were
  calibrated against TradingView. See *Backtest* for results and limits.
- The screener itself is unchanged.
- Weight study (`python -m src.backtest.weights`): the weights stay unchanged.
- Quality factor study (`python -m src.backtest.quality`): adds gross profit, revenue, cost of revenue and total assets to the SEC extraction, dated separately so the screener backtest is unchanged.
- Tests: 90.

**v0.7 (2026-10)**
- Data validation and quarantine (`src/validation.py`). Sanity bounds now
  flag rows instead of silently dropping them.
- Cleaning fixes: SIX temporary lines and exchange-listed debt removed; one
  line per company by liquidity. The non-equity keyword filter used plain
  substrings, so `Unit`/`Right` removed UnitedHealth, UPS, United Airlines,
  Unity, Curtiss-Wright, BrightSpring and Rightmove from the universe.
- PEG = 0.00 is treated as missing data, explicitly.
- Weekly history (`src/history.py`): streaks, score trend, and own-vs-peers
  decomposition of score changes; backfilled from the 2026-08-05 run onwards.
  Shown in Telegram (`Wk` column, "Fading" list) and in an Excel `persistence` sheet.
- Scoring model: FCF yield instead of absolute FCF, winsorisation at 5/95,
  neutral PEG on base effects (see *Scoring model* for the evidence and the
  rejected PEG floor).
- Universe coverage: domestic-exchange query with pagination. The 2,000-row
  limit had cut the US universe at $12.5B and Germany's at $124B.
  Clean universe 956 → 2,152, ranked 53 → 126.
- Funnel reports why data is missing (loss-making / EPS falling / data gap);
  `python -m src.diagnose <tickers>` explains any ticker's outcome.
- Tests: 54.

## References

- Damodaran, A. *Investment Valuation* (3rd ed.)
- Piotroski, J. (2000) *Value Investing: The Use of Historical Financial
  Statement Information to Separate Winners from Losers*
- Greenblatt, J. *The Little Book That Still Beats the Market*

## Disclaimer

Educational / research use only. Not investment advice. Screener output
is a starting point for further fundamental due diligence, not a
buy/sell signal.
