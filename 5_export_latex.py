from __future__ import annotations

from pathlib import Path
from typing import Callable

import pandas as pd

CROSSWALK_PATH = Path("output/ONET29_task_to_ISCO_crosswalk.csv")
ONET_TASKS_PATH = Path("data/onet/29_2/Task Statements.xlsx")
ONET_DWA_PATH = Path("data/onet/29_2/Tasks to DWAs.xlsx")


RESULTS_DIR = Path("results/publication")
GT_RESULTS_DIR = Path("validation/results")
TABLES_DIR = Path("results/publication/tables")
TABLES_DIR.mkdir(parents=True, exist_ok=True)

DATASET_LABELS = {
    "29.2-ID": "O*NET 29.2",
    "25.0-ID": "O*NET 25.0",
}

STAGE_LABELS = {
    "S1_RETRIEVE": "S1: Retrieve",
    "S2_TASK_FILTER": "S2: Task filter",
    "S3_COVERAGE": "S3: Coverage",
    "S4_OVERLOAD": "S4: Overload",
    "S5_FINAL": "S5: Final",
}

CROSSWALK_LABELS = {
    "XW18.1_esco_to_onetsoc": "ESCO-ONET-SOC (SOC18)",
    "XW18.2_onetsoc_to_esco": "ONET-SOC-ESCO (SOC18)",
    "XW10.1_esco_onet": "ESCO-ONET (MHV)",
    "XW10.2_isco_soc": "BLS ISCO-SOC",
}

SOC_VERSION_LABELS = {
    "soc10": "SOC 2010",
    "soc18": "SOC 2018",
}


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
    out["dataset_short"] = out["dataset_short"].map(DATASET_LABELS).fillna(out["dataset_short"])
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
    cols = [
        "dataset_short",
        "reference_crosswalk",
        "pair_precision_vs_ref",
        "pair_recall_vs_ref",
        "pair_f1_vs_ref",
        "top1_agreement_share",
        "top1_sub_major_share",
        "top1_major_group_share",
        "n_shared_soc",
    ]
    out = df[[c for c in cols if c in df.columns]].copy()
    out["dataset_short"] = out["dataset_short"].map(DATASET_LABELS).fillna(out["dataset_short"])
    out["reference_crosswalk"] = out["reference_crosswalk"].map(CROSSWALK_LABELS).fillna(out["reference_crosswalk"])
    out = out.rename(
        columns={
            "dataset_short": "Dataset",
            "reference_crosswalk": "Institutional crosswalk",
            "pair_precision_vs_ref": "Pair precision",
            "pair_recall_vs_ref": "Pair recall",
            "pair_f1_vs_ref": "Pair F1",
            "top1_agreement_share": "In-set (4-digit)",
            "top1_sub_major_share": "In-set (2-digit)",
            "top1_major_group_share": "In-set (1-digit)",
            "n_shared_soc": "Shared SOC n",
        }
    )
    for col in ["Pair precision", "Pair recall", "Pair F1", "In-set (4-digit)", "In-set (2-digit)", "In-set (1-digit)"]:
        if col in out.columns:
            out[col] = _fmt_float(out[col], 3)
    out["Shared SOC n"] = pd.to_numeric(out["Shared SOC n"], errors="coerce").fillna(0).astype(int)
    return out


def _reference_internal(df: pd.DataFrame) -> pd.DataFrame:
    cols = [
        "soc_version",
        "left_reference",
        "right_reference",
        "pair_precision_vs_ref",
        "pair_recall_vs_ref",
        "pair_f1_vs_ref",
        "top1_agreement_share",
        "top1_sub_major_share",
        "top1_major_group_share",
    ]
    out = df[[c for c in cols if c in df.columns]].copy()
    out["soc_version"] = out["soc_version"].map(SOC_VERSION_LABELS).fillna(out["soc_version"])
    out["left_reference"] = out["left_reference"].map(CROSSWALK_LABELS).fillna(out["left_reference"])
    out["right_reference"] = out["right_reference"].map(CROSSWALK_LABELS).fillna(out["right_reference"])
    out = out.rename(
        columns={
            "soc_version": "SOC version",
            "left_reference": "Reference A",
            "right_reference": "Reference B",
            "pair_precision_vs_ref": "Pair precision",
            "pair_recall_vs_ref": "Pair recall",
            "pair_f1_vs_ref": "Pair F1",
            "top1_agreement_share": "In-set (4-digit)",
            "top1_sub_major_share": "In-set (2-digit)",
            "top1_major_group_share": "In-set (1-digit)",
        }
    )
    for col in ["Pair precision", "Pair recall", "Pair F1", "In-set (4-digit)", "In-set (2-digit)", "In-set (1-digit)"]:
        if col in out.columns:
            out[col] = _fmt_float(out[col], 3)
    return out


def _overload_examples(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "dataset_short",
            "iscoGroup",
            "isco_title",
            "tasks_s3",
            "tasks_s4",
            "tasks_s5",
            "pruned_in_s4",
        ]
    ].copy()
    out["dataset_short"] = out["dataset_short"].map(DATASET_LABELS).fillna(out["dataset_short"])
    out = out.rename(
        columns={
            "dataset_short": "Dataset",
            "iscoGroup": "ISCO",
            "isco_title": "Occupation label",
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
            "implied_occupation_label",
            "isco_ref",
            "reference_isco_title",
            "imp_task_support",
            "imp_support_share",
        ]
    ].copy()
    out["dataset_short"] = out["dataset_short"].map(DATASET_LABELS).fillna(out["dataset_short"])
    out["reference_crosswalk"] = out["reference_crosswalk"].map(CROSSWALK_LABELS).fillna(out["reference_crosswalk"])
    # Combine ISCO code + title into a single readable cell
    out["Implied ISCO"] = out["isco_imp"].astype(str) + " " + out["implied_occupation_label"].fillna("")
    out["Reference ISCO"] = out["isco_ref"].astype(str) + " " + out["reference_isco_title"].fillna("")
    out = out.drop(columns=["isco_imp", "implied_occupation_label", "isco_ref", "reference_isco_title"])
    out = out.rename(
        columns={
            "dataset_short": "Dataset",
            "reference_crosswalk": "Reference",
            "soc_code": "SOC",
            "soc_title": "SOC title",
            "imp_task_support": "Task support",
            "imp_support_share": "Support share",
        }
    )
    # Reorder columns
    out = out[["Dataset", "Reference", "SOC", "SOC title", "Implied ISCO", "Reference ISCO", "Task support", "Support share"]]
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
            "isco_title",
            "similarity",
            "kept_reason",
        ]
    ].copy()
    out["dataset_short"] = out["dataset_short"].map(DATASET_LABELS).fillna(out["dataset_short"])
    out["stage_name"] = out["stage_name"].map(STAGE_LABELS).fillna(out["stage_name"])
    out = out.rename(
        columns={
            "dataset_short": "Dataset",
            "stage_name": "Stage",
            "task_id": "Task ID",
            "candidate_rank": "Rank",
            "iscoGroup": "ISCO",
            "isco_title": "Occupation label",
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
    out["dataset_short"] = out["dataset_short"].map(DATASET_LABELS).fillna(out["dataset_short"])
    out["stage"] = out["stage"].map(STAGE_LABELS).fillna(out["stage"])
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


# ── Task examples table (loaded directly from crosswalk + O*NET data) ─────────

def _task_examples_tex() -> str | None:
    """Generate task assignment examples table with full input data (task text,
    SOC occupation, DWA labels, ISCO assignment), one per ISCO major group."""
    for p in [CROSSWALK_PATH, ONET_TASKS_PATH, ONET_DWA_PATH]:
        if not p.exists():
            return None

    df_s5 = pd.read_csv(CROSSWALK_PATH)
    if "stage" in df_s5.columns:
        df_s5 = df_s5[df_s5["stage"] == "S5_FINAL"].copy()

    tasks = pd.read_excel(ONET_TASKS_PATH)
    dwa = pd.read_excel(ONET_DWA_PATH)

    # Join SOC occupation title
    task_soc = (
        tasks[["Task ID", "Title"]]
        .rename(columns={"Task ID": "task_id", "Title": "soc_title"})
        .drop_duplicates("task_id")
    )
    df_s5 = df_s5.merge(task_soc, on="task_id", how="left")

    # Aggregate DWA titles per task: top 2 unique labels, alphabetically
    dwa_agg = (
        dwa.groupby("Task ID")["DWA Title"]
        .apply(lambda x: "; ".join(sorted(set(x))[:2]))
        .reset_index()
        .rename(columns={"Task ID": "task_id", "DWA Title": "dwa_titles"})
    )
    df_s5 = df_s5.merge(dwa_agg, on="task_id", how="left")

    # Pick one example per ISCO major group: highest similarity
    df_s5["isco_major"] = df_s5["iscoGroup"].astype(str).str[0]
    sample = (
        df_s5.sort_values("similarity", ascending=False)
        .groupby("isco_major")
        .first()
        .reset_index()
        .sort_values("isco_major")
    )

    def _esc(s: str) -> str:
        """Escape LaTeX special characters in a string."""
        if not isinstance(s, str):
            return ""
        return (
            s.replace("&", r"\&")
             .replace("%", r"\%")
             .replace("_", r"\_")
             .replace("^", r"\^{}")
             .replace("#", r"\#")
             .replace("$", r"\$")
             .replace("{", r"\{")
             .replace("}", r"\}")
             .rstrip(".")
        )

    rows = []
    for _, row in sample.iterrows():
        task = _esc(str(row["task_text"]))
        soc = _esc(str(row["soc_title"]))
        dwa_str = _esc(str(row["dwa_titles"])) if pd.notna(row.get("dwa_titles")) else "---"
        isco = _esc(f"{int(row['iscoGroup'])} {row['isco_title']}")
        rows.append(f"    {task} & {soc} & {dwa_str} & {isco} \\\\")

    body = "\n\\midrule\n".join(rows)

    return (
        r"\begin{tabular}{p{4.5cm}p{3cm}p{3.5cm}p{3.5cm}}"
        "\n\\toprule\n"
        "O*NET Task & SOC Occupation & DWA Labels (top 2) & ISCO-08 Assignment \\\\\n"
        "\\midrule\n"
        + body
        + "\n\\bottomrule\n\\end{tabular}\n"
    )


# ── Ground-truth tables (read from GT_RESULTS_DIR, write raw LaTeX) ───────────

def _gt01_validation_tex() -> str | None:
    """Chain crosswalk validation longtable from gt01 overall CSVs."""
    p29 = GT_RESULTS_DIR / "chain_eval_onet29_overall.csv"
    p25 = GT_RESULTS_DIR / "chain_eval_onet25_overall.csv"
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
            .replace("∪", r"$\cup$")
            .replace("∩", r"$\cap$")
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
\emph{SOC 2018 (O*NET 29.2)} \\[2pt]
""" + rows29 + r"""
\midrule
\emph{SOC 2010 (O*NET 25.0)} \\[2pt]
""" + rows25 + r"""
\multicolumn{5}{l}{\footnotesize $^{a}$Less independent: derived via the same semantic similarity approach as the pipeline.}\\
\end{longtable}
\end{small}
\end{center}
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

    # Raw-tex tables generated directly from data
    for generator, tex_name in [
        (_gt01_validation_tex, "table_gt01_validation.tex"),
        (_task_examples_tex, "table_task_examples.tex"),
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
