# GTT: valuing a royalty business from its order book

October 2026. After Micron (a cyclical with heavy capex) I wanted the opposite kind of company. GTT licenses the tank technology inside almost every LNG carrier and gets paid a royalty per ship. It has hardly any capex and a 68% EBITDA margin, and the order book tells you most of the next three years. The question is what happens after that.

My view is in the [pitch](../../equity-research/pitches/GTT_pitch.md). This folder holds the model.

## Files

- `gtt_dcf.xlsx`: the model, all live formulas (1,299 of them). Blue cells are inputs, yellow ones are the key assumptions. Sheets:
  - Summary: the three scenarios side by side.
  - Inputs: market data, WACC, the revenue engine, the order-book schedule and scenario orders, all with sources.
  - Historical: 2021–H1 2026 figures and the order book.
  - DCF: one block per scenario, plus two helper blocks.
  - Reverse DCF: the orders a year needed to justify the price, and a WACC × orders sensitivity grid.
- `build_model.py`: writes the workbook. GTT isn't SEC-registered, so the inputs come from its press releases (PDF) and are typed into the script with their sources. Open the result in Excel to calculate it.
- `check_model.py`: after recalculating, checks every formula for errors and prints the key outputs.

## How the revenue engine works

Revenue = royalties already in the order book + future orders × royalty per vessel, spread over construction.

- Order book: the company publishes when its signed royalties will turn into revenue (€655mm in 2027, €603mm in 2028, and so on), so that part is taken as given.
- Royalty per vessel and timing: GTT doesn't publish these. I backed them out by comparing the schedule from December 2025 with the one from June 2026. The 65 orders booked in between added about €596mm, roughly €9.5–10mm per LNG carrier equivalent. That revenue landed about 20% the year after the order, 55% the year after that and 25% in the third year.
- Scenarios: they differ only in how many orders arrive each year from 2027: 35, 60 (the company's own 10-year estimate) or 75.

Before reading anything into the valuation I checked the near term against outside numbers. Modelled 2026 revenue is €737mm against guidance of €740–780mm, and 2027 is ~€810mm against consensus of €815mm.

## What came out

| | Bear | Base | Bull |
|---|---|---|---|
| Orders a year | 35 | 60 | 75 |
| Value per share | €66 | €129 | €172 |

At €211.60, the weighted value is €124. The reverse DCF says the price needs ~96 orders a year at my 9.6% WACC.

With Micron, my first draft was the problem. Here the near term matched guidance and consensus, so I looked for the gap elsewhere, in the sensitivity grid. Even at a 7.5% WACC with the company's 60 orders a year the value is €167. Getting to the price takes a lower discount rate *and* above-plan orders, so it isn't just my WACC.

## Assumptions I'm least sure about

- Beta of 0.9 instead of the regression 0.42. I don't trust a 0.42 beta for a business tied to shipbuilding cycles, but it's the most debatable input. With 0.5 the WACC is ~7.5%.
- The French 10-year (4.75%) as risk-free rate. It's at its highest since 2011 because of French politics. GTT is paid by Korean and Chinese yards, so a Bund-based rate is a fair alternative.
- Flat €9.5mm royalty per LNG-carrier equivalent (+2% a year). FLNGs and big onshore tanks pay more per unit, so a shift in mix would raise it.
- Terminal growth of 1.5% in the base case. It assumes LNG shipping keeps growing slowly after 2035, which is debatable either way given the energy transition.
- Timing. Cash flows from 2027 are discounted from the end of 2026. The H2 2026 cash flow is added to net cash, and the €4.30 interim dividend stays with the shareholder.

Data: GTT FY2025 (2026-02-19) and H1 2026 (2026-07-28) press releases; Yahoo Finance and Trading Economics, mid-October 2026.
