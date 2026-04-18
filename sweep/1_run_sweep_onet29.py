"""
1_run_sweep_onet29.py
=====================
Multi-dimensional random parameter sweep for ONET29.  Additive: safe to
re-run with a larger n — variants whose output CSV already exists are skipped
and folded back into the combined summary.

Seed reproducibility / interrupt safety:
  generate_random_configs(seed=42, n=500) → configs 0..499
  Re-run or interrupt anytime — completed output files are skipped and
  included in the combined summary.  Ctrl+C saves progress before exiting.

Parameters swept (sweep/sweep_random.yaml):
  w_isco, w_isco_task, w_occ, w_dwa, w_soc_title,
  min_sim, margin_best, max_links_per_task,
  overload_quantile, overload_abs, overload_min_sim, overload_margin_best

All Tier-1 embeddings are shared (checkpoint_prefix="ONET29" for all
variants) — only blend + FAISS retrieval runs per variant.

Outputs:
  output/sweep_ONET29/{name}_crosswalk.csv   — per-variant final crosswalk
  output/sweep_ONET29/sweep_results.csv      — ranked combined summary

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

from config import load_config, load_yaml_or_json
from pipeline import run_pipeline
from sweep import (
    generate_random_configs,
    _add_composite_score,
    _add_pareto_flag,
    _load_metrics,
    _flatten_config,
)

BASE_CONFIG = str(ROOT_DIR / "config_onet29.yaml")
SWEEP_SPEC = str(ROOT_DIR / "sweep" / "sweep_random.yaml")
SWEEP_OUT = ROOT_DIR / "output" / "sweep_ONET29"
SUMMARY_PATH = SWEEP_OUT / "sweep_results.csv"

DISPLAY_COLS = [
    "dataset_name", "selection_rank", "selection_score", "pareto_candidate",
    "w_isco", "w_isco_task", "w_occ", "w_dwa", "w_soc_title",
    "min_sim", "margin_best", "max_links_per_task",
    "S5_FINAL_isco_coverage_share", "S5_FINAL_mean_similarity_retained",
    "S5_FINAL_gini_tasks_per_isco",
]

SWEEP_OUT.mkdir(parents=True, exist_ok=True)

base = load_config(BASE_CONFIG)
sweep_spec = load_yaml_or_json(SWEEP_SPEC)
n = int(sweep_spec.get("n", 500))
seed = int(sweep_spec.get("seed", 42))

raw_configs = generate_random_configs(base, sweep_spec, n=n, seed=seed)

# Keep checkpoint_prefix = "ONET29" so all variants share existing Tier-1 caches
configs = []
for i, cfg in enumerate(raw_configs):
    name = f"ONET29_sw{i:04d}"
    configs.append(replace(cfg,
        dataset_name=name,
        checkpoint_prefix="ONET29",
        final_output_path=str(SWEEP_OUT / f"{name}_crosswalk.csv"),
    ))

done = [c for c in configs if Path(c.final_output_path).exists()]
todo = [c for c in configs if not Path(c.final_output_path).exists()]

print(f"Sweep: {n} total variants | {len(done)} already done | {len(todo)} to run")
print(f"Base: {BASE_CONFIG}  |  Spec: {SWEEP_SPEC}\n")

# ── Run new variants ──────────────────────────────────────────────────────────
new_run_outputs = []
interrupted = False
try:
    for i, cfg in enumerate(todo):
        print(f"[{i+1}/{len(todo)}] {cfg.dataset_name}")
        new_run_outputs.append(run_pipeline(cfg))
except KeyboardInterrupt:
    interrupted = True
    completed = len(new_run_outputs)
    print(f"\n[INTERRUPTED] {completed}/{len(todo)} new variants completed — saving progress...")
    # Re-scan done list to include variants finished in this session
    done = [c for c in configs if Path(c.final_output_path).exists()]

# ── Build combined summary from all completed runs ────────────────────────────
all_run_outputs = new_run_outputs  # new ones have full run_output dicts

# For already-done variants, reconstruct run_output from manifest files.
done_names = {c.dataset_name for c in done}
results_root = ROOT_DIR / base.output_dir
for manifest in results_root.glob("*/*/manifest.json"):
    dataset_name = manifest.parents[1].name
    if dataset_name not in done_names:
        continue
    import json
    with open(manifest) as f:
        m = json.load(f)
    all_run_outputs.append({
        "run_id": m.get("run_id", manifest.parent.name),
        "stage_paths": m.get("stage_paths", {}),
        "metrics_path": str(manifest.parent / "metrics.csv"),
        "manifest_path": str(manifest),
        "config": None,
    })

# Build rows
rows = []
for run_output in all_run_outputs:
    metrics_path = Path(run_output["metrics_path"])
    if not metrics_path.exists():
        continue
    metrics_df = _load_metrics(run_output)
    manifest_path = Path(run_output["manifest_path"])
    cfg_obj = run_output.get("config")
    if cfg_obj is not None:
        cfg_data = _flatten_config(cfg_obj)
    else:
        import json
        with open(manifest_path) as f:
            m = json.load(f)
        cfg_data = m.get("config", {})

    metric_map = {row["stage"]: row for _, row in metrics_df.iterrows()}
    row = {"run_id": run_output["run_id"]}
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
results = _add_composite_score(results)
results = _add_pareto_flag(results)
if "selection_score" in results.columns:
    results = results.sort_values(
        ["pareto_candidate", "selection_score"],
        ascending=[False, False],
    ).reset_index(drop=True)
    results["selection_rank"] = range(1, len(results) + 1)

results.to_csv(SUMMARY_PATH, index=False)

status = "interrupted" if interrupted else "complete"
print(f"\nSweep {status}. {len(results)} variants in summary: {SUMMARY_PATH}")
if "pareto_candidate" in results.columns:
    print(f"Pareto candidates: {int(results['pareto_candidate'].sum())}")

available = [c for c in DISPLAY_COLS if c in results.columns]
print(f"\nTop 10:\n{results[available].head(10).to_string(index=False)}")
