"""
4_run_sweep_onet25.py
=====================
Runs the ONET25 pipeline across all w_soc_title sweep points.
Builds each variant's RunConfig programmatically from config_onet25.yaml —
no individual per-weight YAML files needed.

Strategy: runs wt10 first to compute and cache raw task/title embeddings,
then copies them to all other variants before running the remaining sweep
(so subsequent runs only recompute the fast blend step, not model inference).

Skips any variant whose output CSV already exists.

Run from the project root:
    python sweep/4_run_sweep_onet25.py
"""

from __future__ import annotations

import shutil
import sys
from dataclasses import replace
from pathlib import Path

ROOT_DIR = Path(__file__).resolve().parent.parent
sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(ROOT_DIR))

from config import load_config
from pipeline import run_pipeline, checkpoint_path

BASE_CONFIG = str(ROOT_DIR / "config_onet25.yaml")

SWEEP_WEIGHTS = [0.10, 0.20, 0.30, 0.40, 0.50, 0.60,
                 0.65, 0.70, 0.75, 0.80, 0.85, 0.90, 0.99]

RAW_NAMES = ["onet_task_emb_raw", "onet_title_emb_raw"]


def w_tag(w: float) -> str:
    pct = round(w * 100)
    return f"wt{pct:02d}" if pct < 100 else "wt100"


def make_cfg(base, w: float):
    name = f"ONET25_{w_tag(w)}"
    return replace(base,
        dataset_name=name,
        checkpoint_prefix=name,
        w_soc_title=w,
        include_soc_title=(w > 0),
        final_output_path=str(ROOT_DIR / "output" / f"{name}_task_to_ISCO_crosswalk.csv"),
    )


base = load_config(BASE_CONFIG)
cfgs = [make_cfg(base, w) for w in SWEEP_WEIGHTS]

# ── Step 1: Run first variant to generate raw embeddings ─────────────────────
first = cfgs[0]
if Path(first.final_output_path).exists():
    print(f"[SKIP] {first.dataset_name} (already exists)")
else:
    print(f"\n{'='*60}\n[RUN]  {first.dataset_name}  (seed — generates raw embeddings)\n{'='*60}")
    result = run_pipeline(first)
    print(f"[DONE] run_id={result['run_id']}")

# ── Step 2: Copy raw embeddings to all remaining variants ─────────────────────
print("\n[PREP] Copying raw embeddings to remaining variants...")
for tgt in cfgs[1:]:
    for name in RAW_NAMES:
        src = checkpoint_path(first, name)
        dst = checkpoint_path(tgt, name)
        if not src.exists():
            print(f"  [MISSING] {src.name}")
            continue
        if dst.exists():
            continue
        shutil.copy2(src, dst)
        print(f"  [COPIED]  {src.name} -> {dst.name}")

# ── Step 3: Run remaining variants ─────────────────────────────────────────────
for cfg in cfgs[1:]:
    out = Path(cfg.final_output_path)
    if out.exists():
        print(f"[SKIP] {cfg.dataset_name}")
        continue
    print(f"\n{'='*60}\n[RUN]  {cfg.dataset_name}  (w_soc_title={cfg.w_soc_title})\n{'='*60}")
    result = run_pipeline(cfg)
    print(f"[DONE] run_id={result['run_id']}")

print("\nONET25 sweep complete.")
