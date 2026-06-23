import pandas as pd
from pathlib import Path

BASE = Path(".")

cw = pd.read_csv("output/ONET292_task_to_ISCO_crosswalk.csv")
cw["iscoGroup"] = cw["iscoGroup"].astype(str).str.zfill(4)

all_groups = set(cw["iscoGroup"].unique())
best_groups = set(cw[cw["is_best"] == True]["iscoGroup"].unique())

print(f"All rows: {len(cw)}, unique ISCO groups: {len(all_groups)}")
print(f"is_best rows: {int(cw['is_best'].sum())}, unique ISCO groups: {len(best_groups)}")

# Check columns
print(f"\nColumns: {list(cw.columns)}")

xl = pd.read_excel("data/isco/ISCO-08 EN Structure and definitions.xlsx", sheet_name=0)
unit = xl[xl["Level"] == 4].copy()
unit["isco_code"] = unit["ISCO 08 Code"].astype(str).str.strip().str.zfill(4)
all_isco = set(unit["isco_code"].unique())
print(f"\nTotal ISCO-08 4-digit groups: {len(all_isco)}")

missing = sorted(all_isco - best_groups)
print(f"Missing from is_best output: {len(missing)}")
print("Missing groups:", missing)

# Also check all rows
missing_all = sorted(all_isco - all_groups)
print(f"\nMissing from ALL rows: {len(missing_all)}")
print("Missing from all rows:", missing_all)
