# O*NET Task -> ISCO-08 Crosswalk

Code and data for the NLP-based O*NET task-ISCO-08 crosswalk described in:

> Einian, M.  
> 2026.  
> Mapping O*NET Tasks to ISCO Occupations using Text Similarity  
> [in submission process]

Pre-computed crosswalk files are in [`output/`](output/). The sections below describe how to reproduce them from scratch.

---

## What this does

Each O*NET task statement is mapped to exactly one ISCO-08 4-digit unit group using dual-side Sentence-BERT (`all-mpnet-base-v2`) embeddings and FAISS retrieval. The query embedding blends the task text with Detailed Work Activity (DWA) labels and the SOC occupation title; the target embedding blends ISCO-08 official descriptions and task items with ESCO occupation text and ESCO skills. Candidates pass through five filtering stages: retrieval -> task-filter -> coverage -> overload -> final.

Each task is assigned to exactly one ISCO-08 unit group. Coverage backfill ensures missing ISCO groups are represented using only unassigned tasks, so the one-to-one property is preserved throughout.

All 63 O*NET releases from v4.0 (2001) through v30.3 (2025) are covered, spanning five SOC taxonomy generations:

| SOC generation | O*NET versions | Notes |
|----------------|---------------|-------|
| Pre-2006 SOC | v4.0–v9.x | Text format only; occupation titles from `Occupation Data.txt` |
| SOC 2006 | v10.0–v13.x | Text format only |
| SOC 2009 | v14.0–v15.0 | Text format only |
| SOC 2010 | v15.1–v25.0 | Text format only through v20.0; Excel from v20.1 |
| SOC 2018 | v25.1–v30.3 | Excel format |

Production blend weights (all versions share the same settings):

| `w_soc_title` | `w_dwa` | `w_isco` | `w_isco_task` | `w_occ` | `max_links_per_task` |
|---------------|---------|----------|---------------|---------|----------------------|
| 0.375 | 0.2656 | 0.375 | 0.7344 | 0.1562 | 1 |

---

## Repository layout

```text
.
|-- pipeline.py               # Core NLP pipeline (embedding, retrieval, filtering)
|-- config.py                 # RunConfig dataclass (all parameters)
|-- evaluate.py               # Evaluation utilities
|-- metrics_unsup.py          # Unsupervised similarity metrics
|-- stability.py              # Cross-run stability analysis
|
|-- run_all_versions.py       # Run pipeline for all (or selected) O*NET versions
|-- generate_configs.py       # Generate configs/config_onet*.yaml for all versions
|-- download_onet_versions.py # Download and normalise all O*NET release zips
|
|-- report_occupation.py      # Occupation-level comparison vs reference crosswalks
|-- report_publication.py     # Publication tables and figures
|-- export_latex.py           # Export tables to LaTeX fragments
|-- verify_paper_numbers.py   # Sanity-check all numbers cited in the paper
|
|-- configs/                  # One YAML per O*NET release (v4.0–v30.3)
|   |-- config_onet40.yaml
|   |-- config_onet50.yaml
|   |   ...
|   `-- config_onet303.yaml
|
|-- sweep.py                  # Sweep engine (random configs, Pareto scoring)
|-- sweep/
|   |-- run_systematic_sweep_onet29.py # Adaptive iterative parameter sweep
|   |-- plot_sweep_params.py           # Parameter heatmaps
|   |-- _best_config.py                # Inspect best sweep configurations
|   |-- _sweep_stats.py                # Sweep diagnostics
|   `-- _trace_rounds.py               # Trace adaptive sweep rounds
|
|-- output/                   # Pre-computed crosswalk CSVs (one per O*NET release)
|   |-- ONET292_task_to_ISCO_crosswalk.csv
|   |   ...
|   `-- ONET40_task_to_ISCO_crosswalk.csv
|
|-- validation/
|   |-- shared.py                      # Shared paths and loaders
|   |-- validate_chain.py              # Approach 1: chain-crosswalk agreement
|   |-- generate_workbook.py           # Approach 2a: generate expert annotation workbook
|   |-- evaluate_annotations.py        # Approach 2b: evaluate filled workbook
|   `-- results/
|       |-- chain_eval_onet29_overall.csv
|       |-- human_eval_onet29.csv
|       |-- human_eval_onet29_summary.csv
|       `-- annotation_workbook_onet29.xlsx
|
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

**Reference crosswalks**:

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
```

Configs live in `configs/`. To regenerate them (e.g. after changing settings):

```bash
python generate_configs.py
```

Embeddings are cached in `checkpoints/` after the first run. ESCO and ISCO source files are cached in-process across versions, so the 63-version run does not reload them repeatedly.

---

## Reproducing the parameter sweep

The ONET29 sensitivity analysis is produced by:

```bash
# Adaptive five-parameter sweep (ONET29)
python sweep/run_systematic_sweep_onet29.py

# Parameter heatmaps
python sweep/plot_sweep_params.py
```

Sweep metrics are written to `results/summary/`; parameter figures are written to `sweep/` and copied into `results/publication/` by the publication scripts.

---

## Reproducing the paper tables and figures

```bash
python report_occupation.py    # occupation-level comparison -> results/publication/
python report_publication.py   # parameter sensitivity, stage progression -> results/publication/
python export_latex.py         # LaTeX table fragments -> results/publication/tables/
python verify_paper_numbers.py # sanity-check all numbers cited in the paper
```

---

## Validation

Two validation approaches are documented in the paper:

**Approach 1 - Chain crosswalk agreement**:

```bash
cd validation && python validate_chain.py
```

Results: `validation/results/chain_eval_onet{tag}_overall.csv` (one file per selected release; tags: 251, 292, 303, 151, 200, 250)

**Approach 2 - Human expert annotation**:

```bash
# Generate workbook (then fill in expert_isco column)
cd validation && python generate_workbook.py

# After workbook is filled, evaluate
cd validation && python evaluate_annotations.py
```

The workbook intentionally excludes model predictions to avoid biasing annotation.

### Key validation results

| Metric | O*NET 29.2 |
|--------|-----------|
| Chain crosswalk agreement, lenient union | 68.0% exact; 88.4% major-group |
| Human expert annotation (n=108) | 36.1% exact; 57.4% sub-major; 72.2% major-group |

Chain crosswalk validation is available for all 63 releases. The O*NET 29.2 mapping assigns tasks to 435 of 436 ISCO-08 unit groups; the only missing group is ISCO 7516 (Tobacco Preparers and Tobacco Products Makers).

---

## Output format

Final crosswalk CSVs contain one row per retained task-ISCO link after the `S5_FINAL` stage. The current export intentionally writes a compact public-use schema:

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

Full intermediate stage files, including `run_id`, `stage`, `task_key`, `target_id`, `gap_1_k`, `topk_entropy`, `kept_reason`, and `task_text_hash`, are written under `results/predictions/<run_id>/`.

---

## Citation

If you use the crosswalks or code, please cite:

```bibtex
@article{einian2026onet,
  title  = {Mapping O*NET Tasks to ISCO Occupations using Text Similarity},
  author = {Einian, Majid},
  year   = {2026},
  note   = {Working paper}
}
```
