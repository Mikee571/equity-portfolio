"""Builds data/adbe_annual_raw.csv and data/adbe_quarterly_raw.csv from SEC XBRL company facts.

The input, data/adbe_companyfacts.json, is not in git (4.8MB): download it from
https://data.sec.gov/api/xbrl/companyfacts/CIK0000796343.json with a User-Agent header.
"""
import json
from datetime import date
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
facts = json.load(open(HERE / "data" / "adbe_companyfacts.json"))["facts"]["us-gaap"]

TAGS = {  # first tag found wins, so older names go last
    "Revenue": ["Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet"],
    "SubscriptionRevenue": ["SubscriptionRevenue", "LicensesRevenue"],
    "COGS": ["CostOfRevenue"],
    "R&D": ["ResearchAndDevelopmentExpenseSoftwareExcludingAcquiredInProcessCost", "ResearchAndDevelopmentExpense"],
    "S&M": ["SellingAndMarketingExpense"],
    "G&A": ["GeneralAndAdministrativeExpense"],
    "Amort_Intang": ["AmortizationOfIntangibleAssets"],
    "OpIncome": ["OperatingIncomeLoss"],
    "PretaxIncome": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
    "IncomeTax": ["IncomeTaxExpenseBenefit"],
    "NetIncome": ["NetIncomeLoss"],
    "D&A": ["DepreciationDepletionAndAmortization", "DepreciationAmortizationAndAccretionNet"],
    "SBC": ["ShareBasedCompensation"],
    "CFO": ["NetCashProvidedByUsedInOperatingActivities"],
    "Capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "Buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "Cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "ST_Inv": ["ShortTermInvestments", "AvailableForSaleSecuritiesDebtSecuritiesCurrent"],
    "Debt_total": ["LongTermDebt"],
    "Debt_ST": ["DebtCurrent", "LongTermDebtCurrent"],
    "DeferredRevenue": ["ContractWithCustomerLiabilityCurrent", "DeferredRevenueCurrent"],
    "RPO": ["RevenueRemainingPerformanceObligation"],
    "Equity": ["StockholdersEquity"],
    "Assets": ["Assets"],
    "DilutedShares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "SharesOut": ["CommonStockSharesOutstanding"],
}
INSTANT = {"Cash", "ST_Inv", "Debt_total", "Debt_ST", "SharesOut", "DeferredRevenue", "RPO", "Equity", "Assets"}


def series(tag):
    units = facts[tag]["units"]
    rows = units.get("USD") or units.get("shares")
    df = pd.DataFrame(rows)
    df = df[df.form.isin(["10-K", "10-Q"])].sort_values("filed").drop_duplicates(["start", "end"] if "start" in df else ["end"], keep="last")
    return df


ann, qtr = {}, {}
for name, tags in TAGS.items():
    a, q = {}, {}
    for tag in tags:
        if tag not in facts:
            continue
        df = series(tag)
        for _, r in df.iterrows():
            end = date.fromisoformat(r.end)
            if name in INSTANT:
                q.setdefault(r.end, r.val)
                continue
            days = (end - date.fromisoformat(r.start)).days
            if 350 <= days <= 380:
                a.setdefault(f"FY{end.year}", r.val)
            elif 80 <= days <= 100:
                q.setdefault(r.end, r.val)
            elif 260 <= days <= 280:
                q.setdefault("9M_" + r.end, r.val)
    ann[name], qtr[name] = a, q

FYE = {}  # fiscal year-end dates, taken from the revenue series
for _, r in series("Revenues").iterrows():
    if 350 <= (date.fromisoformat(r.end) - date.fromisoformat(r.start)).days <= 380:
        FYE[f"FY{r.end[:4]}"] = r.end
for name in INSTANT:
    ann[name] = {fy: qtr[name][e] for fy, e in FYE.items() if e in qtr[name]}
A = pd.DataFrame(ann).sort_index().loc["FY2015":]
Q = pd.DataFrame(qtr).sort_index()
A.to_csv(HERE / "data" / "adbe_annual_raw.csv")
Q.to_csv(HERE / "data" / "adbe_quarterly_raw.csv")
pd.set_option("display.width", 250)
print((A / 1e9).round(2).to_string())
print((Q[~Q.index.str.startswith("9M")].tail(8) / 1e9).round(3).to_string())
