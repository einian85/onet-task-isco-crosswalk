"""
Scatter plots: pairwise params coloured by max selection_score.
Each cell = max score over all configs sharing that (x, y) pair (marginalising the third param).

Produces PGF files in sweep/ and results/publication/:
  isco_params_plot.pgf   — 3 panels: w_isco x w_isco_task x w_occ
  isco_params_3d.pgf     — same three params as one 3D scatter (full space + zoom)
  task_params_plot.pgf   — 1 panel:  w_soc_title x w_dwa
"""
import itertools
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
    "pgf.preamble": r"\usepackage{amsmath}",
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
    cov      = float(row.get("S2_TASK_FILTER_isco_coverage_share") or 0)
    sim      = float(row.get("S2_TASK_FILTER_mean_similarity_retained") or 0)
    overload = float(row.get("S2_TASK_FILTER_share_tasks_in_overloaded_isco") or 0)
    gini     = float(row.get("S2_TASK_FILTER_gini_tasks_per_isco") or 0)
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
    _save(out)


def _save(out):
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


def make_3d_plot(out, zoom_round="r4_", elev=22, azim=-55):
    """One point per (w_isco, w_isco_task, w_occ) triple, coloured by the max
    sweep_score over the query-side params. Panel (a) is the full unit cube;
    panel (b) zooms into the search box of `zoom_round` (outlined in (a)) on
    the same colour scale. Sized to the journal text width (4.9in)."""
    X, Y, Z = "w_isco", "w_isco_task", "w_occ"
    labels = {X: r"$w_{\text{isco}}$", Y: r"$w_{\text{isco-task}}$", Z: r"$w_{\text{occ}}$"}
    cell = (df.groupby([X, Y, Z])["sweep_score"].max().reset_index()
              .sort_values("sweep_score"))  # best points drawn last, on top
    rz = df[df["dataset_name"].str.startswith(zoom_round)]
    full = {c: (0.0, 1.0) for c in (X, Y, Z)}
    zoom = {c: (rz[c].min(), rz[c].max()) for c in (X, Y, Z)}
    in_zoom = cell[cell[X].between(*zoom[X]) & cell[Y].between(*zoom[Y])
                   & cell[Z].between(*zoom[Z])]
    bx, by, bz = float(best[X]), float(best[Y]), float(best[Z])

    def panel(rect, data, lims, title):
        ax = fig.add_axes(rect, projection="3d")
        ax.computed_zorder = False  # keep draw order so the star is never hidden
        ax.view_init(elev=elev, azim=azim)
        sc = ax.scatter(data[X], data[Y], data[Z], c=data["sweep_score"], cmap=cmap,
                        vmin=vmin, vmax=vmax, s=9, edgecolors="none", depthshade=False)
        ax.plot([bx, bx], [by, by], [lims[Z][0], bz], color="red", lw=0.8, ls="--")
        ax.scatter([bx], [by], [bz], marker="*", s=110, color="red",
                   edgecolors="white", linewidths=0.6, depthshade=False)
        ax.set_xlim(*lims[X]); ax.set_ylim(*lims[Y]); ax.set_zlim(*lims[Z])
        ax.set_xlabel(labels[X], fontsize=9, labelpad=2)
        ax.set_ylabel(labels[Y], fontsize=9, labelpad=2)
        ax.set_zlabel(labels[Z], fontsize=9, labelpad=2)
        ax.tick_params(labelsize=7, pad=0)
        ax.set_box_aspect(None, zoom=0.9)
        ax.text2D(0.03, 0.97, title, transform=ax.transAxes, fontsize=9, va="top")
        return ax, sc

    fig = plt.figure(figsize=(4.9, 5.6))
    ax, sc = panel([0.0, 0.5, 0.80, 0.5], cell, full, "(a) Full search space")
    cb = fig.colorbar(sc, cax=fig.add_axes([0.86, 0.25, 0.03, 0.5]), extend="min")
    cb.set_label("max sweep score", fontsize=8)
    cb.ax.tick_params(labelsize=7, pad=0)
    corners = list(itertools.product(*(zoom[c] for c in (X, Y, Z))))
    for a, b in itertools.combinations(corners, 2):
        if sum(u != v for u, v in zip(a, b)) == 1:  # cube edges only
            ax.plot(*zip(a, b), color="0.3", lw=0.6)
    panel([0.0, 0.0, 0.80, 0.5], in_zoom, zoom,
          f"(b) Zoom: rounds {zoom_round[1]}--6 search region")
    _save(out)


make_plot(
    pairs=[
        ("w_isco",      "w_isco_task", "w_occ"),
        ("w_isco",      "w_occ",       "w_isco_task"),
        ("w_isco_task", "w_occ",       "w_isco"),
    ],
    title="ISCO-side parameter sweep — max sweep_score per cell\n(marginalised over third parameter)",
    out="sweep/isco_params_plot.png",
)

make_3d_plot(out="sweep/isco_params_3d.png")

make_plot(
    pairs=[("w_soc_title", "w_dwa", None)],
    title="Query-side (task) parameter sweep — max sweep_score per cell",
    out="sweep/task_params_plot.png",
)
