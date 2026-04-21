"""
2_run_focused_sweep_onet29.py
=============================
Focused sweep in the area of interest identified from the 500-point random
sweep (1_run_sweep_onet29.py):

  Phase 1 — fine 2D grid: w_dwa × w_soc_title
    w_dwa:       [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]     (7 values)
    w_soc_title: [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]  (9)
    × 3 ISCO settings (w_isco=0/0.4/0.8) = 189 runs

  Phase 2 — focused random: sweep/sweep_focused.yaml (tighter ranges, n=500)

Both phases share the same Tier-1 caches (checkpoint_prefix="ONET29").
slim_output=True: skips stage CSVs, per-variant crosswalk CSVs, and
decorative columns — only metrics + in-memory S5 comparison are kept.
Additive / interrupt-safe: re-run freely.

Output: results/summary/sweep_results_metrics_only.csv
        (merged with phase-1 random sweep if that file already exists)

Run from the project root:
    python sweep/2_run_focused_sweep_onet29.py [--grid-only | --random-only]
"""

from __future__ import annotations

import itertools
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

BASE_CONFIG  = str(ROOT_DIR / "config_onet29.yaml")
FOCUSED_SPEC = str(ROOT_DIR / "sweep" / "sweep_focused.yaml")
SUMMARY_DIR  = ROOT_DIR / "results" / "summary"
SUMMARY_PATH = SUMMARY_DIR / "sweep_results_metrics_only.csv"

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

# ── Grid dimensions ───────────────────────────────────────────────────────────
W_DWA_GRID       = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
W_SOC_TITLE_GRID = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
W_ISCO_SETTINGS  = [
    dict(w_isco=0.0, w_isco_task=0.5, w_occ=0.85),   # ESCO-only
    dict(w_isco=0.4, w_isco_task=0.5, w_occ=0.75),   # mixed
    dict(w_isco=0.8, w_isco_task=0.7, w_occ=0.70),   # ISCO-heavy
]

SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

mode = sys.argv[1] if len(sys.argv) > 1 else "both"
assert mode in ("--grid-only", "--random-only", "both"), \
    "Usage: python sweep/2_run_focused_sweep_onet29.py [--grid-only | --random-only]"

base = load_config(BASE_CONFIG)
code_version = get_code_version()
metrics_root = ROOT_DIR / base.output_dir / "metrics"

# ── Build config list ─────────────────────────────────────────────────────────
configs: list = []

if mode in ("--grid-only", "both"):
    for isco_set, dwa, soc in itertools.product(
        W_ISCO_SETTINGS, W_DWA_GRID, W_SOC_TITLE_GRID
    ):
        tag = (f"fg_isco{round(isco_set['w_isco']*10):02d}"
               f"_dwa{round(dwa*100):02d}"
               f"_soc{round(soc*100):02d}")
        configs.append(replace(base,
            dataset_name=tag,
            checkpoint_prefix="ONET29",
            slim_output=True,
            w_dwa=dwa,
            w_soc_title=soc,
            include_soc_title=(soc > 0),
            final_output_path=str(ROOT_DIR / "output" / "sweep_focused" / f"{tag}_crosswalk.csv"),
            **isco_set,
        ))

if mode in ("--random-only", "both"):
    spec = load_yaml_or_json(FOCUSED_SPEC)
    n    = int(spec.get("n", 500))
    seed = int(spec.get("seed", 99))
    raw  = generate_random_configs(base, spec, n=n, seed=seed)
    for i, cfg in enumerate(raw):
        name = f"fr{i:04d}"
        configs.append(replace(cfg,
            dataset_name=name,
            checkpoint_prefix="ONET29",
            slim_output=True,
            final_output_path=str(ROOT_DIR / "output" / "sweep_focused" / f"{name}_crosswalk.csv"),
        ))

def _metrics_csv(cfg) -> Path:
    run_id = compute_run_id(cfg, code_version, cfg.data_version)
    return metrics_root / run_id / "metrics.csv"

done = [c for c in configs if _metrics_csv(c).exists()]
todo = [c for c in configs if not _metrics_csv(c).exists()]

print(f"Focused sweep: {len(configs)} total | {len(done)} done | {len(todo)} to run")
if mode != "--random-only":
    print(f"  Grid: {len(W_DWA_GRID)}×{len(W_SOC_TITLE_GRID)}×{len(W_ISCO_SETTINGS)} = "
          f"{len(W_DWA_GRID)*len(W_SOC_TITLE_GRID)*len(W_ISCO_SETTINGS)} combos")
print()

# ── Run baseline (first config) for S5 comparison ────────────────────────────
baseline_cfg = configs[0]
print(f"[baseline] {baseline_cfg.dataset_name}")
baseline_out = run_pipeline(baseline_cfg)
baseline_s5  = baseline_out["s5"]

if baseline_cfg in todo:
    todo = [c for c in todo if c is not baseline_cfg]
new_run_outputs = [baseline_out]

# ── Run remaining variants ────────────────────────────────────────────────────
interrupted = False
try:
    for i, cfg in enumerate(todo):
        print(f"[{i+1}/{len(todo)}] {cfg.dataset_name}")
        new_run_outputs.append(run_pipeline(cfg))
except KeyboardInterrupt:
    interrupted = True
    print(f"\n[INTERRUPTED] {len(new_run_outputs)}/{len(todo)} completed — saving progress...")

# ── Build combined summary ────────────────────────────────────────────────────
def _make_row(run_output: dict, s5_df) -> dict | None:
    metrics_path = Path(run_output["metrics_path"]).parent / "metrics.csv"
    if not metrics_path.exists():
        return None
    metrics_df = pd.read_csv(metrics_path)
    cfg_obj = run_output.get("config")
    cfg_data = _flatten_config(cfg_obj) if cfg_obj is not None else {}
    metric_map = {r["stage"]: r for _, r in metrics_df.iterrows()}
    row: dict = {"run_id": run_output.get("run_id", metrics_path.parent.name)}
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

rows = []
for run_output in new_run_outputs:
    r = _make_row(run_output, run_output.get("s5"))
    if r:
        rows.append(r)

new_run_ids = {r["run_id"] for r in new_run_outputs}
for cfg in done:
    run_id = compute_run_id(cfg, code_version, cfg.data_version)
    if run_id in new_run_ids:
        continue
    mc = metrics_root / run_id / "metrics.csv"
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
        ["pareto_candidate", "selection_score"], ascending=[False, False]
    ).reset_index(drop=True)
    results["selection_rank"] = range(1, len(results) + 1)

# Merge with phase-1 random sweep results if they exist, then re-rank.
if SUMMARY_PATH.exists():
    prev = pd.read_csv(SUMMARY_PATH)
    existing_ids = set(results["run_id"].astype(str))
    prev_new = prev[~prev["run_id"].astype(str).isin(existing_ids)]
    results = pd.concat([results, prev_new], ignore_index=True)
    results = _add_composite_score(results)
    results = _add_pareto_flag(results)
    if "selection_score" in results.columns:
        results = results.sort_values(
            ["pareto_candidate", "selection_score"], ascending=[False, False]
        ).reset_index(drop=True)
        results["selection_rank"] = range(1, len(results) + 1)

slim = results[[c for c in SLIM_COLS if c in results.columns]]
slim.to_csv(SUMMARY_PATH, index=False)

status = "interrupted" if interrupted else "complete"
print(f"\nFocused sweep {status}. {len(results)} total variants → {SUMMARY_PATH}")
if "pareto_candidate" in results.columns:
    print(f"Pareto candidates: {int(results['pareto_candidate'].sum())}")

available = [c for c in DISPLAY_COLS if c in results.columns]
print(f"\nTop 10:\n{results[available].head(10).to_string(index=False)}")
