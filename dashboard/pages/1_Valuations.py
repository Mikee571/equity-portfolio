"""Interactive versions of the Micron, GTT, JPMorgan, Adobe and Deckers models (same logic as the Excel models, see models.py)."""
import sys
from dataclasses import replace
from pathlib import Path

import altair as alt
import pandas as pd
import streamlit as st

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from common import ROOT, scenario_scale, style  # noqa: E402
import models  # noqa: E402  (valuation/models.py, path set in common)

st.set_page_config(page_title="Valuations", layout="wide")
st.title("Valuations")
st.caption("Same logic as the Excel models in valuation/ (checked by valuation/test_models.py). Defaults reproduce the published "
           "numbers; the sliders let you challenge them.")

tab_mu, tab_gtt, tab_jpm, tab_adbe, tab_deck, tab_mc = st.tabs(
    ["Micron (MU)", "GTT", "JPMorgan", "Adobe (ADBE)", "Deckers (DECK)", "Monte Carlo"])

# ---------------------------------------------------------------- Micron
with tab_mu:
    base_in = models.MicronInputs()
    st.markdown(
        "**The question:** at ~5x forward earnings (4x on FY28), is Micron cheap after a record year, or is the market right to "
        "distrust peak memory earnings? All scenarios start from consensus for FY27-28 and differ in what happens "
        "after. **My view: expensive.** Full pitch: `equity-research/pitches/MU_pitch.md`; Excel model: `valuation/micron/`."
    )
    left, right = st.columns([1, 2.2])
    with left:
        wacc = st.slider("WACC (%)", 8.0, 18.0, round(base_in.wacc * 100, 2), 0.25, key="mu_w") / 100
        g = st.slider("Terminal growth (%)", 0.0, 4.0, base_in.g * 100, 0.25, key="mu_g") / 100
        st.markdown("Normalised operating margin")
        norms = {n: st.slider(f"{n} (%)", 5, 70, int(s.norm_margin * 100), 5, key=f"mu_n_{n}") / 100
                 for n, s in models.MICRON_SCENARIOS.items()}
        deposits = st.toggle("Treat $12.7bn customer prepayments as debt", True)
        st.markdown("Scenario probabilities")
        pb = st.slider("Bear", 0.0, 0.8, 0.30, 0.05, key="mu_pb")
        pu = st.slider("Bull", 0.0, 1.0 - pb, 0.20, 0.05, key="mu_pu")
    p = replace(base_in, wacc_override=wacc, g=g, deposits_as_debt=deposits)
    res = {n: models.micron_value(replace(s, norm_margin=norms[n]), p) for n, s in models.MICRON_SCENARIOS.items()}
    probs = {"Bear": pb, "Base": 1 - pb - pu, "Bull": pu}
    weighted = sum(res[n][0] * probs[n] for n in res)
    with right:
        cols = st.columns(4)
        for c, n in zip(cols, ("Bear", "Base", "Bull")):
            c.metric(f"{n} ({probs[n]:.0%})", f"${res[n][0]:,.0f}", f"{res[n][0] / p.price - 1:+.0%} vs price")
        cols[3].metric("Probability-weighted", f"${weighted:,.0f}", f"{weighted / p.price - 1:+.0%} vs ${p.price:,.0f}")
        implied = models.micron_implied_margin(replace(p, deposits_as_debt=deposits))
        st.info(f"**Reverse DCF:** on the base-case revenue path, the price needs an operating margin of "
                f"**{implied:.0%}** from FY29 onwards (FY15-25 average: 17%; previous peak FY18: 49%).")
        hist = pd.read_csv(ROOT / "valuation/micron/data/mu_annual_raw.csv", index_col=0)["Revenue"].dropna() / 1e9
        rows = [dict(year=int(y[2:]), revenue=v, scenario="Actual") for y, v in hist.items()]
        rows += [dict(year=2026, revenue=133.188, scenario=n) for n in res]
        rows += [dict(year=r["year"], revenue=r["revenue"] / 1e3, scenario=n) for n in res for r in res[n][1]]
        df = pd.DataFrame(rows)
        dom = ["Actual", "Bear", "Base", "Bull"]
        chart = alt.Chart(df).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=36)).encode(
            x=alt.X("year:O", title="Fiscal year"),
            y=alt.Y("revenue:Q", title="Revenue ($bn)"),
            color=alt.Color("scenario:N", scale=scenario_scale(dom), sort=dom, title=None),
            tooltip=["scenario", "year", alt.Tooltip("revenue:Q", format=",.1f", title="Revenue $bn")])
        st.altair_chart(style(chart.properties(title="Revenue: history and scenarios")), use_container_width=True)

# ---------------------------------------------------------------- GTT
with tab_gtt:
    gi = models.GttInputs()
    st.markdown(
        "**The question:** GTT is paid a royalty on almost every LNG carrier built. The order book covers most of "
        "the next three years; the valuation depends on how many ships are ordered after that. "
        "**My view: expensive.** Full pitch: `equity-research/pitches/GTT_pitch.md`; Excel model: `valuation/gtt/`."
    )
    left, right = st.columns([1, 2.2])
    with left:
        wacc = st.slider("WACC (%)", 6.0, 12.0, round(gi.wacc * 100, 2), 0.25, key="gtt_w") / 100
        royalty = st.slider("Royalty per LNG-carrier equivalent (€mm)", 7.0, 13.0, gi.royalty, 0.5, key="gtt_r")
        custom = st.slider("Your case: orders a year 2027-35", 20, 120, 60, 5, key="gtt_q")
        g_custom = st.slider("Your case: terminal growth (%)", 0.0, 3.0, 1.5, 0.25, key="gtt_g") / 100
    p = replace(gi, wacc_override=wacc, royalty=royalty)
    res = {n: models.gtt_value(s["h2"], s["orders"], s["marine"], s["g"], p) for n, s in models.GTT_SCENARIOS.items()}
    b = models.GTT_SCENARIOS["Base"]
    res["Custom"] = models.gtt_value(b["h2"], custom, b["marine"], g_custom, p)
    with right:
        cols = st.columns(4)
        for c, n in zip(cols, ("Bear", "Base", "Bull", "Custom")):
            label = f"{n} ({models.GTT_SCENARIOS[n]['orders']}/yr)" if n != "Custom" else f"Your case ({custom}/yr)"
            c.metric(label, f"€{res[n][0]:,.0f}", f"{res[n][0] / p.price - 1:+.0%} vs €{p.price:,.0f}")
        st.info(f"**Reverse DCF:** with everything else as in the base case, the price needs "
                f"**{models.gtt_implied_orders(p):.0f} orders a year** for 2027-35. GTT's own 10-year estimate is "
                f"about 60 (c.550 LNG carriers plus ethane carriers, FSRUs, FLNGs and onshore tanks).")
        hist = {2021: 314.7, 2022: 307.3, 2023: 427.7, 2024: 641.4, 2025: 803.0}
        rows = [dict(year=y, revenue=v, scenario="Actual") for y, v in hist.items()]
        rows += [dict(year=r["year"], revenue=r["revenue"], scenario=n) for n in res for r in res[n][1]]
        rows += [dict(year=2025, revenue=803.0, scenario=n) for n in res]
        df = pd.DataFrame(rows)
        dom = ["Actual", "Bear", "Base", "Bull", "Custom"]
        chart = alt.Chart(df).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=36)).encode(
            x=alt.X("year:O", title="Year"),
            y=alt.Y("revenue:Q", title="Revenue (€mm)"),
            color=alt.Color("scenario:N", scale=scenario_scale(dom), sort=dom, title=None),
            tooltip=["scenario", "year", alt.Tooltip("revenue:Q", format=",.0f", title="Revenue €mm")])
        st.altair_chart(style(chart.properties(title="Revenue: history, order book and scenarios")),
                        use_container_width=True)
        st.caption("2026-28 revenue is mostly already signed: the company publishes its order-book schedule "
                   "(€655mm in 2027, €603mm in 2028). After that it depends on new orders.")

# ---------------------------------------------------------------- JPMorgan
with tab_jpm:
    ji = models.JpmInputs()
    st.markdown(
        "**The question:** JPM is the best large US bank by most measures. At 3x tangible book, how good does it have "
        "to stay? A bank is valued on residual income: tangible equity plus the present value of returns above the "
        "cost of equity. **My view: quality at a full price.** Full pitch: `equity-research/pitches/JPM_pitch.md`; "
        "model: `valuation/jpm/`."
    )
    left, right = st.columns([1, 2.2])
    with left:
        coe = st.slider("Cost of equity (%)", 8.0, 13.0, round(ji.coe * 100, 2), 0.25, key="jpm_r") / 100
        g = st.slider("Terminal growth (%)", 2.0, 5.0, ji.g * 100, 0.25, key="jpm_g") / 100
        st.markdown("Long-run ROTE")
        lrs = {n: st.slider(f"{n} (%)", 8, 28, int(round(s["lr"] * 100)), 1, key=f"jpm_lr_{n}") / 100
               for n, s in models.JPM_SCENARIOS.items()}
    p = replace(ji, coe_override=coe, g=g)
    vals = {}
    for n, s in models.JPM_SCENARIOS.items():
        path = s["rote"][:5] + [lrs[n]] * 5 if lrs[n] != s["lr"] else s["rote"]
        vals[n] = models.jpm_value(path, lrs[n], s["payout"], p)
    probs = {"Bear": 0.25, "Base": 0.50, "Bull": 0.25}
    weighted = sum(vals[n] * probs[n] for n in vals)
    with right:
        cols = st.columns(4)
        for c, n in zip(cols, ("Bear", "Base", "Bull")):
            c.metric(f"{n} ({probs[n]:.0%})", f"${vals[n]:,.0f}", f"{vals[n] / p.price - 1:+.0%} vs price")
        cols[3].metric("Probability-weighted", f"${weighted:,.0f}", f"{weighted / p.price - 1:+.0%} vs ${p.price:,.0f}")
        st.info(f"**Reverse:** at {p.price / p.tbvps:.2f}x tangible book, the price needs a ROTE of "
                f"**{models.jpm_implied_rote(p):.1%} forever**. Management's through-the-cycle target is 17%; "
                f"Q3 2026 core ROTCE was 21%.")
        peers = pd.read_csv(ROOT / "valuation/jpm/data/peers.csv")
        line = pd.DataFrame({"rote": [x / 100 for x in range(8, 27)]})
        line["p_tbv"] = (line.rote - g) / (coe - g)
        pts = alt.Chart(peers).mark_circle(size=90, color="#2a78d6").encode(
            x=alt.X("rote:Q", title="ROTE, trailing 12 months", axis=alt.Axis(format="%"), scale=alt.Scale(domain=[0.08, 0.26])),
            y=alt.Y("p_tbv:Q", title="Price / tangible book"),
            tooltip=["bank", alt.Tooltip("rote:Q", format=".1%"), alt.Tooltip("p_tbv:Q", format=".2f")])
        labels = alt.Chart(peers).mark_text(dx=12, align="left", fontSize=11, color="#0b0b0b").encode(
            x="rote:Q", y="p_tbv:Q", text="bank")
        ref = alt.Chart(line).mark_line(color="#eb6834", strokeDash=[4, 3]).encode(x="rote:Q", y="p_tbv:Q")
        st.altair_chart(style((ref + pts + labels).properties(
            title="Large US banks: valuation vs returns (dashed: justified P/TBV at your r and g)")), use_container_width=True)
        st.caption("Banks above the dashed line trade at more than today's returns justify if they lasted forever.")

# ---------------------------------------------------------------- Adobe
with tab_adbe:
    ai = models.AdobeInputs()
    st.markdown(
        "**The question:** Adobe trades at ~15x earnings with a top-decile return on capital. That only makes sense if "
        "the market thinks generative AI will erode its products. Four scenarios, from AI as a tailwind to real "
        "disruption, ask how much erosion is already in the price. **My view: cheap.** Full pitch: "
        "`equity-research/pitches/ADBE_pitch.md`; Excel model: `valuation/adobe/`."
    )
    left, right = st.columns([1, 2.2])
    with left:
        wacc = st.slider("WACC (%)", 8.0, 13.0, round(ai.wacc * 100, 2), 0.25, key="adbe_w") / 100
        sbc_cash = st.toggle("Treat stock-based compensation (8% of revenue) as a cash cost", True, key="adbe_sbc")
        custom_g = st.slider("Your case: revenue growth FY2027-35 (% a year)", -8.0, 12.0, 5.0, 0.5, key="adbe_g") / 100
        custom_m = st.slider("Your case: operating margin from FY2030 (%)", 15, 45, 35, 1, key="adbe_m") / 100
        custom_tg = st.slider("Your case: terminal growth (%)", -2.0, 4.0, 2.5, 0.25, key="adbe_tg") / 100
    p = replace(ai, wacc_override=wacc, sbc_is_cash=sbc_cash)
    probs = {"Bull": 0.20, "Base": 0.40, "Erosion": 0.25, "Disruption": 0.15}
    vals = {n: models.adobe_value(s["g"], s["m"], s["tg"], p) for n, s in models.ADOBE_SCENARIOS.items()}
    custom = models.adobe_value((custom_g,) * 3, (custom_m,) * 2, custom_tg, p)
    weighted = sum(vals[n] * probs[n] for n in vals)
    with right:
        cols = st.columns(3)
        for c, n in zip(cols * 2, ("Bull", "Base", "Erosion", "Disruption")):
            c.metric(f"{n} ({probs[n]:.0%})", f"${vals[n]:,.0f}", f"{vals[n] / p.price - 1:+.0%} vs price")
        cols[1].metric("Probability-weighted", f"${weighted:,.0f}", f"{weighted / p.price - 1:+.0%} vs ${p.price:,.0f}")
        cols[2].metric("Your case", f"${custom:,.0f}", f"{custom / p.price - 1:+.0%} vs price")
        st.info(f"**Reverse DCF:** on the base-case revenue path, the price needs a flat operating margin of "
                f"**{models.adobe_implied_margin(p):.1%}** from FY2027 (after SBC). FY2026 is ~37%.")
        hist = pd.read_csv(ROOT / "valuation/adobe/data/adbe_annual_raw.csv", index_col=0)["Revenue"] / 1e9
        rows = [dict(year=int(y[2:]), revenue=v, scenario="Actual") for y, v in hist.items() if int(y[2:]) >= 2018]
        for n, s in models.ADOBE_SCENARIOS.items():
            growth, _ = models.adobe_paths(s["g"], s["m"], p)
            rev = p.rev0
            rows += [dict(year=2025, revenue=p.rev_prev / 1e3, scenario=n), dict(year=2026, revenue=rev / 1e3, scenario=n)]
            for t, gr in enumerate(growth, start=2027):
                rev *= 1 + gr
                rows.append(dict(year=t, revenue=rev / 1e3, scenario=n))
        df = pd.DataFrame(rows)
        dom = ["Actual", "Bull", "Base", "Erosion", "Disruption"]
        chart = alt.Chart(df).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=36)).encode(
            x=alt.X("year:O", title="Fiscal year (ends late November)"),
            y=alt.Y("revenue:Q", title="Revenue ($bn)"),
            color=alt.Color("scenario:N", scale=scenario_scale(dom), sort=dom, title=None),
            tooltip=["scenario", "year", alt.Tooltip("revenue:Q", format=",.1f", title="Revenue $bn")])
        st.altair_chart(style(chart.properties(title="Revenue: history and scenarios")), use_container_width=True)
        st.caption("FY2026 is the company's guidance midpoint. Turning off the SBC switch raises every value by "
                   "25-40%, which is why it's visible here.")

# ---------------------------------------------------------------- Deckers
with tab_deck:
    di = models.DeckersInputs()
    st.markdown(
        "**The question:** Deckers owns HOKA and UGG, earns a 21-23% operating margin, has no debt and trades at ~10x "
        "forward earnings. The market is pricing a fade in both brands. Revenue is built brand by brand, because "
        "that's where the debate is. **My view: cheap.** The price is roughly the fade case. Full pitch: "
        "`equity-research/pitches/DECK_pitch.md`; Excel model: `valuation/deckers/`."
    )
    left, right = st.columns([1, 2.2])
    with left:
        wacc = st.slider("WACC (%)", 8.0, 13.0, round(di.wacc * 100, 2), 0.25, key="deck_w") / 100
        h = st.slider("Your case: HOKA growth FY2028-36 (% a year)", -4.0, 14.0, 6.0, 0.5, key="deck_h") / 100
        u = st.slider("Your case: UGG growth FY2028-36 (% a year)", -10.0, 6.0, 1.0, 0.5, key="deck_u") / 100
        m = st.slider("Your case: operating margin from FY2028 (%)", 10.0, 26.0, 21.5, 0.5, key="deck_m") / 100
        tg = st.slider("Your case: terminal growth (%)", 0.0, 4.0, 2.5, 0.25, key="deck_tg") / 100
    p = replace(di, wacc_override=wacc)
    res = {n: models.deckers_value(s["h"], s["u"], s["m"], s["tg"], p) for n, s in models.DECKERS_SCENARIOS.items()}
    res["Custom"] = models.deckers_value((h,) * 3, (u,) * 3, (m,) * 3, tg, p)
    probs = models.DECKERS_PROBS
    weighted = sum(res[n][0] * probs[n] for n in probs)
    with right:
        cols = st.columns(3)
        for c, n in zip(cols * 2, ("Bull", "Base", "Fade", "Bust")):
            c.metric(f"{n} ({probs[n]:.0%})", f"${res[n][0]:,.0f}", f"{res[n][0] / p.price - 1:+.0%} vs price")
        cols[1].metric("Probability-weighted", f"${weighted:,.0f}", f"{weighted / p.price - 1:+.0%} vs ${p.price:,.0f}")
        cols[2].metric("Your case", f"${res['Custom'][0]:,.0f}", f"{res['Custom'][0] / p.price - 1:+.0%} vs price")
        st.info(f"**Reverse DCF:** on the base-case brand paths, the price needs a flat operating margin of only "
                f"**{models.deckers_implied_margin(p):.1%}** from FY2028. The FY2027 underlying margin, without "
                f"one-off tariff refunds, is ~21.5%.")
        hist = pd.read_csv(ROOT / "valuation/deckers/data/deck_annual_raw.csv", index_col=0)["Revenue"] / 1e9
        rows = [dict(year=int(y[2:]), revenue=v, scenario="Actual") for y, v in hist.items() if int(y[2:]) >= 2019]
        rows += [dict(year=2026, revenue=p.rev26 / 1e3, scenario=n) for n in res]
        rows += [dict(year=r["year"], revenue=r["revenue"] / 1e3, scenario=n) for n in res for r in res[n][1]]
        df = pd.DataFrame(rows)
        dom = ["Actual", "Bull", "Base", "Fade", "Bust", "Custom"]
        chart = alt.Chart(df).mark_line(strokeWidth=2, point=alt.OverlayMarkDef(size=36)).encode(
            x=alt.X("year:O", title="Fiscal year (ends 31 March)"),
            y=alt.Y("revenue:Q", title="Revenue ($bn)"),
            color=alt.Color("scenario:N", scale=scenario_scale(dom), sort=dom, title=None),
            tooltip=["scenario", "year", alt.Tooltip("revenue:Q", format=",.2f", title="Revenue $bn")])
        st.altair_chart(style(chart.properties(title="Revenue: history and scenarios")), use_container_width=True)
        st.caption("FY2027 is the company's guidance ($5.71bn). In the Fade case UGG goes out of fashion as it did in "
                   "FY2015-17 and HOKA becomes a normal running brand.")

# ---------------------------------------------------------------- Monte Carlo (precomputed by valuation/monte_carlo.py)
with tab_mc:
    st.markdown("Three scenarios hide how likely each one is. Here each model is run on **20,000 random sets of "
                "assumptions** (distributions centred on the base case; see valuation/README.md).")
    mc = pd.read_csv(ROOT / "valuation/results/monte_carlo_summary.csv")
    width = pd.read_csv(ROOT / "valuation/results/monte_carlo_width.csv")
    cols = st.columns(len(mc))
    for c, (_, r) in zip(cols, mc.iterrows()):
        cur = "\\$" if r.currency == "$" else "€"   # escaped: Streamlit reads $...$ as LaTeX
        wide = width[(width.company == r.company) & (width.width == 1.5)].prob_above_price.iloc[0]
        c.metric(f"{r.company}: runs worth more than the price", f"{r.prob_above_price:.1%}",
                 f"{wide:.0%} with 1.5x wider uncertainty", delta_color="off")
        c.caption(f"Median {cur}{r['median']:,.0f} · 5th-95th percentile {cur}{r.p5:,.0f}-{cur}{r.p95:,.0f} · "
                  f"price {cur}{r.price:,.0f} · main driver: {r.top_driver.split(' ')[0]}")
        c.image(str(ROOT / f"valuation/figures/mc_{r.company.lower()}.png"))
