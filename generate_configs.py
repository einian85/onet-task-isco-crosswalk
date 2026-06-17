#!/usr/bin/env python3
"""
generate_configs.py

Auto-generate a config YAML for every O*NET version folder found under
data/onet/.  Existing hand-tuned configs are never overwritten.

SOC taxonomy by version range:
  v4.0  – v9.x : onet_soc_pre2006  (SOC 2000 / DOT-based)
  v10.0 – v13.x: onet_soc_2006
  v14.0 – v15.0: onet_soc_2009
  v15.1 – v25.3: onet_soc_2010     (SOC 2010 standard)
  v26.0+        : onet_soc_2019     (SOC 2018 standard)

Text-only versions (v4.0–v20.0) get two overrides:
  w_dwa=0  — no Tasks-to-DWAs file in any old text release.
  v4.0–v12.x also get use_task_ids=false — Task IDs were introduced gradually
  and are only complete (100% coverage) from v13.0 onward.
  Occupation titles are merged from Occupation Data.txt at download time so
  include_soc_title and w_soc_title remain at sweep values for all versions.

All embedding weights come from the sweep-selected configuration.

Usage:
    python generate_configs.py             # generate all missing configs
    python generate_configs.py --dry-run   # print what would be created
"""
from __future__ import annotations

import argparse
from pathlib import Path

# ── Sweep-selected parameters (identical for all versions) ────────────────────
SWEEP_PARAMS = {
    "use_task_ids": True,
    "output_dir": "results",
    "esco_skills_path": "data/esco/skills_en.csv",
    "esco_occupation_rel_path": "data/esco/occupationSkillRelations_en.csv",
    "esco_occupations_path": "data/esco/occupations_en.csv",
    "data_version": "managed-occupation-standards",
    "esco_release": "ESCO_en",
    "isco_level": 4,
    "random_seed": 42,
    "include_soc_title": True,
    "w_soc_title": 0.375,
    "w_dwa": 0.2656,
    "include_esco_skills": True,
    "isco_tasks_path": "data/isco/ISCO-08 EN Structure and definitions.xlsx",
    "embedding_model": "all-mpnet-base-v2",
    "normalize_embeddings": True,
    "w_isco": 0.375,
    "w_isco_task": 0.7344,
    "w_occ": 0.1562,
    "embedding_cache_dir": "checkpoints",
    "faiss_index_type": "FlatIP",
    "k_retrieve": 5,
    "keep_best_per_task": True,
    "min_sim": 0.45,
    "margin_best": 0.03,
    "max_links_per_task": 1,
    "enforce_isco_coverage": True,
    "coverage_backfill_strategy": "best_task_for_missing_isco",
    "enable_overload_control": True,
    "overload_abs": 200,
    "overload_quantile": 0.95,
    "overload_min_sim": 0.55,
    "overload_margin_best": 0.02,
    "softmax_temperature": 0.05,
    "lowconf_gap_threshold": 0.01,
    "lowconf_entropy_threshold": 1.2,
    "limit_tasks": "null",
}

ONET_DATA_DIR = Path("data/onet")


def version_sort_key(ver: str) -> tuple[int, ...]:
    return tuple(int(x) for x in ver.split("."))


def soc_version(ver: str) -> str:
    major, minor = (int(x) for x in ver.split("."))
    if (major, minor) >= (25, 1):
        return "onet_soc_2019"   # SOC 2018 standard (adopted at O*NET 25.1)
    if (major, minor) >= (15, 1):
        return "onet_soc_2010"   # SOC 2010 standard
    if (major, minor) >= (14, 0):
        return "onet_soc_2009"
    if (major, minor) >= (10, 0):
        return "onet_soc_2006"
    return "onet_soc_pre2006"    # SOC 2000 / DOT-based


def folder_to_version(folder_name: str) -> str:
    """'29_2' → '29.2'"""
    return folder_name.replace("_", ".", 1)


def version_to_tag(ver: str) -> str:
    """'29.2' → 'ONET292'"""
    return "ONET" + ver.replace(".", "")


def config_path_for(ver: str) -> Path:
    tag = version_to_tag(ver).lower()  # config_onet292.yaml
    return Path("configs") / f"config_{tag}.yaml"


def _has_excel(ver: str) -> bool:
    major, minor = (int(x) for x in ver.split("."))
    return (major, minor) >= (20, 1)


def _text_only_overrides(ver: str) -> dict:
    """Parameter overrides for text-only releases (v4.0–v20.0).

    Occupation titles are merged from Occupation Data.txt at download time, so
    include_soc_title and w_soc_title stay at sweep values for all versions.
    Only two things differ from sweep defaults:
      - w_dwa: 0.0  — no Tasks-to-DWAs file exists in any old text release
      - use_task_ids: False  — v4.0–v12.x; Task IDs are only fully populated
                               from v13.0 onward (0% in v4.0, 7% in v5.0,
                               rising to 96% in v12.0, 100% from v13.0)
    """
    major, minor = (int(x) for x in ver.split("."))
    overrides: dict = {"w_dwa": 0.0}
    if (major, minor) < (13, 0):
        overrides["use_task_ids"] = False
    return overrides


def render_yaml(ver: str) -> str:
    ver_str = ver.replace(".", "_")
    tag = version_to_tag(ver)
    soc = soc_version(ver)
    use_excel = _has_excel(ver)
    ext = "xlsx" if use_excel else "txt"
    fmt_label = f"db_{ver_str}_excel" if use_excel else f"db_{ver_str}_text"

    params = dict(SWEEP_PARAMS)
    if not use_excel:
        params.update(_text_only_overrides(ver))

    lines = [
        f"# O*NET {ver} — {soc} taxonomy",
        f"dataset_name: {tag}",
        f"checkpoint_prefix: {tag}",
        f"final_output_path: output/{tag}_task_to_ISCO_crosswalk.csv",
        f"onet_tasks_path: data/onet/{ver_str}/Task Statements.{ext}",
        f"onet_tasks_dwa_path: data/onet/{ver_str}/Tasks to DWAs.{ext}",
        f"onet_release: {fmt_label}",
        f"# soc_version: {soc}",
        "# ── Query-side blend weights ──────────────────────────────────────────",
    ]
    for k, v in params.items():
        if isinstance(v, bool):
            lines.append(f"{k}: {'true' if v else 'false'}")
        elif v == "null":
            lines.append(f"{k}: null")
        else:
            lines.append(f"{k}: {v}")
    return "\n".join(lines) + "\n"


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    args = parser.parse_args()

    if not ONET_DATA_DIR.exists():
        print(f"ERROR: {ONET_DATA_DIR} not found — run download_onet_versions.py first.")
        return

    folders = sorted(
        [d.name for d in ONET_DATA_DIR.iterdir() if d.is_dir()],
        key=version_sort_key,
    )
    versions = [folder_to_version(f) for f in folders]

    created = skipped = 0
    for ver in versions:
        dest = config_path_for(ver)
        if dest.exists():
            print(f"[skip]   {dest.name}  (already exists)")
            skipped += 1
            continue
        yaml_text = render_yaml(ver)
        if args.dry_run:
            print(f"[would create] {dest.name}")
        else:
            dest.write_text(yaml_text, encoding="utf-8")
            print(f"[created] {dest.name}  (O*NET {ver}, {soc_version(ver)})")
        created += 1

    action = "Would create" if args.dry_run else "Created"
    print(f"\n{action}: {created}   Skipped (existing): {skipped}")


if __name__ == "__main__":
    main()
