"""ROE transition heatmap from results/05_roe_persistence.csv (run run_queries.py first)."""
from pathlib import Path
import pandas as pd, matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.colors import LinearSegmentedColormap

HERE = Path(__file__).parent
df = pd.read_csv(HERE / "results" / "05_roe_persistence.csv").set_index("roe_quintile_start")
m = df[["to_q1_lowest", "to_q2", "to_q3", "to_q4", "to_q5_highest"]].values * 100
cmap = LinearSegmentedColormap.from_list("blue", ["#f0f5fc", "#86b6ef", "#2a78d6", "#104281"])
fig, ax = plt.subplots(figsize=(6.4, 4.6), facecolor="#fcfcfb")
ax.imshow(m, cmap=cmap, vmin=0, vmax=60)
for i in range(5):
    for j in range(5):
        ax.text(j, i, f"{m[i, j]:.0f}%", ha="center", va="center", fontsize=10, color="white" if m[i, j] > 35 else "#0b0b0b")
labels = ["Q1\nlowest", "Q2", "Q3", "Q4", "Q5\nhighest"]
ax.set_xticks(range(5), labels, color="#52514e"); ax.set_yticks(range(5), labels, color="#52514e")
ax.set_xlabel("ROE quintile three years later", color="#52514e"); ax.set_ylabel("ROE quintile at start", color="#52514e")
ax.set_title("Where companies end up three years later", loc="left", fontweight="bold", color="#0b0b0b")
for s in ax.spines.values(): s.set_visible(False)
fig.text(0.01, 0.01, "US stocks, revenue > $100mm, start years 2014-2021. 20% in every cell would mean no persistence.",
         color="#898781", fontsize=7.5)
fig.tight_layout(rect=(0, 0.03, 1, 1))
(HERE / "figures").mkdir(exist_ok=True)
fig.savefig(HERE / "figures" / "roe_persistence.png", dpi=160)
print("ok")
