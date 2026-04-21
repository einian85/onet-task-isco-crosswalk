from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from config import RunConfig, compute_run_id, get_code_version, load_yaml_or_json


def _save_fig(fig: plt.Figure, png_path: Path) -> None:
    """Save figure as PNG, PDF and PGF (all in the same results directory)."""
    fig.savefig(png_path, dpi=200, bbox_inches="tight")
    for suffix, fmt in [(".pdf", "pdf"), (".pgf", "pgf")]:
        try:
            fig.savefig(str(png_path.with_suffix(suffix)), format=fmt, bbox_inches="tight")
        except Exception:
            pass


PLOT_STYLE = {
    "figure.figsize": (10, 6),
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.spines.top": False,
    "axes.spines.right": False,
}

SWEEP_PARAMS = [
    "min_sim",
    "margin_best",
    "max_links_per_task",
    "w_occ",
    "k_retrieve",
    "overload_abs",
    "overload_quantile",
    "overload_min_sim",
    "overload_margin_best",
]

STAGE_ORDER = ["S1_RETRIEVE", "S2_TASK_FILTER", "S3_COVERAGE", "S4_OVERLOAD", "S5_FINAL"]

STAGE_LABELS = {
    "S1_RETRIEVE": "S1: Retrieve",
    "S2_TASK_FILTER": "S2: Task filter",
    "S3_COVERAGE": "S3: Coverage",
    "S4_OVERLOAD": "S4: Overload",
    "S5_FINAL": "S5: Final",
}

DATASET_META = {
    "onet292_id": {
        "label": "O*NET 29.2 (Task-ID, latest SOC 2018)",
        "short": "29.2-ID",
        "config_path": "config_onet29.yaml",
    },
    "onet250_id": {
        "label": "O*NET 25.0 (Task-ID, latest SOC 2010)",
        "short": "25.0-ID",
        "config_path": "config_onet25.yaml",
    },
}


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_cfg(path: str) -> RunConfig:
    return RunConfig(**load_yaml_or_json(path))


def latest_run_ids() -> dict[str, dict[str, str]]:
    code_version = get_code_version()
    out: dict[str, dict[str, str]] = {}
    for dataset_id, meta in DATASET_META.items():
        cfg = load_cfg(meta["config_path"])
        out[dataset_id] = {
            "run_id": compute_run_id(cfg, code_version, cfg.data_version),
            "label": meta["label"],
            "short": meta["short"],
        }
    return out


def load_metrics_for_run(run_id: str) -> pd.DataFrame:
    path = Path("results/metrics") / run_id / "metrics.csv"
    return pd.read_csv(path)


def build_baseline_stage_table(run_ids: dict[str, dict[str, str]]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for dataset_id, info in run_ids.items():
        run_id = info["run_id"]
        metrics = load_metrics_for_run(run_id).copy()
        metrics["dataset_id"] = dataset_id
        metrics["dataset"] = info["label"]
        metrics["dataset_short"] = info["short"]
        rows.append(metrics)
    df = pd.concat(rows, ignore_index=True)
    df["stage"] = pd.Categorical(df["stage"], categories=STAGE_ORDER, ordered=True)
    return df.sort_values(["dataset_id", "stage"]).reset_index(drop=True)


def build_s5_summary(stage_df: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "dataset_id",
        "dataset",
        "dataset_short",
        "run_id",
        "isco_coverage_share",
        "mean_similarity_retained",
        "mean_links_per_task",
        "share_tasks_in_overloaded_isco",
        "gini_tasks_per_isco",
        "tasks_per_isco_mean",
        "tasks_per_isco_p95",
        "tasks_per_isco_max",
        "retrieval_lowconf_share",
    ]
    s5 = stage_df.loc[stage_df["stage"] == "S5_FINAL", keep].copy()
    s5 = s5.rename(
        columns={
            "isco_coverage_share": "S5_coverage",
            "mean_similarity_retained": "S5_mean_similarity",
            "mean_links_per_task": "S5_mean_links_per_task",
            "share_tasks_in_overloaded_isco": "S5_overloaded_task_share",
            "gini_tasks_per_isco": "S5_gini_tasks_per_isco",
            "tasks_per_isco_mean": "S5_tasks_per_isco_mean",
            "tasks_per_isco_p95": "S5_tasks_per_isco_p95",
            "tasks_per_isco_max": "S5_tasks_per_isco_max",
            "retrieval_lowconf_share": "S5_lowconf_share",
        }
    )
    return s5.sort_values("dataset_id").reset_index(drop=True)


def identify_sweep_change(row: pd.Series, baseline: pd.Series) -> tuple[str, str]:
    changed = []
    for param in SWEEP_PARAMS:
        if param not in row.index or param not in baseline.index:
            continue
        if pd.isna(row[param]) and pd.isna(baseline[param]):
            continue
        if row[param] != baseline[param]:
            changed.append((param, row[param]))
    if not changed:
        return ("baseline", "baseline")
    if len(changed) == 1:
        return (changed[0][0], str(changed[0][1]))
    return ("multiple", "; ".join(f"{k}={v}" for k, v in changed))


def infer_sweep_baseline(df: pd.DataFrame) -> pd.Series:
    delta_cols = [f"delta_{param}" for param in SWEEP_PARAMS if f"delta_{param}" in df.columns]
    if delta_cols:
        zero_mask = pd.Series(True, index=df.index)
        for col in delta_cols:
            vals = pd.to_numeric(df[col], errors="coerce").fillna(0.0)
            zero_mask &= vals.abs() < 1e-12
        candidates = df.loc[zero_mask]
        if not candidates.empty:
            return candidates.iloc[0]
    # Fallback: most common/default-like row, using the lowest selection rank if available.
    sort_cols = [col for col in ["selection_rank", "run_id"] if col in df.columns]
    if sort_cols:
        return df.sort_values(sort_cols).iloc[0]
    return df.iloc[0]


def build_sweep_tables() -> tuple[pd.DataFrame, pd.DataFrame] | tuple[None, None]:
    path = Path("results/summary/sweep_results_metrics_only.csv")
    if not path.exists():
        return None, None
    df = pd.read_csv(path)
    baseline = infer_sweep_baseline(df)
    change_info = df.apply(lambda row: identify_sweep_change(row, baseline), axis=1)
    df["changed_param"] = [c[0] for c in change_info]
    df["changed_value"] = [c[1] for c in change_info]

    top_cols = [
        "run_id",
        "selection_rank",
        "selection_score",
        "pareto_candidate",
        "changed_param",
        "changed_value",
        "S5_FINAL_isco_coverage_share",
        "S5_FINAL_mean_similarity_retained",
        "S5_FINAL_mean_links_per_task",
        "S5_FINAL_share_tasks_in_overloaded_isco",
        "S5_FINAL_gini_tasks_per_isco",
    ]
    top_table = df[top_cols].sort_values(["selection_rank", "run_id"]).head(12).reset_index(drop=True)

    per_param_rows = []
    for param in sorted(set(df["changed_param"]) - {"baseline", "multiple"}):
        subset = df.loc[df["changed_param"] == param].sort_values(["selection_rank", "selection_score"], ascending=[True, False])
        if subset.empty:
            continue
        best = subset.iloc[0]
        per_param_rows.append(
            {
                "parameter": param,
                "recommended_value": best[param],
                "run_id": best["run_id"],
                "selection_rank": best["selection_rank"],
                "selection_score": best["selection_score"],
                "S5_coverage": best["S5_FINAL_isco_coverage_share"],
                "S5_mean_similarity": best["S5_FINAL_mean_similarity_retained"],
                "S5_mean_links_per_task": best["S5_FINAL_mean_links_per_task"],
                "S5_overloaded_task_share": best["S5_FINAL_share_tasks_in_overloaded_isco"],
            }
        )
    per_param_table = pd.DataFrame(per_param_rows).sort_values("parameter").reset_index(drop=True)
    return top_table, per_param_table


def save_table(df: pd.DataFrame, out_dir: Path, name: str) -> Path:
    path = out_dir / f"{name}.csv"
    df.to_csv(path, index=False)
    return path


def plot_baseline_s5(summary_df: pd.DataFrame, out_dir: Path) -> Path:
    plt.rcParams.update(PLOT_STYLE)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8))
    metrics = [
        ("S5_coverage", "Coverage"),
        ("S5_mean_similarity", "Mean similarity"),
        ("S5_mean_links_per_task", "Mean links/task"),
        ("S5_overloaded_task_share", "Overloaded task share"),
    ]
    dataset_display = {"29.2-ID": "O*NET 29.2", "25.0-ID": "O*NET 25.0"}
    disp_datasets = summary_df["dataset_short"].map(dataset_display).fillna(summary_df["dataset_short"])
    for ax, (col, title) in zip(axes.flatten(), metrics):
        ax.bar(disp_datasets, summary_df[col], color=["#35618f", "#4f8f5b", "#c77b30"])
        ax.set_title(title)
        ax.set_xlabel("")
    fig.tight_layout()
    path = out_dir / "figure_baseline_s5_comparison.png"
    _save_fig(fig, path)
    plt.close(fig)
    return path


def plot_stage_progression(stage_df: pd.DataFrame, out_dir: Path) -> Path:
    plt.rcParams.update(PLOT_STYLE)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    metrics = [
        ("isco_coverage_share", "Coverage"),
        ("mean_similarity_retained", "Mean similarity"),
        ("mean_links_per_task", "Mean links/task"),
        ("share_tasks_in_overloaded_isco", "Overloaded task share"),
    ]
    dataset_display = {"29.2-ID": "O*NET 29.2", "25.0-ID": "O*NET 25.0"}
    for dataset, group in stage_df.groupby("dataset_short"):
        group = group.sort_values("stage")
        x = group["stage"].astype(str).map(STAGE_LABELS).fillna(group["stage"].astype(str))
        for ax, (col, title) in zip(axes.flatten(), metrics):
            ax.plot(x, group[col], marker="o", label=dataset_display.get(dataset, dataset))
            ax.set_title(title)
            ax.tick_params(axis="x", rotation=30)
    axes[0, 0].legend(frameon=False)
    fig.tight_layout()
    path = out_dir / "figure_stage_progression.png"
    _save_fig(fig, path)
    plt.close(fig)
    return path


def plot_sweep_tradeoff(out_dir: Path) -> Path | None:
    path = Path("results/summary/sweep_results_metrics_only.csv")
    if not path.exists():
        return None
    df = pd.read_csv(path)
    plt.rcParams.update(PLOT_STYLE)
    fig, ax = plt.subplots(figsize=(10, 7))
    scatter = ax.scatter(
        df["S5_FINAL_isco_coverage_share"],
        df["S5_FINAL_mean_similarity_retained"],
        s=60 + 220 * (1 - df["S5_FINAL_share_tasks_in_overloaded_isco"]),
        c=df["selection_score"],
        cmap="viridis",
        alpha=0.85,
        edgecolors="black",
        linewidths=0.3,
    )
    pareto = df[df["pareto_candidate"] == True]
    ax.scatter(
        pareto["S5_FINAL_isco_coverage_share"],
        pareto["S5_FINAL_mean_similarity_retained"],
        s=120,
        facecolors="none",
        edgecolors="#d1495b",
        linewidths=1.5,
        label="Pareto candidate",
    )
    ax.set_xlabel("S5 coverage")
    ax.set_ylabel("S5 mean similarity")
    ax.set_title("Sweep trade-off: coverage vs similarity")
    ax.legend(frameon=False)
    fig.colorbar(scatter, ax=ax, label="Selection score")
    fig.tight_layout()
    out = out_dir / "figure_sweep_tradeoff.png"
    _save_fig(fig, out)
    plt.close(fig)
    return out


def plot_parameter_sensitivity(out_dir: Path) -> Path | None:
    path = Path("results/summary/sweep_results_metrics_only.csv")
    if not path.exists():
        return None
    df = pd.read_csv(path)
    baseline = infer_sweep_baseline(df)
    changed = df.apply(lambda row: identify_sweep_change(row, baseline)[0], axis=1)
    df["changed_param"] = changed
    params = [p for p in SWEEP_PARAMS if p in set(df["changed_param"])]
    params = params[:6]
    if not params:
        return None
    plt.rcParams.update(PLOT_STYLE)
    fig, axes = plt.subplots(2, 3, figsize=(14, 8))
    axes = axes.flatten()
    for ax, param in zip(axes, params):
        subset = df[df["changed_param"] == param].copy()
        subset = subset.sort_values(param)
        ax.plot(subset[param], subset["selection_score"], marker="o", color="#35618f")
        ax.set_title(param)
        ax.set_xlabel(param)
        ax.set_ylabel("Selection score")
    for ax in axes[len(params):]:
        ax.axis("off")
    fig.tight_layout()
    out = out_dir / "figure_parameter_sensitivity.png"
    _save_fig(fig, out)
    plt.close(fig)
    return out


def main() -> None:
    out_dir = ensure_dir(Path("results") / "publication")
    run_ids = latest_run_ids()
    stage_df = build_baseline_stage_table(run_ids)
    s5_df = build_s5_summary(stage_df)
    top_sweep, per_param = build_sweep_tables()

    saved = []
    saved.append(save_table(stage_df, out_dir, "table_baseline_stage_metrics"))
    saved.append(save_table(s5_df, out_dir, "table_baseline_s5_summary"))
    if top_sweep is not None:
        saved.append(save_table(top_sweep, out_dir, "table_sweep_top_configs"))
    if per_param is not None and not per_param.empty:
        saved.append(save_table(per_param, out_dir, "table_sweep_parameter_recommendations"))

    saved.append(plot_baseline_s5(s5_df, out_dir))
    saved.append(plot_stage_progression(stage_df, out_dir))
    tradeoff = plot_sweep_tradeoff(out_dir)
    if tradeoff is not None:
        saved.append(tradeoff)
    sensitivity = plot_parameter_sensitivity(out_dir)
    if sensitivity is not None:
        saved.append(sensitivity)

    for path in saved:
        print(path)


if __name__ == "__main__":
    main()
