"""
gt_03_human_generate_v3.py
==========================
Ground Truth – Approach 3 (Step 1, v3): Generate Human Validation Excel

Generates a new validation workbook using the best configs from the
multidimensional parameter sweep (04_run_sweep_onet29.py), replacing the
old 1D w_soc_title sweep variants.

Weight variants shown side-by-side:
  sw0156  — best overall (mixed ISCO+ESCO; w_isco=0.587, w_dwa=0.137, w_soc=0.616)
  sw0099  — rank-2 (mixed; w_isco=0.376, w_dwa=0.092, w_soc=0.530, max_links=1)
  sw0455  — best ESCO-only (w_isco≈0, w_dwa=0.327, w_soc=0.645)
  w0.70   — old 1D ESCO-only peak (historical reference; w_soc_title=0.70)
  w0.00   — pure task-semantic baseline (no title, no ISCO blend)

LAYOUT
------
Same as v2: task_id, onet_soc_code, soc_code, soc_title, task_text, importance,
crosswalk_acceptable_iscos, expert_isco, expert_notes, then one set of
(isco_*, occ_*, sim_*) columns per variant.

TASK SELECTION — unchanged from v2
---------------------------------------
SOC codes sampled from institutional crosswalks, stratified by ISCO major group
1-9 and weighted by real employment (US + Nordic countries). Tasks selected by
O*NET importance score.

Run from the stage-02 directory:
    "C:/Users/einianma/AppData/Local/miniconda3/envs/onet-isco-nlp/python.exe" ground_truth/gt_03_human_generate_v3.py

Previous v2 workbook preserved at:
    ground_truth/results/archive_v2/gt_human_validation_ONET29_v2.xlsx
"""

from __future__ import annotations

import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import (
    GT_RESULTS_DIR,
    PROJECT_DIR,
    PIPELINE_ONET29,
    load_onet_tasks,
    load_pipeline,
    load_task_ratings,
    load_employment_totals,
    load_soc18_crosswalks,
)

# ── Configuration ─────────────────────────────────────────────────────────────
N_SOC_PER_MAJOR  = 4   # SOC codes selected per ISCO major group (1–9)
N_TASKS_PER_SOC  = 3   # Top N tasks (by O*NET importance) per SOC

SWEEP_DIR         = PROJECT_DIR / "output" / "sweep_ONET29"
FOCUSED_SWEEP_DIR = PROJECT_DIR / "output" / "sweep_focused"

# Variants shown side-by-side.
# Each entry: (label, path, description)
ONET29_WEIGHT_VARIANTS: list[tuple[str, Path, str]] = [
    ("fr0043",
     FOCUSED_SWEEP_DIR / "fr0043_crosswalk.csv",
     "Best focused: w_isco=0.828, w_dwa=0.037, w_soc=0.599, min_sim=0.522, links=1"),
    ("fg_isco04_dwa00_soc50",
     FOCUSED_SWEEP_DIR / "fg_isco04_dwa00_soc50_crosswalk.csv",
     "Best grid: w_isco=0.4, w_dwa=0.0, w_soc=0.50, min_sim=0.45, links=1 (clean/interpretable)"),
    ("sw0156",
     SWEEP_DIR / "ONET29_sw0156_crosswalk.csv",
     "Best random sweep: w_isco=0.587, w_dwa=0.137, w_soc=0.616, min_sim=0.381, links=3"),
    ("w0.70",
     PROJECT_DIR / "output" / "ONET29_wt70_task_to_ISCO_crosswalk.csv",
     "Old 1D peak (historical reference): ESCO-only, w_soc_title=0.70"),
    ("w0.00",
     PIPELINE_ONET29,
     "Pure baseline: no title blending, no ISCO component"),
]


def _load_pipeline_lookup(path: Path, label: str) -> pd.DataFrame:
    """Load pipeline output as per-task lookup with label-prefixed columns.

    Handles both single-link (old pipeline) and multi-link (sweep) CSVs.
    For multi-link outputs, only the rank-1 prediction is used.
    Also handles both 'occupationLabel' (old) and 'isco_title' (new) column names.
    """
    pipe = load_pipeline(path)

    # Filter to rank-1 if candidate_rank is present
    if "candidate_rank" in pipe.columns:
        pipe = pipe[pipe["candidate_rank"] == 1].copy()

    # Normalise occupation label column name
    if "isco_title" in pipe.columns and "occupationLabel" not in pipe.columns:
        pipe = pipe.rename(columns={"isco_title": "occupationLabel"})

    lookup = (
        pipe[["task_id", "isco_pred", "occupationLabel", "similarity"]]
        .rename(columns={
            "isco_pred":       f"isco_{label}",
            "occupationLabel": f"occ_{label}",
            "similarity":      f"sim_{label}",
        })
        .drop_duplicates("task_id")
    )
    return lookup


def generate_validation_sheet(
    weight_variants: list[tuple[str, Path, str]],
    onet_version: str,
    crosswalk_dfs: list[pd.DataFrame],
    soc_col: str,
    output_filename: str,
) -> pd.DataFrame:
    """Build a multi-variant validation DataFrame and write it to Excel."""

    # ── Step 1: Combined institutional crosswalk ──────────────────────────────
    combined_xw = (
        pd.concat([df[[soc_col, "isco_code"]] for df in crosswalk_dfs])
        .drop_duplicates()
        .reset_index(drop=True)
    )
    combined_xw["isco_major"] = (combined_xw["isco_code"].astype(int) // 1000).astype(int)

    # ── Step 2: Employment data ───────────────────────────────────────────────
    emp = load_employment_totals()
    combined_xw_emp = combined_xw.merge(emp, on="isco_code", how="left")

    # ── Step 3: Stratified O*NET-SOC selection ────────────────────────────────
    all_tasks = load_onet_tasks(onet_version)
    onet_soc_map = all_tasks[["onet_soc_code", "soc_code", "soc_title"]].drop_duplicates("onet_soc_code")
    xw_for_emp = combined_xw_emp.rename(columns={soc_col: "soc_code"})
    onet_soc_xw_emp = onet_soc_map.merge(xw_for_emp, on="soc_code", how="left")

    sampled_onet_socs: list[str] = []
    already_seen: set[str] = set()

    print(f"\n  {'Major':>5}  {'O*NET-SOC':<14}  {'SOC title':<44}  {'Emp (major)':>12}")
    print(f"  {'-----':>5}  {'-'*14}  {'-'*44}  {'-'*12}")

    for major in sorted(onet_soc_xw_emp["isco_major"].dropna().unique().astype(int)):
        xw_major = onet_soc_xw_emp[onet_soc_xw_emp["isco_major"] == major]
        onet_emp_major = (
            xw_major.groupby("onet_soc_code")["total_emp"]
            .sum().fillna(0).reset_index()
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

    # ── Step 4: Load task ratings ─────────────────────────────────────────────
    ratings = load_task_ratings(onet_version)

    tasks_top = (
        all_tasks[all_tasks["onet_soc_code"].isin(sampled_onet_socs)]
        .merge(ratings, on="task_id", how="left")
        .sort_values(["onet_soc_code", "importance"], ascending=[True, False])
        .groupby("onet_soc_code", group_keys=False)
        .head(N_TASKS_PER_SOC)
        .reset_index(drop=True)
    )

    onet_soc_order = {s: i for i, s in enumerate(sampled_onet_socs)}
    tasks_top["_order"] = tasks_top["onet_soc_code"].map(onet_soc_order)
    tasks_top = (
        tasks_top.sort_values(["_order", "importance"], ascending=[True, False])
        .drop(columns="_order")
    )

    print(f"  Tasks selected for validation: {len(tasks_top)}")

    # ── Step 5: Merge pipeline predictions for each variant ───────────────────
    validation = tasks_top.copy()
    for label, path, desc in weight_variants:
        if not path.exists():
            print(f"  [SKIP] {label}: file not found — {path}")
            continue
        lookup = _load_pipeline_lookup(path, label)
        validation = validation.merge(lookup, on="task_id", how="left")
        print(f"  Merged predictions: {label}  ({desc[:60]})")

    # ── Step 6: Crosswalk reference ───────────────────────────────────────────
    acceptable_per_soc = (
        combined_xw.groupby(soc_col)["isco_code"]
        .apply(lambda x: ", ".join(str(c) for c in sorted(x.dropna().unique().astype(int))))
        .reset_index()
        .rename(columns={soc_col: "soc_code", "isco_code": "crosswalk_acceptable_iscos"})
    )
    validation = validation.merge(acceptable_per_soc, on="soc_code", how="left")

    # ── Step 7: Expert annotation columns ────────────────────────────────────
    validation["expert_isco"]  = ""
    validation["expert_notes"] = ""

    # ── Column order ──────────────────────────────────────────────────────────
    base_cols   = ["task_id", "onet_soc_code", "soc_code", "soc_title", "task_text", "importance"]
    ref_cols    = ["crosswalk_acceptable_iscos"]
    expert_cols = ["expert_isco", "expert_notes"]
    pred_cols   = []
    for label, _, _ in weight_variants:
        for col in [f"isco_{label}", f"occ_{label}", f"sim_{label}"]:
            if col in validation.columns:
                pred_cols.append(col)

    col_order = base_cols + ref_cols + expert_cols + pred_cols
    validation = validation[[c for c in col_order if c in validation.columns]]

    # ── Write to Excel ────────────────────────────────────────────────────────
    out_path = GT_RESULTS_DIR / output_filename
    with pd.ExcelWriter(out_path, engine="xlsxwriter") as writer:
        validation.to_excel(writer, sheet_name="Validation", index=False)

        variant_summary_lines = [
            f"  {label:<12} — {desc}" for label, _, desc in weight_variants
        ]

        instructions = pd.DataFrame({"Instructions": [
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
            "  Columns J+: pipeline predictions for each configuration (scroll right)",
            "",
            "TIP: Freeze panes at column J to keep task context visible while scrolling.",
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
            "PIPELINE CONFIGURATIONS",
            "-----------------------",
            "  This workbook uses the best configs from a 500-run multidimensional",
            "  parameter sweep (v3, 2026). Each config has its own (isco, occ, sim) columns.",
            "",
        ] + variant_summary_lines + [
            "",
            "PREDICTION COLUMNS",
            "------------------",
            "  isco_*  -- predicted 4-digit ISCO code",
            "  occ_*   -- ISCO occupation label for that prediction",
            "  sim_*   -- cosine similarity (0.45-1.00; higher = more confident)",
            "",
            "PARAMETERS (key ones)",
            "---------------------",
            "  w_isco       -- weight of ISCO-08 task descriptions in target blend (0=ESCO-only)",
            "  w_dwa        -- weight of DWA labels in query blend (low = better)",
            "  w_soc_title  -- weight of SOC title in query blend (peaks ~0.5-0.6)",
            "  min_sim      -- minimum similarity to include a link",
            "  links        -- max ISCO links per O*NET task (1 = single best match)",
            "",
            "ISCO major groups (first digit):",
            "  1=Managers  2=Professionals  3=Technicians  4=Clerical  5=Service",
            "  6=Agricultural  7=Craft  8=Operators  9=Elementary",
        ]})
        instructions.to_excel(writer, sheet_name="Instructions", index=False)

    print(f"  Written: {out_path}")
    return validation


if __name__ == "__main__":
    print("\n== Generating: ONET29 / SOC18 (v3 — multidimensional sweep configs) =====")

    xw18 = load_soc18_crosswalks()
    generate_validation_sheet(
        weight_variants=ONET29_WEIGHT_VARIANTS,
        onet_version="29",
        crosswalk_dfs=[xw18["xw18_1"], xw18["xw18_2"][["soc_code18", "isco_code"]]],
        soc_col="soc_code18",
        output_filename="gt_human_validation_ONET29_v3.xlsx",
    )

    print("\nDone. Fill in expert_isco (and optionally expert_notes) for each row,")
    print("then run gt_03_human_evaluate_v3.py.")
