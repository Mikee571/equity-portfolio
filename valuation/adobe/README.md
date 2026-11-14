# Adobe: what the price says about AI disruption

October 2026. Adobe came out of a relative-value check of my screener. Against 45 software companies it has the 11th-percentile P/E and the 96th-percentile FCF yield, with ROIC in the top 7%. A business that good shouldn't trade at 15x earnings unless the market thinks the earnings are going away. So this model isn't really about forecasting Adobe. It asks how much AI disruption is already in the price.

My write-up is in the [pitch](../../equity-research/pitches/ADBE_pitch.md). This folder holds the model.

## Files

- `adobe_dcf.xlsx`: the model, all live formulas (1,256 of them). Blue cells are inputs, yellow ones are the key assumptions. Sheets:
  - Summary: the four scenarios side by side.
  - Inputs: market data, WACC, operating assumptions and the scenario paths, all with sources.
  - Historical: FY2019 to 9M FY2026 from SEC filings.
  - DCF: one block per scenario, plus two helper blocks.
  - Reverse DCF: the margin and perpetual growth the price implies, and two sensitivity grids.
  - Comps: mature software peers.
- `extract.py`: turns the SEC XBRL company facts into `data/adbe_annual_raw.csv` and `data/adbe_quarterly_raw.csv`.
- `build_model.py`: writes the workbook from those files plus the guidance in the Q3 FY2026 press release. Open the result in Excel to calculate it.
- `check_model.py`: after recalculating, checks every formula for errors and prints the key outputs.

## How the model works

It's a plain FCF model. The scenarios change only three things: revenue growth, operating margin and terminal growth. FY2026 is the company's own guidance midpoint ($26.6bn). Growth is set for FY27, FY31 and FY35 and interpolated in between. Margin is set for FY30 and FY35.

Two choices matter more than they look:

- I treat stock-based compensation as a cash cost. Adobe's non-GAAP operating margin is ~45%, but SBC is 8% of revenue, and the company spends about $2bn a year on buybacks just to stop the share count growing. So the margin in the model is ~37%. There is a switch in Inputs to add SBC back. That raises every value by 25–40%, which is why I didn't want it hidden.
- Working capital runs both ways. Adobe is paid upfront, so growth releases cash (deferred revenue). In the scenarios where revenue shrinks, that reverses and becomes a drag. The disruption case catches this automatically.

Before reading anything into the valuation I checked the near term. The base case FY27 revenue is $29.0bn, 0.1% below consensus.

## The four scenarios

| | Bull | Base | Erosion | Disruption |
|---|---|---|---|---|
| FY27 growth | 11% | 9.1% | 7% | 3% |
| Revenue CAGR FY26–35 | 9.4% | 6.3% | 2.1% | −3.7% |
| Margin FY35 (after SBC) | 42% | 37% | 30% | 22% |
| Terminal growth | 3.5% | 3% | 0% | −2% |
| Value per share | $510 | $357 | $200 | $110 |
| Probability (mine) | 20% | 40% | 25% | 15% |

- Bull: AI expands the market. Firefly and the agents bring in new users, and seats get repriced upwards.
- Base: consensus for FY27, then a slow fade. AI is a feature, not a new market.
- Erosion: the low end moves to free or cheaper tools, professionals stay, and price increases stop.
- Disruption: generative models replace the workflow. Revenue in FY35 is 30% below FY26 and keeps shrinking.

At $263.82 the weighted value is $311, 18% above the price.

## What the price implies

The reverse DCF gives three ways to read $263.82:

- On the base revenue path, the price needs a flat margin of 27.0% from FY27, against 37% today. So the market is pricing a bit more than a quarter of the margin away.
- As a perpetuity, it's FCF growing 2.3% a year forever at my WACC. Adding SBC back, it's 0.2%. Right now revenue is growing 12–13%.
- Between my scenarios, the price is a 40/60 mix of base and erosion.

The discount rate matters a lot here. With the same method as Micron (Blume-adjusted beta of 1.28, 5% ERP) the WACC comes out at 11.0%, which is high for a company with net cash and A+ debt. At 10% the base case is worth $406, at 9% $473. The base case only equals the price at a 13.8% WACC. The WACC × growth grid on the Reverse DCF sheet shows this.

## Assumptions I'm least sure about

- The scenario probabilities. They are the most subjective number in the model, and the weighted value is mostly a function of them.
- Organic growth. Reported growth of 13% in Q3 includes Semrush, which closed in Q2 and added ~$480mm of ARR. My rough estimate is that organic ARR growth is closer to 8% than 10%.
- Leadership. The CFO left in June, the head of the creative business left in September, and Anil Chakravarthy takes over from Shantanu Narayen on 1 December. That's a lot of change in one year for a company whose whole question is execution through a technology shift.
- Margin path. I keep the margin flat at 37% in the base case. If AI inference costs grow faster than pricing, gross margin will fall even if revenue holds.
- Timing. Cash flows from FY27 are discounted from the end of FY26 (late November), at mid-year. The Q4 FY26 cash flow is added to net cash.

Data: SEC 10-K FY2025, 10-Qs and 8-Ks for FY2026 (press releases of 12 March, 11 June and 10 September 2026; CEO announcement of 3 September); Yahoo Finance as of 2026-10-23; TradingView as of 2026-10-25.
