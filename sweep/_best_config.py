import pandas as pd

df = pd.read_csv('../results/summary/sweep_results_metrics_only.csv', low_memory=False)
df = df[df['dataset_name'].str.startswith('r')].copy()

def _sweep_score(row):
    cov      = float(row.get('S2_TASK_FILTER_isco_coverage_share') or 0)
    sim      = float(row.get('S2_TASK_FILTER_mean_similarity_retained') or 0)
    overload = float(row.get('S2_TASK_FILTER_share_tasks_in_overloaded_isco') or 0)
    gini     = float(row.get('S2_TASK_FILTER_gini_tasks_per_isco') or 0)
    return (3*cov + 2*sim - 2*overload - 2*gini) / 9

df['sweep_score'] = df.apply(_sweep_score, axis=1)
best = df.nlargest(1, 'sweep_score').iloc[0]

params = ['w_soc_title', 'w_dwa', 'w_isco', 'w_isco_task', 'w_occ']
metrics = [
    'S2_TASK_FILTER_isco_coverage_share',
    'S2_TASK_FILTER_mean_similarity_retained',
    'S2_TASK_FILTER_share_tasks_in_overloaded_isco',
    'S2_TASK_FILTER_gini_tasks_per_isco',
]

print("Best config:")
for p in params:
    print(f"  {p}: {float(best[p]):.6f}")
print(f"  sweep_score: {best['sweep_score']:.6f}")
print()
print("Metrics:")
for m in metrics:
    print(f"  {m}: {float(best[m]):.6f}")
print()
print("dataset_name:", best['dataset_name'])
