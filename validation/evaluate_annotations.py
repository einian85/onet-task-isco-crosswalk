"""
evaluate_annotations.py
=======================
Step 2: Evaluate Filled Human Annotation Excel

Reads the workbook produced by generate_workbook.py after a domain expert
has filled in the "expert_isco" column.

For each available ONET29 crosswalk file computes:
  - match_exact       - expert_isco == predicted ISCO (4-digit)
  - match_sub_major   - first 2 digits match
  - match_major_group - first digit matches

Output CSVs written to validation/results/:
  human_eval_onet29.csv         - per-task detail
  human_eval_onet29_summary.csv - variant comparison table

Run from the project root:
    python validation/evaluate_annotations.py
"""

from __future__ import annotations

import sys
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick
import pandas as pd

matplotlib.use("Agg")
# sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import GT_RESULTS_DIR, PROJECT_DIR, load_pipeline

VALIDATION_FILE = GT_RESULTS_DIR / "annotation_workbook_onet29.xlsx"


def discover_variants() -> list[tuple[str, Path, str]]:
    """Discover available ONET29 candidate crosswalk files."""
    variants: list[tuple[str, Path, str]] = []
    seen: set[str] = set()

    def add_variant(label: str, path: Path, description: str) -> None:
        if label in seen or not path.exists():
            return
        variants.append((label, path, description))
        seen.add(label)

    add_variant(
        "onet29_current",
        PROJECT_DIR / "output" / "ONET29_task_to_ISCO_crosswalk.csv",
        "Current ONET29 candidate config",
    )
    add_variant(
        "onet29_wt70",
        PROJECT_DIR / "output" / "ONET29_wt70_task_to_ISCO_crosswalk.csv",
        "Legacy 1D peak (w_soc_title=0.70)",
    )

    for sweep_name, sweep_dir in [
        ("focused sweep", PROJECT_DIR / "output" / "sweep_focused"),
        ("random sweep", PROJECT_DIR / "output" / "sweep_ONET29"),
    ]:
        if not sweep_dir.exists():
            continue
        for path in sorted(sweep_dir.glob("*_crosswalk.csv")):
            label = path.stem.replace("_task_to_ISCO_crosswalk", "").replace("_crosswalk", "")
            add_variant(label, path, f"Candidate crosswalk from {sweep_name}")

    return variants


def load_filled_excel(path: Path) -> pd.DataFrame | None:
    if not path.exists():
        print(f"  File not found: {path}")
        return None
    df = pd.read_excel(path, sheet_name="Validation", dtype=str)
    df.columns = df.columns.str.strip()
    if "expert_isco" not in df.columns:
        print("  'expert_isco' column not found.")
        return None
    df["expert_isco"] = df["expert_isco"].str.strip()
    filled = df["expert_isco"].notna() & (df["expert_isco"] != "")
    n_total, n_filled = len(df), int(filled.sum())
    if n_filled == 0:
        print("  No expert_isco values found.")
        return None
    print(f"  Loaded {n_total} tasks; {n_filled} have expert_isco ({n_filled / n_total * 100:.0f}%).")
    df = df[filled].copy()
    df["expert_isco_int"] = pd.to_numeric(df["expert_isco"], errors="coerce").astype("Int64")
    df["importance"] = pd.to_numeric(df["importance"], errors="coerce")
    return df


def match_flags(expert: pd.Series, pred: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    e = pd.to_numeric(expert, errors="coerce").astype("Int64")
    p = pd.to_numeric(pred, errors="coerce").astype("Int64")
    valid = e.notna() & p.notna()
    exact = pd.Series(pd.NA, index=expert.index, dtype="boolean")
    sub_major = pd.Series(pd.NA, index=expert.index, dtype="boolean")
    major_grp = pd.Series(pd.NA, index=expert.index, dtype="boolean")
    exact[valid] = e[valid] == p[valid]
    sub_major[valid] = (e[valid] // 100) == (p[valid] // 100)
    major_grp[valid] = (e[valid] // 1000) == (p[valid] // 1000)
    return exact, sub_major, major_grp


def xw_sanity_check(df: pd.DataFrame) -> dict[str, int | float | None]:
    if "crosswalk_acceptable_iscos" not in df.columns:
        return {"n_expert_isco": int(df["expert_isco_int"].notna().sum()), "pct_expert_in_xw": None}

    def in_xw(row: pd.Series) -> bool | None:
        if pd.isna(row["expert_isco_int"]) or pd.isna(row.get("crosswalk_acceptable_iscos")):
            return None
        acceptable = {
            int(x.strip())
            for x in str(row["crosswalk_acceptable_iscos"]).split(",")
            if x.strip().isdigit()
        }
        return int(row["expert_isco_int"]) in acceptable

    df = df.copy()
    df["expert_in_xw"] = df.apply(in_xw, axis=1)
    pct = round(df["expert_in_xw"].dropna().mean() * 100, 1) if df["expert_in_xw"].notna().any() else None
    return {"n_expert_isco": int(df["expert_isco_int"].notna().sum()), "pct_expert_in_xw": pct}


print("\n== Evaluating: ONET29 annotations =========================================")
df = load_filled_excel(VALIDATION_FILE)
if df is None:
    print("Nothing to evaluate. Fill in expert_isco column first.")
    sys.exit(0)

variants = discover_variants()
if not variants:
    print("No ONET29 candidate crosswalk files found.")
    sys.exit(0)

rows = []
primary_label = variants[0][0]
for label, pipeline_path, desc in variants:
    pipe = load_pipeline(pipeline_path)
    if "candidate_rank" in pipe.columns:
        pipe = pipe[pipe["candidate_rank"] == 1].copy()
    pipe = pipe[["task_id", "isco_pred", "similarity"]]

    task_ids = pd.to_numeric(df["task_id"], errors="coerce").astype("Int64")
    merged = task_ids.to_frame("task_id").merge(pipe, on="task_id", how="left")
    pred_isco = merged["isco_pred"].astype("Int64")
    mean_sim = merged["similarity"].mean()

    exact, sub_major, major_grp = match_flags(df["expert_isco_int"], pred_isco)
    n = int(exact.notna().sum())

    rows.append(
        {
            "label": label,
            "description": desc,
            "n_judged": n,
            "pct_exact": round(exact.astype(float).mean() * 100, 1),
            "pct_sub_major": round(sub_major.astype(float).mean() * 100, 1),
            "pct_major_group": round(major_grp.astype(float).mean() * 100, 1),
            "mean_similarity": round(mean_sim, 3) if pd.notna(mean_sim) else None,
        }
    )

    if label == primary_label:
        df[f"match_exact_{label}"] = exact
        df[f"match_sub_major_{label}"] = sub_major
        df[f"match_major_group_{label}"] = major_grp

summary = pd.DataFrame(rows)

print("\n--- Precision by variant --------------------------------------------------")
print(
    summary[
        ["label", "n_judged", "pct_exact", "pct_sub_major", "pct_major_group", "mean_similarity"]
    ].to_string(index=False)
)

xw = xw_sanity_check(df)
print("\n--- Expert ISCO crosswalk sanity ------------------------------------------")
print(f"  {xw['n_expert_isco']} expert ISCOs; {xw['pct_expert_in_xw']}% within crosswalk-acceptable set")

primary_match_col = f"match_exact_{primary_label}"
if primary_match_col in df.columns:
    df["expert_major_group"] = (df["expert_isco_int"].astype("Int64") // 1000).astype("Int64")
    by_major = (
        df.groupby("expert_major_group", observed=True)
        .agg(
            n=(primary_match_col, "count"),
            pct_exact=(primary_match_col, lambda x: round(x.astype(float).mean() * 100, 1)),
        )
        .reset_index()
        .sort_values("expert_major_group")
    )
    print(f"\n--- {primary_label} exact match by ISCO major group ------------------------")
    print(by_major.to_string(index=False))

detail_path = GT_RESULTS_DIR / "human_eval_onet29.csv"
summary_path = GT_RESULTS_DIR / "human_eval_onet29_summary.csv"
df.to_csv(detail_path, index=False)
summary.to_csv(summary_path, index=False)
print(f"\n  Detail:  {detail_path}")
print(f"  Summary: {summary_path}")

fig, ax = plt.subplots(figsize=(9, 5))
x = range(len(summary))
width = 0.25
ax.bar([i - width for i in x], summary["pct_exact"], width, label="Exact (4-digit)", color="C0")
ax.bar([i for i in x], summary["pct_sub_major"], width, label="Sub-major (2-digit)", color="C1")
ax.bar([i + width for i in x], summary["pct_major_group"], width, label="Major group (1-digit)", color="C2")
for i, row in summary.iterrows():
    ax.text(i - width, row["pct_exact"] + 1.5, f"{row['pct_exact']:.1f}", ha="center", fontsize=8, color="C0")
ax.set_xticks(list(x))
ax.set_xticklabels(summary["label"], rotation=15, ha="right", fontsize=10)
ax.set_ylabel("Match rate (%)", fontsize=11)
ax.set_title(
    "ONET29: expert annotation agreement by available candidate crosswalk\n"
    f"(n={len(df)} tasks; rank-1 prediction vs expert_isco)",
    fontsize=11,
)
ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f%%"))
ax.legend(fontsize=9)
ax.grid(True, axis="y", alpha=0.3)
ax.set_ylim(0, min(100, summary["pct_major_group"].max() + 12))
plt.tight_layout()
out_plot = GT_RESULTS_DIR / "human_eval_onet29_by_variant.png"
fig.savefig(out_plot, dpi=150)
plt.close(fig)
print(f"  Plot:    {out_plot}")

print("\nDone.")
