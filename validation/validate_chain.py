"""
validate_chain.py
=================
Chain Crosswalk Validation

Validates pipeline ISCO predictions by tracing the chain:

    O*NET task ──[O*NET assigns]──► SOC code ──[institutional crosswalk]──► ISCO

If the pipeline's predicted ISCO falls within the acceptable ISCO set for
that SOC code (as defined by the crosswalk), it counts as a "hit".

Two pipeline variants are evaluated separately — task IDs do NOT overlap
across O*NET releases because the underlying SOC version differs:

    ONET29 (O*NET 29.2 / SOC18) → crosswalks ESCO-SOC18 + SOC18-ESCO
    ONET25 (O*NET 25.0 / SOC10) → crosswalks ESCO-ONET-MHV + SOC10-ISCO-BLS

For the ONET29 / SOC18 pipeline we run four crosswalk scenarios:

    A1  ESCO-SOC18 alone
    A2  SOC18-ESCO alone
    A3  Strict intersection: ESCO-SOC18 ∩ SOC18-ESCO
    A4  Lenient union: ESCO-SOC18 ∪ SOC18-ESCO

For the ONET25 / SOC10 pipeline we run four scenarios:

    B1  ESCO-ONET-MHV alone  (semantic; NOTE: less independent — see below)
    B2  SOC10-ISCO-BLS alone  (BLS official)
    B3  Lenient union: ESCO-ONET-MHV ∪ SOC10-ISCO-BLS
    B4  Strict intersection: ESCO-ONET-MHV ∩ SOC10-ISCO-BLS

NOTE on ESCO-ONET-MHV: this crosswalk was derived using semantic similarity
(sentence-transformers), the same approach as the pipeline itself. Therefore
agreement between the pipeline and ESCO-ONET-MHV is expected to be higher but is
also less informative as an independent ground-truth signal.

NOTE on IBS Poland: the IBS SOC10-ISCO08 crosswalk is derived from the BLS
official table and produces near-identical results; it has been dropped to
avoid redundant scenarios.

Three match tiers are evaluated for every scenario:
    match_exact       — isco_pred exactly in acceptable ISCO set
    match_sub_major   — first 2 digits in acceptable sub-majors
    match_major_group — first digit in acceptable major groups

Each scenario is broken down three ways:
    Overall summary | By similarity bin | By predicted ISCO major group

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
    PIPELINE_ONET29,
    PIPELINE_ONET29_WT20,
    PIPELINE_ONET25,
    evaluate_match,
    load_onet_tasks,
    load_pipeline,
    load_soc10_crosswalks,
    load_soc18_crosswalks,
    summarise_by_major_group,
    summarise_by_sim_bin,
    summarise_match,
)


# ── Helper: strict crosswalk (intersection) ───────────────────────────────────
# Only keeps SOC codes present in BOTH crosswalks.
# Acceptable ISCOs for a SOC = codes found in BOTH crosswalks.
# Most conservative / highest-confidence scenario.

def make_strict_xw(xw1: pd.DataFrame, xw2: pd.DataFrame, soc_col: str) -> pd.DataFrame:
    common_socs = set(xw1[soc_col]) & set(xw2[soc_col])
    a = xw1.loc[xw1[soc_col].isin(common_socs), [soc_col, "isco_code"]]
    b = xw2.loc[xw2[soc_col].isin(common_socs), [soc_col, "isco_code"]]
    # Inner merge on both columns → only codes that appear in BOTH crosswalks
    return pd.merge(a, b, on=[soc_col, "isco_code"]).drop_duplicates().reset_index(drop=True)


# ── Helper: lenient crosswalk (union) ─────────────────────────────────────────
# Acceptable ISCOs for a SOC = codes found in EITHER crosswalk.
# Most permissive / highest-coverage scenario.

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


# ══════════════════════════════════════════════════════════════════════════════
# PART A – ONET pipeline  (O*NET 29.2 / SOC18)
# ══════════════════════════════════════════════════════════════════════════════

print("\n══ PART A: ONET 29.2 / SOC18 pipeline ════════════════════════════════════")

pipeline_onet = load_pipeline(PIPELINE_ONET29)
task_soc_onet = load_onet_tasks("29")
xw18          = load_soc18_crosswalks()

xw18_1   = xw18["xw18_1"]
xw18_2   = xw18["xw18_2"]
xw18_2hq = xw18_2[xw18_2["type_of_match"] != "broadMatch"]  # high-quality only

print(f"  Pipeline tasks (S5_FINAL):  {len(pipeline_onet):,}")
print(f"  O*NET task→SOC rows (29.2): {len(task_soc_onet):,}")
print(f"  XW-ESCO-SOC18 rows:               {len(xw18_1):,}")
print(f"  XW-SOC18-ESCO rows (all):         {len(xw18_2):,}")
print(f"  XW-SOC18-ESCO rows (HQ only):     {len(xw18_2hq):,}")

print("\n  XW-SOC18-ESCO match type distribution:")
print(xw18_2["type_of_match"].value_counts().to_string())

scenarios_onet = [
    # A1: ESCO-SOC18 alone
    run_scenario(pipeline_onet, task_soc_onet,
                 xw18_1[["soc_code18", "isco_code"]],
                 "soc_code18", "A1 – ESCO-SOC18 alone"),

    # A2: SOC18-ESCO alone (all match types incl. broadMatch)
    run_scenario(pipeline_onet, task_soc_onet,
                 xw18_2[["soc_code18", "isco_code"]],
                 "soc_code18", "A2 – SOC18-ESCO alone"),

    # A3: Strict intersection ESCO-SOC18 ∩ SOC18-ESCO
    run_scenario(pipeline_onet, task_soc_onet,
                 make_strict_xw(xw18_1[["soc_code18", "isco_code"]],
                                xw18_2[["soc_code18", "isco_code"]], "soc_code18"),
                 "soc_code18", "A3 – Strict intersection"),

    # A4: Lenient union ESCO-SOC18 ∪ SOC18-ESCO
    run_scenario(pipeline_onet, task_soc_onet,
                 make_lenient_xw(xw18_1[["soc_code18", "isco_code"]],
                                 xw18_2[["soc_code18", "isco_code"]], "soc_code18"),
                 "soc_code18", "A4 – Lenient union"),
]

results_onet = collect_results(scenarios_onet)

print("\n─── Overall match rates (ONET29 / SOC18) ────────────────────────────────")
print(results_onet["overall"].to_string(index=False))
print("\n─── By similarity bin ────────────────────────────────────────────────────")
print(results_onet["by_sim_bin"].to_string(index=False))
print("\n─── By predicted ISCO major group ────────────────────────────────────────")
print(results_onet["by_major_group"].to_string(index=False))


# ══════════════════════════════════════════════════════════════════════════════
# PART B – ONET25 pipeline  (O*NET 25.0 / SOC10)
# ══════════════════════════════════════════════════════════════════════════════

print("\n══ PART B: ONET25 / SOC10 pipeline ═══════════════════════════════════════")

pipeline_oneto = load_pipeline(PIPELINE_ONET25)
task_soc_oneto = load_onet_tasks("25")
xw10           = load_soc10_crosswalks()

xw10_1 = xw10["xw10_1"]  # ESCO↔O*NET semantic  (less independent — treat with caution)
xw10_2 = xw10["xw10_2"]  # BLS official

print(f"  Pipeline tasks (S5_FINAL):        {len(pipeline_oneto):,}")
print(f"  O*NET task→SOC rows (25.0):       {len(task_soc_oneto):,}")
print(f"  ESCO-ONET-MHV rows (semantic):    {len(xw10_1):,}  [less independent]")
print(f"  SOC10-ISCO-BLS rows (BLS):        {len(xw10_2):,}")

scenarios_oneto = [
    # B1: ESCO-ONET-MHV alone (semantic; less independent as ground truth)
    run_scenario(pipeline_oneto, task_soc_oneto,
                 xw10_1, "soc_code10",
                 "B1 – ESCO-ONET-MHV alone (semantic, less independent)"),

    # B2: SOC10-ISCO-BLS alone (BLS official)
    run_scenario(pipeline_oneto, task_soc_oneto,
                 xw10_2, "soc_code10",
                 "B2 – SOC10-ISCO-BLS alone"),

    # B3: Lenient union ESCO-ONET-MHV ∪ SOC10-ISCO-BLS
    run_scenario(pipeline_oneto, task_soc_oneto,
                 make_lenient_xw(xw10_1, xw10_2, "soc_code10"),
                 "soc_code10", "B3 – Lenient union (MHV ∪ BLS)"),

    # B4: Strict intersection ESCO-ONET-MHV ∩ SOC10-ISCO-BLS
    run_scenario(pipeline_oneto, task_soc_oneto,
                 make_strict_xw(xw10_1, xw10_2, "soc_code10"),
                 "soc_code10", "B4 – Strict intersection (MHV ∩ BLS)"),
]

results_oneto = collect_results(scenarios_oneto)

print("\n─── Overall match rates (ONET25 / SOC10) ────────────────────────────────")
print(results_oneto["overall"].to_string(index=False))
print("\n─── By similarity bin ────────────────────────────────────────────────────")
print(results_oneto["by_sim_bin"].to_string(index=False))
print("\n─── By predicted ISCO major group ────────────────────────────────────────")
print(results_oneto["by_major_group"].to_string(index=False))


# ══════════════════════════════════════════════════════════════════════════════
# PART C – ONET29 w_soc_title=0.20 sensitivity  (SOC18, same crosswalks as A)
# ══════════════════════════════════════════════════════════════════════════════
# Compares against Part A to test whether anchoring task queries to the SOC
# occupation title improves chain-crosswalk agreement, especially for
# managerial occupations (major group 1) whose tasks are semantically broad.

if PIPELINE_ONET29_WT20.exists():
    print("\n══ PART C: ONET29 w_soc_title=0.20 sensitivity ═══════════════════════════")

    pipeline_wt20 = load_pipeline(PIPELINE_ONET29_WT20)

    print(f"  Pipeline tasks (S5_FINAL):  {len(pipeline_wt20):,}")

    scenarios_wt20 = [
        run_scenario(pipeline_wt20, task_soc_onet,
                     xw18_1[["soc_code18", "isco_code"]],
                     "soc_code18", "C1 – wt20 ESCO-SOC18 alone"),

        run_scenario(pipeline_wt20, task_soc_onet,
                     xw18_2[["soc_code18", "isco_code"]],
                     "soc_code18", "C2 – wt20 SOC18-ESCO alone"),

        run_scenario(pipeline_wt20, task_soc_onet,
                     make_strict_xw(xw18_1[["soc_code18", "isco_code"]],
                                    xw18_2[["soc_code18", "isco_code"]], "soc_code18"),
                     "soc_code18", "C3 – wt20 Strict intersection"),

        run_scenario(pipeline_wt20, task_soc_onet,
                     make_lenient_xw(xw18_1[["soc_code18", "isco_code"]],
                                     xw18_2[["soc_code18", "isco_code"]], "soc_code18"),
                     "soc_code18", "C4 – wt20 Lenient union"),
    ]

    results_wt20 = collect_results(scenarios_wt20)

    print("\n─── Overall match rates (ONET29 wt20 vs baseline) ───────────────────────")
    # Side-by-side: baseline A4 vs sensitivity C4 (lenient union — most informative)
    comparison = pd.concat([
        results_onet["overall"][results_onet["overall"]["label"].str.startswith("A4")],
        results_wt20["overall"][results_wt20["overall"]["label"].str.startswith("C4")],
    ], ignore_index=True)
    print(comparison.to_string(index=False))

    print("\n─── By predicted ISCO major group — Lenient union (A4 vs C4) ────────────")
    mg_compare = pd.concat([
        results_onet["by_major_group"][results_onet["by_major_group"]["label"].str.startswith("A4")],
        results_wt20["by_major_group"][results_wt20["by_major_group"]["label"].str.startswith("C4")],
    ], ignore_index=True)
    print(mg_compare.to_string(index=False))

    print("\n─── Full wt20 overall results ────────────────────────────────────────────")
    print(results_wt20["overall"].to_string(index=False))

else:
    print("\n[Part C skipped — run ONET29wt20-ESCO-NLP.py first to generate the wt20 pipeline output]")
    results_wt20 = None


# ── Write results to CSV ──────────────────────────────────────────────────────

runs = [("onet29", results_onet), ("onet25", results_oneto)]
if results_wt20 is not None:
    runs.append(("onet29_wt20", results_wt20))

for stem, results in runs:
    for suffix, df in results.items():
        path = GT_RESULTS_DIR / f"chain_eval_{stem}_{suffix}.csv"
        df.to_csv(path, index=False)

print(f"\nAll results written to: {GT_RESULTS_DIR}")
print("Files: chain_eval_onet29_*.csv, chain_eval_onet25_*.csv" +
      (" chain_eval_onet29_wt20_*.csv" if results_wt20 is not None else " [wt20 skipped]"))
