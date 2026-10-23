# Stock Pitch: Micron Technology (MU)

Date: 2026-10-17 (price as of the 2026-10-16 close; fundamentals through FY2026, ended 2026-09-03)
Sector: Semiconductors, memory (DRAM, HBM, NAND)
Current Price: $878.84
View: Expensive. The price only works if the memory cycle doesn't turn.
Model: [`valuation/micron/micron_dcf.xlsx`](../../valuation/micron)

---

*Why I looked at it: Micron kept showing up in the weekly research I read, always with the same pitch: AI demand, record margins, a 4x P/E. Anything that looks that cheap after a year like this deserves a model before an opinion.*

## 1. Thesis in one sentence

> At $879, Micron's 4x forward P/E isn't cheap: it already assumes record FY27–28 earnings, and on top of that it prices revenue staying near the peak for years. For a business whose operating margin went from −37% to 75% in three years, I'd want a margin of safety, and there isn't one.

## 2. Screening scorecard

| Metric | Value | Threshold | Pass? |
|---|---|---|---|
| P/E (trailing) | 11.8x | < 15x value / < 25x growth | Yes, but on peak earnings |
| ROE (FY26) | ~88% | > 15% | Yes, at the top of the cycle |
| Debt/Equity | ~0.04 | < 1.0 | Yes: $73.5bn of cash and investments against ~$5bn of debt and leases |
| Free cash flow | $62.3bn adjusted (FY26) | Positive & growing | Yes |
| PEG | ~0.01 | < 1.5 | Meaningless: EPS grew ~9x in one year |

Every factor passes, and that's exactly the problem with screening a cyclical at its peak. The screen sees record earnings, not where they sit in the cycle.

## 3. Where Micron is

FY2026 was extraordinary. Revenue went from $37.4bn to $133.2bn, operating margin from 26% to 74.6%, and EPS from $7.59 to $74.33. Q4 alone brought in $54.2bn at an 86.8% gross margin, and Q1 FY27 guidance is $61.5bn. Analysts expect $275bn of revenue in FY27 and $319bn in FY28.

History is the counterweight. Between FY15 and FY25 the operating margin averaged 17.5%, ranging from −37% (FY23) to 49% (FY18, the previous peak). Memory has always been a commodity business: when prices are high, everyone adds capacity, and prices fall.

## 4. Valuation

I built a three-scenario DCF. All three start from consensus-like FY27–28 numbers; what separates them is what happens after.

WACC is 14.2%: risk-free 5.1%, Blume-adjusted beta 1.82, ERP 5%. Terminal growth is 3%, with reinvestment set by a 15% return on new capital. The $12.7bn of customer prepayments are treated as debt.

| | Bear | Base | Bull |
|---|---|---|---|
| Story | FY27 at the low end of estimates, then a 2023-style bust | Consensus FY27–28, then the cycle turns | No real downturn; memory stops being a commodity |
| FY2031 revenue | $86bn | $151bn | $368bn |
| Normalised operating margin | 20% | 35% | 50% |
| Value per share | $208 | $511 | $1,049 |
| vs $879 | −76% | −42% | +19% |

Weighting the scenarios 30/50/20 gives **$528, about 40% below the price**.

The more useful number is the reverse DCF. With the base-case revenue path, Micron would need operating margins of about 94% from FY29 onwards to justify $879. That's impossible, so the market isn't betting on margins. It's betting on revenue not falling back. Put another way, the price sits about two-thirds of the way from my base case to my bull case.

Monte Carlo. I also ran 20,000 simulated DCFs instead of three scenarios ([details](../../valuation/README.md)). The median comes out at $507, and only 5.5% of runs are worth more than $879; with 50% wider distributions, 13% are. The two inputs that matter most are how far revenue falls after FY28 and the normalised margin. The discount rate is a distant third.

The peers look the same: SK hynix trades at 2.7x and Samsung at 3.0x forward earnings. The whole group is priced for a cycle, not for a new normal.

## 5. Bull case (what would make me wrong)

- AI changes the demand curve. HBM is harder to make, uses more wafer per bit and is sold on multi-year contracts. If that keeps supply tight for longer, the bull path is real.
- Strategic Customer Agreements. Customers prepaid $12.7bn in FY26. Longer contracts with price floors would make revenue far less cyclical than it has been.
- The industry is disciplined this time. With only three DRAM makers and new fabs taking years, the supply response could be slower than in past cycles.
- My discount rate is high. At a 10% WACC the base case rises to $675, still below the price, and the bull case to $1,579, almost exactly the sell-side mean target of ~$1,560. So the Street's number looks like my bull case at a lower discount rate. How much of my conclusion rests on that one input is worth being clear about.

## 6. Bear case (why I think it's expensive)

- Every memory peak has been followed by a bust. Margins went 49% → 14% (FY18 → FY20) and 31% → −37% (FY22 → FY23).
- Capacity is coming. Micron is raising capex (net $27.4bn in FY26, more planned), and so are SK hynix and Samsung. High prices fund the supply that ends them.
- Customer concentration. A handful of AI platforms drive the data-centre business. Any slowdown in AI capex reaches memory quickly.
- There's no margin of safety. Even the bull case is only 19% above the price, while the bear case is 76% below.

What would change my view: revenue holding near FY28 consensus through FY29–30 with operating margins above 60%; long-term agreements with price floors covering most of the data-centre business; or industry capex falling as a share of revenue while prices stay high.

## 7. Catalysts to watch

| Catalyst | Expected timing | Impact if it happens |
|---|---|---|
| Q1 FY27 results vs $61.5bn guidance | Late December 2026 | A beat with higher guidance supports the bull path |
| DRAM and HBM contract prices | Monthly / quarterly | The first sign of a turn shows up in prices before revenue |
| Industry capex plans (Micron, SK hynix, Samsung) | With each set of results | Rising capex/revenue is the classic warning sign |
| Hyperscaler capex guidance | January–February 2027 | Demand-side confirmation or warning |
| Customer prepayments and new agreements | 10-Q filings | More, longer agreements argue for structural change |

## 8. Position management

I don't hold Micron directly. My only exposure is through VanEck's semiconductor ETF (SMH) and my global index fund.

- Would reconsider at: around $500 (my base case), or if the "what would change my view" conditions start to show up.
- Review cadence: after each quarterly release, starting with Q1 FY27.

## 9. Sources

- Micron Technology, Form 10-K for fiscal year 2026 (filed 2026-10-09) and SEC EDGAR XBRL company facts, CIK 0000723125.
- Micron Technology, FQ4-26 earnings release (Form 8-K exhibit 99.1, 2026-09-30).
- Prices, beta, peer multiples and analyst estimates: Yahoo Finance via yfinance, 2026-10-16. US 10-year yield: ^TNX, same date.
- Model and every assumption: [`valuation/micron/micron_dcf.xlsx`](../../valuation/micron), generated by `build_model.py`.

---
*This document reflects personal research and is not investment advice.*
