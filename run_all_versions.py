#!/usr/bin/env python3
"""
run_all_versions.py

Run the pipeline for every config_onet*.yaml found in the project root,
in ascending version order.  Versions whose output file already exists
are skipped unless --force is passed.

Usage:
    python run_all_versions.py                  # run all missing outputs
    python run_all_versions.py --force          # re-run everything
    python run_all_versions.py --dry-run        # print order without running
    python run_all_versions.py --versions 25.0 29.2   # specific versions only
"""
from __future__ import annotations

import argparse
import re
import time
from pathlib import Path

from config import load_config
from pipeline import run_pipeline


def _ver_from_config(path: Path) -> tuple[int, int] | None:
    m = re.search(r"config_onet(\d+)\.yaml$", path.name)
    if not m:
        return None
    digits = m.group(1)          # e.g. "40", "51", "292", "2100"
    if len(digits) == 2:
        return int(digits[0]), int(digits[1])
    if len(digits) == 3:
        return int(digits[:2]), int(digits[2])
    if len(digits) == 4:
        return int(digits[:2]), int(digits[2:])
    return None


def _ver_str(key: tuple[int, int]) -> str:
    return f"{key[0]}.{key[1]}"


def collect_configs() -> list[tuple[tuple[int, int], Path]]:
    configs = []
    for p in Path("configs").glob("config_onet*.yaml"):
        key = _ver_from_config(p)
        if key is not None:
            configs.append((key, p))
    return sorted(configs, key=lambda x: x[0])


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--force", action="store_true",
                        help="Re-run even if output already exists")
    parser.add_argument("--dry-run", action="store_true",
                        help="Print run order without executing")
    parser.add_argument("--versions", nargs="*", metavar="VER",
                        help="Only run these versions (e.g. 25.0 29.2)")
    args = parser.parse_args()

    all_configs = collect_configs()
    if not all_configs:
        print("No config_onet*.yaml files found.")
        return

    if args.versions:
        wanted = set(args.versions)
        all_configs = [(k, p) for k, p in all_configs if _ver_str(k) in wanted]
        missing = wanted - {_ver_str(k) for k, _ in all_configs}
        if missing:
            print(f"WARNING: no configs found for: {missing}")

    print(f"Found {len(all_configs)} config(s)\n")

    results: list[dict] = []
    for ver_key, cfg_path in all_configs:
        ver = _ver_str(ver_key)
        cfg = load_config(cfg_path)
        out = Path(cfg.final_output_path)

        if out.exists() and not args.force:
            print(f"[skip]  v{ver:<6}  output exists → {out.name}")
            results.append({"version": ver, "status": "skipped"})
            continue

        if args.dry_run:
            print(f"[would run]  v{ver:<6}  {cfg_path.name}  → {out.name}")
            continue

        print(f"\n{'='*60}")
        print(f"Running O*NET {ver}  ({cfg_path.name})")
        print(f"{'='*60}")
        t0 = time.time()
        try:
            result = run_pipeline(cfg_path)
            elapsed = time.time() - t0
            print(f"  Done in {elapsed/60:.1f} min  run_id={result['run_id']}")
            results.append({"version": ver, "status": "ok", "run_id": result["run_id"],
                            "elapsed_min": round(elapsed / 60, 1)})
        except Exception as exc:
            elapsed = time.time() - t0
            print(f"  FAILED after {elapsed/60:.1f} min: {exc}")
            results.append({"version": ver, "status": "failed", "error": str(exc)})

    if results and not args.dry_run:
        print(f"\n{'='*60}")
        print("Summary")
        print(f"{'='*60}")
        for r in results:
            if r["status"] == "ok":
                print(f"  v{r['version']:<6}  OK   {r['elapsed_min']} min")
            elif r["status"] == "skipped":
                print(f"  v{r['version']:<6}  skipped")
            else:
                print(f"  v{r['version']:<6}  FAILED  {r.get('error','')[:80]}")


if __name__ == "__main__":
    main()
