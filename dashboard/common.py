"""Shared paths, colours and chart helpers for the dashboard pages."""
import sys
from pathlib import Path

import altair as alt

ROOT = Path(__file__).resolve().parent.parent
DASH = ROOT / "dashboard"
sys.path.insert(0, str(ROOT / "valuation"))   # models.py lives with the Excel models

# Categorical colours (validated for colour-blind separation); scenario colours follow the scenario, not its rank
SCENARIO_COLORS = {"Bear": "#eb6834", "Base": "#2a78d6", "Bull": "#1baf7a", "Custom": "#4a3aa7", "Actual": "#52514e",
                   "Erosion": "#eb6834", "Fade": "#eb6834", "Disruption": "#9c2f1c", "Bust": "#9c2f1c"}
BLUE = "#2a78d6"


def scenario_scale(domain):
    return alt.Scale(domain=domain, range=[SCENARIO_COLORS[d] for d in domain])


def style(chart, height=320):
    return (chart.properties(height=height)
            .configure_axis(grid=True, gridColor="#e1e0d9", domainColor="#c3c2b7", labelColor="#52514e",
                            titleColor="#52514e", labelFontSize=11, titleFontSize=11)
            .configure_legend(labelColor="#0b0b0b", titleColor="#52514e", orient="top")
            .configure_view(strokeWidth=0))
