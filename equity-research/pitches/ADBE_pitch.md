# Stock Pitch: Adobe (Nasdaq: ADBE)

Date: 2026-10-25
Sector: Software: creative, document and marketing applications
Current Price: $263.82 (2026-10-23 close)
View: Cheap. The price already assumes a lot of erosion, and the business isn't showing it yet.
Model: [`valuation/adobe/adobe_dcf.xlsx`](../../valuation/adobe)

---

*Why I looked at it: Adobe came out of a relative-value check of my screener. Against 45 software companies it has the 11th-percentile P/E and the 96th-percentile FCF yield, with ROIC in the top 7%. It is down 25% in a year while the median software stock is flat.*

## 1. Thesis in one sentence

> At $264 the market is paying for Adobe to lose about a quarter of its margin, while revenue is still growing 12–13% and the margin is holding at 37% after SBC. AI disruption is a real risk, but the price already pays for a good part of it.

What the model says: at $264 the market is pricing Adobe somewhere between my base case ($339) and my erosion case ($190), close to a 50/50 mix. Equivalently, it is paying for FCF growth of 2.7% a year forever, or a margin that falls from 37% to 28.5% on consensus revenue.

## 2. Screening scorecard

| Metric | Value | Threshold | Pass? |
|---|---|---|---|
| P/E (trailing) | 14.7x | < 15x value / < 25x growth | Yes |
| ROE | 62% | > 15% | Yes, helped by buybacks shrinking equity |
| Debt/Equity | 0.57 ($6.4bn debt, $5.6bn cash) | < 1.0 | Yes, roughly net-debt neutral |
| Free cash flow | $10.6bn TTM ($8.5bn after SBC) | Positive & growing | Yes |
| PEG | ~1.2 on FY27 consensus EPS growth (12%) | < 1.5 | Yes |

## 3. The business

Adobe sells subscriptions to Creative Cloud (Photoshop, Illustrator, Premiere), Document Cloud (Acrobat) and enterprise marketing software. Since FY2026 it reports two customer groups: Creative & Marketing Professionals ($4.65bn of subscription revenue in Q3, +13%) and Business Professionals & Consumers ($1.91bn, +16%).

The numbers are still very good. FY2026 guidance is $26.6bn of revenue (+12%) and a ~45% non-GAAP operating margin. ARR was $27.5bn at the end of Q3. The company says AI-first ARR grew more than 150% a year and that it now has a billion monthly active users across its apps.

Two things make the reported numbers look better than the underlying business:

- Semrush. The acquisition closed in Q2 and brought ~$480mm of ARR. Without it, my rough estimate is that ARR is growing about 8%, not 10%.
- SBC. Stock-based compensation is 8% of revenue. Adobe spent $11.3bn on buybacks in FY2025, more than its free cash flow. That cut the share count from 490mm in FY2019 to 389mm, but about $2bn a year of it only offsets dilution.

## 4. Valuation

Four scenarios that differ only in growth, margin and terminal growth. Margins are after SBC.

| | Bull | Base | Erosion | Disruption |
|---|---|---|---|---|
| Revenue CAGR FY26–35 | 9.4% | 6.3% | 2.1% | −3.7% |
| Margin FY35 | 42% | 37% | 30% | 22% |
| Value per share | $484 | $339 | $190 | $105 |
| vs price | +84% | +28% | −28% | −60% |

With my probabilities (20/40/25/15) the weighted value is $296, 12% above the price.

The reverse DCF:

- Margin the price needs on the base revenue path: 28.5% from FY27, against 37% today.
- Perpetual FCF growth the price implies: 2.7% (0.7% if SBC is added back). In the relative-value check I said about −1%. That was wrong: I used FCF before SBC and a 9% discount rate.
- WACC at which the base case equals the price: 13.2%. My WACC is 11.0%.

Against mature software peers (Microsoft, Oracle, SAP, Salesforce, ADP, Intuit) Adobe trades at roughly a 30% P/E discount. The all-software median (36x) overstates it, because it includes Palantir and CrowdStrike.

## 5. Bull case

- The price already assumes a lot of damage. Even the erosion case, where growth goes to zero and margins drop 7 points, is worth $190, 28% below today.
- AI-first ARR is growing more than 150%, and freemium is adding users. If AI turns out to expand the market, the base case is worth $339 and the bull case $484.
- A lower discount rate. With net cash and A+ debt, an 11% WACC is conservative. At 9–10% the base case is $387–453.

## 6. Bear case

- The disruption case isn't far-fetched. If image, video and document work can be done by a model without the app, the subscription base shrinks, and working capital becomes a cash drain on the way down. That case is worth $105.
- Organic growth is slowing. Without Semrush, ARR growth is closer to 8%, and FY27 consensus is +9%.
- Leadership turnover in one year: the CFO resigned in June, the president of the creative business left in September, and a new CEO starts on 1 December.
- SBC and buybacks. Adobe has spent more than its FCF on buybacks. At a lower share price that is better value, but it leaves less cushion.

## 7. Catalysts to watch

| Catalyst | Expected timing | Impact if it happens |
|---|---|---|
| Q4 FY26 results and FY27 guidance (first under the new CEO) | mid-December 2026 | FY27 revenue guidance below ~$28.5bn would move me towards the erosion case |
| Organic ARR growth disclosed without Semrush | Q4 FY26 / Q1 FY27 | Below 8% supports erosion; above 10% supports base |
| AI-first ARR as a share of total | Each quarter | Rising from ~2% to over 10% would point to the bull case |
| Gross margin trend (AI compute costs) | Each quarter | A fall of more than 1–2 points a year breaks the flat-margin base case |

## 8. Position management rules

My call is cheap, not a sure thing. What I'm betting on is that the erosion the price assumes takes longer, or is smaller, than the market thinks. These rules check that bet against the numbers each quarter.

- Add if the price falls towards the erosion case (~$190–210) and the quarterly numbers still look like the base case: organic ARR growth of 8% or more, and a margin after SBC of 35% or more.
- Trim if the price reaches the base case (~$340). From there, the upside depends on the bull case.
- Exit if the thesis breaks, which means two quarters in a row of any of these: organic ARR growth below 6%, the margin after SBC below 33%, or FY27 guidance pointing to growth below 7%. At that point the business is the erosion case, and the price would no longer be cheap.
- Review after every quarterly release. The first real test is the Q4 FY26 results and FY27 guidance in mid-December, the first under the new CEO.

## 9. Sources

- Adobe 10-K FY2025 and 10-Qs for Q1–Q3 FY2026 (SEC XBRL company facts)
- Press releases (8-K): Q1 FY26 (2026-03-12), Q2 FY26 (2026-06-11), Q3 FY26 (2026-09-10); CEO appointment (2026-09-03); CFO resignation (2026-06-11)
- Yahoo Finance, 2026-10-23: price, beta, consensus, targets
- TradingView, 2026-10-25: peer multiples

---
*This document reflects personal research and is not investment advice.*
