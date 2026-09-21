"""
audit_chain_disagreements.py
=============================
Where the task-level pipeline disagrees with the occupation-level chain crosswalk (lenient union,
scenario A4), is that a pipeline error or is it the pipeline seeing something the chain crosswalk
cannot — genuine task-level heterogeneity within a SOC occupation, which is the paper's central
claim? The chain crosswalk only ever assigns one (or a small closed set of) ISCO code(s) per whole
SOC occupation; it cannot distinguish between two tasks in the same occupation that plausibly belong
in different ISCO groups.

This does NOT feed back into config/parameter selection (see update_configs.py, CONFIG_SELECTION_LOG.md
for why selection must stay independent of validation). It's a qualitative check on the selected
config's disagreements, and doubles as the data Reviewer #1's within-SOC heterogeneity question
(REVISION_TASKS_SJI.md Phase C1) needs.

Run from the project root:
    python validation/audit_chain_disagreements.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import load_config
from pipeline import load_isco_standard
from shared import (
    GT_RESULTS_DIR,
    PROJECT_DIR,
    evaluate_match,
    load_onet_tasks,
    load_pipeline,
    load_soc18_crosswalks,
)

CANDIDATE_PATH = PROJECT_DIR / "output" / "candidates" / "ONET29_sw_s375_d266_i38_t73_o16_task_to_ISCO_crosswalk.csv"
RANDOM_SEED = 42


def _lenient_union_crosswalk() -> pd.DataFrame:
    xw18 = load_soc18_crosswalks()
    xw18_1 = xw18["xw18_1"][["soc_code18", "isco_code"]]
    xw18_2 = xw18["xw18_2"][["soc_code18", "isco_code"]]
    return pd.concat([xw18_1, xw18_2]).drop_duplicates().reset_index(drop=True)


def _isco_titles() -> pd.Series:
    base_cfg = load_config(PROJECT_DIR / "configs" / "config_onet292.yaml")
    df_groups, _ = load_isco_standard(base_cfg)
    df_groups = df_groups.copy()
    df_groups["isco_code"] = pd.to_numeric(df_groups["isco_code"], errors="coerce").astype("Int64")
    return df_groups.set_index("isco_code")["title_en"]


def within_soc_heterogeneity(dt: pd.DataFrame) -> pd.DataFrame:
    """Reviewer #1: how many distinct ISCO groups does each SOC occupation's tasks span?"""
    per_soc = dt.groupby("soc_code")["isco_pred"].nunique().rename("n_distinct_isco")
    n_tasks = dt.groupby("soc_code")["isco_pred"].size().rename("n_tasks")
    out = pd.concat([per_soc, n_tasks], axis=1).reset_index()
    return out.sort_values("n_distinct_isco", ascending=False)


def main() -> None:
    pipeline_df = load_pipeline(CANDIDATE_PATH)
    if "is_best" in pipeline_df.columns:
        pipeline_df = pipeline_df[pipeline_df["is_best"] == True].copy()  # noqa: E712

    task_soc = load_onet_tasks("29.2")
    crosswalk = _lenient_union_crosswalk()
    isco_titles = _isco_titles()

    dt = evaluate_match(pipeline_df, task_soc, crosswalk, "soc_code18")
    dt = dt.merge(task_soc[["task_id", "task_text", "soc_title"]], on="task_id", how="left")

    covered = dt[dt["in_crosswalk"] == True].copy()  # noqa: E712
    disagreements = covered[covered["match_exact"] == False].copy()  # noqa: E712

    print(f"Tasks covered by chain crosswalk: {len(covered)}")
    print(f"Disagreements (pred ISCO not in chain's acceptable set): {len(disagreements)} "
          f"({100 * len(disagreements) / len(covered):.1f}%)")
    print(f"Disagreements by similarity bin:")
    print(disagreements["sim_bin"].value_counts().sort_index().to_string())

    disagreements["our_isco_title"] = disagreements["isco_pred"].map(isco_titles)
    disagreements["chain_acceptable_titles"] = disagreements["acceptable_iscos"].apply(
        lambda codes: "; ".join(
            f"{c} {isco_titles.get(c, '?')}" for c in sorted(codes)
        )
    )

    out_cols = [
        "task_id", "soc_code", "soc_title", "task_text",
        "isco_pred", "our_isco_title", "similarity",
        "chain_acceptable_titles",
    ]
    disagreements_out = disagreements[out_cols].sort_values("similarity", ascending=False)
    full_path = GT_RESULTS_DIR / "chain_disagreements_full.csv"
    disagreements_out.to_csv(full_path, index=False)
    print(f"\nWrote all {len(disagreements_out)} disagreements: {full_path}")

    # A stratified sample for manual review: weighted toward high-similarity disagreements,
    # since those are the most likely to be genuine task-level signal rather than pipeline noise.
    sample_parts = []
    for sim_bin, n in [("[0.70,1.00]", 25), ("[0.60,0.70)", 15), ("[0.50,0.60)", 10), ("[0.45,0.50)", 10)]:
        bucket = disagreements_out[disagreements_out["task_id"].isin(
            disagreements.loc[disagreements["sim_bin"] == sim_bin, "task_id"]
        )]
        sample_parts.append(bucket.sample(n=min(n, len(bucket)), random_state=RANDOM_SEED))
    sample = pd.concat(sample_parts).sort_values("similarity", ascending=False)
    sample_path = GT_RESULTS_DIR / "chain_disagreements_sample_for_review.csv"
    sample.to_csv(sample_path, index=False)
    print(f"Wrote {len(sample)}-row stratified sample for manual review: {sample_path}")

    # Reviewer #1 (within-SOC heterogeneity)
    heterogeneity = within_soc_heterogeneity(dt)
    het_path = GT_RESULTS_DIR / "within_soc_heterogeneity.csv"
    heterogeneity.to_csv(het_path, index=False)
    share_multi = (heterogeneity["n_distinct_isco"] > 1).mean()
    print(f"\nShare of SOC occupations whose tasks span >1 ISCO group: {100 * share_multi:.1f}%")
    print(f"Mean/median distinct ISCO groups per SOC occupation: "
          f"{heterogeneity['n_distinct_isco'].mean():.2f} / {heterogeneity['n_distinct_isco'].median():.1f}")
    print(f"Wrote: {het_path}")


if __name__ == "__main__":
    main()
