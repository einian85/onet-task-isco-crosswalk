"""
score_ablation.py
=================
Scores the production O*NET 29.2 output and the four ablation variants
(Appendix G) with the paper's sweep-score formula (Appendix A), using the same
scoring function as score_candidates.py. This answers whether the unsupervised
selection criterion ranks the ablation variants below production even where
they cover more ISCO-08 groups (SJI review, comment 5).

Requires the ablation outputs from run_ablation.py in output/.

Run from the project root:
    python validation/score_ablation.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import load_config
from pipeline import load_isco_standard
from score_candidates import PROJECT_DIR, RESULTS_DIR, score_candidate

VARIANTS = [
    ("production", "config_onet292.yaml", "ONET292"),
    ("no_soc_title", "config_onet292_abl_no_soc.yaml", "ONET292_abl_no_soc"),
    ("no_dwa", "config_onet292_abl_no_dwa.yaml", "ONET292_abl_no_dwa"),
    ("no_esco", "config_onet292_abl_no_esco.yaml", "ONET292_abl_no_esco"),
    ("task_text_only", "config_onet292_abl_task_only.yaml", "ONET292_abl_task_only"),
]


def main() -> pd.DataFrame:
    base_cfg = load_config(PROJECT_DIR / "configs" / "config_onet292.yaml")
    n_isco_universe = len(load_isco_standard(base_cfg)[0])

    rows = []
    for label, cfg_name, prefix in VARIANTS:
        cfg = load_config(PROJECT_DIR / "configs" / cfg_name)
        cfg = replace(cfg, final_output_path=str(PROJECT_DIR / "output" / f"{prefix}_task_to_ISCO_crosswalk.csv"))
        row = score_candidate(label, cfg, n_isco_universe)
        row["isco_groups"] = round(row["coverage"] * n_isco_universe)
        rows.append(row)

    result = pd.DataFrame(rows)
    out_path = RESULTS_DIR / "ablation_sweep_scores.csv"
    result.to_csv(out_path, index=False)
    print(result[["candidate_label", "isco_groups", "coverage", "mean_sim",
                  "overload_share", "gini", "sweep_score"]].to_string(index=False))
    print(f"\nWrote: {out_path}")
    return result


if __name__ == "__main__":
    main()
