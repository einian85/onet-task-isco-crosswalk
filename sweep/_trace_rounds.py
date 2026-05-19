"""
Trace what w_isco grid values appeared in each sweep round,
and whether w_isco=0.5 was at boundary in each round.
"""
import pandas as pd, re

df = pd.read_csv('../results/summary/sweep_results_metrics_only.csv', low_memory=False)
df = df[df['dataset_name'].str.startswith('r')].copy()

def _sweep_score(row):
    cov      = float(row.get('S5_FINAL_isco_coverage_share') or 0)
    sim      = float(row.get('S5_FINAL_mean_similarity_retained') or 0)
    overload = float(row.get('S5_FINAL_share_tasks_in_overloaded_isco') or 0)
    gini     = float(row.get('S5_FINAL_gini_tasks_per_isco') or 0)
    return (3*cov + 2*sim - 2*overload - 2*gini) / 9

df['sweep_score'] = df.apply(_sweep_score, axis=1)

# Extract round number from dataset_name (e.g. r1_, r2_, ...)
df['round'] = df['dataset_name'].str.extract(r'^r(\d+)_').astype(int)

print("w_isco grid per round (unique values tested that round):")
print(f"{'Round':>6}  {'w_isco values':50}  {'best_w_isco':>12}  {'at_boundary':>12}")
for rnum, grp in df.groupby('round'):
    vals = sorted(grp['w_isco'].round(6).unique())
    best_row = grp.loc[grp['sweep_score'].idxmax()]
    best_w = float(best_row['w_isco'])
    at_bnd = abs(best_w - min(vals)) < 1e-9 or abs(best_w - max(vals)) < 1e-9
    print(f"  {rnum:>4}  {str(vals):50}  {best_w:>12.4f}  {'YES' if at_bnd else 'no':>12}")
