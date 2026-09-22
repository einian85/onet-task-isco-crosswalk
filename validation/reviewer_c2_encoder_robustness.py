"""
reviewer_c2_encoder_robustness.py
===================================
Reviewer #4: task-level disagreement between encoders (paper's Appendix F reports
MPNet vs BGE 73.4%, MPNet vs GTE 75.0%, BGE vs GTE 87.6% exact agreement, under the OLD
config) - does that disagreement wash out once collapsed to occupation (SOC) level, or
does it concentrate in specific ISCO groups / occupation types?

Uses the three O*NET 29.2 encoder outputs from Phase B3 (all under the corrected
production config): all-mpnet-base-v2 (production), BAAI/bge-large-en-v1.5,
thenlper/gte-large.

Outputs (validation/results/):
  reviewer_c2_task_level_agreement.csv        — pairwise task-level agreement (like the
                                                 paper's existing Appendix F numbers)
  reviewer_c2_occupation_level_agreement.csv  — pairwise agreement after collapsing to
                                                 one (SOC-occupation) row via each SOC's
                                                 plurality ISCO assignment
  reviewer_c2_disagreement_by_major_group.csv — where task-level disagreement concentrates

Run from the project root:
    python validation/reviewer_c2_encoder_robustness.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared import PROJECT_DIR, load_onet_tasks  # noqa: E402

RESULTS_DIR = PROJECT_DIR / "validation" / "results"

ENCODERS = {
    "mpnet": PROJECT_DIR / "output" / "ONET292_task_to_ISCO_crosswalk.csv",
    "bge": PROJECT_DIR / "output" / "ONET292_bge_task_to_ISCO_crosswalk.csv",
    "gte": PROJECT_DIR / "output" / "ONET292_gte_task_to_ISCO_crosswalk.csv",
}

PAIRS = [("mpnet", "bge"), ("mpnet", "gte"), ("bge", "gte")]


def load_encoder_output(path: Path) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "is_best" in df.columns:
        df = df[df["is_best"] == True].copy()  # noqa: E712
    df["task_id"] = pd.to_numeric(df["task_id"], errors="coerce").astype("Int64")
    df["isco_code"] = pd.to_numeric(df["iscoGroup"], errors="coerce").astype("Int64")
    return df[["task_id", "isco_code"]].drop_duplicates("task_id")


def match_rates(a: pd.Series, b: pd.Series) -> dict:
    exact = (a == b).mean()
    sub_major = ((a // 100) == (b // 100)).mean()
    major = ((a // 1000) == (b // 1000)).mean()
    return {
        "pct_exact": round(float(exact) * 100, 1),
        "pct_sub_major": round(float(sub_major) * 100, 1),
        "pct_major_group": round(float(major) * 100, 1),
    }


def task_level_agreement(encoders: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows = []
    for left, right in PAIRS:
        merged = encoders[left].merge(encoders[right], on="task_id", suffixes=("_l", "_r"))
        rates = match_rates(merged["isco_code_l"], merged["isco_code_r"])
        rows.append({"pair": f"{left} vs {right}", "n_tasks": len(merged), **rates})
    return pd.DataFrame(rows)


def occupation_level_top1(encoder_df: pd.DataFrame, task_soc: pd.DataFrame) -> pd.DataFrame:
    """For each SOC occupation, its plurality (most common) ISCO assignment under this encoder."""
    joined = encoder_df.merge(task_soc[["task_id", "soc_code"]], on="task_id", how="inner")
    counts = joined.groupby(["soc_code", "isco_code"], as_index=False).size()
    counts = counts.sort_values(["soc_code", "size", "isco_code"], ascending=[True, False, True])
    top1 = counts.drop_duplicates("soc_code", keep="first")[["soc_code", "isco_code"]]
    return top1


def occupation_level_agreement(encoders: dict[str, pd.DataFrame], task_soc: pd.DataFrame) -> pd.DataFrame:
    top1s = {name: occupation_level_top1(df, task_soc) for name, df in encoders.items()}
    rows = []
    for left, right in PAIRS:
        merged = top1s[left].merge(top1s[right], on="soc_code", suffixes=("_l", "_r"))
        rates = match_rates(merged["isco_code_l"], merged["isco_code_r"])
        rows.append({"pair": f"{left} vs {right}", "n_soc_occupations": len(merged), **rates})
    return pd.DataFrame(rows)


def disagreement_by_major_group(encoders: dict[str, pd.DataFrame]) -> pd.DataFrame:
    """Where task-level disagreement concentrates, by MPNet's own major-group assignment."""
    rows = []
    for left, right in PAIRS:
        merged = encoders[left].merge(encoders[right], on="task_id", suffixes=("_l", "_r"))
        merged["major_group_l"] = merged["isco_code_l"] // 1000
        merged["disagree"] = merged["isco_code_l"] != merged["isco_code_r"]
        by_group = merged.groupby("major_group_l", as_index=False).agg(
            n_tasks=("task_id", "count"),
            pct_disagree=("disagree", lambda s: round(float(s.mean()) * 100, 1)),
        )
        by_group.insert(0, "pair", f"{left} vs {right}")
        rows.append(by_group)
    return pd.concat(rows, ignore_index=True)


def main() -> None:
    for name, path in ENCODERS.items():
        if not path.exists():
            raise FileNotFoundError(f"Missing encoder output for '{name}': {path}")
    encoders = {name: load_encoder_output(path) for name, path in ENCODERS.items()}
    task_soc = load_onet_tasks("29.2")

    task_agreement = task_level_agreement(encoders)
    print("Task-level pairwise agreement:")
    print(task_agreement.to_string(index=False))
    task_agreement.to_csv(RESULTS_DIR / "reviewer_c2_task_level_agreement.csv", index=False)

    occ_agreement = occupation_level_agreement(encoders, task_soc)
    print("\nOccupation-level (SOC plurality) pairwise agreement:")
    print(occ_agreement.to_string(index=False))
    occ_agreement.to_csv(RESULTS_DIR / "reviewer_c2_occupation_level_agreement.csv", index=False)

    print("\nDelta (occupation-level exact agreement minus task-level exact agreement):")
    delta = occ_agreement[["pair", "pct_exact"]].merge(
        task_agreement[["pair", "pct_exact"]], on="pair", suffixes=("_occ", "_task")
    )
    delta["delta_pp"] = round(delta["pct_exact_occ"] - delta["pct_exact_task"], 1)
    print(delta.to_string(index=False))

    by_group = disagreement_by_major_group(encoders)
    by_group.to_csv(RESULTS_DIR / "reviewer_c2_disagreement_by_major_group.csv", index=False)
    print(f"\nWrote: {RESULTS_DIR / 'reviewer_c2_task_level_agreement.csv'}")
    print(f"Wrote: {RESULTS_DIR / 'reviewer_c2_occupation_level_agreement.csv'}")
    print(f"Wrote: {RESULTS_DIR / 'reviewer_c2_disagreement_by_major_group.csv'}")


if __name__ == "__main__":
    main()
