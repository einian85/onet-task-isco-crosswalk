"""
reviewer_c4_coverage_reconciliation.py
========================================
Editor's flagged inconsistency: the paper's Appendix A claims "coverage 100%" for the
selected configuration, while the abstract/conclusion cite ~92% (401-404 of 436 ISCO-08
groups). Confirms exactly which pipeline stage each number corresponds to, using the
CURRENT (corrected-config) production output rather than assuming the old explanation
still holds.

Root cause (see CONFIG_SELECTION_LOG.md for the full account): the "100%" came from a
code bug where two different things got conflated -
  1. an intermediate-stage coverage figure being displayed as if it were final-assignment
     coverage (report_publication.py / export_latex.py read an S3_COVERAGE-labeled column
     that, after a pipeline refactor, no longer corresponds to a real distinct filtering
     stage), and
  2. that intermediate figure being read off the wrong ranked row entirely (a different,
     undocumented composite score than the one described in Appendix A) - see
     CONFIG_SELECTION_LOG.md, "Deeper bug found."

This script demonstrates the actual, current magnitude of the gap directly: pipeline.py's
STAGES are exactly S1_RETRIEVE (raw top-k retrieval, k=5 by default - loose, no threshold)
and S2_TASK_FILTER (final: similarity threshold + margin + one best link per task). "100%"-
like coverage is a real, unsurprising property of the loose retrieval stage (with k=5
candidates x ~18,800 tasks, nearly every one of 436 ISCO groups gets touched by something's
top-5 list) - it was never a property of the actual final crosswalk.

Run from the project root:
    python validation/reviewer_c4_coverage_reconciliation.py
"""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from config import load_config  # noqa: E402
from pipeline import load_isco_standard  # noqa: E402

PROJECT_DIR = Path(__file__).resolve().parent.parent
PRODUCTION_CROSSWALK = PROJECT_DIR / "output" / "ONET292_task_to_ISCO_crosswalk.csv"


def _latest_run_id_for(final_output_path: str) -> str:
    target = final_output_path.replace("\\", "/")
    matches = []
    for manifest in (PROJECT_DIR / "results" / "predictions").glob("*/run_manifest.json"):
        d = json.loads(manifest.read_text(encoding="utf-8"))
        cfg_path = d.get("config", {}).get("final_output_path", "").replace("\\", "/")
        if cfg_path == target or cfg_path.endswith(Path(target).name):
            matches.append((manifest, d["run_id"]))
    if not matches:
        raise FileNotFoundError(f"No manifest found for {final_output_path}")
    return max(matches, key=lambda x: x[0].stat().st_mtime)[1]


def main() -> None:
    base_cfg = load_config(PROJECT_DIR / "configs" / "config_onet292.yaml")
    df_groups, _ = load_isco_standard(base_cfg)
    n_universe = len(df_groups)

    run_id = _latest_run_id_for("output/ONET292_task_to_ISCO_crosswalk.csv")
    s1_path = PROJECT_DIR / "results" / "predictions" / run_id / "S1_RETRIEVE.csv"
    if not s1_path.exists():
        raise FileNotFoundError(
            f"{s1_path} not found - run with slim_output=False (production default) so the "
            "S1_RETRIEVE snapshot is written."
        )
    s1 = pd.read_csv(s1_path)
    s1_coverage_groups = s1["iscoGroup"].astype(str).nunique()

    final = pd.read_csv(PRODUCTION_CROSSWALK)
    if "is_best" in final.columns:
        final = final[final["is_best"] == True].copy()  # noqa: E712
    final_coverage_groups = final["iscoGroup"].astype(str).nunique()

    print(f"ISCO-08 universe (Level-4 unit groups): {n_universe}")
    print()
    print(f"S1_RETRIEVE (raw top-{base_cfg.k_retrieve} candidates, no threshold/margin/dedup):")
    print(f"  Distinct ISCO groups touched: {s1_coverage_groups} / {n_universe} "
          f"({100 * s1_coverage_groups / n_universe:.1f}%)")
    print()
    print(f"S2_TASK_FILTER (final: similarity >= {base_cfg.min_sim}, margin <= {base_cfg.margin_best}, "
          f"one best link per task):")
    print(f"  Distinct ISCO groups touched: {final_coverage_groups} / {n_universe} "
          f"({100 * final_coverage_groups / n_universe:.1f}%)")
    print()
    print("Suggested reconciling sentence for the paper:")
    print(
        f'  "The apparent discrepancy between near-complete ISCO-08 group coverage reported '
        f'during candidate screening and the {100 * final_coverage_groups / n_universe:.0f}% '
        f'({final_coverage_groups}/{n_universe}) figure reported for the final crosswalk reflects '
        f'two different pipeline stages: {100 * s1_coverage_groups / n_universe:.0f}% of groups '
        f'are touched by some task\'s unfiltered top-{base_cfg.k_retrieve} retrieval candidates, '
        f'but only {100 * final_coverage_groups / n_universe:.0f}% remain after applying the '
        f'similarity threshold, margin, and one-best-link-per-task selection that define the '
        f'actual final assignment."'
    )


if __name__ == "__main__":
    main()
