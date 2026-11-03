"""Downloads each universe company's filing history from data.sec.gov/submissions
and saves the 8-Ks with item 2.02 (results) and the 10-Qs/10-Ks to data/filings.parquet.

Usage: python fetch_filings.py   (about 15 minutes; resumes from data/raw if interrupted)
"""
import json
import sys
import time
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).parent
SCREENER = HERE.parent.parent / "equity-screener"
sys.path.insert(0, str(SCREENER))
from src.backtest.sec import user_agent  # noqa: E402

RAW = HERE / "data" / "raw"
BASE = "https://data.sec.gov/submissions/"
FORMS = {"8-K", "10-Q", "10-K", "10-KT"}


def get(session, name):
    path = RAW / name
    if path.exists():
        return json.loads(path.read_text(encoding="utf-8"))
    for attempt in range(5):
        r = session.get(BASE + name, timeout=30)
        time.sleep(0.12)  # the SEC allows 10 a second
        if r.status_code == 200:
            path.write_text(r.text, encoding="utf-8")
            return r.json()
        if r.status_code == 404:
            return None
        time.sleep(2 ** attempt)
    raise RuntimeError(f"{name}: {r.status_code}")


def rows(block, cik):
    df = pd.DataFrame({k: block[k] for k in ("form", "filingDate", "acceptanceDateTime", "items", "reportDate")})
    df = df[df.form.isin(FORMS)]
    df["cik"] = cik
    return df


def main():
    RAW.mkdir(parents=True, exist_ok=True)
    ciks = pd.read_pickle(SCREENER / "data" / "backtest" / "universe.pkl")["cik"].dropna().astype(int).unique()
    s = requests.Session()
    s.headers["User-Agent"] = user_agent()
    out = []
    for i, cik in enumerate(ciks):
        main_json = get(s, f"CIK{cik:010d}.json")
        if main_json is None:
            continue
        out.append(rows(main_json["filings"]["recent"], cik))
        for extra in main_json["filings"].get("files", []):
            block = get(s, extra["name"])
            if block:
                out.append(rows(block, cik))
        if i % 200 == 0:
            print(f"{i}/{len(ciks)}", flush=True)
    df = pd.concat(out, ignore_index=True).drop_duplicates()
    df["filingDate"] = pd.to_datetime(df.filingDate)
    df["acceptanceDateTime"] = pd.to_datetime(df.acceptanceDateTime, utc=True, errors="coerce")
    df["reportDate"] = pd.to_datetime(df.reportDate, errors="coerce")
    df.to_parquet(HERE / "data" / "filings.parquet")
    print(df.form.value_counts(), df.cik.nunique())


if __name__ == "__main__":
    main()
