"""
compare_onet29_candidates.py
============================
Materialize and compare a short list of ONET29 candidate configs.

Outputs written to validation/results/:
  - onet29_candidate_chain_overall.csv
  - onet29_candidate_chain_lenient_union.csv
  - onet29_candidate_human_eval.csv
  - onet29_candidate_comparison.csv

Run from the project root:
    python validation/compare_onet29_candidates.py
"""

from __future__ import annotations

from dataclasses import replace
from pathlib import Path

import matplotlib
import matplotlib.pyplot as plt
import pandas as pd

import sys

sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
sys.path.insert(0, str(Path(__file__).resolve().parent))

from config import load_config
from pipeline import run_pipeline
from shared import (
    GT_RESULTS_DIR,
    PROJECT_DIR,
    evaluate_match,
    load_onet_tasks,
    load_pipeline,
    load_soc18_crosswalks,
    summarise_match,
)

matplotlib.use("Agg")

CANDIDATE_DIR = PROJECT_DIR / "output" / "candidates"
CANDIDATE_DIR.mkdir(parents=True, exist_ok=True)
PUBLICATION_DIR = PROJECT_DIR / "results" / "publication"
PUBLICATION_DIR.mkdir(parents=True, exist_ok=True)
PUBLICATION_TABLE_DIR = PUBLICATION_DIR / "tables"
PUBLICATION_TABLE_DIR.mkdir(parents=True, exist_ok=True)

DISPLAY_NAMES: dict[str, str] = {
    # Joint fine-sweep candidates (Phase 6)
    "jf_d030_s675_i80_t60_o60": "C1$^*$ ($w_\\text{dwa}$=3.0\\%, $w_\\text{soc}$=67.5\\%)",
    "jf_d030_s675_i80_t57_o60": "C2 ($w_\\text{itsk}$=57.5\\%)",
    "jf_d030_s675_i75_t60_o60": "C3 ($w_\\text{isco}$=75\\%)",
    "jf_d050_s675_i75_t60_o60": "C4 ($w_\\text{dwa}$=5.0\\%, $w_\\text{isco}$=75\\%)",
    "fg_isco08_dwa00_soc65": "B0 ($w_\\text{dwa}$=0\\%, $w_\\text{soc}$=65.0\\%)",
}

CANDIDATES: list[dict[str, object]] = [
    # ── Selected config (joint fine-sweep marginal optimum) ─────────────
    {
        "label": "jf_d030_s675_i80_t60_o60",
        "description": "Selected: joint sweep marginal optimum (w_dwa=0.030, w_soc=0.675, w_isco=0.80, w_isco_task=0.60, w_occ=0.60)",
        "overrides": {
            "w_isco": 0.8,
            "w_dwa": 0.030,
            "w_soc_title": 0.675,
            "w_occ": 0.6,
            "w_isco_task": 0.6,
            "min_sim": 0.45,
            "margin_best": 0.03,
            "max_links_per_task": 1,
            "k_retrieve": 5,
            "overload_abs": 200,
            "overload_quantile": 0.95,
            "overload_min_sim": 0.55,
            "overload_margin_best": 0.02,
        },
    },
    # ── Joint sweep runner-ups ────────────────────────────────────────────
    {
        "label": "jf_d030_s675_i80_t57_o60",
        "description": "Runner-up: w_isco_task=0.575 variant (w_dwa=0.030, w_soc=0.675, w_isco=0.80, w_isco_task=0.575, w_occ=0.60)",
        "overrides": {
            "w_isco": 0.8,
            "w_dwa": 0.030,
            "w_soc_title": 0.675,
            "w_occ": 0.6,
            "w_isco_task": 0.575,
            "min_sim": 0.45,
            "margin_best": 0.03,
            "max_links_per_task": 1,
            "k_retrieve": 5,
            "overload_abs": 200,
            "overload_quantile": 0.95,
            "overload_min_sim": 0.55,
            "overload_margin_best": 0.02,
        },
    },
    {
        "label": "jf_d030_s675_i75_t60_o60",
        "description": "Runner-up: w_isco=0.75 variant (w_dwa=0.030, w_soc=0.675, w_isco=0.75, w_isco_task=0.60, w_occ=0.60)",
        "overrides": {
            "w_isco": 0.75,
            "w_dwa": 0.030,
            "w_soc_title": 0.675,
            "w_occ": 0.6,
            "w_isco_task": 0.6,
            "min_sim": 0.45,
            "margin_best": 0.03,
            "max_links_per_task": 1,
            "k_retrieve": 5,
            "overload_abs": 200,
            "overload_quantile": 0.95,
            "overload_min_sim": 0.55,
            "overload_margin_best": 0.02,
        },
    },
    {
        "label": "jf_d050_s675_i75_t60_o60",
        "description": "Joint sweep rank-1 by composite score (w_dwa=0.050, w_soc=0.675, w_isco=0.75, w_isco_task=0.60, w_occ=0.60)",
        "overrides": {
            "w_isco": 0.75,
            "w_dwa": 0.050,
            "w_soc_title": 0.675,
            "w_occ": 0.6,
            "w_isco_task": 0.6,
            "min_sim": 0.45,
            "margin_best": 0.03,
            "max_links_per_task": 1,
            "k_retrieve": 5,
            "overload_abs": 200,
            "overload_quantile": 0.95,
            "overload_min_sim": 0.55,
            "overload_margin_best": 0.02,
        },
    },
    # ── Baseline: no DWA ────────────────────────────────────────────────────────────────
    {
        "label": "fg_isco08_dwa00_soc65",
        "description": "Baseline: no DWA (w_dwa=0.000, w_soc=0.650, w_isco_task=0.70, w_occ=0.70)",
        "overrides": {
            "w_isco": 0.8,
            "w_dwa": 0.0,
            "w_soc_title": 0.65,
            "w_occ": 0.7,
            "w_isco_task": 0.7,
            "min_sim": 0.45,
            "margin_best": 0.03,
            "max_links_per_task": 1,
            "k_retrieve": 5,
            "overload_abs": 200,
            "overload_quantile": 0.95,
            "overload_min_sim": 0.55,
            "overload_margin_best": 0.02,
        },
    },
]


def make_strict_xw(xw1: pd.DataFrame, xw2: pd.DataFrame, soc_col: str) -> pd.DataFrame:
    common_socs = set(xw1[soc_col]) & set(xw2[soc_col])
    a = xw1.loc[xw1[soc_col].isin(common_socs), [soc_col, "isco_code"]]
    b = xw2.loc[xw2[soc_col].isin(common_socs), [soc_col, "isco_code"]]
    return pd.merge(a, b, on=[soc_col, "isco_code"]).drop_duplicates().reset_index(drop=True)


def make_lenient_xw(xw1: pd.DataFrame, xw2: pd.DataFrame, soc_col: str) -> pd.DataFrame:
    return (
        pd.concat([xw1[[soc_col, "isco_code"]], xw2[[soc_col, "isco_code"]]])
        .drop_duplicates()
        .reset_index(drop=True)
    )


def _candidate_output_path(label: str) -> Path:
    return CANDIDATE_DIR / f"ONET29_{label}_task_to_ISCO_crosswalk.csv"


def build_candidate_configs() -> list[dict[str, object]]:
    base_cfg = load_config(PROJECT_DIR / "config_onet29.yaml")
    built: list[dict[str, object]] = []
    for item in CANDIDATES:
        label = str(item["label"])
        cfg = replace(
            base_cfg,
            dataset_name=label,
            checkpoint_prefix="ONET29",
            final_output_path=str(_candidate_output_path(label)),
            slim_output=False,
            **dict(item["overrides"]),
        )
        built.append({"label": label, "description": item["description"], "config": cfg})
    return built


def _candidate_parameter_table(candidates: list[dict[str, object]]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for item in candidates:
        cfg = item["config"]
        rows.append(
            {
                "candidate_label": item["label"],
                "w_isco": getattr(cfg, "w_isco"),
                "w_dwa": getattr(cfg, "w_dwa"),
                "w_soc_title": getattr(cfg, "w_soc_title"),
                "w_occ": getattr(cfg, "w_occ"),
                "w_isco_task": getattr(cfg, "w_isco_task"),
                "min_sim": getattr(cfg, "min_sim"),
                "margin_best": getattr(cfg, "margin_best"),
                "max_links": getattr(cfg, "max_links_per_task"),
                "overload_abs": getattr(cfg, "overload_abs"),
                "overload_q": getattr(cfg, "overload_quantile"),
            }
        )
    return pd.DataFrame(rows)


def ensure_candidate_outputs(candidates: list[dict[str, object]]) -> pd.DataFrame:
    rows: list[dict[str, object]] = []
    for item in candidates:
        label = str(item["label"])
        cfg = item["config"]
        path = Path(getattr(cfg, "final_output_path"))
        if path.exists():
            print(f"[skip] {label} -> {path}")
        else:
            print(f"[run] {label}")
            run_pipeline(cfg)
        rows.append(
            {
                "label": label,
                "description": item["description"],
                "pipeline_path": str(path),
            }
        )
    return pd.DataFrame(rows)


def _chain_scenarios() -> list[tuple[str, pd.DataFrame]]:
    xw18 = load_soc18_crosswalks()
    xw18_1 = xw18["xw18_1"][["soc_code18", "isco_code"]]
    xw18_2 = xw18["xw18_2"][["soc_code18", "isco_code"]]
    return [
        ("A1_esco_soc18", xw18_1),
        ("A2_soc18_esco", xw18_2),
        ("A3_strict_intersection", make_strict_xw(xw18_1, xw18_2, "soc_code18")),
        ("A4_lenient_union", make_lenient_xw(xw18_1, xw18_2, "soc_code18")),
    ]


def build_chain_tables(candidate_outputs: pd.DataFrame) -> tuple[pd.DataFrame, pd.DataFrame]:
    task_soc = load_onet_tasks("29")
    chain_rows: list[pd.DataFrame] = []
    for item in candidate_outputs.to_dict(orient="records"):
        pipeline_df = load_pipeline(Path(item["pipeline_path"]))
        for scenario_name, crosswalk_df in _chain_scenarios():
            summary = summarise_match(
                evaluate_match(pipeline_df, task_soc, crosswalk_df, "soc_code18"),
                label=scenario_name,
            )
            summary.insert(0, "candidate_label", item["label"])
            summary.insert(1, "candidate_description", item["description"])
            chain_rows.append(summary)

    chain_overall = pd.concat(chain_rows, ignore_index=True)
    chain_lenient = (
        chain_overall[chain_overall["label"] == "A4_lenient_union"]
        .copy()
        .drop(columns=["label"])
        .rename(
            columns={
                "pct_exact": "chain_pct_exact",
                "pct_sub_major": "chain_pct_sub_major",
                "pct_major_group": "chain_pct_major_group",
                "pct_in_crosswalk": "chain_pct_in_crosswalk",
                "n_tasks": "chain_n_tasks",
                "n_in_crosswalk": "chain_n_in_crosswalk",
            }
        )
        .reset_index(drop=True)
    )
    return chain_overall, chain_lenient


def _load_filled_human_workbook() -> pd.DataFrame:
    path = GT_RESULTS_DIR / "annotation_workbook_onet29.xlsx"
    df = pd.read_excel(path, sheet_name="Validation", dtype=str)
    df.columns = df.columns.str.strip()
    df["expert_isco"] = df["expert_isco"].fillna("").str.strip()
    df = df[df["expert_isco"] != ""].copy()
    df["task_id"] = pd.to_numeric(df["task_id"], errors="coerce").astype("Int64")
    df["expert_isco_int"] = pd.to_numeric(df["expert_isco"], errors="coerce").astype("Int64")
    return df


def _match_flags(expert: pd.Series, pred: pd.Series) -> tuple[pd.Series, pd.Series, pd.Series]:
    e = pd.to_numeric(expert, errors="coerce").astype("Int64")
    p = pd.to_numeric(pred, errors="coerce").astype("Int64")
    valid = e.notna() & p.notna()
    exact = pd.Series(pd.NA, index=expert.index, dtype="boolean")
    sub_major = pd.Series(pd.NA, index=expert.index, dtype="boolean")
    major_group = pd.Series(pd.NA, index=expert.index, dtype="boolean")
    exact[valid] = e[valid] == p[valid]
    sub_major[valid] = (e[valid] // 100) == (p[valid] // 100)
    major_group[valid] = (e[valid] // 1000) == (p[valid] // 1000)
    return exact, sub_major, major_group


def build_human_table(candidate_outputs: pd.DataFrame) -> pd.DataFrame:
    filled = _load_filled_human_workbook()
    human_rows: list[dict[str, object]] = []
    for item in candidate_outputs.to_dict(orient="records"):
        pipe = load_pipeline(Path(item["pipeline_path"]))
        if "candidate_rank" in pipe.columns:
            pipe = pipe[pipe["candidate_rank"] == 1].copy()
        merged = filled[["task_id", "expert_isco_int"]].merge(
            pipe[["task_id", "isco_pred", "similarity"]],
            on="task_id",
            how="left",
        )
        exact, sub_major, major_group = _match_flags(merged["expert_isco_int"], merged["isco_pred"])
        human_rows.append(
            {
                "candidate_label": item["label"],
                "candidate_description": item["description"],
                "human_n_judged": int(exact.notna().sum()),
                "human_pct_exact": round(exact.astype(float).mean() * 100, 1),
                "human_pct_sub_major": round(sub_major.astype(float).mean() * 100, 1),
                "human_pct_major_group": round(major_group.astype(float).mean() * 100, 1),
                "human_mean_similarity": round(pd.to_numeric(merged["similarity"], errors="coerce").mean(), 3),
            }
        )
    return pd.DataFrame(human_rows)


def _write_tex_table(df: pd.DataFrame, path: Path, float_formatters: dict[str, str] | None = None) -> None:
    out = df.copy()
    float_formatters = float_formatters or {}
    for col, fmt in float_formatters.items():
        if col in out.columns:
            out[col] = out[col].map(lambda x: fmt.format(x) if pd.notna(x) else "")
    latex = out.to_latex(index=False, escape=False)
    path.write_text(latex, encoding="utf-8")


def _load_unsupervised_metrics(labels: list[str]) -> pd.DataFrame:
    """Pull unsupervised composite metrics from the sweep summary CSV."""
    summary_path = PROJECT_DIR / "results" / "summary" / "sweep_results_metrics_only.csv"
    if not summary_path.exists():
        return pd.DataFrame()
    df = pd.read_csv(summary_path)
    wanted = [
        "dataset_name", "selection_rank", "selection_score",
        "S5_FINAL_isco_coverage_share", "S5_FINAL_mean_similarity_retained",
        "S5_FINAL_share_tasks_in_overloaded_isco",
        "S5_FINAL_isco_gini", "S5_FINAL_best_link_agreement",
        "S5_FINAL_jaccard_macro",
    ]
    avail = [c for c in wanted if c in df.columns]
    sub = df[df["dataset_name"].isin(labels)][avail].drop_duplicates("dataset_name")
    return sub.set_index("dataset_name").reindex(labels).reset_index()


def export_publication_artifacts(
    comparison: pd.DataFrame,
    chain_overall: pd.DataFrame,
    candidates: list[dict[str, object]],
) -> None:
    params = _candidate_parameter_table(candidates)
    selected = "jf_d030_s675_i80_t60_o60"
    def _apply_display(series: pd.Series) -> pd.Series:
        return series.map(lambda s: DISPLAY_NAMES.get(s, s))

    def _bold_selected(series: pd.Series, selected_display: str) -> pd.Series:
        return series.map(
            lambda s: f"\\textbf{{{s}}}" if s == selected_display else s
        )

    selected_display = DISPLAY_NAMES.get(selected, selected)

    comp_table = comparison[
        [
            "candidate_label",
            "chain_pct_exact",
            "chain_pct_sub_major",
            "chain_pct_major_group",
            "human_pct_exact",
            "human_pct_sub_major",
            "human_pct_major_group",
            "human_mean_similarity",
        ]
    ].copy()
    comp_table.columns = [
        "Candidate",
        "Chain exact",
        "Chain sub-major",
        "Chain major",
        "Human exact",
        "Human sub-major",
        "Human major",
        "Human sim.",
    ]
    comp_table["Candidate"] = _apply_display(comp_table["Candidate"])
    comp_table["Candidate"] = _bold_selected(comp_table["Candidate"], selected_display)

    params_table = params.copy()
    params_table.columns = [
        "Candidate",
        "$w_{isco}$",
        "$w_{dwa}$",
        "$w_{soc}$",
        "$w_{occ}$",
        "$w_{isco-task}$",
        "min sim.",
        "margin",
        "max links",
        "overload abs.",
        "overload q",
    ]
    params_table["Candidate"] = _apply_display(params_table["Candidate"])
    params_table["Candidate"] = _bold_selected(params_table["Candidate"], selected_display)

    chain_scenarios = chain_overall.copy()
    chain_scenarios = chain_scenarios.pivot(
        index="candidate_label",
        columns="label",
        values="pct_exact",
    ).reset_index()
    chain_scenarios = chain_scenarios[
        [
            "candidate_label",
            "A1_esco_soc18",
            "A2_soc18_esco",
            "A3_strict_intersection",
            "A4_lenient_union",
        ]
    ]
    chain_scenarios.columns = [
        "Candidate",
        "A1 exact",
        "A2 exact",
        "A3 exact",
        "A4 exact",
    ]
    chain_scenarios["Candidate"] = _apply_display(chain_scenarios["Candidate"])
    chain_scenarios["Candidate"] = _bold_selected(chain_scenarios["Candidate"], selected_display)

    # ── Unsupervised metrics table ─────────────────────────────────────────────
    label_list = [str(c["label"]) for c in candidates]
    unsup = _load_unsupervised_metrics(label_list)
    if not unsup.empty:
        unsup_table = unsup.rename(columns={
            "dataset_name": "Candidate",
            "selection_rank": "Rank",
            "selection_score": "Score",
            "S5_FINAL_isco_coverage_share": "Coverage",
            "S5_FINAL_mean_similarity_retained": "Mean sim.",
            "S5_FINAL_share_tasks_in_overloaded_isco": "Overload",
            "S5_FINAL_isco_gini": "Gini",
            "S5_FINAL_best_link_agreement": "Best-link agr.",
            "S5_FINAL_jaccard_macro": "Jaccard",
        })
        unsup_table["Candidate"] = _apply_display(unsup_table["Candidate"])
        unsup_table["Candidate"] = _bold_selected(unsup_table["Candidate"], selected_display)
        present_cols = ["Candidate", "Rank", "Score", "Coverage", "Mean sim.",
                        "Overload", "Gini", "Best-link agr.", "Jaccard"]
        unsup_table = unsup_table[[c for c in present_cols if c in unsup_table.columns]]
        _write_tex_table(
            unsup_table,
            PUBLICATION_TABLE_DIR / "table_candidate_selection_unsupervised.tex",
            {
                "Score": "{:.4f}",
                "Coverage": "{:.3f}",
                "Mean sim.": "{:.4f}",
                "Overload": "{:.4f}",
                "Gini": "{:.4f}",
                "Best-link agr.": "{:.4f}",
                "Jaccard": "{:.4f}",
            },
        )

    _write_tex_table(
        comp_table,
        PUBLICATION_TABLE_DIR / "table_candidate_selection_comparison.tex",
        {
            "Chain exact": "{:.1f}",
            "Chain sub-major": "{:.1f}",
            "Chain major": "{:.1f}",
            "Human exact": "{:.1f}",
            "Human sub-major": "{:.1f}",
            "Human major": "{:.1f}",
            "Human sim.": "{:.3f}",
        },
    )
    _write_tex_table(
        params_table,
        PUBLICATION_TABLE_DIR / "table_candidate_selection_parameters.tex",
        {
            "$w_{isco}$": "{:.3f}",
            "$w_{dwa}$": "{:.3f}",
            "$w_{soc}$": "{:.3f}",
            "$w_{occ}$": "{:.3f}",
            "$w_{isco-task}$": "{:.3f}",
            "min sim.": "{:.3f}",
            "margin": "{:.3f}",
            "overload q": "{:.3f}",
        },
    )
    _write_tex_table(
        chain_scenarios,
        PUBLICATION_TABLE_DIR / "table_candidate_selection_chain_scenarios.tex",
        {
            "A1 exact": "{:.1f}",
            "A2 exact": "{:.1f}",
            "A3 exact": "{:.1f}",
            "A4 exact": "{:.1f}",
        },
    )

    fig_df = comparison.sort_values("human_pct_exact", ascending=False).copy()
    x = range(len(fig_df))
    width = 0.36
    fig, ax = plt.subplots(figsize=(10, 5.5))
    colors = ["#c44e52" if label == selected else "#4c72b0" for label in fig_df["candidate_label"]]
    ax.bar(
        [i - width / 2 for i in x],
        fig_df["chain_pct_exact"],
        width,
        label="Chain exact",
        color=colors,
        alpha=0.75,
    )
    ax.bar(
        [i + width / 2 for i in x],
        fig_df["human_pct_exact"],
        width,
        label="Human exact",
        color="#55a868",
        alpha=0.85,
    )
    for i, row in enumerate(fig_df.itertuples(index=False)):
        ax.text(i - width / 2, row.chain_pct_exact + 0.7, f"{row.chain_pct_exact:.1f}", ha="center", va="bottom", fontsize=8)
        ax.text(i + width / 2, row.human_pct_exact + 0.7, f"{row.human_pct_exact:.1f}", ha="center", va="bottom", fontsize=8)
    ax.set_xticks(list(x))
    def _strip_latex(s: str) -> str:
        return (
            s.replace(r"$w_\text{dwa}$", "DWA")
             .replace(r"$w_\text{soc}$", "SOC")
             .replace(r"$w_\text{isco}$", "ISCO")
             .replace(r"$w_\text{itsk}$", "itsk")
             .replace(r"$^*$", "*")
             .replace(r"\%", "%")
             .replace("\\textbf{", "")
             .replace("$", "")
             .replace("}", "")
        )
    ax.set_xticklabels(
        [_strip_latex(DISPLAY_NAMES.get(lbl, lbl)) for lbl in fig_df["candidate_label"]],
        rotation=15, ha="right"
    )
    ax.set_ylabel("Agreement rate (%)")
    ax.set_ylim(0, 100)
    ax.set_title("Shortlisted ONET29 candidates: chain and human exact agreement")
    ax.grid(True, axis="y", alpha=0.25)
    ax.legend(frameon=False)
    plt.tight_layout()
    fig.savefig(PUBLICATION_DIR / "figure_candidate_selection_comparison.png", dpi=180)
    fig.savefig(PUBLICATION_DIR / "figure_candidate_selection_comparison.pdf")
    plt.close(fig)


def main() -> None:
    candidates = build_candidate_configs()
    candidate_outputs = ensure_candidate_outputs(candidates)
    chain_overall, chain_lenient = build_chain_tables(candidate_outputs)
    human_eval = build_human_table(candidate_outputs)
    comparison = chain_lenient.merge(
        human_eval,
        on=["candidate_label", "candidate_description"],
        how="outer",
    )
    comparison = comparison.sort_values(
        ["human_pct_exact", "chain_pct_exact", "candidate_label"],
        ascending=[False, False, True],
    ).reset_index(drop=True)

    out_chain = GT_RESULTS_DIR / "onet29_candidate_chain_overall.csv"
    out_chain_lenient = GT_RESULTS_DIR / "onet29_candidate_chain_lenient_union.csv"
    out_human = GT_RESULTS_DIR / "onet29_candidate_human_eval.csv"
    out_comparison = GT_RESULTS_DIR / "onet29_candidate_comparison.csv"

    chain_overall.to_csv(out_chain, index=False)
    chain_lenient.to_csv(out_chain_lenient, index=False)
    human_eval.to_csv(out_human, index=False)
    comparison.to_csv(out_comparison, index=False)
    export_publication_artifacts(comparison, chain_overall, candidates)

    print("\nCandidate comparison summary:")
    print(
        comparison[
            [
                "candidate_label",
                "chain_pct_exact",
                "chain_pct_sub_major",
                "chain_pct_major_group",
                "human_pct_exact",
                "human_pct_sub_major",
                "human_pct_major_group",
                "human_mean_similarity",
            ]
        ].to_string(index=False)
    )
    print(f"\nWrote: {out_chain}")
    print(f"Wrote: {out_chain_lenient}")
    print(f"Wrote: {out_human}")
    print(f"Wrote: {out_comparison}")


if __name__ == "__main__":
    main()
