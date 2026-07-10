"""
run_ablation.py
===============
Runs four ablation variants of the O*NET-to-ISCO pipeline (all using cached
all-mpnet-base-v2 embeddings, so very fast), validates each against the
lenient-union SOC-2018 benchmark (scenario A4, O*NET 29.2), and writes a
comparison table for Appendix A.

Ablations:
  no_soc      w_soc_title=0.0        remove SOC occupation title from query
  no_dwa      w_dwa=0.0              remove DWA labels from query
  no_esco     w_isco=1.0             target = pure ISCO-08 (no ESCO)
  task_only   w_soc_title=0, w_dwa=0 raw task text only, no occupational context

Outputs:
  validation/results/ablation_comparison.csv
  results/publication/tables/table_ablation.tex

Run from the project root (conda env onet-isco-nlp):
    conda run -n onet-isco-nlp python run_ablation.py
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

VARIANTS = [
    {
        "label":       "Production (all components)",
        "config":      None,
        "output":      "output/ONET292_task_to_ISCO_crosswalk.csv",
        "query_desc":  "SOC title + task + DWA",
        "target_desc": "ISCO + ESCO",
    },
    {
        "label":       "No SOC title",
        "config":      "configs/config_onet292_abl_no_soc.yaml",
        "output":      "output/ONET292_abl_no_soc_task_to_ISCO_crosswalk.csv",
        "query_desc":  "task + DWA only",
        "target_desc": "ISCO + ESCO",
    },
    {
        "label":       "No DWA labels",
        "config":      "configs/config_onet292_abl_no_dwa.yaml",
        "output":      "output/ONET292_abl_no_dwa_task_to_ISCO_crosswalk.csv",
        "query_desc":  "SOC title + task",
        "target_desc": "ISCO + ESCO",
    },
    {
        "label":       "No ESCO (ISCO-08 only)",
        "config":      "configs/config_onet292_abl_no_esco.yaml",
        "output":      "output/ONET292_abl_no_esco_task_to_ISCO_crosswalk.csv",
        "query_desc":  "SOC title + task + DWA",
        "target_desc": "ISCO only",
    },
    {
        "label":       "Task text only",
        "config":      "configs/config_onet292_abl_task_only.yaml",
        "output":      "output/ONET292_abl_task_only_task_to_ISCO_crosswalk.csv",
        "query_desc":  "task text only",
        "target_desc": "ISCO + ESCO",
    },
]


def run_pipeline(config_path: str, output_path: str) -> None:
    if Path(output_path).exists():
        print(f"  Exists — skipping: {output_path}")
        return
    print(f"\n{'='*60}\n  Running: {config_path}\n{'='*60}")
    subprocess.run([sys.executable, "pipeline.py", config_path], check=True)


def load_crosswalk(path: str) -> pd.DataFrame:
    df = pd.read_csv(path)
    if "iscoGroup" in df.columns:
        df = df.rename(columns={"iscoGroup": "isco_pred"})
    df["isco_pred"] = pd.to_numeric(df["isco_pred"], errors="coerce").astype("Int64")
    df["task_id"]   = pd.to_numeric(df["task_id"],   errors="coerce").astype("Int64")
    if "is_best" in df.columns:
        df = df[df["is_best"] == True]
    return df.reset_index(drop=True)


def validate(output_path: str, label: str) -> dict:
    df_pipe  = load_crosswalk(output_path)
    df_tasks = load_onet_tasks("29.2")
    xw18     = load_soc18_crosswalks()
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
    mean_sim = round(float(df_pipe["similarity"].mean()), 3) if "similarity" in df_pipe.columns else float("nan")
    return {
        "label":           label,
        "isco_groups":     n_groups,
        "mean_sim":        mean_sim,
        "pct_coverage":    float(summ["pct_in_crosswalk"]),
        "pct_exact":       float(summ["pct_exact"]),
        "pct_sub_major":   float(summ["pct_sub_major"]),
        "pct_major_group": float(summ["pct_major_group"]),
    }


def write_latex(rows: list[dict], variants: list[dict], out_path: Path) -> None:
    lines = [
        r"\begin{tabular}{llllrrrr}",
        r"\toprule",
        r"Variant & Query side & Target side & ISCO & Mean & Exact & Sub- & Major \\",
        r"        &            &             & groups & sim. & (\%) & major (\%) & (\%) \\",
        r"\midrule",
    ]
    for r, v in zip(rows, variants):
        suffix = r" \emph{(production)}" if v["config"] is None else ""
        lines.append(
            f"{r['label']}{suffix} & "
            f"{v['query_desc']} & "
            f"{v['target_desc']} & "
            f"{r['isco_groups']} & "
            f"{r['mean_sim']:.3f} & "
            f"{r['pct_exact']:.1f} & "
            f"{r['pct_sub_major']:.1f} & "
            f"{r['pct_major_group']:.1f} \\\\"
        )
    lines += [
        r"\bottomrule",
        r"\multicolumn{8}{l}{\footnotesize "
        r"Validation: O*NET 29.2, SOC~2018, scenario A4 (lenient union). "
        r"All variants use identical threshold parameters ($\tau=0.45$, $\delta=0.03$).}",
        r"\end{tabular}",
    ]
    out_path.write_text("\n".join(lines), encoding="utf-8")
    print(f"\nLaTeX table written: {out_path}")


def main() -> None:
    # Step 1: run ablation pipelines (all use cached embeddings — fast)
    for v in VARIANTS:
        if v["config"] is not None:
            run_pipeline(v["config"], v["output"])

    # Step 2: validate
    print("\n" + "="*60)
    print("Validating ablation variants (O*NET 29.2, scenario A4) …")
    print("="*60)
    results = []
    for v in VARIANTS:
        print(f"\n  {v['label']}")
        row = validate(v["output"], v["label"])
        results.append(row)
        print(
            f"    Exact: {row['pct_exact']:.1f}%  Sub-major: {row['pct_sub_major']:.1f}%  "
            f"Major: {row['pct_major_group']:.1f}%  Groups: {row['isco_groups']}  "
            f"MeanSim: {row['mean_sim']:.3f}"
        )

    # Step 3: save CSV
    csv_path = Path("validation/results/ablation_comparison.csv")
    pd.DataFrame(results).to_csv(csv_path, index=False)
    print(f"\nCSV saved: {csv_path}")

    # Step 4: write LaTeX table
    tex_path = Path("results/publication/tables/table_ablation.tex")
    write_latex(results, VARIANTS, tex_path)

    print("\nDone.")


if __name__ == "__main__":
    main()
