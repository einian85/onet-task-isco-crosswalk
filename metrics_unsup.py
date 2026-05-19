from __future__ import annotations

from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import RunConfig, compute_overload_threshold

_TASK_TOTAL_CACHE: dict[tuple[str, bool, int | None], int] = {}


def _task_universe_size(cfg: RunConfig) -> int:
    key = (str(Path(cfg.onet_tasks_path)), bool(cfg.use_task_ids), cfg.limit_tasks)
    cached = _TASK_TOTAL_CACHE.get(key)
    if cached is not None:
        return cached

    df_tasks = pd.read_excel(cfg.onet_tasks_path, usecols=["Task ID", "Task"])
    if cfg.limit_tasks is not None:
        df_tasks = df_tasks.head(cfg.limit_tasks).copy()
    if cfg.use_task_ids:
        total = int(df_tasks["Task ID"].astype(str).nunique())
    else:
        total = int(df_tasks["Task"].astype(str).drop_duplicates().shape[0])
    _TASK_TOTAL_CACHE[key] = total
    return total



def compute_gini(counts: np.ndarray) -> float:
    arr = np.sort(counts.astype(float))
    if arr.size == 0 or arr.sum() == 0:
        return 0.0
    index = np.arange(1, arr.size + 1)
    return float((2 * np.sum(index * arr) / (arr.size * arr.sum())) - (arr.size + 1) / arr.size)



def compute_entropy(counts: np.ndarray) -> float:
    arr = counts.astype(float)
    total = arr.sum()
    if total <= 0:
        return 0.0
    probs = arr / total
    return float(-(probs * np.log(probs + 1e-12)).sum())



def compute_retrieval_confidence(df_s1: pd.DataFrame, cfg: RunConfig) -> pd.DataFrame:
    if df_s1.empty:
        return pd.DataFrame(columns=["task_id", "sim_1", "sim_2", "sim_k", "gap_1_2", "gap_1_k", "topk_entropy", "low_confidence"])
    grouped = df_s1.sort_values(["task_id", "candidate_rank"]).groupby("task_id", as_index=False).agg(
        sim_1=("task_best_similarity", "first"),
        sim_2=("similarity", lambda s: s.iloc[1] if len(s) > 1 else s.iloc[0]),
        sim_k=("similarity", "last"),
        gap_1_2=("gap_1_2", "first"),
        gap_1_k=("gap_1_k", "first"),
        topk_entropy=("topk_entropy", "first"),
    )
    grouped["low_confidence"] = (
        (grouped["gap_1_2"] < cfg.lowconf_gap_threshold) |
        (grouped["topk_entropy"] > cfg.lowconf_entropy_threshold)
    )
    return grouped



def compute_unsup_metrics(df_stage: pd.DataFrame, cfg: RunConfig, universe_isco: set[str], stage_name: str) -> dict[str, Any]:
    total_tasks = _task_universe_size(cfg)
    metrics: dict[str, Any] = {"stage": stage_name}
    if df_stage.empty:
        metrics.update(
            {
                "n_tasks_total": total_tasks,
                "n_tasks_with_any_link": 0,
                "mean_links_per_task": 0.0,
                "median_links_per_task": 0.0,
                "p95_links_per_task": 0.0,
                "n_unique_isco": 0,
                "isco_coverage_share": 0.0,
                "tasks_per_isco_mean": 0.0,
                "tasks_per_isco_median": 0.0,
                "tasks_per_isco_p95": 0.0,
                "tasks_per_isco_max": 0.0,
                "share_tasks_in_top5_isco": 0.0,
                "gini_tasks_per_isco": 0.0,
                "entropy_tasks_per_isco": 0.0,
                "mean_similarity_retained": 0.0,
                "median_similarity_retained": 0.0,
                "p10_similarity_retained": 0.0,
                "n_overloaded_isco": 0,
                "share_tasks_in_overloaded_isco": 0.0,
                "retrieval_sim1_mean": 0.0,
                "retrieval_gap12_median": 0.0,
                "retrieval_entropy_mean": 0.0,
                "retrieval_lowconf_share": 0.0,
            }
        )
        return metrics

    df = df_stage.copy()
    df["task_id"] = df["task_id"].astype(str)
    df["target_id"] = df["target_id"].astype(str)

    task_counts = df.groupby("task_id")["target_id"].nunique()
    isco_counts = df.groupby("target_id")["task_id"].nunique()
    top5_share = float(isco_counts.sort_values(ascending=False).head(5).sum() / isco_counts.sum()) if isco_counts.sum() else 0.0
    overload_thr = compute_overload_threshold(isco_counts, cfg)
    overloaded = set(isco_counts[isco_counts > overload_thr].index.astype(str))
    tasks_in_overloaded = df[df["target_id"].isin(overloaded)]["task_id"].nunique()

    metrics.update(
        {
            "n_tasks_total": total_tasks,
            "n_tasks_with_any_link": int(task_counts.shape[0]),
            "mean_links_per_task": float(task_counts.mean()),
            "median_links_per_task": float(task_counts.median()),
            "p95_links_per_task": float(task_counts.quantile(0.95)),
            "n_unique_isco": int(isco_counts.shape[0]),
            "isco_coverage_share": float(isco_counts.shape[0] / len(universe_isco)) if universe_isco else 0.0,
            "tasks_per_isco_mean": float(isco_counts.mean()),
            "tasks_per_isco_median": float(isco_counts.median()),
            "tasks_per_isco_p95": float(isco_counts.quantile(0.95)),
            "tasks_per_isco_max": float(isco_counts.max()),
            "share_tasks_in_top5_isco": top5_share,
            "gini_tasks_per_isco": compute_gini(isco_counts.to_numpy()),
            "entropy_tasks_per_isco": compute_entropy(isco_counts.to_numpy()),
            "mean_similarity_retained": float(df["similarity"].mean()),
            "median_similarity_retained": float(df["similarity"].median()),
            "p10_similarity_retained": float(df["similarity"].quantile(0.10)),
            "n_overloaded_isco": int(len(overloaded)),
            "share_tasks_in_overloaded_isco": float(tasks_in_overloaded / total_tasks) if total_tasks else 0.0,
        }
    )

    if stage_name == "S1_RETRIEVE":
        conf = compute_retrieval_confidence(df, cfg)
        metrics.update(
            {
                "retrieval_sim1_mean": float(conf["sim_1"].mean()),
                "retrieval_sim1_median": float(conf["sim_1"].median()),
                "retrieval_gap12_mean": float(conf["gap_1_2"].mean()),
                "retrieval_gap12_median": float(conf["gap_1_2"].median()),
                "retrieval_gap1k_mean": float(conf["gap_1_k"].mean()),
                "retrieval_entropy_mean": float(conf["topk_entropy"].mean()),
                "retrieval_entropy_median": float(conf["topk_entropy"].median()),
                "retrieval_lowconf_share": float(conf["low_confidence"].mean()),
            }
        )
    else:
        metrics.update(
            {
                "retrieval_sim1_mean": float(df["task_best_similarity"].mean()),
                "retrieval_gap12_median": float(df.groupby("task_id")["gap_1_2"].first().median()),
                "retrieval_entropy_mean": float(df.groupby("task_id")["topk_entropy"].first().mean()),
                "retrieval_lowconf_share": float(
                    (
                        (df.groupby("task_id")["gap_1_2"].first() < cfg.lowconf_gap_threshold) |
                        (df.groupby("task_id")["topk_entropy"].first() > cfg.lowconf_entropy_threshold)
                    ).mean()
                ),
            }
        )
    return metrics

