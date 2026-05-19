import pandas as pd

df = pd.read_csv('../results/summary/sweep_results_metrics_only.csv', low_memory=False)
df = df[df['dataset_name'].str.startswith('r')].copy()

vals = sorted(df['w_isco'].dropna().round(6).unique())
print('All w_isco values explored:', vals)

def _sweep_score(row):
    cov      = float(row.get('S5_FINAL_isco_coverage_share') or 0)
    sim      = float(row.get('S5_FINAL_mean_similarity_retained') or 0)
    overload = float(row.get('S5_FINAL_share_tasks_in_overloaded_isco') or 0)
    gini     = float(row.get('S5_FINAL_gini_tasks_per_isco') or 0)
    return (3*cov + 2*sim - 2*overload - 2*gini) / 9

df['sweep_score'] = df.apply(_sweep_score, axis=1)

print()
print('Top 10 configs by sweep_score:')
top = df.nlargest(10, 'sweep_score')[['w_isco','w_isco_task','w_occ','w_soc_title','w_dwa','sweep_score']]
print(top.sort_values('sweep_score', ascending=False).to_string(index=False))

print()
print('Mean sweep_score by w_isco (marginalised over all other params):')
by_isco = df.groupby('w_isco')['sweep_score'].agg(['mean','max','count']).round(6)
print(by_isco.to_string())
