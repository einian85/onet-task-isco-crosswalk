"""
run_embedding_comparison.py
===========================
Runs the O*NET-to-ISCO pipeline on O*NET 29.2 with two alternative sentence
encoders (BAAI/bge-large-en-v1.5 and thenlper/gte-large), keeping all
production weights unchanged, then validates each against the lenient-union
SOC-2018 benchmark (scenario A4) and writes a comparison table.

Outputs:
  validation/results/embedding_model_comparison.csv
  results/publication/tables/table_embedding_model_comparison.tex

Run from the project root (conda env onet-isco-nlp):
    conda run -n onet-isco-nlp python run_embedding_comparison.py
"""

from __future__ import annotations

import sys
import subprocess
from pathlib import Path

import pandas as pd

sys.path.insert(0, str(Path(__file__).resolve().parent / "validation"))
from shared import (
    load_soc18_crosswalks,
    load_onet_tasks,
    evaluate_match,
    summarise_match,
)

# ── Configuration ──────────────────────────────────────────────────────────────

MODELS = [
    {
        "label":   "all-mpnet-base-v2",
        "config":  None,  # production run already exists; skip re-run
        "output":  "output/ONET292_task_to_ISCO_crosswalk.csv",
    },
    {
        "label":   "BAAI/bge-large-en-v1.5",
        "config":  "configs/config_onet292_bge.yaml",
        "output":  "output/ONET292_bge_task_to_ISCO_crosswalk.csv",
    },
    {
        "label":   "thenlper/gte-large",
        "config":  "configs/config_onet292_gte.yaml",
        "output":  "output/ONET292_gte_task_to_ISCO_crosswalk.csv",
    },
]

# ── Pipeline runner ────────────────────────────────────────────────────────────

def run_pipeline(config_path: str, output_path: str) -> None:
    out = Path(output_path)
    if out.exists():
        print(f"  Output exists — skipping: {output_path}")
        return
    print(f"\n{'='*60}")
    print(f"  Running pipeline: {config_path}")
    print(f"{'='*60}")
    subprocess.run([sys.executable, "pipeline.py", config_path], check=True)


# ── Loader ────────────────────────────────────────────────────────────────────

def load_crosswalk(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "iscoGroup" in df.columns:
        df = df.rename(columns={"iscoGroup": "isco_pred"})
    df["isco_pred"] = pd.to_numeric(df["isco_pred"], errors="coerce").astype("Int64")
    df["task_id"]   = pd.to_numeric(df["task_id"],   errors="coerce").astype("Int64")
    # Keep only the best assignment per task (is_best flag or take first)
    if "is_best" in df.columns:
        df = df[df["is_best"] == True].copy()
    return df.reset_index(drop=True)


# ── Validator ─────────────────────────────────────────────────────────────────

def validate_model(output_path: str, label: str) -> dict:
    df_pipe  = load_crosswalk(output_path)
    df_tasks = load_onet_tasks("29.2")
    xw18     = load_soc18_crosswalks()

    # Scenario A4: lenient union of both SOC-2018 crosswalks
    xw_a4 = (
        pd.concat([
            xw18["xw18_1"][["soc_code18", "isco_code"]],
            xw18["xw18_2"][["soc_code18", "isco_code"]],
        ])
        .drop_duplicates()
        .reset_index(drop=True)
    )

    ev   = evaluate_match(df_pipe, df_tasks, xw_a4, "soc_code18")
    summ = summarise_match(ev, label).iloc[0]

    n_groups = int(df_pipe["isco_pred"].dropna().nunique())
    mean_sim = (
        round(float(df_pipe["similarity"].mean()), 3)
        if "similarity" in df_pipe.columns else float("nan")
    )

    return {
        "model":             label,
        "isco_groups":       n_groups,
        "mean_sim":          mean_sim,
        "pct_coverage":      float(summ["pct_in_crosswalk"]),
        "pct_exact":         float(summ["pct_exact"]),
        "pct_sub_major":     float(summ["pct_sub_major"]),
        "pct_major_group":   float(summ["pct_major_group"]),
    }


# ── LaTeX writer ───────────────────────────────────────────────────────────────

def write_latex_table(rows: list[dict], out_path: Path) -> None:
    # Short model name for display
    def short(m: str) -> str:
        return m.replace("BAAI/", "").replace("thenlper/", "")

    lines = [
        r"\begin{tabular}{lrrrrrr}",
        r"\toprule",
        r"Encoder & ISCO & Mean & Cov.\ & Exact & Sub-major & Major \\",
        r"        & groups & sim. & (\%) & (\%) & (\%) & (\%) \\",
        r"\midrule",
    ]
    for i, r in enumerate(rows):
        suffix = r" \quad \emph{(production)}" if i == 0 else ""
        lines.append(
            f"{short(r['model'])}{suffix} & "
            f"{r['isco_groups']} & "
            f"{r['mean_sim']:.3f} & "
            f"{r['pct_coverage']:.1f} & "
            f"{r['pct_exact']:.1f} & "
            f"{r['pct_sub_major']:.1f} & "
            f"{r['pct_major_group']:.1f} \\\\"
        )
    lines += [
        r"\bottomrule",
        r"\multicolumn{7}{l}{\footnotesize "
        r"Validation: O*NET 29.2, SOC~2018, scenario A4 (lenient union). "
        r"All models use identical production weights. "
        r"Mean similarity is not directly comparable across models.}",
        r"\end{tabular}",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nLaTeX table written: {out_path}")


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    # Step 1: run pipeline for alternative models (skip if output already exists)
    for m in MODELS:
        if m["config"] is not None:
            run_pipeline(m["config"], m["output"])

    # Step 2: validate all three models
    print("\n" + "="*60)
    print("Validating all models (O*NET 29.2, scenario A4) …")
    print("="*60)
    results = []
    for m in MODELS:
        print(f"\n  {m['label']}")
        row = validate_model(m["output"], m["label"])
        results.append(row)
        print(
            f"    Exact: {row['pct_exact']:.1f}%  Sub-major: {row['pct_sub_major']:.1f}%  "
            f"Major: {row['pct_major_group']:.1f}%  "
            f"Groups: {row['isco_groups']}  MeanSim: {row['mean_sim']:.3f}"
        )

    # Step 3: save CSV
    csv_path = Path("validation/results/embedding_model_comparison.csv")
    pd.DataFrame(results).to_csv(csv_path, index=False)
    print(f"\nCSV saved: {csv_path}")

    # Step 4: write LaTeX table
    tex_path = Path("results/publication/tables/table_embedding_model_comparison.tex")
    write_latex_table(results, tex_path)

    print("\nDone.")


if __name__ == "__main__":
    main()
