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

SHOW_VERSIONS = {15.1, 20.0, 25.0, 25.1, 29.2, 30.3}

DATASET_LABELS = {
    "25.1-ID": "O*NET 25.1",
    "29.2-ID": "O*NET 29.2",
    "30.3-ID": "O*NET 30.3",
    "15.1-ID": "O*NET 15.1",
    "20.0-ID": "O*NET 20.0",
    "25.0-ID": "O*NET 25.0",
}

STAGE_LABELS = {
    "S1_RETRIEVE": "S1: Retrieve",
    "S2_TASK_FILTER": "S2: Task filter",
    "S3_COVERAGE": "S3: Coverage",
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


def _write_tex(df: pd.DataFrame, out_path: Path, longtable: bool = False,
               caption: str | None = None, label: str | None = None) -> None:
    df.to_latex(out_path, index=False, escape=True,
                longtable=longtable, caption=caption, label=label)


def _write_raw_tex(content: str, out_path: Path) -> None:
    out_path.write_text(content, encoding="utf-8")


def _baseline_s3(df: pd.DataFrame) -> pd.DataFrame:
    df = df[df["dataset_short"].isin(SHOW_VERSIONS)].copy()
    out = df[
        [
            "dataset_short",
            "S3_coverage",
            "S3_mean_similarity",
            "S3_mean_links_per_task",
            "S3_gini_tasks_per_isco",
        ]
    ].copy()
    out["dataset_short"] = out["dataset_short"].map(DATASET_LABELS).fillna(out["dataset_short"])
    out = out.rename(
        columns={
            "dataset_short": "Dataset",
            "S3_coverage": "Cov.",
            "S3_mean_similarity": "Sim.",
            "S3_mean_links_per_task": "Links",
            "S3_gini_tasks_per_isco": "Gini",
        }
    )
    for col in out.columns[1:]:
        out[col] = _fmt_float(out[col], 3)
    return out


def _sweep_top(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "selection_rank",
            "changed_param",
            "changed_value",
            "selection_score",
            "S3_COVERAGE_isco_coverage_share",
            "S3_COVERAGE_mean_similarity_retained",
            "S3_COVERAGE_gini_tasks_per_isco",
        ]
    ].copy()
    out = out.rename(
        columns={
            "selection_rank": "Rank",
            "changed_param": "Changed parameter",
            "changed_value": "Value",
            "selection_score": "Selection score",
            "S3_COVERAGE_isco_coverage_share": "S3 coverage",
            "S3_COVERAGE_mean_similarity_retained": "S3 mean similarity",
            "S3_COVERAGE_gini_tasks_per_isco": "S3 Gini",
        }
    )
    out["Rank"] = pd.to_numeric(out["Rank"], errors="coerce").fillna(0).astype(int)
    for col in ["Selection score", "S3 coverage", "S3 mean similarity", "S3 Gini"]:
        out[col] = _fmt_float(out[col], 3)
    return out


_PARAM_LABELS = {
    "w_dwa":       r"$w_{\text{dwa}}$",
    "w_soc_title": r"$w_{\text{soc}}$",
    "w_occ":       r"$w_{\text{occ}}$",
    "w_isco":      r"$w_{\text{isco}}$",
    "w_isco_task": r"$w_{\text{isco,task}}$",
}


def _sweep_param(df: pd.DataFrame) -> pd.DataFrame:
    out = df[
        [
            "parameter",
            "recommended_value",
            "selection_score",
            "S3_coverage",
            "S3_mean_similarity",
            "S3_gini_tasks_per_isco",
        ]
    ].copy()
    out["parameter"] = out["parameter"].map(lambda x: _PARAM_LABELS.get(x, x))
    out = out.rename(
        columns={
            "parameter": "Parameter",
            "recommended_value": "Recommended value",
            "selection_score": "Selection score",
            "S3_coverage": "S3 coverage",
            "S3_mean_similarity": "S3 mean similarity",
            "S3_gini_tasks_per_isco": "S3 Gini",
        }
    )
    for col in ["Selection score", "S3 coverage", "S3 mean similarity", "S3 Gini"]:
        out[col] = _fmt_float(out[col], 3)
    return out


_SELECTED_VERSIONS = {"15.1", "20.0", "25.0", "25.1", "29.2", "30.3"}


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
    # dataset_short is stored as float (e.g. 15.1, 29.2); filter to selected versions only
    ver_str = pd.to_numeric(out["dataset_short"], errors="coerce").apply(
        lambda v: f"{v:.1f}" if pd.notna(v) else ""
    )
    out = out[ver_str.isin(_SELECTED_VERSIONS)].copy()
    ver_str = ver_str[out.index]
    out["dataset_short"] = ver_str.apply(lambda s: f"O*NET {s}")
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
        ]
    ].copy()
    out["dataset_short"] = out["dataset_short"].map(DATASET_LABELS).fillna(out["dataset_short"])
    out = out.rename(
        columns={
            "dataset_short": "Dataset",
            "iscoGroup": "ISCO",
            "isco_title": "Occupation label",
            "tasks_s3": "Tasks",
        }
    )
    out["Occupation label"] = out["Occupation label"].str.slice(0, 32)
    out["Tasks"] = pd.to_numeric(out["Tasks"], errors="coerce").fillna(0).astype(int)
    return out


def _mismatch_tex() -> str | None:
    """Mismatch examples table with p{} columns for readable multiline cells."""
    src = RESULTS_DIR / "table_mismatch_examples.csv"
    if not src.exists():
        return None
    df = pd.read_csv(src)

    ver_str = pd.to_numeric(df["dataset_short"], errors="coerce").apply(
        lambda v: f"{v:.1f}" if pd.notna(v) else ""
    )
    df = df[ver_str.isin({"25.0", "29.2"})].copy()
    ver_str = ver_str[df.index]
    df = df.groupby(ver_str, group_keys=False).head(4)

    def _esc(s: object) -> str:
        if pd.isna(s):
            return ""
        return (str(s).replace("&", r"\&").replace("%", r"\%")
                .replace("_", r"\_").replace("#", r"\#").replace("$", r"\$"))

    # Group rows by version; emit a section header per version naming both crosswalks
    ERA_LABELS = {
        "25.0": r"O*NET~25.0 (SOC~2010): Ref.\,1\,=\,BLS ISCO-SOC;\enspace Ref.\,2\,=\,ESCO--O*NET",
        "29.2": r"O*NET~29.2 (SOC~2018): Ref.\,1\,=\,ONET-SOC-ESCO;\enspace Ref.\,2\,=\,ESCO--ONET-SOC",
    }
    sections = []
    for ver in ["25.0", "29.2"]:
        sub = df[ver_str == ver]
        if sub.empty:
            continue
        data_rows = []
        for idx, r in sub.iterrows():
            soc = f"{_esc(r['soc_code'])} {_esc(r['soc_title'])}"
            imp = f"{int(r['isco_imp'])}~{_esc(r['implied_occupation_label'])}"
            ref = f"{int(r['isco_ref'])}~{_esc(r['reference_isco_title'])}"
            ref2_raw = r.get("isco_ref2")
            ref2_title = r.get("reference_isco_title2")
            if pd.notna(ref2_raw) and pd.notna(ref2_title):
                ref2 = f"{int(float(ref2_raw))}~{_esc(ref2_title)}"
            else:
                ref2 = r"—"
            data_rows.append(f"    {soc} & {imp} & {ref} & {ref2} \\\\")
        header = f"    \\multicolumn{{4}}{{l}}{{\\emph{{{ERA_LABELS[ver]}}}}} \\\\[2pt]"
        sections.append(header + "\n" + "\n".join(data_rows))

    body = "\n\\midrule\n".join(sections)
    return (
        r"\begin{small}" + "\n"
        r"\begin{tabular}{p{3.5cm}p{4.5cm}p{4.5cm}p{4.0cm}}" + "\n"
        r"\toprule" + "\n"
        r"SOC occupation & Pipeline ISCO & Ref.~1 ISCO & Ref.~2 ISCO \\" + "\n"
        r"\midrule" + "\n"
        + body + "\n"
        r"\bottomrule" + "\n"
        r"\end{tabular}" + "\n"
        r"\end{small}" + "\n"
    )


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


def _baseline_stage_tex() -> str | None:
    src_path = RESULTS_DIR / "table_baseline_stage_metrics.csv"
    if not src_path.exists():
        return None
    df = pd.read_csv(src_path)
    df = df[df["dataset_short"].isin(SHOW_VERSIONS)].copy()
    df = df[df["stage"].notna()].copy()
    for col in ["isco_coverage_share", "mean_similarity_retained", "mean_links_per_task", "gini_tasks_per_isco"]:
        df[col] = _fmt_float(df[col], 3)
    rows_tex = []
    prev_dataset = None
    for _, row in df.iterrows():
        if prev_dataset is not None and row["dataset_short"] != prev_dataset:
            rows_tex.append(r"\midrule")
        dataset_label = f"O*NET {row['dataset_short']:.1f}"
        stage_label = STAGE_LABELS.get(row["stage"], row["stage"])
        rows_tex.append(
            f"{dataset_label} & {stage_label} & "
            f"{row['isco_coverage_share']} & {row['mean_similarity_retained']} & "
            f"{row['mean_links_per_task']} & {row['gini_tasks_per_isco']} \\\\"
        )
        prev_dataset = row["dataset_short"]
    body = "\n".join(rows_tex)
    return (
        r"""\begin{longtable}{rlllll}
\caption{Pipeline metrics by stage and dataset.} \label{tab:stage-metrics} \\
\toprule
Dataset & Stage & Cov. & Sim. & Links & Gini \\
\midrule
\endfirsthead
\caption[]{Pipeline metrics by stage and dataset.} \\
\toprule
Dataset & Stage & Cov. & Sim. & Links & Gini \\
\midrule
\endhead
\midrule
\multicolumn{6}{r}{\emph{Continued on next page}} \\
\endfoot
\bottomrule
\endlastfoot
"""
        + body
        + "\n"
        + r"""\end{longtable}
"""
    )


# ── Task examples table (loaded directly from crosswalk + O*NET data) ─────────

def _task_examples_tex() -> str | None:
    """Generate task assignment examples table with full input data (task text,
    SOC occupation, DWA labels, ISCO assignment), one per ISCO major group."""
    for p in [CROSSWALK_PATH, ONET_TASKS_PATH, ONET_DWA_PATH]:
        if not p.exists():
            return None

    df_s5 = pd.read_csv(CROSSWALK_PATH)
    if "stage" in df_s5.columns:
        df_s5 = df_s5[df_s5["stage"] == "S3_COVERAGE"].copy()

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
    """Chain crosswalk validation longtable: 3 SOC 2018 + 3 SOC 2010 releases."""
    SOC18_VERSIONS = [
        ("251", "SOC~2018 --- O*NET~25.1 (first SOC~2018 release)"),
        ("292", "SOC~2018 --- O*NET~29.2 (release used for parameter selection)"),
        ("303", "SOC~2018 --- O*NET~30.3 (latest release)"),
    ]
    SOC10_VERSIONS = [
        ("151", "SOC~2010 --- O*NET~15.1 (first SOC~2010 release)"),
        ("200", "SOC~2010 --- O*NET~20.0 (mid-era)"),
        ("250", "SOC~2010 --- O*NET~25.0 (last SOC~2010 release)"),
    ]

    all_versions = SOC18_VERSIONS + SOC10_VERSIONS
    # Check all required CSVs exist
    for tag, _ in all_versions:
        p = GT_RESULTS_DIR / f"chain_eval_onet{tag}_overall.csv"
        if not p.exists():
            return None

    def _row(r: pd.Series, is_soc10: bool) -> str:
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

    sections = []
    for i, (tag, header) in enumerate(all_versions):
        df = pd.read_csv(GT_RESULTS_DIR / f"chain_eval_onet{tag}_overall.csv")
        is_soc10 = tag in {t for t, _ in SOC10_VERSIONS}
        rows_list = [_row(r, is_soc10) for _, r in df.iterrows()]
        # Add footnote marker to B1 row (first row of SOC 2010 sections)
        if is_soc10 and rows_list:
            rows_list[0] = rows_list[0].replace("ESCO-ONET-MHV &", r"ESCO-ONET-MHV$^{a}$ &")
        sep = r"\midrule" + "\n" if i > 0 else ""
        sections.append(
            f"{sep}\\multicolumn{{5}}{{l}}{{\\emph{{{header}}}}} \\\\[2pt]\n" + "\n".join(rows_list)
        )

    body = "\n".join(sections)

    return r"""\begin{center}
\begin{small}
\begin{longtable}{lrrrr}
\caption{Chain crosswalk validation: match rates across scenarios and representative O*NET releases.}
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
""" + body + r"""
\multicolumn{5}{l}{\footnotesize $^{a}$Less independent: derived via the same semantic similarity approach as the pipeline.}\\
\end{longtable}
\end{small}
\end{center}
"""



# (src_csv, tex_name, transform, longtable, caption, label)
TABLE_SPECS: list[tuple] = [
    ("table_baseline_s3_summary.csv", "table_baseline_s3_summary.tex", _baseline_s3,
     True, "Final-stage (S3) summary metrics across all O*NET releases (v4.0--v30.3).", "tab:s3-summary"),
    ("table_sweep_top_configs.csv", "table_sweep_top_configs.tex", _sweep_top,
     False, None, None),
    ("table_sweep_parameter_recommendations.csv", "table_sweep_parameter_recommendations.tex", _sweep_param,
     False, None, None),
    ("table_occupation_level_comparison.csv", "table_occupation_level_comparison.tex", _occupation_cmp,
     False, None, None),
    ("table_reference_internal_comparison.csv", "table_reference_internal_comparison.tex", _reference_internal,
     False, None, None),
    ("table_overload_examples.csv", "table_overload_examples.tex", _overload_examples,
     True, r"ISCO-08 unit groups attracting the highest number of task assignments in the final output, shown for all O*NET releases.", "tab:overload"),
    ("table_stage_task_examples.csv", "table_stage_task_examples.tex", _stage_examples,
     False, None, None),
]


def main() -> None:
    written: list[Path] = []

    # Standard tables from results/publication/
    for src_name, tex_name, transform, use_longtable, cap, lbl in TABLE_SPECS:
        src_path = RESULTS_DIR / src_name
        if not src_path.exists():
            continue
        df = pd.read_csv(src_path)
        out_df = transform(df)
        out_path = TABLES_DIR / tex_name
        _write_tex(out_df, out_path, longtable=use_longtable, caption=cap, label=lbl)
        written.append(out_path)

    # Raw-tex tables generated directly from data
    for generator, tex_name in [
        (_gt01_validation_tex, "table_gt01_validation.tex"),
        (_mismatch_tex, "table_mismatch_examples.tex"),
        (_task_examples_tex, "table_task_examples.tex"),
        (_baseline_stage_tex, "table_baseline_stage_metrics.tex"),
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
