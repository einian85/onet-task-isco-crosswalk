"""
verify_paper_numbers_v2.py
Computes every key quantity cited in the paper and supplementary.
Run from the project root (conda env onet-isco-nlp):
    python verify_paper_numbers_v2.py
"""
import sys
import re
import pandas as pd
from pathlib import Path

sys.stdout.reconfigure(encoding="utf-8")

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
# Anchored at the end (\.yaml$) so this only matches plain per-release configs
# like config_onet292.yaml, not config_onet292_abl_no_dwa.yaml / _bge.yaml / _gte.yaml -
# an unanchored version of this regex previously matched those too (m stayed None,
# silently producing a bogus "v0.0" entry per file and inflating the count by 6).
configs_dir = BASE / 'configs'
_ver_re = re.compile(r'config_onet(\d+)\.yaml$')
onet_configs = sorted(p for p in configs_dir.glob('config_onet*.yaml') if _ver_re.search(p.name))
print(f"\n[5] O*NET version configs found:  {len(onet_configs)}")
if onet_configs:
    def ver_tuple(p):
        digits = _ver_re.search(p.name).group(1)
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
print("(No hardcoded 'paper says' comparisons below - the ones previously here were")
print(" from an old draft of the paper with a since-abandoned config and are not a")
print(" meaningful check against the current submission. Compare the numbers below")
print(" directly against the current paper_iaos.tex by hand.)")
lenient_292 = eval292[eval292['label'].str.contains('union|A4', na=False)]
if not lenient_292.empty:
    row = lenient_292.iloc[0]
    print(f"\nValidation (ONET292, lenient union):")
    print(f"  Exact match:       {row['pct_exact']:.1f}%")
    print(f"  Major group:       {row['pct_major_group']:.1f}%")

print(f"\nParameters (from config_onet292.yaml):")
print(f"  w_soc_title: {cfg.get('w_soc_title')}")
print(f"  w_dwa:       {cfg.get('w_dwa')}")
print(f"  w_isco:      {cfg.get('w_isco')}")
print(f"  w_isco_task: {cfg.get('w_isco_task')}")
print(f"  w_occ:       {cfg.get('w_occ')}")

print(f"\nO*NET versions covered: {len(onet_configs)}")

# ── 11. Multi-release aggregate ranges (SOC2018 / SOC2010 eras) ─────────────
# These are the ranges cited in the abstract/introduction/conclusion ("across
# all N releases, tasks range from X to Y..."); added 2026-09-23 because they
# previously existed only as one-off calculations, not as reusable script
# output -- everything cited in the paper should be reproducible from this repo.
SOC2018_VERSIONS = ['251','252','253','260','261','262','263','270','271','272',
                     '273','280','281','282','283','290','291','292','293','300',
                     '301','302','303']
SOC2010_VERSIONS = ['151','160','170','180','181','190','200','201','202','203',
                     '210','211','212','213','220','221','222','223','230','231',
                     '232','233','240','241','242','243','250']

def era_ranges(versions, label):
    n_tasks, n_groups, sims = [], [], []
    for v in versions:
        f = BASE / 'output' / f'ONET{v}_task_to_ISCO_crosswalk.csv'
        if not f.exists():
            continue
        df = pd.read_csv(f)
        best = df[df['is_best'] == True]
        n_tasks.append(len(best))
        n_groups.append(best['iscoGroup'].nunique())
        sims.append(best['similarity'].mean())
    return {
        'era': label, 'n_releases': len(n_tasks),
        'tasks_min': min(n_tasks), 'tasks_max': max(n_tasks),
        'isco_groups_min': min(n_groups), 'isco_groups_max': max(n_groups),
        'mean_sim_min': round(min(sims), 3), 'mean_sim_max': round(max(sims), 3),
    }

def era_chain_ranges(versions, label):
    exacts, majors = [], []
    for v in versions:
        f = BASE / 'validation' / 'results' / f'chain_eval_onet{v}_overall.csv'
        if not f.exists():
            continue
        df = pd.read_csv(f)
        row = df[df['label'].str.contains('Lenient union', na=False)]
        if row.empty:
            continue
        exacts.append(row['pct_exact'].values[0])
        majors.append(row['pct_major_group'].values[0])
    return {
        'era': label, 'n_releases': len(exacts),
        'exact_min': min(exacts), 'exact_max': max(exacts),
        'major_min': min(majors), 'major_max': max(majors),
    }

range_rows = [era_ranges(SOC2018_VERSIONS, 'SOC2018'), era_ranges(SOC2010_VERSIONS, 'SOC2010')]
chain_range_rows = [era_chain_ranges(SOC2018_VERSIONS, 'SOC2018'), era_chain_ranges(SOC2010_VERSIONS, 'SOC2010')]

print(f"\n[13] Multi-release aggregate ranges (for abstract/introduction/conclusion):")
for r in range_rows:
    print(f"     {r['era']} (n={r['n_releases']} releases): "
          f"tasks {r['tasks_min']:,}-{r['tasks_max']:,}, "
          f"ISCO groups {r['isco_groups_min']}-{r['isco_groups_max']}, "
          f"mean sim {r['mean_sim_min']}-{r['mean_sim_max']}")
for r in chain_range_rows:
    print(f"     {r['era']} chain-exact (A4 lenient union): {r['exact_min']}-{r['exact_max']}%, "
          f"major-group: {r['major_min']}-{r['major_max']}%")

out_dir = BASE / 'results' / 'summary'
out_dir.mkdir(parents=True, exist_ok=True)
pd.DataFrame(range_rows).to_csv(out_dir / 'paper_era_ranges.csv', index=False)
pd.DataFrame(chain_range_rows).to_csv(out_dir / 'paper_era_chain_ranges.csv', index=False)
print(f"     Written: results/summary/paper_era_ranges.csv, results/summary/paper_era_chain_ranges.csv")

# ── 12. Wilson 95% CIs for the O*NET 29.2 headline figures ──────────────────
import math
def wilson_ci(pct, n, z=1.96):
    p = pct / 100
    denom = 1 + z**2 / n
    center = p + z**2 / (2 * n)
    margin = z * math.sqrt(p * (1 - p) / n + z**2 / (4 * n**2))
    return round((center - margin) / denom * 100, 1), round((center + margin) / denom * 100, 1)

wilson_rows = []
for _, row in eval292.iterrows():
    n = row['n_in_crosswalk']
    for metric in ['pct_exact', 'pct_sub_major', 'pct_major_group']:
        lo, hi = wilson_ci(row[metric], n)
        wilson_rows.append({'release': 'ONET292', 'scenario': row['label'],
                             'metric': metric, 'pct': row[metric], 'n': n,
                             'ci_lo': lo, 'ci_hi': hi})

print(f"\n[14] Wilson 95% CIs (O*NET 29.2):")
for r in wilson_rows:
    print(f"     {r['scenario']} {r['metric']}: {r['pct']}% [{r['ci_lo']}%, {r['ci_hi']}%] (n={r['n']:,})")

pd.DataFrame(wilson_rows).to_csv(out_dir / 'paper_wilson_cis.csv', index=False)
print(f"     Written: results/summary/paper_wilson_cis.csv")

# ── 13. Effective query-side / target-side blend percentages ────────────────
# The paper explains the selected weights in terms of their sequential-blend
# effective shares (Appendix A "Selected configuration"); computed here once,
# reusably, rather than by hand in the paper-writing process.
w_dwa, w_soc = cfg['w_dwa'], cfg['w_soc_title']
w_isco, w_isco_task, w_occ = cfg['w_isco'], cfg['w_isco_task'], cfg['w_occ']

query_shares = {
    'dwa_share': (1 - w_soc) * w_dwa,
    'task_text_share': (1 - w_soc) * (1 - w_dwa),
    'soc_title_share': w_soc,
}
target_shares = {
    'isco_task_share': w_isco * w_isco_task,
    'isco_info_share': w_isco * (1 - w_isco_task),
    'esco_occ_share': (1 - w_isco) * w_occ,
    'esco_skill_share': (1 - w_isco) * (1 - w_occ),
}
print(f"\n[15] Effective query-side shares (production config):")
for k, v in query_shares.items():
    print(f"     {k}: {v*100:.1f}%")
print(f"     sum check: {sum(query_shares.values())*100:.1f}%")
print(f"[15b] Effective target-side shares (production config):")
for k, v in target_shares.items():
    print(f"     {k}: {v*100:.1f}%")
print(f"     sum check: {sum(target_shares.values())*100:.1f}%")

pd.DataFrame([{**query_shares, **target_shares}]).to_csv(out_dir / 'paper_effective_weight_shares.csv', index=False)
print(f"     Written: results/summary/paper_effective_weight_shares.csv")

# ── 14. Overloaded-group SOC-major-group concentration ───────────────────────
# The paper claims overloaded ISCO groups are "structural, not a pipeline
# problem" because each draws most of its tasks from one dominant SOC major
# group. This claim previously had no script behind it (a hand-check from an
# earlier session, per CONFIG_SELECTION_LOG.md) and the set of overloaded
# groups changed under the corrected config (results/publication/tables/
# table_overload_examples.tex now lists 8 groups for O*NET 29.2, not 2) -- so
# it needs recomputing against the current output, not carried over by assumption.
sys.path.insert(0, str(BASE / 'validation'))
from shared import load_onet_tasks  # noqa: E402

onet_tasks = load_onet_tasks("29.2")[['task_id', 'soc_code']]
onet_tasks['soc_major'] = onet_tasks['soc_code'].str.slice(0, 2)
best29_soc = best29.merge(onet_tasks, on='task_id', how='left')

counts_by_group = best29_soc.groupby('iscoGroup').size()
threshold = max(200, counts_by_group.quantile(0.95))
overloaded_groups = counts_by_group[counts_by_group > threshold].sort_values(ascending=False)

print(f"\n[16] Overloaded-group SOC-major-group concentration (O*NET 29.2):")
print(f"     Threshold T = max(200, Q95) = {threshold:.1f}; {len(overloaded_groups)} groups over threshold")
concentration_rows = []
for isco_group, n_tasks_grp in overloaded_groups.items():
    sub = best29_soc[best29_soc['iscoGroup'] == isco_group]
    major_counts = sub['soc_major'].value_counts()
    top_major = major_counts.index[0]
    top_share = major_counts.iloc[0] / len(sub) * 100
    concentration_rows.append({'isco_group': isco_group, 'n_tasks': int(n_tasks_grp),
                                'dominant_soc_major': top_major, 'dominant_soc_major_share_pct': round(top_share, 1)})
    print(f"     ISCO {isco_group}: {n_tasks_grp} tasks, {top_share:.1f}% from SOC major group {top_major}")

pd.DataFrame(concentration_rows).to_csv(out_dir / 'paper_overload_concentration.csv', index=False)
print(f"     Written: results/summary/paper_overload_concentration.csv")
