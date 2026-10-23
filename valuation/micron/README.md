# Micron: a DCF at the top of a memory cycle

October 2026. Micron had just reported a year nobody would have modelled two years earlier: revenue up from $37bn to $133bn and operating margin from 26% to 75%. The stock traded at about 4x forward earnings. I wanted to know whether that was cheap or whether the market was right to distrust the earnings.

The write-up with my view is the [pitch](../../equity-research/pitches/MU_pitch.md). This folder holds the model.

## Files

- `micron_dcf.xlsx`: the model, all live formulas (465 of them). Blue cells are inputs, yellow ones are the key assumptions. Sheets:
  - Summary: the three scenarios side by side and the probability-weighted value.
  - Inputs: market data, WACC, scenario paths, all with sources.
  - Historical: FY14–FY26 from SEC filings, plus through-cycle margins.
  - DCF: one block per scenario.
  - Reverse DCF: the margin needed to justify the price, and a WACC × margin sensitivity grid.
  - Comps: six memory and storage peers.
- `build_model.py`: writes the workbook from `data/mu_annual_raw.csv` (pulled from the SEC XBRL API) and the inputs listed in the script. Open the result in Excel to calculate it.
- `check_model.py`: after recalculating, checks every formula for errors and prints the key outputs.

## How I approached it

The hard part of valuing a cyclical at the peak is that the current year tells you almost nothing about the steady state. So I anchored all three scenarios to analyst consensus for FY27–28 ($275bn and $319bn of revenue) and let them differ in what happens after:

| | Bear | Base | Bull |
|---|---|---|---|
| After FY28 | 2023-style bust | Cycle turns, normalises | No real downturn |
| Normalised operating margin | 20% (≈ FY15–25 average of 17.5%) | 35% (above history, HBM mix) | 50% |
| Value per share | $208 | $511 | $1,049 |

At $879, the weighted value (30/50/20) is $528.

My first version had the near term far below consensus. All three scenarios came out under the price, and the reverse DCF asked for a 139% margin. That was a sign my inputs were off, not that the market was mad, so I recalibrated to consensus before drawing any conclusion.

The most useful output turned out to be the reverse DCF. With base-case revenue, the price needs operating margins of ~94% from FY29, which can't happen. So the market isn't really pricing margins; it's pricing revenue that doesn't come back down. That reframed the question for me, from "is 4x cheap?" to "do I believe memory has stopped being cyclical?"

## Where the model could be wrong

- WACC of 14.2%. It comes from a raw beta of 2.2, Blume-adjusted to 1.82. That's the input that most separates my numbers from the sell-side mean target of ~$1,560. At 10% the base case is $675, and the bull case is $1,579, which is basically the Street's target.
- Customer deposits ($12.7bn) treated as debt. They're prepayments to be repaid in product. Switching that off in Inputs adds about $11 a share.
- Capex paths are my own estimates. Memory capex is lumpy, and it moves free cash flow a lot in the explicit years.
- Discounting. End-of-year discounting from September 2026, with a five-year explicit period and a terminal value based on reinvestment (g / RONIC). In the base case the terminal value is only a third of EV, so the near term carries a lot of weight.

Data: SEC EDGAR (10-K FY26 filed 2026-10-09, 8-K of 2026-09-30) and Yahoo Finance as of 2026-10-16.
