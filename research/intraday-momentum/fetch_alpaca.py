"""1-minute SPY bars (SIP feed, unadjusted) from Alpaca, from 2016 to yesterday.

Needs intraday-momentum/.env with
    ALPACA_KEY_ID=...
    ALPACA_SECRET_KEY=...
(a free Alpaca account; the free plan gives historical SIP data except the last 15 minutes).
Saves data/spy_1m_alpaca.parquet in New York time, regular hours only.
Usage: python fetch_alpaca.py
"""
import os
import time
from pathlib import Path

import pandas as pd
import requests
from dotenv import load_dotenv

HERE = Path(__file__).resolve().parent
OUT = HERE / "data" / "spy_1m_alpaca.parquet"
URL = "https://data.alpaca.markets/v2/stocks/SPY/bars"
TZ = "America/New_York"


def main(start: str = "2016-01-01") -> None:
    load_dotenv(HERE / ".env")
    key, secret = os.getenv("ALPACA_KEY_ID"), os.getenv("ALPACA_SECRET_KEY")
    if not key or not secret:
        raise SystemExit("ALPACA_KEY_ID / ALPACA_SECRET_KEY missing from intraday-momentum/.env")
    s = requests.Session()
    s.headers.update({"APCA-API-KEY-ID": key, "APCA-API-SECRET-KEY": secret})
    end = (pd.Timestamp.now(tz="UTC").normalize()).isoformat()
    params = {"timeframe": "1Min", "start": start, "end": end, "feed": "sip",
              "adjustment": "raw", "limit": 10000}
    bars, page = [], None
    while True:
        if page:
            params["page_token"] = page
        r = s.get(URL, params=params, timeout=60)
        if r.status_code == 429:
            time.sleep(5)
            continue
        r.raise_for_status()
        js = r.json()
        bars += js.get("bars") or []
        page = js.get("next_page_token")
        if len(bars) % 200_000 < 10_000:
            print(f"{len(bars):,} bars, up to {bars[-1]['t'] if bars else '-'}", flush=True)
        if not page:
            break
        time.sleep(0.35)  # free plan: 200 requests a minute
    df = pd.DataFrame(bars).rename(columns={"t": "time", "o": "Open", "h": "High", "l": "Low",
                                            "c": "Close", "v": "Volume", "vw": "VWAPbar", "n": "trades"})
    df.index = pd.to_datetime(df.pop("time"), utc=True).dt.tz_convert(TZ)
    df = df.between_time("09:30", "15:59")
    OUT.parent.mkdir(exist_ok=True)
    df.to_parquet(OUT)
    print(f"saved {OUT.name}: {len(df):,} bars, {df.index[0]} to {df.index[-1]}, "
          f"{len(set(df.index.date)):,} days")


if __name__ == "__main__":
    main()
