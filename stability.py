from __future__ import annotations

from typing import Any

import pandas as pd



def compare_runs_links(dfA: pd.DataFrame, dfB: pd.DataFrame) -> dict[str, Any]:
    A = dfA.copy()
    B = dfB.copy()
    A["task_id"] = A["task_id"].astype(str)
    B["task_id"] = B["task_id"].astype(str)
    A["target_id"] = A["target_id"].astype(str)
    B["target_id"] = B["target_id"].astype(str)

    links_a = set(zip(A["task_id"], A["target_id"]))
    links_b = set(zip(B["task_id"], B["target_id"]))
    union = links_a | links_b
    inter = links_a & links_b
    jaccard = len(inter) / len(union) if union else 1.0

    tasks = sorted(set(A["task_id"].unique()) | set(B["task_id"].unique()))
    per_task = []
    best_agree = []
    for task_id in tasks:
        ta = set(A.loc[A["task_id"] == task_id, "target_id"].astype(str))
        tb = set(B.loc[B["task_id"] == task_id, "target_id"].astype(str))
        union_t = ta | tb
        inter_t = ta & tb
        per_task.append(len(inter_t) / len(union_t) if union_t else 1.0)
        best_a = A.loc[A["task_id"] == task_id].sort_values(["candidate_rank", "similarity"], ascending=[True, False])["target_id"].astype(str)
        best_b = B.loc[B["task_id"] == task_id].sort_values(["candidate_rank", "similarity"], ascending=[True, False])["target_id"].astype(str)
        if len(best_a) and len(best_b):
            best_agree.append(float(best_a.iloc[0] == best_b.iloc[0]))
    return {
        "jaccard_links": jaccard,
        "task_level_overlap_mean": sum(per_task) / len(per_task) if per_task else 1.0,
        "best_link_agreement": sum(best_agree) / len(best_agree) if best_agree else 1.0,
    }



def compare_runs_topk(dfA_S1: pd.DataFrame, dfB_S1: pd.DataFrame, k: int) -> dict[str, Any]:
    A = dfA_S1.copy()
    B = dfB_S1.copy()
    A["task_id"] = A["task_id"].astype(str)
    B["task_id"] = B["task_id"].astype(str)
    A["target_id"] = A["target_id"].astype(str)
    B["target_id"] = B["target_id"].astype(str)
    tasks = sorted(set(A["task_id"].unique()) | set(B["task_id"].unique()))
    overlaps = []
    best_agree = []
    for task_id in tasks:
        top_a = set(A.loc[A["task_id"] == task_id].sort_values("candidate_rank").head(k)["target_id"].tolist())
        top_b = set(B.loc[B["task_id"] == task_id].sort_values("candidate_rank").head(k)["target_id"].tolist())
        union = top_a | top_b
        inter = top_a & top_b
        overlaps.append(len(inter) / len(union) if union else 1.0)
        ra = A.loc[A["task_id"] == task_id].sort_values("candidate_rank")["target_id"]
        rb = B.loc[B["task_id"] == task_id].sort_values("candidate_rank")["target_id"]
        if len(ra) and len(rb):
            best_agree.append(float(ra.iloc[0] == rb.iloc[0]))
    return {
        "topk_set_overlap_mean": sum(overlaps) / len(overlaps) if overlaps else 1.0,
        "best_link_agreement": sum(best_agree) / len(best_agree) if best_agree else 1.0,
    }
