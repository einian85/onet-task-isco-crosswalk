"""Direct crosswalk agreement between embedding models (task-level ISCO assignments)."""
import pandas as pd

def load(path):
    df = pd.read_csv(path)
    if 'iscoGroup' in df.columns:
        df = df.rename(columns={'iscoGroup': 'isco'})
    df['task_id'] = pd.to_numeric(df['task_id'], errors='coerce').astype('Int64')
    df['isco']    = pd.to_numeric(df['isco'],    errors='coerce').astype('Int64')
    if 'is_best' in df.columns:
        df = df[df['is_best'] == True]
    return df[['task_id', 'isco']].dropna()

mpnet = load('output/ONET292_task_to_ISCO_crosswalk.csv')
bge   = load('output/ONET292_bge_task_to_ISCO_crosswalk.csv')
gte   = load('output/ONET292_gte_task_to_ISCO_crosswalk.csv')

def compare(a, b, label):
    m = a.merge(b, on='task_id', suffixes=('_a', '_b'))
    exact    = (m['isco_a'] == m['isco_b']).mean() * 100
    submajor = ((m['isco_a'] // 100) == (m['isco_b'] // 100)).mean() * 100
    major    = ((m['isco_a'] // 1000) == (m['isco_b'] // 1000)).mean() * 100
    print(f'{label:<22}  exact={exact:.1f}%  sub-major={submajor:.1f}%  major={major:.1f}%  (n={len(m):,})')

compare(mpnet, bge, 'MPNet vs BGE')
compare(mpnet, gte, 'MPNet vs GTE')
compare(bge,   gte, 'BGE   vs GTE')
