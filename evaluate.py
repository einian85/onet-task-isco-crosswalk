from __future__ import annotations

import json
import math
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import RunConfig
from pipeline import STAGES, read_table


def load_ground_truth(path: str | Path) -> pd.DataFrame:
    p = Path(path)
    if p.suffix.lower() == ".parquet":
        gt = pd.read_parquet(p)
    elif p.suffix.lower() in {".csv", ".tsv"}:
        sep = "\t" if p.suffix.lower() == ".tsv" else ","
        gt = pd.read_csv(p, sep=sep)
    else:
        raise ValueError(f"Unsupported ground truth file format: {p}")
    required = {"task_id", "target_id"}
    missing = required - set(gt.columns)
    if missing:
        raise ValueError(f"Ground truth missing columns: {sorted(missing)}")
    if "relevance_grade" not in gt.columns:
        gt["relevance_grade"] = 1
    gt["task_id"] = gt["task_id"].astype(str)
    gt["target_id"] = gt["target_id"].astype(str)
    return gt


def gini(values: np.ndarray) -> float:
    arr = np.sort(values.astype(float))
    if arr.size == 0 or arr.sum() == 0:
        return 0.0
    index = np.arange(1, arr.size + 1)
    return float((2 * np.sum(index * arr) / (arr.size * arr.sum())) - (arr.size + 1) / arr.size)


def entropy(values: np.ndarray) -> float:
    arr = values.astype(float)
    total = arr.sum()
    if total <= 0:
        return 0.0
    probs = arr / total
    return float(-(probs * np.log(probs + 1e-12)).sum())


def ranking_metrics(preds: pd.DataFrame, gt: pd.DataFrame, ks: tuple[int, ...] = (1, 5)) -> dict[str, Any]:
    if preds.empty:
        metrics = {"MRR": 0.0, "Precision@1": 0.0}
        for k in ks:
            metrics[f"Precision@{k}"] = 0.0
            metrics[f"Recall@{k}"] = 0.0
            metrics[f"nDCG@{k}"] = 0.0
        return metrics

    preds = preds.sort_values(["task_id", "candidate_rank", "similarity"], ascending=[True, True, False]).copy()
    preds["task_id"] = preds["task_id"].astype(str)
    preds["target_id"] = preds["target_id"].astype(str)
    gt = gt.copy()

    gt_map = gt.groupby("task_id").apply(lambda g: dict(zip(g["target_id"], g["relevance_grade"]))).to_dict()
    gt_binary = gt.groupby("task_id")["target_id"].apply(set).to_dict()

    tasks = sorted(set(preds["task_id"].unique()) | set(gt["task_id"].unique()))
    reciprocal_ranks = []
    p_at_1 = []
    precision_k = {k: [] for k in ks}
    recall_k = {k: [] for k in ks}
    ndcg_k = {k: [] for k in ks}

    for task_id in tasks:
        truth = gt_binary.get(task_id, set())
        grades = gt_map.get(task_id, {})
        task_preds = preds[preds["task_id"] == task_id].sort_values("candidate_rank")
        ranked_targets = task_preds["target_id"].tolist()
        rr = 0.0
        for idx, target_id in enumerate(ranked_targets, start=1):
            if target_id in truth:
                rr = 1.0 / idx
                break
        reciprocal_ranks.append(rr)
        p_at_1.append(1.0 if ranked_targets[:1] and ranked_targets[0] in truth else 0.0)

        for k in ks:
            topk = ranked_targets[:k]
            hits = sum(1 for t in topk if t in truth)
            precision_k[k].append(hits / k if k else 0.0)
            recall_k[k].append(hits / len(truth) if truth else 0.0)

            dcg = 0.0
            for rank, target_id in enumerate(topk, start=1):
                rel = grades.get(target_id, 0)
                dcg += (2 ** rel - 1) / math.log2(rank + 1)
            ideal_rels = sorted(grades.values(), reverse=True)[:k]
            idcg = 0.0
            for rank, rel in enumerate(ideal_rels, start=1):
                idcg += (2 ** rel - 1) / math.log2(rank + 1)
            ndcg_k[k].append(dcg / idcg if idcg > 0 else 0.0)

    metrics = {
        "MRR": float(np.mean(reciprocal_ranks)) if reciprocal_ranks else 0.0,
        "Precision@1": float(np.mean(p_at_1)) if p_at_1 else 0.0,
    }
    for k in ks:
        metrics[f"Precision@{k}"] = float(np.mean(precision_k[k])) if precision_k[k] else 0.0
        metrics[f"Recall@{k}"] = float(np.mean(recall_k[k])) if recall_k[k] else 0.0
        metrics[f"nDCG@{k}"] = float(np.mean(ndcg_k[k])) if ndcg_k[k] else 0.0
    return metrics


def distribution_metrics(preds: pd.DataFrame, config: RunConfig) -> dict[str, Any]:
    if preds.empty:
        return {
            "ISCO coverage": 0.0,
            "tasks_per_ISCO_mean": 0.0,
            "tasks_per_ISCO_median": 0.0,
            "tasks_per_ISCO_p95": 0.0,
            "tasks_per_ISCO_max": 0.0,
            "Gini": 0.0,
            "Entropy": 0.0,
            "share_overloaded": 0.0,
            "mean_links_per_task": 0.0,
            "overload_threshold": float(config.overload_abs),
        }
    target_counts = preds.groupby("target_id")["task_id"].nunique()
    task_counts = preds.groupby("task_id")["target_id"].nunique()
    coverage = float((target_counts > 0).mean())
    overload_threshold = max(config.overload_abs, float(target_counts.quantile(config.overload_quantile)))
    overloaded_targets = set(target_counts[target_counts > overload_threshold].index.astype(str))
    overloaded_rows = preds[preds["target_id"].astype(str).isin(overloaded_targets)]
    return {
        "ISCO coverage": coverage,
        "tasks_per_ISCO_mean": float(target_counts.mean()),
        "tasks_per_ISCO_median": float(target_counts.median()),
        "tasks_per_ISCO_p95": float(target_counts.quantile(0.95)),
        "tasks_per_ISCO_max": float(target_counts.max()),
        "Gini": gini(target_counts.to_numpy()),
        "Entropy": entropy(target_counts.to_numpy()),
        "share_overloaded": float(overloaded_rows["task_id"].nunique() / preds["task_id"].nunique()),
        "mean_links_per_task": float(task_counts.mean()),
        "overload_threshold": float(overload_threshold),
    }


def evaluate_stage(preds: pd.DataFrame, gt: pd.DataFrame, config: RunConfig, stage: str, run_id: str) -> dict[str, Any]:
    preds = preds.copy()
    preds["task_id"] = preds["task_id"].astype(str)
    preds["target_id"] = preds["target_id"].astype(str)
    metrics = {
        "run_id": run_id,
        "stage": stage,
    }
    metrics.update(ranking_metrics(preds, gt, ks=(1, config.k_retrieve)))
    metrics.update(distribution_metrics(preds, config))
    return metrics


def evaluate_run(run_id: str, config: RunConfig, ground_truth_path: str | Path) -> pd.DataFrame:
    gt = load_ground_truth(ground_truth_path)
    root = Path(config.output_dir)
    metric_dir = root / "metrics" / run_id
    metric_dir.mkdir(parents=True, exist_ok=True)

    rows = []
    for stage in STAGES:
        stage_table = read_table(root / "predictions" / run_id / stage)
        metrics = evaluate_stage(stage_table, gt, config, stage, run_id)
        rows.append(metrics)
        (metric_dir / f"metrics_{stage}.json").write_text(json.dumps(metrics, indent=2), encoding="utf-8")

    metrics_df = pd.DataFrame(rows)
    metrics_df.to_csv(metric_dir / "metrics.csv", index=False)
    return metrics_df


def append_summary(metrics_df: pd.DataFrame, results_dir: str | Path) -> Path:
    summary_path = Path(results_dir) / "summary" / "results.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    if summary_path.exists():
        existing = pd.read_csv(summary_path)
        combined = pd.concat([existing, metrics_df], ignore_index=True)
        combined = combined.drop_duplicates(subset=["run_id", "stage"], keep="last")
    else:
        combined = metrics_df.copy()
    combined.to_csv(summary_path, index=False)
    return summary_path


if __name__ == "__main__":
    raise SystemExit("Use evaluate_run(...) from Python or import this module.")
