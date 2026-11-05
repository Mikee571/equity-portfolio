"""Builds adobe_dcf.xlsx: a four-scenario DCF for Adobe (Nasdaq: ADBE) built around AI disruption, with live formulas.

The scenarios differ only in revenue growth, operating margin and terminal growth. Margin is after stock-based
compensation (SBC is treated as a cash cost by default; there is a switch).
Historical data: SEC XBRL company facts (data/adbe_annual_raw.csv, data/adbe_quarterly_raw.csv, built by extract.py).
Guidance: Q3 FY2026 press release (8-K, 2026-09-10). Market data and consensus: Yahoo Finance, close 2026-10-23.
Peers: TradingView, 2026-10-25 (data/peers_tradingview_20261025.csv).
Run: python build_model.py, then open in Excel (or recalculate) to cache values.
"""
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment

HERE = Path(__file__).parent
OUT = HERE / "adobe_dcf.xlsx"

BLUE, GREEN, BLACK = "0000FF", "008000", "000000"
YELLOW = PatternFill("solid", fgColor="FFFF00")
HEAD = PatternFill("solid", fgColor="DDE6F0")
USD = '#,##0;(#,##0);"-"'
USD2 = '$#,##0.00;($#,##0.00);"-"'
PCT = '0.0%;(0.0%);"-"'
MULT = '0.0"x"'
I = "Inputs!"
YEARS = list(range(2026, 2036))           # model columns C..L (fiscal years end late Nov / early Dec)
YC = [chr(ord("C") + i) for i in range(len(YEARS))]
COL = dict(zip(YEARS, YC))
NAMES = ("Bull", "Base", "Erosion", "Disruption")


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


A = pd.read_csv(HERE / "data" / "adbe_annual_raw.csv", index_col=0) / 1e6   # $mm (shares in mm)
Q = pd.read_csv(HERE / "data" / "adbe_quarterly_raw.csv", index_col=0) / 1e6
PEERS = pd.read_csv(HERE / "data" / "peers_tradingview_20261025.csv")

wb = Workbook()

# ---------------------------------------------------------------- Inputs
inp = wb.active
inp.title = "Inputs"
inp.column_dimensions["A"].width = 58
for c in YC + ["B", "M"]:
    inp.column_dimensions[c].width = 10
inp.column_dimensions["N"].width = 100
put(inp, "A1", "Adobe: inputs and scenario levers ($mm unless stated)", bold=True)
put(inp, "A2", "Blue = hardcoded input. Yellow = key assumption. Black = formula. Sources in column N.", italic=True)

cash_aug = Q.loc["2026-08-28", "Cash"] + Q.loc["2026-08-28", "ST_Inv"]
debt_aug = Q.loc["2026-08-28", "Debt_total"] + Q.loc["2026-08-28", "Debt_ST"]
ROWS = [
    (4, "Market data and capital structure", None, None, None),
    (5, "Share price ($)", 263.82, USD2, "Yahoo Finance, close 2026-10-23 (52-week range $190.12-363.70)"),
    (6, "Shares outstanding (mm)", 389.2, "0.0", "Yahoo Finance; 10-Q: 391.0mm at 2026-08-28; Q4 FY26 diluted count guided at ~389mm"),
    (7, "Cash and short-term investments at 28 Aug 2026", round(cash_aug), USD,
     "10-Q Q3 FY26: cash 4,359 + short-term investments 1,280"),
    (8, "Debt at 28 Aug 2026", round(debt_aug), USD, "10-Q Q3 FY26: long-term debt 4,766 + current portion 1,597"),
    (9, "Net cash / (net debt)", "=B7-B8", USD, "Formula"),
    (11, "Discount rate (same method as the Micron model)", None, None, None),
    (12, "Risk-free rate (US 10-year)", 0.0499, PCT, "^TNX close 2026-10-23: 4.99%"),
    (13, "Raw beta (5y monthly)", 1.415, "0.00", "Yahoo Finance"),
    (14, "Adjusted beta (Blume: 0.67 x raw + 0.33)", "=0.67*B13+0.33", "0.00", "Formula"),
    (15, "Equity risk premium", 0.05, PCT, "Assumption (author), as in the Micron model"),
    (16, "Cost of equity", "=B12+B14*B15", PCT, "CAPM"),
    (17, "Pre-tax cost of debt", 0.055, PCT, "Assumption: 10-year yield + ~50bp (A+ rated)"),
    (18, "Tax rate", 0.21, PCT, "FY26 guidance: GAAP ~22.5%, non-GAAP ~18%; FY25 cash taxes 2,219 on pretax 8,730 (25%)"),
    (19, "Market capitalisation", "=B5*B6", USD, "Formula"),
    (20, "WACC", "=(B19*B16+B8*B17*(1-B18))/(B19+B8)", PCT, "Formula, market-value weights"),
    (22, "Operating assumptions", None, None, None),
    (23, "FY2026 revenue", 26601, USD, "Q3 FY26 press release: FY26 target $26.576-26.626bn (midpoint); 9M actual 19,776"),
    (24, "FY2026 operating margin after SBC, before acquired-intangible amortisation", 0.37, PCT,
     "FY26 target non-GAAP op. margin ~45% less SBC ~8% of revenue; 9M GAAP 35.4% + amortisation 0.8%"),
    (25, "SBC as % of revenue", 0.08, PCT, "TTM to Q3 FY26: SBC 2,069 / revenue 25,970 = 8.0%"),
    (26, "Treat SBC as a cash cost (1 = yes, 0 = add it back)", 1, "0", "Author's choice: SBC is a real cost; buybacks spend ~$2bn a year offsetting it"),
    (27, "D&A as % of revenue", 0.01, PCT, "FY25 D&A 821 incl. 309 intangible amortisation; set equal to capex in steady state"),
    (28, "Capex as % of revenue", 0.01, PCT, "FY25 capex 179 (0.8%); 9M FY26 180 (0.9%)"),
    (29, "Working-capital inflow as % of revenue change", 0.15, PCT,
     "Deferred revenue rose 1,059 on +4,357 revenue FY23-25 (24%); haircut for other items. Reverses when revenue falls"),
    (30, "Q4 FY2026 free cash flow as share of FY2026 FCF", 0.25, PCT, "Cash generated after 28 Aug 2026, added to net cash"),
    (31, "FY2025 revenue", round(A.loc["FY2025", "Revenue"]), USD, "10-K FY2025"),
]
for r, label, val, fmt, src in ROWS:
    put(inp, f"A{r}", label, bold=val is None)
    if val is None:
        continue
    is_formula = isinstance(val, str) and val.startswith("=")
    put(inp, f"B{r}", val, BLACK if is_formula else BLUE, fmt)
    put(inp, f"N{r}", src, italic=True)
for r in (15, 24, 26):
    inp[f"B{r}"].fill = YELLOW

SCEN = {
    "Bull": dict(start=36, g=(0.11, 0.10, 0.07), m=(0.40, 0.42), tg=0.035,
                 story="AI expands the market: Firefly and agents bring in new users (1bn MAU), seats are repriced upwards, "
                       "CX/GenStudio wins enterprise content budgets. Growth holds at ~10% and margins rise."),
    "Base": dict(start=42, g=(0.091, 0.06, 0.04), m=(0.37, 0.37), tg=0.03,
                 story="Consensus FY27 (+9.1%), then a slow fade as Creative Cloud matures. AI adds features, not a new market; "
                       "inference costs offset efficiency, so margins stay flat."),
    "Erosion": dict(start=48, g=(0.07, 0.01, -0.01), m=(0.33, 0.30), tg=0.00,
                    story="AI commoditises the low end: casual and SMB users move to free or cheaper tools (Canva, Figma, "
                          "Google, OpenAI). Professionals stay, but price increases stop and seats slowly shrink."),
    "Disruption": dict(start=54, g=(0.03, -0.07, -0.05), m=(0.27, 0.22), tg=-0.02,
                       story="Generative models replace the workflow: most image/video/document work no longer needs "
                             "Adobe apps. Revenue falls ~30% from its peak by FY35 and keeps shrinking; margins compress "
                             "as fixed costs and AI compute stay."),
}
put(inp, "A34", "AI scenarios: revenue growth and operating margin (after SBC). Yellow = lever; years in between interpolate.",
    bold=True)
header_row(inp, 35, ["", ""] + [f"FY{y}" for y in YEARS])


def scenario_rows(start, g=None, m=None, tg=None, link_growth=None, flat_margin=None):
    """Writes one scenario block in Inputs: growth row (start+1), margin row (start+2), terminal growth (start+3)."""
    rg, rm, rt = start + 1, start + 2, start + 3
    put(inp, f"A{rg}", "  Revenue growth")
    put(inp, f"A{rm}", "  Operating margin (after SBC)")
    put(inp, f"A{rt}", "  Terminal growth (after FY2035)")
    put(inp, f"C{rg}", "=B23/B31-1", GREEN, PCT)
    put(inp, f"C{rm}", "=$B$24", GREEN, PCT)
    for k, y in enumerate(YEARS[1:], start=1):
        c = YC[k]
        if link_growth:
            put(inp, f"{c}{rg}", f"={c}{link_growth}", GREEN, PCT)
        elif y in (2027, 2031, 2035):
            put(inp, f"{c}{rg}", g[(2027, 2031, 2035).index(y)], BLUE, PCT, fill=YELLOW)
        else:
            a, b, n, j = ("D", "H", 4, y - 2027) if y < 2031 else ("H", "L", 4, y - 2031)
            put(inp, f"{c}{rg}", f"=${a}{rg}+(${b}{rg}-${a}{rg})*{j}/{n}", fmt=PCT)
        if flat_margin is not None:
            put(inp, f"{c}{rm}", flat_margin, BLUE, PCT)
        elif y in (2030, 2035):
            put(inp, f"{c}{rm}", m[(2030, 2035).index(y)], BLUE, PCT, fill=YELLOW)
        else:
            a, b, n, j = ("C", "G", 4, y - 2026) if y < 2030 else ("G", "L", 5, y - 2030)
            put(inp, f"{c}{rm}", f"=${a}{rm}+(${b}{rm}-${a}{rm})*{j}/{n}", fmt=PCT)
    if isinstance(tg, str):
        put(inp, f"C{rt}", tg, GREEN, PCT)
    else:
        put(inp, f"C{rt}", tg, BLUE, PCT, fill=YELLOW)


for name, s in SCEN.items():
    put(inp, f"A{s['start']}", f"{name} case", bold=True)
    put(inp, f"N{s['start']}", s["story"], italic=True)
    scenario_rows(s["start"], s["g"], s["m"], s["tg"])

# Reverse-DCF helpers: base revenue path, flat margin of 0% and 100% from FY2027 (value is linear in margin)
for name, start, m in (("Rev0", 60, 0.0), ("Rev1", 64, 1.0)):
    put(inp, f"A{start}", f"Reverse-DCF helper (base growth, margin = {m:.0%} from FY2027)", bold=True)
    scenario_rows(start, link_growth=SCEN["Base"]["start"] + 1, flat_margin=m, tg=f"=C{SCEN['Base']['start'] + 3}")
    SCEN[name] = dict(start=start)

put(inp, "A69", "Scenario probabilities", bold=True)
PROBS = dict(zip(NAMES, (0.20, 0.40, 0.25, 0.15)))
for k, name in enumerate(NAMES):
    put(inp, f"A{70 + k}", f"  {name}")
    put(inp, f"B{70 + k}", PROBS[name], BLUE, PCT, fill=YELLOW)
put(inp, "N70", "Author's judgement; this is the most subjective input in the model", italic=True)
put(inp, "A74", "  Check (must be 100%)")
put(inp, "B74", "=SUM(B70:B73)", fmt=PCT)

put(inp, "A76", "For reference", bold=True)
REF = [("Consensus revenue FY2026 / FY2027", 26607, 29038, USD, "Yahoo Finance analyst estimates, 2026-10-23 (35-37 analysts)"),
       ("Consensus non-GAAP EPS FY2026 / FY2027 ($)", 24.48, 27.51, USD2, "Same; FY26 company target $24.45-24.50"),
       ("Analyst price target mean / low / high ($)", 272.31, 195.0, USD2, "Yahoo Finance, 32 analysts; high $373"),
       ("Total ARR Q1 / Q3 FY2026", 26060, 27500, USD,
        "Press releases: Q2 27,100 incl. ~480 from Semrush (closed Q2); FY26 ending ARR growth target 10.2%"),
       ("AI-first ARR: Q2 FY26 (>$500mm, 'tripled') / Q3 growth", 500, 1.5, USD,
        "Press releases Q2 and Q3 FY26 (Q3: 'grew more than 150% year over year')")]
for k, (lab, a, b, fmt, src) in enumerate(REF):
    put(inp, f"A{77 + k}", f"  {lab}")
    put(inp, f"B{77 + k}", a, BLUE, fmt)
    put(inp, f"C{77 + k}", b, BLUE, PCT if k == 4 else fmt)
    put(inp, f"N{77 + k}", src, italic=True)
put(inp, "A83", "  Leadership: CFO Dan Durn resigned June 2026 (interim CFO Steve Day); Anil Chakravarthy becomes CEO on "
                "1 Dec 2026, Shantanu Narayen moves to executive chair; David Wadhwani (Creativity & Productivity) left Sept 2026.",
    italic=True)

# ---------------------------------------------------------------- Historical
his = wb.create_sheet("Historical")
his.column_dimensions["A"].width = 46
HY = [f"FY{y}" for y in range(2019, 2026)]
HC = [chr(ord("B") + i) for i in range(len(HY) + 2)]          # + 9M FY25, 9M FY26
for c in HC + ["K"]:
    his.column_dimensions[c].width = 11
put(his, "A1", "Adobe: historical figures ($mm)", bold=True)
put(his, "A2", "Source: SEC XBRL company facts (10-K and 10-Q), data/adbe_annual_raw.csv and adbe_quarterly_raw.csv. "
               "TTM = FY2025 - 9M FY25 + 9M FY26.", italic=True)
header_row(his, 4, ["$mm"] + HY + ["9M FY25", "9M FY26", "TTM"])
FIELDS = [("Revenue", "Revenue"), ("GAAP operating income", "OpIncome"), ("Amortisation of intangibles (opex)", "Amort_Intang"),
          ("Stock-based compensation", "SBC"), ("Net income", "NetIncome"), ("Cash flow from operations", "CFO"),
          ("Capex", "Capex"), ("Share repurchases", "Buybacks"), ("Diluted shares (mm)", "DilutedShares"),
          ("Deferred revenue (current)", "DeferredRevenue"), ("Remaining performance obligations", "RPO")]
HR = {}
for i, (lab, key) in enumerate(FIELDS):
    r = 5 + i
    HR[lab] = r
    put(his, f"A{r}", lab, bold=lab == "Revenue")
    vals = [A.loc[y, key] for y in HY] + [Q.loc["9M_2025-08-29", key] if key in Q and "9M_2025-08-29" in Q.index else None,
                                          Q.loc["9M_2026-08-28", key] if key in Q and "9M_2026-08-28" in Q.index else None]
    if key in ("DeferredRevenue", "RPO"):
        vals[-2:] = [Q.loc["2025-08-29", key], Q.loc["2026-08-28", key]]
    for c, v in zip(HC, vals):
        if v is not None and pd.notna(v):
            put(his, f"{c}{r}", round(float(v), 1), BLUE, "0.0" if "shares" in lab else USD)
    if key not in ("DilutedShares", "DeferredRevenue", "RPO"):
        put(his, f"K{r}", f"=H{r}-I{r}+J{r}", fmt=USD)
put(his, "K13", "=J13", fmt="0.0")
put(his, "K14", "=J14", fmt=USD)
put(his, "K15", "=J15", fmt=USD)
R = HR
DER = [("Revenue growth", lambda c, p: f"={c}{R['Revenue']}/{p}{R['Revenue']}-1" if p else None),
       ("GAAP operating margin", lambda c, p: f"={c}{R['GAAP operating income']}/{c}{R['Revenue']}"),
       ("Operating margin after SBC, before amortisation", lambda c, p: f"=({c}{R['GAAP operating income']}+{c}{R['Amortisation of intangibles (opex)']})/{c}{R['Revenue']}"),
       ("SBC as % of revenue", lambda c, p: f"={c}{R['Stock-based compensation']}/{c}{R['Revenue']}"),
       ("Free cash flow (CFO - capex)", lambda c, p: f"={c}{R['Cash flow from operations']}-{c}{R['Capex']}"),
       ("FCF after SBC", lambda c, p: f"={c}{R['Cash flow from operations']}-{c}{R['Capex']}-{c}{R['Stock-based compensation']}"),
       ("FCF after SBC as % of revenue", lambda c, p: f"=({c}{R['Cash flow from operations']}-{c}{R['Capex']}-{c}{R['Stock-based compensation']})/{c}{R['Revenue']}"),
       ("Buybacks as % of FCF", lambda c, p: f"={c}{R['Share repurchases']}/({c}{R['Cash flow from operations']}-{c}{R['Capex']})")]
for i, (lab, fn) in enumerate(DER):
    r = 17 + i
    put(his, f"A{r}", lab)
    for j, c in enumerate(HC + ["K"]):
        prev = {"C": "B", "D": "C", "E": "D", "F": "E", "G": "F", "H": "G", "J": "I"}.get(c)
        f = fn(c, prev)
        if f:
            put(his, f"{c}{r}", f, fmt=PCT if "%" in lab or "margin" in lab or "growth" in lab else USD)
put(his, "A26", "9M growth column J compares with 9M FY25 (column I). FY2020 net income includes a one-off tax benefit.",
    italic=True)

# ---------------------------------------------------------------- DCF
dcf = wb.create_sheet("DCF")
dcf.column_dimensions["A"].width = 46
dcf.column_dimensions["B"].width = 4
for c in YC + ["M"]:
    dcf.column_dimensions[c].width = 10
put(dcf, "A1", "DCF by scenario ($mm). Fiscal years end late November. Cash flows FY2027-35 discounted from end of FY2026; "
               "Q4 FY2026 cash flow added to net cash.", bold=True)
FLOW = ["Revenue", "Revenue growth", "Operating margin (after SBC)", "Operating income", "Taxes", "NOPAT",
        "+ SBC added back (if not treated as cash)", "+ D&A", "- Capex", "+ Working-capital inflow", "Free cash flow",
        "FCF margin", "Discount period (years)", "Discount factor", "PV of FCF"]
VAL = ["Terminal growth", "Terminal value at FY2035", "PV of terminal value", "Sum of PV of FCF (FY2027-35)",
       "Enterprise value", "+ Net cash at 28 Aug 2026", "+ Q4 FY2026 free cash flow", "Equity value",
       "Value per share ($)", "Upside / (downside) vs price", "Terminal value as % of EV",
       "Implied EV / FY2027 FCF", "Revenue CAGR FY2026-35", "FY2035 revenue vs FY2026"]
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
            put(dcf, f"{c}{rr['Revenue']}", f"={I}$B$23", GREEN, USD, bold=True)
        else:
            put(dcf, f"{c}{rr['Revenue']}", f"={prev}{rr['Revenue']}*(1+{c}{rr['Revenue growth']})", fmt=USD, bold=True)
        put(dcf, f"{c}{rr['Revenue growth']}", f"={I}{c}{sr + 1}", GREEN, PCT)
        put(dcf, f"{c}{rr['Operating margin (after SBC)']}", f"={I}{c}{sr + 2}", GREEN, PCT)
        put(dcf, f"{c}{rr['Operating income']}", f"={c}{rr['Revenue']}*{c}{rr['Operating margin (after SBC)']}", fmt=USD)
        put(dcf, f"{c}{rr['Taxes']}", f"=-{c}{rr['Operating income']}*{I}$B$18", fmt=USD)
        put(dcf, f"{c}{rr['NOPAT']}", f"={c}{rr['Operating income']}+{c}{rr['Taxes']}", fmt=USD)
        put(dcf, f"{c}{rr['+ SBC added back (if not treated as cash)']}",
            f"=(1-{I}$B$26)*{I}$B$25*{c}{rr['Revenue']}", fmt=USD)
        put(dcf, f"{c}{rr['+ D&A']}", f"={I}$B$27*{c}{rr['Revenue']}", fmt=USD)
        put(dcf, f"{c}{rr['- Capex']}", f"=-{I}$B$28*{c}{rr['Revenue']}", fmt=USD)
        prev_rev = f"{I}$B$31" if k == 0 else f"{prev}{rr['Revenue']}"
        put(dcf, f"{c}{rr['+ Working-capital inflow']}", f"={I}$B$29*({c}{rr['Revenue']}-{prev_rev})", fmt=USD)
        put(dcf, f"{c}{rr['Free cash flow']}",
            f"=SUM({c}{rr['NOPAT']}:{c}{rr['+ Working-capital inflow']})", fmt=USD, bold=True)
        put(dcf, f"{c}{rr['FCF margin']}", f"={c}{rr['Free cash flow']}/{c}{rr['Revenue']}", fmt=PCT)
        if k > 0:
            put(dcf, f"{c}{rr['Discount period (years)']}", k, BLUE, "0")
            put(dcf, f"{c}{rr['Discount factor']}", f"=1/(1+{I}$B$20)^{c}{rr['Discount period (years)']}", fmt="0.000")
            put(dcf, f"{c}{rr['PV of FCF']}", f"={c}{rr['Free cash flow']}*{c}{rr['Discount factor']}", fmt=USD)
    last, first = YC[-1], YC[0]
    v0 = top + 2 + len(FLOW) + 1
    vr = {lab: v0 + i for i, lab in enumerate(VAL)}
    for lab, r in vr.items():
        put(dcf, f"A{r}", lab, bold=lab in ("Enterprise value", "Equity value", "Value per share ($)"))
    put(dcf, f"C{vr['Terminal growth']}", f"={I}C{sr + 3}", GREEN, PCT)
    put(dcf, f"C{vr['Terminal value at FY2035']}",
        f"={last}{rr['Free cash flow']}*(1+C{vr['Terminal growth']})/({I}$B$20-C{vr['Terminal growth']})", fmt=USD)
    put(dcf, f"C{vr['PV of terminal value']}", f"=C{vr['Terminal value at FY2035']}*{last}{rr['Discount factor']}", fmt=USD)
    put(dcf, f"C{vr['Sum of PV of FCF (FY2027-35)']}", f"=SUM(D{rr['PV of FCF']}:{last}{rr['PV of FCF']})", fmt=USD)
    put(dcf, f"C{vr['Enterprise value']}",
        f"=C{vr['PV of terminal value']}+C{vr['Sum of PV of FCF (FY2027-35)']}", fmt=USD, bold=True)
    put(dcf, f"C{vr['+ Net cash at 28 Aug 2026']}", f"={I}$B$9", GREEN, USD)
    put(dcf, f"C{vr['+ Q4 FY2026 free cash flow']}", f"={first}{rr['Free cash flow']}*{I}$B$30", fmt=USD)
    put(dcf, f"C{vr['Equity value']}", f"=SUM(C{vr['Enterprise value']}:C{vr['+ Q4 FY2026 free cash flow']})", fmt=USD, bold=True)
    put(dcf, f"C{vr['Value per share ($)']}", f"=C{vr['Equity value']}/{I}$B$6", fmt=USD2, bold=True)
    put(dcf, f"C{vr['Upside / (downside) vs price']}", f"=C{vr['Value per share ($)']}/{I}$B$5-1", fmt=PCT)
    put(dcf, f"C{vr['Terminal value as % of EV']}", f"=C{vr['PV of terminal value']}/C{vr['Enterprise value']}", fmt=PCT)
    put(dcf, f"C{vr['Implied EV / FY2027 FCF']}", f"=({I}$B$19-{I}$B$9)/D{rr['Free cash flow']}", fmt=MULT)
    put(dcf, f"C{vr['Revenue CAGR FY2026-35']}", f"=({last}{rr['Revenue']}/{first}{rr['Revenue']})^(1/9)-1", fmt=PCT)
    put(dcf, f"C{vr['FY2035 revenue vs FY2026']}", f"={last}{rr['Revenue']}/{first}{rr['Revenue']}-1", fmt=PCT)
    BLOCK[name] = dict(rows=rr, vals=vr)
    return v0 + len(VAL) + 2


top = 3
for name in NAMES + ("Rev0", "Rev1"):
    if name == "Rev0":
        put(dcf, f"A{top}", "Helper blocks for the reverse DCF (base growth, flat margin of 0% and 100% from FY2027)", italic=True)
        top += 2
    top = block(name, top)

# ---------------------------------------------------------------- Reverse DCF
rev = wb.create_sheet("Reverse DCF")
rev.column_dimensions["A"].width = 58
for c in "BCDEFGHIJKL":
    rev.column_dimensions[c].width = 10
put(rev, "A1", "What do you have to believe at $263.82?", bold=True)
e0 = f"DCF!C{BLOCK['Rev0']['vals']['Equity value']}"
e1 = f"DCF!C{BLOCK['Rev1']['vals']['Equity value']}"
b = BLOCK["Base"]
put(rev, "A3", "1. Margin needed on the base revenue path", bold=True)
put(rev, "A4", "Target equity value (price x shares)")
put(rev, "C4", f"={I}B19", GREEN, USD)
put(rev, "A5", "Equity value with 0% margin from FY2027")
put(rev, "C5", f"={e0}", GREEN, USD)
put(rev, "A6", "Extra equity value per 100pp of margin")
put(rev, "C6", f"={e1}-{e0}", fmt=USD)
put(rev, "A7", "Flat operating margin FY2027 onwards that justifies the price", bold=True)
put(rev, "C7", "=(C4-C5)/C6", fmt=PCT, bold=True)
put(rev, "A8", "  FY2026 margin (after SBC)")
put(rev, "C8", f"={I}B24", GREEN, PCT)

put(rev, "A10", "2. Perpetual FCF growth the price implies (Gordon growth from FY2026 FCF, base case)", bold=True)
put(rev, "A11", "Enterprise value at market (market cap - net cash - Q4 FY26 FCF)")
put(rev, "C11", f"={I}B19-{I}B9-DCF!C{b['vals']['+ Q4 FY2026 free cash flow']}", fmt=USD)
put(rev, "A12", "FY2026 free cash flow (after SBC)")
put(rev, "C12", f"=DCF!C{b['rows']['Free cash flow']}", GREEN, USD)
put(rev, "A13", "FCF yield on enterprise value")
put(rev, "C13", "=C12/C11", fmt=PCT)
put(rev, "A14", "Implied perpetual FCF growth at the model WACC", bold=True)
put(rev, "C14", f"=(C11*{I}B20-C12)/(C11+C12)", fmt=PCT, bold=True)
put(rev, "A15", "  Same, with SBC added back to FCF")
put(rev, "C15", f"=(C11*{I}B20-(C12+{I}B25*{I}B23*{I}B26))/(C11+C12+{I}B25*{I}B23*{I}B26)", fmt=PCT)

# grids: constant revenue growth FY2027-35, flat margin; FCF_k = R0 (1+g)^k [m(1-t) + (1-T)s + da - cx + n g/(1+g)]
put(rev, "A17", "Discount periods (helper)")
for k in range(9):
    put(rev, f"{chr(ord('C') + k)}17", k + 1, BLUE, "0")
KS = "$C$17:$K$17"
TG = f"{I}$C${SCEN['Base']['start'] + 3}"


def grid_cell(g, m, w):
    gt = f"MIN({g},{TG})"
    x = f"({m}*(1-{I}$B$18)+(1-{I}$B$26)*{I}$B$25+{I}$B$27-{I}$B$28+{I}$B$29*{g}/(1+{g}))"
    q4 = f"DCF!$C${b['vals']['+ Q4 FY2026 free cash flow']}"
    return (f"=({I}$B$23*{x}*(SUMPRODUCT(((1+{g})/(1+{w}))^{KS})+(1+{g})^9*(1+{gt})/(({w}-{gt})*(1+{w})^9))"
            f"+{I}$B$9+{q4})/{I}$B$6")


put(rev, "A19", "3. Value per share ($): revenue CAGR FY2027-35 (rows) x flat operating margin (columns), model WACC", bold=True)
put(rev, "A20", "Terminal growth = the lower of the CAGR and the base-case 3%. Shaded: the price.", italic=True)
MARGINS = [0.22, 0.26, 0.30, 0.34, 0.37, 0.40, 0.44]
GROWTHS = [-0.06, -0.04, -0.02, 0.0, 0.02, 0.04, 0.06, 0.08, 0.10]
header_row(rev, 21, ["CAGR \\ margin", ""] + [""] * len(MARGINS))
for k, m in enumerate(MARGINS):
    put(rev, f"{chr(ord('C') + k)}21", m, BLUE, "0%", bold=True)
for i, g in enumerate(GROWTHS):
    r = 22 + i
    put(rev, f"A{r}", g, BLUE, PCT, bold=True)
    for k in range(len(MARGINS)):
        c = chr(ord("C") + k)
        put(rev, f"{c}{r}", grid_cell(f"$A{r}", f"{c}$21", f"{I}$B$20"), fmt="$#,##0")

put(rev, "A33", "4. Value per share ($): WACC (rows) x revenue CAGR FY2027-35 (columns), flat 37% margin", bold=True)
WACCS = [0.08, 0.09, 0.10, 0.11, 0.12]
G2 = [-0.04, -0.02, 0.0, 0.02, 0.04, 0.06, 0.08]
header_row(rev, 34, ["WACC \\ CAGR", ""] + [""] * len(G2))
for k, g in enumerate(G2):
    put(rev, f"{chr(ord('C') + k)}34", g, BLUE, "0%", bold=True)
for i, w in enumerate(WACCS):
    r = 35 + i
    put(rev, f"A{r}", w, BLUE, PCT, bold=True)
    for k in range(len(G2)):
        c = chr(ord("C") + k)
        put(rev, f"{c}{r}", grid_cell(f"{c}$34", "0.37", f"$A{r}"), fmt="$#,##0")
put(rev, "A41", "Current price ($)")
put(rev, "C41", f"={I}B5", GREEN, USD2)
put(rev, "A42", "Model WACC")
put(rev, "C42", f"={I}B20", GREEN, PCT)

# ---------------------------------------------------------------- Comps
cmp_ = wb.create_sheet("Comps")
cmp_.column_dimensions["A"].width = 34
for c in "BCDEFGHI":
    cmp_.column_dimensions[c].width = 12
put(cmp_, "A1", "Mature software peers (TradingView, 2026-10-25; trailing twelve months)", bold=True)
header_row(cmp_, 3, ["Company", "Mkt cap ($bn)", "P/E", "EV/EBITDA", "FCF yield", "ROIC", "Op. margin", "Revenue growth", "1-year return"])
for i, row in enumerate(PEERS.sort_values("market_cap_basic", ascending=False).itertuples()):
    r = 4 + i
    put(cmp_, f"A{r}", row.description, bold=row.ticker == "NASDAQ:ADBE")
    vals = [row.market_cap_basic / 1e9, row.price_earnings_ttm, row.enterprise_value_ebitda_ttm, row.fcf_y / 100,
            row.return_on_invested_capital_fq / 100, row.operating_margin_ttm / 100, row.total_revenue_yoy_growth_ttm / 100,
            row._11 / 100]
    for j, v in enumerate(vals):
        put(cmp_, f"{'BCDEFGHI'[j]}{r}", round(float(v), 4), BLUE, "#,##0" if j == 0 else (MULT if j in (1, 2) else PCT))
last_peer = 3 + len(PEERS)
put(cmp_, f"A{last_peer + 1}", "Median (all, incl. Adobe)", bold=True)
for j in range(1, 9):
    c = "BCDEFGHI"[j - 1]
    put(cmp_, f"{c}{last_peer + 1}", f"=MEDIAN({c}4:{c}{last_peer})", fmt="#,##0" if j == 1 else (MULT if j in (2, 3) else PCT))
put(cmp_, f"A{last_peer + 3}", "SAP market cap is in euros as reported by Xetra. Oracle FCF is negative because of AI data-centre capex.",
    italic=True)

# ---------------------------------------------------------------- Summary
sm = wb.create_sheet("Summary", 0)
sm.column_dimensions["A"].width = 50
for c in "BCDEF":
    sm.column_dimensions[c].width = 14
put(sm, "A1", "Adobe (ADBE): four-scenario DCF around AI disruption", bold=True)
put(sm, "A2", "Valuation date 2026-10-23. $mm unless stated. Change blue/yellow cells in 'Inputs'; everything else recalculates.",
    italic=True)
header_row(sm, 4, ["", *NAMES, "Prob.-weighted"])


def link(n, key, kind="vals", col="C"):
    return f"=DCF!{col}{BLOCK[n][kind][key]}"


SUMMARY = [("FY2027 revenue growth", lambda n: link(n, "Revenue growth", "rows", "D"), PCT),
           ("Revenue CAGR FY2026-35", lambda n: link(n, "Revenue CAGR FY2026-35"), PCT),
           ("FY2035 revenue", lambda n: link(n, "Revenue", "rows", "L"), USD),
           ("FY2030 operating margin (after SBC)", lambda n: link(n, "Operating margin (after SBC)", "rows", "G"), PCT),
           ("FY2035 operating margin (after SBC)", lambda n: link(n, "Operating margin (after SBC)", "rows", "L"), PCT),
           ("Enterprise value", lambda n: link(n, "Enterprise value"), USD),
           ("Value per share ($)", lambda n: link(n, "Value per share ($)"), USD2),
           ("Upside / (downside)", lambda n: link(n, "Upside / (downside) vs price"), PCT),
           ("Terminal value as % of EV", lambda n: link(n, "Terminal value as % of EV"), PCT),
           ("Probability", None, PCT)]
for i, (lab, fn, fmt) in enumerate(SUMMARY):
    r = 5 + i
    put(sm, f"A{r}", lab, bold=lab == "Value per share ($)")
    for k, n in enumerate(NAMES):
        put(sm, f"{'BCDE'[k]}{r}", fn(n) if fn else f"=Inputs!B{70 + k}", GREEN, fmt, bold=lab == "Value per share ($)")
put(sm, "F11", "=SUMPRODUCT(B11:E11,B14:E14)", fmt=USD2, bold=True)
put(sm, "F12", "=F11/Inputs!B5-1", fmt=PCT)
put(sm, "A16", "Current share price ($)")
put(sm, "B16", "=Inputs!B5", GREEN, USD2)
put(sm, "A17", "WACC")
put(sm, "B17", "=Inputs!B20", GREEN, PCT)
put(sm, "A18", "Flat margin from FY2027 needed to justify the price (base growth)", bold=True)
put(sm, "B18", "='Reverse DCF'!C7", GREEN, PCT, bold=True)
put(sm, "A19", "Perpetual FCF growth the price implies", bold=True)
put(sm, "B19", "='Reverse DCF'!C14", GREEN, PCT, bold=True)
put(sm, "A20", "Base FY2027 revenue vs consensus")
put(sm, "B20", f"=DCF!D{BLOCK['Base']['rows']['Revenue']}/Inputs!C77-1", fmt=PCT)
put(sm, "A21", "FY2026 FCF yield after SBC (base, on market cap)")
put(sm, "B21", f"=DCF!C{BLOCK['Base']['rows']['Free cash flow']}/Inputs!B19", fmt=PCT)
put(sm, "A23", "Legend: blue = input, black = formula, green = link to another sheet, yellow = key assumption.", italic=True)
put(sm, "A24", "Sources: SEC 10-K FY2025, 10-Qs and 8-Ks FY2026; Yahoo Finance 2026-10-23; TradingView 2026-10-25.", italic=True)
put(sm, "A25", "Personal research, not investment advice.", italic=True)

for ws in wb.worksheets:
    ws.sheet_view.showGridLines = False
wb.save(OUT)
print("saved", OUT)
