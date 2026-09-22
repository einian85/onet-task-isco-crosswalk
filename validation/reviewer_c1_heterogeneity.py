"""
reviewer_c1_heterogeneity.py
=============================
Reviewer #1: does task-level crosswalking reveal within-SOC-occupation heterogeneity that
occupation-level (institutional) crosswalks cannot see?

For O*NET 29.2 (SOC 2018), compares two views of "how many ISCO-08 groups does a SOC
occupation map to":
  - task-level: distinct ISCO groups actually assigned across that SOC's tasks by the
    (corrected) production pipeline
  - occupation-level: distinct ISCO groups the institutional reference crosswalks
    (XW18.1 ESCO-to-ONET-SOC, XW18.2 ONET-SOC-to-ESCO — the same ones used for chain
    validation elsewhere in this project) assign to that whole SOC occupation

Reuses report_occupation.py's existing join/reference-crosswalk loading (DATASETS,
load_implied_links, aggregate_implied_soc_isco, load_reference_crosswalks,
reference_subset_for_soc_version) rather than re-deriving it.

Outputs (validation/results/):
  reviewer_c1_per_soc_heterogeneity.csv  — one row per SOC occupation
  reviewer_c1_summary.csv                — headline numbers

Run from the project root:
    python validation/reviewer_c1_heterogeneity.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from report_occupation import (  # noqa: E402
    DATASETS,
    aggregate_implied_soc_isco,
    load_implied_links,
    load_reference_crosswalks,
    reference_subset_for_soc_version,
)

RESULTS_DIR = Path(__file__).resolve().parent / "results"
TASK_COUNT_THRESHOLDS = [1, 5, 10, 20]


def task_level_heterogeneity(meta: dict) -> pd.DataFrame:
    implied_links = load_implied_links(meta)
    implied_pairs = aggregate_implied_soc_isco(implied_links)
    per_soc = implied_pairs.groupby("soc_code", as_index=False).agg(
        n_distinct_isco_task_level=("isco_code", "nunique"),
        n_tasks=("task_support", "sum"),
    )
    return per_soc


def occupation_level_heterogeneity(refs: dict[str, pd.DataFrame], soc_version: str) -> pd.DataFrame:
    subset = reference_subset_for_soc_version(refs, soc_version)
    frames = []
    for name, ref_df in subset.items():
        per_soc = ref_df.groupby("soc_code", as_index=False)["isco_code"].nunique()
        per_soc = per_soc.rename(columns={"isco_code": f"n_distinct_isco_{name}"})
        frames.append(per_soc.set_index("soc_code"))
    if not frames:
        return pd.DataFrame(columns=["soc_code"])
    combined = pd.concat(frames, axis=1).reset_index()
    return combined


def summarize(per_soc: pd.DataFrame, col: str, label: str) -> dict:
    valid = per_soc[col].dropna()
    return {
        "view": label,
        "n_soc_occupations": int(valid.shape[0]),
        "share_spanning_gt1_isco": round(float((valid > 1).mean()) * 100, 1) if len(valid) else float("nan"),
        "mean_distinct_isco": round(float(valid.mean()), 2) if len(valid) else float("nan"),
        "median_distinct_isco": float(valid.median()) if len(valid) else float("nan"),
        "max_distinct_isco": int(valid.max()) if len(valid) else 0,
    }


def main() -> None:
    meta = DATASETS["onet292_id"]
    refs = load_reference_crosswalks()

    task_level = task_level_heterogeneity(meta)
    occ_level = occupation_level_heterogeneity(refs, meta["soc_version"])

    merged = task_level.merge(occ_level, on="soc_code", how="left")
    out_path = RESULTS_DIR / "reviewer_c1_per_soc_heterogeneity.csv"
    merged.to_csv(out_path, index=False)
    print(f"Wrote per-SOC detail: {out_path}  ({len(merged)} SOC occupations)")

    summary_rows = [summarize(merged, "n_distinct_isco_task_level", "task-level (this pipeline)")]
    for col in [c for c in occ_level.columns if c.startswith("n_distinct_isco_")]:
        ref_name = col.replace("n_distinct_isco_", "")
        summary_rows.append(summarize(merged, col, f"occupation-level ({ref_name})"))

    summary = pd.DataFrame(summary_rows)
    print("\n" + summary.to_string(index=False))

    # Task-count-threshold breakdown for the task-level view (mean/median ISCO groups
    # per SOC occupation with >= N tasks) - the "with ≥N tasks" cut the task file asks for.
    print("\nTask-level heterogeneity by minimum SOC task count:")
    threshold_rows = []
    for n in TASK_COUNT_THRESHOLDS:
        sub = merged[merged["n_tasks"] >= n]["n_distinct_isco_task_level"]
        threshold_rows.append(
            {
                "min_tasks_per_soc": n,
                "n_soc_occupations": int(sub.shape[0]),
                "mean_distinct_isco": round(float(sub.mean()), 2) if len(sub) else float("nan"),
                "median_distinct_isco": float(sub.median()) if len(sub) else float("nan"),
            }
        )
    threshold_df = pd.DataFrame(threshold_rows)
    print(threshold_df.to_string(index=False))

    summary_path = RESULTS_DIR / "reviewer_c1_summary.csv"
    summary.to_csv(summary_path, index=False)
    threshold_path = RESULTS_DIR / "reviewer_c1_by_task_count.csv"
    threshold_df.to_csv(threshold_path, index=False)
    print(f"\nWrote: {summary_path}")
    print(f"Wrote: {threshold_path}")


if __name__ == "__main__":
    main()
