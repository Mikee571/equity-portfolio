"""Latest five-factor screener ranking (snapshot of the weekly run)."""
import sys
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import BLUE, DASH, style  # noqa: E402

st.set_page_config(page_title="Screener", layout="wide")
st.title("Five-factor screener")
st.caption("Snapshot of the weekly run on 2026-10-11 (TradingView data). Stocks must pass all five hard filters; "
           "survivors are ranked on a weighted z-score. Financials are excluded.")

df = pd.read_csv(DASH / "data" / "screener_2026-10-11.csv")
with st.sidebar:
    st.header("Filters")
    countries = st.multiselect("Country", sorted(df.country.unique()))
    sectors = st.multiselect("Sector", sorted(df.sector.unique()))
    min_cap = st.slider("Minimum market cap ($bn)", 1.0, 50.0, 1.0, 1.0)
view = df[df.market_cap >= min_cap * 1e9]
if countries:
    view = view[view.country.isin(countries)]
if sectors:
    view = view[view.sector.isin(sectors)]

view = view.assign(market_cap=view.market_cap / 1e9)

c1, c2, c3 = st.columns(3)
c1.metric("Stocks passing all filters", len(view))
c2.metric("Median P/E", f"{view.pe.median():.1f}x" if len(view) else "-")
c3.metric("Median FCF yield", f"{view.fcf_yield.median():.1%}" if len(view) else "-")

st.dataframe(
    view[["rank", "ticker", "company", "country", "sector", "market_cap", "pe", "roe_pct", "debt_to_equity",
          "peg", "fcf_yield", "score"]],
    hide_index=True, use_container_width=True,
    column_config={
        "market_cap": st.column_config.NumberColumn("Mkt cap ($bn)", format="%.1f"),
        "pe": st.column_config.NumberColumn("P/E", format="%.1f"),
        "roe_pct": st.column_config.NumberColumn("ROE %", format="%.0f"),
        "debt_to_equity": st.column_config.NumberColumn("D/E", format="%.2f"),
        "peg": st.column_config.NumberColumn("PEG", format="%.2f"),
        "fcf_yield": st.column_config.NumberColumn("FCF yield", format="percent"),
        "score": st.column_config.NumberColumn("Score", format="%.2f"),
    },
)
st.subheader("Factor profile")
if len(view):
    pick = st.selectbox("Stock", view.ticker + " · " + view.company)
    row = view[view.ticker + " · " + view.company == pick].iloc[0]
    z = pd.DataFrame({"factor": ["P/E (cheap)", "ROE", "Low debt", "PEG", "FCF yield"],
                      "z": [row.z_pe, row.z_roe, row.z_de, row.z_peg, row.z_fcf],
                      "weight": ["20%", "30%", "15%", "20%", "15%"]})
    chart = alt.Chart(z).mark_bar(color=BLUE, cornerRadiusEnd=4).encode(
        x=alt.X("z:Q", title="z-score vs other survivors (winsorised)"),
        y=alt.Y("factor:N", sort=None, title=None),
        tooltip=["factor", alt.Tooltip("z:Q", format=".2f"), "weight"])
    st.altair_chart(style(chart, 220), use_container_width=True)
    if isinstance(row.data_warnings, str):
        st.caption(f"Data warnings: {row.data_warnings}. PEG_BASE_EFFECT means EPS growth comes off a depressed "
                   f"base, so the PEG is scored as neutral.")

st.warning("What the backtest says: from 2012 to 2026 the top 10 beat its universe by 3.2% a year, but with t ≈ 1. "
           "That isn't proven skill. I use the screen to generate ideas, not as a buy list.")
