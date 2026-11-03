"""Quarterly net income (first filing) and a seasonal random-walk SUE.

Q1-Q3 come from the 10-Qs. Q4 is the quarterly value if the 10-K has one, and otherwise the
annual figure minus the nine-month year-to-date (both from their first filing).
Output: data/sue.parquet with cik, period_end, ni, report_filed, sue.
"""
from pathlib import Path

import duckdb
import numpy as np
import pandas as pd

HERE = Path(__file__).parent
DB = HERE.parent.parent / "sql-analysis" / "sec.duckdb"

SQL = """
with f as (
    select cik, period_start, period_end, value, filed,
           date_diff('day', period_start, period_end) as days
    from facts
    where tag = 'NetIncomeLoss' and unit = 'USD'
      and form in ('10-Q', '10-K', '10-KT', '10-Q/A', '10-K/A')
      and period_start is not null
)
select cik, period_start, period_end, days,
       arg_min(value, filed) as value, min(filed) as filed
from f
where days between 80 and 100 or days between 260 and 285 or days between 350 and 380
group by all
"""


def quarterly(raw: pd.DataFrame) -> pd.DataFrame:
    q = raw[raw.days.between(80, 100)][["cik", "period_end", "value", "filed"]]
    ann = raw[raw.days.between(350, 380)]
    ytd9 = raw[raw.days.between(260, 285)]
    q4 = ann.merge(ytd9, on=["cik", "period_start"], suffixes=("", "_9m"))
    q4 = q4[(q4.period_end - q4.period_end_9m).dt.days.between(80, 100)]
    q4 = q4.assign(value=q4.value - q4.value_9m, filed=q4[["filed", "filed_9m"]].max(axis=1))
    q4 = q4[["cik", "period_end", "value", "filed"]]
    # an explicit quarterly value takes priority over the derived one
    out = pd.concat([q.assign(src=0), q4.assign(src=1)]).sort_values(["cik", "period_end", "src"])
    out = out.drop_duplicates(["cik", "period_end"]).drop(columns="src")
    # period ends a few days apart (52/53-week years) count as the same quarter
    out = out.sort_values(["cik", "period_end"])
    gap = out.groupby("cik").period_end.diff().dt.days
    return out[~(gap < 45)].rename(columns={"value": "ni", "filed": "report_filed"})


def sue(q: pd.DataFrame) -> pd.DataFrame:
    frames = []
    for cik, g in q.groupby("cik", sort=False):
        g = g.sort_values("period_end").reset_index(drop=True)
        ends = g.period_end.values
        ni = g.ni.values
        d = np.full(len(g), np.nan)
        for i in range(len(g)):
            # the quarter a year earlier: period end 350 to 380 days before
            lag = (ends[i] - ends[:i]) / np.timedelta64(1, "D")
            j = np.where((lag >= 350) & (lag <= 380))[0]
            if len(j):
                d[i] = ni[i] - ni[j[-1]]
        s = np.full(len(g), np.nan)
        for i in range(len(g)):
            lag = (ends[i] - ends[:i]) / np.timedelta64(1, "D")
            prev = d[:i][(lag <= 760) & ~np.isnan(d[:i])][-8:]
            if len(prev) >= 6 and np.isfinite(d[i]):
                sd = prev.std(ddof=1)
                s[i] = d[i] / sd if sd > 0 else np.nan
        frames.append(g.assign(seasonal_diff=d, sue=s))
    return pd.concat(frames, ignore_index=True)


def main():
    con = duckdb.connect(str(DB), read_only=True)
    raw = con.sql(SQL).df()
    q = quarterly(raw)
    out = sue(q)
    out.to_parquet(HERE / "data" / "sue.parquet")
    ok = out.dropna(subset=["sue"])
    print(f"quarters {len(out):,}  with SUE {len(ok):,}  companies {ok.cik.nunique():,}")
    print(ok.sue.describe(percentiles=[.01, .1, .5, .9, .99]).round(2).to_string())
    print(ok.groupby(ok.period_end.dt.year).size().to_string())


if __name__ == "__main__":
    main()
