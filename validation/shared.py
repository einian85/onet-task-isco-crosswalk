"""
shared.py
=========
Shared helpers imported by all validation scripts.

Run any validation script from the project root, e.g.:
    python validation/validate_chain.py

All data paths resolve relative to the project directory automatically (data/ subfolder).
"""

from __future__ import annotations

import re
from pathlib import Path

import numpy as np
import pandas as pd

# ── Project directory (two levels up from this file) ─────────────────────────
PROJECT_DIR   = Path(__file__).resolve().parent.parent
AI_ON_JOBS_DIR = PROJECT_DIR.parent   # root AI-on-Jobs repo
DATA_DIR      = PROJECT_DIR / "data"

# ── Output directory ──────────────────────────────────────────────────────────
GT_RESULTS_DIR = PROJECT_DIR / "validation" / "results"
GT_RESULTS_DIR.mkdir(parents=True, exist_ok=True)

# ── Pipeline output paths ─────────────────────────────────────────────────────
# Two crosswalk variants derived from different O*NET releases.
# NEVER mix task IDs across releases: O*NET ≤25.0 uses SOC10, ≥25.1 uses SOC18.
PIPELINE_ONET29      = PROJECT_DIR / "output" / "ONET29_task_to_ISCO_crosswalk.csv"       # 29.2 / SOC18 (baseline w=0.00)
PIPELINE_ONET29_WT10 = PROJECT_DIR / "output" / "ONET29_wt10_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.10)
PIPELINE_ONET29_WT20 = PROJECT_DIR / "output" / "ONET29_wt20_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.20)
PIPELINE_ONET29_WT30 = PROJECT_DIR / "output" / "ONET29_wt30_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.30)
PIPELINE_ONET29_WT40 = PROJECT_DIR / "output" / "ONET29_wt40_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.40)
PIPELINE_ONET29_WT50 = PROJECT_DIR / "output" / "ONET29_wt50_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.50)
PIPELINE_ONET29_WT60 = PROJECT_DIR / "output" / "ONET29_wt60_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.60)
PIPELINE_ONET29_WT65 = PROJECT_DIR / "output" / "ONET29_wt65_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.65)
PIPELINE_ONET29_WT70 = PROJECT_DIR / "output" / "ONET29_wt70_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.70)
PIPELINE_ONET29_WT75 = PROJECT_DIR / "output" / "ONET29_wt75_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.75)
PIPELINE_ONET29_WT80 = PROJECT_DIR / "output" / "ONET29_wt80_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.80)
PIPELINE_ONET29_WT85 = PROJECT_DIR / "output" / "ONET29_wt85_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.85)
PIPELINE_ONET29_WT90 = PROJECT_DIR / "output" / "ONET29_wt90_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.90)
PIPELINE_ONET29_WT99 = PROJECT_DIR / "output" / "ONET29_wt99_task_to_ISCO_crosswalk.csv"  # 29.2 / SOC18 (w_soc_title=0.99)
PIPELINE_ONET25      = PROJECT_DIR / "output" / "ONET25_task_to_ISCO_crosswalk.csv"       # 25.0 / SOC10 (baseline w=0.00)
PIPELINE_ONET25_WT10 = PROJECT_DIR / "output" / "ONET25_wt10_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.10)
PIPELINE_ONET25_WT20 = PROJECT_DIR / "output" / "ONET25_wt20_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.20)
PIPELINE_ONET25_WT30 = PROJECT_DIR / "output" / "ONET25_wt30_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.30)
PIPELINE_ONET25_WT40 = PROJECT_DIR / "output" / "ONET25_wt40_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.40)
PIPELINE_ONET25_WT50 = PROJECT_DIR / "output" / "ONET25_wt50_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.50)
PIPELINE_ONET25_WT60 = PROJECT_DIR / "output" / "ONET25_wt60_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.60)
PIPELINE_ONET25_WT65 = PROJECT_DIR / "output" / "ONET25_wt65_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.65)
PIPELINE_ONET25_WT70 = PROJECT_DIR / "output" / "ONET25_wt70_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.70)
PIPELINE_ONET25_WT75 = PROJECT_DIR / "output" / "ONET25_wt75_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.75)
PIPELINE_ONET25_WT80 = PROJECT_DIR / "output" / "ONET25_wt80_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.80)
PIPELINE_ONET25_WT85 = PROJECT_DIR / "output" / "ONET25_wt85_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.85)
PIPELINE_ONET25_WT90 = PROJECT_DIR / "output" / "ONET25_wt90_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.90)
PIPELINE_ONET25_WT99 = PROJECT_DIR / "output" / "ONET25_wt99_task_to_ISCO_crosswalk.csv"  # 25.0 / SOC10 (w_soc_title=0.99)

# ── O*NET task statement paths ────────────────────────────────────────────────
ONET_TASKS_29   = DATA_DIR / "onet" / "29_2" / "Task Statements.xlsx"
ONET_TASKS_25   = DATA_DIR / "onet" / "25_0" / "Task Statements.xlsx"

# ── O*NET Task Ratings paths (in main Data dir — too large for stage 02 data/) ─
ONET_TASK_RATINGS_29 = (
    AI_ON_JOBS_DIR / "Data" / "Managed-Occupation-Standards"
    / "ONET-db_29_2_excel" / "Task Ratings.xlsx"
)
ONET_TASK_RATINGS_25 = (
    AI_ON_JOBS_DIR / "Data" / "Managed-Occupation-Standards"
    / "db_25_0_excel" / "Task Ratings.xlsx"
)

# ── Employment statistics directory ───────────────────────────────────────────
EMP_STATS_DIR = AI_ON_JOBS_DIR / "Data" / "Managed-EmpStats"

# ── Raw crosswalk file paths ──────────────────────────────────────────────────
# SOC18 crosswalks — use with ONET29 pipeline
XW_ESCO_TO_SOC18 = DATA_DIR / "crosswalks" / "ESCO_to_ONET-SOC.xlsx"             # ESCO → ONET-SOC18
XW_SOC18_TO_ESCO = DATA_DIR / "crosswalks" / "ONET_(Occupations)_0_updated.csv"  # ONET-SOC18 → ESCO/ISCO (ESCO Secretariat)

# SOC10 crosswalks — use with ONET25 pipeline
XW_ESCO_ONET_MHV  = DATA_DIR / "crosswalks" / "esco_onet_matysiaketal2024.csv"  # ESCO ↔ O*NET, semantic similarity (Matysiak et al. 2024)
XW_SOC10_ISCO_BLS = DATA_DIR / "crosswalks" / "isco_soc_crosswalk.xls"          # BLS official SOC10 → ISCO

# ── HR survey path ────────────────────────────────────────────────────────────
# Optional — not included in standalone distribution. Script skips Part B if missing.
HR_SURVEY_PATH = PROJECT_DIR / "data" / "hr_survey" / "AI in HR Tasks – Optional Follow-Up Survey(1-12).xlsx"


# ── SOC code normalisation ────────────────────────────────────────────────────

def soc_to_7(s: pd.Series) -> pd.Series:
    """Extract the 7-char base SOC code: '11-1011.00' → '11-1011'."""
    return s.astype(str).str.strip().str[:7]


def clean_names(df: pd.DataFrame) -> pd.DataFrame:
    """Convert column names to snake_case (equivalent to janitor::clean_names)."""
    def _snake(name: str) -> str:
        name = re.sub(r"[^\w\s]", "_", name)
        name = re.sub(r"\s+", "_", name)
        name = re.sub(r"_+", "_", name)
        return name.lower().strip("_")
    df.columns = [_snake(c) for c in df.columns]
    return df


# ── Load SOC18 crosswalks ─────────────────────────────────────────────────────
# Returns a dict with keys "xw18_1" and "xw18_2".
# Both DataFrames have columns: soc_code18 (str 7-char), isco_code (int 4-digit).
# xw18_2 additionally has: type_of_match, match_score.
#
# Match score mapping for XW18.2:
#   exactMatch / exactISCO → 1.00 (official ISCO equivalence)
#   narrowMatch            → 0.90
#   closeMatch             → 0.75
#   broadMatch             → 0.60  (excluded from high-quality analyses)

MATCH_SCORES = {
    "exactMatch":  1.00,
    "exactISCO":   1.00,
    "narrowMatch": 0.90,
    "closeMatch":  0.75,
    "broadMatch":  0.60,
}

def load_soc18_crosswalks() -> dict[str, pd.DataFrame]:
    # XW18.1: ESCO → ONET-SOC
    # The ISCO code is embedded in the ESCO URI as the numeric prefix before the dot.
    raw1 = clean_names(pd.read_excel(XW_ESCO_TO_SOC18, sheet_name="Crosswalk"))
    raw1["isco_code"] = (
        raw1["esco_code"].astype(str)
        .str.split(".", n=1).str[0]
        .pipe(pd.to_numeric, errors="coerce")
        .astype("Int64")
    )
    xw18_1 = (
        raw1.assign(soc_code18=soc_to_7(raw1["soc19_code"]))
        [["soc_code18", "isco_code"]]
        .dropna(subset=["isco_code"])
        .loc[lambda d: d["isco_code"].astype(str).str.len() == 4]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    # XW18.2: ONET-SOC → ESCO/ISCO (CSV; ISCO code extracted from URI, e.g. ".../isco/C2512")
    # The file has a 16-row metadata preamble before the actual column header row.
    raw2 = clean_names(pd.read_csv(XW_SOC18_TO_ESCO, skiprows=16))
    raw2["isco_code_raw"] = (
        raw2["esco_or_isco_uri"]
        .where(raw2["esco_or_isco_uri"].str.contains("/isco/", na=False))
        .str.extract(r"/C(\d{4})", expand=False)
    )
    xw18_2 = (
        raw2.assign(
            soc_code18=soc_to_7(raw2["o_net_id"]),
            isco_code=pd.to_numeric(raw2["isco_code_raw"], errors="coerce").astype("Int64"),
            match_score=raw2["type_of_match"].map(MATCH_SCORES),
        )
        [["soc_code18", "isco_code", "type_of_match", "match_score"]]
        .dropna(subset=["isco_code"])
        .loc[lambda d: d["isco_code"].astype(str).str.len() == 4]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    return {"xw18_1": xw18_1, "xw18_2": xw18_2}


# ── Load SOC10 crosswalks ─────────────────────────────────────────────────────
# Returns a dict with keys "xw10_1", "xw10_2".
# All DataFrames have columns: soc_code10 (str 7-char), isco_code (int 4-digit).
#
# xw10_1 was built from ESCO ↔ O*NET semantic similarity; it is less
# independent as ground truth than xw10_2 (see note in gt_01_chain.py).
# xw10_2 is the BLS official SOC10-ISCO08 table.
# IBS Poland (xw10_3) was dropped: derived from BLS, adds no independent information.

def load_soc10_crosswalks() -> dict[str, pd.DataFrame]:
    # XW10.1: ESCO ↔ O*NET semantic similarity (Matysiak et al. 2024)
    # O*NET codes ("11-1011.00") are truncated to 7-char SOC10 codes.
    raw1 = clean_names(pd.read_csv(XW_ESCO_ONET_MHV))
    xw10_1 = (
        raw1.assign(soc_code10=soc_to_7(raw1["onet_code"]),
                    isco_code=pd.to_numeric(raw1["isco_code"], errors="coerce").astype("Int64"))
        [["soc_code10", "isco_code"]]
        .dropna(subset=["isco_code"])
        .loc[lambda d: d["isco_code"].astype(str).str.len() == 4]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    # XW10.2: BLS official ISCO08-SOC10 crosswalk (.xls — requires xlrd)
    raw2 = clean_names(pd.read_excel(XW_SOC10_ISCO_BLS))
    xw10_2 = (
        raw2.assign(soc_code10=soc_to_7(raw2["2010_soc_code"]),
                    isco_code=pd.to_numeric(raw2["isco_08_code"], errors="coerce").astype("Int64"))
        [["soc_code10", "isco_code"]]
        .dropna(subset=["isco_code"])
        .loc[lambda d: d["isco_code"].astype(str).str.len() == 4]
        .drop_duplicates()
        .reset_index(drop=True)
    )

    return {"xw10_1": xw10_1, "xw10_2": xw10_2}


# ── Load O*NET task statements ────────────────────────────────────────────────
# Returns DataFrame with columns: task_id (int), soc_code (str 7-char),
#   task_text (str), soc_title (str).
# onet_version: "29" or "25".

def load_onet_tasks(onet_version: str = "29") -> pd.DataFrame:
    path = ONET_TASKS_29 if onet_version == "29" else ONET_TASKS_25
    if not path.exists():
        raise FileNotFoundError(f"O*NET task statements not found: {path}")
    raw = clean_names(pd.read_excel(path))
    return (
        raw.assign(
            task_id=raw["task_id"].astype(int),
            onet_soc_code=raw["o_net_soc_code"].astype(str).str.strip(),  # full code e.g. "11-9199.01"
            soc_code=soc_to_7(raw["o_net_soc_code"]),                     # 6-digit e.g. "11-9199"
            task_text=raw["task"],
            soc_title=raw["title"],
        )
        [["task_id", "onet_soc_code", "soc_code", "task_text", "soc_title"]]
        .drop_duplicates()
        .reset_index(drop=True)
    )



# ── Load pipeline S5_FINAL output ────────────────────────────────────────────
# Returns DataFrame with all S5_FINAL rows; renames iscoGroup → isco_pred.

def load_pipeline(pipeline_path: Path) -> pd.DataFrame:
    if not pipeline_path.exists():
        raise FileNotFoundError(
            f"Pipeline output not found: {pipeline_path}\n  Run the Python pipeline first."
        )
    df = pd.read_csv(pipeline_path)
    df = df[df["stage"] == "S5_FINAL"].copy()
    if "iscoGroup" in df.columns:
        df = df.rename(columns={"iscoGroup": "isco_pred"})
    df["isco_pred"] = pd.to_numeric(df["isco_pred"], errors="coerce").astype("Int64")
    # task_id is stored as string in the pipeline CSV (task_key for ID-keyed runs);
    # convert to Int64 so it merges correctly with O*NET integer task IDs.
    df["task_id"] = pd.to_numeric(df["task_id"], errors="coerce").astype("Int64")
    return df.reset_index(drop=True)


# ── Core match evaluation ─────────────────────────────────────────────────────
# Given a pipeline DataFrame [task_id, isco_pred, similarity, gap_1_2],
# a task→SOC mapping [task_id, soc_code], and a crosswalk [soc_col, isco_code],
# returns the merged DataFrame with added boolean columns:
#   match_exact       — isco_pred exactly in acceptable ISCO set
#   match_sub_major   — first 2 digits of isco_pred in acceptable sub-majors
#   match_major_group — first digit of isco_pred in acceptable major groups
#   in_crosswalk      — whether the task's SOC has any entry in the crosswalk
#   sim_bin           — similarity binned into 4 ranges
#   pred_major_group  — first digit of isco_pred (1–9)

def evaluate_match(
    pipeline_df: pd.DataFrame,
    task_soc_df: pd.DataFrame,
    crosswalk_df: pd.DataFrame,
    soc_col: str,
) -> pd.DataFrame:
    # Build acceptable ISCO sets per SOC code
    grp = crosswalk_df.groupby(soc_col)["isco_code"].apply(
        lambda x: set(x.dropna().astype(int))
    ).reset_index()
    grp.columns = ["soc_code", "acceptable_iscos"]
    grp["acceptable_major_groups"] = grp["acceptable_iscos"].apply(lambda s: {c // 1000 for c in s})
    grp["acceptable_sub_majors"]   = grp["acceptable_iscos"].apply(lambda s: {c // 100  for c in s})

    # Merge pipeline → task SOC
    dt = (
        pipeline_df[["task_id", "isco_pred", "similarity", "gap_1_2"]]
        .merge(task_soc_df[["task_id", "soc_code"]], on="task_id", how="left")
    )

    # Merge → acceptable ISCO sets
    dt = dt.merge(grp, on="soc_code", how="left")

    # in_crosswalk: the task's SOC code has at least one entry in the crosswalk
    dt["in_crosswalk"] = dt["acceptable_iscos"].notna()

    # Match flags (only for tasks covered by crosswalk)
    covered = dt["in_crosswalk"]
    dt["match_exact"]       = pd.NA
    dt["match_sub_major"]   = pd.NA
    dt["match_major_group"] = pd.NA

    dt.loc[covered, "match_exact"] = dt.loc[covered].apply(
        lambda r: int(r["isco_pred"]) in r["acceptable_iscos"], axis=1
    )
    dt.loc[covered, "match_sub_major"] = dt.loc[covered].apply(
        lambda r: (int(r["isco_pred"]) // 100) in r["acceptable_sub_majors"], axis=1
    )
    dt.loc[covered, "match_major_group"] = dt.loc[covered].apply(
        lambda r: (int(r["isco_pred"]) // 1000) in r["acceptable_major_groups"], axis=1
    )

    # Similarity bins
    dt["sim_bin"] = np.select(
        [dt["similarity"] < 0.50, dt["similarity"] < 0.60, dt["similarity"] < 0.70],
        ["[0.45,0.50)", "[0.50,0.60)", "[0.60,0.70)"],
        default="[0.70,1.00]",
    )

    dt["pred_major_group"] = dt["isco_pred"].astype("Int64") // 1000

    return dt.reset_index(drop=True)


# ── Summary metrics ───────────────────────────────────────────────────────────

def summarise_match(dt: pd.DataFrame, label: str = "") -> pd.DataFrame:
    """One-row summary: overall coverage and match rates."""
    covered = dt[dt["in_crosswalk"] == True]
    return pd.DataFrame([{
        "label":            label,
        "n_tasks":          len(dt),
        "n_in_crosswalk":   int(dt["in_crosswalk"].sum()),
        "pct_in_crosswalk": round(dt["in_crosswalk"].mean() * 100, 1),
        "pct_exact":        round(covered["match_exact"].astype(float).mean() * 100, 1),
        "pct_sub_major":    round(covered["match_sub_major"].astype(float).mean() * 100, 1),
        "pct_major_group":  round(covered["match_major_group"].astype(float).mean() * 100, 1),
    }])


def summarise_by_sim_bin(dt: pd.DataFrame, label: str = "") -> pd.DataFrame:
    """Match rates broken down by similarity bin."""
    covered = dt[dt["in_crosswalk"] == True].copy()
    agg = (
        covered.groupby("sim_bin", observed=True)
        .agg(
            n=("match_exact", "count"),
            pct_exact=("match_exact", lambda x: round(x.astype(float).mean() * 100, 1)),
            pct_sub_major=("match_sub_major", lambda x: round(x.astype(float).mean() * 100, 1)),
            pct_major_group=("match_major_group", lambda x: round(x.astype(float).mean() * 100, 1)),
        )
        .reset_index()
        .sort_values("sim_bin")
    )
    agg.insert(0, "label", label)
    return agg


# ── Load O*NET Task Ratings (importance) ──────────────────────────────────────
# Returns DataFrame with columns: task_id (int), importance (float, 1–5 scale).
# Filters to Scale ID = "IM" (one row per task, no category breakdown).

def load_task_ratings(onet_version: str = "29") -> pd.DataFrame:
    path = ONET_TASK_RATINGS_29 if onet_version == "29" else ONET_TASK_RATINGS_25
    if not path.exists():
        raise FileNotFoundError(f"Task Ratings not found: {path}")
    raw = clean_names(pd.read_excel(path))
    im = raw[raw["scale_id"] == "IM"][["task_id", "data_value"]].copy()
    im["task_id"]   = im["task_id"].astype(int)
    im["importance"] = pd.to_numeric(im["data_value"], errors="coerce")
    return im[["task_id", "importance"]].dropna().reset_index(drop=True)


# ── Load employment totals per ISCO4 group ────────────────────────────────────
# Returns DataFrame with columns: isco_code (int), total_emp (float).
# Sums employment across USA + Norway + Finland + Sweden + Denmark.

def load_employment_totals() -> pd.DataFrame:
    specs = [
        ("USA-24-ISCO4-Sex.csv", "US"),
        ("NOR-24-ISCO4-Sex.csv", "Norway"),
        ("FIN-23-ISCO4-Sex.csv", "Finland"),
        ("SWE-24-ISCO4-Sex.csv", "Sweden"),
        ("DNK-24-ISCO4-Sex.csv", "Denmark"),
    ]
    frames = []
    for fname, col in specs:
        df = pd.read_csv(EMP_STATS_DIR / fname)
        df = df.dropna(subset=["isco_code"])
        df["isco_code"] = pd.to_numeric(df["isco_code"], errors="coerce")
        df = df.dropna(subset=["isco_code"]).copy()
        df["isco_code"] = df["isco_code"].astype(int)
        frames.append(df[["isco_code", col]].rename(columns={col: "emp"}))
    combined = pd.concat(frames).groupby("isco_code")["emp"].sum().reset_index()
    combined.columns = ["isco_code", "total_emp"]
    # Keep only 4-digit ISCO codes (major groups 1–9)
    combined = combined[(combined["isco_code"] >= 1000) & (combined["isco_code"] < 10000)]
    return combined.reset_index(drop=True)


def summarise_by_major_group(dt: pd.DataFrame, label: str = "") -> pd.DataFrame:
    """Match rates broken down by predicted ISCO major group (1–9)."""
    covered = dt[dt["in_crosswalk"] == True].copy()
    agg = (
        covered.groupby("pred_major_group", observed=True)
        .agg(
            n=("match_exact", "count"),
            pct_exact=("match_exact", lambda x: round(x.astype(float).mean() * 100, 1)),
            pct_sub_major=("match_sub_major", lambda x: round(x.astype(float).mean() * 100, 1)),
            pct_major_group=("match_major_group", lambda x: round(x.astype(float).mean() * 100, 1)),
        )
        .reset_index()
        .sort_values("pred_major_group")
    )
    agg.insert(0, "label", label)
    return agg
