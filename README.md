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

Each task is assigned to exactly one ISCO-08 unit group. Coverage backfill ensures missing ISCO groups are represented using only unassigned tasks, so the one-to-one property is preserved throughout. Use the YAML configs in the repository for the current production settings.

Two datasets are covered:

| Config | O*NET release | SOC version | Output |
|--------|---------------|-------------|--------|
| `config_onet29.yaml` | 29.2 | SOC 2018 | `output/ONET29_task_to_ISCO_crosswalk.csv` |
| `config_onet25.yaml` | 25.0 | SOC 2010 | `output/ONET25_task_to_ISCO_crosswalk.csv` |

Current headline settings:

| Config | `w_soc_title` | `w_dwa` | `w_isco` | `w_isco_task` | `w_occ` | `max_links_per_task` |
|--------|---------------|---------|----------|---------------|---------|----------------------|
| `config_onet29.yaml` | 0.375 | 0.2656 | 0.375 | 0.7344 | 0.1562 | 1 |
| `config_onet25.yaml` | 0.375 | 0.2656 | 0.375 | 0.7344 | 0.1562 | 1 |

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
|-- config_onet29.yaml        # Production config - O*NET 29.2
|-- config_onet25.yaml        # Production config - O*NET 25.0
|
|-- 1_run_onet29.py           # Step 1a: run pipeline for O*NET 29.2
|-- 2_run_onet25.py           # Step 1b: run pipeline for O*NET 25.0
|-- 3_report_occupation.py    # Step 2: occupation-level comparison vs reference crosswalks
|-- 4_report_publication.py   # Step 3: generate publication tables and figures
|-- 5_export_latex.py         # Step 4: export tables to LaTeX
|-- verify_paper_numbers.py   # Verify all numbers cited in the paper
|
|-- sweep.py                  # Sweep engine (random configs, Pareto scoring)
|-- sweep/
|   |-- run_systematic_sweep_onet29.py # Adaptive iterative parameter sweep
|   |-- plot_sweep_params.py           # Parameter heatmaps
|   |-- _best_config.py                # Inspect best sweep configurations
|   |-- _sweep_stats.py                # Sweep diagnostics
|   `-- _trace_rounds.py               # Trace adaptive sweep rounds
|
|-- output/
|   |-- ONET29_task_to_ISCO_crosswalk.csv   # Pre-computed (O*NET 29.2)
|   `-- ONET25_task_to_ISCO_crosswalk.csv   # Pre-computed (O*NET 25.0)
|
|-- validation/
|   |-- shared.py                      # Shared paths and loaders
|   |-- validate_chain.py              # Approach 1: chain-crosswalk agreement
|   |-- generate_workbook.py           # Approach 2a: generate expert annotation workbook
|   |-- evaluate_annotations.py        # Approach 2b: evaluate filled workbook
|   `-- results/
|       |-- chain_eval_onet29_overall.csv
|       |-- chain_eval_onet25_overall.csv
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
- O*NET 29.2 -> extract `Task Statements.xlsx`, `Tasks to DWAs.xlsx`, `Task Categories.xlsx` into `data/onet/29_2/`
- O*NET 25.0 -> same files into `data/onet/25_0/`

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
python 1_run_onet29.py   # produces output/ONET29_task_to_ISCO_crosswalk.csv
python 2_run_onet25.py   # produces output/ONET25_task_to_ISCO_crosswalk.csv
```

Embeddings are cached in `checkpoints/` after the first run. Subsequent runs with the same data and model are near-instant.

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
python 3_report_occupation.py   # occupation-level comparison -> results/publication/
python 4_report_publication.py  # parameter sensitivity, stage progression -> results/publication/
python 5_export_latex.py        # LaTeX table fragments -> results/publication/tables/
python verify_paper_numbers.py  # sanity-check all numbers cited in the paper
```

---

## Validation

Two validation approaches are documented in the paper:

**Approach 1 - Chain crosswalk agreement**:

```bash
cd validation && python validate_chain.py
```

Results: `validation/results/chain_eval_onet29_overall.csv`, `validation/results/chain_eval_onet25_overall.csv`

**Approach 2 - Human expert annotation**:

```bash
# Generate workbook (then fill in expert_isco column)
cd validation && python generate_workbook.py

# After workbook is filled, evaluate
cd validation && python evaluate_annotations.py
```

The workbook intentionally excludes model predictions to avoid biasing annotation.

### Key validation results

| Metric | O*NET 29.2 | O*NET 25.0 |
|--------|-----------|-----------|
| Chain crosswalk agreement, lenient union | 68.0% exact; 88.4% major-group | 49.4% exact; 74.2% major-group |
| Human expert annotation (n=108) | 36.1% exact; 57.4% sub-major; 72.2% major-group | not evaluated |
| Current `w_soc_title` | 0.375 | 0.375 |

The final O*NET 29.2 mapping currently assigns tasks to 435 of 436 ISCO-08 unit groups. The missing unit group is ISCO 7516, Tobacco Preparers and Tobacco Products Makers.

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
