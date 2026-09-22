"""
reviewer_c3_objective_sensitivity.py
======================================
Reviewer #5: is the paper's composite sweep-score formula's specific weighting
(3*coverage + 2*similarity - 2*overload - 2*gini)/9 arbitrary, and would a differently
weighted objective select a materially different configuration?

STRATEGY (see CONFIG_SELECTION_LOG.md for why this shape, not a different one):

1. Test against the full 16,000-candidate systematic sweep
   (results/summary/sweep_results_metrics_only.csv), not just the small validated
   shortlist (jf_*/fg_/sw_) - that shortlist was itself only ever a handful of points
   near two different regions of parameter space, and has nowhere near the statistical
   power for a sensitivity claim across the whole design space.

2. A fixed, pre-specified set of alternative formulas (not tuned to produce a particular
   answer) - each testing a specific, articulable objection to the baseline weighting:
     - equal_1111        : removes the assumption that coverage should dominate
     - coverage_only      : isolates the highest-weighted term
     - similarity_only    : isolates pure retrieval-quality, ignoring distributional shape
     - no_gini            : tests whether the Gini penalty alone is doing the work
     - no_overload        : tests whether the overload penalty alone is doing the work
     - gini_doubled       : tests over-penalizing concentration relative to baseline
     - coverage_deprioritized : coverage's weight of 3 (vs 2 for the others) was chosen for
                            an ordinal reason in Appendix A ("smallest integer strictly
                            greater than 2"), not a magnitude argument - this variant
                            weakens it to test how load-bearing that specific choice is

3. For each formula: report the argmax over the full 16,000 candidates (what config that
   formula alone would pick), the Spearman rank correlation between that formula's full
   ranking and the baseline formula's full ranking (the standard summary statistic for "how
   much does the ranking change"), and the Jaccard overlap of the two formulas' top-10 sets.

4. Separately, and NOT part of the ranking/selection test above: show how each formula
   scores the already-validated candidate shortlist, since that's the set actually discussed
   elsewhere in the paper and readers will want to see it react to formula changes too.

This is a diagnostic/robustness report only. It must not, and does not, feed back into
config selection - selection is already finalized independent of validation (see
CONFIG_SELECTION_LOG.md / project_config_selection_bug memory). Re-running this script with
a different formula list does not change configs/config_onet*.yaml.

Outputs (validation/results/):
  reviewer_c3_formula_sensitivity.csv   — one row per formula: argmax config, distance from
                                           baseline argmax, Spearman rho, top-10 Jaccard
  reviewer_c3_shortlist_under_formulas.csv — the validated candidate shortlist's score/rank
                                           under every formula

Run from the project root:
    python validation/reviewer_c3_objective_sensitivity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import numpy as np
import pandas as pd
from scipy.stats import spearmanr

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from compare_onet29_candidates import CANDIDATES  # noqa: E402

RESULTS_DIR = Path(__file__).resolve().parent / "results"
SWEEP_PATH = Path(__file__).resolve().parent.parent / "results" / "summary" / "sweep_results_metrics_only.csv"
SWEEP_SCORE_PATH = RESULTS_DIR / "candidate_sweep_scores.csv"

PARAM_COLS = ["w_soc_title", "w_dwa", "w_isco", "w_isco_task", "w_occ"]

# name -> (w_coverage, w_similarity, w_overload, w_gini)
FORMULAS: dict[str, tuple[float, float, float, float]] = {
    "baseline_3220": (3, 2, 2, 2),
    "equal_1111": (1, 1, 1, 1),
    "coverage_only": (1, 0, 0, 0),
    "similarity_only": (0, 1, 0, 0),
    "no_gini": (3, 2, 2, 0),
    "no_overload": (3, 2, 0, 2),
    "gini_doubled": (3, 2, 2, 4),
    "coverage_deprioritized_1222": (1, 2, 2, 2),
}


def score(df: pd.DataFrame, weights: tuple[float, float, float, float]) -> pd.Series:
    wc, ws, wo, wg = weights
    denom = wc + ws + wo + wg
    cov = df["S5_FINAL_isco_coverage_share"]
    sim = df["S5_FINAL_mean_similarity_retained"]
    overload = df["S5_FINAL_share_tasks_in_overloaded_isco"]
    gini = df["S5_FINAL_gini_tasks_per_isco"]
    return (wc * cov + ws * sim - wo * overload - wg * gini) / denom


def top10_jaccard(a_idx: pd.Index, b_idx: pd.Index) -> float:
    a, b = set(a_idx), set(b_idx)
    return len(a & b) / len(a | b) if (a | b) else float("nan")


def weight_distance(row_a: pd.Series, row_b: pd.Series) -> float:
    return float(np.sqrt(sum((row_a[c] - row_b[c]) ** 2 for c in PARAM_COLS)))


def analyze_full_sweep(df: pd.DataFrame) -> pd.DataFrame:
    baseline_scores = score(df, FORMULAS["baseline_3220"])
    baseline_argmax_row = df.loc[baseline_scores.idxmax()]
    baseline_top10 = baseline_scores.nlargest(10).index

    rows = []
    for name, weights in FORMULAS.items():
        s = score(df, weights)
        argmax_row = df.loc[s.idxmax()]
        rho, _ = spearmanr(baseline_scores, s)
        jac = top10_jaccard(baseline_top10, s.nlargest(10).index)
        rows.append(
            {
                "formula": name,
                "weights_cov_sim_overload_gini": str(weights),
                **{f"argmax_{c}": round(float(argmax_row[c]), 4) for c in PARAM_COLS},
                "distance_from_baseline_argmax": round(weight_distance(argmax_row, baseline_argmax_row), 4),
                "spearman_rho_vs_baseline": round(float(rho), 4),
                "top10_jaccard_vs_baseline": round(jac, 3),
            }
        )
    return pd.DataFrame(rows)


def analyze_validated_shortlist() -> pd.DataFrame:
    if not SWEEP_SCORE_PATH.exists():
        print(f"[skip] {SWEEP_SCORE_PATH} not found - run validation/score_candidates.py first "
              "to get real per-candidate metrics for the shortlist table.")
        return pd.DataFrame()
    scores_df = pd.read_csv(SWEEP_SCORE_PATH)
    label_meta = {str(c["label"]): c for c in CANDIDATES}

    rows = []
    for _, r in scores_df.iterrows():
        label = r["candidate_label"]
        row_as_series = pd.Series(
            {
                "S5_FINAL_isco_coverage_share": r["coverage"],
                "S5_FINAL_mean_similarity_retained": r["mean_sim"],
                "S5_FINAL_share_tasks_in_overloaded_isco": r["overload_share"],
                "S5_FINAL_gini_tasks_per_isco": r["gini"],
            }
        )
        entry = {"candidate_label": label}
        for name, weights in FORMULAS.items():
            entry[name] = round(float(score(row_as_series.to_frame().T, weights).iloc[0]), 5)
        rows.append(entry)

    out = pd.DataFrame(rows)
    for name in FORMULAS:
        out[f"{name}_rank"] = out[name].rank(ascending=False, method="min").astype(int)
    return out


def main() -> None:
    df = pd.read_csv(SWEEP_PATH)
    print(f"Loaded {len(df)} candidates from the full systematic sweep.\n")

    sensitivity = analyze_full_sweep(df)
    print("Formula sensitivity (full 16,000-candidate sweep):")
    print(sensitivity.to_string(index=False))
    out1 = RESULTS_DIR / "reviewer_c3_formula_sensitivity.csv"
    sensitivity.to_csv(out1, index=False)
    print(f"\nWrote: {out1}")

    shortlist = analyze_validated_shortlist()
    if not shortlist.empty:
        print("\nValidated candidate shortlist, ranked under each formula "
              "(context only - not part of the selection process):")
        print(shortlist.to_string(index=False))
        out2 = RESULTS_DIR / "reviewer_c3_shortlist_under_formulas.csv"
        shortlist.to_csv(out2, index=False)
        print(f"\nWrote: {out2}")


if __name__ == "__main__":
    main()
