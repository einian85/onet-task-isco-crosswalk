from __future__ import annotations

import hashlib
import json
import subprocess
from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

try:
    import yaml  # type: ignore
except ImportError:
    yaml = None


@dataclass
class RunConfig:
    dataset_name: str
    checkpoint_prefix: str
    use_task_ids: bool
    output_dir: str
    final_output_path: str
    onet_tasks_path: str
    onet_tasks_dwa_path: str
    onet_tasks_cat_path: str
    esco_skills_path: str
    esco_occupation_rel_path: str
    esco_occupations_path: str
    data_version: str
    onet_release: str
    esco_release: str
    isco_level: int
    random_seed: int
    include_soc_title: bool = False
    # ── Query-side blend weights (independent dials — no sum constraint) ─────────
    #   w_soc_title : separate SOC-title embedding blended into query (0 = text-prepend)
    #   w_dwa       : separate DWA-items embedding blended into query core (0 = no DWA)
    # Query blend: core = (1−w_dwa)·task_emb + w_dwa·dwa_avg_emb
    #              query = (1−w_soc_title)·core + w_soc_title·title_emb
    # DWA items are embedded individually and averaged per task (not concatenated).
    w_soc_title: float = 0.0       # separate SOC-title embedding weight
    w_dwa: float = 0.0             # DWA items embedding weight (0 = DWAs unused)
    include_esco_skills: bool = True
    # ── ISCO-08 standard (target-side) ──────────────────────────────────────────
    isco_tasks_path: str = "data/isco/ISCO-08 EN Structure and definitions.xlsx"
    # ── Target-side blend weights (3 independent dials — no sum constraint) ─────
    #   w_isco      : ISCO-group vs ESCO blend (0 = pure ESCO, 1 = pure ISCO)
    #   w_isco_task : within ISCO: task items vs info text (0 = pure info text)
    #   w_occ       : within ESCO: occ vs skill (skill = 1 − w_occ)
    # Final blend: w_isco·(w_isco_task·isco_task_avg + (1−w_isco_task)·isco_info)
    #            + (1−w_isco)·(w_occ·esco_occ_avg + (1−w_occ)·esco_skill_avg)
    # All ESCO data is averaged to ISCO-group level before blending.
    embedding_model: str = "all-mpnet-base-v2"
    normalize_embeddings: bool = True
    w_isco: float = 0.0          # ISCO share; 0 = pure ESCO (legacy default)
    w_isco_task: float = 0.0     # within ISCO: task items vs info text
    w_occ: float = 0.85          # occ share within ESCO component; skill = 1 - w_occ
    embedding_cache_dir: str = "checkpoints"
    faiss_index_type: str = "FlatIP"
    k_retrieve: int = 5
    keep_best_per_task: bool = True
    min_sim: float = 0.45
    margin_best: float = 0.03
    max_links_per_task: int = 3
    enforce_isco_coverage: bool = True
    coverage_backfill_strategy: str = "best_task_for_missing_isco"
    enable_overload_control: bool = True
    overload_abs: int = 200
    overload_quantile: float = 0.95
    overload_min_sim: float = 0.55
    overload_margin_best: float = 0.02
    softmax_temperature: float = 0.05
    lowconf_gap_threshold: float = 0.01
    lowconf_entropy_threshold: float = 1.2
    limit_tasks: int | None = None
    slim_output: bool = False   # sweep mode: skip stage CSVs and final crosswalk write

    def to_dict(self) -> dict[str, Any]:
        return asdict(self)

    def to_hash_dict(self) -> dict[str, Any]:
        """Dict used for run-ID hashing — excludes output-mode flags."""
        d = self.to_dict()
        d.pop("slim_output", None)
        return d


KNOWN_FIELDS = {f.name for f in fields(RunConfig)}


def _canonicalize(obj: Any) -> Any:
    if isinstance(obj, dict):
        return {k: _canonicalize(obj[k]) for k in sorted(obj)}
    if isinstance(obj, list):
        return [_canonicalize(v) for v in obj]
    if isinstance(obj, float):
        return float(f"{obj:.12g}")
    return obj



def canonical_json(data: Any) -> str:
    return json.dumps(_canonicalize(data), sort_keys=True, ensure_ascii=True, separators=(",", ":"))



def load_yaml_or_json(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    text = p.read_text(encoding="utf-8")
    if p.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is not installed; cannot load YAML config")
        return yaml.safe_load(text)
    return json.loads(text)



def load_config(path: str | Path) -> RunConfig:
    raw = load_yaml_or_json(path)
    unknown = set(raw) - KNOWN_FIELDS
    if unknown:
        raise ValueError(f"Unknown config keys: {sorted(unknown)}")
    cfg = RunConfig(**raw)
    validate_config(cfg)
    return cfg



def save_config(cfg: RunConfig, path: str | Path) -> None:
    p = Path(path)
    p.parent.mkdir(parents=True, exist_ok=True)
    payload = canonical_json(cfg.to_dict())
    if p.suffix.lower() in {".yaml", ".yml"}:
        if yaml is None:
            raise RuntimeError("PyYAML is not installed; cannot save YAML config")
        p.write_text(yaml.safe_dump(json.loads(payload), sort_keys=True), encoding="utf-8")
    else:
        p.write_text(json.dumps(json.loads(payload), indent=2, sort_keys=True), encoding="utf-8")



def validate_config(cfg: RunConfig) -> None:
    if not 0 <= cfg.w_isco <= 1:
        raise ValueError("w_isco must be in [0, 1]")
    if not 0 <= cfg.w_isco_task <= 1:
        raise ValueError("w_isco_task must be in [0, 1]")
    if not 0 <= cfg.w_occ <= 1:
        raise ValueError("w_occ must be in [0, 1]")
    if cfg.k_retrieve < max(cfg.max_links_per_task, 5):
        raise ValueError("k_retrieve must be >= max_links_per_task and >= 5")
    if not 0 <= cfg.min_sim <= 1:
        raise ValueError("min_sim must be in [0,1]")
    if not 0 <= cfg.margin_best <= 1:
        raise ValueError("margin_best must be in [0,1]")
    if not 0 <= cfg.overload_min_sim <= 1:
        raise ValueError("overload_min_sim must be in [0,1]")
    if not 0 <= cfg.overload_margin_best <= 1:
        raise ValueError("overload_margin_best must be in [0,1]")
    if not 0 < cfg.overload_quantile < 1:
        raise ValueError("overload_quantile must be in (0,1)")
    if cfg.max_links_per_task < 1:
        raise ValueError("max_links_per_task must be >= 1")
    if not 0 <= cfg.w_soc_title <= 1:
        raise ValueError("w_soc_title must be in [0, 1]")
    if cfg.w_soc_title > 0 and not cfg.include_soc_title:
        raise ValueError("w_soc_title > 0 requires include_soc_title=True")
    if not 0 <= cfg.w_dwa <= 1:
        raise ValueError("w_dwa must be in [0, 1]")
    if cfg.faiss_index_type != "FlatIP":
        raise ValueError("Only FlatIP is currently implemented")
    if cfg.coverage_backfill_strategy != "best_task_for_missing_isco":
        raise ValueError("Only best_task_for_missing_isco is currently implemented")
    if cfg.softmax_temperature <= 0:
        raise ValueError("softmax_temperature must be > 0")
    if cfg.limit_tasks is not None and cfg.limit_tasks < 1:
        raise ValueError("limit_tasks must be >=1 if provided")



def stable_hash(obj: Any) -> str:
    return hashlib.sha256(canonical_json(obj).encode("utf-8")).hexdigest()



def get_code_version() -> str:
    try:
        out = subprocess.check_output(["git", "rev-parse", "HEAD"], stderr=subprocess.DEVNULL, text=True).strip()
        if out:
            return out
    except Exception:
        pass
    return "manual-no-git"



def compute_run_id(cfg: RunConfig, code_version: str, data_version: str) -> str:
    return stable_hash({"config": cfg.to_hash_dict(), "code_version": code_version, "data_version": data_version})[:16]


def compute_overload_threshold(counts, cfg: RunConfig) -> float:
    """Shared helper so pipeline and metrics use identical overload threshold logic."""
    return max(float(cfg.overload_abs), float(counts.quantile(cfg.overload_quantile)))



def file_signature(path: str | Path) -> dict[str, Any]:
    p = Path(path)
    stat = p.stat()
    return {"path": str(p), "size": stat.st_size, "mtime_ns": stat.st_mtime_ns}



def compute_input_hashes(cfg: RunConfig) -> dict[str, Any]:
    keys = [
        "onet_tasks_path",
        "onet_tasks_dwa_path",
        "onet_tasks_cat_path",
        "esco_skills_path",
        "esco_occupation_rel_path",
        "esco_occupations_path",
        "isco_tasks_path",
    ]
    return {key: file_signature(getattr(cfg, key)) for key in keys}



def save_manifest(
    run_dir: str | Path,
    cfg: RunConfig,
    run_id: str,
    inputs_hashes: dict[str, Any],
    stage_paths: dict[str, str],
    metrics_paths: dict[str, str] | None = None,
    extra: dict[str, Any] | None = None,
) -> Path:
    payload = {
        "run_id": run_id,
        "config": cfg.to_dict(),
        "inputs_hashes": inputs_hashes,
        "stage_paths": stage_paths,
        "metrics_paths": metrics_paths or {},
        "extra": extra or {},
    }
    path = Path(run_dir) / "run_manifest.json"
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2, sort_keys=True), encoding="utf-8")
    return path



def dataset_preset(name: str) -> RunConfig:
    common = dict(
        output_dir="results",
        include_soc_title=True,
        esco_skills_path="data/esco/skills_en.csv",
        esco_occupation_rel_path="data/esco/occupationSkillRelations_en.csv",
        esco_occupations_path="data/esco/occupations_en.csv",
        esco_release="ESCO_en",
        isco_level=4,
        random_seed=42,
        data_version="managed-occupation-standards",
    )
    presets = {
        "ONET29": RunConfig(
            dataset_name="ONET29",
            checkpoint_prefix="ONET29",
            use_task_ids=True,
            final_output_path="output/ONET29_task_to_ISCO_crosswalk.csv",
            onet_tasks_path="data/onet/29_2/Task Statements.xlsx",
            onet_tasks_dwa_path="data/onet/29_2/Tasks to DWAs.xlsx",
            onet_tasks_cat_path="data/onet/29_2/Task Categories.xlsx",
            onet_release="db_29_2_excel",
            **common,
        ),
        "ONET25": RunConfig(
            dataset_name="ONET25",
            checkpoint_prefix="ONET25",
            use_task_ids=True,
            final_output_path="output/ONET25_task_to_ISCO_crosswalk.csv",
            onet_tasks_path="data/onet/25_0/Task Statements.xlsx",
            onet_tasks_dwa_path="data/onet/25_0/Tasks to DWAs.xlsx",
            onet_tasks_cat_path="data/onet/25_0/Task Categories.xlsx",
            onet_release="db_25_0_excel",
            **common,
        ),
        "ONET25txt": RunConfig(
            dataset_name="ONET25txt",
            checkpoint_prefix="ONET25txt",
            use_task_ids=False,
            final_output_path="output/ONET25txt_task_to_ISCO_crosswalk.csv",
            onet_tasks_path="data/onet/25_0/Task Statements.xlsx",
            onet_tasks_dwa_path="data/onet/25_0/Tasks to DWAs.xlsx",
            onet_tasks_cat_path="data/onet/25_0/Task Categories.xlsx",
            onet_release="db_25_0_excel",
            **{**common, "include_soc_title": False},
        ),
    }
    cfg = presets[name]
    validate_config(cfg)
    return cfg
