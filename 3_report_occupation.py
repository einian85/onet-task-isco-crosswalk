from __future__ import annotations

from pathlib import Path
from typing import Any
import re

import matplotlib.pyplot as plt
import pandas as pd

OUT_DIR = Path("results/publication")
OUT_DIR.mkdir(parents=True, exist_ok=True)


def _save_fig(fig: plt.Figure, png_path: Path) -> None:
    """Save figure as PNG and as a PGF file (both in the same results directory)."""
    fig.savefig(png_path, dpi=200, bbox_inches="tight")
    pgf_path = png_path.with_suffix(".pgf")
    try:
        fig.savefig(str(pgf_path), format="pgf", bbox_inches="tight")
    except Exception:
        pass

PLOT_STYLE = {
    "figure.figsize": (10, 6),
    "axes.grid": True,
    "grid.alpha": 0.25,
    "axes.spines.top": False,
    "axes.spines.right": False,
}

DATASET_LABELS = {
    "29.2-ID": "O*NET 29.2",
    "25.0-ID": "O*NET 25.0",
}

CROSSWALK_LABELS = {
    "XW18.1_esco_to_onetsoc": "ESCO-ONET-SOC (SOC18)",
    "XW18.2_onetsoc_to_esco": "ONET-SOC-ESCO (SOC18)",
    "XW10.1_esco_onet": "ESCO-ONET (MHV)",
    "XW10.2_isco_soc": "BLS ISCO-SOC",
}

MATCH_SCORE = {
    "exactMatch": 1.0,
    "exactISCO": 1.0,
    "narrowMatch": 0.9,
    "closeMatch": 0.75,
    "broadMatch": 0.6,
}

DATASETS = {
    "onet292_id": {
        "label": "O*NET 29.2 (Task-ID, latest SOC 2018)",
        "short": "29.2-ID",
        "soc_version": "soc18",
        "crosswalk_path": Path("output/ONET29_task_to_ISCO_crosswalk.csv"),
        "task_path": Path("data/onet/29_2/Task Statements.xlsx"),
        "use_task_ids": True,
    },
    "onet250_id": {
        "label": "O*NET 25.0 (Task-ID, latest SOC 2010)",
        "short": "25.0-ID",
        "soc_version": "soc10",
        "crosswalk_path": Path("output/ONET25_task_to_ISCO_crosswalk.csv"),
        "task_path": Path("data/onet/25_0/Task Statements.xlsx"),
        "use_task_ids": True,
    },
}


def normalize_soc(value: Any) -> str | None:
    if pd.isna(value):
        return None
    text = str(value).strip()
    match = re.search(r"(\d{2})-(\d{4})", text)
    if match:
        return f"{match.group(1)}-{match.group(2)}"
    digits = "".join(ch for ch in text if ch.isdigit())
    if len(digits) >= 6:
        return f"{digits[:2]}-{digits[2:6]}"
    return None


def normalize_isco(value: Any) -> str | None:
    if pd.isna(value):
        return None
    digits = "".join(ch for ch in str(value) if ch.isdigit())
    if len(digits) >= 4:
        return digits[:4]
    return None


def _load_task_table(task_path: Path) -> pd.DataFrame:
    task_df = pd.read_excel(task_path)
    out = task_df[["Task ID", "Task", "O*NET-SOC Code", "Title"]].copy()
    out["soc_code"] = out["O*NET-SOC Code"].map(normalize_soc)
    return out.dropna(subset=["soc_code"])


def load_implied_links(meta: dict[str, Any]) -> pd.DataFrame:
    pred = pd.read_csv(meta["crosswalk_path"])
    pred = pred.loc[pred["stage"] == "S5_FINAL"].copy()
    pred["isco_code"] = pred["iscoGroup"].map(normalize_isco)
    pred = pred.dropna(subset=["isco_code"])

    task_df = _load_task_table(meta["task_path"])

    if meta["use_task_ids"]:
        task_df["Task ID"] = pd.to_numeric(task_df["Task ID"], errors="coerce")
        pred["task_id_num"] = pd.to_numeric(pred["task_id"], errors="coerce")
        merged = pred.merge(task_df[["Task ID", "soc_code", "Title"]], left_on="task_id_num", right_on="Task ID", how="left")
    else:
        merged = pred.merge(task_df[["Task", "soc_code", "Title"]].drop_duplicates(), left_on="task_key", right_on="Task", how="left")

    merged = merged.dropna(subset=["soc_code"]).copy()
    merged["task_proxy"] = merged["task_id"].astype(str)
    return merged


def aggregate_implied_soc_isco(df: pd.DataFrame) -> pd.DataFrame:
    pair_counts = (
        df.groupby(["soc_code", "isco_code"], as_index=False)
        .agg(task_support=("task_proxy", "nunique"), mean_similarity=("similarity", "mean"))
    )
    soc_totals = pair_counts.groupby("soc_code", as_index=False)["task_support"].sum().rename(columns={"task_support": "soc_total_tasks"})
    out = pair_counts.merge(soc_totals, on="soc_code", how="left")
    out["support_share"] = out["task_support"] / out["soc_total_tasks"]
    return out


def top1_mapping(df: pd.DataFrame, score_col: str) -> pd.DataFrame:
    ranked = df.sort_values(["soc_code", score_col, "isco_code"], ascending=[True, False, True]).copy()
    return ranked.drop_duplicates(subset=["soc_code"], keep="first")[["soc_code", "isco_code", score_col]]


def load_reference_crosswalks() -> dict[str, pd.DataFrame]:
    refs: dict[str, pd.DataFrame] = {}

    xw10_1 = pd.read_csv("data/crosswalks/esco_onet_crosswalk.csv")
    xw10_1 = xw10_1.rename(columns={"onet_code": "soc_raw", "isco_code": "isco_raw", "semantic_similarity": "score"})
    xw10_1["soc_code"] = xw10_1["soc_raw"].map(normalize_soc)
    xw10_1["isco_code"] = xw10_1["isco_raw"].map(normalize_isco)
    refs["XW10.1_esco_onet"] = xw10_1[["soc_code", "isco_code", "score"]].dropna().drop_duplicates()

    try:
        xw10_2 = pd.read_excel("data/crosswalks/isco_soc_crosswalk.xls", sheet_name="Data")
        norm_cols = {c: c.strip().lower().replace("-", "_").replace(" ", "_") for c in xw10_2.columns}
        xw10_2 = xw10_2.rename(columns=norm_cols)
        xw10_2 = xw10_2.rename(columns={"2010_soc_code": "soc_raw", "isco_08_code": "isco_raw"})
        xw10_2["soc_code"] = xw10_2["soc_raw"].map(normalize_soc)
        xw10_2["isco_code"] = xw10_2["isco_raw"].map(normalize_isco)
        xw10_2["score"] = 1.0
        refs["XW10.2_isco_soc"] = xw10_2[["soc_code", "isco_code", "score"]].dropna().drop_duplicates()
    except Exception:
        pass

    xw18_1 = pd.read_excel("data/crosswalks/ESCO_to_ONET-SOC.xlsx", sheet_name="Crosswalk")
    xw18_1 = xw18_1.rename(columns={"SOC19-Code": "soc_raw", "ESCO-Code": "isco_raw"})
    xw18_1["soc_code"] = xw18_1["soc_raw"].map(normalize_soc)
    xw18_1["isco_code"] = xw18_1["isco_raw"].map(normalize_isco)
    xw18_1["score"] = 1.0
    refs["XW18.1_esco_to_onetsoc"] = xw18_1[["soc_code", "isco_code", "score"]].dropna().drop_duplicates()

    xw18_2 = pd.read_csv("data/crosswalks/ONET_(Occupations)_0_updated.csv", skiprows=16)
    xw18_2 = xw18_2.rename(columns={"O*NET Id": "soc_raw", "Type of Match": "match_type"})
    # Extract 4-digit ISCO code from URI (e.g. ".../esco/isco/C2512"); skip ESCO occupation URIs
    xw18_2["isco_raw"] = xw18_2["ESCO or ISCO URI"].where(
        xw18_2["ESCO or ISCO URI"].str.contains("/isco/", na=False)
    ).str.extract(r"/C(\d{4})", expand=False)
    xw18_2["soc_code"] = xw18_2["soc_raw"].map(normalize_soc)
    xw18_2["isco_code"] = xw18_2["isco_raw"].map(normalize_isco)
    xw18_2["score"] = xw18_2["match_type"].map(MATCH_SCORE).fillna(0.6)
    refs["XW18.2_onetsoc_to_esco"] = xw18_2[["soc_code", "isco_code", "score"]].dropna().drop_duplicates()

    return refs


def compare_pair_sets(implied: pd.DataFrame, reference: pd.DataFrame) -> dict[str, Any]:
    imp_pairs = set(map(tuple, implied[["soc_code", "isco_code"]].drop_duplicates().values.tolist()))
    ref_pairs = set(map(tuple, reference[["soc_code", "isco_code"]].drop_duplicates().values.tolist()))
    inter = imp_pairs & ref_pairs
    precision = len(inter) / len(imp_pairs) if imp_pairs else 0.0
    recall = len(inter) / len(ref_pairs) if ref_pairs else 0.0
    f1 = 2 * precision * recall / (precision + recall) if (precision + recall) > 0 else 0.0
    return {
        "n_implied_pairs": len(imp_pairs),
        "n_ref_pairs": len(ref_pairs),
        "n_pair_overlap": len(inter),
        "pair_precision_vs_ref": precision,
        "pair_recall_vs_ref": recall,
        "pair_f1_vs_ref": f1,
    }


def compare_top1(implied: pd.DataFrame, reference: pd.DataFrame) -> dict[str, Any]:
    imp_top = top1_mapping(implied, "support_share").rename(columns={"isco_code": "isco_imp"})
    ref_scored = reference.groupby(["soc_code", "isco_code"], as_index=False)["score"].sum()
    ref_top = top1_mapping(ref_scored, "score").rename(columns={"isco_code": "isco_ref"})
    merged = imp_top.merge(ref_top[["soc_code", "isco_ref"]], on="soc_code", how="inner")
    if merged.empty:
        return {
            "n_shared_soc": 0,
            "top1_agreement_share": 0.0,
        }
    agree = (merged["isco_imp"] == merged["isco_ref"]).mean()
    return {
        "n_shared_soc": int(len(merged)),
        "top1_agreement_share": float(agree),
    }


def compare_top1_between_refs(ref_a: pd.DataFrame, ref_b: pd.DataFrame) -> dict[str, Any]:
    a_scored = ref_a.groupby(["soc_code", "isco_code"], as_index=False)["score"].sum()
    b_scored = ref_b.groupby(["soc_code", "isco_code"], as_index=False)["score"].sum()
    a_top = top1_mapping(a_scored, "score").rename(columns={"isco_code": "isco_a"})
    b_top = top1_mapping(b_scored, "score").rename(columns={"isco_code": "isco_b"})
    merged = a_top.merge(b_top[["soc_code", "isco_b"]], on="soc_code", how="inner")
    if merged.empty:
        return {"n_shared_soc": 0, "top1_agreement_share": 0.0}
    return {
        "n_shared_soc": int(len(merged)),
        "top1_agreement_share": float((merged["isco_a"] == merged["isco_b"]).mean()),
    }


def reference_subset_for_soc_version(refs: dict[str, pd.DataFrame], soc_version: str) -> dict[str, pd.DataFrame]:
    if soc_version == "soc10":
        return {k: v for k, v in refs.items() if k.startswith("XW10.")}
    return {k: v for k, v in refs.items() if k.startswith("XW18.")}


def build_reference_internal_comparison(refs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[dict[str, Any]] = []
    for soc_version in ("soc10", "soc18"):
        subset = reference_subset_for_soc_version(refs, soc_version)
        names = sorted(subset.keys())
        for i in range(len(names)):
            for j in range(i + 1, len(names)):
                left = names[i]
                right = names[j]
                left_df = subset[left]
                right_df = subset[right]
                pair_metrics = compare_pair_sets(left_df, right_df)
                top1_metrics = compare_top1_between_refs(left_df, right_df)
                rows.append(
                    {
                        "soc_version": soc_version,
                        "left_reference": left,
                        "right_reference": right,
                        **pair_metrics,
                        **top1_metrics,
                    }
                )
    return pd.DataFrame(rows)


def build_outputs() -> tuple[pd.DataFrame, pd.DataFrame, pd.DataFrame]:
    refs = load_reference_crosswalks()
    summary_rows: list[dict[str, Any]] = []
    implied_rows: list[pd.DataFrame] = []

    for dataset_id, meta in DATASETS.items():
        implied_links = load_implied_links(meta)
        implied_pairs = aggregate_implied_soc_isco(implied_links)
        implied_pairs["dataset_id"] = dataset_id
        implied_pairs["dataset"] = meta["label"]
        implied_pairs["dataset_short"] = meta["short"]
        implied_rows.append(implied_pairs)

        ref_subset = reference_subset_for_soc_version(refs, meta["soc_version"])
        for ref_name, ref_df in ref_subset.items():
            pair_metrics = compare_pair_sets(implied_pairs, ref_df)
            top1_metrics = compare_top1(implied_pairs, ref_df)
            summary_rows.append(
                {
                    "dataset_id": dataset_id,
                    "dataset": meta["label"],
                    "dataset_short": meta["short"],
                    "soc_version": meta["soc_version"],
                    "reference_crosswalk": ref_name,
                    "n_implied_soc": int(implied_pairs["soc_code"].nunique()),
                    "n_implied_isco": int(implied_pairs["isco_code"].nunique()),
                    **pair_metrics,
                    **top1_metrics,
                }
            )

    summary = pd.DataFrame(summary_rows)
    implied = pd.concat(implied_rows, ignore_index=True)
    ref_internal = build_reference_internal_comparison(refs)
    return summary, implied, ref_internal


def _select_reference_for_dataset(meta: dict[str, Any]) -> str:
    if meta["soc_version"] == "soc18":
        return "XW18.2_onetsoc_to_esco"
    return "XW10.2_isco_soc"


def _get_run_id_from_crosswalk(crosswalk_path: Path) -> str:
    df = pd.read_csv(crosswalk_path, usecols=["run_id"])
    return str(df["run_id"].iloc[0])


def _load_stage_df(run_id: str, stage: str) -> pd.DataFrame:
    path = Path("results/predictions") / run_id / f"{stage}.csv"
    return pd.read_csv(path)


def build_overload_examples() -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    for dataset_id, meta in DATASETS.items():
        run_id = _get_run_id_from_crosswalk(meta["crosswalk_path"])
        s3 = _load_stage_df(run_id, "S3_COVERAGE")
        s4 = _load_stage_df(run_id, "S4_OVERLOAD")
        s5 = _load_stage_df(run_id, "S5_FINAL")
        c3 = s3.groupby("iscoGroup", as_index=False).agg(tasks_s3=("task_id", "nunique"))
        c4 = s4.groupby("iscoGroup", as_index=False).agg(tasks_s4=("task_id", "nunique"))
        c5 = s5.groupby("iscoGroup", as_index=False).agg(tasks_s5=("task_id", "nunique"))
        labels = (
            s3.assign(isco_title=s3["isco_title"].astype(str).str.split("|").str[0])
            .groupby("iscoGroup", as_index=False)["isco_title"]
            .first()
        )
        out = c3.merge(c4, on="iscoGroup", how="left").merge(c5, on="iscoGroup", how="left").merge(labels, on="iscoGroup", how="left")
        out = out.fillna(0)
        out["pruned_in_s4"] = out["tasks_s3"] - out["tasks_s4"]
        out["dataset_id"] = dataset_id
        out["dataset_short"] = meta["short"]
        out["run_id"] = run_id
        out = out.sort_values("tasks_s3", ascending=False).head(8)
        rows.append(out)
    return pd.concat(rows, ignore_index=True)


def build_stage_task_examples() -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    stage_order = ["S1_RETRIEVE", "S2_TASK_FILTER", "S3_COVERAGE", "S4_OVERLOAD", "S5_FINAL"]
    for dataset_id, meta in DATASETS.items():
        run_id = _get_run_id_from_crosswalk(meta["crosswalk_path"])
        s1 = _load_stage_df(run_id, "S1_RETRIEVE")
        task_rank_counts = s1.groupby("task_id", as_index=False).agg(k=("candidate_rank", "max"), entropy=("topk_entropy", "first"))
        task_rank_counts = task_rank_counts.sort_values(["k", "entropy"], ascending=[False, False])
        picked_task = str(task_rank_counts.iloc[0]["task_id"])
        for stage in stage_order:
            st = _load_stage_df(run_id, stage)
            sub = st[st["task_id"].astype(str) == picked_task].copy()
            if stage == "S1_RETRIEVE":
                sub = sub.sort_values("candidate_rank").head(5)
            sub["dataset_id"] = dataset_id
            sub["dataset_short"] = meta["short"]
            sub["run_id"] = run_id
            sub["stage_name"] = stage
            rows.append(
                sub[
                    [
                        "dataset_short",
                        "run_id",
                        "stage_name",
                        "task_id",
                        "task_text",
                        "candidate_rank",
                        "iscoGroup",
                        "isco_title",
                        "similarity",
                        "kept_reason",
                        "topk_entropy",
                    ]
                ]
            )
    return pd.concat(rows, ignore_index=True)


def build_top1_mismatch_examples(refs: dict[str, pd.DataFrame]) -> pd.DataFrame:
    rows: list[pd.DataFrame] = []
    isco_def = pd.read_excel(
        "data/isco/ISCO-08 EN Structure and definitions.xlsx",
        sheet_name="ISCO-08 EN Struct and defin",
        usecols=["Level", "ISCO 08 Code", "Title EN"],
    )
    isco_def = isco_def[isco_def["Level"] == 4].copy()
    isco_def["isco_code"] = isco_def["ISCO 08 Code"].astype(str).str.zfill(4)
    isco_title_map = isco_def[["isco_code", "Title EN"]].rename(columns={"Title EN": "reference_isco_title"}).drop_duplicates(subset=["isco_code"])

    for dataset_id, meta in DATASETS.items():
        implied_links = load_implied_links(meta)
        implied_pairs = aggregate_implied_soc_isco(implied_links)
        imp_top = implied_pairs.sort_values(["soc_code", "support_share", "task_support"], ascending=[True, False, False]).drop_duplicates("soc_code")
        imp_top = imp_top.rename(columns={"isco_code": "isco_imp", "support_share": "imp_support_share", "task_support": "imp_task_support"})

        ref_name = _select_reference_for_dataset(meta)
        ref_df = refs[ref_name]
        ref_top = ref_df.groupby(["soc_code", "isco_code"], as_index=False)["score"].sum()
        ref_top = ref_top.sort_values(["soc_code", "score"], ascending=[True, False]).drop_duplicates("soc_code")
        ref_top = ref_top.rename(columns={"isco_code": "isco_ref", "score": "ref_score"})

        soc_titles = implied_links[["soc_code", "Title"]].dropna().drop_duplicates().rename(columns={"Title": "soc_title"})
        imp_occ = (
            implied_links.groupby(["soc_code", "isco_code"], as_index=False)["isco_title"]
            .first()
            .rename(columns={"isco_code": "isco_imp", "isco_title": "implied_occupation_label"})
        )

        merged = imp_top.merge(ref_top[["soc_code", "isco_ref", "ref_score"]], on="soc_code", how="inner")
        merged = merged[merged["isco_imp"] != merged["isco_ref"]].copy()
        merged = merged.merge(soc_titles, on="soc_code", how="left").merge(imp_occ, on=["soc_code", "isco_imp"], how="left")
        if meta["soc_version"] == "soc18":
            merged = merged.merge(isco_title_map.rename(columns={"isco_code": "isco_ref"}), on="isco_ref", how="left")
        else:
            merged["reference_isco_title"] = ""

        merged["dataset_id"] = dataset_id
        merged["dataset_short"] = meta["short"]
        merged["reference_crosswalk"] = ref_name
        merged = merged.sort_values(["imp_support_share", "imp_task_support"], ascending=False).head(12)
        rows.append(
            merged[
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
            ]
        )
    return pd.concat(rows, ignore_index=True)


def plot_top1_agreement(summary_df: pd.DataFrame) -> Path:
    plt.rcParams.update(PLOT_STYLE)
    fig, ax = plt.subplots(figsize=(12, 6))
    x = range(len(summary_df))
    disp_d = summary_df["dataset_short"].map(DATASET_LABELS).fillna(summary_df["dataset_short"])
    disp_r = summary_df["reference_crosswalk"].map(CROSSWALK_LABELS).fillna(summary_df["reference_crosswalk"])
    labels = [f"{d}\n{r}" for d, r in zip(disp_d, disp_r)]
    ax.bar(x, summary_df["top1_agreement_share"], color="#35618f")
    ax.set_xticks(list(x))
    ax.set_xticklabels(labels, rotation=35, ha="right")
    ax.set_ylabel("SOC-level Top-1 Agreement")
    ax.set_title("Implied SOC\u2192ISCO vs Institutional Crosswalks")
    fig.tight_layout()
    out = OUT_DIR / "figure_occupation_top1_agreement.png"
    _save_fig(fig, out)
    plt.close(fig)
    return out


def main() -> None:
    summary_df, implied_df, ref_internal_df = build_outputs()
    refs = load_reference_crosswalks()
    overload_examples_df = build_overload_examples()
    stage_examples_df = build_stage_task_examples()
    mismatch_examples_df = build_top1_mismatch_examples(refs)
    summary_path = OUT_DIR / "table_occupation_level_comparison.csv"
    implied_path = OUT_DIR / "table_implied_soc_isco_pairs.csv"
    ref_internal_path = OUT_DIR / "table_reference_internal_comparison.csv"
    overload_examples_path = OUT_DIR / "table_overload_examples.csv"
    stage_examples_path = OUT_DIR / "table_stage_task_examples.csv"
    mismatch_examples_path = OUT_DIR / "table_mismatch_examples.csv"
    summary_df.to_csv(summary_path, index=False)
    implied_df.to_csv(implied_path, index=False)
    ref_internal_df.to_csv(ref_internal_path, index=False)
    overload_examples_df.to_csv(overload_examples_path, index=False)
    stage_examples_df.to_csv(stage_examples_path, index=False)
    mismatch_examples_df.to_csv(mismatch_examples_path, index=False)
    fig_path = plot_top1_agreement(summary_df)
    print(summary_path)
    print(implied_path)
    print(ref_internal_path)
    print(overload_examples_path)
    print(stage_examples_path)
    print(mismatch_examples_path)
    print(fig_path)


if __name__ == "__main__":
    main()
