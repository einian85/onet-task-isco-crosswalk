# O*NET Task -> ISCO-08 Crosswalk

Code and data for the NLP-based O*NET task-ISCO-08 crosswalk described in:

> Einian, M.  
> 2026.  
> Mapping O*NET Tasks to ISCO Occupations using Text Similarity  
> [in submission process]

Pre-computed crosswalk files are in [`output/`](output/). The sections below describe how to reproduce them from scratch.

---

## What this does

Each O*NET task statement is mapped to one or more ISCO-08 4-digit unit groups using dual-side Sentence-BERT (`all-mpnet-base-v2`) embeddings and FAISS retrieval. The query embedding blends the task text with the SOC occupation title; the target embedding blends the ISCO-08 official task descriptions, ESCO occupation text, and ESCO skills. Candidates pass through five filtering stages: retrieval -> task-filter -> coverage -> overload -> final.

Production parameters are still being tuned. Use the YAML configs in the repository for the current settings.

Two datasets are covered:

| Config | O*NET release | SOC version | Output |
|--------|---------------|-------------|--------|
| `config_onet29.yaml` | 29.2 | SOC 2018 | `output/ONET29_task_to_ISCO_crosswalk.csv` |
| `config_onet25.yaml` | 25.0 | SOC 2010 | `output/ONET25_task_to_ISCO_crosswalk.csv` |

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
|   |-- 1_run_sweep_onet29.py          # 500-point random parameter sweep (ONET29)
|   |-- 2_run_focused_sweep_onet29.py  # Focused 2D grid + random sweep (ONET29)
|   |-- 3_visualize_sweep.py           # Heatmaps and Pareto plots
|   |-- sweep_random.yaml              # Random sweep parameter spec
|   |-- sweep_focused.yaml             # Focused sweep parameter spec
|   `-- sweep_oat.yaml                 # One-at-a-time sensitivity spec
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
# Step 1: 500-point random sweep (ONET29)
python sweep/1_run_sweep_onet29.py

# Step 2: Focused 2D grid + random sweep around the region of interest
python sweep/2_run_focused_sweep_onet29.py

# Step 3: Visualize sweep results
python sweep/3_visualize_sweep.py   # -> results/summary/sweep_visualizations/*.png
```

Sweep metrics and figures go to `results/summary/` and `results/summary/sweep_visualizations/`.

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
| Chain crosswalk agreement (exact) | 88.2% | see `chain_eval_onet25_overall.csv` |
| Human expert annotation (exact, n=108) | 61.1% (81.5% at major-group level) | not evaluated |
| Optimal `w_soc_title` | under active tuning | under active tuning |

---

## Output format

Both crosswalk CSVs share the same schema. Each row is one task-ISCO candidate link at pipeline stage `S5_FINAL`:

| Column | Description |
|--------|-------------|
| `run_id` | Hash identifying the pipeline run |
| `stage` | Pipeline stage (`S5_FINAL` = kept after all filters) |
| `task_key` | Task key used internally by the pipeline |
| `task_id` | O*NET Task ID |
| `task_text` | Task statement text |
| `candidate_rank` | Rank of the retained ISCO candidate for that task |
| `iscoGroup` | 4-digit ISCO-08 unit group |
| `target_id` | Internal target identifier (same as `iscoGroup`) |
| `isco_title` | ISCO occupation label |
| `similarity` | Cosine similarity score |
| `task_best_similarity` | Best retrieval similarity for the task before filtering |
| `task_best_target` | Best retrieval target before filtering |
| `gap_1_2` | Similarity gap between the top-1 and top-2 retrieved targets |
| `gap_1_k` | Similarity gap between the top-1 and top-k retrieved targets |
| `topk_entropy` | Softmax entropy across the retrieved candidates |
| `is_best` | Whether the row is the task's best-scoring retained target |
| `kept_reason` | Why the row survived the filtering pipeline |
| `task_text_hash` | Stable hash of the original task text |

---

## Citation

If you use the crosswalks or code, please cite:

```bibtex
@article{[cite key],
  title   = {[Title]},
  author  = {[Authors]},
  journal = {[Journal]},
  year    = {[Year]},
}
```
