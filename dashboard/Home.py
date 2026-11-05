"""Home page. Run with: streamlit run dashboard/Home.py"""
import streamlit as st

st.set_page_config(page_title="Investment research · Marcelo Renere", layout="wide")

st.title("Investment research")
st.caption("Marcelo Renere · Ingeniería Comercial and MSc Finance (UAI) · Master in Big Data & Data Science (UCM) · Master in Finance (EAE) · CFA Level I candidate")

st.markdown(
    """
This dashboard is the front door to the research in this repository. Each page is interactive and built on
the same code and data as the projects behind it.
"""
)

c1, c2 = st.columns(2)
with c1:
    st.subheader("Valuations")
    st.markdown("Scenario models of five companies: **Micron** (a memory cycle at its peak), **GTT** (a royalty "
                "business driven by its order book), **JPMorgan** (residual income), **Adobe** (how much AI disruption "
                "is in the price) and **Deckers** (HOKA and UGG). Move the discount rate or the assumptions and see "
                "what the price implies.")
    st.page_link("pages/1_Valuations.py", label="Open the valuations")

    st.subheader("Screener")
    st.markdown("The weekly five-factor screen (P/E, ROE, D/E, PEG, FCF yield) over ~2,150 US and European stocks: "
                "latest ranking and each stock's factor profile.")
    st.page_link("pages/2_Screener.py", label="Open the screener")
with c2:
    st.subheader("Strategy research")
    st.markdown("Eleven systematic ideas tested with fixed criteria, costs and out-of-sample data. "
                "None passed, and the page explains why.")
    st.page_link("pages/3_Research.py", label="Open the research scorecard")

    st.subheader("SQL on SEC filings")
    st.markdown("Ten million XBRL facts in DuckDB: sector margins, restatements, buybacks, ROE persistence "
                "and 10-K filing lags.")
    st.page_link("pages/4_SQL_insights.py", label="Open the SQL insights")

st.divider()
st.caption("Personal research, not investment advice. Prices and fundamentals as of mid-October to early November 2026. "
           "Python, SQL and Excel; Claude used as a coding and writing assistant.")
