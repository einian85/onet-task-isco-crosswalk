"""
1_run_sweep_onet29.py
=====================
Multi-dimensional random parameter sweep for ONET29.  Additive: safe to
re-run with a larger n — completed variants (detected via metrics file) are
skipped and folded back into the combined summary.

Seed reproducibility / interrupt safety:
  generate_random_configs(seed=42, n=500) → configs 0..499
  Re-run or interrupt anytime — completed metrics are reloaded automatically.
  Ctrl+C saves progress before exiting.

Parameters swept (sweep/sweep_random.yaml):
  w_isco, w_isco_task, w_occ, w_dwa, w_soc_title,
  min_sim, margin_best, max_links_per_task,
  overload_quantile, overload_abs, overload_min_sim, overload_margin_best

All Tier-1 embeddings are shared (checkpoint_prefix="ONET29").
slim_output=True: skips stage CSVs, per-variant crosswalk CSVs, and
decorative columns — only metrics + in-memory S5 comparison are kept.

Outputs:
  results/summary/sweep_results_metrics_only.csv  — ranked slim summary

Run from the project root:
    python sweep/1_run_sweep_onet29.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(ROOT_DIR))

from config import load_config, load_yaml_or_json, compute_run_id, get_code_version
from pipeline import run_pipeline
from stability import compare_runs_links
from sweep import (
    generate_random_configs,
    _add_composite_score,
    _add_pareto_flag,
    _add_baseline_deltas,
    _flatten_config,
)

BASE_CONFIG = str(ROOT_DIR / "config_onet29.yaml")
SWEEP_SPEC  = str(ROOT_DIR / "sweep" / "sweep_random.yaml")
SUMMARY_DIR = ROOT_DIR / "results" / "summary"
SUMMARY_PATH = SUMMARY_DIR / "sweep_results_metrics_only.csv"

# Columns kept in the slim summary (everything downstream actually needs).
SLIM_COLS = [
    "run_id", "dataset_name",
    "w_isco", "w_dwa", "w_soc_title", "w_occ", "w_isco_task",
    "min_sim", "margin_best", "max_links_per_task", "k_retrieve",
    "overload_abs", "overload_quantile", "overload_min_sim", "overload_margin_best",
    "delta_min_sim", "delta_margin_best", "delta_max_links_per_task", "delta_w_occ",
    "delta_k_retrieve", "delta_overload_abs", "delta_overload_quantile",
    "delta_overload_min_sim", "delta_overload_margin_best",
    "S5_FINAL_isco_coverage_share", "S5_FINAL_mean_similarity_retained",
    "S5_FINAL_mean_links_per_task", "S5_FINAL_share_tasks_in_overloaded_isco",
    "S5_FINAL_gini_tasks_per_isco",
    "S1_RETRIEVE_retrieval_lowconf_share", "S1_RETRIEVE_retrieval_gap12_median",
    "S5_best_link_agreement", "S5_jaccard_links",
    "selection_score", "selection_rank", "pareto_candidate",
]

DISPLAY_COLS = [
    "dataset_name", "selection_rank", "selection_score", "pareto_candidate",
    "w_isco", "w_dwa", "w_soc_title", "min_sim", "max_links_per_task",
    "S5_FINAL_isco_coverage_share", "S5_FINAL_mean_similarity_retained",
]

SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

base = load_config(BASE_CONFIG)
sweep_spec = load_yaml_or_json(SWEEP_SPEC)
n    = int(sweep_spec.get("n", 500))
seed = int(sweep_spec.get("seed", 42))
code_version = get_code_version()

raw_configs = generate_random_configs(base, sweep_spec, n=n, seed=seed)

# All variants share Tier-1 caches; slim_output skips all CSV writes.
configs = []
for i, cfg in enumerate(raw_configs):
    name = f"ONET29_sw{i:04d}"
    configs.append(replace(cfg,
        dataset_name=name,
        checkpoint_prefix="ONET29",
        slim_output=True,
        # final_output_path unused in slim mode but must be a valid string
        final_output_path=str(ROOT_DIR / "output" / "sweep_ONET29" / f"{name}_crosswalk.csv"),
    ))

# Skip variants whose metrics file already exists.
metrics_root = ROOT_DIR / base.output_dir / "metrics"

def _metrics_csv(cfg) -> Path:
    run_id = compute_run_id(cfg, code_version, cfg.data_version)
    return metrics_root / run_id / "metrics.csv"

done = [c for c in configs if _metrics_csv(c).exists()]
todo = [c for c in configs if not _metrics_csv(c).exists()]

print(f"Sweep: {n} total variants | {len(done)} already done | {len(todo)} to run")
print(f"Base: {BASE_CONFIG}  |  Spec: {SWEEP_SPEC}\n")

# ── Run baseline first (needed for Jaccard comparison) ────────────────────────
baseline_cfg = configs[0]
baseline_run_id = compute_run_id(baseline_cfg, code_version, baseline_cfg.data_version)
baseline_metrics_csv = metrics_root / baseline_run_id / "metrics.csv"

if baseline_metrics_csv.exists() and baseline_cfg not in todo:
    # Baseline already done — we need its S5 for comparison; re-run is cheap
    # (embeddings cached) but we need the DataFrame.  Run it slim again.
    print(f"[baseline] Re-running {baseline_cfg.dataset_name} to get in-memory S5...")
    baseline_out = run_pipeline(baseline_cfg)
else:
    print(f"[baseline] {baseline_cfg.dataset_name}")
    baseline_out = run_pipeline(baseline_cfg)
    todo = [c for c in todo if c is not baseline_cfg]

baseline_s5 = baseline_out["s5"]
new_run_outputs = [baseline_out] if baseline_cfg in todo else []

# ── Run remaining variants ────────────────────────────────────────────────────
interrupted = False
try:
    for i, cfg in enumerate(todo):
        if cfg is baseline_cfg:
            continue
        print(f"[{i+1}/{len(todo)}] {cfg.dataset_name}")
        new_run_outputs.append(run_pipeline(cfg))
except KeyboardInterrupt:
    interrupted = True
    print(f"\n[INTERRUPTED] {len(new_run_outputs)} new variants completed — saving progress...")

# ── Build combined summary ────────────────────────────────────────────────────
# Collect rows from new runs (have in-memory S5 for comparison).
rows = []

def _make_row(run_output: dict, s5_df) -> dict | None:
    metrics_path = Path(run_output["metrics_path"]).parent / "metrics.csv"
    if not metrics_path.exists():
        return None
    metrics_df = pd.read_csv(metrics_path)
    cfg_obj = run_output.get("config")
    cfg_data = _flatten_config(cfg_obj) if cfg_obj is not None else {}
    metric_map = {r["stage"]: r for _, r in metrics_df.iterrows()}
    row: dict = {"run_id": run_output["run_id"]}
    row.update(cfg_data)
    for stage_name, metric_row in metric_map.items():
        for key, value in metric_row.items():
            if key in {"run_id", "stage"}:
                continue
            row[f"{stage_name}_{key}"] = value
    if s5_df is not None and baseline_s5 is not None:
        cmp = compare_runs_links(baseline_s5, s5_df)
        row.update({f"S5_{k}": v for k, v in cmp.items()})
    return row

for run_output in new_run_outputs:
    r = _make_row(run_output, run_output.get("s5"))
    if r:
        rows.append(r)

# Re-load already-done variants from metrics files (no S5 comparison available).
done_run_ids = {compute_run_id(c, code_version, c.data_version) for c in done
                if _metrics_csv(c).exists()}
new_run_ids = {r["run_id"] for r in new_run_outputs}
for cfg in done:
    run_id = compute_run_id(cfg, code_version, cfg.data_version)
    if run_id in new_run_ids:
        continue
    mc = metrics_root / run_id / "metrics.csv"
    manifest = metrics_root.parent / "predictions" / run_id / "run_manifest.json"
    if not mc.exists():
        continue
    metrics_df = pd.read_csv(mc)
    cfg_data = _flatten_config(cfg)
    metric_map = {r["stage"]: r for _, r in metrics_df.iterrows()}
    row: dict = {"run_id": run_id}
    row.update(cfg_data)
    for stage_name, metric_row in metric_map.items():
        for key, value in metric_row.items():
            if key in {"run_id", "stage"}:
                continue
            row[f"{stage_name}_{key}"] = value
    rows.append(row)

if not rows:
    print("No completed runs found.")
    sys.exit(0)

results = pd.DataFrame(rows)
results = _add_baseline_deltas(results, baseline_out["run_id"])
results = _add_composite_score(results)
results = _add_pareto_flag(results)
if "selection_score" in results.columns:
    results = results.sort_values(
        ["pareto_candidate", "selection_score"],
        ascending=[False, False],
    ).reset_index(drop=True)
    results["selection_rank"] = range(1, len(results) + 1)

# Write slim summary (only columns downstream actually uses).
slim = results[[c for c in SLIM_COLS if c in results.columns]]
slim.to_csv(SUMMARY_PATH, index=False)

status = "interrupted" if interrupted else "complete"
print(f"\nSweep {status}. {len(results)} variants → {SUMMARY_PATH}")
if "pareto_candidate" in results.columns:
    print(f"Pareto candidates: {int(results['pareto_candidate'].sum())}")

available = [c for c in DISPLAY_COLS if c in results.columns]
print(f"\nTop 10:\n{results[available].head(10).to_string(index=False)}")
