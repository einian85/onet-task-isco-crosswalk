"""
generate_workbook_expand_phase_d.py
=====================================
Phase D1-D3: expand the annotation workbook from n=108 (3 tasks/SOC x 36 SOC occupations)
to n=180 (5 tasks/SOC, same 36 occupations, same stratification), merge in the existing
108 filled answers so only the 72 new tasks need fresh judgment, and add a ~20-task blind
test-retest sample for intra-rater reliability.

IMPORTANT: this pins the exact 36 onet_soc_code values from the existing filled workbook,
rather than re-running generate_workbook.py's employment-weighted SOC-selection logic from
scratch. Checked empirically (2026-09-22): re-running that selection today picks 3 different
occupations than the original April pass (Carpenters, Fast Food/Counter Workers, and
Manufactured Building/Mobile Home Installers dropped out, replaced by others) - the
selection isn't stable across reruns, for reasons not investigated further (crosswalk-data
drift or non-deterministic tie-breaking in the already_seen/cross-major exclusion logic are
both plausible). Since Phase D explicitly requires "same 36 occupations, same stratification,
same 9-major-group coverage," reusing the selection logic here would silently violate that.
Pinning the existing 36 occupations sidesteps the instability entirely and is unambiguously
what was asked for.

Does NOT re-annotate the original 108 (D2), and does NOT reveal which of the "to annotate"
rows are genuinely new vs. blind repeats (D3) - the retest duplicates are shuffled in among
the 72 new tasks with blank answers and no reference to the original verdict. The mapping
needed to score test-retest agreement afterward is written to a SEPARATE file
(reviewer_d3_retest_key.csv) that is not part of the workbook the annotator sees - its whole
point is to sit unopened until annotation is done.

Output:
  validation/results/annotation_workbook_onet29.xlsx        — expanded workbook (this is
                                                                the file to fill in)
  validation/results/annotation_workbook_onet29_original_108_backup.xlsx  — safety copy of
                                                                the pre-expansion file
  validation/results/reviewer_d3_retest_key.csv              — DO NOT OPEN before annotating;
                                                                needed only for D4 scoring

Run from the project root:
    python validation/generate_workbook_expand_phase_d.py
"""

from __future__ import annotations

import shutil
import sys
from pathlib import Path

import pandas as pd

sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from shared import GT_RESULTS_DIR, load_onet_tasks, load_soc18_crosswalks, load_task_ratings  # noqa: E402
from generate_workbook import N_SOC_PER_MAJOR, N_TASKS_PER_SOC  # noqa: E402

RANDOM_SEED = 42
N_RETEST = 20

EXISTING_WORKBOOK = GT_RESULTS_DIR / "annotation_workbook_onet29.xlsx"
BACKUP_WORKBOOK = GT_RESULTS_DIR / "annotation_workbook_onet29_original_108_backup.xlsx"
RETEST_KEY_PATH = GT_RESULTS_DIR / "reviewer_d3_retest_key.csv"

COL_ORDER = [
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


def build_fresh_pool(sampled_onet_socs: list[str], soc_col: str, combined_xw: pd.DataFrame) -> pd.DataFrame:
    """Same task-selection logic as generate_workbook.py's generate_validation_sheet, but
    for a caller-supplied (pinned) list of onet_soc_code values instead of re-deriving it."""
    all_tasks = load_onet_tasks("29")
    ratings = load_task_ratings("29")
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

    acceptable_per_soc = (
        combined_xw.groupby(soc_col)["isco_code"]
        .apply(lambda x: ", ".join(str(c) for c in sorted(x.dropna().unique().astype(int))))
        .reset_index()
        .rename(columns={soc_col: "soc_code", "isco_code": "crosswalk_acceptable_iscos"})
    )
    validation = tasks_top.merge(acceptable_per_soc, on="soc_code", how="left")
    validation["expert_isco"] = ""
    validation["expert_notes"] = ""
    return validation[COL_ORDER]


def main() -> None:
    assert N_TASKS_PER_SOC == 5, (
        f"generate_workbook.py's N_TASKS_PER_SOC is {N_TASKS_PER_SOC}, expected 5 for the "
        "Phase D expansion - edit it there, not here."
    )
    assert N_SOC_PER_MAJOR == 4, "N_SOC_PER_MAJOR changed - Phase D expects the same 36 occupations."

    if not EXISTING_WORKBOOK.exists():
        raise FileNotFoundError(f"{EXISTING_WORKBOOK} not found - nothing to expand.")

    print("== Reading existing n=108 filled workbook ==")
    old = pd.read_excel(EXISTING_WORKBOOK, sheet_name="Validation")
    old["expert_isco"] = old["expert_isco"].astype(str).str.strip()
    old_answered = old[old["expert_isco"] != ""].copy()
    print(f"  {len(old)} rows, {len(old_answered)} with expert_isco filled in.")
    if len(old_answered) != len(old):
        raise RuntimeError(
            "Not every row in the existing workbook has expert_isco filled in - finish "
            "annotating the current n=108 pass before expanding it."
        )

    pinned_socs = list(dict.fromkeys(old["onet_soc_code"].tolist()))
    print(f"  {len(pinned_socs)} unique onet_soc_code values pinned from the original pass.")

    if not BACKUP_WORKBOOK.exists():
        shutil.copy(EXISTING_WORKBOOK, BACKUP_WORKBOOK)
        print(f"  Backed up pre-expansion workbook to: {BACKUP_WORKBOOK}")
    else:
        print(f"  Backup already exists, not overwriting: {BACKUP_WORKBOOK}")

    print("\n== Building expanded task pool (same 36 occupations, top 5 tasks each) ==")
    xw18 = load_soc18_crosswalks()
    combined_xw = (
        pd.concat([
            xw18["xw18_1"][["soc_code18", "isco_code"]],
            xw18["xw18_2"][["soc_code18", "isco_code"]],
        ])
        .drop_duplicates()
        .reset_index(drop=True)
    )
    fresh = build_fresh_pool(pinned_socs, "soc_code18", combined_xw)
    print(f"  {len(fresh)} total tasks in the expanded pool.")

    old_ids = set(old["task_id"])
    fresh_ids = set(fresh["task_id"])
    missing_old = old_ids - fresh_ids
    if missing_old:
        raise RuntimeError(
            f"{len(missing_old)} task_ids from the original 108 are not in the fresh pull "
            f"even with SOC occupations pinned (task_ids: {sorted(missing_old)[:10]}...). "
            "Likely an importance-rating change for one of these specific tasks - investigate "
            "before proceeding; do not silently drop or re-derive answers for these."
        )

    new_ids = fresh_ids - old_ids
    print(f"  {len(old_ids)} carried over from the original pass, {len(new_ids)} genuinely new.")
    if len(new_ids) != 72:
        print(f"  NOTE: expected 72 new tasks (36 SOC x 2 additional ranks), got {len(new_ids)}. "
              "Some SOC occupations may have fewer than 5 rated tasks available. Continuing anyway.")

    # Section 1: the original 108, answers carried over, in their original order.
    section1 = old[COL_ORDER].copy()

    # Section 2: the "to annotate" pool = genuinely-new tasks + blind retest duplicates,
    # shuffled together, all with blank expert_isco/expert_notes.
    new_tasks = fresh[fresh["task_id"].isin(new_ids)][COL_ORDER].copy()
    new_tasks["expert_isco"] = ""
    new_tasks["expert_notes"] = ""

    retest_source = old_answered.sample(n=min(N_RETEST, len(old_answered)), random_state=RANDOM_SEED)
    retest_rows = retest_source[COL_ORDER].copy()
    retest_key = retest_rows[["task_id", "expert_isco", "expert_notes"]].rename(
        columns={"expert_isco": "original_expert_isco", "expert_notes": "original_expert_notes"}
    )
    retest_rows["expert_isco"] = ""
    retest_rows["expert_notes"] = ""

    section2 = pd.concat([new_tasks, retest_rows], ignore_index=True)
    section2 = section2.sample(frac=1.0, random_state=RANDOM_SEED).reset_index(drop=True)

    combined = pd.concat([section1, section2], ignore_index=True)
    print(f"\n  Final workbook: {len(section1)} already-answered + {len(section2)} to annotate "
          f"({len(new_tasks)} new + {len(retest_rows)} blind repeats) = {len(combined)} rows.")

    retest_key.to_csv(RETEST_KEY_PATH, index=False)
    print(f"\n  Wrote retest key (DO NOT OPEN before annotating): {RETEST_KEY_PATH}")

    with pd.ExcelWriter(EXISTING_WORKBOOK, engine="xlsxwriter") as writer:
        combined.to_excel(writer, sheet_name="Validation", index=False)

        instructions = pd.DataFrame(
            {
                "Instructions": [
                    "ANNOTATION TASK (Phase D expansion: n=108 -> n=180 + test-retest)",
                    "-------------------------------------------------------------------",
                    f"Rows 1-{len(section1)}: ALREADY ANSWERED from the original pass.",
                    "  Do not modify these - expert_isco/expert_notes are pre-filled.",
                    f"Rows {len(section1)+1}-{len(combined)}: NEED YOUR JUDGMENT.",
                    "  This block mixes genuinely new tasks with a small number of blind",
                    "  repeats of already-answered tasks, shuffled together and not marked.",
                    "  Judge every row in this block fresh, from the task and occupation",
                    "  context alone - do not try to recall or look up earlier answers.",
                    "  (The repeats exist to measure your own test-retest consistency; do",
                    "  not open reviewer_d3_retest_key.csv until you are completely done.)",
                    "",
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
                    "  Column H: expert_isco  <- FILL IN YOUR ANSWER HERE (for unanswered rows)",
                    "  Column I: expert_notes <- optional comments",
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

    print(f"\nWrote expanded workbook: {EXISTING_WORKBOOK}")
    print("Fill in expert_isco (and optionally expert_notes) for the unanswered rows only,")
    print("then run validation/evaluate_annotations.py (D4).")


if __name__ == "__main__":
    main()
