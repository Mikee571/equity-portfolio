"""Builds micron_dcf.xlsx: a three-scenario DCF for Micron Technology (MU) with live Excel formulas.

Historical data: SEC XBRL company facts (data/mu_annual_raw.csv; revenue FY14-16 from tag SalesRevenueNet).
Market data: Yahoo Finance, close of 2026-10-16. Every hardcoded input carries its source in the sheet.
Run: python build_model.py, then recalculate (open in Excel, or LibreOffice headless) to cache values.
"""
from pathlib import Path
import pandas as pd
from openpyxl import Workbook
from openpyxl.styles import Font, PatternFill, Alignment
from openpyxl.comments import Comment

HERE = Path(__file__).parent
OUT = HERE / "micron_dcf.xlsx"

BLUE, GREEN, BLACK = "0000FF", "008000", "000000"
YELLOW = PatternFill("solid", fgColor="FFFF00")
HEAD = PatternFill("solid", fgColor="DDE6F0")
USD = '#,##0;(#,##0);"-"'
USD2 = '$#,##0.00;($#,##0.00);"-"'
PCT = '0.0%;(0.0%);"-"'
MULT = '0.0"x"'
I = "Inputs!"


def font(color=BLACK, bold=False, italic=False):
    return Font(name="Arial", size=10, color=color, bold=bold, italic=italic)


def put(ws, ref, value, color=BLACK, fmt=None, bold=False, fill=None, note=None, italic=False):
    c = ws[ref]
    c.value = value
    c.font = font(color, bold, italic)
    if fmt:
        c.number_format = fmt
    if fill:
        c.fill = fill
    if note:
        c.comment = Comment(note, "MR")
    return c


def header_row(ws, row, labels):
    for j, lab in enumerate(labels):
        c = ws.cell(row=row, column=1 + j, value=lab)
        c.font = font(bold=True)
        c.fill = HEAD
        c.alignment = Alignment(horizontal="left" if j == 0 else "center")


wb = Workbook()

# ---------------------------------------------------------------- Inputs
inp = wb.active
inp.title = "Inputs"
inp.column_dimensions["A"].width = 48
for col in "BCDEFGH":
    inp.column_dimensions[col].width = 12
inp.column_dimensions["I"].width = 90
put(inp, "A1", "Micron Technology (MU): inputs and scenario levers ($mm unless stated)", bold=True)
put(inp, "A2", "Blue = hardcoded input. Yellow = key assumption. Black = formula. Sources in column I.", italic=True)

ROWS = [
    (4, "Market data and capital structure", None, None, None),
    (5, "Share price ($)", 878.84, USD2, "Yahoo Finance, close 2026-10-16"),
    (6, "Diluted shares (mm)", 1147, USD, "FQ4-26 GAAP net income $37,701mm / diluted EPS $32.87 (8-K exhibit 99.1, 2026-09-30)"),
    (7, "Cash, marketable investments and restricted cash", 73480, USD, "FY26 earnings release (8-K exhibit 99.1, 2026-09-30)"),
    (8, "Debt (notes)", 2792, USD, "10-K FY26, XBRL LongTermDebt at 2026-09-03"),
    (9, "Finance lease liabilities", 2387, USD, "10-K FY26, XBRL FinanceLeaseLiability at 2026-09-03"),
    (10, "Customer contract liability deposits", 12747, USD, "FY26 cash flow: proceeds from customer contract liability deposits (Strategic Customer Agreements)"),
    (11, "Treat customer deposits as debt? (1 = yes, 0 = no)", 1, "0", "Prepayments settled in future product; debt-like by default (conservative)"),
    (13, "Discount rate", None, None, None),
    (14, "Risk-free rate (US 10-year)", 0.051, PCT, "^TNX close 2026-10-16: 5.10%"),
    (15, "Raw beta (5y monthly)", 2.23, "0.00", "Yahoo Finance"),
    (16, "Adjusted beta (Blume: 0.67 x raw + 0.33)", "=0.67*B15+0.33", "0.00", "Formula"),
    (17, "Equity risk premium", 0.05, PCT, "Assumption (author)"),
    (18, "Cost of equity", "=B14+B16*B17", PCT, "CAPM"),
    (19, "Pre-tax cost of debt", 0.055, PCT, "Assumption: 10-year yield + ~40bp (investment grade)"),
    (20, "Tax rate", 0.15, PCT, "FY26 effective rate 14.8% (tax $14,761mm / pretax $99,671mm, 10-K)"),
    (21, "Market capitalisation", "=B5*B6", USD, "Formula"),
    (22, "Debt incl. finance leases", "=B8+B9", USD, "Formula"),
    (23, "WACC", "=(B21*B18+B22*B19*(1-B20))/(B21+B22)", PCT, "Formula, market-value weights"),
    (25, "Operating and terminal assumptions", None, None, None),
    (26, "Terminal growth", 0.03, PCT, "Assumption: roughly nominal GDP"),
    (27, "Return on new invested capital (terminal)", 0.15, PCT, "Assumption: terminal reinvestment rate = g / RONIC"),
    (28, "Change in NWC as % of change in revenue", 0.10, PCT, "Assumption (inventory + receivables, net of payables)"),
    (29, "D&A catch-up to prior-year capex (per year)", 0.20, PCT, "Assumption: D&A(t) = D&A(t-1) + 20% x (Capex(t-1) - D&A(t-1))"),
    (30, "FY26 revenue", 133188, USD, "10-K FY26"),
    (31, "FY26 D&A", 9503, USD, "10-K FY26 cash flow statement"),
    (32, "FY26 capex, net", 27370, USD, "FY26 earnings release: investments in capital expenditures, net $27.37bn"),
]
for r, label, val, fmt, src in ROWS:
    put(inp, f"A{r}", label, bold=val is None)
    if val is None:
        continue
    is_formula = isinstance(val, str) and val.startswith("=")
    put(inp, f"B{r}", val, BLACK if is_formula else BLUE, fmt)
    put(inp, f"I{r}", src, italic=True)
for r in (11, 17, 26, 27):
    inp[f"B{r}"].fill = YELLOW

SCEN = {
    "Bear": dict(start=37, growth=[0.60, -0.45, -0.35, 0.05, 0.08], margin=[0.72, 0.35, 0.10, 0.15, 0.20],
                 capex=[45000, 30000, 20000, 20000, 21000], norm=0.20,
                 story="FY27 at the lowest analyst estimate, then a 2023-style bust. Normalised margin ~ FY15-25 through-cycle average."),
    "Base": dict(start=43, growth=[1.07, 0.16, -0.25, -0.30, -0.10], margin=[0.80, 0.75, 0.55, 0.40, 0.35],
                 capex=[50000, 60000, 50000, 45000, 42000], norm=0.35,
                 story="Consensus for FY27-28, then the cycle turns; margins normalise above history (35%) thanks to HBM mix."),
    "Bull": dict(start=49, growth=[1.15, 0.25, 0.05, -0.05, 0.03], margin=[0.82, 0.80, 0.70, 0.60, 0.50],
                 capex=[55000, 70000, 70000, 65000, 65000], norm=0.50,
                 story="Above consensus and no real downturn: memory stops behaving like a commodity; margins settle at 50%."),
}
put(inp, "A34", "Scenarios (fiscal years end in early September)", bold=True)
header_row(inp, 35, ["", "", "FY2027", "FY2028", "FY2029", "FY2030", "FY2031"])
for name, s in SCEN.items():
    r = s["start"]
    put(inp, f"A{r}", f"{name} case", bold=True)
    put(inp, f"I{r}", s["story"], italic=True)
    put(inp, f"A{r+1}", "  Revenue growth")
    put(inp, f"A{r+2}", "  Operating margin")
    put(inp, f"A{r+3}", "  Capex, net ($mm)")
    put(inp, f"A{r+4}", "  Normalised (terminal) operating margin")
    for j, col in enumerate("CDEFG"):
        put(inp, f"{col}{r+1}", s["growth"][j], BLUE, PCT)
        put(inp, f"{col}{r+2}", s["margin"][j], BLUE, PCT)
        put(inp, f"{col}{r+3}", s["capex"][j], BLUE, USD)
    put(inp, f"C{r+4}", s["norm"], BLUE, PCT, fill=YELLOW)
put(inp, "I38", "Consensus (Yahoo Finance, 2026-10-16): FY27 revenue $275.5bn (+107%, low $212.4bn), FY28 $318.9bn (+16%, low $224.2bn).", italic=True)
put(inp, "I44", "FY27 Q1 guidance: revenue $61.5bn +/- 1.5bn, gross margin ~86% (8-K 2026-09-30).", italic=True)
put(inp, "A61", "Analyst consensus for reference ($mm)", bold=True)
for k, (lab, v) in enumerate([("FY2027 revenue", 275505), ("FY2028 revenue", 318882), ("FY2027 EPS ($)", 176.55), ("FY2028 EPS ($)", 206.89)]):
    put(inp, f"A{62+k}", f"  {lab}")
    put(inp, f"B{62+k}", v, BLUE, USD2 if "EPS" in lab else USD)
put(inp, "I62", "Yahoo Finance analyst estimates, 2026-10-16 (35-36 analysts)", italic=True)
put(inp, "A55", "Scenario probabilities", bold=True)
for k, (name, p) in enumerate([("Bear", 0.30), ("Base", 0.50), ("Bull", 0.20)]):
    put(inp, f"A{56+k}", f"  {name}")
    put(inp, f"B{56+k}", p, BLUE, PCT, fill=YELLOW)
put(inp, "I56", "Author's judgement; change freely", italic=True)
put(inp, "A59", "  Check (must be 100%)")
put(inp, "B59", "=SUM(B56:B58)", fmt=PCT)

# ---------------------------------------------------------------- Historical
his = wb.create_sheet("Historical")
raw = pd.read_csv(HERE / "data" / "mu_annual_raw.csv", index_col=0) / 1e6
raw.loc[["FY2014", "FY2015", "FY2016"], "Revenue"] = [16358, 16192, 12399]  # $mm, XBRL tag SalesRevenueNet
years = [f"FY{y}" for y in range(2014, 2027)]
cols = [chr(ord("B") + i) for i in range(len(years))]
his.column_dimensions["A"].width = 34
for c in cols:
    his.column_dimensions[c].width = 10
put(his, "A1", "Micron: historical financials ($mm). Fiscal years end late August / early September.", bold=True)
put(his, "A2", "Source: SEC EDGAR XBRL company facts (10-K filings), CIK 0000723125.", italic=True)
header_row(his, 4, ["$mm"] + [y[2:] for y in years])
LINES = [("Revenue", "Revenue"), ("Cost of goods sold", "COGS"), ("Gross profit", None), ("R&D", "R&D"),
         ("SG&A", "SG&A"), ("Operating income", "OpIncome"), ("Net income", "NetIncome"), ("D&A", "D&A"),
         ("Stock-based compensation", "SBC"), ("Cash from operations", "CFO"), ("Capex (PP&E purchases)", "Capex"),
         ("Free cash flow (CFO - capex)", None), ("Diluted shares (mm)", "DilutedShares"), ("Diluted EPS ($)", None),
         ("", None), ("Gross margin", None), ("Operating margin", None), ("FCF margin", None), ("Capex / revenue", None)]
R = {label: 5 + i for i, (label, _) in enumerate(LINES)}
for label, _ in LINES:
    put(his, f"A{R[label]}", label, bold=label in ("Revenue", "Operating income", "Free cash flow (CFO - capex)"))
for j, y in enumerate(years):
    c = cols[j]
    for label, key in LINES:
        if key and y in raw.index and pd.notna(raw.loc[y, key]):
            put(his, f"{c}{R[label]}", round(float(raw.loc[y, key]), 1), BLUE, USD)
    rv, cfo, cap = R["Revenue"], R["Cash from operations"], R["Capex (PP&E purchases)"]
    fcf = R["Free cash flow (CFO - capex)"]
    put(his, f"{c}{R['Gross profit']}", f"={c}{rv}-{c}{R['Cost of goods sold']}", fmt=USD)
    put(his, f"{c}{fcf}", f'=IF({c}{cfo}="","",{c}{cfo}-{c}{cap})', fmt=USD)
    put(his, f"{c}{R['Diluted EPS ($)']}", f"={c}{R['Net income']}/{c}{R['Diluted shares (mm)']}", fmt=USD2)
    put(his, f"{c}{R['Gross margin']}", f"={c}{R['Gross profit']}/{c}{rv}", fmt=PCT)
    put(his, f"{c}{R['Operating margin']}", f"={c}{R['Operating income']}/{c}{rv}", fmt=PCT)
    put(his, f"{c}{R['FCF margin']}", f'=IF({c}{fcf}="","",{c}{fcf}/{c}{rv})', fmt=PCT)
    put(his, f"{c}{R['Capex / revenue']}", f"={c}{cap}/{c}{rv}", fmt=PCT)
om = R["Operating margin"]
put(his, "A26", "Operating margin through the cycle, FY15-FY25", bold=True)
put(his, "A27", "  Average")
put(his, "B27", f"=AVERAGE(C{om}:M{om})", fmt=PCT)
put(his, "A28", "  Minimum")
put(his, "B28", f"=MIN(C{om}:M{om})", fmt=PCT)
put(his, "A29", "  Maximum")
put(his, "B29", f"=MAX(C{om}:M{om})", fmt=PCT)
put(his, "A30", "  FY26 (this cycle)")
put(his, "B30", f"=N{om}", fmt=PCT)

# ---------------------------------------------------------------- DCF
dcf = wb.create_sheet("DCF")
dcf.column_dimensions["A"].width = 42
for c in "BCDEFGH":
    dcf.column_dimensions[c].width = 12
put(dcf, "A1", "DCF by scenario ($mm). End-of-year discounting from the start of FY27 (September 2026).", bold=True)
BLOCK = {}
FLOW = ["Revenue", "  growth", "Operating margin", "EBIT", "Taxes", "NOPAT", "D&A", "Capex, net", "Change in NWC",
        "Free cash flow", "Discount period (years)", "Discount factor", "PV of FCF"]
VAL = ["Normalised operating margin", "Terminal NOPAT (FY2032)", "Terminal reinvestment rate (g / RONIC)",
       "Terminal FCF (FY2032)", "Terminal value at FY2031", "PV of terminal value", "Sum of PV of FCF (FY27-31)",
       "Enterprise value", "+ Cash and investments", "- Debt and finance leases",
       "- Customer deposits (if treated as debt)", "Equity value", "Value per share ($)",
       "Upside / (downside) vs price", "Terminal value as % of EV", "Implied EV / FY2027 EBIT"]


def block(name, top):
    s = SCEN[name]
    sr = s["start"]
    put(dcf, f"A{top}", f"{name} case", bold=True)
    header_row(dcf, top + 1, ["$mm", "", "FY2026A", "FY2027", "FY2028", "FY2029", "FY2030", "FY2031"])
    rr = {lab: top + 2 + i for i, lab in enumerate(FLOW)}
    for lab, r in rr.items():
        put(dcf, f"A{r}", lab, bold=lab in ("Revenue", "Free cash flow"))
    put(dcf, f"C{rr['Revenue']}", f"={I}$B$30", GREEN, USD)
    put(dcf, f"C{rr['EBIT']}", f"=Historical!N{R['Operating income']}", GREEN, USD)
    put(dcf, f"C{rr['Operating margin']}", f"=C{rr['EBIT']}/C{rr['Revenue']}", fmt=PCT)
    put(dcf, f"C{rr['D&A']}", f"={I}$B$31", GREEN, USD)
    put(dcf, f"C{rr['Capex, net']}", f"={I}$B$32", GREEN, USD)
    for j, c in enumerate("DEFGH"):
        p = chr(ord(c) - 1)
        sc = "CDEFG"[j]
        put(dcf, f"{c}{rr['  growth']}", f"={I}{sc}{sr+1}", GREEN, PCT)
        put(dcf, f"{c}{rr['Revenue']}", f"={p}{rr['Revenue']}*(1+{c}{rr['  growth']})", fmt=USD)
        put(dcf, f"{c}{rr['Operating margin']}", f"={I}{sc}{sr+2}", GREEN, PCT)
        put(dcf, f"{c}{rr['EBIT']}", f"={c}{rr['Revenue']}*{c}{rr['Operating margin']}", fmt=USD)
        put(dcf, f"{c}{rr['Taxes']}", f"=-{c}{rr['EBIT']}*{I}$B$20", fmt=USD)
        put(dcf, f"{c}{rr['NOPAT']}", f"={c}{rr['EBIT']}+{c}{rr['Taxes']}", fmt=USD)
        put(dcf, f"{c}{rr['D&A']}", f"={p}{rr['D&A']}+{I}$B$29*({p}{rr['Capex, net']}-{p}{rr['D&A']})", fmt=USD)
        put(dcf, f"{c}{rr['Capex, net']}", f"={I}{sc}{sr+3}", GREEN, USD)
        put(dcf, f"{c}{rr['Change in NWC']}", f"={I}$B$28*({c}{rr['Revenue']}-{p}{rr['Revenue']})", fmt=USD)
        put(dcf, f"{c}{rr['Free cash flow']}",
            f"={c}{rr['NOPAT']}+{c}{rr['D&A']}-{c}{rr['Capex, net']}-{c}{rr['Change in NWC']}", fmt=USD, bold=True)
        put(dcf, f"{c}{rr['Discount period (years)']}", j + 1, BLUE, "0")
        put(dcf, f"{c}{rr['Discount factor']}", f"=1/(1+{I}$B$23)^{c}{rr['Discount period (years)']}", fmt="0.000")
        put(dcf, f"{c}{rr['PV of FCF']}", f"={c}{rr['Free cash flow']}*{c}{rr['Discount factor']}", fmt=USD)
    v0 = top + 2 + len(FLOW) + 1
    vr = {lab: v0 + i for i, lab in enumerate(VAL)}
    for lab, r in vr.items():
        put(dcf, f"A{r}", lab, bold=lab in ("Enterprise value", "Equity value", "Value per share ($)"))
    put(dcf, f"C{vr['Normalised operating margin']}", f"={I}C{sr+4}", GREEN, PCT)
    put(dcf, f"C{vr['Terminal NOPAT (FY2032)']}",
        f"=H{rr['Revenue']}*(1+{I}$B$26)*C{vr['Normalised operating margin']}*(1-{I}$B$20)", fmt=USD)
    put(dcf, f"C{vr['Terminal reinvestment rate (g / RONIC)']}", f"={I}$B$26/{I}$B$27", fmt=PCT)
    put(dcf, f"C{vr['Terminal FCF (FY2032)']}",
        f"=C{vr['Terminal NOPAT (FY2032)']}*(1-C{vr['Terminal reinvestment rate (g / RONIC)']})", fmt=USD)
    put(dcf, f"C{vr['Terminal value at FY2031']}", f"=C{vr['Terminal FCF (FY2032)']}/({I}$B$23-{I}$B$26)", fmt=USD)
    put(dcf, f"C{vr['PV of terminal value']}", f"=C{vr['Terminal value at FY2031']}*H{rr['Discount factor']}", fmt=USD)
    put(dcf, f"C{vr['Sum of PV of FCF (FY27-31)']}", f"=SUM(D{rr['PV of FCF']}:H{rr['PV of FCF']})", fmt=USD)
    put(dcf, f"C{vr['Enterprise value']}",
        f"=C{vr['PV of terminal value']}+C{vr['Sum of PV of FCF (FY27-31)']}", fmt=USD, bold=True)
    put(dcf, f"C{vr['+ Cash and investments']}", f"={I}$B$7", GREEN, USD)
    put(dcf, f"C{vr['- Debt and finance leases']}", f"=-{I}$B$22", GREEN, USD)
    put(dcf, f"C{vr['- Customer deposits (if treated as debt)']}", f"=-{I}$B$10*{I}$B$11", GREEN, USD)
    put(dcf, f"C{vr['Equity value']}",
        f"=SUM(C{vr['Enterprise value']}:C{vr['- Customer deposits (if treated as debt)']})", fmt=USD, bold=True)
    put(dcf, f"C{vr['Value per share ($)']}", f"=C{vr['Equity value']}/{I}$B$6", fmt=USD2, bold=True)
    put(dcf, f"C{vr['Upside / (downside) vs price']}", f"=C{vr['Value per share ($)']}/{I}$B$5-1", fmt=PCT)
    put(dcf, f"C{vr['Terminal value as % of EV']}", f"=C{vr['PV of terminal value']}/C{vr['Enterprise value']}", fmt=PCT)
    put(dcf, f"C{vr['Implied EV / FY2027 EBIT']}", f"=C{vr['Enterprise value']}/D{rr['EBIT']}", fmt=MULT)
    BLOCK[name] = dict(rows=rr, vals=vr)
    return v0 + len(VAL) + 2


top = 3
for name in ("Bear", "Base", "Bull"):
    top = block(name, top)

# ---------------------------------------------------------------- Reverse DCF + sensitivity
rev = wb.create_sheet("Reverse DCF")
rev.column_dimensions["A"].width = 48
for c in "BCDEFGHI":
    rev.column_dimensions[c].width = 12
put(rev, "A1", "What do you have to believe? Base-case revenue and capex; FY27-28 margins as in the base case;"
               " operating margin from FY29 onwards = m.", bold=True)
put(rev, "A2", "Value is linear in m, so FCF splits into a part that does not depend on m (F0) and the part per unit of margin (dF).",
    italic=True)
b = BLOCK["Base"]["rows"]
header_row(rev, 4, ["$mm", "", "", "FY2027", "FY2028", "FY2029", "FY2030", "FY2031"])
put(rev, "A5", "Revenue (base case)")
put(rev, "A6", "Margin fixed at base case (1 = yes)")
put(rev, "A7", "F0: FCF with margin = 0 where not fixed")
put(rev, "A8", "dF: FCF per unit of margin")
put(rev, "A9", "Discount period")
for j, c in enumerate("DEFGH"):
    put(rev, f"{c}5", f"=DCF!{c}{b['Revenue']}", GREEN, USD)
    put(rev, f"{c}6", 1 if j < 2 else 0, BLUE, "0")
    put(rev, f"{c}7", f"=IF({c}6=1,DCF!{c}{b['Free cash flow']},"
                      f"DCF!{c}{b['D&A']}-DCF!{c}{b['Capex, net']}-DCF!{c}{b['Change in NWC']})", GREEN, USD)
    put(rev, f"{c}8", f"=IF({c}6=1,0,{c}5*(1-{I}$B$20))", fmt=USD)
    put(rev, f"{c}9", j + 1, BLUE, "0")
K = f"$H$5*(1+{I}$B$26)*(1-{I}$B$20)*(1-{I}$B$26/{I}$B$27)"
NET = f"({I}$B$7-{I}$B$22-{I}$B$10*{I}$B$11)"
put(rev, "A11", "Target equity value (price x diluted shares)")
put(rev, "C11", f"={I}B21", GREEN, USD)
put(rev, "A12", "PV of F0 + net cash")
put(rev, "C12", f"=SUMPRODUCT(D7:H7/(1+{I}$B$23)^D9:H9)+{NET}", fmt=USD)
put(rev, "A13", "PV per unit of margin (explicit + terminal)")
put(rev, "C13", f"=SUMPRODUCT(D8:H8/(1+{I}$B$23)^D9:H9)+{K}/({I}$B$23-{I}$B$26)/(1+{I}$B$23)^H9", fmt=USD)
put(rev, "A14", "Implied operating margin from FY29 onwards", bold=True)
put(rev, "C14", "=(C11-C12)/C13", fmt=PCT, bold=True)
put(rev, "A15", "  FY15-25 through-cycle average")
put(rev, "C15", "=Historical!B27", GREEN, PCT)
put(rev, "A16", "  Previous-cycle peak (FY18)")
put(rev, "C16", f"=Historical!F{R['Operating margin']}", GREEN, PCT)

put(rev, "A19", "Value per share ($): WACC (rows) x operating margin from FY29 onwards (columns)", bold=True)
MARGINS = [0.15, 0.20, 0.25, 0.30, 0.35, 0.40, 0.50]
WACCS = [0.10, 0.11, 0.12, 0.13, 0.14, 0.15, 0.16, 0.18]
header_row(rev, 20, ["WACC \\ margin", ""] + [""] * len(MARGINS))
for k, m in enumerate(MARGINS):
    put(rev, f"{chr(ord('C') + k)}20", m, BLUE, PCT, bold=True)
for i, w in enumerate(WACCS):
    r = 21 + i
    put(rev, f"A{r}", w, BLUE, PCT, bold=True)
    for k in range(len(MARGINS)):
        c = chr(ord("C") + k)
        put(rev, f"{c}{r}",
            f"=(SUMPRODUCT(($D$7:$H$7+{c}$20*$D$8:$H$8)/(1+$A{r})^$D$9:$H$9)"
            f"+{c}$20*{K}/($A{r}-{I}$B$26)/(1+$A{r})^$H$9+{NET})/{I}$B$6", fmt='$#,##0;($#,##0)')
put(rev, "A30", "Current price ($)")
put(rev, "C30", f"={I}B5", GREEN, USD2)
put(rev, "A31", "Model WACC")
put(rev, "C31", f"={I}B23", GREEN, PCT)

# ---------------------------------------------------------------- Comps
cp = wb.create_sheet("Comps")
cp.column_dimensions["A"].width = 30
for c in "BCDEFGH":
    cp.column_dimensions[c].width = 14
put(cp, "A1", "Memory and storage peers. Source: Yahoo Finance via yfinance, 2026-10-16 (multiples are currency-neutral).", bold=True)
put(cp, "A2", "Peak-cycle earnings make every P/E in the group look cheap: compare multiples within the cycle, not with the market.",
    italic=True)
header_row(cp, 4, ["Company", "Ticker", "Trailing P/E", "Forward P/E", "EV / EBITDA", "EV / revenue",
                   "Operating margin", "Gross margin"])
PEERS = [("Micron", "MU", 11.8, 4.2, 8.8, 7.2, 0.807, 0.807),
         ("SK hynix", "000660.KS", None, 2.7, 5.8, 4.4, 0.763, 0.763),
         ("Samsung Electronics", "005930.KS", None, 3.0, 5.6, 2.6, 0.522, 0.575),
         ("Sandisk", "SNDK", 17.6, 4.9, 14.7, 9.2, 0.785, 0.715),
         ("Western Digital", "WDC", 12.3, 10.0, 23.9, 9.2, 0.436, 0.489),
         ("Seagate", "STX", 46.0, 11.3, 32.7, 12.1, 0.431, 0.456)]
for i, row in enumerate(PEERS):
    for j, v in enumerate(row):
        fmt = None if j < 2 else (MULT if j < 6 else PCT)
        put(cp, f"{chr(ord('A') + j)}{5 + i}", "n/a" if v is None else v, BLUE if j >= 2 else BLACK, fmt)
put(cp, "A12", "Median, peers excl. Micron", bold=True)
for c, fmt in zip("CDEFGH", [MULT] * 4 + [PCT] * 2):
    put(cp, f"{c}12", f"=MEDIAN({c}6:{c}10)", fmt=fmt)
put(cp, "A13", "Micron forward P/E vs peer median")
put(cp, "D13", "=D5/D12-1", fmt=PCT)

# ---------------------------------------------------------------- Summary (first tab)
sm = wb.create_sheet("Summary", 0)
sm.column_dimensions["A"].width = 44
for c in "BCDE":
    sm.column_dimensions[c].width = 15
put(sm, "A1", "Micron Technology (MU): three-scenario DCF", bold=True)
put(sm, "A2", "Valuation date 2026-10-16. $mm unless stated. Change blue/yellow cells in 'Inputs'; everything else recalculates.",
    italic=True)
header_row(sm, 4, ["", "Bear", "Base", "Bull", "Prob.-weighted"])


def val(n, key):
    return f"=DCF!C{BLOCK[n]['vals'][key]}"


SUMMARY = [("FY2027 revenue", lambda n: f"=DCF!D{BLOCK[n]['rows']['Revenue']}", USD),
           ("FY2031 revenue", lambda n: f"=DCF!H{BLOCK[n]['rows']['Revenue']}", USD),
           ("Normalised operating margin", lambda n: val(n, "Normalised operating margin"), PCT),
           ("Enterprise value", lambda n: val(n, "Enterprise value"), USD),
           ("Equity value", lambda n: val(n, "Equity value"), USD),
           ("Value per share ($)", lambda n: val(n, "Value per share ($)"), USD2),
           ("Upside / (downside)", lambda n: val(n, "Upside / (downside) vs price"), PCT),
           ("Terminal value as % of EV", lambda n: val(n, "Terminal value as % of EV"), PCT),
           ("Probability", None, PCT)]
for i, (lab, fn, fmt) in enumerate(SUMMARY):
    r = 5 + i
    put(sm, f"A{r}", lab, bold=lab == "Value per share ($)")
    for k, n in enumerate(("Bear", "Base", "Bull")):
        c = "BCD"[k]
        put(sm, f"{c}{r}", fn(n) if fn else f"=Inputs!B{56 + k}", GREEN, fmt, bold=lab == "Value per share ($)")
put(sm, "E10", "=SUMPRODUCT(B10:D10,B13:D13)", fmt=USD2, bold=True)
put(sm, "E11", "=E10/Inputs!B5-1", fmt=PCT)
put(sm, "A15", "Current share price ($)")
put(sm, "B15", "=Inputs!B5", GREEN, USD2)
put(sm, "A16", "WACC")
put(sm, "B16", "=Inputs!B23", GREEN, PCT)
put(sm, "A17", "Margin from FY29 needed to justify the price", bold=True)
put(sm, "B17", "='Reverse DCF'!C14", GREEN, PCT, bold=True)
put(sm, "A18", "Through-cycle operating margin FY15-25")
put(sm, "B18", "=Historical!B27", GREEN, PCT)
put(sm, "A19", "Forward P/E: Micron / peer median")
put(sm, "B19", "=Comps!D5", GREEN, MULT)
put(sm, "C19", "=Comps!D12", GREEN, MULT)
put(sm, "A21", "Legend: blue = input, black = formula, green = link to another sheet, yellow = key assumption.", italic=True)
put(sm, "A22", "Sources: SEC EDGAR (10-K FY26 filed 2026-10-09; 8-K earnings release 2026-09-30); Yahoo Finance 2026-10-16.",
    italic=True)
put(sm, "A23", "Personal research, not investment advice.", italic=True)

for ws in wb.worksheets:
    ws.sheet_view.showGridLines = False
wb.save(OUT)
print("saved", OUT)
