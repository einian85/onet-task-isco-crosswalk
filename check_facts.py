"""
Verify facts #15, #50b, and #104 from the fact audit table.
"""
import sys
import pandas as pd
sys.path.insert(0, 'validation')
from shared import load_soc18_crosswalks, load_onet_tasks, evaluate_match, summarise_match

# ── Fact #15: O*NET 25.0 task count ──────────────────────────────────────────
df250 = pd.read_csv('output/ONET250_task_to_ISCO_crosswalk.csv')
print(f"Fact #15 — ONET 25.0 task count: {df250['task_id'].nunique()}")

# ── Fact #50b: DWA count ──────────────────────────────────────────────────────
dwa = pd.read_excel('data/onet/29_2/Tasks to DWAs.xlsx')
print(f"Fact #50b — Unique DWA titles: {dwa['DWA Title'].nunique()}")

# ── Fact #104: chain-crosswalk A4 on annotation subset (108 tasks) ───────────
print("\nFact #104 — chain-crosswalk A4 agreement on annotation subset:")

# Load annotation workbook — get the 108 task IDs
ann = pd.read_excel('validation/results/annotation_workbook_onet29.xlsx')
ann_task_ids = pd.to_numeric(ann['task_id'], errors='coerce').dropna().astype('Int64')
print(f"  Annotation task count: {len(ann_task_ids)}")

# Load production crosswalk and filter to annotation subset
xw = pd.read_csv('output/ONET292_task_to_ISCO_crosswalk.csv')
if 'is_best' in xw.columns:
    xw = xw[xw['is_best'] == True].copy()
xw['task_id'] = pd.to_numeric(xw['task_id'], errors='coerce').astype('Int64')
xw['isco_pred'] = pd.to_numeric(
    xw['iscoGroup'] if 'iscoGroup' in xw.columns else xw['isco_pred'],
    errors='coerce'
).astype('Int64')
xw_subset = xw[xw['task_id'].isin(ann_task_ids)].copy()
print(f"  Tasks matched in crosswalk: {xw_subset['task_id'].nunique()}")

# Build A4 benchmark (lenient union SOC 2018)
xw18 = load_soc18_crosswalks()
xw_a4 = (
    pd.concat([
        xw18['xw18_1'][['soc_code18', 'isco_code']],
        xw18['xw18_2'][['soc_code18', 'isco_code']],
    ])
    .drop_duplicates()
    .reset_index(drop=True)
)

# Load O*NET 29.2 tasks for SOC codes
df_tasks = load_onet_tasks('29.2')
df_tasks['task_id'] = pd.to_numeric(df_tasks['task_id'], errors='coerce').astype('Int64')
df_tasks_subset = df_tasks[df_tasks['task_id'].isin(ann_task_ids)].copy()
print(f"  Tasks in O*NET 29.2 task list: {df_tasks_subset['task_id'].nunique()}")

# Evaluate
ev = evaluate_match(xw_subset, df_tasks_subset, xw_a4, 'soc_code18')
summ = summarise_match(ev, 'A4_annotation_subset').iloc[0]
print(f"\n  Columns: {list(summ.index)}")
print(f"  Summary: {summ.to_dict()}")
# find pct_exact column
exact_col = [c for c in summ.index if 'exact' in c.lower()][0]
print(f"\n  Exact agreement: {summ[exact_col]:.1f}%")
print(f"  Paper states 68.0% — {'CONFIRMED' if abs(float(summ[exact_col]) - 68.0) < 0.5 else 'DIFFERS — UPDATE NEEDED'}")
