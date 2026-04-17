from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd


RESULTS_DIR = Path("results/publication")
GT_RESULTS_DIR = Path("ground_truth/results")
TABLES_DIR = Path("paper/tex/tables")
TABLES_DIR.mkdir(parents=True, exist_ok=True)


def _fmt_float(series: pd.Series, digits: int = 3) -> pd.Series:
    return pd.to_numeric(series, errors="coerce").map(lambda x: f"{x:.{digits}f}" if pd.notna(x) else "")


def _write_tex(df: pd.DataFrame, out_path: Path) -> None:
    df.to_latex(out_path, index=False, escape=True)


def _write_raw_tex(content: str, out_path: Path) -> None:
    out_path.write_text(content, encoding="utf-8")


def _baseline_s5(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "dataset_short",
            "S5_coverage",
            "S5_mean_similarity",
            "S5_mean_links_per_task",
            "S5_overloaded_task_share",
            "S5_gini_tasks_per_isco",
        ]
    ].copy()
    out = out.rename(
        columns={
            "dataset_short": "Dataset",
            "S5_coverage": "Coverage",
            "S5_mean_similarity": "Mean similarity",
            "S5_mean_links_per_task": "Mean links/task",
            "S5_overloaded_task_share": "Overloaded task share",
            "S5_gini_tasks_per_isco": "Gini",
        }
    )
    for col in out.columns[1:]:
        out[col] = _fmt_float(out[col], 3)
    return out


def _sweep_top(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "selection_rank",
            "run_id",
            "changed_param",
            "changed_value",
            "selection_score",
            "S5_FINAL_isco_coverage_share",
            "S5_FINAL_mean_similarity_retained",
            "S5_FINAL_share_tasks_in_overloaded_isco",
        ]
    ].copy()
    out = out.rename(
        columns={
            "selection_rank": "Rank",
            "run_id": "Run ID",
            "changed_param": "Changed parameter",
            "changed_value": "Value",
            "selection_score": "Selection score",
            "S5_FINAL_isco_coverage_share": "S5 coverage",
            "S5_FINAL_mean_similarity_retained": "S5 mean similarity",
            "S5_FINAL_share_tasks_in_overloaded_isco": "S5 overloaded share",
        }
    )
    out["Rank"] = pd.to_numeric(out["Rank"], errors="coerce").fillna(0).astype(int)
    for col in ["Selection score", "S5 coverage", "S5 mean similarity", "S5 overloaded share"]:
        out[col] = _fmt_float(out[col], 3)
    return out


def _sweep_param(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "parameter",
            "recommended_value",
            "selection_score",
            "S5_coverage",
            "S5_mean_similarity",
            "S5_overloaded_task_share",
        ]
    ].copy()
    out = out.rename(
        columns={
            "parameter": "Parameter",
            "recommended_value": "Recommended value",
            "selection_score": "Selection score",
            "S5_coverage": "S5 coverage",
            "S5_mean_similarity": "S5 mean similarity",
            "S5_overloaded_task_share": "S5 overloaded share",
        }
    )
    for col in ["Selection score", "S5 coverage", "S5 mean similarity", "S5 overloaded share"]:
        out[col] = _fmt_float(out[col], 3)
    return out


def _occupation_cmp(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "dataset_short",
            "reference_crosswalk",
            "pair_precision_vs_ref",
            "pair_recall_vs_ref",
            "pair_f1_vs_ref",
            "top1_agreement_share",
            "n_shared_soc",
        ]
    ].copy()
    out = out.rename(
        columns={
            "dataset_short": "Dataset",
            "reference_crosswalk": "Institutional crosswalk",
            "pair_precision_vs_ref": "Pair precision",
            "pair_recall_vs_ref": "Pair recall",
            "pair_f1_vs_ref": "Pair F1",
            "top1_agreement_share": "SOC top-1 agreement",
            "n_shared_soc": "Shared SOC n",
        }
    )
    for col in ["Pair precision", "Pair recall", "Pair F1", "SOC top-1 agreement"]:
        out[col] = _fmt_float(out[col], 3)
    out["Shared SOC n"] = pd.to_numeric(out["Shared SOC n"], errors="coerce").fillna(0).astype(int)
    return out


def _reference_internal(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "soc_version",
            "left_reference",
            "right_reference",
            "pair_precision_vs_ref",
            "pair_recall_vs_ref",
            "pair_f1_vs_ref",
            "top1_agreement_share",
        ]
    ].copy()
    out = out.rename(
        columns={
            "soc_version": "SOC version",
            "left_reference": "Reference A",
            "right_reference": "Reference B",
            "pair_precision_vs_ref": "Pair precision",
            "pair_recall_vs_ref": "Pair recall",
            "pair_f1_vs_ref": "Pair F1",
            "top1_agreement_share": "Top-1 agreement",
        }
    )
    for col in ["Pair precision", "Pair recall", "Pair F1", "Top-1 agreement"]:
        out[col] = _fmt_float(out[col], 3)
    return out


def _overload_examples(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "dataset_short",
            "iscoGroup",
            "occupationLabel",
            "tasks_s3",
            "tasks_s4",
            "tasks_s5",
            "pruned_in_s4",
        ]
    ].copy()
    out = out.rename(
        columns={
            "dataset_short": "Dataset",
            "iscoGroup": "ISCO",
            "occupationLabel": "Occupation label",
            "tasks_s3": "Tasks at S3",
            "tasks_s4": "Tasks at S4",
            "tasks_s5": "Tasks at S5",
            "pruned_in_s4": "Pruned in S4",
        }
    )
    for col in ["Tasks at S3", "Tasks at S4", "Tasks at S5", "Pruned in S4"]:
        out[col] = pd.to_numeric(out[col], errors="coerce").fillna(0).astype(int)
    return out


def _mismatch_examples(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "dataset_short",
            "reference_crosswalk",
            "soc_code",
            "soc_title",
            "isco_imp",
            "isco_ref",
            "imp_task_support",
            "imp_support_share",
        ]
    ].copy()
    out = out.rename(
        columns={
            "dataset_short": "Dataset",
            "reference_crosswalk": "Reference",
            "soc_code": "SOC",
            "soc_title": "SOC title",
            "isco_imp": "Implied ISCO",
            "isco_ref": "Reference ISCO",
            "imp_task_support": "Task support",
            "imp_support_share": "Support share",
        }
    )
    out["Task support"] = pd.to_numeric(out["Task support"], errors="coerce").fillna(0).astype(int)
    out["Support share"] = _fmt_float(out["Support share"], 3)
    return out


def _stage_examples(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "dataset_short",
            "stage_name",
            "task_id",
            "candidate_rank",
            "iscoGroup",
            "occupationLabel",
            "similarity",
            "kept_reason",
        ]
    ].copy()
    out = out.rename(
        columns={
            "dataset_short": "Dataset",
            "stage_name": "Stage",
            "task_id": "Task ID",
            "candidate_rank": "Rank",
            "iscoGroup": "ISCO",
            "occupationLabel": "Occupation label",
            "similarity": "Similarity",
            "kept_reason": "Reason",
        }
    )
    out["Rank"] = pd.to_numeric(out["Rank"], errors="coerce").fillna(0).astype(int)
    out["Similarity"] = _fmt_float(out["Similarity"], 3)
    return out


def _baseline_stage(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "dataset_short",
            "stage",
            "isco_coverage_share",
            "mean_similarity_retained",
            "mean_links_per_task",
            "share_tasks_in_overloaded_isco",
        ]
    ].copy()
    out = out.rename(
        columns={
            "dataset_short": "Dataset",
            "stage": "Stage",
            "isco_coverage_share": "Coverage",
            "mean_similarity_retained": "Mean similarity",
            "mean_links_per_task": "Mean links/task",
            "share_tasks_in_overloaded_isco": "Overloaded task share",
        }
    )
    for col in ["Coverage", "Mean similarity", "Mean links/task", "Overloaded task share"]:
        out[col] = _fmt_float(out[col], 3)
    return out


# ── Ground-truth tables (read from GT_RESULTS_DIR, write raw LaTeX) ───────────

def _gt01_validation_tex() -> str | None:
    """Chain crosswalk validation longtable from gt01 overall CSVs."""
    p29 = GT_RESULTS_DIR / "gt01_onet29_overall.csv"
    p25 = GT_RESULTS_DIR / "gt01_onet25_overall.csv"
    if not p29.exists() or not p25.exists():
        return None
    df29 = pd.read_csv(p29)
    df25 = pd.read_csv(p25)

    def _row(r: pd.Series) -> str:
        label = (
            r["label"]
            .replace("&", r"\&").replace("$", r"\$")
            .replace(" alone", "")
            .replace(" (semantic, less independent)", "")
        )
        return (
            f"    {label} & {r['pct_in_crosswalk']:.1f}"
            f" & {r['pct_exact']:.1f}"
            f" & {r['pct_sub_major']:.1f}"
            f" & {r['pct_major_group']:.1f} \\\\"
        )

    rows29 = "\n".join(_row(r) for _, r in df29.iterrows())
    rows25_list = [_row(r) for _, r in df25.iterrows()]
    # Add footnote marker to B1 (ESCO-ONET-MHV, less independent)
    if rows25_list:
        rows25_list[0] = rows25_list[0].replace("ESCO-ONET-MHV &", r"ESCO-ONET-MHV$^{a}$ &")
    rows25 = "\n".join(rows25_list)

    return r"""\begin{center}
\begin{small}
\begin{longtable}{lrrrr}
\caption{Chain crosswalk validation: match rates across scenarios.}
\label{tab:gt01-validation}\\
\toprule
Scenario & Cov.\ & Exact & Sub- & Major \\
         & (\%)  & (\%)  & major (\%) & group (\%) \\
\midrule
\endfirsthead
\multicolumn{5}{c}{\tablename\ \thetable{} -- continued}\\
\toprule
Scenario & Cov.\ & Exact & Sub- & Major \\
         & (\%)  & (\%)  & major (\%) & group (\%) \\
\midrule
\endhead
\midrule\multicolumn{5}{r}{\emph{Continued on next page}}\\
\endfoot
\bottomrule
\endlastfoot
\emph{SOC18 (O*NET 29.2-ID)} \\[2pt]
""" + rows29 + r"""
\midrule
\emph{SOC10 (O*NET 25.0-ID)} \\[2pt]
""" + rows25 + r"""
\multicolumn{5}{l}{\footnotesize $^{a}$Less independent: derived via the same semantic similarity approach as the pipeline.}\\
\end{longtable}
\end{small}
\end{center}
"""


def _gt02_hr_tex() -> str | None:
    """HR practitioner survey table from gt02 CSVs."""
    p_detail  = GT_RESULTS_DIR / "gt02_hr_task_detail.csv"
    p_summary = GT_RESULTS_DIR / "gt02_hr_summary.csv"
    if not p_detail.exists() or not p_summary.exists():
        return None
    detail  = pd.read_csv(p_detail)
    summary = pd.read_csv(p_summary)

    # Summary header line
    s = summary.iloc[0]
    summary_line = (
        f"Overall: n={int(s['n_tasks'])}, "
        f"coverage={s['pct_in_crosswalk']:.1f}\\%, "
        f"exact={s['pct_exact']:.1f}\\%, "
        f"sub-major={s['pct_sub_major']:.1f}\\%, "
        f"major-group={s['pct_major_group']:.1f}\\%"
    )

    def _trunc(text: str, n: int = 45) -> str:
        text = str(text).replace("&", r"\&").replace("%", r"\%").replace("_", r"\_")
        return text[:n] + r"\ldots{}" if len(text) > n else text

    def _yn(val: object) -> str:
        return "Yes" if str(val).strip().lower() in ("true", "yes", "1") else "No"

    rows = []
    for _, r in detail.iterrows():
        survey_num = str(r['survey_task_num']).replace("_", r"\_")
        rows.append(
            f"    {_trunc(r['task_text'])} & {int(r['task_id'])} & {survey_num}"
            f" & {int(r['isco_pred'])} & {float(r['similarity']):.2f}"
            f" & {_yn(r['match_exact'])} & {_yn(r['match_sub_major'])} \\\\"
        )

    return r"""\begin{table}[H]
\centering
\caption{HR practitioner survey validation: pipeline predictions for recruitment tasks.}
\label{tab:gt02-hr}
\begin{small}
\begin{tabular}{p{5.5cm}rrp{2.2cm}rcc}
\toprule
Task text (truncated) & Task & Survey & ISCO & Similarity & Exact & Sub- \\
                      & ID   & Num    & pred &            & match & major \\
\midrule
\multicolumn{7}{l}{\emph{""" + summary_line + r"""}} \\
\midrule
""" + "\n".join(rows) + r"""
\bottomrule
\end{tabular}
\end{small}
\end{table}
"""


TABLE_SPECS: list[tuple[str, str, Callable[[pd.DataFrame], pd.DataFrame]]] = [
    ("table_baseline_s5_summary.csv", "table_baseline_s5_summary.tex", _baseline_s5),
    ("table_sweep_top_configs.csv", "table_sweep_top_configs.tex", _sweep_top),
    ("table_sweep_parameter_recommendations.csv", "table_sweep_parameter_recommendations.tex", _sweep_param),
    ("table_occupation_level_comparison.csv", "table_occupation_level_comparison.tex", _occupation_cmp),
    ("table_reference_internal_comparison.csv", "table_reference_internal_comparison.tex", _reference_internal),
    ("table_overload_examples.csv", "table_overload_examples.tex", _overload_examples),
    ("table_mismatch_examples.csv", "table_mismatch_examples.tex", _mismatch_examples),
    ("table_stage_task_examples.csv", "table_stage_task_examples.tex", _stage_examples),
    ("table_baseline_stage_metrics.csv", "table_baseline_stage_metrics.tex", _baseline_stage),
]


def main() -> None:
    written: list[Path] = []

    # Standard tables from results/publication/
    for src_name, tex_name, transform in TABLE_SPECS:
        src_path = RESULTS_DIR / src_name
        if not src_path.exists():
            continue
        df = pd.read_csv(src_path)
        out_df = transform(df)
        out_path = TABLES_DIR / tex_name
        _write_tex(out_df, out_path)
        written.append(out_path)

    # Ground-truth tables from ground_truth/results/
    for generator, tex_name in [
        (_gt01_validation_tex, "table_gt01_validation.tex"),
        (_gt02_hr_tex,         "table_gt02_hr.tex"),
    ]:
        content = generator()
        if content is None:
            print(f"SKIP {tex_name} (source CSVs not found in {GT_RESULTS_DIR})")
            continue
        out_path = TABLES_DIR / tex_name
        _write_raw_tex(content, out_path)
        written.append(out_path)

    for path in written:
        print(path)


if __name__ == "__main__":
    main()
