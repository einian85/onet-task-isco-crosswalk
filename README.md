# O*NET Task → ISCO-08 Crosswalk

Code and data for the NLP-based O*NET task–ISCO-08 crosswalk described in:

> **[Paper title]**
> [Authors]
> [Journal/conference, year]

Pre-computed crosswalk files are in [`output/`](output/). The sections below describe how to reproduce them from scratch.

---

## What this does

Each O\*NET task statement is mapped to one or more ISCO-08 4-digit unit groups using dual-side Sentence-BERT (`all-mpnet-base-v2`) embeddings and FAISS retrieval. The query embedding blends the task text with the SOC occupation title (`w_soc_title = 0.75`); the target embedding blends the ISCO-08 official task descriptions, ESCO occupation text, and ESCO skills. Candidates pass through five filtering stages (retrieval → task-filter → coverage → overload → final).

Two datasets are covered:

| Config | O\*NET release | SOC version | Output |
|--------|---------------|-------------|--------|
| `config_onet29.yaml` | 29.2 | SOC 2018 | `output/ONET29_task_to_ISCO_crosswalk.csv` |
| `config_onet25.yaml` | 25.0 | SOC 2010 | `output/ONET25_task_to_ISCO_crosswalk.csv` |

---

## Repository layout

```
.
├── pipeline.py               # Core NLP pipeline (embedding, retrieval, filtering)
├── config.py                 # RunConfig dataclass (all parameters)
├── evaluate.py               # Evaluation utilities
├── metrics_unsup.py          # Unsupervised similarity metrics
├── stability.py              # Cross-run stability analysis
│
├── config_onet29.yaml        # Production config – O*NET 29.2
├── config_onet25.yaml        # Production config – O*NET 25.0
│
├── 1_run_onet29.py           # Step 1a: run pipeline for O*NET 29.2
├── 2_run_onet25.py           # Step 1b: run pipeline for O*NET 25.0
├── 3_report_occupation.py    # Step 2:  occupation-level comparison vs reference crosswalks
├── 4_report_publication.py   # Step 3:  generate publication tables and figures
├── 5_export_latex.py         # Step 4:  export tables to LaTeX
├── verify_paper_numbers.py   # Verify all numbers cited in the paper
│
├── output/
│   ├── ONET29_task_to_ISCO_crosswalk.csv   # Pre-computed (O*NET 29.2)
│   └── ONET25_task_to_ISCO_crosswalk.csv   # Pre-computed (O*NET 25.0)
│
├── validation/
│   ├── shared.py                      # Shared paths and loaders
│   ├── validate_chain.py              # Approach 1: chain-crosswalk agreement
│   ├── generate_workbook.py           # Approach 3a: generate expert annotation workbook
│   ├── evaluate_annotations.py        # Approach 3b: evaluate filled workbook
│   └── results/
│       ├── chain_eval_onet29_overall.csv
│       ├── chain_eval_onet25_overall.csv
│       ├── human_eval_onet29.csv
│       ├── human_eval_onet29_summary.csv
│       ├── annotation_workbook_onet29.xlsx
│       └── weight_sweep_overall.csv / .png
│
└── data/                      # Not included — download instructions below
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

**O\*NET** (https://www.onetcenter.org/database.html):
- O\*NET 29.2 → extract `Task Statements.xlsx`, `Tasks to DWAs.xlsx`, `Task Categories.xlsx` into `data/onet/29_2/`
- O\*NET 25.0 → same files into `data/onet/25_0/`

**ESCO v1.2** (https://esco.ec.europa.eu/en/use-esco/download):
- Download English CSV bulk download → place `occupations_en.csv`, `skills_en.csv`, `occupationSkillRelations_en.csv` into `data/esco/`

**ISCO-08** (https://www.ilo.org/public/english/bureau/stat/isco/isco08/):
- `ISCO-08 EN Structure and definitions.xlsx` → `data/isco/`

**Reference crosswalks** (for validation only):
- ESCO–O\*NET crosswalk → `data/crosswalks/esco_onet_crosswalk-1680.xlsx`
- ISCO-08–SOC 2010 crosswalk → `data/crosswalks/isco08_soc10_crosswalk-1125.xls`
- ESCO–O\*NET-SOC (8627 rows) → `data/crosswalks/ESCO_to_ONET-SOC-8627.xlsx`
- O\*NET-SOC–ESCO (4253 rows) → `data/crosswalks/ONET-SOC-to-ESCO-4253.xlsx`

---

## Reproducing the crosswalks

Run from the repository root:

```bash
python 1_run_onet29.py   # produces output/ONET29_task_to_ISCO_crosswalk.csv
python 2_run_onet25.py   # produces output/ONET25_task_to_ISCO_crosswalk.csv
```

Embeddings are cached in `checkpoints/` after the first run (~40 min on CPU). Subsequent runs with the same data and model are near-instant.

---

## Reproducing the paper tables and figures

```bash
python 3_report_occupation.py   # occupation-level comparison → results/publication/
python 4_report_publication.py  # parameter sensitivity, stage progression → results/publication/
python 5_export_latex.py        # LaTeX table fragments → paper/tex/tables/
python verify_paper_numbers.py  # sanity-check all numbers cited in the paper
```

---

## Validation

Three validation approaches are documented in the paper:

**Approach 1 — Chain crosswalk agreement** (automated):
```bash
cd validation && python validate_chain.py
```
Results: `validation/results/chain_eval_onet29_overall.csv`, `chain_eval_onet25_overall.csv`

**Approach 3 — Human expert annotation**:
```bash
# Generate workbook (then fill in expert_isco column)
cd validation && python generate_workbook.py

# After workbook is filled, evaluate
cd validation && python evaluate_annotations.py
```
Pre-filled workbook and results: `validation/results/annotation_workbook_onet29.xlsx`, `human_eval_onet29.csv`

### Key validation results

| Metric | O*NET 29.2 | O*NET 25.0 |
|--------|-----------|-----------|
| Chain crosswalk agreement (exact) | 88.2% | — |
| Human expert agreement (exact, n=108) | 82.4% | — |
| Optimal `w_soc_title` | 0.75 | 0.75 |

---

## Output format

Both crosswalk CSVs share the same schema. Each row is one task–ISCO candidate link at pipeline stage `S5_FINAL`:

| Column | Description |
|--------|-------------|
| `task_id` | O\*NET Task ID |
| `task_text` | Task statement text |
| `soc_code` | 6-digit SOC code |
| `iscoGroup` | 4-digit ISCO-08 unit group |
| `occupationLabel` | ISCO occupation label(s) |
| `similarity` | Cosine similarity score |
| `stage` | Pipeline stage (`S5_FINAL` = kept after all filters) |
| `run_id` | Hash identifying the pipeline run |

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
