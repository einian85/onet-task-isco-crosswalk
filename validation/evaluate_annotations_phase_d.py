"""
evaluate_annotations_phase_d.py
=================================
D4: evaluate the expanded (n=180) annotation pass plus the blind test-retest sample.

evaluate_annotations.py assumes a single n=108 pass and would double-count if pointed at the
expanded 200-row workbook directly (20 of those rows are blind repeats sharing a task_id with
a row already in the original 108). This script splits the workbook properly:

  - "official" n=180 set: the original 108 answers (unchanged) + the 72 genuinely new tasks.
    The 20 retest rows are EXCLUDED from this set - their task_id's canonical answer is
    already the original one, so including the repeat too would double-count that task.
  - test-retest pairs (n=20): original_expert_isco (validation/results/reviewer_d3_retest_key.csv,
    first pass) vs. the blind re-judged expert_isco for the same task_id in the "to annotate"
    block (second pass, same annotator, no access to the first answer while re-judging).

Outputs (validation/results/):
  human_eval_onet29_expanded_summary.csv  — n=180 exact/sub-major/major agreement + Wilson CIs,
                                             against the current production crosswalk
  human_eval_onet29_expanded_detail.csv   — per-task detail for the n=180 set
  human_eval_onet29_test_retest.csv       — the 20 original/re-judged pairs + agreement rates

Run from the project root:
    python validation/evaluate_annotations_phase_d.py
"""

from __future__ import annotations

import math
import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

matplotlib.use("Agg")

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared import GT_RESULTS_DIR, PROJECT_DIR, load_pipeline  # noqa: E402
from evaluate_annotations import match_flags, xw_sanity_check  # noqa: E402

WORKBOOK_PATH = GT_RESULTS_DIR / "annotation_workbook_onet29.xlsx"
RETEST_KEY_PATH = GT_RESULTS_DIR / "reviewer_d3_retest_key.csv"
PRODUCTION_CROSSWALK = PROJECT_DIR / "output" / "ONET292_task_to_ISCO_crosswalk.csv"


def wilson_ci(p: float, n: int, z: float = 1.96) -> tuple[float, float]:
    """p in [0,1], returns (lo, hi) as percentages."""
    if n == 0:
        return (float("nan"), float("nan"))
    center = (p + z**2 / (2 * n)) / (1 + z**2 / n)
    margin = (z / (1 + z**2 / n)) * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return round((center - margin) * 100, 1), round((center + margin) * 100, 1)


def load_workbook() -> pd.DataFrame:
    df = pd.read_excel(WORKBOOK_PATH, sheet_name="Validation", dtype=str)
    df.columns = df.columns.str.strip()
    df["expert_isco"] = df["expert_isco"].str.strip()
    df["task_id"] = pd.to_numeric(df["task_id"], errors="coerce").astype("Int64")
    df["expert_isco_int"] = pd.to_numeric(df["expert_isco"], errors="coerce").astype("Int64")
    unfilled = df["expert_isco"].isna() | (df["expert_isco"] == "")
    if unfilled.any():
        raise RuntimeError(f"{int(unfilled.sum())} rows still unfilled - finish annotating first.")
    return df


def split_official_and_retest(df: pd.DataFrame, retest_key: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    retest_ids = set(retest_key["task_id"])
    n_total = len(df)
    n_official_108 = n_total - 92  # everything except the 92-row "to annotate" block, by construction
    original_block = df.iloc[:n_official_108].copy()
    to_annotate_block = df.iloc[n_official_108:].copy()

    is_retest_row = to_annotate_block["task_id"].isin(retest_ids)
    genuinely_new = to_annotate_block[~is_retest_row].copy()
    retest_rejudged = to_annotate_block[is_retest_row].copy()

    official_180 = pd.concat([original_block, genuinely_new], ignore_index=True)
    if official_180["task_id"].duplicated().any():
        dupes = official_180.loc[official_180["task_id"].duplicated(), "task_id"].tolist()
        raise RuntimeError(f"Official n=180 set has duplicate task_ids: {dupes} - investigate.")

    return official_180, retest_rejudged


def evaluate_official_set(official: pd.DataFrame) -> pd.DataFrame:
    pipe = load_pipeline(PRODUCTION_CROSSWALK)
    if "candidate_rank" in pipe.columns:
        pipe = pipe[pipe["candidate_rank"] == 1].copy()
    pipe = pipe[["task_id", "isco_pred", "similarity"]]

    merged = official[["task_id", "expert_isco_int"]].merge(pipe, on="task_id", how="left")
    exact, sub_major, major_grp = match_flags(merged["expert_isco_int"], merged["isco_pred"])
    n = int(exact.notna().sum())

    rows = []
    for name, flags in [("exact", exact), ("sub_major", sub_major), ("major_group", major_grp)]:
        pct = float(flags.astype(float).mean())
        lo, hi = wilson_ci(pct, n)
        rows.append({"metric": name, "pct": round(pct * 100, 1), "ci_lo": lo, "ci_hi": hi, "n": n})

    summary = pd.DataFrame(rows)
    xw = xw_sanity_check(official.assign(expert_isco_int=official["expert_isco_int"]))
    print(f"  {xw['n_expert_isco']} expert ISCOs; {xw['pct_expert_in_xw']}% within crosswalk-acceptable set")

    detail = official.copy()
    detail["isco_pred"] = merged["isco_pred"].values
    detail["mean_similarity"] = merged["similarity"].values
    detail["match_exact"] = exact
    detail["match_sub_major"] = sub_major
    detail["match_major_group"] = major_grp
    return summary, detail, float(merged["similarity"].mean())


def evaluate_test_retest(retest_rejudged: pd.DataFrame, retest_key: pd.DataFrame) -> pd.DataFrame:
    paired = retest_rejudged[["task_id", "expert_isco_int"]].rename(
        columns={"expert_isco_int": "rejudged_expert_isco"}
    ).merge(
        retest_key.rename(columns={"original_expert_isco": "original_expert_isco_str"}),
        on="task_id",
        how="inner",
    )
    paired["original_expert_isco_int"] = pd.to_numeric(
        paired["original_expert_isco_str"], errors="coerce"
    ).astype("Int64")

    exact, sub_major, major_grp = match_flags(
        paired["original_expert_isco_int"], paired["rejudged_expert_isco"]
    )
    paired["retest_match_exact"] = exact
    paired["retest_match_sub_major"] = sub_major
    paired["retest_match_major_group"] = major_grp
    return paired


def main() -> None:
    df = load_workbook()
    retest_key = pd.read_csv(RETEST_KEY_PATH, dtype={"task_id": "Int64"})
    print(f"Loaded workbook: {len(df)} rows total. Retest key: {len(retest_key)} tasks.")

    official_180, retest_rejudged = split_official_and_retest(df, retest_key)
    print(f"\nOfficial set: {len(official_180)} unique tasks (should be 180).")
    print(f"Retest re-judged rows found: {len(retest_rejudged)} (should be {len(retest_key)}).")

    print("\n--- n=180 headline agreement (vs. current production crosswalk) -----------")
    summary, detail, mean_sim = evaluate_official_set(official_180)
    print(summary.to_string(index=False))

    print("\n--- Test-retest (intra-rater) agreement, n=%d pairs -------------------------" % len(retest_rejudged))
    paired = evaluate_test_retest(retest_rejudged, retest_key)
    retest_summary_rows = []
    for name, col in [
        ("exact", "retest_match_exact"),
        ("sub_major", "retest_match_sub_major"),
        ("major_group", "retest_match_major_group"),
    ]:
        n = int(paired[col].notna().sum())
        pct = float(paired[col].astype(float).mean())
        lo, hi = wilson_ci(pct, n)
        retest_summary_rows.append({"metric": name, "pct": round(pct * 100, 1), "ci_lo": lo, "ci_hi": hi, "n": n})
    retest_summary = pd.DataFrame(retest_summary_rows)
    print(retest_summary.to_string(index=False))

    disagreements = paired[paired["retest_match_exact"] == False]  # noqa: E712
    if not disagreements.empty:
        print(f"\n  {len(disagreements)} of {len(paired)} retest pairs disagreed at the exact level:")
        print(disagreements[["task_id", "original_expert_isco_str", "rejudged_expert_isco"]].to_string(index=False))

    detail_path = GT_RESULTS_DIR / "human_eval_onet29_expanded_detail.csv"
    summary_path = GT_RESULTS_DIR / "human_eval_onet29_expanded_summary.csv"
    retest_path = GT_RESULTS_DIR / "human_eval_onet29_test_retest.csv"
    detail.to_csv(detail_path, index=False)
    summary.to_csv(summary_path, index=False)
    paired.to_csv(retest_path, index=False)
    retest_summary.to_csv(GT_RESULTS_DIR / "human_eval_onet29_test_retest_summary.csv", index=False)

    # Also overwrite the canonical human_eval_onet29_summary.csv / _onet29.csv (the ones
    # verify_paper_numbers_v2.py / check_facts.py read) with the correct n=180 numbers, in
    # the same wide format the old n=108 pass used. Running evaluate_annotations.py directly
    # against the now-200-row workbook would naively double-count the 20 retest duplicates -
    # this is the authoritative replacement.
    canonical_summary = pd.DataFrame(
        [
            {
                "label": "onet29_current",
                "description": "Current ONET29.2 production config (expanded n=180, Phase D)",
                "n_judged": int(summary.loc[summary["metric"] == "exact", "n"].iloc[0]),
                "pct_exact": float(summary.loc[summary["metric"] == "exact", "pct"].iloc[0]),
                "pct_sub_major": float(summary.loc[summary["metric"] == "sub_major", "pct"].iloc[0]),
                "pct_major_group": float(summary.loc[summary["metric"] == "major_group", "pct"].iloc[0]),
                "mean_similarity": round(mean_sim, 3),
            }
        ]
    )
    canonical_summary.to_csv(GT_RESULTS_DIR / "human_eval_onet29_summary.csv", index=False)
    detail.to_csv(GT_RESULTS_DIR / "human_eval_onet29.csv", index=False)

    # Regenerate the canonical plot too - evaluate_annotations.py's own version, if re-run
    # directly against this workbook, would double-count the retest duplicates.
    fig, ax = plt.subplots(figsize=(6, 5))
    labels = ["Exact\n(4-digit)", "Sub-major\n(2-digit)", "Major\n(1-digit)"]
    pcts = summary.set_index("metric").loc[["exact", "sub_major", "major_group"], "pct"].tolist()
    ci_lo = summary.set_index("metric").loc[["exact", "sub_major", "major_group"], "ci_lo"].tolist()
    ci_hi = summary.set_index("metric").loc[["exact", "sub_major", "major_group"], "ci_hi"].tolist()
    errs = [[p - lo for p, lo in zip(pcts, ci_lo)], [hi - p for p, hi in zip(pcts, ci_hi)]]
    colors = ["C0", "C1", "C2"]
    ax.bar(labels, pcts, color=colors, yerr=errs, capsize=6)
    for i, p in enumerate(pcts):
        ax.text(i, p + 3, f"{p:.1f}%", ha="center", fontsize=10)
    ax.set_ylabel("Match rate (%)", fontsize=11)
    ax.set_title(f"ONET29 human annotation agreement, expanded set (n={len(official_180)})\n"
                 "95% Wilson CI error bars", fontsize=11)
    ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f%%"))
    ax.set_ylim(0, 100)
    ax.grid(True, axis="y", alpha=0.3)
    plt.tight_layout()
    plot_path = GT_RESULTS_DIR / "human_eval_onet29_by_variant.png"
    fig.savefig(plot_path, dpi=150)
    plt.close(fig)

    print(f"\nWrote: {detail_path}")
    print(f"Wrote: {summary_path}")
    print(f"Wrote: {retest_path}")
    print(f"Wrote: {GT_RESULTS_DIR / 'human_eval_onet29_test_retest_summary.csv'}")
    print(f"Wrote (canonical, n=180): {GT_RESULTS_DIR / 'human_eval_onet29_summary.csv'}")
    print(f"Wrote (canonical, n=180): {GT_RESULTS_DIR / 'human_eval_onet29.csv'}")
    print(f"Wrote (canonical, n=180): {plot_path}")


if __name__ == "__main__":
    main()
