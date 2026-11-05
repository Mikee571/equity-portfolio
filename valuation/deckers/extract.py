"""Builds data/deck_annual_raw.csv and data/deck_quarterly_raw.csv from SEC XBRL company facts.

The input, data/deck_companyfacts.json, is not in git (3MB): download it from
https://data.sec.gov/api/xbrl/companyfacts/CIK0000910521.json with a User-Agent header.
Deckers' fiscal year ends 31 March, so FY2026 is April 2025 to March 2026.
"""
import json
from datetime import date
from pathlib import Path
import pandas as pd

HERE = Path(__file__).parent
facts = json.load(open(HERE / "data" / "deck_companyfacts.json"))["facts"]["us-gaap"]

TAGS = {  # first tag found wins, so older names go last
    "Revenue": ["RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet", "Revenues"],
    "COGS": ["CostOfGoodsAndServicesSold", "CostOfGoodsSold"],
    "OpIncome": ["OperatingIncomeLoss"],
    "PretaxIncome": ["IncomeLossFromContinuingOperationsBeforeIncomeTaxesExtraordinaryItemsNoncontrollingInterest"],
    "IncomeTax": ["IncomeTaxExpenseBenefit"],
    "NetIncome": ["NetIncomeLoss"],
    "Advertising": ["MarketingAndAdvertisingExpense"],
    "D&A": ["DepreciationAmortizationAndAccretionNet", "DepreciationDepletionAndAmortization"],
    "SBC": ["ShareBasedCompensation"],
    "CFO": ["NetCashProvidedByUsedInOperatingActivities"],
    "Capex": ["PaymentsToAcquirePropertyPlantAndEquipment"],
    "Buybacks": ["PaymentsForRepurchaseOfCommonStock"],
    "TaxesPaid": ["IncomeTaxesPaidNet"],
    "LeasePayments": ["OperatingLeasePayments"],
    "Cash": ["CashAndCashEquivalentsAtCarryingValue"],
    "Receivables": ["AccountsReceivableNetCurrent"],
    "Inventory": ["InventoryNet"],
    "Payables": ["AccountsPayableTradeCurrent"],
    "LeaseLiab_ST": ["OperatingLeaseLiabilityCurrent"],
    "LeaseLiab_LT": ["OperatingLeaseLiabilityNoncurrent"],
    "Equity": ["StockholdersEquity"],
    "Assets": ["LiabilitiesAndStockholdersEquity"],
    "DilutedShares": ["WeightedAverageNumberOfDilutedSharesOutstanding"],
    "SharesOut": ["CommonStockSharesOutstanding"],
}
INSTANT = {"Cash", "Receivables", "Inventory", "Payables", "LeaseLiab_ST", "LeaseLiab_LT", "Equity", "Assets", "SharesOut"}


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
            elif 170 <= days <= 190:
                q.setdefault("6M_" + r.end, r.val)
    ann[name], qtr[name] = a, q

FYE = {f"FY{y}": f"{y}-03-31" for y in range(2015, 2027)}
for name in INSTANT:
    ann[name] = {fy: qtr[name][e] for fy, e in FYE.items() if e in qtr[name]}
A = pd.DataFrame(ann).sort_index().loc["FY2016":]
Q = pd.DataFrame(qtr).sort_index()
A.to_csv(HERE / "data" / "deck_annual_raw.csv")
Q.to_csv(HERE / "data" / "deck_quarterly_raw.csv")
if __name__ == "__main__":
    pd.set_option("display.width", 250)
    print((A / 1e6).round(0).to_string())
    print((Q[~Q.index.str.startswith("6M")].tail(9) / 1e6).round(1).to_string())
    print((Q[Q.index.str.startswith("6M")].tail(3) / 1e6).round(1).to_string())
