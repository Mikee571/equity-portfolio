# Deckers: how much fade is in the price

November 2026. Deckers came out of my screener: rank 15 on 1 November, with a P/E of 10.9, ROE of 44%, an FCF yield of 9.6% and no debt. Unlike most names near the top that week, its earnings growth wasn't a base effect. The stock is down from $122 to $82 in a year. A company that owns HOKA and UGG and earns a 21–23% operating margin doesn't trade at 10x forward earnings unless the market thinks both brands are at a peak. So, like the Adobe model, this one asks what the price already assumes.

My write-up is in the [pitch](../../equity-research/pitches/DECK_pitch.md). This folder holds the model.

## Files

- `deckers_dcf.xlsx`: the model, all live formulas (1,679 of them). Blue cells are inputs, yellow ones are the key assumptions. Sheets:
  - Summary: the four scenarios side by side.
  - Inputs: market data, WACC, operating assumptions and the brand growth paths, all with sources.
  - Historical: FY2021 to 6M FY2027, by brand, from SEC filings.
  - DCF: one block per scenario, plus two helper blocks.
  - Reverse DCF: the margin and perpetual growth the price implies, and three sensitivity grids (HOKA × UGG growth, margin × growth, WACC × growth).
  - Comps: footwear and apparel peers.
- `extract.py`: turns the SEC XBRL company facts into `data/deck_annual_raw.csv` and `data/deck_quarterly_raw.csv`.
- `build_model.py`: writes the workbook from those files, the brand sales in the 10-Ks and the guidance in the Q2 FY2027 release. Open the result in Excel to calculate it.
- `check_model.py`: after recalculating, checks every formula for errors and prints the key outputs.
- `data/filings/`: the 10-Ks, 10-Q and 8-Ks the numbers come from (not in git).

## How the model works

Revenue is built by brand, because that's where the debate is. HOKA has gone from +56% growth in FY2022 to +16% in FY2026 and +7% in the first half of FY2027. UGG has grown for five years in a row, and it has been through this before: in FY2015–17 it went out of fashion and Deckers' operating income went to zero. The scenarios change only four things: HOKA growth, UGG growth, operating margin and terminal growth. Other brands (mostly Teva, ~$100mm) stay flat.

FY2027 is the company's own guidance: $5.71bn of revenue and a ~23% operating margin. That margin includes about 1.5 points of one-off IEEPA tariff refunds, so the underlying margin is ~21.5%, against 23.1% in FY2026. Every scenario starts from 21.5% or lower in FY2028. Growth is set for FY28, FY32 and FY36 and interpolated in between. Margin is set for FY28, FY31 and FY36.

A few choices that matter:

- Timing. The fiscal year ends on 31 March. FY2028–36 cash flows are discounted to 31 March 2027, the second half of FY2027 is added there, and the total is discounted five months back to 30 October 2026. H2 matters, because it's when the UGG season turns inventory into cash: H1 FCF was −$47mm, the full year should be close to $1bn.
- Cash. Net cash is $1.21bn at 30 September, the seasonal low. There's no debt. I don't deduct lease liabilities ($540mm), because rent is already inside operating income.
- No SBC adjustment this time. It's 0.8% of revenue and already in GAAP operating income, so unlike Adobe there's nothing to argue about.
- Working capital is 8% of each extra dollar of revenue, the FY24–26 average. In the scenarios where revenue shrinks, it releases cash.

Before reading anything into the valuation I checked the near term. The base case FY2028 revenue is $6.05bn, 0.1% above consensus.

## The four scenarios

| | Bull | Base | Fade | Bust |
|---|---|---|---|---|
| HOKA growth FY28 / FY32 / FY36 | 13% / 10% / 5% | 9% / 6% / 4% | 5% / 3% / 2% | 0% / −2% / 1% |
| UGG growth FY28 / FY32 / FY36 | 5% / 3% / 2% | 3% / 2% / 2% | −3% / −2% / 0% | −10% / −4% / 0% |
| Operating margin FY36 | 24% | 21% | 17% | 13% |
| Terminal growth | 3.5% | 3% | 2% | 1% |
| Value per share | $156 | $118 | $80 | $54 |
| Probability (mine) | 20% | 45% | 25% | 10% |

- Bull: HOKA becomes a global top-three running brand and keeps compounding internationally. Margins go back above FY2025.
- Base: consensus for FY28, then a slow fade. Tariffs keep margins about 1.5 points below FY2026 for good.
- Fade: the UGG cycle ends the way it did in FY2015–17, and HOKA loses share in the US to On and Asics. Margins go back to the FY22–23 level.
- Bust: both brands go out of fashion at once. Margins fall towards where they were before HOKA.

At $81.99 the weighted value is $110, 34% above the price.

## What the price implies

The reverse DCF gives three ways to read $81.99:

- On the base revenue path, the price needs a flat operating margin of 13.9% from FY2028, against 21.5% underlying today. That's lower than any year since FY2018.
- As a perpetuity, it's FCF shrinking 0.3% a year forever at my WACC.
- At today's margin, it's roughly zero growth for both brands, forever. The HOKA × UGG grid puts the price at about HOKA 0% and UGG 0%, or HOKA +4% with UGG falling 6–8% a year.

Between my scenarios, the price is almost exactly the fade case. In other words, the market is already paying for the UGG cycle to end and HOKA to slow to low single digits.

The discount rate matters less here than for Adobe. With a beta of 1.07 and no debt, the WACC is 10.3%. At 12%, zero growth is still worth $72. At 2% growth it's worth $84, about the price.

## Assumptions I'm least sure about

- UGG. Five years of growth in a brand that is partly a fashion item. Wholesale is still growing (+6.7% in Q2) while DTC is falling (−8.4%), and that's how the last downturn started: retailers stocked up as consumers bought less at full price.
- HOKA in the US. Company-wide, international sales grew 9% in Q2 and the US was flat. HOKA's growth came from international, and the 10-Q says its US DTC customers are going to wholesale partners "seeking promotional offerings". If that's the start of discounting, the margin in the base case is too high.
- Tariffs. The 21.5% underlying margin already includes the current tariffs. Higher tariffs, or the refunds being clawed back, would take another point or two off.
- The scenario probabilities, as always. Fade gets 25% and bust 10%. If I'm wrong about the fashion risk, it's more likely there.
- Buybacks. The company is buying back about $1bn a year, around 9% of the market cap. At $82 that adds value if the base case is right, and destroys it in the bust case. The model treats them as neutral.

Data: SEC 10-Ks FY2022, FY2024 and FY2026, 10-Q Q2 FY2027, 8-Ks of 27 August and 22 October 2026 (Q2 FY27 release); Yahoo Finance as of 2026-10-30 (price, beta, consensus) and 2026-11-02 (peers).
