"""
Scatter plots: pairwise params coloured by max selection_score.
Each cell = max score over all configs sharing that (x, y) pair (marginalising the third param).

Produces PGF files in sweep/ and results/publication/:
  isco_params_plot.pgf   — 3 panels: w_isco x w_isco_task x w_occ
  task_params_plot.pgf   — 1 panel:  w_soc_title x w_dwa
"""
import os
import shutil
os.environ["PATH"] += r";C:\Users\einianma\AppData\Local\texlive\2026\bin\windows"

import matplotlib
matplotlib.use("pgf")
matplotlib.rcParams.update({
    "pgf.texsystem": "xelatex",
    "font.family": "serif",
    "text.usetex": False,
    "pgf.rcfonts": False,
})
import pandas as pd
import matplotlib.pyplot as plt

CSV = "results/summary/sweep_results_metrics_only.csv"
PUB_DIR = "results/publication"

df = pd.read_csv(CSV, low_memory=False)
df = df[df["dataset_name"].str.startswith("r")].copy()

ALL_PARAMS = ["w_soc_title", "w_dwa", "w_isco", "w_isco_task", "w_occ"]
df[ALL_PARAMS] = df[ALL_PARAMS].round(4)

def _sweep_score(row) -> float:
    cov      = float(row.get("S5_FINAL_isco_coverage_share") or 0)
    sim      = float(row.get("S5_FINAL_mean_similarity_retained") or 0)
    overload = float(row.get("S5_FINAL_share_tasks_in_overloaded_isco") or 0)
    gini     = float(row.get("S5_FINAL_gini_tasks_per_isco") or 0)
    return (3*cov + 2*sim - 2*overload - 2*gini) / 9

df["sweep_score"] = df.apply(_sweep_score, axis=1)
vmin = df["sweep_score"].quantile(0.10)
vmax = df["sweep_score"].max()
cmap = "viridis"
best = df.nlargest(1, "sweep_score").iloc[0]


def make_plot(pairs, title, out):
    ncols = len(pairs)
    fig, axes = plt.subplots(1, ncols, figsize=(5 * ncols, 4.5))
    if ncols == 1:
        axes = [axes]
    fig.suptitle(title, fontsize=12, y=1.01)

    for ax, (xp, yp, _) in zip(axes, pairs):
        cell = df.groupby([xp, yp])["sweep_score"].max().reset_index()
        sc = ax.scatter(cell[xp], cell[yp], c=cell["sweep_score"],
                        cmap=cmap, vmin=vmin, vmax=vmax,
                        s=30, edgecolors="none")
        ax.scatter(best[xp], best[yp], marker="*", s=120, color="red", zorder=5)
        # adaptive annotation offset: push label away from the nearest edge
        bx, by = float(best[xp]), float(best[yp])
        off_x = -55 if bx > 0.5 else 6
        off_y = -12 if by > 0.5 else 6
        ax.annotate(f"best ({best['sweep_score']:.4f})",
                    xy=(bx, by),
                    xytext=(off_x, off_y), textcoords="offset points",
                    fontsize=7, color="red",
                    bbox=dict(boxstyle="round,pad=0.2", fc="white", alpha=0.7, ec="none"))
        ax.set_xlim(0, 1)
        ax.set_ylim(0, 1)
        ax.set_xlabel(xp, fontsize=10)
        ax.set_ylabel(yp, fontsize=10)
        ax.set_title(f"{xp} x {yp}", fontsize=10)
        plt.colorbar(sc, ax=ax, label="max score")

    plt.tight_layout()
    pgf_out = out.replace(".png", ".pgf")
    plt.savefig(out, bbox_inches="tight", dpi=150)
    plt.savefig(pgf_out, bbox_inches="tight")
    plt.close()
    # copy PGF and all companion raster images to publication dir
    stem = os.path.splitext(os.path.basename(pgf_out))[0]
    sweep_dir = os.path.dirname(pgf_out)
    for fname in [os.path.basename(out), os.path.basename(pgf_out)] + [
        f for f in os.listdir(sweep_dir) if f.startswith(stem + "-img")
    ]:
        shutil.copy(os.path.join(sweep_dir, fname), os.path.join(PUB_DIR, fname))
    print(f"Saved {pgf_out} + companions -> {PUB_DIR}")


make_plot(
    pairs=[
        ("w_isco",      "w_isco_task", "w_occ"),
        ("w_isco",      "w_occ",       "w_isco_task"),
        ("w_isco_task", "w_occ",       "w_isco"),
    ],
    title="ISCO-side parameter sweep — max sweep_score per cell\n(marginalised over third parameter)",
    out="sweep/isco_params_plot.png",
)

make_plot(
    pairs=[("w_soc_title", "w_dwa", None)],
    title="Query-side (task) parameter sweep — max sweep_score per cell",
    out="sweep/task_params_plot.png",
)
