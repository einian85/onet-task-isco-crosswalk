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
Additive / interrupt-safe: re-run freely.

Output: output/sweep_focused/sweep_results.csv

Run from the project root:
    python sweep/2_run_focused_sweep_onet29.py [--grid-only | --random-only]
"""

from __future__ import annotations

import itertools
import json
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

BASE_CONFIG  = str(ROOT_DIR / "config_onet29.yaml")
FOCUSED_SPEC = str(ROOT_DIR / "sweep" / "sweep_focused.yaml")
SWEEP_OUT    = ROOT_DIR / "output" / "sweep_focused"
SUMMARY_PATH = SWEEP_OUT / "sweep_results.csv"

DISPLAY_COLS = [
    "dataset_name", "selection_rank", "selection_score", "pareto_candidate",
    "w_isco", "w_isco_task", "w_occ", "w_dwa", "w_soc_title",
    "min_sim", "margin_best", "max_links_per_task",
    "S5_FINAL_isco_coverage_share", "S5_FINAL_mean_similarity_retained",
    "S5_FINAL_gini_tasks_per_isco",
]

# ── Grid dimensions ───────────────────────────────────────────────────────────
W_DWA_GRID        = [0.00, 0.05, 0.10, 0.15, 0.20, 0.25, 0.30]
W_SOC_TITLE_GRID  = [0.30, 0.35, 0.40, 0.45, 0.50, 0.55, 0.60, 0.65, 0.70]
W_ISCO_SETTINGS   = [
    dict(w_isco=0.0, w_isco_task=0.5, w_occ=0.85),   # ESCO-only
    dict(w_isco=0.4, w_isco_task=0.5, w_occ=0.75),   # mixed
    dict(w_isco=0.8, w_isco_task=0.7, w_occ=0.70),   # ISCO-heavy
]

SWEEP_OUT.mkdir(parents=True, exist_ok=True)

mode = sys.argv[1] if len(sys.argv) > 1 else "both"
assert mode in ("--grid-only", "--random-only", "both"), \
    "Usage: python sweep/2_run_focused_sweep_onet29.py [--grid-only | --random-only]"

base = load_config(BASE_CONFIG)

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
            w_dwa=dwa,
            w_soc_title=soc,
            include_soc_title=(soc > 0),
            final_output_path=str(SWEEP_OUT / f"{tag}_crosswalk.csv"),
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
            final_output_path=str(SWEEP_OUT / f"{name}_crosswalk.csv"),
        ))

done = [c for c in configs if Path(c.final_output_path).exists()]
todo = [c for c in configs if not Path(c.final_output_path).exists()]

print(f"Focused sweep: {len(configs)} total | {len(done)} done | {len(todo)} to run")
print(f"  Grid: {len(W_DWA_GRID)}×{len(W_SOC_TITLE_GRID)}×{len(W_ISCO_SETTINGS)} = "
      f"{len(W_DWA_GRID)*len(W_SOC_TITLE_GRID)*len(W_ISCO_SETTINGS)} combos"
      if mode != "--random-only" else "")
print()

# ── Run ───────────────────────────────────────────────────────────────────────
new_run_outputs = []
interrupted = False
try:
    for i, cfg in enumerate(todo):
        print(f"[{i+1}/{len(todo)}] {cfg.dataset_name}")
        new_run_outputs.append(run_pipeline(cfg))
except KeyboardInterrupt:
    interrupted = True
    print(f"\n[INTERRUPTED] {len(new_run_outputs)}/{len(todo)} completed — saving progress...")
    done = [c for c in configs if Path(c.final_output_path).exists()]

# ── Build combined summary ────────────────────────────────────────────────────
all_run_outputs = list(new_run_outputs)
done_names = {c.dataset_name for c in done}
results_root = ROOT_DIR / base.output_dir

for manifest in results_root.glob("*/*/manifest.json"):
    dataset_name = manifest.parents[1].name
    if dataset_name not in done_names:
        continue
    with open(manifest) as f:
        m = json.load(f)
    all_run_outputs.append({
        "run_id": m.get("run_id", manifest.parent.name),
        "stage_paths": m.get("stage_paths", {}),
        "metrics_path": str(manifest.parent / "metrics.csv"),
        "manifest_path": str(manifest),
        "config": None,
    })

rows = []
for run_output in all_run_outputs:
    metrics_path = Path(run_output["metrics_path"])
    if not metrics_path.exists():
        continue
    metrics_df = _load_metrics(run_output)
    cfg_obj = run_output.get("config")
    if cfg_obj is not None:
        cfg_data = _flatten_config(cfg_obj)
    else:
        with open(run_output["manifest_path"]) as f:
            cfg_data = json.load(f).get("config", {})

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
        ["pareto_candidate", "selection_score"], ascending=[False, False]
    ).reset_index(drop=True)
    results["selection_rank"] = range(1, len(results) + 1)

results.to_csv(SUMMARY_PATH, index=False)

status = "interrupted" if interrupted else "complete"
print(f"\nFocused sweep {status}. {len(results)} variants: {SUMMARY_PATH}")
if "pareto_candidate" in results.columns:
    print(f"Pareto candidates: {int(results['pareto_candidate'].sum())}")

available = [c for c in DISPLAY_COLS if c in results.columns]
print(f"\nTop 10:\n{results[available].head(10).to_string(index=False)}")
