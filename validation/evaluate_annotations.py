"""
gt_03_human_evaluate_v3.py
==========================
Ground Truth – Approach 3 (Step 2, v3): Evaluate Filled Human Validation Excel

Reads the Excel file produced by gt_03_human_generate_v3.py after a domain
expert has filled in the "expert_isco" column.

For each pipeline configuration (sw0156, sw0099, sw0455, w0.70, w0.00) computes:
  - match_exact       — expert_isco == isco_{label}  (4-digit)
  - match_sub_major   — first 2 digits match
  - match_major_group — first digit matches

Also compares against the v2 results to track improvement.

Output CSVs written to ground_truth/results/:
  gt03_human_eval_ONET29_v3.csv         — per-task detail
  gt03_human_eval_summary_ONET29_v3.csv — variant comparison table

Usage:
    "C:/Users/einianma/AppData/Local/miniconda3/envs/onet-isco-nlp/python.exe" ground_truth/gt_03_human_evaluate_v3.py
"""

from __future__ import annotations

import sys
sys.stdout.reconfigure(encoding="utf-8")

from pathlib import Path
import numpy as np
import pandas as pd
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
import matplotlib.ticker as mtick

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))

from shared import GT_RESULTS_DIR, PROJECT_DIR, load_pipeline

VALIDATION_FILE = GT_RESULTS_DIR / "gt_human_validation_ONET29_v3.xlsx"
SWEEP_DIR         = PROJECT_DIR / "output" / "sweep_ONET29"
FOCUSED_SWEEP_DIR = PROJECT_DIR / "output" / "sweep_focused"

# All variants to evaluate.
# For columns already in the workbook, path=None; otherwise load from pipeline CSV.
VARIANTS: list[tuple[str, Path | None, str]] = [
    ("fr0043", None,
     "Best focused (w_isco=0.828, w_dwa=0.037, w_soc=0.599, links=1)"),
    ("fg_isco04_dwa00_soc50", None,
     "Best grid (w_isco=0.4, w_dwa=0.0, w_soc=0.50, links=1)"),
    ("sw0156", None,
     "Best random sweep (w_isco=0.587, w_dwa=0.137, w_soc=0.616, links=3)"),
    ("w0.70",  None,
     "Old 1D peak (ESCO-only, w_soc_title=0.70)"),
    ("w0.00",  None,
     "Pure baseline (no title, no ISCO)"),
]


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
    n_total, n_filled = len(df), filled.sum()
    if n_filled == 0:
        print("  No expert_isco values found.")
        return None
    print(f"  Loaded {n_total} tasks; {n_filled} have expert_isco ({n_filled/n_total*100:.0f}%).")
    df = df[filled].copy()
    df["expert_isco_int"] = pd.to_numeric(df["expert_isco"], errors="coerce").astype("Int64")
    df["importance"]      = pd.to_numeric(df["importance"],  errors="coerce")
    return df


def match_flags(expert: pd.Series, pred: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    e = pd.to_numeric(expert, errors="coerce").astype("Int64")
    p = pd.to_numeric(pred,   errors="coerce").astype("Int64")
    valid = e.notna() & p.notna()
    exact     = pd.Series(pd.NA, index=expert.index, dtype="boolean")
    sub_major = pd.Series(pd.NA, index=expert.index, dtype="boolean")
    major_grp = pd.Series(pd.NA, index=expert.index, dtype="boolean")
    exact[valid]     = e[valid] == p[valid]
    sub_major[valid] = (e[valid] // 100) == (p[valid] // 100)
    major_grp[valid] = (e[valid] // 1000) == (p[valid] // 1000)
    return exact, sub_major, major_grp


def xw_sanity_check(df: pd.DataFrame) -> dict:
    if "crosswalk_acceptable_iscos" not in df.columns:
        return {"n_expert_isco": int(df["expert_isco_int"].notna().sum()), "pct_expert_in_xw": None}
    def in_xw(row):
        if pd.isna(row["expert_isco_int"]) or pd.isna(row.get("crosswalk_acceptable_iscos")):
            return None
        acceptable = {int(x.strip()) for x in str(row["crosswalk_acceptable_iscos"]).split(",")
                      if x.strip().isdigit()}
        return int(row["expert_isco_int"]) in acceptable
    df = df.copy()
    df["expert_in_xw"] = df.apply(in_xw, axis=1)
    pct = round(df["expert_in_xw"].dropna().mean() * 100, 1) if df["expert_in_xw"].notna().any() else None
    return {"n_expert_isco": int(df["expert_isco_int"].notna().sum()), "pct_expert_in_xw": pct}


# ── Main ──────────────────────────────────────────────────────────────────────

print(f"\n== Evaluating: ONET29 v3 ==================================================")
df = load_filled_excel(VALIDATION_FILE)
if df is None:
    print("Nothing to evaluate. Fill in expert_isco column first.")
    sys.exit(0)

rows = []
for label, pipeline_path, desc in VARIANTS:
    isco_col = f"isco_{label}"
    sim_col  = f"sim_{label}"

    if isco_col in df.columns:
        pred_isco = df[isco_col]
        mean_sim  = pd.to_numeric(df[sim_col], errors="coerce").mean() if sim_col in df.columns else None
    elif pipeline_path is not None and pipeline_path.exists():
        pipe = load_pipeline(pipeline_path)
        if "candidate_rank" in pipe.columns:
            pipe = pipe[pipe["candidate_rank"] == 1]
        pipe = pipe[["task_id", "isco_pred", "similarity"]]
        task_ids = pd.to_numeric(df["task_id"], errors="coerce").astype("Int64")
        merged = task_ids.to_frame("task_id").merge(pipe, on="task_id", how="left")
        pred_isco = merged["isco_pred"].astype("Int64")
        mean_sim  = merged["similarity"].mean()
    else:
        print(f"  No source for {label} — skipping")
        continue

    exact, sub_major, major_grp = match_flags(df["expert_isco_int"], pred_isco)
    n = int(exact.notna().sum())

    rows.append({
        "label":           label,
        "description":     desc,
        "n_judged":        n,
        "pct_exact":       round(exact.astype(float).mean() * 100, 1),
        "pct_sub_major":   round(sub_major.astype(float).mean() * 100, 1),
        "pct_major_group": round(major_grp.astype(float).mean() * 100, 1),
        "mean_similarity": round(mean_sim, 3) if mean_sim is not None else None,
    })

    # Store per-task flags for fr0043 breakdown
    if label == "fr0043":
        df["match_exact_fr0043"]       = exact
        df["match_sub_major_fr0043"]   = sub_major
        df["match_major_group_fr0043"] = major_grp

summary = pd.DataFrame(rows)

print("\n─── Precision by variant ─────────────────────────────────────────────────")
print(summary[["label","n_judged","pct_exact","pct_sub_major","pct_major_group","mean_similarity"]].to_string(index=False))

xw = xw_sanity_check(df)
print(f"\n─── Expert ISCO crosswalk sanity ─────────────────────────────────────────")
print(f"  {xw['n_expert_isco']} expert ISCOs; {xw['pct_expert_in_xw']}% within crosswalk-acceptable set")

# ── Breakdown by ISCO major group (sw0156) ────────────────────────────────────
if "match_exact_fr0043" in df.columns:
    df["expert_major_group"] = (df["expert_isco_int"].astype("Int64") // 1000).astype("Int64")
    by_major = (
        df.groupby("expert_major_group", observed=True)
        .agg(
            n=("match_exact_fr0043", "count"),
            pct_exact=("match_exact_fr0043",
                       lambda x: round(x.astype(float).mean() * 100, 1)),
        )
        .reset_index()
        .sort_values("expert_major_group")
    )
    print(f"\n─── fr0043 exact match by ISCO major group ───────────────────────────────")
    print(by_major.to_string(index=False))

# ── Write outputs ─────────────────────────────────────────────────────────────
detail_path  = GT_RESULTS_DIR / "gt03_human_eval_ONET29_v3.csv"
summary_path = GT_RESULTS_DIR / "gt03_human_eval_summary_ONET29_v3.csv"
df.to_csv(detail_path, index=False)
summary.to_csv(summary_path, index=False)
print(f"\n  Detail:  {detail_path}")
print(f"  Summary: {summary_path}")

# ── Plot: precision by variant ────────────────────────────────────────────────
fig, ax = plt.subplots(figsize=(9, 5))
x = range(len(summary))
width = 0.25
ax.bar([i - width for i in x], summary["pct_exact"],     width, label="Exact (4-digit)", color="C0")
ax.bar([i         for i in x], summary["pct_sub_major"], width, label="Sub-major (2-digit)", color="C1")
ax.bar([i + width for i in x], summary["pct_major_group"], width, label="Major group (1-digit)", color="C2")
for i, row in summary.iterrows():
    ax.text(i - width, row["pct_exact"] + 1.5, f"{row['pct_exact']:.1f}", ha="center", fontsize=8, color="C0")
ax.set_xticks(list(x))
ax.set_xticklabels(summary["label"], rotation=15, ha="right", fontsize=10)
ax.set_ylabel("Match rate (%)", fontsize=11)
ax.set_title("ONET29 v3: expert annotation agreement by configuration\n"
             f"(n={len(df)} tasks; rank-1 prediction vs expert_isco)", fontsize=11)
ax.yaxis.set_major_formatter(mtick.FormatStrFormatter("%.0f%%"))
ax.legend(fontsize=9)
ax.grid(True, axis="y", alpha=0.3)
ax.set_ylim(0, min(100, summary["pct_major_group"].max() + 12))
plt.tight_layout()
out_plot = GT_RESULTS_DIR / "gt03_human_eval_ONET29_v3_by_variant.png"
fig.savefig(out_plot, dpi=150)
plt.close(fig)
print(f"  Plot:    {out_plot}")

# ── Comparison table with v2 results ─────────────────────────────────────────
v2_summary_path = GT_RESULTS_DIR / "archive_v2" / "gt03_human_eval_summary_ONET29_v2.csv"
if v2_summary_path.exists():
    v2 = pd.read_csv(v2_summary_path)
    v2_best = v2.loc[v2["pct_exact"].idxmax()]
    fr0043_row = summary[summary["label"] == "fr0043"]
    if not fr0043_row.empty:
        sw = fr0043_row.iloc[0]
        print(f"\n─── v2 vs v3 comparison ──────────────────────────────────────────────────")
        print(f"  v2 best ({v2_best['weight']}): exact={v2_best['pct_exact']}%  "
              f"sub_major={v2_best['pct_sub_major']}%  major={v2_best['pct_major_group']}%")
        print(f"  v3 fr0043:          exact={sw['pct_exact']}%  "
              f"sub_major={sw['pct_sub_major']}%  major={sw['pct_major_group']}%")
        delta = sw['pct_exact'] - v2_best['pct_exact']
        print(f"  Delta exact: {delta:+.1f}pp")

print("\nDone.")
