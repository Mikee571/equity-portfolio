# JPMorgan: a residual income model

October 2026. The JPM pitch started as a quick check of what 3x tangible book implies. After building full models for Micron and GTT, I wanted the same depth here. A bank needs a different tool, though: deposits are raw material rather than financing, so free cash flow means very little. The standard approach is residual income. Equity value is today's tangible common equity plus the present value of whatever the bank earns above its cost of equity on that capital.

The view is in the [pitch](../../equity-research/pitches/JPM_pitch.md). This folder holds the model.

## Files

- `jpm_ri_model.xlsx`: the model, all live formulas (528). Sheets:
  - Summary.
  - Inputs, with sources.
  - Historical: 2012–2025 from SEC filings.
  - RI model: one block per scenario, plus a per-share block on buybacks.
  - Reverse: the ROTE the price implies, and a cost of equity × ROTE grid.
  - Peers: six US banks on the same method.
- `build_model.py`: writes the workbook. `check_model.py` checks every formula after Excel recalculates it.
- `peers.py`: rebuilds `data/peers.csv`.

## The model

Starting point: tangible book of $112.64 a share at 30 September 2026, 2,651mm shares and a price of $339.72, which is 3.02x tangible book.

Cost of equity is 10.15%: 10-year at 5.10%, beta 1.0, ERP 5%. Terminal growth is 4%, roughly nominal GDP, the same as in the original pitch.

Each year, net income = ROTE × opening tangible equity. A payout ratio decides how much stays to grow the capital base. Residual income = net income − 10.15% × opening equity.

| | Bear | Base | Bull |
|---|---|---|---|
| Story | Credit cycle in 2027–28, then 15% | Glide from today's 21% to management's 17% target | Stays above 20% for a decade |
| ROTE in year 2 | 12% | 19% | 21% |
| Long-run ROTE | 15% | 17% | 20% |
| Value per share | $227 | $276 | $345 |
| vs $339.72 | −33% | −19% | +2% |
| Implied P/TBV | 2.02x | 2.45x | 3.06x |

Weighted 25/50/25: $281, 17% below the price.

The reverse is the cleanest way to say it. In steady state, P/TBV = (ROTE − g) / (r − g), so 3.02x means a ROTE of 22.5% forever. That's above management's own 17% through-the-cycle target, and above the 21% core ROTCE JPM just printed in a good quarter.

## Things I learned building it

- The cost of equity matters far more here than for Micron or GTT. In the Monte Carlo it's the second driver of value (rank correlation −0.60, against −0.25 for GTT). At 9%, the base case is worth about $293 on the steady-state formula; at 11%, about $209.
- Buybacks at 3x book are subtle. They lift EPS, and they lift tangible book per share compared with paying the same cash as dividends. But compared with keeping the money they dilute it, because every $1 spent removes $1 of tangible book and only $0.33 of book's worth of shares. When JPM cut buybacks to $0.66bn in Q3 to fund loan growth, that wasn't necessarily bad news for book value. I first described this the wrong way, as buybacks *reducing* TBVPS; the per-share block in the model made me fix it.
- Next to its peers, JPM isn't an outlier. On a P/TBV vs ROTE chart, JPM and Morgan Stanley sit a little above the "justified" line, Goldman a little below, and Citi well above. Citi's price is a bet on a turnaround, not on today's 10% ROTE.

## Monte Carlo

20,000 runs ([`../monte_carlo.py`](../monte_carlo.py)):

- long-run ROTE around 17% (±2.5 pp);
- a 30% chance of a credit cycle that drops ROTE to 8–14% in years 2–3;
- cost of equity ±1 pp, growth 3–5%, payout 45–70%.

Median $274; 5–95% range $170–458; **24% of runs are above the price** (29% with wider distributions). That's very different from Micron (5%) and GTT (9%). JPM isn't clearly expensive. It's priced for its best realistic outcome, which is what "quality at a full price" means in numbers.

## Where it could be wrong

- **Beta of 1.0.** Banks' betas swing with credit fears; one point of cost of equity moves the steady-state value by $35–50.
- **ROTE glide paths are my judgement.** Management's 17% target has been beaten for several years running, so the market may reasonably treat it as conservative.
- **No explicit regulation.** The stress capital buffer is recalculated in 2027. A higher requirement would mean lower payouts or slower growth, which isn't modelled beyond the payout ratio.
- **Peer ROTEs use trailing twelve months,** and they include JPM's Q2 2026 one-offs (the Visa gain).

Data: JPM Q3 2026 earnings release (2026-10-13), SEC EDGAR XBRL, Yahoo Finance at the 2026-10-16 close.
