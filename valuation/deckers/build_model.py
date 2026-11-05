"""Builds deckers_dcf.xlsx: a four-scenario DCF for Deckers Brands (NYSE: DECK) driven by HOKA and UGG, with live formulas.

Revenue is built by brand (HOKA, UGG, Other). The scenarios differ only in HOKA growth, UGG growth, operating margin
and terminal growth. Fiscal years end 31 March. FY2027 is the company's own guidance (Q2 FY27 release, 2026-10-22).
Historical data: SEC XBRL company facts (data/deck_annual_raw.csv, data/deck_quarterly_raw.csv, built by extract.py);
brand revenue from the 10-Ks for FY2022, FY2024 and FY2026 and the Q2 FY27 10-Q (data/filings/).
Market data and consensus: Yahoo Finance, close 2026-10-30. Peers: Yahoo Finance, 2026-11-02 (data/peers_yahoo_20261102.csv).
Run: python build_model.py, then open in Excel (or recalculate) to cache values.
"""
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

HERE = Path(__file__).parent
OUT = HERE / "deckers_dcf.xlsx"

BLUE, GREEN, BLACK = "0000FF", "008000", "000000"
YELLOW = PatternFill("solid", fgColor="FFFF00")
HEAD = PatternFill("solid", fgColor="DDE6F0")
USD = '#,##0;(#,##0);"-"'
USD2 = '$#,##0.00;($#,##0.00);"-"'
PCT = '0.0%;(0.0%);"-"'
MULT = '0.0"x"'
I = "Inputs!"
YEARS = list(range(2027, 2037))           # model columns C..L (fiscal years end 31 March)
YC = [chr(ord("C") + i) for i in range(len(YEARS))]
COL = dict(zip(YEARS, YC))
NAMES = ("Bull", "Base", "Fade", "Bust")


def font(color=BLACK, bold=False, italic=False):
    return Font(name="Arial", size=10, color=color, bold=bold, italic=italic)


def put(ws, ref, value, color=BLACK, fmt=None, bold=False, fill=None, italic=False):
    c = ws[ref]
    c.value = value
    c.font = font(color, bold, italic)
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    return c


def header_row(ws, row, labels, first_col=1):
    for j, lab in enumerate(labels):
        c = ws.cell(row=row, column=first_col + j, value=lab)
        c.font = font(bold=True)
        c.fill = HEAD
        c.alignment = Alignment(horizontal="left" if j == 0 else "center")


A = pd.read_csv(HERE / "data" / "deck_annual_raw.csv", index_col=0) / 1e6   # $mm (shares in mm)
Q = pd.read_csv(HERE / "data" / "deck_quarterly_raw.csv", index_col=0) / 1e6
PEERS = pd.read_csv(HERE / "data" / "peers_yahoo_20261102.csv").dropna(subset=["market_cap"])

# Brand net sales ($mm), not in the XBRL company facts (they are dimensional). Sources: 10-K FY2022 (FY21-22),
# 10-K FY2024 (FY23-24), 10-K FY2026 (FY25-26), 10-Q Q2 FY27 (six months to September).
BRANDS = {
    "HOKA": {"FY2021": 571.2, "FY2022": 891.6, "FY2023": 1412.9, "FY2024": 1806.7, "FY2025": 2233.1, "FY2026": 2587.3,
             "6M FY26": 1287.2, "6M FY27": 1380.7},
    "UGG": {"FY2021": 1717.1, "FY2022": 1982.0, "FY2023": 1929.2, "FY2024": 2239.1, "FY2025": 2531.4, "FY2026": 2738.8,
            "6M FY26": 1024.7, "6M FY27": 1064.4},
}
h1_fcf = Q.loc["6M_2026-09-30", "CFO"] - Q.loc["6M_2026-09-30", "Capex"]

wb = Workbook()

# ---------------------------------------------------------------- Inputs
inp = wb.active
inp.title = "Inputs"
inp.column_dimensions["A"].width = 58
for c in YC + ["B", "M"]:
    inp.column_dimensions[c].width = 10
inp.column_dimensions["N"].width = 100
put(inp, "A1", "Deckers: inputs and scenario levers ($mm unless stated)", bold=True)
put(inp, "A2", "Blue = hardcoded input. Yellow = key assumption. Black = formula. Sources in column N.", italic=True)

ROWS = [
    (4, "Market data and capital structure", None, None, None),
    (5, "Share price ($)", 81.99, USD2, "Yahoo Finance, close 2026-10-30 (52-week range $77.20-122.29)"),
    (6, "Shares outstanding (mm)", 133.5, "0.0", "10-Q Q2 FY27 cover: 133,479,987 at 2026-10-08; dilutive awards add only ~0.3mm"),
    (7, "Cash at 30 Sep 2026", round(Q.loc["2026-09-30", "Cash"], 1), USD,
     "10-Q Q2 FY27. Seasonal low: inventory peaks before the UGG holiday season (cash was 1,907 at 31 March)"),
    (8, "Debt at 30 Sep 2026", 0, USD, "No borrowings; $500mm revolver undrawn (amended 2026-08-27). Lease liabilities (540) are "
                                       "treated as operating: rent is inside operating income"),
    (9, "Net cash / (net debt)", "=B7-B8", USD, "Formula"),
    (11, "Discount rate (same method as the Micron and Adobe models)", None, None, None),
    (12, "Risk-free rate (US 10-year)", 0.0493, PCT, "^TNX close 2026-10-30: 4.93%"),
    (13, "Raw beta (5y monthly)", 1.106, "0.00", "Yahoo Finance"),
    (14, "Adjusted beta (Blume: 0.67 x raw + 0.33)", "=0.67*B13+0.33", "0.00", "Formula"),
    (15, "Equity risk premium", 0.05, PCT, "Assumption (author), as in the Micron and Adobe models"),
    (16, "Cost of equity", "=B12+B14*B15", PCT, "CAPM"),
    (17, "Pre-tax cost of debt", 0.06, PCT, "Not used while debt is zero; revolver at SOFR + 1.00-1.50%"),
    (18, "Tax rate", 0.23, PCT, "FY27 guidance: effective tax rate ~23%; FY26 actual 302 on 1,326 pretax (22.8%)"),
    (19, "Market capitalisation", "=B5*B6", USD, "Formula"),
    (20, "WACC", "=(B19*B16+B8*B17*(1-B18))/(B19+B8)", PCT, "Formula, market-value weights (all equity)"),
    (22, "Operating assumptions", None, None, None),
    (23, "FY2027 revenue", 5712.5, USD, "Q2 FY27 release: FY27 net sales $5.700-5.725bn (midpoint); 6M actual 2,500"),
    (24, "FY2027 operating margin (GAAP, as guided)", 0.23, PCT,
     "Q2 FY27 release: ~23%, incl. ~150bp from IEEPA tariff refunds received through 8 Oct 2026 (one-off)"),
    (25, "  of which one-off tariff refunds", 0.015, PCT, "Q2 FY27 release, note (2): $87.9mm refunds + $4.7mm interest"),
    (26, "  FY2027 underlying operating margin", "=B24-B25", PCT, "Formula. FY26 was 23.1%, FY25 23.6%"),
    (27, "D&A as % of revenue", 0.014, PCT, "FY26 D&A 76 on revenue 5,472 (1.4%)"),
    (28, "Capex as % of revenue", 0.016, PCT, "FY26 capex 85 (1.6%); FY24-25 1.7-2.1%"),
    (29, "Working-capital investment as % of revenue change", 0.08, PCT,
     "Receivables + inventory - payables at 31 March: 7.7% of revenue FY26, 8.2% FY25, 9.1% FY24"),
    (30, "H1 FY2027 free cash flow (actual)", round(h1_fcf, 1), USD,
     "10-Q Q2 FY27: CFO (9.3) - capex 37.2. H2 is where the cash comes in (UGG season)"),
    (31, "FY2026 revenue", round(A.loc["FY2026", "Revenue"], 1), USD, "10-K FY2026"),
    (32, "  HOKA FY2026", BRANDS["HOKA"]["FY2026"], USD, "10-K FY2026, net sales by brand"),
    (33, "  UGG FY2026", BRANDS["UGG"]["FY2026"], USD, "10-K FY2026"),
    (34, "  Other brands FY2026", "=B31-B32-B33", USD, "Formula (Teva, plus Koolaburra and AHNU being phased out)"),
    (35, "HOKA growth FY2027", 0.08, PCT, "Guidance: 'high-single-digit'; 6M +7.3%"),
    (36, "UGG growth FY2027", 0.03, PCT, "Guidance: 'low-single-digit'; 6M +3.9%"),
    (37, "Other brands growth FY2027 (balancing item)", "=(B23-B32*(1+B35)-B33*(1+B36))/B34-1", PCT,
     "Formula: whatever reconciles to guided revenue; 6M Other brands 55 vs 84 last year (-34%)"),
    (38, "Other brands growth from FY2028", 0.0, PCT, "Assumption: Teva flat"),
    (39, "Months from valuation date to 31 Mar 2027", 5, "0", "Valuation date 30 Oct 2026; FY2028+ cash flows discounted "
                                                          "to 31 Mar 2027, then back to today"),
]
for r, label, val, fmt, src in ROWS:
    put(inp, f"A{r}", label, bold=val is None)
    if val is None:
        continue
    is_formula = isinstance(val, str) and val.startswith("=")
    put(inp, f"B{r}", val, BLACK if is_formula else BLUE, fmt)
    put(inp, f"N{r}", src, italic=True)
for r in (15, 25, 29):
    inp[f"B{r}"].fill = YELLOW

# growth levers at FY28, FY32, FY36; margin levers at FY28, FY31, FY36
SCEN = {
    "Bull": dict(start=44, h=(0.13, 0.10, 0.05), u=(0.05, 0.03, 0.02), m=(0.225, 0.24, 0.24), tg=0.035,
                 story="HOKA becomes a global top-3 running brand: international and DTC keep compounding at double digits "
                       "into the 2030s, UGG keeps winning new categories. Operating leverage takes margins back above FY25."),
    "Base": dict(start=50, h=(0.09, 0.06, 0.04), u=(0.03, 0.02, 0.02), m=(0.215, 0.215, 0.21), tg=0.03,
                 story="Consensus for FY28 (+5.8%), then a slow fade. HOKA grows like a mature premium brand, UGG grows with "
                       "the market. Tariffs keep margins ~1.5pp below FY26, with no recovery."),
    "Fade": dict(start=56, h=(0.05, 0.03, 0.02), u=(-0.03, -0.02, 0.0), m=(0.20, 0.18, 0.17), tg=0.02,
                 story="The UGG fashion cycle ends: wholesale demand rolls over and DTC keeps shrinking, as in FY2015-17. "
                       "HOKA loses share to On, Asics and others in the US and becomes a normal running brand. "
                       "Promotions and deleverage take margins back to the FY22-23 level."),
    "Bust": dict(start=62, h=(0.0, -0.02, 0.01), u=(-0.10, -0.04, 0.0), m=(0.18, 0.14, 0.13), tg=0.01,
                 story="Both brands go out of fashion at once: UGG falls ~30% from its peak by FY32, HOKA stalls and shrinks "
                       "in the US. Margins fall towards the pre-HOKA level (FY17-18: 0-12% GAAP)."),
}
put(inp, "A42", "Scenarios: brand growth and operating margin. Yellow = lever; years in between interpolate.", bold=True)
header_row(inp, 43, ["", ""] + [f"FY{y}" for y in YEARS])


def scenario_rows(start, h=None, u=None, m=None, tg=None, link_growth=None, flat_margin=None):
    """Writes one scenario block: HOKA growth (start+1), UGG growth (start+2), margin (start+3), terminal growth (start+4)."""
    rh, ru, rm, rt = start + 1, start + 2, start + 3, start + 4
    put(inp, f"A{rh}", "  HOKA revenue growth")
    put(inp, f"A{ru}", "  UGG revenue growth")
    put(inp, f"A{rm}", "  Operating margin")
    put(inp, f"A{rt}", "  Terminal growth (after FY2036)")
    put(inp, f"C{rh}", "=$B$35", GREEN, PCT)
    put(inp, f"C{ru}", "=$B$36", GREEN, PCT)
    put(inp, f"C{rm}", "=$B$24", GREEN, PCT)
    for k, y in enumerate(YEARS[1:], start=1):
        c = YC[k]
        for row, path in ((rh, h), (ru, u)):
            if link_growth:
                put(inp, f"{c}{row}", f"={c}{link_growth + row - start - 1}", GREEN, PCT)
            elif y in (2028, 2032, 2036):
                put(inp, f"{c}{row}", path[(2028, 2032, 2036).index(y)], BLUE, PCT, fill=YELLOW)
            else:
                a, b, j = ("D", "H", y - 2028) if y < 2032 else ("H", "L", y - 2032)
                put(inp, f"{c}{row}", f"=${a}{row}+(${b}{row}-${a}{row})*{j}/4", fmt=PCT)
        if flat_margin is not None:
            put(inp, f"{c}{rm}", flat_margin, BLUE, PCT)
        elif y in (2028, 2031, 2036):
            put(inp, f"{c}{rm}", m[(2028, 2031, 2036).index(y)], BLUE, PCT, fill=YELLOW)
        else:
            a, b, n, j = ("D", "G", 3, y - 2028) if y < 2031 else ("G", "L", 5, y - 2031)
            put(inp, f"{c}{rm}", f"=${a}{rm}+(${b}{rm}-${a}{rm})*{j}/{n}", fmt=PCT)
    if isinstance(tg, str):
        put(inp, f"C{rt}", tg, GREEN, PCT)
    else:
        put(inp, f"C{rt}", tg, BLUE, PCT, fill=YELLOW)


for name, s in SCEN.items():
    put(inp, f"A{s['start']}", f"{name} case", bold=True)
    put(inp, f"N{s['start']}", s["story"], italic=True)
    scenario_rows(s["start"], s["h"], s["u"], s["m"], s["tg"])

# Reverse-DCF helpers: base brand paths, flat margin of 0% and 100% from FY2028 (value is linear in margin)
BASE = SCEN["Base"]["start"]
for name, start, m in (("Rev0", 68, 0.0), ("Rev1", 74, 1.0)):
    put(inp, f"A{start}", f"Reverse-DCF helper (base growth, margin = {m:.0%} from FY2028)", bold=True)
    scenario_rows(start, link_growth=BASE + 1, flat_margin=m, tg=f"=C{BASE + 4}")
    SCEN[name] = dict(start=start)

put(inp, "A80", "Scenario probabilities", bold=True)
PROBS = dict(zip(NAMES, (0.20, 0.45, 0.25, 0.10)))
for k, name in enumerate(NAMES):
    put(inp, f"A{81 + k}", f"  {name}")
    put(inp, f"B{81 + k}", PROBS[name], BLUE, PCT, fill=YELLOW)
put(inp, "N81", "Author's judgement; this is the most subjective input in the model", italic=True)
put(inp, "A85", "  Check (must be 100%)")
put(inp, "B85", "=SUM(B81:B84)", fmt=PCT)

put(inp, "A87", "For reference", bold=True)
REF = [("Consensus revenue FY2027 / FY2028", 5709, 6041, USD, "Yahoo Finance analyst estimates, 2026-11-02 (21 analysts)"),
       ("Consensus EPS FY2027 / FY2028 ($)", 7.86, 8.11, USD2,
        "Same. FY27 guidance $7.80-7.95 includes ~$0.52 of tariff refunds, so FY28 growth is ~10% underlying"),
       ("Analyst price target mean / low ($)", 96.74, 70.0, USD2, "Yahoo Finance, 21 analysts; high $137, median $95; consensus 'hold'"),
       ("Buybacks FY2027 guided / done in H1 ($mm)", 1000, 637.5, USD,
        "Q2 FY27 release: 6.5mm shares at $98.77 average in H1; $4.4bn authorisation left"),
       ("HOKA / UGG growth Q2 FY27 (yoy)", 0.068, 0.035, PCT,
        "Q2 FY27 release. DTC comparable sales -6.4%; US -0.4%, international +9.0%")]
for k, (lab, a, b, fmt, src) in enumerate(REF):
    put(inp, f"A{88 + k}", f"  {lab}")
    put(inp, f"B{88 + k}", a, BLUE, fmt)
    put(inp, f"C{88 + k}", b, BLUE, fmt)
    put(inp, f"N{88 + k}", src, italic=True)

# ---------------------------------------------------------------- Historical
his = wb.create_sheet("Historical")
his.column_dimensions["A"].width = 46
HY = [f"FY{y}" for y in range(2021, 2027)]
HC = [chr(ord("B") + i) for i in range(len(HY) + 2)]          # + 6M FY26, 6M FY27
for c in HC + ["J"]:
    his.column_dimensions[c].width = 11
put(his, "A1", "Deckers: historical figures ($mm; fiscal years end 31 March)", bold=True)
put(his, "A2", "Source: SEC XBRL company facts (10-K and 10-Q), data/deck_annual_raw.csv and deck_quarterly_raw.csv; brand "
               "sales from the 10-Ks and 10-Q. TTM = FY2026 - 6M FY26 + 6M FY27.", italic=True)
header_row(his, 4, ["$mm"] + HY + ["6M FY26", "6M FY27", "TTM"])
FIELDS = [("Revenue", "Revenue"), ("  HOKA", None), ("  UGG", None), ("  Other brands", None), ("Cost of sales", "COGS"),
          ("Operating income", "OpIncome"), ("Advertising and marketing", "Advertising"), ("Stock-based compensation", "SBC"),
          ("Net income", "NetIncome"), ("Cash flow from operations", "CFO"), ("Capex", "Capex"), ("Share repurchases", "Buybacks"),
          ("Diluted shares (mm, split-adjusted)", "DilutedShares"), ("Net working capital at period end", None)]
HR = {}
SIX = {"6M FY26": ("6M_2025-09-30", "2025-09-30"), "6M FY27": ("6M_2026-09-30", "2026-09-30")}
for i, (lab, key) in enumerate(FIELDS):
    r = 5 + i
    HR[lab] = r
    put(his, f"A{r}", lab, bold=lab == "Revenue")
    for c, y in zip(HC, HY + list(SIX)):
        if lab.strip() in BRANDS:
            v = BRANDS[lab.strip()][y]
        elif lab == "  Other brands":
            put(his, f"{c}{r}", f"={c}5-{c}6-{c}7", fmt=USD)
            continue
        elif lab.startswith("Net working capital"):
            src, idx = (A, y) if y in HY else (Q, SIX[y][1])
            v = src.loc[idx, "Receivables"] + src.loc[idx, "Inventory"] - src.loc[idx, "Payables"]
        elif y in HY:
            v = A.loc[y, key]
            if key == "DilutedShares" and y in ("FY2021", "FY2022"):
                v *= 6                                            # 6-for-1 split in September 2024
        else:
            v = Q.loc[SIX[y][0], key]
        if pd.notna(v):
            put(his, f"{c}{r}", round(float(v), 1), BLUE, "0.0" if "shares" in lab else USD)
    if key not in ("DilutedShares",) and not lab.startswith("Net working"):
        put(his, f"J{r}", f"=G{r}-H{r}+I{r}", fmt=USD)
put(his, f"J{HR['Diluted shares (mm, split-adjusted)']}", f"=I{HR['Diluted shares (mm, split-adjusted)']}", fmt="0.0")
R = HR
PREV = {"C": "B", "D": "C", "E": "D", "F": "E", "G": "F", "I": "H"}
DER = [("Revenue growth", lambda c, p: f"={c}{R['Revenue']}/{p}{R['Revenue']}-1" if p else None),
       ("HOKA growth", lambda c, p: f"={c}{R['  HOKA']}/{p}{R['  HOKA']}-1" if p else None),
       ("UGG growth", lambda c, p: f"={c}{R['  UGG']}/{p}{R['  UGG']}-1" if p else None),
       ("HOKA as % of revenue", lambda c, p: f"={c}{R['  HOKA']}/{c}{R['Revenue']}"),
       ("Gross margin", lambda c, p: f"=1-{c}{R['Cost of sales']}/{c}{R['Revenue']}"),
       ("Operating margin", lambda c, p: f"={c}{R['Operating income']}/{c}{R['Revenue']}"),
       ("Advertising as % of revenue", lambda c, p: f"={c}{R['Advertising and marketing']}/{c}{R['Revenue']}"),
       ("Free cash flow (CFO - capex)", lambda c, p: f"={c}{R['Cash flow from operations']}-{c}{R['Capex']}"),
       ("FCF margin", lambda c, p: f"=({c}{R['Cash flow from operations']}-{c}{R['Capex']})/{c}{R['Revenue']}"),
       ("Buybacks as % of FCF", lambda c, p: f"={c}{R['Share repurchases']}/({c}{R['Cash flow from operations']}-{c}{R['Capex']})"),
       ("Net working capital as % of revenue (year-end)", lambda c, p: f"={c}{R['Net working capital at period end']}/{c}{R['Revenue']}" if c <= "G" else None)]
for i, (lab, fn) in enumerate(DER):
    r = 20 + i
    put(his, f"A{r}", lab)
    for c in HC + ["J"]:
        if c == "J" and ("growth" in lab or "working" in lab):
            continue
        f = fn(c, PREV.get(c))
        if f:
            put(his, f"{c}{r}", f, fmt=PCT if "%" in lab or "margin" in lab or "growth" in lab else USD)
put(his, "A32", "6M growth columns compare with 6M FY26 (column H). FY2023 operating margin was hit by freight costs; "
                "6M FY27 includes $46mm of tariff refunds in cost of sales. Working capital is seasonal: it peaks in September.",
    italic=True)

# ---------------------------------------------------------------- DCF
dcf = wb.create_sheet("DCF")
dcf.column_dimensions["A"].width = 46
dcf.column_dimensions["B"].width = 4
for c in YC + ["M"]:
    dcf.column_dimensions[c].width = 10
put(dcf, "A1", "DCF by scenario ($mm). Fiscal years end 31 March. FY2028-36 cash flows discounted to 31 Mar 2027; that value "
               "plus H2 FY2027 FCF is then discounted 5 months to today. Net cash added at face value.", bold=True)
FLOW = ["HOKA revenue", "UGG revenue", "Other brands revenue", "Revenue", "Revenue growth", "HOKA growth", "UGG growth",
        "HOKA as % of revenue", "Operating margin", "Operating income", "Taxes", "NOPAT", "+ D&A", "- Capex",
        "- Working-capital investment", "Free cash flow", "FCF margin", "Discount period (years from 31 Mar 2027)",
        "Discount factor", "PV of FCF"]
VAL = ["Terminal growth", "Terminal value at FY2036", "PV of terminal value", "Sum of PV of FCF (FY2028-36)",
       "Enterprise value at 31 Mar 2027", "+ H2 FY2027 free cash flow", "Discount factor to today", "+ Net cash at 30 Sep 2026",
       "Equity value today", "Value per share ($)", "Upside / (downside) vs price", "Terminal value as % of EV",
       "Market EV / FY2028 FCF", "Revenue CAGR FY2027-36", "HOKA revenue CAGR FY2027-36", "UGG revenue CAGR FY2027-36"]
BLOCK = {}


def block(name, top):
    sr = SCEN[name]["start"]
    put(dcf, f"A{top}", f"{name} case", bold=True)
    header_row(dcf, top + 1, ["$mm", ""] + [f"FY{y}" for y in YEARS])
    rr = {lab: top + 2 + i for i, lab in enumerate(FLOW)}
    for lab, r in rr.items():
        put(dcf, f"A{r}", lab, bold=lab in ("Revenue", "Free cash flow"))
    for k, y in enumerate(YEARS):
        c = COL[y]
        prev = YC[k - 1] if k else None
        if k == 0:
            put(dcf, f"{c}{rr['HOKA revenue']}", f"={I}$B$32*(1+{c}{rr['HOKA growth']})", fmt=USD)
            put(dcf, f"{c}{rr['UGG revenue']}", f"={I}$B$33*(1+{c}{rr['UGG growth']})", fmt=USD)
            put(dcf, f"{c}{rr['Other brands revenue']}", f"={I}$B$34*(1+{I}$B$37)", fmt=USD)
        else:
            put(dcf, f"{c}{rr['HOKA revenue']}", f"={prev}{rr['HOKA revenue']}*(1+{c}{rr['HOKA growth']})", fmt=USD)
            put(dcf, f"{c}{rr['UGG revenue']}", f"={prev}{rr['UGG revenue']}*(1+{c}{rr['UGG growth']})", fmt=USD)
            put(dcf, f"{c}{rr['Other brands revenue']}", f"={prev}{rr['Other brands revenue']}*(1+{I}$B$38)", fmt=USD)
        put(dcf, f"{c}{rr['Revenue']}", f"=SUM({c}{rr['HOKA revenue']}:{c}{rr['Other brands revenue']})", fmt=USD, bold=True)
        prev_rev = f"{I}$B$31" if k == 0 else f"{prev}{rr['Revenue']}"
        put(dcf, f"{c}{rr['Revenue growth']}", f"={c}{rr['Revenue']}/{prev_rev}-1", fmt=PCT)
        put(dcf, f"{c}{rr['HOKA growth']}", f"={I}{c}{sr + 1}", GREEN, PCT)
        put(dcf, f"{c}{rr['UGG growth']}", f"={I}{c}{sr + 2}", GREEN, PCT)
        put(dcf, f"{c}{rr['HOKA as % of revenue']}", f"={c}{rr['HOKA revenue']}/{c}{rr['Revenue']}", fmt=PCT)
        put(dcf, f"{c}{rr['Operating margin']}", f"={I}{c}{sr + 3}", GREEN, PCT)
        put(dcf, f"{c}{rr['Operating income']}", f"={c}{rr['Revenue']}*{c}{rr['Operating margin']}", fmt=USD)
        put(dcf, f"{c}{rr['Taxes']}", f"=-{c}{rr['Operating income']}*{I}$B$18", fmt=USD)
        put(dcf, f"{c}{rr['NOPAT']}", f"={c}{rr['Operating income']}+{c}{rr['Taxes']}", fmt=USD)
        put(dcf, f"{c}{rr['+ D&A']}", f"={I}$B$27*{c}{rr['Revenue']}", fmt=USD)
        put(dcf, f"{c}{rr['- Capex']}", f"=-{I}$B$28*{c}{rr['Revenue']}", fmt=USD)
        put(dcf, f"{c}{rr['- Working-capital investment']}", f"=-{I}$B$29*({c}{rr['Revenue']}-{prev_rev})", fmt=USD)
        put(dcf, f"{c}{rr['Free cash flow']}",
            f"=SUM({c}{rr['NOPAT']}:{c}{rr['- Working-capital investment']})", fmt=USD, bold=True)
        put(dcf, f"{c}{rr['FCF margin']}", f"={c}{rr['Free cash flow']}/{c}{rr['Revenue']}", fmt=PCT)
        if k > 0:
            put(dcf, f"{c}{rr['Discount period (years from 31 Mar 2027)']}", k, BLUE, "0")
            put(dcf, f"{c}{rr['Discount factor']}",
                f"=1/(1+{I}$B$20)^{c}{rr['Discount period (years from 31 Mar 2027)']}", fmt="0.000")
            put(dcf, f"{c}{rr['PV of FCF']}", f"={c}{rr['Free cash flow']}*{c}{rr['Discount factor']}", fmt=USD)
    last, first = YC[-1], YC[0]
    v0 = top + 2 + len(FLOW) + 1
    vr = {lab: v0 + i for i, lab in enumerate(VAL)}
    for lab, r in vr.items():
        put(dcf, f"A{r}", lab, bold=lab in ("Enterprise value at 31 Mar 2027", "Equity value today", "Value per share ($)"))
    put(dcf, f"C{vr['Terminal growth']}", f"={I}C{sr + 4}", GREEN, PCT)
    put(dcf, f"C{vr['Terminal value at FY2036']}",
        f"={last}{rr['Free cash flow']}*(1+C{vr['Terminal growth']})/({I}$B$20-C{vr['Terminal growth']})", fmt=USD)
    put(dcf, f"C{vr['PV of terminal value']}", f"=C{vr['Terminal value at FY2036']}*{last}{rr['Discount factor']}", fmt=USD)
    put(dcf, f"C{vr['Sum of PV of FCF (FY2028-36)']}", f"=SUM(D{rr['PV of FCF']}:{last}{rr['PV of FCF']})", fmt=USD)
    put(dcf, f"C{vr['Enterprise value at 31 Mar 2027']}",
        f"=C{vr['PV of terminal value']}+C{vr['Sum of PV of FCF (FY2028-36)']}", fmt=USD, bold=True)
    put(dcf, f"C{vr['+ H2 FY2027 free cash flow']}", f"={first}{rr['Free cash flow']}-{I}$B$30", fmt=USD)
    put(dcf, f"C{vr['Discount factor to today']}", f"=1/(1+{I}$B$20)^({I}$B$39/12)", fmt="0.000")
    put(dcf, f"C{vr['+ Net cash at 30 Sep 2026']}", f"={I}$B$9", GREEN, USD)
    put(dcf, f"C{vr['Equity value today']}",
        f"=(C{vr['Enterprise value at 31 Mar 2027']}+C{vr['+ H2 FY2027 free cash flow']})*C{vr['Discount factor to today']}"
        f"+C{vr['+ Net cash at 30 Sep 2026']}", fmt=USD, bold=True)
    put(dcf, f"C{vr['Value per share ($)']}", f"=C{vr['Equity value today']}/{I}$B$6", fmt=USD2, bold=True)
    put(dcf, f"C{vr['Upside / (downside) vs price']}", f"=C{vr['Value per share ($)']}/{I}$B$5-1", fmt=PCT)
    put(dcf, f"C{vr['Terminal value as % of EV']}",
        f"=C{vr['PV of terminal value']}/C{vr['Enterprise value at 31 Mar 2027']}", fmt=PCT)
    put(dcf, f"C{vr['Market EV / FY2028 FCF']}", f"=({I}$B$19-{I}$B$9)/D{rr['Free cash flow']}", fmt=MULT)
    put(dcf, f"C{vr['Revenue CAGR FY2027-36']}", f"=({last}{rr['Revenue']}/{first}{rr['Revenue']})^(1/9)-1", fmt=PCT)
    put(dcf, f"C{vr['HOKA revenue CAGR FY2027-36']}",
        f"=({last}{rr['HOKA revenue']}/{first}{rr['HOKA revenue']})^(1/9)-1", fmt=PCT)
    put(dcf, f"C{vr['UGG revenue CAGR FY2027-36']}",
        f"=({last}{rr['UGG revenue']}/{first}{rr['UGG revenue']})^(1/9)-1", fmt=PCT)
    BLOCK[name] = dict(rows=rr, vals=vr)
    return v0 + len(VAL) + 2


top = 3
for name in NAMES + ("Rev0", "Rev1"):
    if name == "Rev0":
        put(dcf, f"A{top}", "Helper blocks for the reverse DCF (base growth, flat margin of 0% and 100% from FY2028)", italic=True)
        top += 2
    top = block(name, top)

# ---------------------------------------------------------------- Reverse DCF
rev = wb.create_sheet("Reverse DCF")
rev.column_dimensions["A"].width = 58
for c in "BCDEFGHIJKL":
    rev.column_dimensions[c].width = 10
put(rev, "A1", "What do you have to believe at $81.99?", bold=True)
e0 = f"DCF!C{BLOCK['Rev0']['vals']['Equity value today']}"
e1 = f"DCF!C{BLOCK['Rev1']['vals']['Equity value today']}"
b = BLOCK["Base"]
put(rev, "A3", "1. Margin needed on the base revenue path", bold=True)
put(rev, "A4", "Target equity value (price x shares)")
put(rev, "C4", f"={I}B19", GREEN, USD)
put(rev, "A5", "Equity value with 0% margin from FY2028")
put(rev, "C5", f"={e0}", GREEN, USD)
put(rev, "A6", "Extra equity value per 100pp of margin")
put(rev, "C6", f"={e1}-{e0}", fmt=USD)
put(rev, "A7", "Flat operating margin FY2028 onwards that justifies the price", bold=True)
put(rev, "C7", "=(C4-C5)/C6", fmt=PCT, bold=True)
put(rev, "A8", "  FY2027 underlying margin (guided, ex tariff refunds)")
put(rev, "C8", f"={I}B26", GREEN, PCT)

put(rev, "A10", "2. Perpetual FCF growth the price implies (Gordon growth on base FY2028 FCF)", bold=True)
put(rev, "A11", "Enterprise value at market, rolled to 31 Mar 2027 (less H2 FY27 FCF)")
put(rev, "C11", f"=({I}B19-{I}B9)/DCF!C{b['vals']['Discount factor to today']}-DCF!C{b['vals']['+ H2 FY2027 free cash flow']}",
    fmt=USD)
put(rev, "A12", "FY2028 free cash flow (base)")
put(rev, "C12", f"=DCF!D{b['rows']['Free cash flow']}", GREEN, USD)
put(rev, "A13", "FCF yield on enterprise value")
put(rev, "C13", "=C12/C11", fmt=PCT)
put(rev, "A14", "Implied perpetual FCF growth at the model WACC", bold=True)
put(rev, "C14", f"={I}B20-C13", fmt=PCT, bold=True)

# Grids: HOKA and UGG grow at constant rates from FY2028, Other brands as in Inputs, flat margin.
# PV(FCF_1..9) = sum over brands of B0 * SP(a) * (x - n*g/(1+g)), SP(a) = sum_k (a/(1+w))^k, x = m(1-t) + da - capex.
# FCF_9 = sum over brands of B0 * a^9 * (x - n*g/(1+g)); terminal growth = min(base, revenue growth in FY2036).
put(rev, "A16", "Discount periods (helper)")
for k in range(9):
    put(rev, f"{chr(ord('C') + k)}16", k + 1, BLUE, "0")
KS = "$C$16:$K$16"
TG = f"{I}$C${BASE + 4}"
H0, U0, O0 = (f"DCF!$C${b['rows'][r]}" for r in ("HOKA revenue", "UGG revenue", "Other brands revenue"))
GO = f"{I}$B$38"


def grid_cell(gh, gu, m, w):
    x = f"({m}*(1-{I}$B$18)+{I}$B$27-{I}$B$28)"
    brands = ((H0, gh), (U0, gu), (O0, GO))
    pv = "+".join(f"{b0}*SUMPRODUCT(((1+{g})/(1+{w}))^{KS})*({x}-{I}$B$29*{g}/(1+{g}))" for b0, g in brands)
    f9 = "+".join(f"{b0}*(1+{g})^9*({x}-{I}$B$29*{g}/(1+{g}))" for b0, g in brands)
    r9 = "+".join(f"{b0}*(1+{g})^9" for b0, g in brands)
    r8 = "+".join(f"{b0}*(1+{g})^8" for b0, g in brands)
    gt = f"MIN({TG},({r9})/({r8})-1)"
    h2 = f"DCF!$C${b['vals']['+ H2 FY2027 free cash flow']}"
    return (f"=((({pv})+({f9})*(1+{gt})/(({w}-{gt})*(1+{w})^9)+{h2})/(1+{w})^({I}$B$39/12)+{I}$B$9)/{I}$B$6")


BASE_M = f"{I}$D${BASE + 3}"
put(rev, "A18", "3. Value per share ($): UGG revenue CAGR FY2028-36 (rows) x HOKA revenue CAGR (columns)", bold=True)
put(rev, "A19", "Base FY2028 margin held flat, model WACC. Terminal growth = the lower of base 3% and FY2036 revenue growth.",
    italic=True)
HG = [-0.02, 0.0, 0.02, 0.04, 0.06, 0.08, 0.10, 0.12]
UG = [-0.08, -0.06, -0.04, -0.02, 0.0, 0.02, 0.04]
header_row(rev, 20, ["UGG \\ HOKA", ""] + [""] * len(HG))
for k, g in enumerate(HG):
    put(rev, f"{chr(ord('C') + k)}20", g, BLUE, "0%", bold=True)
for i, g in enumerate(UG):
    r = 21 + i
    put(rev, f"A{r}", g, BLUE, PCT, bold=True)
    for k in range(len(HG)):
        c = chr(ord("C") + k)
        put(rev, f"{c}{r}", grid_cell(f"{c}$20", f"$A{r}", BASE_M, f"{I}$B$20"), fmt="$#,##0")

put(rev, "A30", "4. Value per share ($): flat operating margin (rows) x revenue CAGR FY2028-36, both brands (columns)", bold=True)
MARGINS = [0.13, 0.15, 0.17, 0.19, 0.215, 0.23, 0.25]
G2 = [-0.04, -0.02, 0.0, 0.02, 0.04, 0.06, 0.08]
header_row(rev, 31, ["Margin \\ CAGR", ""] + [""] * len(G2))
for k, g in enumerate(G2):
    put(rev, f"{chr(ord('C') + k)}31", g, BLUE, "0%", bold=True)
for i, m in enumerate(MARGINS):
    r = 32 + i
    put(rev, f"A{r}", m, BLUE, PCT, bold=True)
    for k in range(len(G2)):
        c = chr(ord("C") + k)
        put(rev, f"{c}{r}", grid_cell(f"{c}$31", f"{c}$31", f"$A{r}", f"{I}$B$20"), fmt="$#,##0")

put(rev, "A40", "5. Value per share ($): WACC (rows) x revenue CAGR FY2028-36, both brands (columns), base FY2028 margin", bold=True)
WACCS = [0.08, 0.09, 0.10, 0.11, 0.12]
header_row(rev, 41, ["WACC \\ CAGR", ""] + [""] * len(G2))
for k, g in enumerate(G2):
    put(rev, f"{chr(ord('C') + k)}41", g, BLUE, "0%", bold=True)
for i, w in enumerate(WACCS):
    r = 42 + i
    put(rev, f"A{r}", w, BLUE, PCT, bold=True)
    for k in range(len(G2)):
        c = chr(ord("C") + k)
        put(rev, f"{c}{r}", grid_cell(f"{c}$41", f"{c}$41", BASE_M, f"$A{r}"), fmt="$#,##0")
put(rev, "A48", "Current price ($)")
put(rev, "C48", f"={I}B5", GREEN, USD2)
put(rev, "A49", "Model WACC")
put(rev, "C49", f"={I}B20", GREEN, PCT)

# ---------------------------------------------------------------- Comps
cmp_ = wb.create_sheet("Comps")
cmp_.column_dimensions["A"].width = 30
for c in "BCDEFGHIJ":
    cmp_.column_dimensions[c].width = 12
put(cmp_, "A1", "Footwear and apparel peers (Yahoo Finance, 2026-11-02; trailing twelve months unless stated)", bold=True)
header_row(cmp_, 3, ["Company", "Currency", "Mkt cap (bn)", "P/E", "Forward P/E", "EV/EBITDA", "Op. margin",
                     "Revenue growth (last qtr)", "FCF yield", "1-year return"])
COLS = ["market_cap", "pe_ttm", "pe_fwd", "ev_ebitda", "op_margin", "rev_growth", "fcf_yield", "ret_52w"]
for i, row in enumerate(PEERS.itertuples()):
    r = 4 + i
    put(cmp_, f"A{r}", row.name.split("  ")[0].strip(), bold=row.ticker == "DECK")
    put(cmp_, f"B{r}", row.currency, BLUE)
    for j, col in enumerate(COLS):
        v = getattr(row, col)
        if pd.isna(v) or (col == "ev_ebitda" and v < 0):
            continue
        v = v / 1e9 if col == "market_cap" else v
        put(cmp_, f"{'CDEFGHIJ'[j]}{r}", round(float(v), 4), BLUE, "#,##0" if j == 0 else (MULT if j in (1, 2, 3) else PCT))
last_peer = 3 + len(PEERS)
put(cmp_, f"A{last_peer + 1}", "Median (all, incl. Deckers)", bold=True)
for j in range(1, 8):
    c = "CDEFGHIJ"[j]
    put(cmp_, f"{c}{last_peer + 1}", f"=MEDIAN({c}4:{c}{last_peer})", fmt=MULT if j in (1, 2, 3) else PCT)
put(cmp_, f"A{last_peer + 3}", "Market caps in local currency (Asics in yen). Puma is loss-making, so P/E and EV/EBITDA are blank. "
                               "Skechers was taken private in 2025.", italic=True)

# ---------------------------------------------------------------- Summary
sm = wb.create_sheet("Summary", 0)
sm.column_dimensions["A"].width = 50
for c in "BCDEF":
    sm.column_dimensions[c].width = 14
put(sm, "A1", "Deckers (DECK): four-scenario DCF driven by HOKA and UGG", bold=True)
put(sm, "A2", "Valuation date 2026-10-30. $mm unless stated. Change blue/yellow cells in 'Inputs'; everything else recalculates.",
    italic=True)
header_row(sm, 4, ["", *NAMES, "Prob.-weighted"])


def link(n, key, kind="vals", col="C"):
    return f"=DCF!{col}{BLOCK[n][kind][key]}"


SUMMARY = [("FY2028 revenue growth", lambda n: link(n, "Revenue growth", "rows", "D"), PCT),
           ("HOKA revenue CAGR FY2027-36", lambda n: link(n, "HOKA revenue CAGR FY2027-36"), PCT),
           ("UGG revenue CAGR FY2027-36", lambda n: link(n, "UGG revenue CAGR FY2027-36"), PCT),
           ("FY2036 revenue", lambda n: link(n, "Revenue", "rows", "L"), USD),
           ("FY2031 operating margin", lambda n: link(n, "Operating margin", "rows", "G"), PCT),
           ("FY2036 operating margin", lambda n: link(n, "Operating margin", "rows", "L"), PCT),
           ("Enterprise value at 31 Mar 2027", lambda n: link(n, "Enterprise value at 31 Mar 2027"), USD),
           ("Value per share ($)", lambda n: link(n, "Value per share ($)"), USD2),
           ("Upside / (downside)", lambda n: link(n, "Upside / (downside) vs price"), PCT),
           ("Terminal value as % of EV", lambda n: link(n, "Terminal value as % of EV"), PCT),
           ("Probability", None, PCT)]
for i, (lab, fn, fmt) in enumerate(SUMMARY):
    r = 5 + i
    put(sm, f"A{r}", lab, bold=lab == "Value per share ($)")
    for k, n in enumerate(NAMES):
        put(sm, f"{'BCDE'[k]}{r}", fn(n) if fn else f"=Inputs!B{81 + k}", GREEN, fmt, bold=lab == "Value per share ($)")
put(sm, "F12", "=SUMPRODUCT(B12:E12,B15:E15)", fmt=USD2, bold=True)
put(sm, "F13", "=F12/Inputs!B5-1", fmt=PCT)
put(sm, "A17", "Current share price ($)")
put(sm, "B17", "=Inputs!B5", GREEN, USD2)
put(sm, "A18", "WACC")
put(sm, "B18", "=Inputs!B20", GREEN, PCT)
put(sm, "A19", "Flat margin from FY2028 needed to justify the price (base growth)", bold=True)
put(sm, "B19", "='Reverse DCF'!C7", GREEN, PCT, bold=True)
put(sm, "A20", "Perpetual FCF growth the price implies", bold=True)
put(sm, "B20", "='Reverse DCF'!C14", GREEN, PCT, bold=True)
put(sm, "A21", "Base FY2028 revenue vs consensus")
put(sm, "B21", f"=DCF!D{BLOCK['Base']['rows']['Revenue']}/Inputs!C88-1", fmt=PCT)
put(sm, "A22", "Base FY2028 FCF yield on market cap")
put(sm, "B22", f"=DCF!D{BLOCK['Base']['rows']['Free cash flow']}/Inputs!B19", fmt=PCT)
put(sm, "A24", "Legend: blue = input, black = formula, green = link to another sheet, yellow = key assumption.", italic=True)
put(sm, "A25", "Sources: SEC 10-Ks FY2022/24/26, 10-Q and 8-K Q2 FY2027; Yahoo Finance 2026-10-30 and 2026-11-02.", italic=True)
put(sm, "A26", "Personal research, not investment advice.", italic=True)

for ws in wb.worksheets:
    ws.sheet_view.showGridLines = False
wb.save(OUT)
print("saved", OUT)
