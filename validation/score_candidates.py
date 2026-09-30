"""
score_candidates.py
====================
Computes the paper's sweep-score formula (Appendix A) directly from candidate
crosswalk output files, so config selection never again has to rely on a
hardcoded docstring in update_configs.py.

    sweep_score = (3*coverage + 2*mean_sim - 2*overload_share - 2*gini) / 9

  - coverage        = distinct ISCO-08 groups assigned (is_best==True rows) / 436
  - mean_sim        = mean `similarity` of is_best==True rows
  - overload_share  = share of tasks assigned to an "overloaded" ISCO group,
                       where a group is overloaded if its task count exceeds
                       T = max(overload_abs, overload_quantile-th pct of
                       per-group task counts) — see config.compute_overload_threshold,
                       using each candidate's own overload_abs/overload_quantile.
  - gini            = Gini coefficient of per-group task counts (metrics_unsup.compute_gini)

This reproduces the same numbers pipeline.py's own S2_TASK_FILTER (final-stage)
unsupervised metrics would produce, but computed standalone from the
already-materialized candidate CSVs in output/candidates/, so it does not
require re-running the pipeline.

Run from the project root:
    python validation/score_candidates.py
"""

from __future__ import annotations

import sys
from dataclasses import replace
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import KNOWN_FIELDS, compute_overload_threshold, load_config
from metrics_unsup import compute_gini
from pipeline import load_isco_standard

from compare_onet29_candidates import CANDIDATES, PROJECT_DIR, _candidate_output_path

RESULTS_DIR = PROJECT_DIR / "validation" / "results"
RESULTS_DIR.mkdir(parents=True, exist_ok=True)


def _build_candidate_config(item: dict[str, object], base_cfg):
    label = str(item["label"])
    safe_overrides = {k: v for k, v in item["overrides"].items() if k in KNOWN_FIELDS}
    return replace(
        base_cfg,
        dataset_name=label,
        checkpoint_prefix="ONET29",
        final_output_path=str(_candidate_output_path(label)),
        slim_output=False,
        **safe_overrides,
    )


def score_candidate(label: str, cfg, n_isco_universe: int) -> dict[str, object]:
    path = Path(getattr(cfg, "final_output_path"))
    if not path.exists():
        raise FileNotFoundError(
            f"Candidate output not found for '{label}': {path}. "
            "Run validation/compare_onet29_candidates.py first to materialize it."
        )
    df = pd.read_csv(path)
    best = df[df["is_best"] == True].copy()  # noqa: E712
    target_col = "target_id" if "target_id" in best.columns else "iscoGroup"
    best = best.rename(columns={target_col: "target_id"}) if target_col != "target_id" else best

    coverage = best["target_id"].nunique() / n_isco_universe
    mean_sim = float(best["similarity"].mean())

    counts = best.groupby("target_id")["task_id"].nunique()
    overload_thr = compute_overload_threshold(counts, cfg)
    overloaded = set(counts[counts > overload_thr].index)
    overload_share = (
        best[best["target_id"].isin(overloaded)]["task_id"].nunique() / best["task_id"].nunique()
    )

    gini = compute_gini(counts.to_numpy())

    sweep_score = (3 * coverage + 2 * mean_sim - 2 * overload_share - 2 * gini) / 9

    return {
        "candidate_label": label,
        "w_dwa": cfg.w_dwa,
        "w_soc_title": cfg.w_soc_title,
        "w_isco": cfg.w_isco,
        "w_isco_task": cfg.w_isco_task,
        "w_occ": cfg.w_occ,
        "coverage": round(coverage, 4),
        "mean_sim": round(mean_sim, 4),
        "overload_share": round(overload_share, 4),
        "gini": round(gini, 4),
        "sweep_score": round(sweep_score, 5),
    }


def main() -> pd.DataFrame:
    base_cfg = load_config(PROJECT_DIR / "configs" / "config_onet292.yaml")
    df_isco_groups, _ = load_isco_standard(base_cfg)
    n_isco_universe = len(df_isco_groups)

    rows = []
    for item in CANDIDATES:
        cfg = _build_candidate_config(item, base_cfg)
        rows.append(score_candidate(str(item["label"]), cfg, n_isco_universe))

    result = pd.DataFrame(rows).sort_values("sweep_score", ascending=False).reset_index(drop=True)

    out_path = RESULTS_DIR / "candidate_sweep_scores.csv"
    result.to_csv(out_path, index=False)

    print(f"ISCO-08 universe size: {n_isco_universe}")
    print(result.to_string(index=False))
    print(f"\nWrote: {out_path}")
    print(f"\nWinner: {result.iloc[0]['candidate_label']} (sweep_score={result.iloc[0]['sweep_score']})")
    return result


if __name__ == "__main__":
    main()
