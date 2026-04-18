"""
3_visualize_sweep.py
====================
Visualizations for the focused sweep results (output/sweep_focused/sweep_results.csv).

Outputs (all saved to output/sweep_focused/):
  1. heatmap_dwa_soc.png           — mean selection_score heatmap: w_dwa × w_soc_title
                                     for each of the 3 ISCO settings (grid variants only)
  2. pareto_3d_focused.png         — 3D scatter of Pareto candidates
  3. param_effects_focused.png     — selection_score vs each key parameter (all variants)
  4. pareto_coverage_sim.png       — Pareto front coloured by max_links_per_task

Run from the project root:
    python sweep/3_visualize_sweep.py
"""

from __future__ import annotations

import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
from matplotlib.colors import Normalize
from matplotlib.cm import ScalarMappable

ROOT_DIR  = Path(__file__).resolve().parent.parent
SWEEP_OUT = ROOT_DIR / "output" / "sweep_focused"
results   = pd.read_csv(SWEEP_OUT / "sweep_results.csv")

grid    = results[results["dataset_name"].str.startswith("fg_")].copy()
random  = results[results["dataset_name"].str.startswith("fr")].copy()
pareto  = results[results["pareto_candidate"] == True].copy()

print(f"Total: {len(results)}  |  Grid: {len(grid)}  |  Random: {len(random)}  |  Pareto: {len(pareto)}")

# ── 1. Heatmaps: w_dwa × w_soc_title for each ISCO setting ───────────────────
print("\n[1] Heatmaps...")
isco_labels = {0.0: "ESCO-only (w_isco=0.0)", 0.4: "Mixed (w_isco=0.4)", 0.8: "ISCO-heavy (w_isco=0.8)"}
isco_vals   = [0.0, 0.4, 0.8]

fig, axes = plt.subplots(1, 3, figsize=(16, 5), sharey=True)

vmin = grid["selection_score"].min()
vmax = grid["selection_score"].max()

for ax, w_isco_target in zip(axes, isco_vals):
    sub = grid[np.isclose(grid["w_isco"], w_isco_target, atol=0.05)].copy()
    if sub.empty:
        ax.set_title(f"w_isco≈{w_isco_target} (no data)")
        continue

    pivot = sub.pivot_table(
        index="w_dwa", columns="w_soc_title", values="selection_score", aggfunc="mean"
    )
    pivot = pivot.sort_index(ascending=False)

    im = ax.imshow(pivot.values, aspect="auto", vmin=vmin, vmax=vmax,
                   cmap="RdYlGn", origin="upper")
    ax.set_xticks(range(len(pivot.columns)))
    ax.set_xticklabels([f"{v:.2f}" for v in pivot.columns], rotation=45, ha="right", fontsize=8)
    ax.set_yticks(range(len(pivot.index)))
    ax.set_yticklabels([f"{v:.2f}" for v in pivot.index], fontsize=8)
    ax.set_xlabel("w_soc_title", fontsize=10)
    ax.set_ylabel("w_dwa", fontsize=10)
    ax.set_title(isco_labels.get(w_isco_target, f"w_isco≈{w_isco_target}"), fontsize=11)

    for i in range(len(pivot.index)):
        for j in range(len(pivot.columns)):
            val = pivot.values[i, j]
            if not np.isnan(val):
                ax.text(j, i, f"{val:.3f}", ha="center", va="center",
                        fontsize=6.5, color="black" if val > (vmin+vmax)/2 else "white")

fig.colorbar(im, ax=axes[-1], label="selection_score")
fig.suptitle("Focused sweep: selection_score heatmap  (w_dwa × w_soc_title, max_links=1)\n"
             "Each cell = mean over the 3 crosswalk grid variants; higher = better", fontsize=11)
plt.tight_layout()
out = SWEEP_OUT / "heatmap_dwa_soc.png"
fig.savefig(out, dpi=150, bbox_inches="tight")
plt.close(fig)
print(f"  Saved: {out}")

# ── 2. 3D Pareto scatter ──────────────────────────────────────────────────────
print("\n[2] 3D Pareto scatter...")
cov_col  = "S5_FINAL_isco_coverage_share"
sim_col  = "S5_FINAL_mean_similarity_retained"
gini_col = "S5_FINAL_gini_tasks_per_isco"

p3 = pareto[[cov_col, sim_col, gini_col, "w_dwa", "w_soc_title", "max_links_per_task",
             "selection_score", "dataset_name"]].dropna()

fig = plt.figure(figsize=(10, 7))
ax  = fig.add_subplot(111, projection="3d")

sc = ax.scatter(
    p3["w_dwa"], p3["w_soc_title"], p3[sim_col],
    c=p3["selection_score"], cmap="plasma",
    s=60, alpha=0.8, edgecolors="none",
)
ax.set_xlabel("w_dwa", fontsize=10)
ax.set_ylabel("w_soc_title", fontsize=10)
ax.set_zlabel("mean_similarity", fontsize=10)
ax.set_title(f"Focused sweep: {len(p3)} Pareto candidates\n"
             "axes: w_dwa × w_soc_title × mean_similarity  |  colour: selection_score", fontsize=10)
fig.colorbar(sc, ax=ax, shrink=0.6, label="selection_score")
plt.tight_layout()
out = SWEEP_OUT / "pareto_3d_focused.png"
fig.savefig(out, dpi=150)
plt.close(fig)
print(f"  Saved: {out}")

# ── 3. Parameter effects (all variants) ──────────────────────────────────────
print("\n[3] Parameter effects...")
params = ["w_dwa", "w_soc_title", "w_isco", "w_isco_task", "w_occ",
          "min_sim", "margin_best", "max_links_per_task"]
params = [p for p in params if p in results.columns]

ncols = 4
nrows = int(np.ceil(len(params) / ncols))
fig, axes = plt.subplots(nrows, ncols, figsize=(14, 3.5 * nrows))
axes = axes.flatten()

for ax, param in zip(axes, params):
    x = results[param]
    y = results["selection_score"]
    ax.scatter(x, y, s=6, alpha=0.3, color="C0", label="all")
    pareto_x = pareto[param]
    pareto_y = pareto["selection_score"]
    ax.scatter(pareto_x, pareto_y, s=20, alpha=0.8, color="red", zorder=5, label="Pareto")
    if results[param].nunique() > 10:
        order = x.argsort()
        xsort, ysort = x.iloc[order].values, y.iloc[order].values
        w = max(1, len(xsort) // 20)
        roll = pd.Series(ysort).rolling(w, center=True, min_periods=1).median()
        ax.plot(xsort, roll, color="C1", linewidth=2, label="rolling median")
    ax.set_xlabel(param, fontsize=9)
    ax.set_ylabel("selection_score", fontsize=9)
    ax.set_title(param, fontsize=10)
    ax.grid(True, alpha=0.3)
    ax.legend(fontsize=7)

for ax in axes[len(params):]:
    ax.set_visible(False)

fig.suptitle("Focused sweep: selection_score vs each parameter\n"
             "(red = Pareto candidates)", fontsize=12)
plt.tight_layout()
out = SWEEP_OUT / "param_effects_focused.png"
fig.savefig(out, dpi=150)
plt.close(fig)
print(f"  Saved: {out}")

# ── 4. Pareto front: coverage vs similarity, coloured by max_links ────────────
print("\n[4] Pareto coverage vs similarity...")
fig, ax = plt.subplots(figsize=(9, 6))
for links in sorted(pareto["max_links_per_task"].unique()):
    sub = pareto[pareto["max_links_per_task"] == links]
    ax.scatter(sub[cov_col], sub[sim_col],
               label=f"max_links={int(links)}", s=60, alpha=0.8, zorder=5)

top10 = results[results["pareto_candidate"] != True].nlargest(20, "selection_score")
ax.scatter(top10[cov_col], top10[sim_col],
           c="lightgray", s=25, alpha=0.5, zorder=3, label="top-20 non-Pareto")

for _, row in results.nlargest(5, "selection_score").iterrows():
    if cov_col in row and sim_col in row:
        ax.annotate(row["dataset_name"],
                    xy=(row[cov_col], row[sim_col]),
                    xytext=(5, 5), textcoords="offset points",
                    fontsize=7, color="black")

ax.set_xlabel("ISCO coverage share", fontsize=11)
ax.set_ylabel("Mean similarity retained", fontsize=11)
ax.set_title(f"Focused sweep Pareto front ({len(pareto)} candidates)\n"
             "coloured by max_links_per_task", fontsize=11)
ax.legend(fontsize=9)
ax.grid(True, alpha=0.3)
plt.tight_layout()
out = SWEEP_OUT / "pareto_coverage_sim.png"
fig.savefig(out, dpi=150)
plt.close(fig)
print(f"  Saved: {out}")

# ── Summary ───────────────────────────────────────────────────────────────────
print(f"\nTop 5 (focused sweep):")
display_cols = ["dataset_name", "selection_rank", "selection_score",
                "w_isco", "w_dwa", "w_soc_title", "min_sim", "max_links_per_task",
                cov_col, sim_col, gini_col]
available = [c for c in display_cols if c in results.columns]
print(results[available].head(5).to_string(index=False))
