from __future__ import annotations

import argparse
import gc
import hashlib
import json
import pickle
import random
import re
from pathlib import Path
from typing import Any

import faiss
import numpy as np
import pandas as pd
from sentence_transformers import SentenceTransformer
from sklearn.preprocessing import normalize

from config import (
    RunConfig,
    compute_input_hashes,
    compute_run_id,
    get_code_version,
    load_config,
    save_config,
    save_manifest,
    validate_config,
)
from metrics_unsup import compute_unsup_metrics, append_metrics_long

STAGES = ("S1_RETRIEVE", "S2_TASK_FILTER", "S3_COVERAGE", "S4_OVERLOAD", "S5_FINAL")

# In-process memory cache for Tier-1 embedding arrays.
# Key: str(raw_checkpoint_path). All sweep variants share the same raw embeddings,
# so after the first variant loads the pickle files every subsequent call is free.
_EMBEDDING_MEM_CACHE: dict[str, "np.ndarray"] = {}

# In-process cache for the SentenceTransformer model object.
# Key: model name string.  Loading the model hits HuggingFace Hub on every call
# in newer transformers versions; caching it here avoids repeated network calls
# and prevents segfaults from the offline/cached code path.
_MODEL_CACHE: dict[str, "SentenceTransformer"] = {}


def ensure_dir(path: str | Path) -> Path:
    p = Path(path)
    p.mkdir(parents=True, exist_ok=True)
    return p


def stable_task_hash(text: str) -> str:
    return hashlib.sha1(text.encode("utf-8")).hexdigest()[:16]


def _embedding_cache_dir(cfg: RunConfig) -> Path:
    return ensure_dir(cfg.embedding_cache_dir)


# Tier 1: raw model-inference embeddings — weight-independent, shared across ALL
# sweep variants (any w_isco, w_isco_task, w_occ, w_soc_title, w_dwa value).
# Stored as  checkpoints/{name}_{raw_fingerprint}.pkl
_TIER1_NAMES = frozenset({
    "onet_task_emb_raw",       # task text only (no DWA concatenation)
    "onet_title_emb_raw",      # SOC occupation title
    "onet_dwa_label_emb_raw",  # unique DWA label strings
    "esco_occ_emb_raw",
    "esco_skill_label_emb_raw",
    "isco_info_emb_raw",
    "isco_task_item_emb_raw",
})


def _raw_fingerprint(cfg: RunConfig) -> str:
    """Fingerprint for Tier 1 embeddings — depends only on data files + model."""
    relevant = {
        "include_esco_skills": cfg.include_esco_skills,
        "embedding_model": cfg.embedding_model,
        "limit_tasks": cfg.limit_tasks,
        "onet_tasks_path": cfg.onet_tasks_path,
        "onet_tasks_dwa_path": cfg.onet_tasks_dwa_path,
        "esco_skills_path": cfg.esco_skills_path,
        "esco_occupation_rel_path": cfg.esco_occupation_rel_path,
        "esco_occupations_path": cfg.esco_occupations_path,
        "isco_tasks_path": cfg.isco_tasks_path,
    }
    return hashlib.sha256(json.dumps(relevant, sort_keys=True).encode("utf-8")).hexdigest()[:12]


def raw_checkpoint_path(cfg: RunConfig, name: str) -> Path:
    """Path for Tier 1 (weight-independent) embeddings — no variant prefix."""
    return _embedding_cache_dir(cfg) / f"{name}_{_raw_fingerprint(cfg)}.pkl"


def is_valid_embedding(emb, expected_rows: int | None = None, expected_dim: int | None = None) -> bool:
    if emb is None or not hasattr(emb, "shape") or len(emb.shape) != 2:
        return False
    if expected_rows is not None and emb.shape[0] != expected_rows:
        return False
    if expected_dim is not None and emb.shape[1] != expected_dim:
        return False
    return True


def write_table(df: pd.DataFrame, path_without_suffix: Path) -> Path:
    ensure_dir(path_without_suffix.parent)
    try:
        out = path_without_suffix.with_suffix(".parquet")
        df.to_parquet(out, index=False)
        return out
    except Exception:
        out = path_without_suffix.with_suffix(".csv")
        df.to_csv(out, index=False)
        return out


def read_table(path_without_suffix: Path) -> pd.DataFrame:
    parquet_path = path_without_suffix.with_suffix(".parquet")
    csv_path = path_without_suffix.with_suffix(".csv")
    if parquet_path.exists():
        return pd.read_parquet(parquet_path)
    if csv_path.exists():
        return pd.read_csv(csv_path)
    raise FileNotFoundError(f"Missing stage file for {path_without_suffix}")


def _join_nonempty(parts: list[str]) -> str:
    return " ".join([p.strip() for p in parts if p and str(p).strip()]).strip()


# ── O*NET task loading ────────────────────────────────────────────────────────

def build_task_text(df_tasks: pd.DataFrame, cfg: RunConfig) -> pd.DataFrame:
    """Build task_text column (task description only — DWAs are embedded separately)."""
    df_tasks = df_tasks.copy()
    titles = df_tasks["Title"].fillna("").astype(str).str.strip()
    parts = []
    # When w_soc_title > 0, title is contributed via a separate weighted embedding
    # so it is NOT prepended here (avoids double-counting).
    if cfg.include_soc_title and cfg.w_soc_title == 0:
        parts.append("Occupation: " + titles + ".")
    parts.append(df_tasks["Task"].astype(str).str.strip() + ".")
    df_tasks["task_text"] = [_join_nonempty(list(vals)) for vals in zip(*parts)]
    df_tasks["soc_title_text"] = titles
    return df_tasks


def build_task_table(cfg: RunConfig) -> pd.DataFrame:
    """Load O*NET tasks. DWAs are no longer concatenated into task_text."""
    df_tasks = pd.read_excel(cfg.onet_tasks_path)[
        ["O*NET-SOC Code", "Title", "Task ID", "Task", "Task Type"]
    ]
    if cfg.limit_tasks is not None:
        df_tasks = df_tasks.head(cfg.limit_tasks).copy()
    if cfg.use_task_ids:
        df_tasks["task_key"] = df_tasks["Task ID"].astype(str)
        df_tasks["task_id"] = df_tasks["task_key"]
    else:
        df_tasks = (
            df_tasks.drop(columns=["Task ID"])
            .drop_duplicates(subset=["Task"])
            .reset_index(drop=True)
        )
        df_tasks["task_key"] = df_tasks["Task"].astype(str)
        df_tasks["task_id"] = df_tasks["Task"].astype(str).map(stable_task_hash)
    df_tasks["task_text_hash"] = df_tasks["Task"].astype(str).map(stable_task_hash)
    return build_task_text(df_tasks, cfg)


def load_dwa_long(cfg: RunConfig, df_tasks: pd.DataFrame) -> pd.DataFrame:
    """Return (task_id, dwa_title) pairs — one row per unique DWA item per task.

    DWA items are embedded individually and averaged per task so that tasks
    with many DWAs are not over-represented relative to tasks with few DWAs.
    """
    df_dwa_raw = pd.read_excel(cfg.onet_tasks_dwa_path)[["Task ID", "DWA Title"]].dropna(
        subset=["DWA Title"]
    )
    if cfg.use_task_ids:
        df = df_dwa_raw.copy()
        df["task_id"] = df["Task ID"].astype(str)
    else:
        # task_id is a hash of Task text — bridge via Task ID → Task text → hash
        df_task_ids = pd.read_excel(cfg.onet_tasks_path)[["Task ID", "Task"]].drop_duplicates()
        df = df_dwa_raw.merge(df_task_ids, on="Task ID", how="left")
        df["task_id"] = df["Task"].astype(str).map(stable_task_hash)
    valid_ids = set(df_tasks["task_id"].astype(str))
    df = df[df["task_id"].isin(valid_ids)]
    return (
        df[["task_id", "DWA Title"]]
        .rename(columns={"DWA Title": "dwa_title"})
        .drop_duplicates()
        .reset_index(drop=True)
    )


# ── ESCO loaders ──────────────────────────────────────────────────────────────

def load_esco_occupations(cfg: RunConfig) -> pd.DataFrame:
    """Return ESCO occupation table: occupationUri, occupationLabel, occupationDescription, iscoGroup."""
    return pd.read_csv(cfg.esco_occupations_path)[
        ["conceptUri", "preferredLabel", "description", "iscoGroup"]
    ].rename(columns={
        "conceptUri": "occupationUri",
        "preferredLabel": "occupationLabel",
        "description": "occupationDescription",
    }).reset_index(drop=True)


def load_esco_skills_long(cfg: RunConfig) -> pd.DataFrame:
    """Return unique (iscoGroup, preferredLabel) skill pairs across all ESCO occupations."""
    df_skills = pd.read_csv(cfg.esco_skills_path)[["conceptUri", "preferredLabel"]].rename(
        columns={"conceptUri": "skillUri"}
    )
    df_rel = pd.read_csv(cfg.esco_occupation_rel_path)[["occupationUri", "skillUri"]]
    df_occ_grp = pd.read_csv(cfg.esco_occupations_path)[["conceptUri", "iscoGroup"]].rename(
        columns={"conceptUri": "occupationUri"}
    )
    return (
        df_rel
        .merge(df_skills, on="skillUri", how="left")
        .merge(df_occ_grp, on="occupationUri", how="left")
        [["iscoGroup", "preferredLabel"]]
        .dropna(subset=["iscoGroup", "preferredLabel"])
        .drop_duplicates()
        .reset_index(drop=True)
    )


# ── ISCO-08 standard loaders ──────────────────────────────────────────────────

def load_isco_standard(cfg: RunConfig) -> tuple[pd.DataFrame, pd.DataFrame]:
    """Load ISCO-08 4-digit unit groups from the official Excel.

    Returns:
        df_groups     — one row per ISCO-08 4-digit group (typically 436),
                        columns: isco_code, title_en, isco_info_text
        df_task_items — one row per lettered task item within each group,
                        columns: isco_code, task_item_id (e.g. '8341_a'), task_text
    """
    xl = pd.read_excel(cfg.isco_tasks_path, sheet_name=0)
    unit = xl[xl["Level"] == 4].copy()
    unit["isco_code"] = unit["ISCO 08 Code"].astype(str).str.strip()
    unit["title_en"] = unit["Title EN"].fillna("").astype(str).str.strip()

    def _build_info(row) -> str:
        parts = [row["title_en"]]
        defn = str(row.get("Definition", "") or "").strip()
        if defn:
            parts.append(defn)
        incl = str(row.get("Included occupations", "") or "").strip()
        if incl:
            parts.append("Includes: " + incl)
        return " ".join(p for p in parts if p)

    unit["isco_info_text"] = unit.apply(_build_info, axis=1)
    df_groups = unit[["isco_code", "title_en", "isco_info_text"]].reset_index(drop=True)

    # Expand lettered task items into individual rows
    letters = "abcdefghijklmnopqrstuvwxyz"
    task_rows: list[dict] = []
    for _, row in unit.iterrows():
        raw = row.get("Tasks include", "")
        if pd.isna(raw) or not str(raw).strip():
            continue
        s = re.sub(r"Tasks includes?\s*-\s*", "", str(raw)).strip()
        items = re.split(r"\([a-z]\)\s*", s)
        items = [it.strip().rstrip(";").strip() for it in items if it.strip()]
        for i, text in enumerate(items):
            if text:
                letter = letters[i] if i < len(letters) else str(i)
                task_rows.append({
                    "isco_code": row["isco_code"],
                    "task_item_id": f"{row['isco_code']}_{letter}",
                    "task_text": text,
                })

    df_task_items = (
        pd.DataFrame(task_rows) if task_rows
        else pd.DataFrame(columns=["isco_code", "task_item_id", "task_text"])
    )
    print(f"  ISCO standard: {len(df_groups)} groups, {len(df_task_items)} task items")
    return df_groups, df_task_items


# ── Embedding utilities ───────────────────────────────────────────────────────

def embed_texts(
    texts: list[str],
    model: SentenceTransformer,
    cache_name: str,
    cfg: RunConfig,
    normalize_output: bool = False,
    expected_dim: int | None = None,
):
    """Embed texts using the shared Tier-1 weight-independent cache."""
    path = raw_checkpoint_path(cfg, cache_name)
    cache_key = str(path)

    # Fast path: already in process memory (subsequent sweep variants)
    if cache_key in _EMBEDDING_MEM_CACHE:
        emb = _EMBEDDING_MEM_CACHE[cache_key]
        print(f"{cache_name} shape: {emb.shape} (cached)")
        return emb

    emb = None
    if path.exists():
        print(f"Loading checkpoint: {path}")
        with path.open("rb") as f:
            emb = pickle.load(f)
    if not is_valid_embedding(emb, expected_rows=len(texts), expected_dim=expected_dim):
        print(f"Recomputing embeddings for {cache_name}.")
        emb = model.encode(texts, batch_size=64, show_progress_bar=True)
        if normalize_output:
            emb = normalize(emb)
        with path.open("wb") as f:
            pickle.dump(emb, f, protocol=pickle.HIGHEST_PROTOCOL)
        print(f"Saved checkpoint: {path}")
    print(f"{cache_name} shape: {emb.shape}")
    _EMBEDDING_MEM_CACHE[cache_key] = emb
    gc.collect()
    return emb


def _mean_embeddings_per_group(
    raw_emb: np.ndarray,
    group_labels: list[str],
    all_groups: list[str],
) -> np.ndarray:
    """Average raw_emb rows per group → shape (len(all_groups), dim).

    Groups absent from group_labels receive a zero vector (Option A: missing = 0).
    """
    dim = raw_emb.shape[1]
    group_idx = {g: i for i, g in enumerate(all_groups)}
    result = np.zeros((len(all_groups), dim), dtype=np.float32)
    counts = np.zeros(len(all_groups), dtype=np.int32)
    for i, g in enumerate(group_labels):
        j = group_idx.get(g)
        if j is not None:
            result[j] += raw_emb[i]
            counts[j] += 1
    nonzero = counts > 0
    result[nonzero] /= counts[nonzero, np.newaxis]
    return result


def _mean_embeddings_per_task(
    label_emb: np.ndarray,
    unique_labels: list[str],
    df_long: pd.DataFrame,
    all_task_ids: list[str],
    label_col: str = "dwa_title",
    task_col: str = "task_id",
) -> np.ndarray:
    """Average label embeddings per task → shape (len(all_task_ids), dim).

    Tasks with no entries receive a zero vector.
    Uses vectorized numpy scatter-add for speed.
    """
    dim = label_emb.shape[1]
    label_to_idx = {lbl: i for i, lbl in enumerate(unique_labels)}
    task_to_idx = {tid: i for i, tid in enumerate(all_task_ids)}

    df = df_long[[task_col, label_col]].copy()
    df["_li"] = df[label_col].map(label_to_idx)
    df["_ti"] = df[task_col].astype(str).map(task_to_idx)
    df = df.dropna(subset=["_li", "_ti"])
    li = df["_li"].astype(int).values
    ti = df["_ti"].astype(int).values

    result = np.zeros((len(all_task_ids), dim), dtype=np.float32)
    counts = np.zeros(len(all_task_ids), dtype=np.int32)
    np.add.at(result, ti, label_emb[li])
    np.add.at(counts, ti, 1)
    nonzero = counts > 0
    result[nonzero] /= counts[nonzero, np.newaxis]
    return result


def build_embeddings(
    cfg: RunConfig,
    df_tasks: pd.DataFrame,
    df_dwa_long: pd.DataFrame,
    df_esco_occ: pd.DataFrame,
    df_esco_skills: pd.DataFrame,
    df_isco_groups: pd.DataFrame,
    df_isco_task_items: pd.DataFrame,
) -> tuple[np.ndarray, np.ndarray]:
    """Compute query (O*NET task) and target (ISCO-group) embeddings.

    Query blend (independent dials):
        core  = (1−w_dwa)·task_emb + w_dwa·dwa_avg_emb
        query = (1−w_soc_title)·core + w_soc_title·title_emb

    Target blend (3 independent dials):
        esco_component = w_occ·esco_occ_avg + (1−w_occ)·esco_skill_avg
        isco_component = w_isco_task·isco_task_avg + (1−w_isco_task)·isco_info
        isco_group_emb = w_isco·isco_component + (1−w_isco)·esco_component

    All data is averaged to the appropriate level (per-task for DWAs,
    per-ISCO-group for ESCO/ISCO) before blending.
    """
    if cfg.embedding_model not in _MODEL_CACHE:
        _MODEL_CACHE[cfg.embedding_model] = SentenceTransformer(cfg.embedding_model)
    model = _MODEL_CACHE[cfg.embedding_model]
    all_task_ids = df_tasks["task_id"].astype(str).tolist()
    all_isco_codes = df_isco_groups["isco_code"].tolist()

    # ── Query side ────────────────────────────────────────────────────────────
    task_emb_raw = embed_texts(
        df_tasks["task_text"].tolist(), model, "onet_task_emb_raw", cfg,
    )
    dim = task_emb_raw.shape[1]

    # DWA items: embed unique labels, average per task
    if cfg.w_dwa > 0 and not df_dwa_long.empty:
        unique_dwas = df_dwa_long["dwa_title"].unique().tolist()
        dwa_label_emb = embed_texts(
            unique_dwas, model, "onet_dwa_label_emb_raw", cfg, expected_dim=dim,
        )
        dwa_task_emb = _mean_embeddings_per_task(
            dwa_label_emb, unique_dwas, df_dwa_long, all_task_ids,
        )
        core_emb = normalize(
            (1.0 - cfg.w_dwa) * normalize(task_emb_raw)
            + cfg.w_dwa * normalize(dwa_task_emb)
        )
    else:
        core_emb = normalize(task_emb_raw)

    if cfg.w_soc_title > 0:
        title_emb_raw = embed_texts(
            df_tasks["soc_title_text"].tolist(), model, "onet_title_emb_raw", cfg,
        )
        onet_emb = normalize(
            (1.0 - cfg.w_soc_title) * core_emb
            + cfg.w_soc_title * normalize(title_emb_raw)
        )
    else:
        onet_emb = core_emb

    # ── ESCO occ → group average ──────────────────────────────────────────────
    occ_texts = (
        df_esco_occ["occupationLabel"].fillna("").astype(str) + ". " +
        df_esco_occ["occupationDescription"].fillna("").astype(str)
    ).tolist()
    occ_emb_raw = embed_texts(occ_texts, model, "esco_occ_emb_raw", cfg, expected_dim=dim)
    occ_group_emb = _mean_embeddings_per_group(
        occ_emb_raw, df_esco_occ["iscoGroup"].astype(str).tolist(), all_isco_codes
    )

    # ── ESCO skills → group average ───────────────────────────────────────────
    if cfg.include_esco_skills and not df_esco_skills.empty:
        skill_emb_raw = embed_texts(
            df_esco_skills["preferredLabel"].tolist(), model,
            "esco_skill_label_emb_raw", cfg, expected_dim=dim,
        )
        skill_group_emb = _mean_embeddings_per_group(
            skill_emb_raw, df_esco_skills["iscoGroup"].astype(str).tolist(), all_isco_codes
        )
    else:
        skill_group_emb = np.zeros((len(all_isco_codes), dim), dtype=np.float32)

    # ── ISCO info (title + definition + included occupations) ─────────────────
    isco_info_emb = embed_texts(
        df_isco_groups["isco_info_text"].tolist(), model,
        "isco_info_emb_raw", cfg, expected_dim=dim,
    )

    # ── ISCO task items → group average ──────────────────────────────────────
    if not df_isco_task_items.empty:
        isco_item_emb_raw = embed_texts(
            df_isco_task_items["task_text"].tolist(), model,
            "isco_task_item_emb_raw", cfg, expected_dim=dim,
        )
        isco_task_group_emb = _mean_embeddings_per_group(
            isco_item_emb_raw, df_isco_task_items["isco_code"].tolist(), all_isco_codes
        )
    else:
        isco_task_group_emb = np.zeros((len(all_isco_codes), dim), dtype=np.float32)

    # ── Target blend: 3-dial hierarchical system ─────────────────────────────
    esco_component = cfg.w_occ * occ_group_emb + (1.0 - cfg.w_occ) * skill_group_emb
    isco_component = cfg.w_isco_task * isco_task_group_emb + (1.0 - cfg.w_isco_task) * isco_info_emb
    isco_group_emb = cfg.w_isco * isco_component + (1.0 - cfg.w_isco) * esco_component

    if cfg.normalize_embeddings:
        isco_group_emb = normalize(isco_group_emb)

    return onet_emb, isco_group_emb


# ── Retrieval ─────────────────────────────────────────────────────────────────

def _retrieve_raw(
    df_tasks: pd.DataFrame,
    df_isco_groups: pd.DataFrame,
    distances,
    indices,
    cfg: RunConfig,
) -> pd.DataFrame:
    slim = cfg.slim_output
    rows: list[dict[str, Any]] = []
    for task_idx in range(len(df_tasks)):
        task = df_tasks.iloc[task_idx]
        sims = [float(distances[task_idx, rank]) for rank in range(len(indices[task_idx]))]
        sim1 = sims[0] if sims else float("nan")
        sim2 = sims[1] if len(sims) > 1 else sim1
        simk = sims[-1] if sims else sim1
        best_target = str(df_isco_groups.iloc[indices[task_idx][0]]["isco_code"]) if len(indices[task_idx]) else ""
        scaled = np.exp(np.array(sims, dtype=float) / cfg.softmax_temperature)
        probs = scaled / scaled.sum() if scaled.sum() else np.array([1.0])
        entropy = float(-(probs * np.log(probs + 1e-12)).sum())
        for raw_rank, isco_idx in enumerate(indices[task_idx], start=1):
            isco_row = df_isco_groups.iloc[isco_idx]
            isco_code = str(isco_row["isco_code"])
            row: dict[str, Any] = {
                "task_key": task["task_key"],
                "task_id": task["task_id"],
                "candidate_rank": raw_rank,
                "target_id": isco_code,
                "iscoGroup": isco_code,
                "similarity": float(distances[task_idx, raw_rank - 1]),
                "task_best_similarity": sim1,
                "task_best_target": best_target,
                "gap_1_2": sim1 - sim2,
                "gap_1_k": sim1 - simk,
                "topk_entropy": entropy,
                "is_best": raw_rank == 1,
            }
            if not slim:
                # Decorative columns: not needed for metrics or filtering.
                row["task_text"] = task["task_text"]
                row["task_text_hash"] = task["task_text_hash"]
                row["isco_title"] = str(isco_row["title_en"])
                row["kept_reason"] = "retrieved"
            rows.append(row)
    # Build column-by-column to avoid pandas type-inference overhead (which
    # allocates large complex128 scratch arrays on fragmented heaps).
    if not rows:
        return pd.DataFrame()
    gc.collect()
    cols = list(rows[0].keys())
    return pd.DataFrame({col: [r[col] for r in rows] for col in cols})


def faiss_retrieve(
    task_emb: np.ndarray,
    isco_group_emb: np.ndarray,
    df_tasks: pd.DataFrame,
    df_isco_groups: pd.DataFrame,
    k: int,
    cfg: RunConfig,
) -> pd.DataFrame:
    if cfg.faiss_index_type != "FlatIP":
        raise ValueError("Only FlatIP is implemented")
    index = faiss.IndexFlatIP(isco_group_emb.shape[1])
    index.add(isco_group_emb.astype("float32"))
    k_actual = min(k, len(df_isco_groups))
    distances, indices = index.search(task_emb.astype("float32"), k_actual)
    df = _retrieve_raw(df_tasks, df_isco_groups, distances, indices, cfg)
    df["kept_reason"] = "retrieved"
    return df.sort_values(
        ["task_id", "candidate_rank", "target_id"], ascending=[True, True, True]
    ).reset_index(drop=True)


def _dedupe_targets(df: pd.DataFrame) -> pd.DataFrame:
    if df.empty:
        return df.copy()
    # Core columns always present; optional columns only in full (non-slim) mode.
    core_agg = dict(
        task_key=("task_key", "first"),
        iscoGroup=("iscoGroup", "first"),
        similarity=("similarity", "max"),
        task_best_similarity=("task_best_similarity", "first"),
        task_best_target=("task_best_target", "first"),
        gap_1_2=("gap_1_2", "first"),
        gap_1_k=("gap_1_k", "first"),
        topk_entropy=("topk_entropy", "first"),
        is_best=("is_best", "max"),
    )
    # Decorative columns: present only in full (non-slim) mode.
    optional_agg = dict(
        task_text=("task_text", "first"),
        task_text_hash=("task_text_hash", "first"),
        isco_title=("isco_title", "first"),
        kept_reason=("kept_reason", "first"),
    )
    agg = {k: v for k, v in {**core_agg, **optional_agg}.items() if v[0] in df.columns}
    grouped = df.groupby(["task_id", "target_id"], as_index=False).agg(**agg)
    grouped = grouped.sort_values(
        ["task_id", "similarity", "target_id"], ascending=[True, False, True]
    ).reset_index(drop=True)
    grouped["candidate_rank"] = grouped.groupby("task_id").cumcount() + 1
    return grouped


# ── Pipeline stages ───────────────────────────────────────────────────────────

def apply_task_filter(df_s1: pd.DataFrame, cfg: RunConfig) -> pd.DataFrame:
    if df_s1.empty:
        return df_s1.copy()
    best = (
        df_s1.sort_values(["task_id", "similarity", "target_id"], ascending=[True, False, True])
        .groupby("task_id", group_keys=False)
        .head(1)
        .copy()
    )
    best["kept_reason"] = "best"
    filtered = df_s1.copy()
    filtered = filtered[
        (filtered["similarity"] >= cfg.min_sim) &
        (filtered["similarity"] >= (filtered["task_best_similarity"] - cfg.margin_best))
    ]
    filtered = (
        filtered.sort_values(["task_id", "similarity", "target_id"], ascending=[True, False, True])
        .groupby("task_id", group_keys=False)
        .head(cfg.max_links_per_task)
        .copy()
    )
    filtered["kept_reason"] = np.where(filtered["is_best"], "best", "task_filter")
    kept = pd.concat([best, filtered], ignore_index=True)
    kept = _dedupe_targets(kept)
    return kept


def apply_coverage_backfill(
    df_stage: pd.DataFrame,
    universe_isco: set[str],
    df_s1: pd.DataFrame,
    cfg: RunConfig,
    reason: str = "coverage_backfill",
) -> pd.DataFrame:
    covered = set(df_stage["target_id"].astype(str).unique())
    missing = sorted(universe_isco - covered)
    if not missing or not cfg.enforce_isco_coverage:
        return _dedupe_targets(df_stage)
    add_rows = (
        df_s1[df_s1["target_id"].astype(str).isin(missing)]
        .sort_values(["target_id", "similarity", "task_id"], ascending=[True, False, True])
        .groupby("target_id", group_keys=False)
        .head(1)
        .copy()
    )
    add_rows["kept_reason"] = reason
    combined = pd.concat([df_stage, add_rows], ignore_index=True)
    return _dedupe_targets(combined)


def apply_overload_control(
    df_s3: pd.DataFrame,
    cfg: RunConfig,
) -> tuple[pd.DataFrame, dict[str, Any]]:
    if df_s3.empty or not cfg.enable_overload_control:
        return _dedupe_targets(df_s3), {
            "overload_threshold": None,
            "overloaded_targets": [],
            "pruned_links_count": 0,
            "pruned_tasks_affected_share": 0.0,
        }
    counts = df_s3.groupby("target_id")["task_id"].nunique()
    threshold = max(cfg.overload_abs, int(counts.quantile(cfg.overload_quantile)))
    overloaded = set(counts[counts > threshold].index.astype(str))
    if not overloaded:
        return _dedupe_targets(df_s3), {
            "overload_threshold": threshold,
            "overloaded_targets": [],
            "pruned_links_count": 0,
            "pruned_tasks_affected_share": 0.0,
        }
    mask_overloaded = df_s3["target_id"].astype(str).isin(overloaded)
    mask_non_best = ~df_s3["is_best"].astype(bool)
    mask_low_quality = (
        (df_s3["similarity"] < cfg.overload_min_sim) |
        (df_s3["similarity"] < (df_s3["task_best_similarity"] - cfg.overload_margin_best))
    )
    prune_mask = mask_overloaded & mask_non_best & mask_low_quality
    pruned = df_s3[~prune_mask].copy()
    pruned.loc[mask_overloaded & ~prune_mask, "kept_reason"] = np.where(
        pruned.loc[mask_overloaded & ~prune_mask, "is_best"].astype(bool),
        pruned.loc[mask_overloaded & ~prune_mask, "kept_reason"],
        "overload_retained",
    )
    pruned = _dedupe_targets(pruned)
    affected_tasks = set(df_s3.loc[prune_mask, "task_id"].astype(str))
    info = {
        "overload_threshold": threshold,
        "overloaded_targets": sorted(overloaded),
        "pruned_links_count": int(prune_mask.sum()),
        "pruned_tasks_affected_share": float(len(affected_tasks) / df_s3["task_id"].nunique()),
    }
    return pruned, info


def finalize(
    df_s4: pd.DataFrame,
    universe_isco: set[str],
    df_s1: pd.DataFrame,
    cfg: RunConfig,
) -> pd.DataFrame:
    return apply_coverage_backfill(df_s4, universe_isco, df_s1, cfg, reason="final_coverage_backfill")


# ── Output helpers ────────────────────────────────────────────────────────────

def _stage_output_dir(cfg: RunConfig, run_id: str) -> Path:
    return ensure_dir(Path(cfg.output_dir) / "predictions" / run_id)


def _metrics_dir(cfg: RunConfig) -> Path:
    return ensure_dir(Path(cfg.output_dir) / "metrics")


_FULL_STAGE_COLS = [
    "run_id", "stage", "task_key", "task_id", "task_text", "candidate_rank",
    "iscoGroup", "target_id", "isco_title", "similarity", "task_best_similarity",
    "task_best_target", "gap_1_2", "gap_1_k", "topk_entropy", "is_best",
    "kept_reason", "task_text_hash",
]


def _standardize_stage(df: pd.DataFrame, stage: str, run_id: str) -> pd.DataFrame:
    out = df.copy()
    out["run_id"] = run_id
    out["stage"] = stage
    for col in _FULL_STAGE_COLS:
        if col not in out.columns:
            out[col] = pd.NA
    return out[_FULL_STAGE_COLS]


def _write_stage(df: pd.DataFrame, stage: str, run_id: str, cfg: RunConfig) -> Path:
    if cfg.slim_output:
        # In slim mode skip writing stage CSVs; return a placeholder path.
        return _stage_output_dir(cfg, run_id) / stage
    return write_table(_standardize_stage(df, stage, run_id), _stage_output_dir(cfg, run_id) / stage)


# ── Main pipeline ─────────────────────────────────────────────────────────────

def run_pipeline(cfg: RunConfig | str | Path) -> dict[str, Any]:
    if not isinstance(cfg, RunConfig):
        cfg = load_config(cfg)
    validate_config(cfg)
    random.seed(cfg.random_seed)
    np.random.seed(cfg.random_seed)

    code_version = get_code_version()
    run_id = compute_run_id(cfg, code_version, cfg.data_version)
    run_dir = _stage_output_dir(cfg, run_id)
    save_config(cfg, run_dir / "config.json")
    inputs_hashes = compute_input_hashes(cfg)

    # Load data
    df_tasks = build_task_table(cfg)
    df_dwa_long = load_dwa_long(cfg, df_tasks)
    df_esco_occ = load_esco_occupations(cfg)
    df_esco_skills = (
        load_esco_skills_long(cfg) if cfg.include_esco_skills
        else pd.DataFrame(columns=["iscoGroup", "preferredLabel"])
    )
    df_isco_groups, df_isco_task_items = load_isco_standard(cfg)
    universe_isco = set(df_isco_groups["isco_code"].astype(str).unique())

    # Build embeddings and retrieve
    task_emb, isco_group_emb = build_embeddings(
        cfg, df_tasks, df_dwa_long, df_esco_occ, df_esco_skills,
        df_isco_groups, df_isco_task_items,
    )
    s1 = faiss_retrieve(task_emb, isco_group_emb, df_tasks, df_isco_groups, cfg.k_retrieve, cfg)
    s2 = apply_task_filter(s1, cfg)
    s3 = apply_coverage_backfill(s2, universe_isco, s1, cfg, reason="coverage_backfill")
    s4, overload_info = apply_overload_control(s3, cfg)
    s5 = finalize(s4, universe_isco, s1, cfg)

    stage_tables = {
        "S1_RETRIEVE": s1,
        "S2_TASK_FILTER": s2,
        "S3_COVERAGE": s3,
        "S4_OVERLOAD": s4,
        "S5_FINAL": s5,
    }
    stage_paths: dict[str, str] = {}
    metrics_payload: dict[str, Any] = {}
    metrics_long_rows: list[dict[str, Any]] = []

    prev_df = None
    for stage_name in STAGES:
        stage_df = stage_tables[stage_name]
        stage_path = _write_stage(stage_df, stage_name, run_id, cfg)
        stage_paths[stage_name] = str(stage_path)
        metrics = compute_unsup_metrics(stage_df, cfg, universe_isco, stage_name)
        if prev_df is not None:
            prev_links = set(zip(prev_df["task_id"].astype(str), prev_df["target_id"].astype(str)))
            curr_links = set(zip(stage_df["task_id"].astype(str), stage_df["target_id"].astype(str)))
            metrics["delta_links_vs_prev"] = len(curr_links) - len(prev_links)
            metrics["delta_tasks_with_any_link_vs_prev"] = stage_df["task_id"].nunique() - prev_df["task_id"].nunique()
        else:
            metrics["delta_links_vs_prev"] = 0
            metrics["delta_tasks_with_any_link_vs_prev"] = 0
        if stage_name == "S4_OVERLOAD":
            metrics.update(overload_info)
        metrics["run_id"] = run_id
        metrics["stage"] = stage_name
        metrics_payload[stage_name] = metrics
        metrics_long_rows.append(metrics)
        prev_df = stage_df

    metrics_dir = _metrics_dir(cfg)
    run_metrics_dir = ensure_dir(metrics_dir / run_id)
    metrics_json_path = run_metrics_dir / "metrics.json"
    metrics_json_path.write_text(json.dumps(metrics_payload, indent=2, sort_keys=True), encoding="utf-8")
    flat_metrics_json_path = metrics_dir / f"{run_id}.json"
    flat_metrics_json_path.write_text(json.dumps(metrics_payload, indent=2, sort_keys=True), encoding="utf-8")
    for stage_name, metrics in metrics_payload.items():
        (run_metrics_dir / f"metrics_{stage_name}.json").write_text(
            json.dumps(metrics, indent=2, sort_keys=True), encoding="utf-8"
        )
    metrics_long_df = pd.DataFrame(metrics_long_rows)
    metrics_csv_path = run_metrics_dir / "metrics.csv"
    metrics_long_df.to_csv(metrics_csv_path, index=False)
    append_metrics_long(metrics_long_df, Path(cfg.output_dir) / "metrics" / "metrics_long.csv")

    if not cfg.slim_output:
        final_df = _standardize_stage(s5, "S5_FINAL", run_id)
        ensure_dir(Path(cfg.final_output_path).parent)
        final_df.to_csv(cfg.final_output_path, index=False)
        print(f"Saved final crosswalk: {cfg.final_output_path}")

    manifest_path = save_manifest(
        run_dir,
        cfg,
        run_id,
        inputs_hashes,
        stage_paths,
        metrics_paths={"metrics_json": str(metrics_json_path), "metrics_csv": str(metrics_csv_path)},
        extra={"code_version": code_version, "overload_info": overload_info},
    )

    return {
        "run_id": run_id,
        "stage_paths": stage_paths,
        "metrics_path": str(metrics_json_path),
        "metrics_flat_path": str(flat_metrics_json_path),
        "manifest_path": str(manifest_path),
        "final_output_path": cfg.final_output_path,
        "config": cfg,
        "s5": s5,   # in-memory S5 DataFrame (used by sweep for comparison metrics)
    }


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run the O*NET to ISCO pipeline.")
    parser.add_argument(
        "config",
        nargs="?",
        default=str(Path(__file__).resolve().with_name("config_onet29.yaml")),
        help="Path to a YAML or JSON run config. Defaults to config_onet29.yaml.",
    )
    args = parser.parse_args(argv)
    result = run_pipeline(Path(args.config))
    print(f"Run complete: {result['run_id']}")


if __name__ == "__main__":
    main()
