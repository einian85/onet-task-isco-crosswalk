"""
validate_chain.py
=================
Chain Crosswalk Validation

Validates pipeline ISCO predictions by tracing the chain:

    O*NET task ──[O*NET assigns]──► SOC code ──[institutional crosswalk]──► ISCO

If the pipeline's predicted ISCO falls within the acceptable ISCO set for
that SOC code (as defined by the crosswalk), it counts as a "hit".

SOC taxonomy generations:
    SOC 2010: O*NET ≤25.0   → crosswalks ESCO-ONET-MHV + SOC10-ISCO-BLS
    SOC 2018: O*NET ≥25.1   → crosswalks ESCO-SOC18 + SOC18-ESCO

Selected releases evaluated (3 per SOC era):
    SOC 2018: 25.1 (first SOC 2018 release), 29.2 (parameter selection), 30.3 (latest)
    SOC 2010: 15.1 (first SOC 2010 release), 20.0 (mid-era), 25.0 (last SOC 2010)

For each SOC 2018 release we run four crosswalk scenarios:
    A1  ESCO-SOC18 alone
    A2  SOC18-ESCO alone
    A3  Strict intersection: ESCO-SOC18 ∩ SOC18-ESCO
    A4  Lenient union:       ESCO-SOC18 ∪ SOC18-ESCO

For each SOC 2010 release we run four scenarios:
    B1  ESCO-ONET-MHV alone  (semantic; NOTE: less independent — see below)
    B2  SOC10-ISCO-BLS alone  (BLS official)
    B3  Lenient union: ESCO-ONET-MHV ∪ SOC10-ISCO-BLS
    B4  Strict intersection: ESCO-ONET-MHV ∩ SOC10-ISCO-BLS

NOTE on ESCO-ONET-MHV: derived using semantic similarity (same approach as the
pipeline), so agreement is expected to be higher but is less informative as an
independent ground-truth signal.

Results are written per version to validation/results/chain_eval_onet{tag}_{suffix}.csv.

Run from the project root:
    python validation/validate_chain.py
"""

from __future__ import annotations

import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent))
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.stdout.reconfigure(encoding="utf-8")

import pandas as pd

from shared import (
    GT_RESULTS_DIR,
    evaluate_match,
    load_onet_tasks,
    load_pipeline,
    load_soc10_crosswalks,
    load_soc18_crosswalks,
    pipeline_path_for_version,
    summarise_by_major_group,
    summarise_by_sim_bin,
    summarise_match,
)

# ── Selected releases ──────────────────────────────────────────────────────────
SOC18_VERSIONS = ["25.1", "29.2", "30.3"]   # first, sweep, latest
SOC10_VERSIONS = ["15.1", "20.0", "25.0"]   # first, mid, last

SOC18_VERSION_LABELS = {
    "25.1": "SOC 2018 — O*NET 25.1 (first SOC 2018 release)",
    "29.2": "SOC 2018 — O*NET 29.2 (release used for parameter selection)",
    "30.3": "SOC 2018 — O*NET 30.3 (latest release)",
}
SOC10_VERSION_LABELS = {
    "15.1": "SOC 2010 — O*NET 15.1 (first SOC 2010 release)",
    "20.0": "SOC 2010 — O*NET 20.0 (mid-era)",
    "25.0": "SOC 2010 — O*NET 25.0 (last SOC 2010 release)",
}


def ver_tag(ver: str) -> str:
    return ver.replace(".", "")


# ── Helper: strict crosswalk (intersection) ───────────────────────────────────

def make_strict_xw(xw1: pd.DataFrame, xw2: pd.DataFrame, soc_col: str) -> pd.DataFrame:
    common_socs = set(xw1[soc_col]) & set(xw2[soc_col])
    a = xw1.loc[xw1[soc_col].isin(common_socs), [soc_col, "isco_code"]]
    b = xw2.loc[xw2[soc_col].isin(common_socs), [soc_col, "isco_code"]]
    return pd.merge(a, b, on=[soc_col, "isco_code"]).drop_duplicates().reset_index(drop=True)


# ── Helper: lenient crosswalk (union) ─────────────────────────────────────────

def make_lenient_xw(xw1: pd.DataFrame, xw2: pd.DataFrame, soc_col: str) -> pd.DataFrame:
    return (
        pd.concat([xw1[[soc_col, "isco_code"]], xw2[[soc_col, "isco_code"]]])
        .drop_duplicates()
        .reset_index(drop=True)
    )


# ── Helper: run all three summaries for one (pipeline × crosswalk) scenario ───

def run_scenario(
    pipeline_df: pd.DataFrame,
    task_soc_df: pd.DataFrame,
    crosswalk_df: pd.DataFrame,
    soc_col: str,
    label: str,
) -> dict[str, pd.DataFrame]:
    ev = evaluate_match(pipeline_df, task_soc_df, crosswalk_df, soc_col)
    return {
        "overall":        summarise_match(ev, label),
        "by_sim_bin":     summarise_by_sim_bin(ev, label),
        "by_major_group": summarise_by_major_group(ev, label),
    }


def collect_results(scenario_list: list[dict]) -> dict[str, pd.DataFrame]:
    return {
        "overall":        pd.concat([s["overall"]        for s in scenario_list], ignore_index=True),
        "by_sim_bin":     pd.concat([s["by_sim_bin"]     for s in scenario_list], ignore_index=True),
        "by_major_group": pd.concat([s["by_major_group"] for s in scenario_list], ignore_index=True),
    }


# ── Load reference crosswalks once ────────────────────────────────────────────

print("Loading reference crosswalks …")
xw18 = load_soc18_crosswalks()
xw10 = load_soc10_crosswalks()

xw18_1 = xw18["xw18_1"]
xw18_2 = xw18["xw18_2"]
xw10_1 = xw10["xw10_1"]
xw10_2 = xw10["xw10_2"]

print(f"  XW18.1 (ESCO-SOC18):          {len(xw18_1):,} rows")
print(f"  XW18.2 (SOC18-ESCO, all):     {len(xw18_2):,} rows")
print(f"  XW10.1 (ESCO-ONET-MHV):       {len(xw10_1):,} rows  [less independent]")
print(f"  XW10.2 (SOC10-ISCO-BLS):      {len(xw10_2):,} rows")


# ══════════════════════════════════════════════════════════════════════════════
# PART A – SOC 2018 releases  (O*NET 25.1, 29.2, 30.3)
# ══════════════════════════════════════════════════════════════════════════════

for ver in SOC18_VERSIONS:
    tag = ver_tag(ver)
    print(f"\n══ SOC 2018: O*NET {ver} ({'first' if ver == '25.1' else 'sweep' if ver == '29.2' else 'latest'}) ══")

    pipeline_df = load_pipeline(pipeline_path_for_version(ver))
    task_soc    = load_onet_tasks(ver)

    print(f"  Pipeline tasks (S5_FINAL):  {len(pipeline_df):,}")
    print(f"  O*NET task→SOC rows:        {len(task_soc):,}")

    scenarios = [
        run_scenario(pipeline_df, task_soc,
                     xw18_1[["soc_code18", "isco_code"]],
                     "soc_code18", "A1 – ESCO-SOC18 alone"),

        run_scenario(pipeline_df, task_soc,
                     xw18_2[["soc_code18", "isco_code"]],
                     "soc_code18", "A2 – SOC18-ESCO alone"),

        run_scenario(pipeline_df, task_soc,
                     make_strict_xw(xw18_1[["soc_code18", "isco_code"]],
                                    xw18_2[["soc_code18", "isco_code"]], "soc_code18"),
                     "soc_code18", "A3 – Strict intersection"),

        run_scenario(pipeline_df, task_soc,
                     make_lenient_xw(xw18_1[["soc_code18", "isco_code"]],
                                     xw18_2[["soc_code18", "isco_code"]], "soc_code18"),
                     "soc_code18", "A4 – Lenient union"),
    ]

    results = collect_results(scenarios)
    print("\n  Overall:")
    print(results["overall"].to_string(index=False))

    for suffix, df in results.items():
        path = GT_RESULTS_DIR / f"chain_eval_onet{tag}_{suffix}.csv"
        df.to_csv(path, index=False)
    print(f"  → chain_eval_onet{tag}_*.csv")


# ══════════════════════════════════════════════════════════════════════════════
# PART B – SOC 2010 releases  (O*NET 15.1, 20.0, 25.0)
# ══════════════════════════════════════════════════════════════════════════════

for ver in SOC10_VERSIONS:
    tag = ver_tag(ver)
    print(f"\n══ SOC 2010: O*NET {ver} ({'first' if ver == '15.1' else 'mid' if ver == '20.0' else 'last'}) ══")

    pipeline_df = load_pipeline(pipeline_path_for_version(ver))
    task_soc    = load_onet_tasks(ver)

    print(f"  Pipeline tasks (S5_FINAL):  {len(pipeline_df):,}")
    print(f"  O*NET task→SOC rows:        {len(task_soc):,}")

    scenarios = [
        run_scenario(pipeline_df, task_soc,
                     xw10_1, "soc_code10",
                     "B1 – ESCO-ONET-MHV alone (semantic, less independent)"),

        run_scenario(pipeline_df, task_soc,
                     xw10_2, "soc_code10",
                     "B2 – SOC10-ISCO-BLS alone"),

        run_scenario(pipeline_df, task_soc,
                     make_lenient_xw(xw10_1, xw10_2, "soc_code10"),
                     "soc_code10", "B3 – Lenient union (MHV ∪ BLS)"),

        run_scenario(pipeline_df, task_soc,
                     make_strict_xw(xw10_1, xw10_2, "soc_code10"),
                     "soc_code10", "B4 – Strict intersection (MHV ∩ BLS)"),
    ]

    results = collect_results(scenarios)
    print("\n  Overall:")
    print(results["overall"].to_string(index=False))

    for suffix, df in results.items():
        path = GT_RESULTS_DIR / f"chain_eval_onet{tag}_{suffix}.csv"
        df.to_csv(path, index=False)
    print(f"  → chain_eval_onet{tag}_*.csv")


print(f"\nAll results written to: {GT_RESULTS_DIR}")
