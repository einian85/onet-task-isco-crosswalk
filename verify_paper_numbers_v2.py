"""
verify_paper_numbers_v2.py
Computes every key quantity cited in the paper and supplementary.
Run from the project root (conda env onet-isco-nlp):
    python verify_paper_numbers_v2.py
"""
import re
import pandas as pd
from pathlib import Path

BASE = Path(__file__).parent

def read_yaml_simple(path):
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

print("=" * 70)
print("PAPER NUMBER VERIFICATION v2")
print("=" * 70)

# ── 1. O*NET task counts ─────────────────────────────────────────────────────
tasks29 = pd.read_excel(BASE / 'data/onet/29_2/Task Statements.xlsx')
tasks25 = pd.read_excel(BASE / 'data/onet/25_0/Task Statements.xlsx')
tasks29.columns = tasks29.columns.str.strip()
tasks25.columns = tasks25.columns.str.strip()
n_tasks29 = len(tasks29)
n_tasks25 = len(tasks25)
soc29 = tasks29['O*NET-SOC Code'].nunique()
soc25 = tasks25['O*NET-SOC Code'].nunique()
print(f"\n[1] O*NET 29.2 task statements:  {n_tasks29:,}")
print(f"    O*NET 29.2 unique SOC codes:  {soc29:,}")
print(f"[2] O*NET 25.0 task statements:  {n_tasks25:,}")
print(f"    O*NET 25.0 unique SOC codes:  {soc25:,}")

# ── 2. ESCO occupations ──────────────────────────────────────────────────────
esco = pd.read_csv(BASE / 'data/esco/occupations_en.csv')
n_esco = len(esco)
print(f"\n[3] ESCO occupations:  {n_esco:,}")

# ── 3. DWA labels ────────────────────────────────────────────────────────────
try:
    dwa29 = pd.read_excel(BASE / 'data/onet/29_2/Tasks to DWAs.xlsx')
    dwa25 = pd.read_excel(BASE / 'data/onet/25_0/Tasks to DWAs.xlsx')
    n_dwa29 = dwa29['DWA ID'].nunique() if 'DWA ID' in dwa29.columns else dwa29.iloc[:,1].nunique()
    n_dwa25 = dwa25['DWA ID'].nunique() if 'DWA ID' in dwa25.columns else dwa25.iloc[:,1].nunique()
    print(f"\n[4] DWA unique labels — O*NET 29.2: {n_dwa29:,}")
    print(f"    DWA unique labels — O*NET 25.0: {n_dwa25:,}")
except Exception as e:
    print(f"\n[4] DWA count: error — {e}")

# ── 4. O*NET version count ───────────────────────────────────────────────────
configs_dir = BASE / 'configs'
onet_configs = sorted(configs_dir.glob('config_onet*.yaml'))
print(f"\n[5] O*NET version configs found:  {len(onet_configs)}")
if onet_configs:
    def ver_tuple(p):
        m = re.search(r'config_onet(\d+)\.yaml', p.name)
        digits = m.group(1) if m else ''
        if len(digits) == 2: return (int(digits[0]), int(digits[1]))
        if len(digits) == 3: return (int(digits[:2]), int(digits[2]))
        if len(digits) == 4: return (int(digits[:2]), int(digits[2:]))
        return (0, 0)
    versions = sorted([ver_tuple(p) for p in onet_configs])
    first = f"{versions[0][0]}.{versions[0][1]}"
    last  = f"{versions[-1][0]}.{versions[-1][1]}"
    print(f"    Range: v{first} to v{last}")

# ── 5. Production config parameters ─────────────────────────────────────────
cfg_path = BASE / 'configs/config_onet292.yaml'
cfg = read_yaml_simple(cfg_path)
print(f"\n[6] Production config — configs/config_onet292.yaml:")
for k in ['w_soc_title', 'w_dwa', 'w_isco', 'w_isco_task', 'w_occ',
          'min_sim', 'margin_best', 'max_links_per_task']:
    print(f"    {k}: {cfg.get(k)}")

# ── 6. ISCO-08 coverage from production output ───────────────────────────────
cw29_path = BASE / 'output/ONET292_task_to_ISCO_crosswalk.csv'
cw29 = pd.read_csv(cw29_path)
cw29['iscoGroup'] = cw29['iscoGroup'].astype(str).str.zfill(4)
best29 = cw29[cw29['is_best'] == True].copy()
n_best29 = len(best29)
n_isco_groups = best29['iscoGroup'].nunique()
has_1113 = '1113' in best29['iscoGroup'].values
print(f"\n[7] ONET292 output — tasks with is_best=True: {n_best29:,}")
print(f"    ISCO-08 unit groups covered: {n_isco_groups}")
print(f"    ISCO 1113 assigned: {has_1113}")

# ── 7. Validation numbers from pre-computed chain eval ───────────────────────
eval292 = pd.read_csv(BASE / 'validation/results/chain_eval_onet292_overall.csv')
print(f"\n[8] Chain crosswalk agreement — ONET292 production config:")
for _, row in eval292.iterrows():
    print(f"    {row['label']}: "
          f"cov={row['pct_in_crosswalk']:.1f}%, "
          f"exact={row['pct_exact']:.1f}%, "
          f"major={row['pct_major_group']:.1f}%")

eval250 = pd.read_csv(BASE / 'validation/results/chain_eval_onet250_overall.csv')
print(f"\n[9] Chain crosswalk agreement — ONET250 production config:")
for _, row in eval250.iterrows():
    print(f"    {row['label']}: "
          f"cov={row['pct_in_crosswalk']:.1f}%, "
          f"exact={row['pct_exact']:.1f}%, "
          f"major={row['pct_major_group']:.1f}%")

# ── 8. Cross-release stability (ONET292 vs ONET250) ──────────────────────────
cw25_path = BASE / 'output/ONET250_task_to_ISCO_crosswalk.csv'
if cw25_path.exists():
    cw25 = pd.read_csv(cw25_path)
    cw25['iscoGroup'] = cw25['iscoGroup'].astype(str).str.zfill(4)
    best25 = cw25[cw25['is_best'] == True].copy()
    # match on task_id
    shared = best29[['task_id','iscoGroup']].merge(
        best25[['task_id','iscoGroup']].rename(columns={'iscoGroup':'iscoGroup25'}),
        on='task_id', how='inner')
    n_shared = len(shared)
    pct_agree = (shared['iscoGroup'] == shared['iscoGroup25']).mean() * 100
    print(f"\n[10] Cross-release stability — shared tasks ONET292 vs ONET250:")
    print(f"     Shared task IDs: {n_shared:,}")
    print(f"     Exact ISCO agreement: {pct_agree:.1f}%")
else:
    print(f"\n[10] ONET250 output not found at {cw25_path}")

# ── 9. Supp appendix C: human eval numbers ───────────────────────────────────
heval = pd.read_csv(BASE / 'validation/results/human_eval_onet29_summary.csv')
print(f"\n[11] Human eval (Appendix C):")
for _, row in heval.iterrows():
    print(f"     {row['label']}: n={row['n_judged']}, "
          f"exact={row['pct_exact']:.1f}%, "
          f"sub-major={row['pct_sub_major']:.1f}%, "
          f"major={row['pct_major_group']:.1f}%, "
          f"mean_sim={row['mean_similarity']:.3f}")

# ── 10. Supp appendix D: candidate sweep selected config ─────────────────────
cand = pd.read_csv(BASE / 'validation/results/onet29_candidate_chain_lenient_union.csv')
print(f"\n[12] Candidate sweep — selected config (lenient union A4):")
selected = cand[cand['candidate_description'].str.contains('Selected', na=False)]
if not selected.empty:
    row = selected.iloc[0]
    print(f"     Label: {row['candidate_label']}")
    print(f"     Desc: {row['candidate_description']}")
    print(f"     n_tasks={row['chain_n_tasks']:,}, "
          f"exact={row['chain_pct_exact']:.1f}%, "
          f"major={row['chain_pct_major_group']:.1f}%")

print("\n" + "=" * 70)
print("SUMMARY OF KEY PAPER CLAIMS vs ACTUAL VALUES")
print("=" * 70)
lenient_292 = eval292[eval292['label'].str.contains('union|A4', na=False)]
if not lenient_292.empty:
    row = lenient_292.iloc[0]
    print(f"\nValidation (ONET292, lenient union):")
    print(f"  Exact match:       {row['pct_exact']:.1f}%   [paper says 84.6%]")
    print(f"  Major group:       {row['pct_major_group']:.1f}%   [paper says 94.7%]")

print(f"\nParameters (from config_onet292.yaml):")
print(f"  w_soc_title: {cfg.get('w_soc_title')}  [paper says 0.25]")
print(f"  w_dwa:       {cfg.get('w_dwa')}   [paper says 0.125]")
print(f"  w_isco:      {cfg.get('w_isco')}   [paper says 0.5]")
print(f"  w_isco_task: {cfg.get('w_isco_task')}   [paper says 0.8125]")
print(f"  w_occ:       {cfg.get('w_occ')}   [paper says 0.125]")

print(f"\nO*NET versions covered: {len(onet_configs)}  [paper says 'two versions']")
