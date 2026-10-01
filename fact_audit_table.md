# Fact Audit Table — "Mapping O*NET Tasks to ISCO Occupations using Text Similarity"

Audit of the revised manuscript resubmitted on 30 September 2026 (`paper_iaos.tex`, main text and Appendices A–G). It lists every stated fact in document order, with where it can be verified and the result of checking it against this repository on 1 October 2026 (commit `74c6dab` plus this file). The audit of earlier versions is in the git history of this file.

Check column: **ok** = reproduced from the source named; **ERROR** = the source gives a different value; **not supported** / **overstated** / **inconsistent** = the paper's wording goes beyond or contradicts what the sources show; **not checkable** = depends on something outside this repository. The *My Note* column is left for the author.

---

## Issues found

Errors (the paper states something the data contradict):

1. **ISCO-08 task descriptions cover 427, not 435, of the 436 unit groups (facts 20, 62).** The nine without a task list in `ISCO-08 EN Structure and definitions.xlsx` are six "not elsewhere classified" groups (1439, 3139, 3435, 5249, 7319, 8189) and the three armed-forces groups (0110, 0210, 0310).
2. **ISCO 1113 does have official task descriptions (facts 20, 124).** It has seven task items, e.g. "allocating the use of communal land and other resources among households". Section 2 and Appendix E say it has none.
3. **ESCO vectors exist for 426, not 436, unit groups (facts 64–65).** Ten unit groups have no ESCO occupation, so their ESCO component is a zero vector: 1113, 2240, 3221, 4414, 6310, 6320, 6330, 6340, 7549 and 9624.
4. **"Eight alternative formulas" (fact 93).** Seven alternatives are tested, plus the baseline. The later "all eight formulas" (baseline included) is right.
5. **"Up to 9–13 overloaded groups with task counts exceeding 700" (fact 82)** does not match the current sweep. It reaches up to 16 overloaded groups, and the largest group holds up to 1,677 tasks. The figure probably comes from the sweep before the 30 September correction.
6. **Lower agreement on the 72 tasks ranked 4th–5th (fact 116)** does not hold under the selected configuration. Their exact agreement is 25.0% against 24.1% for the top-three 108, and sub-major agreement is 44.4% against 38.9%. Only major-group agreement is lower (52.8% vs 56.5%).

Inconsistent or overstated descriptions:

7. **How the headline agreement is computed (facts 44, 96).** Section 5 says task-level assignments "are aggregated to the occupation level" before comparison. Appendix B defines the in-set rate as the share of SOC occupations whose modal ISCO falls in the reference set. But the headline rates (53.7%, 83.1%, and Table C1) are task-level: the share of the 18,773 covered tasks whose own ISCO group falls in the set for their SOC code (`validation/shared.py::evaluate_match`). The modal-ISCO comparison is Table C2.
8. **"Groups with the highest counts draw over 75% of their tasks from a single SOC major group" (fact 128).** Among O*NET 29.2's eight largest groups this holds for 1345 (77.6%), 2351 (95.0%) and 2310 (81.4%), but not for 3341 (16.5%), 7233 (54.8%), 3131 (45.1%), 2133 (66.3%) or 2423 (53.4%). It does hold for the one overloaded group, 1345 (facts 39, 85).
9. **ISCO 1113 as the example of a group that "cannot be matched" (fact 55).** It receives tasks in the 30 releases from v13.0 to v25.0. It is unmatched only in the SOC 2018 releases and in v4.0–v12.0.
10. **"Results are similar across benchmark definitions" / "robust to the choice of reference crosswalk" (facts 50, 98).** For O*NET 29.2, exact agreement is 53.6% (A1), 45.1% (A2), 45.1% (A3) and 53.7% (A4), a spread of 8.6 pp. Major-group agreement runs from 74.4% to 83.1%.
11. **The ISCO "title" embedding (facts 27, 63).** Equation 2 and the notation table call it the ISCO occupation title. The code embeds title + definition + included occupations (`pipeline.py::load_isco_standard`), which Appendix A calls the "generic group description" or "ISCO information text".
12. **"Retrieval stage reaches 435 … before the similarity threshold and margin are applied" (fact 123).** The drop from 435 to 431 groups comes from keeping one group per task (`max_links_per_task = 1`). The threshold and margin do not bind in that setting.
13. **Sweep-table caption (fact 87).** It says the selection score is "a normalised composite". Since the 21 September fix it is the paper's raw formula, which is why the table shows 0.389 for both.
14. **"Alternative encoders clearly outperform" (fact 136).** That holds for gte-large (+4.8 pp exact). bge-large is +0.6 pp exact and +0.2 pp major group.
15. **"Combining ISCO-08 and ESCO text still improves retrieval over using either source alone (Appendix G)" (fact 91).** The ablation tests only the ISCO-only variant. The ESCO-only half is supported by the sweep instead: best score 0.366 with `w_isco = 0` and 0.368 with `w_isco = 1`, against 0.389.
16. **"Broadly consistent with expert judgement at the occupation-group level" (fact 118).** This wording dates from when major-group agreement was 81.5%. It is 55.0% now.
17. **"Available via Zenodo since 14 August 2026" (fact 57).** The concept DOI was already in the paper PDFs on 24 May 2026 (commit `ddfa275`), and release tags v1.0.0–v1.0.2 date from 23–24 May. Check the Zenodo version list.

Minor:

18. **"53.7%, all 18,796 tasks" (fact 114).** The rate is over the 18,773 tasks the crosswalk covers, the *n* used for its confidence interval.

---

## Abstract

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 1 | O*NET task data are widely used to measure technology exposure and skill demand; O*NET uses SOC while international statistics use ISCO | Abstract | Literature (Section 1 citations) | statement | |
| 2 | Existing SOC–ISCO concordances operate at the occupation level | Abstract | The four concordances of Section 2.2 | ok | |
| 3 | Crosswalk covers all 63 O*NET releases, v4.0–v30.3 | Abstract | `output/` (63 release files), `data/version_list.csv` | ok: 63 | |
| 4 | Detailed validation across the 50 SOC 2010 and SOC 2018 releases (v15.1–v30.3) | Abstract | `validation/results/chain_eval_onet*_overall.csv` | ok: 50 files | |
| 5 | SOC 2018 releases: 18,796–19,281 tasks assigned to 430–431 of 436 groups | Abstract | Release outputs, v25.1–v30.3 | ok | |
| 6 | SOC 2018 releases: 53.6–53.7% exact and 83.0–83.1% major-group agreement | Abstract | Chain eval, scenario A4, 23 releases | ok | |

## 1 Introduction

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 7 | O*NET task data used for technology exposure, skill demand, occupational change | §1 | Autor et al. 2003; Acemoglu & Autor 2011; Frey & Osborne 2017 | citation | |
| 8 | AI-exposure datasets published at O*NET task level, for SOC 2010 and SOC 2018 versions | §1 | Eloundou et al. 2024 | citation | |
| 9 | O*NET organised under SOC; international statistics use ISCO | §1 | ILO 2012 | citation | |
| 10 | Four concordances operate at occupation level; two built with text similarity (O*NET Center 2022; Matysiak et al. 2024); all four match titles, not tasks | §1 | Crosswalk documentation; B1 label in chain eval ("semantic") | citation; consistent | |
| 11 | Related literature on automated coding of free-text occupation responses | §1 | Gweon et al. 2017; Schierholz & Schonlau 2021 | citation | |
| 12 | Crosswalk versions for all releases v4.0–v30.3, spanning SOC 2018, SOC 2010 and earlier | §1 | `output/` | ok | |
| 13 | Across the 50 SOC 2010 + SOC 2018 releases: 430–433 groups, 18,783–19,735 tasks, mean cosine similarity 0.691–0.722 | §1 | Release outputs (task and group counts, mean `similarity`) | ok | |
| 14 | 16,049 tasks shared by O*NET 29.2 and 25.0; assignments agree in 98.5% | §1 | `output/ONET292_*`, `output/ONET250_*` (task ID merge) | ok | |

## 2 Data

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 15 | O*NET is maintained by the U.S. Department of Labor and updated quarterly | §2.1 | onetcenter.org | not checkable here | |
| 16 | Crosswalk files for all 63 releases v4.0–v30.3 | §2.1 | `output/` | ok | |
| 17 | O*NET 29.2 was the most recent SOC 2018 release at the time of parameter selection | §2.1 | O*NET release history | not checkable here | |
| 18 | O*NET 29.2 contains 18,796 task statements | §2.1 | `output/ONET292_task_to_ISCO_crosswalk.csv`; `verify_paper_numbers_v2.py` | ok | |
| 19 | DWAs: 2,082 granular activity descriptors | §2.1 | `Tasks to DWAs.xlsx` (29.2); `verify_paper_numbers_v2.py` | ok | |
| 20 | Official ISCO-08 task descriptions available for 435 of 436 unit groups; the remaining one is ISCO 1113 | §2.1 | `ISCO-08 EN Structure and definitions.xlsx` via `pipeline.py::load_isco_standard` | **ERROR**: 427 of 436; 1113 has 7 task items; the nine without are 1439, 3139, 3435, 5249, 7319, 8189, 0110, 0210, 0310 | |
| 21 | ESCO: approximately 3,000 occupation concepts linked to ISCO-08 | §2.1 | `data/esco/occupations_en.csv` | ok: 3,039 | |
| 22 | Four concordances used for validation only: SOC 2018 — O*NET–ESCO and ESCO–SOC 2018; SOC 2010 — BLS SOC 2010–ISCO-08 and ESCO–O*NET (Matysiak et al.) | §2.2 | `validation/shared.py`, `validate_chain.py` | ok | |

## 3 Method

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 23 | Encoder `all-mpnet-base-v2` | §3.1 | `configs/config_onet*.yaml` | ok | |
| 24 | Alternative encoders `bge-large-en-v1.5`, `gte-large` for sensitivity | §3.1 | `configs/config_onet292_bge.yaml`, `_gte.yaml` | ok | |
| 25 | Embeddings are 768-dimensional and unit-normalised | §3.2 | `pipeline.py` (embedding shapes 18,796 × 768; `normalize`) | ok | |
| 26 | Query = (1 − w_soc)[w_dwa·DWA + (1 − w_dwa)·task] + w_soc·title (Eq. 1) | §3.2 | `pipeline.py::build_embeddings` (components and blends normalised, as App. A notes) | ok | |
| 27 | ISCO component = task descriptions blended with the ISCO occupation *title* (Eq. 2) | §3.2 | `pipeline.py::load_isco_standard` | **inconsistent**: the second term is title + definition + included occupations ("info text"), as App. A describes | |
| 28 | ESCO component = ESCO occupation descriptions blended with ESCO skill texts (Eq. 3) | §3.2 | `pipeline.py` (label + description; unique skill labels per group) | ok | |
| 29 | Embeddings of several ESCO occupations in one unit group are averaged | §3.2 | `pipeline.py::_mean_embeddings_per_group` | ok | |
| 30 | Final target = w_isco·ISCO + (1 − w_isco)·ESCO (Eq. 4) | §3.2 | `pipeline.py::build_embeddings` | ok | |
| 31 | Cosine similarity against all 436 targets; each task assigned to the most similar | §3.3 | `pipeline.py` (FAISS IndexFlatIP over 436 vectors; `max_links_per_task = 1`) | ok | |
| 32 | Threshold and margin assess confidence; every task still receives an assignment | §3.3 | `pipeline.py::apply_task_filter` (best candidate always kept) | ok | |
| 33 | ≈30 min to embed ≈19,000 tasks on a CPU, ≈2 GB peak; embeddings cached by hash; FAISS overhead negligible | §3.3 | Runtime; `pipeline.py::embed_texts` | caching ok (text store by hash; since `4e25858` checkpoints also keyed by text hash); runtime not checkable here | |
| 34 | Figure 1: task side = task text, DWA labels, SOC title; occupation side = ISCO-08 task descriptions + ESCO titles and skills; crosswalks used only for validation | §3, Fig. 1 | `pipeline.py` | ok | |

## 4 Parameter Selection

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 35 | w_dwa = 0.2030, w_soc = 0.2344, w_isco = 0.4296, w_isco-task = 0.9610, w_occ = 0.0157 | §4 | `configs/config_onet292.yaml` (all 63 release configs) | ok | |
| 36 | Similarity threshold 0.45, margin 0.03 | §4 | Configs | ok | |
| 37 | Each task assigned to the single most similar unit group | §4 | `max_links_per_task: 1` | ok | |
| 38 | Selection on unsupervised criteria: coverage, mean similarity, concentration | §4 | `sweep/run_systematic_sweep_onet29.py::_sweep_score` | ok | |
| 39 | Concentration share 1.4%; the one group above the threshold draws over 75% of its tasks from one SOC major group | §4 | 29.2 output: T = max(200, Q₀.₉₅) = 200; only ISCO 1345 (268 tasks) above; 77.6% from SOC major group 25 | ok | |
| 40 | w_dwa = 0.2030 is 15.5% of the query vector; removing DWAs costs 0.7 pp exact | §4 | (1 − 0.2344) × 0.2030; `validation/results/ablation_comparison.csv` (53.7 → 53.0) | ok | |
| 41 | SOC title 23.4% of the query; raw task text 61.0% | §4 | Weights | ok | |
| 42 | Target: ESCO 57.0% vs ISCO 43.0% nominal; effective 56.1% ESCO skills, 41.3% ISCO task items, 1.7% ISCO info text, 0.9% ESCO occupations | §4 | Weights | ok | |
| 43 | Ablation: no SOC title −10.8 pp (53.7 → 42.9); no ESCO −3.7 pp; no DWA −0.7 pp | §4 | `ablation_comparison.csv` (no-title runs re-checked 1 Oct: title truly absent) | ok | |

## 5 Validation

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 44 | Task-level assignments are aggregated to the occupation level and compared with the concordances | §5 | `validation/shared.py::evaluate_match` | **inconsistent**: the headline rates compare each task's own ISCO group with its SOC code's accepted set, with no aggregation | |
| 45 | 23 SOC 2018 releases (25.1–30.3): 53.6–53.7% exact; 83.0–83.1% major group | §5 | Chain eval A4 | ok | |
| 46 | 27 SOC 2010 releases (15.1–25.0): 35.7–36.7% exact; 65.5–66.5% major group | §5 | Chain eval B3 | ok | |
| 47 | Lower SOC 2010 figures reflect weaker crosswalks: fewer occupations covered, and one is itself derived by semantic similarity | §5 | Chain eval B1 (Matysiak et al.) covers 79.3% of 20.1 tasks; B2 99.9% | consistent | |
| 48 | 16,049 shared tasks (29.2 vs 25.0), 98.5% agreement | §5 | See fact 14 | ok | |
| 49 | Selection does not use validation results; a better-validating configuration was available and not adopted | §5 | `CONFIG_SELECTION_LOG.md`; `validation/results/onet29_candidate_comparison.csv` | ok | |
| 50 | Agreement rates are robust to the choice of reference crosswalk | §5 | `chain_eval_onet292_overall.csv` | **overstated**: A1–A4 exact 45.1–53.7%, major 74.4–83.1% | |
| 51 | Wilson 95% CIs within ±0.7 pp for SOC 2018 (n ≈ 18,800), within ±0.8 pp for SOC 2010 (n ≈ 19,700) | §5 | Wilson intervals from chain eval | ok: largest half-width 0.71 pp in both eras | |
| 52 | Benchmark is indirect: no task-level ground truth exists | §5 | Methodological statement | statement | |

## 6 Conclusion, declarations and data availability

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 53 | All 63 releases; SOC 2018: 18,796–19,281 tasks, 430–431 groups, 53.6–53.7%; SOC 2010: 18,783–19,735 tasks, 431–433 groups | §6 | Release outputs; chain eval | ok | |
| 54 | Variation in group counts reflects SOC additions and removals between releases | §6 | Release outputs | interpretation | |
| 55 | ISCO groups without a U.S. counterpart cannot be matched (e.g., ISCO 1113) | §6 | Release outputs | **overstated**: 1113 receives tasks in all 30 releases from v13.0 to v25.0; unmatched in SOC 2018 releases and v4.0–v12.0 | |
| 56 | International comparability: O*NET task content assumed transferable outside the U.S. | §6 | Methodological statement | statement | |
| 57 | Crosswalk, code and manuscript publicly available via Zenodo since 14 August 2026, concept DOI 10.5281/zenodo.20359118 | Data availability | Zenodo; git history | DOI ok (concept record 20359118, latest version `submission-journal-2.1`, 30 Sep 2026, CC-BY-4.0); **date to check**: the DOI was in the paper PDFs on 24 May 2026 (`ddfa275`) | |
| 58 | AI-assistance statement; funding from Stiftelsen Arcada (No. 419) | Declarations | Author records | not checkable here | |

## Appendix notation

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 59 | Task-text embedding: one per task (≈19k) | Notation | Outputs | ok | |
| 60 | DWA embedding: one per task (2,082 unique DWAs) | Notation | 29.2 DWA file | ok | |
| 61 | SOC-title embedding: one per SOC occupation (≈900–1,000) | Notation | 923 in 29.2; 974 in 25.0 | ok | |
| 62 | ISCO task-description embedding: 435 unit groups | Notation | `load_isco_standard` | **ERROR**: 427 | |
| 63 | ISCO occupation-title embedding: 436 unit groups | Notation | `load_isco_standard` | count ok; content is title + definition + included occupations (see fact 27) | |
| 64 | ESCO occupation embedding (averaged per group): 436 unit groups | Notation | `data/esco/occupations_en.csv` (`iscoGroup`) | **ERROR**: 426; ten groups get a zero vector (1113, 2240, 3221, 4414, 6310, 6320, 6330, 6340, 7549, 9624) | |
| 65 | ESCO skill embedding (averaged per group): 436 unit groups | Notation | ESCO occupation–skill relations | **ERROR**: 426 (same ten groups) | |
| 66 | Combined ISCO, combined ESCO and final target vectors: 436 unit groups | Notation | `build_embeddings` | ok | |

## Appendix A — Parameter Selection

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 67 | Sweep run on O*NET 29.2 | App. A | `sweep/run_systematic_sweep_onet29.py` | ok | |
| 68 | Weights transfer unchanged to all 63 releases | App. A | Release configs | ok | |
| 69 | Five weights, each in [0, 1] | App. A | Sweep script | ok | |
| 70 | Component embeddings pre-computed and shared by all candidates | App. A | `pipeline.py` embedding caches | ok | |
| 71 | Feasibility constraint w_soc + w_dwa ≤ 0.90 | App. A | `MAX_QUERY_USED = 0.90`; largest value in sweep 0.875 | ok | |
| 72 | Round 1: five values per parameter, 5⁵ = 3,125 reduced to 1,250 feasible | App. A | Sweep file (round 1: 1,250 rows; grid 0, 0.25, …, 1) | ok | |
| 73 | Rounds 2–6: trust-region re-gridding (expand at grid boundary, one-sided refinement at a global bound, symmetric halving when interior; step floor max(h)/4); all parameters re-gridded together | App. A | Sweep script (`min_step_allowed = max(steps)/4`) | ok | |
| 74 | Stops when improvement < 0.0005, every best value is interior, and every step is below the round-1 step of 0.25 | App. A | `CONVERGENCE_THRESHOLD = 0.0005`; interior check in sweep script | ok | |
| 75 | 0.0005 ≈ 0.15 pp of coverage, below one ISCO coverage step | App. A | 0.0005 × 9/3 = 0.0015; one group = 1/436 = 0.23 pp | ok | |
| 76 | Sweep is deterministic; no ties for the best score arose in the six rounds | App. A | Sweep file: one row at the maximum in every round | ok | |
| 77 | 16,750 candidates: 1,250, 3,000 and 3,125 in each of rounds 3–6 | App. A | `results/summary/sweep_results_metrics_only.csv` | ok | |
| 78 | Sweep score = (3·cov + 2·sim − 2·overload − 2·gini)/9 | App. A | `_sweep_score` | ok | |
| 79 | Overloaded if task count > T = max(200, Q₀.₉₅) | App. A | `config.py::compute_overload_threshold` | ok | |
| 80 | Overload share across candidates 1.1–31.0% (std 3.3 pp) | App. A | Sweep file | ok | |
| 81 | Score range −4/9 to 5/9 | App. A | Formula | ok | |
| 82 | Pathological configurations have lower mean similarity and up to 9–13 overloaded groups with task counts above 700 | App. A | Sweep file | lower similarity ok (0.649 vs 0.703 for configurations with ≥ 9 overloaded groups); **ERROR**: up to 16 overloaded groups, largest group up to 1,677 tasks | |
| 83 | Optimum unchanged under (1,1,1,1) and (1,2,2,2); changes modestly under three variants that remove or double one term | App. A | `validation/results/reviewer_c3_formula_sensitivity.csv` | ok | |
| 84 | Selected configuration: score 0.389; coverage 98.9%, mean similarity 0.722, Gini 0.441, overload share 1.4% | App. A | `validation/results/candidate_sweep_scores.csv` | ok | |
| 85 | The one group above the concentration threshold (ISCO 1345) draws over 75% of its tasks from one SOC major group | App. A | 29.2 output | ok: 77.6% | |
| 86 | C1–C4 and B0 agree more with the chain crosswalk (80.7–82.1% vs 53.7%) and with the annotations (50.0–53.3% vs 24.4%); S* ranks first on the sweep score | App. A | `onet29_candidate_comparison.csv`, `candidate_sweep_scores.csv` | ok | |
| 87 | Top configurations: coverage 98.9%, sweep scores 0.388–0.389; caption calls the selection score "a normalised composite" | App. A, Table A-sweep-top | `tables/table_sweep_top_configs.tex` | values ok; **caption stale**: the selection score is now the raw formula | |
| 88 | Query side: components normalised before blending, query re-normalised after each blend; effective shares 61.0 / 23.4 / 15.5% | App. A | `build_embeddings` | ok | |
| 89 | Target side: 43.0 / 57.0% ISCO vs ESCO; 96.1 / 3.9% within ISCO; 1.6 / 98.4% within ESCO; effective 56.1 / 41.3 / 1.7 / 0.9%; target normalised before retrieval | App. A | Weights; `build_embeddings` | ok | |
| 90 | Heatmaps (Figs. A1–A2) show the maximum sweep score per cell; red star at the selected configuration | App. A | `sweep/plot_sweep_params.py` (regenerated 30 Sep) | figure | |
| 91 | Combining ISCO-08 and ESCO text improves retrieval over either source alone (Appendix G) | App. A, Findings | Sweep file; ablation | **partly**: the ablation has no ESCO-only variant; the sweep supports both halves (best 0.366 with w_isco = 0, 0.368 with w_isco = 1, vs 0.389) | |
| 92 | High-scoring configurations cluster in a narrow region | App. A | `table_sweep_top_configs.tex` | ok | |
| 93 | Eight alternative objective formulas tested; ρ ≥ 0.978 for equal and coverage-de-prioritised; ρ = 0.77–0.97 for no-Gini, no-overload, double-Gini; ρ = 0.42 and 0.33 for coverage-only and similarity-only; S* first under all eight | App. A | `reviewer_c3_formula_sensitivity.csv`, `reviewer_c3_shortlist_under_formulas.csv` | **ERROR** in the count: seven alternatives (eight with the baseline); all ρ values and the "first under all eight" result ok | |
| 94 | Within-SOC heterogeneity: 798 / 99.5% / 9.37 / 9.0 (task level); 797 / 89.5% / 4.75 / 4.0 and 784 / 71.7% / 2.62 / 2.0 (occupation level) | App. A | `validation/results/reviewer_c1_summary.csv` | ok | |
| 95 | 8,686 of the 18,773 covered 29.2 tasks (46.3%) disagree with the chain crosswalk; the four examples are assigned to ISCO 1349, 5111, 3253 and 5312; full sample in replication materials | App. A | `chain_disagreements_full.csv`; 29.2 output | ok | |

## Appendix B — Validation Framework

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 96 | Each SOC occupation gets its modal ISCO group; the in-set rate is the share of SOC occupations whose modal group falls in the reference set | App. B | `evaluate_match` vs `report_occupation.py` | **inconsistent** with the headline rates (task level, see fact 44); describes Table C2 | |
| 97 | Strict benchmark = intersection; lenient = union of available crosswalks | App. B | Scenarios A3/A4, B4/B3 | ok | |
| 98 | Results are similar across benchmark definitions | App. B | Chain eval | **overstated** (see fact 50) | |
| 99 | Institutional crosswalks are used only for validation | App. B | `pipeline.py` does not read them | ok | |

## Appendix C — Full Validation Results

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 100 | 63 releases across five SOC generations | App. C | `data/version_list.csv` | ok | |
| 101 | Table C1 reports 25.1, 29.2, 30.3 (SOC 2018) and 15.1, 20.0, 25.0 (SOC 2010) | App. C | `tables/table_gt01_validation.tex` | ok | |
| 102 | ESCO–O*NET-SOC chain crosswalks cover SOC 2018; ESCO–O*NET and BLS cover SOC 2010 | App. C | Scenario sets per era | ok | |
| 103 | 29.2 A4 (n = 18,773): exact [53.0, 54.4], sub-major [71.6, 72.8], major [82.6, 83.6]; 25.0 B3 (n = 19,735): exact 36.6 [35.9, 37.3], major 66.4 [65.7, 67.1]; all within ±0.7 pp | App. C | Wilson intervals from chain eval | ok | |
| 104 | Table C2: modal ISCO per SOC; pair precision and in-set rates; Table C3: internal consistency of reference crosswalks | App. C | `report_occupation.py`, `export_latex.py` | generated tables | |
| 105 | Medical Dosimetrists (29-2036): pipeline 3211, both references 2269; Rock Splitters (47-5051): pipeline 7113, ESCO→O*NET-SOC 7113, O*NET-SOC→ESCO 8114 | App. C | `tables/table_mismatch_examples.tex` | ok | |
| 106 | The in-set rate is a lower bound on true quality when references contain errors | App. C | Argument | statement | |

## Appendix D — Author Annotation

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 107 | 180 O*NET 29.2 tasks from 36 SOC occupations covering all nine ISCO major groups; top five per occupation; the top three (n = 108) underpin a test-retest check | App. D | `validation/results/human_eval_onet29_expanded_detail.csv` | ok (36 O*NET-SOC occupations = 30 six-digit SOC codes; expert codes in all nine major groups) | |
| 108 | Occupations chosen by combined U.S. and Nordic employment within each major group | App. D | Sampling records | not checkable here | |
| 109 | Annotation from a shortlist, without reference to the pipeline's predictions | App. D | `validation/generate_workbook.py` (workbook omits predictions) | ok | |
| 110 | Selected configuration: 24.4% exact, 41.1% sub-major, 55.0% major; mean similarity 0.727 | App. D | `human_eval_onet29_summary.csv` | ok | |
| 111 | Wilson CIs: exact [18.7, 31.2], sub-major [34.2, 48.4], major [47.7, 62.1] | App. D | `human_eval_onet29_expanded_summary.csv` | ok | |
| 112 | Alternative configurations reach 50.0–53.3% exact on the same sample | App. D | `onet29_candidate_comparison.csv` | ok | |
| 113 | Chain A4 on the 180-task subset: 56.1% exact, 78.3% sub-major, 87.8% major | App. D | `evaluate_match` on the annotated task IDs | ok | |
| 114 | Full-dataset chain rate 53.7% "on all 18,796 tasks" | App. D | Chain eval | ok value; denominator is the 18,773 covered tasks | |
| 115 | 108 top-three tasks plus 72 ranked 4th–5th; 20 of the 108 re-annotated blind: 85.0% exact [64.0, 94.8], 100% sub-major and major; the three exact disagreements stay within the same sub-major group | App. D | `human_eval_onet29_test_retest_summary.csv` | ok | |
| 116 | Lower agreement on the 72 tasks ranked 4th–5th than on the top-three group | App. D | Expanded detail vs `annotation_workbook_onet29_original_108_backup.xlsx` | **not supported**: exact 25.0% vs 24.1%, sub-major 44.4% vs 38.9%; only major group lower (52.8% vs 56.5%) | |
| 117 | No independent second annotator; an LLM was considered and rejected | App. D | Statement | statement | |
| 118 | Results confirm assignments broadly consistent with expert judgement at the occupation-group level | App. D | Annotation results | **overstated** for 55.0% major-group agreement (wording from the 81.5% version) | |
| 119 | The chain benchmark is the primary validation criterion | App. D | Statement | statement | |

## Appendix E — Coverage and Example Matches

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 120 | Releases before v20.1 are text only; Excel from v20.1 | App. E | `data/version_list.csv` | ok | |
| 121 | Titles merged from `Occupation Data.txt` for pre-v20.1 releases | App. E | `download_onet_versions.py` | ok | |
| 122 | All parameters and thresholds identical across versions; only input data differ | App. E | Release configs | ok for weights and thresholds; `use_task_ids` is false for v4.0–v12.0, and releases before v20.1 have no DWA file (DWA term drops out) | |
| 123 | 29.2: 431 of 436 groups in the final assignment (98.9%); retrieval stage 435 of 436 (99.8%) "before the similarity threshold and margin are applied" | App. E | S1/S2 stage files of the production run | counts ok; **wording**: the drop is from keeping one group per task, not from the threshold or margin | |
| 124 | Unassigned groups typically lack a U.S. counterpart; most notable 1113, "for which no official ISCO-08 task descriptions are available" | App. E | 29.2 output; ISCO-08 file | unassigned in 29.2: 1113, 5161, 7516, 9332, 9624; **ERROR**: 1113 has 7 official task items | |
| 125 | Coverage broad across major groups | App. E | 29.2 output (all major groups, including armed forces 0110/0210/0310, receive tasks) | ok | |
| 126 | Figure E1: coverage and mean similarity by stage across releases; S2 keeps near-complete coverage | App. E | `figure_stage_progression.pgf` | ok (98.9% for 29.2) | |
| 127 | Tables E1–E2: stage and S2 metrics for selected releases | App. E | `table_baseline_stage_metrics.tex`, `table_baseline_s3_summary.tex` | generated tables | |
| 128 | Groups with the highest counts draw over 75% of their tasks from a single SOC major group | App. E | 29.2 output with O*NET-SOC codes | **overstated**: true for 1345 (77.6%), 2351 (95.0%), 2310 (81.4%); not for 3341 (16.5%), 7233 (54.8%), 3131 (45.1%), 2133 (66.3%), 2423 (53.4%) | |
| 129 | Overload table covers four releases; the groups are structurally dense nodes, not catch-alls | App. E | `table_overload_examples.tex` (20.0, 25.0, 29.2, 30.3) | releases ok; "not catch-alls" is interpretation (3341 Office Supervisors draws on many SOC major groups) | |
| 130 | Example table: one task per ISCO major group | App. E | `table_task_examples.tex` (nine rows) | ok | |

## Appendix F — Embedding Model Robustness

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 131 | `BAAI/bge-large-en-v1.5` and `thenlper/gte-large`, both 1024-dimensional | App. F | Model cards | not checkable here (known model dimensions) | |
| 132 | All other parameters identical to production | App. F | `config_onet292_bge.yaml`, `_gte.yaml` | ok | |
| 133 | Mean similarities are not comparable across encoders; agreement rates are | App. F | Statement | statement | |
| 134 | Exact A4: 53.7% (MPNet), 54.3% (BGE), 58.5% (GTE), range 4.8 pp; major 83.1–85.3% (2.2 pp); coverage 426–431 groups | App. F | `validation/results/embedding_model_comparison.csv` | ok | |
| 135 | Switching the production encoder was not attempted | App. F | Configs | ok | |
| 136 | The alternative encoders clearly outperform the production model | App. F | `embedding_model_comparison.csv` | **overstated** for BGE (+0.6 pp exact, +0.2 pp major) | |
| 137 | Task-level agreement: MPNet–BGE 62.5%, MPNet–GTE 64.7%, BGE–GTE 80.4% | App. F | `reviewer_c2_task_level_agreement.csv` | ok | |
| 138 | Occupation-level agreement: 71.6%, 74.3%, 82.2% (n = 798); gains 9.1–9.6 pp (MPNet pairs) and 1.8 pp | App. F | `reviewer_c2_occupation_level_agreement.csv` | ok | |
| 139 | Disagreement 42–52% in ISCO major groups 1 and 6, 28–32% in 4 and 7 | App. F | `reviewer_c2_disagreement_by_major_group.csv` (MG1 47.3/51.9, MG6 46.4/41.5, MG4 28.6/28.1, MG7 32.1/29.2) | ok | |

## Appendix G — Ablation Study

| # | Fact | Location | Verification source | Check (1 Oct 2026) | My Note |
|---|------|----------|---------------------|--------------------|---------|
| 140 | Four variants: no SOC title, no DWA, no ESCO (ISCO-08 only), task text only | App. G | `run_ablation.py`, `configs/config_onet292_abl_*.yaml` | ok | |
| 141 | No SOC title: 53.7% → 42.9% (−10.8 pp), the largest drop | App. G | `ablation_comparison.csv` | ok; re-checked 1 Oct: the run's query contains no title | |
| 142 | No ESCO: 50.0% (−3.7 pp) | App. G | `ablation_comparison.csv` | ok | |
| 143 | No DWA: 53.0% (−0.7 pp) | App. G | `ablation_comparison.csv` | ok | |
| 144 | Task text only: 42.6%, about the same as no SOC title | App. G | `ablation_comparison.csv` | ok | |

---

*Checked 1 October 2026 against this repository (outputs, configs, `validation/results/`, `results/summary/sweep_results_metrics_only.csv`, `data/`) and the tables in the manuscript's `tables/` folder.*
