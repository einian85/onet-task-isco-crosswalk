"""
Compare metric options for XW18.1 (many-to-many, flat scores).

For each SOC code the pipeline assigns one top-1 ISCO.
The reference maps each SOC to 1..40 acceptable ISCOs.

Options:
  A. top1 vs top1           -- current metric (strict, arbitrary tie-break)
  B. in-set rate            -- is pipeline's top-1 anywhere in reference set?
  C. pair recall            -- what share of ref (soc,isco) pairs does pipeline imply?
  D. unique-SOC top1        -- option A restricted to SOCs with only 1 ref ISCO
  E. weighted top-1 by set size  -- same as B but weight = 1/|ref set| per SOC
"""
import re, sys
from pathlib import Path
import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from validation.shared import load_pipeline

ROOT = Path(__file__).resolve().parent.parent

def normalize_isco(v):
    try:
        digits = re.sub(r'[^0-9]', '', str(v))
        if len(digits) >= 4:
            return int(digits[:4])
    except: pass
    return None

def normalize_soc(v):
    try:
        digits = re.sub(r'[^0-9]', '', str(v))
        if len(digits) >= 6:
            return digits[:2] + '-' + digits[2:6]
    except: pass
    return None

# ── Load pipeline top-1 per SOC ──────────────────────────────────────────────
pred = load_pipeline(ROOT / "output" / "ONET29_task_to_ISCO_crosswalk.csv")
pred = pred.merge(
    pd.read_excel(ROOT / "data/onet/29_2/Task Statements.xlsx")[["Task ID","O*NET-SOC Code"]]
      .rename(columns={"Task ID":"task_id","O*NET-SOC Code":"soc_raw"}),
    on="task_id", how="left"
)
pred["soc_code"] = pred["soc_raw"].map(normalize_soc)
pred = pred.dropna(subset=["soc_code","isco_pred"])
pred["isco_code"] = pred["isco_pred"].apply(lambda x: int(x) if pd.notna(x) else None)
pred = pred.dropna(subset=["isco_code"])

# top-1 per SOC = ISCO receiving most tasks
top1_imp = (
    pred.groupby(["soc_code","isco_code"])
        .size().reset_index(name="n")
        .sort_values(["soc_code","n"], ascending=[True,False])
        .drop_duplicates("soc_code")
        .rename(columns={"isco_code":"isco_imp"})
)

# ── Load XW18.1 ───────────────────────────────────────────────────────────────
xw = pd.read_excel(ROOT / "data/crosswalks/ESCO_to_ONET-SOC.xlsx", sheet_name="Crosswalk")
xw = xw.rename(columns={"SOC19-Code":"soc_raw","ESCO-Code":"isco_raw"})
xw["soc_code"]  = xw["soc_raw"].map(normalize_soc)
xw["isco_code"] = xw["isco_raw"].map(normalize_isco)
xw = xw[["soc_code","isco_code"]].dropna().drop_duplicates()

ref_sets = xw.groupby("soc_code")["isco_code"].apply(set).reset_index()
ref_sets.columns = ["soc_code","isco_ref_set"]
ref_sets["ref_size"] = ref_sets["isco_ref_set"].apply(len)

# ── Reference top-1 (current method) ─────────────────────────────────────────
ref_top1 = (
    xw.sort_values(["soc_code","isco_code"])   # alphabetical tie-break
      .drop_duplicates("soc_code")
      .rename(columns={"isco_code":"isco_ref_top1"})
)

# ── Merge ─────────────────────────────────────────────────────────────────────
m = top1_imp.merge(ref_sets, on="soc_code").merge(ref_top1[["soc_code","isco_ref_top1"]], on="soc_code")
print(f"Shared SOC codes: {len(m)}")
print()

# A. strict top1 vs top1
A = (m["isco_imp"] == m["isco_ref_top1"]).mean()
print(f"A. Strict top-1 vs top-1 (current):       {A:.1%}  [{len(m)} SOC codes]")

# B. in-set rate: pipeline top-1 anywhere in reference set
m["in_set"] = m.apply(lambda r: r["isco_imp"] in r["isco_ref_set"], axis=1)
B = m["in_set"].mean()
print(f"B. In-set rate (top-1 ∈ ref set):          {B:.1%}  [{len(m)} SOC codes]")

# C. pair recall (already in table: 46.4%)
imp_pairs = set(zip(pred["soc_code"], pred["isco_code"]))
ref_pairs = set(zip(xw["soc_code"], xw["isco_code"]))
C = len(imp_pairs & ref_pairs) / len(ref_pairs)
print(f"C. Pair recall (imp pairs ∩ ref / ref):    {C:.1%}  [{len(ref_pairs)} ref pairs]")

# D. top-1 agreement for unique-reference SOCs only
unique = m[m["ref_size"] == 1]
D = (unique["isco_imp"] == unique["isco_ref_top1"]).mean()
print(f"D. Top-1 agreement (unique ref only):      {D:.1%}  [{len(unique)} SOC codes]")

# E. weighted in-set (weight = 1/|ref set|) — penalises large sets
m["weighted"] = m.apply(lambda r: (1/r["ref_size"]) if r["in_set"] else 0, axis=1)
E = m["weighted"].mean()
print(f"E. Weighted in-set (1/|ref set|):          {E:.1%}  [{len(m)} SOC codes]")

print()
print("Distribution of reference set sizes:")
print(m["ref_size"].value_counts().sort_index().head(10).to_string())
