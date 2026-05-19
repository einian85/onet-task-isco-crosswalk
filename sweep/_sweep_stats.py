import pandas as pd

df = pd.read_csv('../results/summary/sweep_results_metrics_only.csv', low_memory=False)
df = df[df['dataset_name'].str.startswith('r')].copy()

def _sweep_score(row):
    cov      = float(row.get('S5_FINAL_isco_coverage_share') or 0)
    sim      = float(row.get('S5_FINAL_mean_similarity_retained') or 0)
    overload = float(row.get('S5_FINAL_share_tasks_in_overloaded_isco') or 0)
    gini     = float(row.get('S5_FINAL_gini_tasks_per_isco') or 0)
    return (3*cov + 2*sim - 2*overload - 2*gini) / 9

df['sweep_score'] = df.apply(_sweep_score, axis=1)
df['round'] = df['dataset_name'].str.extract(r'^r(\d+)_').astype(int)

print(f"Total variants evaluated: {len(df)}")
print(f"Rounds run: {sorted(df['round'].unique())}")
print()
for rnum, grp in df.groupby('round'):
    print(f"  Round {rnum}: {len(grp)} configs,  best score={grp['sweep_score'].max():.6f}")

print()
best = df.nlargest(1, 'sweep_score').iloc[0]
print(f"Best config (round {int(best['round'])}):")
for p in ['w_soc_title','w_dwa','w_isco','w_isco_task','w_occ']:
    print(f"  {p} = {float(best[p]):.4f}")
print(f"  sweep_score = {best['sweep_score']:.6f}")
print(f"  coverage    = {float(best['S5_FINAL_isco_coverage_share']):.4f}")
print(f"  similarity  = {float(best['S5_FINAL_mean_similarity_retained']):.4f}")
print(f"  overload    = {float(best['S5_FINAL_share_tasks_in_overloaded_isco']):.4f}")
print(f"  gini        = {float(best['S5_FINAL_gini_tasks_per_isco']):.4f}")
print(f"  dataset_name = {best['dataset_name']}")
