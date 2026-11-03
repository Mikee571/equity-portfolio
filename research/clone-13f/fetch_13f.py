"""Downloads the SEC's "Form 13F data sets" and keeps only what's needed.

For each ZIP: 13F-HR filings (SUBMISSION + COVERPAGE) and equity positions
(INFOTABLE with SSHPRNAMTTYPE = SH and no PUTCALL), aggregated by filing and CUSIP.
Deletes each ZIP after processing it. Can be rerun: it skips the ones already done.
Usage: python fetch_13f.py
"""
import io
import re
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

HERE = Path(__file__).resolve().parent
sys.path.insert(0, str(HERE.parent.parent / "equity-screener"))
from src.backtest.sec import user_agent  # noqa: E402

OUT = HERE / "data" / "13f"
PAGE = "https://www.sec.gov/data-research/sec-markets-data/form-13f-data-sets"


def read(z, name, cols):
    member = next(n for n in z.namelist() if n.upper().endswith(name))
    with z.open(member) as f:
        return pd.read_csv(f, sep="\t", usecols=lambda c: c in cols, dtype=str, quoting=3, on_bad_lines="skip")


def process(raw: bytes) -> tuple:
    z = zipfile.ZipFile(io.BytesIO(raw))
    sub = read(z, "SUBMISSION.TSV", {"ACCESSION_NUMBER", "FILING_DATE", "SUBMISSIONTYPE", "CIK", "PERIODOFREPORT"})
    cov = read(z, "COVERPAGE.TSV", {"ACCESSION_NUMBER", "ISAMENDMENT", "FILINGMANAGER_NAME"})
    sub = sub.merge(cov, on="ACCESSION_NUMBER", how="left")
    sub = sub[(sub.SUBMISSIONTYPE == "13F-HR") & (sub.ISAMENDMENT.fillna("N") != "Y")]
    info = read(z, "INFOTABLE.TSV", {"ACCESSION_NUMBER", "CUSIP", "NAMEOFISSUER", "VALUE", "SSHPRNAMT",
                                     "SSHPRNAMTTYPE", "PUTCALL"})
    info = info[info.ACCESSION_NUMBER.isin(sub.ACCESSION_NUMBER) & (info.SSHPRNAMTTYPE == "SH")
                & info.PUTCALL.isna()]
    info["VALUE"] = pd.to_numeric(info.VALUE, errors="coerce")
    info["SSHPRNAMT"] = pd.to_numeric(info.SSHPRNAMT, errors="coerce")
    info["CUSIP"] = info.CUSIP.str.upper().str.strip()
    hold = (info.groupby(["ACCESSION_NUMBER", "CUSIP"], as_index=False)
            .agg(value=("VALUE", "sum"), shares=("SSHPRNAMT", "sum"), issuer=("NAMEOFISSUER", "first")))
    return sub, hold


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    s = requests.Session()
    s.headers["User-Agent"] = user_agent()
    html = s.get(PAGE, timeout=60).text
    links = sorted(set(re.findall(r'href="([^"]*form13f[^"]*\.zip)"', html)))
    print(f"{len(links)} ficheros", flush=True)
    for link in links:
        name = link.rsplit("/", 1)[-1].replace(".zip", "")
        if (OUT / f"{name}_hold.parquet").exists():
            continue
        url = link if link.startswith("http") else "https://www.sec.gov" + link
        for attempt in range(8):
            try:
                r = s.get(url, timeout=600)
                if r.status_code == 200:
                    break
            except requests.exceptions.RequestException as e:  # network drops: retry
                print(f"  {name}: {type(e).__name__}, reintento {attempt + 1}", flush=True)
            time.sleep(15 * (attempt + 1))
        r.raise_for_status()
        sub, hold = process(r.content)
        sub.to_parquet(OUT / f"{name}_sub.parquet")
        hold.to_parquet(OUT / f"{name}_hold.parquet")
        print(f"{name}: {len(r.content) / 1e6:.0f} MB, {len(sub):,} 13F-HR, {len(hold):,} posiciones", flush=True)
        time.sleep(1)


if __name__ == "__main__":
    main()
