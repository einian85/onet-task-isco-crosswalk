from __future__ import annotations

from pathlib import Path
from typing import Any

import matplotlib.pyplot as plt
import pandas as pd

from config import RunConfig, compute_run_id, get_code_version, load_config, load_yaml_or_json


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
    "w_dwa",
    "w_soc_title",
    "w_occ",
    "w_isco",
    "w_isco_task",
]

STAGE_ORDER = ["S1_RETRIEVE", "S2_TASK_FILTER", "S3_COVERAGE"]

STAGE_LABELS = {
    "S1_RETRIEVE": "S1: Retrieve",
    "S2_TASK_FILTER": "S2: Task filter",
    "S3_COVERAGE": "S3: Coverage",
}

_SOC_LONG = {
    "onet_soc_2019":    "SOC 2018",
    "onet_soc_2010":    "SOC 2010",
    "onet_soc_2009":    "O*NET-SOC 2009",
    "onet_soc_2006":    "O*NET-SOC 2006",
    "onet_soc_pre2006": "O*NET-SOC pre-2006",
}


def _build_dataset_meta() -> dict:
    """Generate DATASET_META from version_list.csv for all versions with existing output."""
    vlist = pd.read_csv(
        Path(__file__).parent / "data" / "version_list.csv", dtype={"version": str}
    )
    rows = sorted(vlist.to_dict("records"),
                  key=lambda r: tuple(int(x) for x in r["version"].split(".")))
    out = {}
    for r in rows:
        ver = r["version"]
        tag = "ONET" + ver.replace(".", "")
        config_path = f"configs/config_{tag.lower()}.yaml"
        xwalk = Path(f"output/{tag}_task_to_ISCO_crosswalk.csv")
        if not Path(config_path).exists() or not xwalk.exists():
            continue
        soc = r.get("soc_taxonomy", "")
        out[f"{tag.lower()}_id"] = {
            "label": f"O*NET {ver} ({_SOC_LONG.get(soc, soc)})",
            "short": ver,
            "config_path": config_path,
        }
    return out


DATASET_META = _build_dataset_meta()


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def load_cfg(path: str) -> RunConfig:
    return load_config(path)


def _run_id_from_manifest(final_output_path: str) -> str:
    """Find the run_id for final_output_path by matching manifest mtime to the output CSV mtime.
    When multiple manifests match, the one written closest in time to the output CSV wins —
    the pipeline writes both atomically in the same run.
    """
    import json
    target = final_output_path.replace("\\", "/")
    preds_root = Path("results/predictions")
    output_csv = Path(final_output_path)

    matching: list[tuple[Path, dict]] = []
    for manifest in preds_root.glob("*/run_manifest.json"):
        try:
            d = json.loads(manifest.read_text(encoding="utf-8"))
        except Exception:
            continue
        cfg_path = d.get("config", {}).get("final_output_path", "").replace("\\", "/")
        if cfg_path == target or cfg_path.endswith(Path(target).name):
            matching.append((manifest, d))

    if not matching:
        raise FileNotFoundError(f"No manifest found for final_output_path={final_output_path}")

    if len(matching) == 1:
        return matching[0][1]["run_id"]

    # Pick the manifest whose mtime is closest to the output CSV's mtime.
    # The pipeline writes the CSV and the manifest in the same run, so their
    # mtimes are nearly identical; old sweep manifests will be far off.
    csv_mtime = output_csv.stat().st_mtime if output_csv.exists() else None
    if csv_mtime is not None:
        best = min(matching, key=lambda x: abs(x[0].stat().st_mtime - csv_mtime))
        return best[1]["run_id"]

    # Fallback: newest manifest
    return max(matching, key=lambda x: x[0].stat().st_mtime)[1]["run_id"]


def latest_run_ids() -> dict[str, dict[str, str]]:
    out: dict[str, dict[str, str]] = {}
    for dataset_id, meta in DATASET_META.items():
        cfg = load_cfg(meta["config_path"])
        run_id = _run_id_from_manifest(cfg.final_output_path)
        out[dataset_id] = {
            "run_id": run_id,
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
    df["_ver"] = pd.to_numeric(df["dataset_short"], errors="coerce")
    return df.sort_values(["_ver", "stage"]).drop(columns=["_ver"]).reset_index(drop=True)


def build_s3_summary(stage_df: pd.DataFrame) -> pd.DataFrame:
    keep = [
        "dataset_id",
        "dataset",
        "dataset_short",
        "run_id",
        "isco_coverage_share",
        "mean_similarity_retained",
        "mean_links_per_task",
        "gini_tasks_per_isco",
        "tasks_per_isco_mean",
        "tasks_per_isco_p95",
        "tasks_per_isco_max",
        "retrieval_lowconf_share",
    ]
    # Use the last available stage per dataset: S3 if present (old pipeline runs),
    # S2 otherwise (current pipeline). S3 == S2 in value; this just avoids
    # dropping versions whose runs were produced by the current pipeline.
    last_stage_idx = (
        stage_df.groupby("dataset_id")["stage"]
        .transform(lambda s: s == s.max())
    )
    s3 = stage_df.loc[last_stage_idx, keep].copy()
    s3 = s3.rename(
        columns={
            "isco_coverage_share": "S3_coverage",
            "mean_similarity_retained": "S3_mean_similarity",
            "mean_links_per_task": "S3_mean_links_per_task",
            "gini_tasks_per_isco": "S3_gini_tasks_per_isco",
            "tasks_per_isco_mean": "S3_tasks_per_isco_mean",
            "tasks_per_isco_p95": "S3_tasks_per_isco_p95",
            "tasks_per_isco_max": "S3_tasks_per_isco_max",
            "retrieval_lowconf_share": "S3_lowconf_share",
        }
    )
    s3["_ver"] = pd.to_numeric(s3["dataset_short"], errors="coerce")
    s3 = s3.sort_values("_ver").drop(columns=["_ver"]).reset_index(drop=True)
    return s3


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
        "S3_COVERAGE_isco_coverage_share",
        "S3_COVERAGE_mean_similarity_retained",
        "S3_COVERAGE_mean_links_per_task",
        "S3_COVERAGE_gini_tasks_per_isco",
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
                "S3_coverage": best["S3_COVERAGE_isco_coverage_share"],
                "S3_mean_similarity": best["S3_COVERAGE_mean_similarity_retained"],
                "S3_mean_links_per_task": best["S3_COVERAGE_mean_links_per_task"],
                "S3_gini_tasks_per_isco": best["S3_COVERAGE_gini_tasks_per_isco"],
            }
        )
    per_param_table = pd.DataFrame(per_param_rows).sort_values("parameter").reset_index(drop=True)
    return top_table, per_param_table


def build_version_coverage_table() -> pd.DataFrame:
    """Per-version task count, ISCO coverage, and mean similarity for SOC 2010 and SOC 2018."""
    vlist = pd.read_csv(
        Path(__file__).parent / "data" / "version_list.csv", dtype={"version": str}
    )
    soc_filter = {"onet_soc_2010", "onet_soc_2019"}
    vlist = vlist[vlist["soc_taxonomy"].isin(soc_filter)].copy()
    vlist["_ver_tuple"] = vlist["version"].apply(
        lambda v: tuple(int(x) for x in v.split("."))
    )
    vlist = vlist.sort_values("_ver_tuple").reset_index(drop=True)

    rows = []
    for _, r in vlist.iterrows():
        ver = r["version"]
        soc_label = _SOC_LONG.get(r["soc_taxonomy"], r["soc_taxonomy"])
        tag = "ONET" + ver.replace(".", "")
        path = Path(__file__).parent / f"output/{tag}_task_to_ISCO_crosswalk.csv"
        if not path.exists():
            continue
        df = pd.read_csv(path)
        best = df[df["is_best"] == True]
        rows.append({
            "version": ver,
            "soc": soc_label,
            "n_tasks": len(best),
            "isco_groups_covered": best["iscoGroup"].astype(str).str.zfill(4).nunique(),
            "mean_similarity": round(best["similarity"].mean(), 3) if "similarity" in best.columns else None,
        })
    return pd.DataFrame(rows)


def save_table(df: pd.DataFrame, out_dir: Path, name: str) -> Path:
    path = out_dir / f"{name}.csv"
    df.to_csv(path, index=False)
    return path


def plot_baseline_s3(summary_df: pd.DataFrame, out_dir: Path) -> Path:
    plt.rcParams.update(PLOT_STYLE)
    metrics = [
        ("S3_coverage", "Coverage"),
        ("S3_mean_similarity", "Mean similarity"),
        ("S3_gini_tasks_per_isco", "Gini (task distribution)"),
    ]
    fig, axes = plt.subplots(1, 3, figsize=(14, 5))
    dataset_display = {"29.2-ID": "O*NET 29.2", "25.0-ID": "O*NET 25.0"}
    disp_datasets = summary_df["dataset_short"].map(dataset_display).fillna(summary_df["dataset_short"])
    labels = disp_datasets.tolist()
    sparse_labels = [lab if i % 3 == 0 else "" for i, lab in enumerate(labels)]
    for ax, (col, title) in zip(axes, metrics):
        ax.bar(disp_datasets, summary_df[col], color=["#35618f", "#4f8f5b", "#c77b30"])
        ax.set_title(title)
        ax.set_xlabel("")
        ax.set_xticks(range(len(labels)))
        ax.set_xticklabels(sparse_labels, rotation=90, fontsize=7)
    fig.tight_layout()
    path = out_dir / "figure_baseline_s3_comparison.png"
    _save_fig(fig, path)
    plt.close(fig)
    return path


def plot_stage_progression(stage_df: pd.DataFrame, out_dir: Path) -> Path:
    stage_df = stage_df[stage_df["stage"].notna()].copy()
    plt.rcParams.update(PLOT_STYLE)
    fig, axes = plt.subplots(2, 2, figsize=(12, 8), sharex=True)
    metrics = [
        ("isco_coverage_share", "Coverage"),
        ("mean_similarity_retained", "Mean similarity"),
        ("mean_links_per_task", "Mean links/task"),
        ("gini_tasks_per_isco", "Gini (task distribution)"),
    ]
    # Background: all versions in light gray
    for dataset, group in stage_df.groupby("dataset_short"):
        group = group.sort_values("stage")
        x = group["stage"].astype(str).map(STAGE_LABELS).fillna(group["stage"].astype(str))
        for ax, (col, _) in zip(axes.flatten(), metrics):
            ax.plot(x, group[col], color="#cccccc", linewidth=0.8, zorder=1)
    # Foreground: 6 representative versions with labels
    HIGHLIGHT = {
        "15.1": ("SOC 2010: v15.1", "#1f77b4"),
        "20.0": ("SOC 2010: v20.0", "#aec7e8"),
        "25.0": ("SOC 2010: v25.0", "#17becf"),
        "25.1": ("SOC 2018: v25.1", "#ff7f0e"),
        "29.2": ("SOC 2018: v29.2", "#d62728"),
        "30.3": ("SOC 2018: v30.3", "#9467bd"),
    }
    for dataset, group in stage_df.groupby("dataset_short"):
        ver = str(dataset).replace("-ID", "")
        if ver not in HIGHLIGHT:
            continue
        label, color = HIGHLIGHT[ver]
        group = group.sort_values("stage")
        x = group["stage"].astype(str).map(STAGE_LABELS).fillna(group["stage"].astype(str))
        for ax, (col, title) in zip(axes.flatten(), metrics):
            ax.plot(x, group[col], marker="o", color=color, linewidth=1.5,
                    label=label, zorder=2)
            ax.set_title(title)
            ax.tick_params(axis="x", rotation=30)
    axes[0, 0].legend(frameon=False, fontsize=7, ncol=2)
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
        df["S3_COVERAGE_isco_coverage_share"],
        df["S3_COVERAGE_mean_similarity_retained"],
        s=60 + 220 * (1 - df["S3_COVERAGE_gini_tasks_per_isco"]),
        c=df["selection_score"],
        cmap="viridis",
        alpha=0.85,
        edgecolors="black",
        linewidths=0.3,
    )
    pareto = df[df["pareto_candidate"] == True]
    ax.scatter(
        pareto["S3_COVERAGE_isco_coverage_share"],
        pareto["S3_COVERAGE_mean_similarity_retained"],
        s=120,
        facecolors="none",
        edgecolors="#d1495b",
        linewidths=1.5,
        label="Pareto candidate",
    )
    ax.set_xlabel("S3 coverage")
    ax.set_ylabel("S3 mean similarity")
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
    s3_df = build_s3_summary(stage_df)
    top_sweep, per_param = build_sweep_tables()

    version_cov_df = build_version_coverage_table()

    saved = []
    saved.append(save_table(stage_df, out_dir, "table_baseline_stage_metrics"))
    saved.append(save_table(s3_df, out_dir, "table_baseline_s3_summary"))
    saved.append(save_table(version_cov_df, out_dir, "table_version_coverage"))
    if top_sweep is not None:
        saved.append(save_table(top_sweep, out_dir, "table_sweep_top_configs"))
    if per_param is not None and not per_param.empty:
        saved.append(save_table(per_param, out_dir, "table_sweep_parameter_recommendations"))

    saved.append(plot_baseline_s3(s3_df, out_dir))
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
