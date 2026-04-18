"""
verify_paper_numbers.py
Computes and prints every key quantity cited in the paper.
Run from the project root: python verify_paper_numbers.py
"""
import re
import pandas as pd
from pathlib import Path

BASE = Path(__file__).parent

def norm_soc(v):
    m = re.search(r'(\d{2})-(\d{4})', str(v).strip())
    return f'{m.group(1)}-{m.group(2)}' if m else None

def norm_isco(v):
    d = ''.join(c for c in str(v) if c.isdigit())
    return d[:4] if len(d) >= 4 else None

def norm_soc10(v):
    d = ''.join(c for c in str(v) if c.isdigit())
    return f'{d[:2]}-{d[2:]}' if len(d) == 6 else None

print("=" * 60)
print("PAPER NUMBER VERIFICATION")
print("=" * 60)

# ── 1. O*NET task counts ──────────────────────────────────────────────────────
tasks29 = pd.read_excel(BASE / 'data/onet/29_2/Task Statements.xlsx')
tasks25 = pd.read_excel(BASE / 'data/onet/25_0/Task Statements.xlsx')
tasks29.columns = tasks29.columns.str.strip()
tasks25.columns = tasks25.columns.str.strip()
n_tasks29 = len(tasks29)
n_tasks25 = len(tasks25)
print(f"\n[1] O*NET 29.2 task statements:  {n_tasks29:,}   (paper says 18,796)")
print(f"[2] O*NET 25.0 task statements:  {n_tasks25:,}")

# ── 2. ESCO occupations ───────────────────────────────────────────────────────
esco = pd.read_csv(BASE / 'data/esco/occupations_en.csv')
n_esco = len(esco)
print(f"\n[3] ESCO occupations in dataset: {n_esco:,}   (paper says ~3,000)")

# ── 3. Production config parameters ──────────────────────────────────────────
def read_yaml_simple(path):
    """Read key: value pairs from YAML without pyyaml."""
    result = {}
    for line in Path(path).read_text(encoding='utf-8').splitlines():
        line = line.split('#')[0].strip()
        if ':' in line:
            k, v = line.split(':', 1)
            k, v = k.strip(), v.strip()
            try:
                result[k] = float(v) if '.' in v else int(v)
            except ValueError:
                result[k] = v
    return result

cfg = read_yaml_simple(BASE / 'config_onet29.yaml')
print(f"\n[4] Production config (config_onet29.yaml):")
print(f"    w_soc_title:  {cfg.get('w_soc_title')}  (SOC title weight in query)")
print(f"    w_isco:       {cfg.get('w_isco')}   (ISCO task weight in target)")
print(f"    w_dwa:        {cfg.get('w_dwa')}   (DWA weight)")
print(f"    min_sim:      {cfg.get('min_sim')}")
print(f"    margin_best:  {cfg.get('margin_best')}")
print(f"    max_links_per_task: {cfg.get('max_links_per_task')}")

# ── 4. ISCO-08 coverage (S5_FINAL stage = coverage-enforced output) ───────────
cw29 = pd.read_csv(BASE / 'output/ONET29_task_to_ISCO_crosswalk.csv')
cw29_best = cw29[cw29['stage'] == 'S5_FINAL'].copy()
cw29_best['iscoGroup'] = cw29_best['iscoGroup'].astype(str).str.zfill(4)
assigned_groups = cw29_best['iscoGroup'].nunique()
has_1113 = '1113' in cw29_best['iscoGroup'].values
print(f"\n[5] ISCO-08 unit groups with >=1 task:  {assigned_groups}  (paper says 435)")
print(f"    ISCO 1113 assigned:  {has_1113}  (paper says NOT assigned)")

# ── 5. Chain crosswalk agreement (production config, ONET29) ─────────────────
tasks29['soc'] = tasks29['O*NET-SOC Code'].apply(norm_soc)
m29 = cw29_best.merge(tasks29[['Task ID','soc']].rename(columns={'Task ID':'task_id'}),
                      on='task_id', how='inner')
m29['isco_major'] = m29['iscoGroup'].str[0]

xw2 = pd.read_csv(BASE / 'data/crosswalks/ONET_(Occupations)_0_updated.csv')
xw2['soc'] = xw2['O*NET Id'].apply(norm_soc)
# Extract 4-digit ISCO code from URI (e.g. ".../isco/C2512"); skip ESCO occupation URIs
xw2['isco'] = (xw2['ESCO or ISCO URI']
    .where(xw2['ESCO or ISCO URI'].str.contains('/isco/', na=False))
    .str.extract(r'/C(\d{4})', expand=False))
xw2 = xw2.dropna(subset=['soc', 'isco'])

xw1 = pd.read_excel(BASE / 'data/crosswalks/ESCO_to_ONET-SOC-8627.xlsx')
xw1.columns = xw1.columns.str.strip()
xw1['soc'] = xw1['SOC19-Code'].apply(norm_soc)
xw1['isco'] = xw1['ESCO-Code'].apply(
    lambda v: norm_isco(str(v).split('/')[-1].lstrip('C')) if isinstance(v, str) else None)
xw1 = xw1.dropna(subset=['soc','isco'])

soc18 = pd.concat([xw1[['soc','isco']], xw2[['soc','isco']]])
soc18_union = (soc18.groupby('soc')['isco']
               .apply(set).reset_index()
               .rename(columns={'isco': 'isco_set'}))

m29 = m29.merge(soc18_union, on='soc', how='left')
m29_in = m29[m29['isco_set'].apply(lambda x: isinstance(x, set) and len(x) > 0)]
exact29 = m29_in.apply(lambda r: r['iscoGroup'] in r['isco_set'], axis=1).mean() * 100
major29 = m29_in.apply(
    lambda r: any(r['isco_major'] == i[0] for i in r['isco_set']), axis=1).mean() * 100

print(f"\n[6] Chain crosswalk agreement — O*NET 29.2 (lenient union, n={len(m29_in):,}):")
print(f"    Exact (4-digit):       {exact29:.1f}%  (paper says 84.6%)")
print(f"    Major-group (1-digit): {major29:.1f}%  (paper says 94.7%)")

# ── 6. Cross-release stability ────────────────────────────────────────────────
stab_path = BASE / 'validation/results/stability_cross_dataset_overall.csv'
if stab_path.exists():
    stab = pd.read_csv(stab_path)
    row = stab[stab['label'] == 'ONET29 vs ONET25']
    if not row.empty:
        n_shared = int(row['n'].values[0])
        stab_pct = float(row['exact_agreement_pct'].values[0])
        print(f"\n[7] Cross-release stability (shared tasks, ONET29 vs ONET25):")
        print(f"    Shared tasks:      {n_shared:,}   (paper says 14,174)")
        print(f"    Exact agreement:   {stab_pct:.1f}%  (paper says 100%)")
else:
    print(f"\n[7] Cross-release stability: {stab_path.name} not found — skipped")

print("\n" + "=" * 60)
