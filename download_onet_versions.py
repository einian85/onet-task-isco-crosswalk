#!/usr/bin/env python3
"""
download_onet_versions.py

Download O*NET database releases (v4.0–v30.3) and extract only the files
needed by the pipeline into data/onet/<XX_X>/.

Versions with Excel available (v20.1+):
  Extracts Task Statements.xlsx and Tasks to DWAs.xlsx from the Excel zip.

Versions with text only (v4.0–v20.0):
  Finds the task file (name varied across releases), normalises column names
  to the modern standard, and saves as Task Statements.txt.
  No DWA-equivalent exists in the old text releases.

Task file naming across releases:
  v4.0:        Tasks.TXT  (3 cols: O*NET-SOC CODE, TITLE, TASKS; no Task ID)
  v5.0–v12.x:  Tasks.txt  (wide ratings file; has Task ID, Task, Task Type)
  v13.0–v20.0: Task Statements.txt  (modern name, no Title column)

Source: data/version_list.csv (local, no external dependency).
Folder naming: "29.2" → "29_2". Already-present files are skipped.

Usage:
    conda activate onet-isco-nlp
    python download_onet_versions.py
    python download_onet_versions.py --dry-run
    python download_onet_versions.py --versions 4.0 10.0 15.1 29.2
"""

from __future__ import annotations

import argparse
import io
import sys
import time
import zipfile
from pathlib import Path

import pandas as pd
import requests

# ── Configuration ─────────────────────────────────────────────────────────────

VERSION_LIST_CSV  = Path(__file__).parent / "data" / "version_list.csv"
ONET_DATA_DIR     = Path(__file__).parent / "data" / "onet"

EXCEL_TARGET_FILES = ["Task Statements.xlsx", "Tasks to DWAs.xlsx"]

# Old task file names in priority order (first match wins)
OLD_TASK_NAMES = ["Task Statements.txt", "Tasks.txt", "Tasks.TXT"]

# Column renames for pre-v5 analyst-DB format
OLD_COL_MAP = {
    "O*NET-SOC CODE": "O*NET-SOC Code",
    "TITLE":          "Title",
    "TASKS":          "Task",
}
STANDARD_COLS = ["O*NET-SOC Code", "Title", "Task ID", "Task", "Task Type"]

MAX_ATTEMPTS      = 3
RETRY_WAIT_S      = 10
REQUEST_TIMEOUT_S = 300

# ── Helpers ───────────────────────────────────────────────────────────────────

def folder_name(version: str) -> str:
    return version.replace(".", "_")


def version_sort_key(v: str) -> tuple[int, ...]:
    return tuple(int(x) for x in v.split("."))


def download_bytes(url: str) -> bytes:
    for attempt in range(1, MAX_ATTEMPTS + 1):
        try:
            resp = requests.get(url, timeout=REQUEST_TIMEOUT_S, stream=True)
            resp.raise_for_status()
            size_mb = len(resp.content) / 1024 ** 2
            print(f"  downloaded {size_mb:.1f} MB")
            return resp.content
        except Exception as exc:
            print(f"  attempt {attempt}/{MAX_ATTEMPTS} failed: {exc}")
            if attempt < MAX_ATTEMPTS:
                time.sleep(RETRY_WAIT_S)
    raise RuntimeError(f"All {MAX_ATTEMPTS} attempts failed for {url}")


def extract_excel_files(zip_bytes: bytes, dest_dir: Path) -> list[str]:
    """Extract EXCEL_TARGET_FILES from an Excel zip, flat into dest_dir."""
    dest_dir.mkdir(parents=True, exist_ok=True)
    extracted: list[str] = []
    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        name_map = {Path(m).name: m for m in zf.namelist()}
        for target in EXCEL_TARGET_FILES:
            if target in name_map:
                (dest_dir / target).write_bytes(zf.read(name_map[target]))
                extracted.append(target)
    return extracted


def _read_tsv(raw: bytes) -> pd.DataFrame:
    """Read tab-delimited bytes with encoding fallback (old files use cp1252)."""
    for enc in ("utf-8", "cp1252", "latin-1"):
        try:
            return pd.read_csv(io.BytesIO(raw), sep="\t", dtype=str,
                               encoding=enc, low_memory=False)
        except UnicodeDecodeError:
            continue
    raise ValueError("Cannot decode file in utf-8, cp1252, or latin-1")


def extract_text_version(zip_bytes: bytes, dest_dir: Path) -> list[str]:
    """Find, normalise, and save the task statements file from an old text zip.

    Handles three historical task-file formats:
      v4.0        Tasks.TXT            — O*NET-SOC CODE / TITLE / TASKS (no Task ID)
      v5.0–v12.x  Tasks.txt            — O*NET-SOC Code / Task ID / Task / Task Type + stats
      v13.0–v20.0 Task Statements.txt  — O*NET-SOC Code / Task ID / Task / Task Type

    In all formats the Title column (occupation name) comes from Occupation Data.txt
    via a merge on O*NET-SOC Code so that the pipeline can use the occupation title
    for the soc_title embedding blend.  Output is always Task Statements.txt with
    STANDARD_COLS.
    """
    dest_dir.mkdir(parents=True, exist_ok=True)

    with zipfile.ZipFile(io.BytesIO(zip_bytes)) as zf:
        member_map = {Path(m).name: m for m in zf.namelist()}

        # ── Task statements file ──────────────────────────────────────────────
        task_raw = None
        found_name = None
        for candidate in OLD_TASK_NAMES:
            if candidate in member_map:
                task_raw = zf.read(member_map[candidate])
                found_name = candidate
                break

        if task_raw is None:
            print(f"  ERROR: no task file found. zip contents: {sorted(member_map)}")
            return []

        # ── Occupation Data file (for Title merge) ────────────────────────────
        occ_raw = None
        for candidate in ("Occupation Data.txt", "onetsoc_data.txt"):
            if candidate in member_map:
                occ_raw = zf.read(member_map[candidate])
                break

    # ── Parse and normalise task file ─────────────────────────────────────────
    df = _read_tsv(task_raw)
    df = df.rename(columns={k: v for k, v in OLD_COL_MAP.items() if k in df.columns})
    for col in STANDARD_COLS:
        if col not in df.columns:
            df[col] = ""

    # ── Merge occupation titles from Occupation Data ───────────────────────────
    if occ_raw is not None and "Title" not in df.columns.tolist() or df["Title"].eq("").all():
        try:
            occ = _read_tsv(occ_raw)
            # Normalise occupation-data column names (v4.0 uses uppercase)
            occ = occ.rename(columns={
                "O*NET-SOC CODE": "O*NET-SOC Code",
                "ONETSOC":        "O*NET-SOC Code",
                "TITLE":          "Title",
            })
            if {"O*NET-SOC Code", "Title"}.issubset(occ.columns):
                title_map = occ.set_index("O*NET-SOC Code")["Title"].to_dict()
                df["Title"] = df["O*NET-SOC Code"].map(title_map).fillna("")
                print(f"  titles merged from occupation data  "
                      f"({df['Title'].ne('').sum():,}/{len(df):,} tasks have title)")
        except Exception as e:
            print(f"  WARNING: could not merge occupation titles: {e}")

    out_bytes = df[STANDARD_COLS].to_csv(sep="\t", index=False).encode("utf-8")
    (dest_dir / "Task Statements.txt").write_bytes(out_bytes)
    print(f"  normalised from '{found_name}'  ({len(df):,} rows)")
    return ["Task Statements.txt"]


# ── Main ──────────────────────────────────────────────────────────────────────

def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--dry-run", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="Re-download even if output file already exists")
    parser.add_argument("--versions", nargs="*", metavar="VER")
    args = parser.parse_args()

    if not VERSION_LIST_CSV.exists():
        print(f"ERROR: version_list.csv not found at:\n  {VERSION_LIST_CSV}")
        sys.exit(1)

    vlist = pd.read_csv(VERSION_LIST_CSV, dtype={"version": str})
    vlist = vlist[vlist["version"].notna()].copy()

    if args.versions:
        vlist = vlist[vlist["version"].isin(args.versions)]
        missing = set(args.versions) - set(vlist["version"])
        if missing:
            print(f"WARNING: versions not in version_list.csv: {missing}")

    vlist = vlist.sort_values("version", key=lambda s: s.map(version_sort_key)).reset_index(drop=True)

    print(f"Versions to process : {len(vlist)}")
    print(f"Destination root    : {ONET_DATA_DIR.resolve()}")
    if args.dry_run:
        print("DRY-RUN — no files will be downloaded\n")
    print()

    skipped = done = failed = 0

    for _, row in vlist.iterrows():
        ver       = row["version"]
        use_excel = row["excel_available"] == True
        dest_dir  = ONET_DATA_DIR / folder_name(ver)
        primary   = "Task Statements.xlsx" if use_excel else "Task Statements.txt"
        url       = row["url_excel"] if use_excel else row["url_text"]
        fmt       = "excel" if use_excel else "text"

        if (dest_dir / primary).exists() and not args.force:
            print(f"[skip] v{ver:<6}  {dest_dir.name}/")
            skipped += 1
            continue

        if args.dry_run:
            print(f"[would download] v{ver:<6}  {fmt}  → {dest_dir.name}/")
            continue

        print(f"[download] v{ver:<6}  {fmt}  {url}")
        try:
            data = download_bytes(url)
            if use_excel:
                extracted = extract_excel_files(data, dest_dir)
                missing_f = [f for f in EXCEL_TARGET_FILES if f not in extracted]
                print(f"  extracted : {extracted}")
                if missing_f:
                    print(f"  not found : {missing_f}")
            else:
                extracted = extract_text_version(data, dest_dir)

            if primary not in extracted:
                print(f"  ERROR: {primary} missing — cleaning up")
                for f in extracted:
                    (dest_dir / f).unlink(missing_ok=True)
                failed += 1
            else:
                done += 1
        except Exception as exc:
            print(f"  FAILED: {exc}")
            failed += 1

    print(f"\nDone: {done}   Skipped: {skipped}   Failed: {failed}")
    if done:
        print(f"\nNew folders under {ONET_DATA_DIR}:")
        for d in sorted(ONET_DATA_DIR.iterdir(),
                        key=lambda p: version_sort_key(p.name.replace("_", "."))):
            if d.is_dir():
                files = [f.name for f in d.iterdir() if f.suffix in {".xlsx", ".txt"}]
                print(f"  {d.name}/  {files}")


if __name__ == "__main__":
    main()
