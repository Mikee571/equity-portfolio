"""Builds sec.duckdb from the SEC's companyfacts.zip (every XBRL fact filed by every company).

Only a list of key us-gaap tags is kept, but *every version* of each fact is kept: the same number can be
filed several times (original 10-K, later 10-Ks, restatements), and the `filed` date tells them apart.

Tables
  facts      one row per filed fact: cik, tag, unit, period start/end, value, fiscal year/period, form, filed, accn
  companies  cik, entity name, ticker and exchange (SEC company_tickers_exchange.json)
  sectors    cik, sector, industry for ~2,600 US stocks > $50mm (TradingView classification, from the screener backtest)
  prices     month-end adjusted close for those stocks, 2010-2026 (yfinance, from the screener backtest)

Usage:
  python build_db.py --data ../equity-screener/data
The data folder needs sec/companyfacts.zip and sec/company_tickers_exchange.json (both from sec.gov), and
backtest/universe.pkl + backtest/prices_adj_close.parquet (built by equity-screener/run_backtest.py).
"""
import argparse
import json
import time
import zipfile
from pathlib import Path

import duckdb
import pandas as pd

TAGS = {
    "Revenues", "RevenueFromContractWithCustomerExcludingAssessedTax", "SalesRevenueNet",
    "OperatingIncomeLoss", "NetIncomeLoss", "StockholdersEquity", "Assets", "LongTermDebt",
    "CashAndCashEquivalentsAtCarryingValue", "NetCashProvidedByUsedInOperatingActivities",
    "PaymentsToAcquirePropertyPlantAndEquipment", "PaymentsForRepurchaseOfCommonStock",
    "PaymentsOfDividendsCommonStock", "PaymentsOfDividends", "ResearchAndDevelopmentExpense",
    "WeightedAverageNumberOfDilutedSharesOutstanding",
}
UNITS = {"USD", "shares"}


def parse(zip_path: Path) -> pd.DataFrame:
    rows, names = [], []
    t0 = time.time()
    with zipfile.ZipFile(zip_path) as zf:
        members = zf.namelist()
        for i, m in enumerate(members):
            doc = json.loads(zf.read(m))
            cik = int(doc.get("cik") or m[3:13])
            names.append((cik, doc.get("entityName")))
            for tag, body in doc.get("facts", {}).get("us-gaap", {}).items():
                if tag not in TAGS:
                    continue
                for unit, items in body["units"].items():
                    if unit not in UNITS:
                        continue
                    for x in items:
                        rows.append((cik, tag, unit, x.get("start"), x["end"], x["val"], x.get("fy"), x.get("fp"),
                                     x.get("form"), x.get("filed"), x.get("accn"), x.get("frame")))
            if i % 2000 == 0:
                print(f"  {i:>6}/{len(members)} companies, {len(rows):,} facts, {time.time() - t0:.0f}s", flush=True)
    facts = pd.DataFrame(rows, columns=["cik", "tag", "unit", "period_start", "period_end", "value", "fy", "fp",
                                        "form", "filed", "accn", "frame"])
    for c in ("period_start", "period_end", "filed"):
        facts[c] = pd.to_datetime(facts[c], errors="coerce")
    return facts, pd.DataFrame(names, columns=["cik", "entity_name"])


def main():
    ap = argparse.ArgumentParser()
    ap.add_argument("--data", default="../equity-screener/data")
    ap.add_argument("--out", default="sec.duckdb")
    a = ap.parse_args()
    data = Path(a.data)

    print("Parsing companyfacts.zip ...")
    facts, names = parse(data / "sec" / "companyfacts.zip")

    tick = json.loads((data / "sec" / "company_tickers_exchange.json").read_text())
    tickers = pd.DataFrame(tick["data"], columns=tick["fields"]).rename(columns={"name": "ticker_name"})
    companies = names.merge(tickers.drop_duplicates("cik"), on="cik", how="left")

    uni = pd.read_pickle(data / "backtest" / "universe.pkl")
    sectors = uni[["cik", "symbol", "sector", "industry", "exchange"]].dropna(subset=["cik"]).copy()
    sectors["cik"] = sectors["cik"].astype(int)

    px = pd.read_parquet(data / "backtest" / "prices_adj_close.parquet")
    px.index = pd.to_datetime(px.index)
    prices = (px.resample("ME").last().stack().rename("adj_close").reset_index()
                .rename(columns={"level_0": "month_end", "Date": "month_end", "level_1": "symbol", "Ticker": "symbol"}))
    prices.columns = ["month_end", "symbol", "adj_close"]

    con = duckdb.connect(a.out)
    for name, df in (("facts", facts), ("companies", companies), ("sectors", sectors), ("prices", prices)):
        con.execute(f"CREATE OR REPLACE TABLE {name} AS SELECT * FROM df")
        print(f"  {name}: {con.execute(f'SELECT COUNT(*) FROM {name}').fetchone()[0]:,} rows")
    con.close()


if __name__ == "__main__":
    main()
