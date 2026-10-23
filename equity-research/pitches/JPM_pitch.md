# Stock Pitch: JPMorgan Chase & Co. (JPM)

Date: 2026-10-11, updated 2026-10-13 with Q3 2026 results (§0)
Sector: Financials, US money-center bank
Current Price: $334.05 (2026-10-13; $332.99 at the original 2026-10-09 close)
Position size: decided separately under my personal portfolio rules (not published here).
Model: [`valuation/jpm/jpm_ri_model.xlsx`](../../valuation/jpm) (residual income, added 2026-10-18)

> §0 supersedes the figures in §1–§5 where they differ. Sections 1–5 are
> kept as written on 2026-10-11 (Q2 2026 data) for the record.

---

*Why I looked at it: JPM kept coming up in the weekly research I read, usually described as the best bank in the US. I wanted to put a number on what "best" is worth. Banks also make a good exercise because the metrics my screener relies on, debt/equity and free cash flow, don't work for them, so the valuation has to be built differently: tangible book, ROTE and capital.*

## Full model (2026-10-18)

After the Q3 update I built a proper residual income model, the bank equivalent of the DCFs I did for Micron and GTT ([details](../../valuation/jpm)). Price $339.72, tangible book $112.64, cost of equity 10.15%, growth 4%.

| | Bear | Base | Bull |
|---|---|---|---|
| ROTE path | Credit cycle in 2027–28, then 15% | 21% → 17% (management's target) | Above 20% for a decade |
| Value per share | $227 | $276 | $345 |
| vs price | −33% | −19% | +2% |

- Weighted 25/50/25: $281 (−17%).
- The price implies a 22.5% ROTE forever.
- A Monte Carlo with a 30% chance of a credit cycle puts 24% of outcomes above the price, against 5% for Micron and 9% for GTT.

So the conclusion of this pitch holds, and the model makes it more precise: JPM isn't expensive the way Micron is. It's priced for its best realistic outcome, which leaves no margin of safety. Another way to see it: the base case justifies today's price only at a cost of equity just under 9% (about $347 at 9%), while at my 10.15% it's worth about $276. I'd look again closer to $280.

## 0. Q3 2026 update (results of 2026-10-13)

Verdict: thesis intact, valuation tension higher. None of the §4
thesis-breaking conditions occurred. But core ROTCE (21%) is now *below*
the 23% the price implies, and the capital-return leg of the bull case
weakened.

| Item | Q2 2026 (pitch) | Q3 2026 | Read |
|---|---|---|---|
| EPS reported / ex items | — | $5.57 / $5.75 (consensus ~$5.91–5.94) | Miss of ~3% |
| ROTCE reported / ex items | 29% / 23% | 20% / 21% | Lower; still above the 17% through-the-cycle target |
| Significant item | Visa + equity gains (+$1.56) | $658M securities losses (−$0.18) | One-offs flipped sign |
| Revenue (managed) | $58.0B | $50.9B, +8% YoY | NII $27.1B (+13%); NIR $23.8B (+3%) |
| Expenses | — | $27.3B, **+12% YoY** | Negative operating leverage (revenue +8%) |
| Credit costs | — | $2.7B: NCO $2.2B, reserve build $539M (mostly Wholesale) | Card NCO rate **2.91%** (3.34% in Q2); 2026 guide ~3.2% |
| CET1 (Standardized) | 14.1% | 13.9% (−30 bp: AOCI, RWA growth, distributions) | Dimon: ~**$30B** excess capital (pitch estimated ~$55B) |
| Net buybacks | $6.2B | **$0.66B** | Cut on purpose: capital redirected to organic growth (loans +10% YoY) |
| TBVPS | $113.35 (+10% YoY) | $112.64 (**−0.6% QoQ**, +7% YoY) | AOCI losses |
| Segments | — | CCB ROE 36%, CIB 18%, AWM 45% | Markets $10.3B (+15%), IB fees $3.0B (+14%) |
| Guidance | — | Q4 NII ~$28B (~$25.5B ex Markets); Q4 expenses ~$27.5B; 2027 NII ex Markets ~$107B | ~+5% over the Q4 run-rate |

**Updated valuation** (TBVPS $112.64, price $334.05, g = 4%):

- P/TBV **2.97x**. Implied sustained ROTE at r = 10.5%: **23.3%**, unchanged.
- TTM EPS ≈ $23.84 (P/E 14.0x); ex significant items ≈ $22.46 (P/E 14.9x).
  Approximate: Q3 2025 EPS inferred from the +10% YoY growth.

| Sustained ROTE | r = 9.5% | r = 10.5% | r = 11.5% |
|---|---|---|---|
| 17% | $266 | $225 | $195 |
| 20% | $328 | $277 | $240 |
| **21% (Q3 core)** | $348 | **$295** | $255 |
| 23% | $389 | $329 | $285 |

At Q3's core return, the base case (r = 10.5%) gives ~$295, about 12%
below the price.

**Changes to the case**

- *Weaker:* the buyback was the main support for EPS/TBVPS growth. It fell
  by 90% in one quarter, and real excess capital (~$30B) is about half what
  the pitch assumed. Expenses grew faster than revenue. TBVPS growth slowed
  from 10% to 7% YoY.
- *Stronger:* card losses improved (2.91% vs 3.34%). Loan growth of 10% is
  where the capital is going, which is a better use than buybacks *if* it
  earns the ROE. Management guides 2027 NII ex Markets ~5% above the Q4
  run-rate, and Dimon says JPM is tightening credit while others loosen.
- *Unchanged:* succession (no news) and the 2027 SCB recalculation.

**Thesis-breaking conditions (§4)**

| Condition | Status |
|---|---|
| Core ROTCE < ~17% for two consecutive quarters | Not met: 21% |
| CET1 towards 12.5% | Not met: 13.9%, but trending down (−30 bp) |
| Disorderly leadership transition | Not met: no news |

The miss isn't thesis-breaking, so there's no decision to write up. This
section is the post-earnings review that §6 asks for.

**What to watch in Q4 2026 (January 2027)**

- Does core ROTCE stay ≥ 20%?
- Do buybacks resume, or does organic growth keep absorbing capital?
- CET1 trend and the expense run-rate vs the $27.5B guide.
- Card NCO vs the ~3.2% guide.

**Sources for §0**

- JPMorgan Chase Q3 2026 earnings release (Form 8-K exhibit 99.1,
  2026-10-13, accession 0001628280-26-065582).
- Earnings-call coverage: MarketBeat call highlights and the Investing.com
  transcript (2026-10-13).
- Price: yfinance, 2026-10-13.

---

## 1. Thesis in one sentence

> JPM is the highest-quality large US bank: core ROTCE of 23%, CET1 2.6 points
> above its requirement, and tangible book value per share up 10% a year. At
> 2.9x tangible book, though, the price already assumes it keeps that return
> indefinitely, so this is a quality-at-a-full-price idea, not a value idea.

## 2. Screening scorecard

The five-factor screen excludes financials by design: debt/equity and free
cash flow are not meaningful for a bank, because deposits are its raw
material and trading flows swamp operating cash flow. The template's
factors are shown where they apply, with bank equivalents for the other
two.

| Metric | Value | Threshold | Pass? |
|---|---|---|---|
| P/E (TTM, reported) | 14.3x | < 15x value / < 25x growth | Borderline value / yes growth |
| P/E (TTM, ex Q2 significant items) | 15.3x | < 15x value / < 25x growth | No value / yes growth |
| ROE (Q2 2026, annualised) | 24% (ROTCE ex items 23%) | > 15% | Yes |
| Debt/Equity → *CET1 ratio (Standardized)* | 14.1% vs 11.5% required | Comfortably above requirement | Yes |
| Free Cash Flow → *TBVPS growth / payout* | TBVPS +10% YoY; LTM net payout 73% | Positive & growing | Yes |
| PEG (P/E ÷ TTM EPS growth of 19.7%) | 0.73 | < 1.5 | Yes, but growth is flattered by one-offs (§4) |

Sources: Q2 2026 earnings release (8-K, 2026-07-14), 10-Q for Q2 2026, SEC
XBRL company facts. TTM figures were computed from the filings with the
same point-in-time method as the screener backtest.

## 3. Bull case

- Best-in-class profitability. In Q2 2026, ROTCE was 23% excluding
  significant items (29% reported). Computed on the same basis for all six
  banks, JPM's TTM return on tangible equity is 21.6%, against:

  | Bank | TTM ROTE (computed) |
  |---|---|
  | BAC | 15.6% |
  | WFC | 16.2% |
  | C | 8.5% |
  | GS | 20.9% |
  | MS | 22.2% |

  Only the two investment banks come close, and they have different
  business mixes.
- Diversified revenue. Q2 managed revenue was $58.0B: net interest
  income $25.6B (+10% YoY) and noninterest revenue $32.4B. Average loans grew
  10% YoY and average deposits 7%.
- Excess capital and a large return programme. CET1 is 14.1% against an
  11.5% requirement. The stress capital buffer is fixed at 2.5% until
  September 2027. The 2.6-point cushion is worth about $55B of capital on
  $2.1T of risk-weighted assets.
  - The Board raised the quarterly dividend to $1.65 (from $1.50) from Q3
    2026 and authorised a new $50B buyback from 2026-07-01.
  - Q2 net repurchases were $6.2B; LTM net payout was 73%.
- Compounding book value. Tangible book value per share was $113.35 at
  2026-06-30, up 10% YoY, while returning most of the earnings.

## 4. Bear case

- The valuation already prices it in. The justified price-to-tangible-
  book of a bank is (ROTE − g) / (r − g).
  - Inputs: cost of equity r ≈ 10.5% (US 10-year at 5.24%, weekly beta
    1.02–1.09, equity risk premium 5%) and growth g = 4%.
  - On those inputs, today's 2.94x requires a **sustained ROTE of 23%**:
    exactly the current core level, with no margin of safety.

  Justified value per share (TBVPS $113.35, g = 4%):

  | Sustained ROTE | r = 9.5% | r = 10.5% | r = 11.5% |
  |---|---|---|---|
  | 17% | $268 | $227 | $196 |
  | 20% | $330 | $279 | $242 |
  | 23% | $392 | $331 | $287 |

  If returns normalise to the high teens, the model gives $196–268, 20% to
  41% below today.
- Earnings quality. Q2 2026 included $4.2B after tax of significant
  items: a gain related to Visa shares (+$1.27 EPS) and $1.0B of gains on
  equity investments (+$0.29 EPS). TTM EPS of $23.34 is overstated by at
  least $1.56. Markets revenue is cyclical too.
- Credit normalisation. The Card Services net charge-off rate was
  3.34% in Q2, with a reserve build of only $149M. A recession would show up
  first in card losses and reserve builds.
- Succession. On 2026-06-25, Doug Petno and Troy Rohrbaugh were named
  Co-Presidents and CEOs of the two largest businesses as part of "ongoing
  succession planning". Marianne Lake (CEO of CCB) is retiring, and one-off
  retention awards were granted. Jamie Dimon remains Chairman and CEO. The
  eventual handover is a key-person risk the premium valuation leaves
  little room for.
- The rules can change. The 2.5% stress capital buffer will be
  recalculated in 2027 under revised supervisory models. A higher
  requirement would shrink the excess capital behind the buyback.
- Relative performance. JPM is up 5.3% YTD and 11.1% over 12 months,
  against SPY at +15.1% and +17.3%. It has beaten the financials ETF (XLF
  +1.1% YTD) but not the market.
- What would make this thesis wrong: core ROTCE falling below ~17% for
  two consecutive quarters, CET1 dropping towards 12.5%, or a disorderly
  leadership transition.

## 5. Catalysts to watch

| Catalyst | Expected timing | Impact if it happens |
|---|---|---|
| Q3 2026 results | 2026-10-13 | Tests core ROTCE excluding one-offs; consensus EPS $5.94 |
| Pace of the $50B buyback | Quarterly, from Q3 2026 | Supports EPS and TBVPS growth while CET1 excess lasts |
| Dividend ($1.65, payable 2026-10-31) | Quarterly | Yield ~2.0% at today's price |
| Stress capital buffer recalculation | 2027 (current SCB fixed to 2027-09-30) | A higher requirement cuts excess capital and buybacks |
| Leadership transition | Not scheduled | Key-person risk on the valuation premium |
| Card charge-offs and reserve builds | Each quarter | Early sign of the credit cycle turning |

## 6. Position management rules

- Size: decided separately, not published here.
- Add if: the price falls toward the 20% ROTE / 10.5% line of the table
  (~$279) with no change in core ROTCE or capital.
- Trim or exit if: any thesis-breaking condition in §4 occurs. After a
  material negative catalyst I write the decision down within 48 hours.
- Review cadence: quarterly and after each earnings release. The next
  one is 2026-10-13, two days after this pitch.

## 7. Sources

- JPMorgan Chase, Q2 2026 earnings release and supplement (Form 8-K,
  2026-07-14, accession 0001628280-26-048078).
- JPMorgan Chase, Form 10-Q for the quarter ended 2026-06-30 (filed
  2026-08-06, accession 0001628280-26-054343).
- JPMorgan Chase, press release on the dividend increase and $50B
  repurchase programme (Form 8-K, 2026-06-24, accession
  0001628280-26-045167).
- JPMorgan Chase, Form 8-K Item 5.02 on Co-Presidents and executive changes
  (2026-06-25, accession 0000019617-26-000241).
- SEC EDGAR XBRL company facts for JPM, BAC, WFC, C, GS and MS. Peer TTM
  ROTE and P/TBV were computed by the author with one method for all six,
  so they differ from each bank's reported figures. JPM's computed TBVPS is
  $112.27, against $113.35 reported. Citi's latest computed period is
  2025-12-31.
- Prices, dividends, earnings date and consensus: Yahoo Finance via
  yfinance, close of 2026-10-09.

---
*This document reflects personal research and is not investment advice.*
