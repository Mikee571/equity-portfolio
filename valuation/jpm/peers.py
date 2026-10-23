"""Peer table for the JPM model: price / tangible book and return on tangible equity for six large US banks,
computed the same way for all of them.

TBVPS = book value per share (Yahoo Finance) - (goodwill + intangibles) / shares (SEC XBRL, latest 10-Q/10-K).
ROTE  = trailing-12-month net income to common (Yahoo Finance) / tangible common equity.
I tried doing everything from SEC XBRL first, but preferred stock isn't tagged consistently across banks, so book
value per share comes from Yahoo. For JPM it matches the earnings release to the cent ($132.30).

Usage: SEC_USER_AGENT="Your Name you@example.com" python peers.py   -> data/peers.csv
"""
import json
import os
import urllib.request
import warnings
from pathlib import Path

import pandas as pd
import yfinance as yf

warnings.filterwarnings("ignore")
HERE = Path(__file__).parent
BANKS = {"0000019617": "JPM", "0000070858": "BAC", "0000072971": "WFC", "0000831001": "C",
         "0000886982": "GS", "0000895421": "MS"}


def company_facts(cik):
    req = urllib.request.Request(f"https://data.sec.gov/api/xbrl/companyfacts/CIK{cik}.json",
                                 headers={"User-Agent": os.environ["SEC_USER_AGENT"]})
    return json.load(urllib.request.urlopen(req, timeout=60))["facts"]["us-gaap"]


def last_instant(f, tags):
    for t in tags:
        xs = [x for u in f.get(t, {}).get("units", {}).values() for x in u
              if "start" not in x and x.get("form") in ("10-K", "10-Q")]
        if xs:
            x = max(xs, key=lambda x: x["end"])
            if x["end"] >= "2025-06-01":
                return x["val"], x["end"]
    return 0.0, None


def main():
    rows = []
    for cik, tk in BANKS.items():
        f = company_facts(cik)
        gw, gw_date = last_instant(f, ["Goodwill"])
        it, _ = last_instant(f, ["IntangibleAssetsNetExcludingGoodwill", "FiniteLivedIntangibleAssetsNet",
                                 "OtherIntangibleAssetsNet"])
        info = yf.Ticker(tk).info
        price = float(yf.Ticker(tk).history(period="5d")["Close"].iloc[-1])
        shares, bvps, ni = info["sharesOutstanding"], info["bookValue"], info["netIncomeToCommon"]
        tbvps = bvps - (gw + it) / shares
        rows.append(dict(bank=tk, price=price, bvps=bvps, gw_intang_bn=(gw + it) / 1e9, gw_date=gw_date, tbvps=tbvps,
                         ttm_ni_common_bn=ni / 1e9, rote=ni / (tbvps * shares), p_tbv=price / tbvps,
                         p_e=price / (ni / shares)))
    df = pd.DataFrame(rows)
    df.to_csv(HERE / "data" / "peers.csv", index=False)
    print(df.round(3).to_string(index=False))


if __name__ == "__main__":
    main()
