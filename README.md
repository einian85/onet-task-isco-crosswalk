# O*NET Task -> ISCO-08 Crosswalk

Code and data for the O*NET task -> ISCO-08 crosswalk described in:

> Einian, M.
> 2026.
> Mapping O*NET Tasks to ISCO Occupations using Text Similarity
> [manuscript under review]

The crosswalk files, code and manuscript versions are archived on Zenodo under the concept DOI [10.5281/zenodo.20359118](https://doi.org/10.5281/zenodo.20359118), which resolves to the latest version.

Pre-computed crosswalk files are in [`output/`](output/). The sections below describe how to reproduce them from scratch.

---

## What this does

Each O*NET task statement is mapped to exactly one ISCO-08 4-digit unit group. Both sides are represented with Sentence-BERT (`all-mpnet-base-v2`) embeddings, and each task is matched to the closest unit group by exact nearest-neighbour search (FAISS inner product on normalised vectors, i.e. cosine similarity).

- **Query (one vector per task).** The task text is blended with the average embedding of its Detailed Work Activity (DWA) labels, and then with the embedding of its SOC occupation title:
  `core = (1 - w_dwa) * task + w_dwa * DWA average`, `query = (1 - w_soc_title) * core + w_soc_title * SOC title`.
  With `w_soc_title = 0` the query has no title.
- **Target (one vector per ISCO-08 unit group, 436 in all).** An ISCO part blends the unit group's official task items with its title, definition and included occupations. An ESCO part blends the label and description of the ESCO occupations in the group with their skills:
  `ISCO = w_isco_task * ISCO task items + (1 - w_isco_task) * ISCO info text`,
  `ESCO = w_occ * ESCO occupations + (1 - w_occ) * ESCO skills`,
  `target = w_isco * ISCO + (1 - w_isco) * ESCO`.
- **Two stages.** `S1_RETRIEVE` retrieves the 5 most similar unit groups per task. `S2_TASK_FILTER` keeps the best one. The final crosswalk is written from S2.

All 63 O*NET releases from v4.0 (2001) through v30.3 (2025) are covered, spanning five SOC taxonomy generations:

| SOC generation | O*NET versions | Releases | Notes |
|----------------|---------------|----------|-------|
| Pre-2006 SOC | v4.0–v9.0 | 7 | Text format only; occupation titles from `Occupation Data.txt`; no task IDs |
| SOC 2006 | v10.0–v13.0 | 4 | Text format only; task IDs complete from v13.0 |
| SOC 2009 | v14.0–v15.0 | 2 | Text format only |
| SOC 2010 | v15.1–v25.0 | 27 | Text format through v20.0; Excel from v20.1 |
| SOC 2018 | v25.1–v30.3 | 23 | Excel format |

Releases before v20.1 have no Tasks-to-DWAs file, so the DWA term drops out of their query (the pipeline falls back to `w_dwa = 0` when the file is missing).

### Production settings

All 63 release configs share these values:

| `w_soc_title` | `w_dwa` | `w_isco` | `w_isco_task` | `w_occ` | `k_retrieve` | `max_links_per_task` |
|---------------|---------|----------|---------------|---------|--------------|----------------------|
| 0.2344 | 0.2030 | 0.4296 | 0.9610 | 0.0157 | 5 | 1 |

Multiplied out, the query vector is 61.0% task text, 15.5% DWA average and 23.4% SOC title. `min_sim = 0.45` and `margin_best = 0.03` are the S2 thresholds; they do not bind when only one link per task is kept.

The weights are the optimum of an unsupervised parameter sweep on O*NET 29.2 (see below), selected on 30 September 2026. [`CONFIG_SELECTION_LOG.md`](CONFIG_SELECTION_LOG.md) records how the selection was made and corrected.

---

## Repository layout

```text
.
|-- pipeline.py               # Core pipeline: text construction, embeddings, retrieval (S1), task filter (S2)
|-- config.py                 # RunConfig dataclass (all parameters), config loading, run IDs
|-- metrics_unsup.py          # Unsupervised stage metrics (coverage, similarity, Gini, overload, confidence)
|-- evaluate.py               # Evaluation utilities
|-- stability.py              # Cross-run stability analysis
|
|-- run_all_versions.py       # Run the pipeline for all (or selected) O*NET releases
|-- download_onet_versions.py # Download and normalise all O*NET release zips
|-- generate_configs.py       # Generate configs/config_onet*.yaml for releases that have none
|-- update_configs.py         # Write the sweep's top-scoring weights into every config
|
|-- run_ablation.py           # Ablation study on O*NET 29.2 (no DWA, no ESCO, no SOC title, task text only)
|-- run_embedding_comparison.py # Same pipeline with BAAI/bge-large-en-v1.5 and thenlper/gte-large
|-- compare_crosswalk_agreement.py # Task-level agreement between encoders
|-- compute_cis.py            # Wilson 95% confidence intervals for the validation statistics
|
|-- report_occupation.py      # Occupation-level comparison vs reference crosswalks
|-- report_publication.py     # Publication tables and figures
|-- export_latex.py           # Export tables to LaTeX fragments
|-- verify_paper_numbers_v2.py # Print every key quantity cited in the paper from the current files
|-- verify_paper_numbers.py   # Superseded by v2 (its "paper says" values are from an earlier draft)
|-- check_coverage.py         # Quick coverage check of the O*NET 29.2 crosswalk
|-- check_facts.py            # Checks for three facts of the August 2026 fact audit (historical)
|
|-- configs/                  # One YAML per O*NET release (v4.0–v30.3), plus ablation and encoder variants
|-- sweep.py                  # Sweep engine (candidate configs, selection score)
|-- sweep/
|   |-- run_systematic_sweep_onet29.py # Adaptive iterative five-parameter sweep on O*NET 29.2
|   |-- plot_sweep_params.py           # Parameter heatmaps
|   `-- _best_config.py, _check_wisco.py, _sweep_stats.py, _trace_rounds.py  # Sweep diagnostics
|
|-- output/                   # Pre-computed crosswalk CSVs: one per O*NET release, plus
|   |                         # ONET292_abl_* (ablations) and ONET292_bge_*, ONET292_gte_* (encoders)
|   |-- ONET292_task_to_ISCO_crosswalk.csv
|   |   ...
|   `-- ONET40_task_to_ISCO_crosswalk.csv
|-- results_ablation/, results_bge/, results_gte/   # Stage files and metrics of the ablation and encoder runs
|
|-- validation/
|   |-- shared.py                      # Shared paths and loaders
|   |-- validate_chain.py              # Approach 1: chain crosswalk agreement
|   |-- audit_chain_disagreements.py   # Inspect tasks where the chain crosswalks disagree
|   |-- generate_workbook.py           # Approach 2a: expert annotation workbook
|   |-- evaluate_annotations.py        # Approach 2b: evaluate the filled workbook
|   |-- *_phase_d.py                   # Expansion of the annotation sample to 180 tasks
|   |-- compare_onet29_candidates.py, score_candidates.py   # Candidate-configuration comparisons
|   |-- reviewer_c1_*.py ... reviewer_c4_*.py               # Reviewer checks: heterogeneity, encoders,
|   |                                                       # objective sensitivity, coverage
|   `-- results/                       # Chain, annotation, ablation and reviewer-check results
|
|-- CONFIG_SELECTION_LOG.md   # Dated record of the configuration selection
|-- fact_audit_table.md       # Fact audit of the manuscript resubmitted 30 Sep 2026 (checked 1 Oct 2026)
|
|-- LICENSE                  # MIT (code); data and documentation CC BY 4.0
`-- data/                      # Not included - download instructions below
```

---

## Setup

### Requirements

Python 3.11. Install dependencies in a fresh environment:

```bash
conda create -n onet-isco-nlp python=3.11
conda activate onet-isco-nlp
pip install sentence-transformers faiss-cpu pandas numpy scikit-learn openpyxl xlrd pyyaml matplotlib
```

Key package versions used in the paper:

| Package | Version |
|---------|---------|
| sentence-transformers | 5.1.0 |
| torch | 2.8.0 |
| faiss-cpu | 1.9.0 |
| pandas | 2.3.1 |
| numpy | 1.26.4 |

### Data

Source data is not included in this repository. Download and place files as follows:

**O*NET** (<https://www.onetcenter.org/database.html>):

All 63 releases can be downloaded and normalised automatically:

```bash
python download_onet_versions.py        # download all versions
python download_onet_versions.py --force  # re-download everything
```

This reads `data/version_list.csv` and places normalised `Task Statements.txt` (or `.xlsx` for v20.1+) and `Tasks to DWAs` files under `data/onet/<major>_<minor>/`.

**ESCO v1.2** (<https://esco.ec.europa.eu/en/use-esco/download>):
- Download English CSV bulk download -> place `occupations_en.csv`, `skills_en.csv`, `occupationSkillRelations_en.csv` into `data/esco/`

**ISCO-08** (<https://www.ilo.org/public/english/bureau/stat/isco/isco08/>):
- `ISCO-08 EN Structure and definitions.xlsx` -> `data/isco/`

**Reference crosswalks** (used for validation only):

| Source | File | Save to |
|--------|------|---------|
| Matysiak et al. (2024) ESCO-O*NET | `esco_onet_crosswalk.csv` | `data/crosswalks/` |
| BLS SOC 2010 <-> ISCO-08 | `isco_soc_crosswalk.xls` | `data/crosswalks/` |
| O*NET Center ESCO -> O*NET-SOC | `ESCO_to_ONET-SOC.xlsx` | `data/crosswalks/` |
| ESCO Secretariat O*NET-SOC -> ESCO | `ONET_(Occupations)_0_updated.csv` | `data/crosswalks/` |

---

## Reproducing the crosswalks

Run from the repository root:

```bash
python run_all_versions.py                        # all 63 versions (skips existing outputs)
python run_all_versions.py --force                # re-run everything
python run_all_versions.py --versions 29.2 25.0  # specific versions only
python run_all_versions.py --dry-run              # print run order without executing
python pipeline.py configs/config_onet292.yaml    # a single release
```

Configs live in `configs/`. `generate_configs.py` creates configs for releases that have none, and `update_configs.py` writes the sweep's top-scoring weights into all of them.

Embeddings are cached in `checkpoints/`. A text store holds one vector per distinct text, so a text shared across releases is encoded once. The per-release matrices are saved under names that include a hash of their texts, so a cached matrix is reused only for exactly the texts it was built from. ESCO and ISCO source files are also cached in-process across releases.

---

## Reproducing the parameter sweep

```bash
python sweep/run_systematic_sweep_onet29.py   # adaptive five-parameter sweep on O*NET 29.2
python sweep/plot_sweep_params.py             # parameter heatmaps
```

Each round evaluates a 5-point grid per parameter and zooms in around the best candidate, until the improvement falls below the convergence threshold. Every candidate is scored on its final-stage (S2) metrics:

`score = (3 * ISCO coverage + 2 * mean similarity - 2 * overload share - 2 * Gini) / 9`

The selection is unsupervised: the validation data play no part in it. The run behind the production settings took 6 rounds and 16,750 candidates. Sweep metrics are written to `results/summary/` (regenerable, not tracked). `update_configs.py` then takes the top-scoring candidate.

---

## Reproducing the paper tables and figures

```bash
python report_occupation.py        # occupation-level comparison -> results/publication/
python report_publication.py       # parameter sensitivity, stage progression -> results/publication/
python export_latex.py             # LaTeX table fragments -> results/publication/tables/
python compute_cis.py              # Wilson confidence intervals
python verify_paper_numbers_v2.py  # print every key quantity cited in the paper
```

---

## Validation

**Approach 1 - Chain crosswalk agreement.** For each of the 50 SOC 2010 and SOC 2018 releases (v15.1–v30.3), each task's ISCO-08 group is compared with the groups that institutional concordances assign to its SOC occupation. The scenarios are:
- SOC 2018 releases: ESCO–SOC 2018 alone (A1), SOC 2018–ESCO alone (A2), strict intersection (A3), lenient union (A4).
- SOC 2010 releases: Matysiak et al. ESCO–O*NET alone (B1), BLS SOC 2010–ISCO-08 alone (B2), lenient union (B3), strict intersection (B4).

```bash
cd validation && python validate_chain.py
```

Results: `validation/results/chain_eval_onet{tag}_overall.csv`, one file per release.

**Approach 2 - Human expert annotation.** A sample of O*NET 29.2 tasks was annotated with ISCO-08 codes, without access to the model's answers, and compared with the crosswalk. The sample was later expanded to 180 tasks (`*_phase_d.py`), and 20 tasks were annotated twice as a test-retest check.

```bash
cd validation && python generate_workbook.py     # generate the workbook (then fill in expert_isco)
cd validation && python evaluate_annotations.py  # evaluate the filled workbook
```

**Robustness.** `run_ablation.py` removes one input at a time on O*NET 29.2: the SOC title, the DWA labels, ESCO, or everything but the task text. `run_embedding_comparison.py` reruns the pipeline with two other encoders. The `validation/reviewer_c*` scripts hold the checks requested in review.

### Key validation results

| Releases | Tasks | ISCO-08 groups reached | Exact | Sub-major | Major group |
|----------|-------|------------------------|-------|-----------|-------------|
| SOC 2018 releases (23), chain A4 | 18,796–19,281 | 430–431 | 53.6–53.7% | | 83.0–83.1% |
| SOC 2010 releases (27), chain B3 | 18,783–19,735 | 431–433 | 35.7–36.7% | | 65.5–66.5% |
| O*NET 29.2, chain A4 | 18,796 | 431 | 53.7% | 72.2% | 83.1% |
| O*NET 29.2, human annotation (n = 180) | | | 24.4% [18.7, 31.2] | 41.1% [34.2, 48.4] | 55.0% [47.7, 62.1] |

Brackets give Wilson 95% confidence intervals. In the test-retest check (n = 20), the two annotation rounds agreed on 85.0% of tasks at four digits and on all tasks at the major-group level.

The O*NET 29.2 crosswalk reaches 431 of the 436 ISCO-08 unit groups. The five groups without a task are 1113 (traditional chiefs and heads of villages), 5161 (astrologers and fortune-tellers), 7516 (tobacco preparers), 9332 (drivers of animal-drawn vehicles) and 9624 (water and firewood collectors).

---

## Output format

Final crosswalk CSVs contain one row per task, the unit group kept at the `S2_TASK_FILTER` stage:

| Column | Description |
|--------|-------------|
| `task_id` | O*NET Task ID |
| `task_text` | Task statement text |
| `candidate_rank` | Rank of the retained ISCO candidate for that task |
| `iscoGroup` | 4-digit ISCO-08 unit group |
| `isco_title` | ISCO occupation label |
| `similarity` | Cosine similarity score |
| `task_best_similarity` | Best retrieval similarity for the task before filtering |
| `task_best_target` | Best retrieval target before filtering |
| `gap_1_2` | Similarity gap between the top-1 and top-2 retrieved targets |
| `is_best` | Whether the row is the task's best-scoring retained target |

The full stage files (`S1_RETRIEVE`, `S2_TASK_FILTER`, with `run_id`, `stage`, `task_key`, `target_id`, `gap_1_k`, `topk_entropy`, `kept_reason` and `task_text_hash`) are written under `results/predictions/<run_id>/`, together with `config.json` and `run_manifest.json`. The run ID is a hash of the config, the git commit and the data version.

---

## Licence

- **Code** (all `.py` files and configs): MIT License, see [`LICENSE`](LICENSE).
- **Data and documentation** (the crosswalk files in `output/`; the results in `validation/results/`, `results_ablation/`, `results_bge/` and `results_gte/`; this README and the other documentation): [CC BY 4.0](https://creativecommons.org/licenses/by/4.0/). Versions released before October 2026 were deposited on Zenodo under CC BY 4.0 as a whole.
- **Third-party content.** The crosswalk files contain O*NET task statements and occupation titles (U.S. Department of Labor, Employment and Training Administration), and ISCO-08 titles (International Labour Organization). The pipeline also uses ESCO occupation and skill labels (European Commission). This content remains subject to its providers' terms; please credit O*NET, ESCO and the ILO as their terms require when you redistribute it.

---

## Citation

If you use the crosswalks or code, please cite:

```bibtex
@misc{einian2026onet,
  title  = {Mapping O*NET Tasks to ISCO Occupations using Text Similarity},
  author = {Einian, Majid},
  year   = {2026},
  doi    = {10.5281/zenodo.20359118},
  note   = {Manuscript under review}
}
```
