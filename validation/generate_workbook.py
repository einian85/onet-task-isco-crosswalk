"""
generate_workbook.py
====================
Step 1: Generate Human Annotation Excel

Generates a human annotation workbook without model predictions.
Output: validation/results/annotation_workbook_onet29.xlsx

LAYOUT: task_id, onet_soc_code, soc_code, soc_title, task_text, importance,
crosswalk_acceptable_iscos, expert_isco, expert_notes.

TASK SELECTION: SOC codes sampled from institutional crosswalks, stratified by
ISCO major group 1-9 and weighted by employment (US + Nordic countries). Tasks
selected by O*NET importance score.

Run from the project root:
    python validation/generate_workbook.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import (
    GT_RESULTS_DIR,
    load_employment_totals,
    load_onet_tasks,
    load_soc18_crosswalks,
    load_task_ratings,
)

N_SOC_PER_MAJOR = 4
N_TASKS_PER_SOC = 3


def generate_validation_sheet(
    crosswalk_dfs: list[pd.DataFrame],
    soc_col: str,
    output_filename: str,
) -> pd.DataFrame:
    """Build the unbiased ONET29 validation DataFrame and write it to Excel."""
    onet_version = "29"

    combined_xw = (
        pd.concat([df[[soc_col, "isco_code"]] for df in crosswalk_dfs])
        .drop_duplicates()
        .reset_index(drop=True)
    )
    combined_xw["isco_major"] = (combined_xw["isco_code"].astype(int) // 1000).astype(int)

    emp = load_employment_totals()
    combined_xw_emp = combined_xw.merge(emp, on="isco_code", how="left")

    all_tasks = load_onet_tasks(onet_version)
    onet_soc_map = all_tasks[["onet_soc_code", "soc_code", "soc_title"]].drop_duplicates("onet_soc_code")
    xw_for_emp = combined_xw_emp.rename(columns={soc_col: "soc_code"})
    onet_soc_xw_emp = onet_soc_map.merge(xw_for_emp, on="soc_code", how="left")

    sampled_onet_socs: list[str] = []
    already_seen: set[str] = set()

    print(f"\n  {'Major':>5}  {'O*NET-SOC':<14}  {'SOC title':<44}  {'Emp (major)':>12}")
    print(f"  {'-----':>5}  {'-' * 14}  {'-' * 44}  {'-' * 12}")

    for major in sorted(onet_soc_xw_emp["isco_major"].dropna().unique().astype(int)):
        xw_major = onet_soc_xw_emp[onet_soc_xw_emp["isco_major"] == major]
        onet_emp_major = (
            xw_major.groupby("onet_soc_code")["total_emp"]
            .sum()
            .fillna(0)
            .reset_index()
            .rename(columns={"total_emp": "onet_emp"})
            .sort_values("onet_emp", ascending=False)
        )

        chosen = []
        for _, row in onet_emp_major.iterrows():
            if len(chosen) >= N_SOC_PER_MAJOR:
                break
            if row["onet_soc_code"] not in already_seen:
                chosen.append(row)

        if len(chosen) < N_SOC_PER_MAJOR:
            for _, row in onet_emp_major.iterrows():
                if len(chosen) >= N_SOC_PER_MAJOR:
                    break
                if row["onet_soc_code"] not in [r["onet_soc_code"] for r in chosen]:
                    chosen.append(row)

        for row in chosen:
            onet_soc = row["onet_soc_code"]
            emp_val = row["onet_emp"]
            title = onet_soc_map.loc[onet_soc_map["onet_soc_code"] == onet_soc, "soc_title"]
            title_str = title.iloc[0][:42] if len(title) > 0 else "(no title)"
            marker = "*" if onet_soc in already_seen else " "
            print(f"  {major:>5}  {marker}{onet_soc:<14}  {title_str:<44}  {emp_val:>12,.0f}")
            sampled_onet_socs.append(onet_soc)
            already_seen.add(onet_soc)

    sampled_onet_socs = list(dict.fromkeys(sampled_onet_socs))
    print(f"\n  -> {len(sampled_onet_socs)} unique O*NET-SOC occupations selected")

    ratings = load_task_ratings(onet_version)
    tasks_top = (
        all_tasks[all_tasks["onet_soc_code"].isin(sampled_onet_socs)]
        .merge(ratings, on="task_id", how="left")
        .sort_values(["onet_soc_code", "importance"], ascending=[True, False])
        .groupby("onet_soc_code", group_keys=False)
        .head(N_TASKS_PER_SOC)
        .reset_index(drop=True)
    )

    onet_soc_order = {soc: i for i, soc in enumerate(sampled_onet_socs)}
    tasks_top["_order"] = tasks_top["onet_soc_code"].map(onet_soc_order)
    tasks_top = tasks_top.sort_values(["_order", "importance"], ascending=[True, False]).drop(columns="_order")
    print(f"  Tasks selected for validation: {len(tasks_top)}")
    print("  Workbook excludes pipeline predictions to avoid biasing annotation.")

    acceptable_per_soc = (
        combined_xw.groupby(soc_col)["isco_code"]
        .apply(lambda x: ", ".join(str(c) for c in sorted(x.dropna().unique().astype(int))))
        .reset_index()
        .rename(columns={soc_col: "soc_code", "isco_code": "crosswalk_acceptable_iscos"})
    )

    validation = tasks_top.merge(acceptable_per_soc, on="soc_code", how="left")
    validation["expert_isco"] = ""
    validation["expert_notes"] = ""

    col_order = [
        "task_id",
        "onet_soc_code",
        "soc_code",
        "soc_title",
        "task_text",
        "importance",
        "crosswalk_acceptable_iscos",
        "expert_isco",
        "expert_notes",
    ]
    validation = validation[[c for c in col_order if c in validation.columns]]

    out_path = GT_RESULTS_DIR / output_filename
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        validation.to_excel(writer, sheet_name="Validation", index=False)

        instructions = pd.DataFrame(
            {
                "Instructions": [
                    "ANNOTATION TASK",
                    "---------------",
                    "For each task row, consider: given that this task is performed by the",
                    "SOC occupation shown in 'soc_title', what is the most appropriate",
                    "4-digit ISCO code for the occupation performing it?",
                    "",
                    "This is NOT asking which ISCO best describes the task text in isolation.",
                    "It is asking which ISCO best represents the source occupation in the",
                    "context of performing this specific task.",
                    "",
                    "COLUMN LAYOUT",
                    "-------------",
                    "  Column A: task_id",
                    "  Column B: onet_soc_code -- specific O*NET occupation (e.g. 11-9199.01)",
                    "  Column C: soc_code      -- 6-digit BLS SOC grouping",
                    "  Column D: soc_title     -- O*NET occupation title",
                    "  Column E: task_text",
                    "  Column F: importance    -- O*NET importance rating (1-5)",
                    "  Column G: crosswalk_acceptable_iscos -- reference ISCOs from institutional crosswalks",
                    "  Column H: expert_isco  <- FILL IN YOUR ANSWER HERE",
                    "  Column I: expert_notes <- optional comments",
                    "",
                    "YOUR ANNOTATION COLUMNS",
                    "-----------------------",
                    "  expert_isco  -- 4-digit ISCO code most appropriate for the OCCUPATION",
                    "                  performing this task (not the task text alone).",
                    "  expert_notes -- optional: note ambiguities, edge cases, or concerns.",
                    "",
                    "REFERENCE COLUMN",
                    "----------------",
                    "  crosswalk_acceptable_iscos -- ISCO codes structurally linked to this SOC",
                    "  via institutional crosswalks (ESCO-SOC18 + SOC18-ESCO union).",
                    "  Your answer should usually be one of these, but need not be.",
                    "",
                    "BIAS REDUCTION",
                    "--------------",
                    "  This workbook intentionally excludes model predictions.",
                    "  Annotate from the occupation context and task text only.",
                    "",
                    "TIP",
                    "---",
                    "  Freeze panes at column H or I to keep task context visible while annotating.",
                    "",
                    "ISCO major groups (first digit):",
                    "  1=Managers  2=Professionals  3=Technicians  4=Clerical  5=Service",
                    "  6=Agricultural  7=Craft  8=Operators  9=Elementary",
                ]
            }
        )
        instructions.to_excel(writer, sheet_name="Instructions", index=False)

    print(f"  Written: {out_path}")
    return validation


if __name__ == "__main__":
    print("\n== Generating: ONET29 / SOC18 unbiased annotation workbook ================")

    xw18 = load_soc18_crosswalks()
    generate_validation_sheet(
        crosswalk_dfs=[xw18["xw18_1"], xw18["xw18_2"][["soc_code18", "isco_code"]]],
        soc_col="soc_code18",
        output_filename="annotation_workbook_onet29.xlsx",
    )

    print("\nDone. Fill in expert_isco (and optionally expert_notes),")
    print("then run validation/evaluate_annotations.py.")
