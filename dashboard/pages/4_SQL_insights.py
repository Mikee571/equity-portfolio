"""Results of the SQL analysis of SEC XBRL filings (sql-analysis/results)."""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import BLUE, ROOT, SCENARIO_COLORS, style  # noqa: E402

st.set_page_config(page_title="SQL insights", layout="wide")
st.title("SQL on SEC filings")
st.caption("10.4 million XBRL facts from 20,438 filers in DuckDB, with every filed version of each number. "
           "Queries and method in sql-analysis/.")
R = ROOT / "sql-analysis" / "results"

st.subheader("How often do companies change last year's revenue?")
rs = pd.read_csv(R / "03_restatements.csv")
rs["series"] = rs["item"]
chart = alt.Chart(rs).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=36)).encode(
    x=alt.X("fiscal_year:O", title="Fiscal year"),
    y=alt.Y("share_revised_over_1pct:Q", title="Share revised by more than 1%", axis=alt.Axis(format="%")),
    color=alt.Color("series:N", scale=alt.Scale(domain=["Revenue", "Net income"],
                                                range=[BLUE, SCENARIO_COLORS["Bear"]]), title=None),
    tooltip=["item", "fiscal_year", alt.Tooltip("share_revised_over_1pct:Q", format=".1%"),
             alt.Tooltip("share_revised_down:Q", format=".1%", title="revised down")])
st.altair_chart(style(chart, 280), width="stretch")
st.caption("Revenue revisions are almost always downwards: past revenue is re-presented without businesses that "
           "were later sold. A backtest on 'latest' numbers quietly knows about future divestitures.")

c1, c2 = st.columns(2)
with c1:
    st.subheader("Buybacks and later returns")
    bb = pd.read_csv(R / "04_buybacks_and_returns.csv")
    bb["group"] = bb["quintile"].map({1: "Q1 most shrinkage", 2: "Q2", 3: "Q3", 4: "Q4", 5: "Q5 most dilution"})
    chart = alt.Chart(bb).mark_bar(color=BLUE, cornerRadiusEnd=4).encode(
        x=alt.X("group:N", sort=None, title="Share-count change FY2015-20"),
        y=alt.Y("median_return_2021_25:Q", title="Median return 2021-25", axis=alt.Axis(format="%")),
        tooltip=["group", alt.Tooltip("median_share_change_2015_20:Q", format=".0%", title="share change"),
                 alt.Tooltip("median_return_2021_25:Q", format=".0%", title="median return"),
                 alt.Tooltip("mean_return_2021_25:Q", format=".0%", title="mean return")])
    st.altair_chart(style(chart, 260), width="stretch")
    st.caption("The median buyback company did best, but the mean returns of the two extremes are equal (~+90%): "
               "heavy diluters include a few huge winners. Survivors only.")
with c2:
    st.subheader("Do high-ROE companies stay high-ROE?")
    st.image(str(ROOT / "sql-analysis/figures/roe_persistence.png"))

st.subheader("Sector margins, 2012-2025")
sm = pd.read_csv(R / "02_sector_margins.csv")
st.dataframe(sm, hide_index=True, width="stretch", column_config={
    c: st.column_config.NumberColumn(format="percent") for c in ("typical_margin", "worst_year_margin", "best_year_margin")})

st.subheader("Days to file the 10-K")
st.dataframe(pd.read_csv(R / "06_filing_lag.csv"), hide_index=True, width="stretch")
