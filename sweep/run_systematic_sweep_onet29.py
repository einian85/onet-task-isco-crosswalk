"""
run_systematic_sweep_onet29.py
=================================
Adaptive iterative sweep over all 5 blend parameters.
Tags: r1_s750_d012_i62_t64_o83  (round / param values).

Strategy
--------
Each round uses exactly 5 values per parameter.

Round 1: uniformly-spaced 5-point grid across the full plausible range.
Round k: zoom from Round k-1 best config.
  For each parameter with best value b and previous grid values g:
    nb_lo = nearest g value strictly below b  (or lo_bound)
    nb_hi = nearest g value strictly above b  (or hi_bound)
    new grid = [nb_lo, (nb_lo+b)/2, b, (b+nb_hi)/2, nb_hi]
  This halves the step each round while always covering the full
  neighbor-to-neighbor interval around the current best.

Stop when best-score improvement < CONVERGENCE_THRESHOLD or MAX_ROUNDS reached.

Each round is restartable: a config is skipped if its metrics file already
exists on disk (safe to Ctrl-C and re-run at any time).

Usage (from the project root):
    python sweep/run_systematic_sweep_onet29.py
"""

from __future__ import annotations

import contextlib
import gc
import io
import itertools
import sys
import time
from dataclasses import replace
from pathlib import Path

import numpy as np
import pandas as pd

ROOT_DIR = Path(__file__).resolve().parent.parent
if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8")
sys.path.insert(0, str(ROOT_DIR))

from config import load_config, compute_run_id, get_code_version
from pipeline import run_pipeline
from sweep import _add_composite_score, _add_pareto_flag, _flatten_config

# ── Paths ─────────────────────────────────────────────────────────────────────
BASE_CONFIG  = str(ROOT_DIR / "config_onet29.yaml")
SUMMARY_DIR  = ROOT_DIR / "results" / "summary"
SUMMARY_PATH = SUMMARY_DIR / "sweep_results_metrics_only.csv"
SUMMARY_DIR.mkdir(parents=True, exist_ok=True)

base             = load_config(BASE_CONFIG)
code_version     = get_code_version()
metrics_root     = ROOT_DIR / base.output_dir / "metrics"
CHECKPOINT_PATH  = metrics_root / "checkpoints.csv"

# ── Settings ──────────────────────────────────────────────────────────────────
MAX_QUERY_USED       = 0.90    # w_soc + w_dwa ≤ this  (keeps ≥10% raw task text)
N_VALUES             = 5       # values per parameter per round
MAX_ROUNDS           = 20      # safety cap on total rounds
CONVERGENCE_THRESHOLD = 0.0005 # stop when best-score improvement < this

PARAM_BOUNDS = {
    "w_soc_title": (0.00, 1.00),
    "w_dwa":       (0.00, 1.00),
    "w_isco":      (0.00, 1.00),
    "w_isco_task": (0.00, 1.00),
    "w_occ":       (0.00, 1.00),
}

# ── Sweep score ───────────────────────────────────────────────────────────────
# Fixed raw weighted sum — no min-max normalization, so directly comparable
# across rounds. Used for both finding the best config and convergence.

def _sweep_score(row) -> float:
    cov      = float(row.get("S5_FINAL_isco_coverage_share") or 0)
    sim      = float(row.get("S5_FINAL_mean_similarity_retained") or 0)
    overload = float(row.get("S5_FINAL_share_tasks_in_overloaded_isco") or 0)
    gini     = float(row.get("S5_FINAL_gini_tasks_per_isco") or 0)
    return (3*cov + 2*sim - 2*overload - 2*gini) / 9


# ── Helpers ───────────────────────────────────────────────────────────────────

def _fmt_time(seconds: float) -> str:
    seconds = int(seconds)
    if seconds < 60:
        return f"{seconds}s"
    m, s = divmod(seconds, 60)
    if m < 60:
        return f"{m}m {s:02d}s"
    h, m = divmod(m, 60)
    return f"{h}h {m:02d}m {s:02d}s"


def _make_tag(phase: str, soc: float, dwa: float,
              wi: float, wt: float, wo: float) -> str:
    return (f"{phase}"
            f"_s{round(soc * 1000):03d}"
            f"_d{round(dwa * 1000):03d}"
            f"_i{round(wi  * 100):02d}"
            f"_t{round(wt  * 100):02d}"
            f"_o{round(wo  * 100):02d}")


def _stable_tag(soc: float, dwa: float,
                wi: float, wt: float, wo: float) -> str:
    """Tag used for output path — round-independent."""
    return (f"s{round(soc * 1000):03d}"
            f"_d{round(dwa * 1000):03d}"
            f"_i{round(wi  * 100):02d}"
            f"_t{round(wt  * 100):02d}"
            f"_o{round(wo  * 100):02d}")


def _build_configs(phase: str, grid: dict[str, list[float]]) -> list:
    out_dir = ROOT_DIR / "output" / "sweep_all"
    out_dir.mkdir(parents=True, exist_ok=True)
    cfgs = []
    for soc, dwa, wi, wt, wo in itertools.product(
        grid["w_soc_title"], grid["w_dwa"],
        grid["w_isco"], grid["w_isco_task"], grid["w_occ"],
    ):
        if soc + dwa > MAX_QUERY_USED:
            continue
        display_tag = _make_tag(phase, soc, dwa, wi, wt, wo)
        stable      = _stable_tag(soc, dwa, wi, wt, wo)
        cfgs.append(replace(
            base,
            dataset_name=display_tag,
            checkpoint_prefix="ONET29",
            slim_output=True,
            w_soc_title=soc,
            w_dwa=dwa,
            include_soc_title=True,
            w_isco=wi,
            w_isco_task=wt,
            w_occ=wo,
            final_output_path=str(out_dir / f"{stable}_crosswalk.csv"),
        ))
    return cfgs


def _run_id(cfg) -> str:
    return compute_run_id(cfg, code_version, cfg.data_version)


# ── Checkpoint cache (primary) ────────────────────────────────────────────────
# Single checkpoints.csv holds one flat row per completed slim run.
# Loaded once at startup into a dict keyed by run_id.

_PARAM_COLS = ["w_soc_title", "w_dwa", "w_isco", "w_isco_task", "w_occ"]

# Primary checkpoint cache: run_id -> flat metrics row dict, loaded from checkpoints.csv
_checkpoint_cache: dict | None = None
# Secondary fallback: param-tuple -> summary row dict, loaded from summary CSV
_summary_cache: dict | None = None


def _load_checkpoint_cache() -> dict:
    global _checkpoint_cache
    if _checkpoint_cache is not None:
        return _checkpoint_cache
    _checkpoint_cache = {}
    if not CHECKPOINT_PATH.exists():
        return _checkpoint_cache
    df = _safe_read_csv(CHECKPOINT_PATH)
    if df is not None and "run_id" in df.columns:
        for _, row in df.iterrows():
            _checkpoint_cache[str(row["run_id"])] = row.to_dict()
    print(f"  Checkpoint cache loaded: {len(_checkpoint_cache)} completed runs.")
    return _checkpoint_cache


def _load_summary_cache() -> dict:
    global _summary_cache
    if _summary_cache is not None:
        return _summary_cache
    _summary_cache = {}
    if not SUMMARY_PATH.exists():
        return _summary_cache
    df = _safe_read_csv(SUMMARY_PATH)
    if df is None or not all(p in df.columns for p in _PARAM_COLS):
        return _summary_cache
    scored = df[df["selection_score"].notna()] if "selection_score" in df.columns else df
    for _, row in scored.iterrows():
        key = tuple(round(float(row[p]), 4) for p in _PARAM_COLS)
        if key not in _summary_cache:
            _summary_cache[key] = row.to_dict()
    print(f"  Summary cache loaded: {len(_summary_cache)} unique param combinations.")
    return _summary_cache


def _param_key(cfg) -> tuple:
    return tuple(round(getattr(cfg, p), 4) for p in _PARAM_COLS)


def _is_done(cfg) -> bool:
    return _run_id(cfg) in _load_checkpoint_cache() or _param_key(cfg) in _load_summary_cache()


def _safe_read_csv(path: Path) -> pd.DataFrame | None:
    try:
        df = pd.read_csv(path, low_memory=False)
        return df if not df.empty else None
    except Exception:
        return None


def _make_row(run_output: dict) -> dict | None:
    metrics_df = run_output.get("metrics_df")
    if metrics_df is None:
        return None
    cfg_obj = run_output.get("config")
    cfg_data = _flatten_config(cfg_obj) if cfg_obj is not None else {}
    row: dict = {"run_id": run_output["run_id"]}
    row.update(cfg_data)
    for _, mrow in metrics_df.iterrows():
        stage = mrow["stage"]
        for key, val in mrow.items():
            if key not in {"run_id", "stage"}:
                row[f"{stage}_{key}"] = val
    # Keep checkpoint cache in sync within this session
    _load_checkpoint_cache()[str(run_output["run_id"])] = row
    return row


def _row_from_cache(cfg) -> dict | None:
    rid = _run_id(cfg)
    cached_row = _load_checkpoint_cache().get(rid)
    if cached_row is not None:
        row = dict(cached_row)
        row.update(_flatten_config(cfg))
        row["run_id"] = rid
        return row
    # Fall back to summary cache for configs from previous runs/schemes
    key = _param_key(cfg)
    cached = _load_summary_cache().get(key)
    if cached is not None:
        row = dict(cached)
        row.update(_flatten_config(cfg))
        row["run_id"] = rid
        return row
    return None


def _merge_into_summary(new_rows: list[dict]) -> pd.DataFrame:
    new_df = pd.DataFrame(new_rows) if new_rows else pd.DataFrame()
    if SUMMARY_PATH.exists():
        _prev = _safe_read_csv(SUMMARY_PATH)
        prev = _prev if _prev is not None else pd.DataFrame()
        if not new_df.empty:
            existing_ids = set(new_df["run_id"].astype(str))
            prev = prev[~prev["run_id"].astype(str).isin(existing_ids)]
            combined = pd.concat([new_df, prev], ignore_index=True)
        else:
            combined = prev
    else:
        combined = new_df
    if combined.empty:
        return combined
    combined = _add_composite_score(combined)
    combined = _add_pareto_flag(combined)
    if "selection_score" in combined.columns:
        combined = combined.sort_values(
            ["pareto_candidate", "selection_score"], ascending=[False, False]
        ).reset_index(drop=True)
        combined["selection_rank"] = range(1, len(combined) + 1)
    combined.to_csv(SUMMARY_PATH, index=False)

    # Keep in-memory cache in sync so cross-round deduplication works within a
    # single uninterrupted run (not just across Ctrl-C / restart cycles).
    global _summary_cache
    if _summary_cache is not None and all(p in combined.columns for p in _PARAM_COLS):
        scored = combined[combined["selection_score"].notna()] if "selection_score" in combined.columns else combined
        for _, row in scored.iterrows():
            key = tuple(round(float(row[p]), 4) for p in _PARAM_COLS)
            if key not in _summary_cache:
                _summary_cache[key] = row.to_dict()

    return combined


def _run_phase(phase_label: str, configs: list) -> list[dict]:
    """
    Run all configs not already done.  Shows a live progress bar with ETA.
    Returns list of result rows (new + cached).
    """
    todo  = [c for c in configs if not _is_done(c)]
    cache = [c for c in configs if _is_done(c)]

    print(f"\n{'━'*70}")
    print(f"  PHASE {phase_label}  —  {len(configs)} configs  "
          f"({len(cache)} cached, {len(todo)} to run)")
    print(f"{'━'*70}")

    rows: list[dict] = []

    # Collect cached rows
    for cfg in cache:
        r = _row_from_cache(cfg)
        if r:
            rows.append(r)

    if not todo:
        print("  All configs already complete — loading from cache.")
        return rows

    # ── Progress tracking ────────────────────────────────────────────────────
    n_total    = len(todo)
    n_done     = 0
    times: list[float] = []          # per-config wall times
    phase_start = time.time()

    BAR_WIDTH  = 40
    SAVE_EVERY = 50   # flush to summary CSV every N completed configs

    def _print_progress(current: int, total: int) -> None:
        frac    = current / total if total else 1.0
        filled  = int(BAR_WIDTH * frac)
        bar     = "█" * filled + "░" * (BAR_WIDTH - filled)
        elapsed = time.time() - phase_start
        if times:
            avg_t = sum(times) / len(times)
            eta   = avg_t * (total - current)
            eta_s = f"ETA {_fmt_time(eta)}"
            speed = f"{avg_t:.1f}s/cfg"
        else:
            eta_s = "ETA --"
            speed = ""
        line = f"  [{bar}] {current}/{total}  elapsed {_fmt_time(elapsed)}  {eta_s}  {speed}"
        print(f"\r{line:<90}", end="", flush=True)

    _print_progress(0, n_total)

    try:
        for cfg in todo:
            t0  = time.time()
            try:
                with contextlib.redirect_stdout(io.StringIO()):
                    out = run_pipeline(cfg)
                t1 = time.time()
                times.append(t1 - t0)
                r = _make_row(out)
                if r:
                    rows.append(r)
                del out
            except Exception as e:
                print(f"\n  [error] {cfg.dataset_name}: {type(e).__name__}: {e} — skipping", flush=True)
            gc.collect()
            n_done += 1
            _print_progress(n_done, n_total)
            if n_done % SAVE_EVERY == 0 and rows:
                _merge_into_summary(rows)

    except KeyboardInterrupt:
        print(f"\n  [Ctrl-C]  {n_done}/{n_total} completed — saving progress …")

    elapsed_total = time.time() - phase_start
    print(f"\n  Phase {phase_label} done in {_fmt_time(elapsed_total)}.  "
          f"{n_done} new configs run.")
    return rows


def _initial_grid() -> dict[str, list[float]]:
    """Round 1: N_VALUES uniformly-spaced points across each param's full range."""
    grid: dict[str, list[float]] = {}
    for param, (lo, hi) in PARAM_BOUNDS.items():
        vals = np.linspace(lo, hi, N_VALUES)
        grid[param] = [round(float(v), 4) for v in vals]
    return grid

def _zoom_grid(best_vals: dict[str, float],
               prev_grid: dict[str, list[float]]) -> dict[str, list[float]]:
    """
    Adaptive trust-region grid.

    Rules:
      1. Always return all parameters in PARAM_BOUNDS.
      2. If best is interior: shrink step and refine around best.
      3. If best is at a local grid boundary but not a global parameter bound:
         expand outward using the current step.
      4. If best is at a true global bound:
         use one-sided local refinement.
      5. Prevent one dimension from becoming much finer than the others.
    """

    EPS = 1e-9
    ROUND = 4

    # Current local step per parameter
    steps: dict[str, float] = {}

    for p, (lo_bound, hi_bound) in PARAM_BOUNDS.items():
        vals = sorted(prev_grid[p])
        diffs = [vals[i + 1] - vals[i] for i in range(len(vals) - 1)]
        steps[p] = (
            min(diffs)
            if diffs
            else (hi_bound - lo_bound) / (N_VALUES - 1)
        )

    # Step-balance rule
    min_step_allowed = max(steps.values()) / 4.0

    grid: dict[str, list[float]] = {}

    for param, (lo_bound, hi_bound) in PARAM_BOUNDS.items():
        b = best_vals[param]
        prev_vals = sorted(prev_grid[param])

        lo_prev = min(prev_vals)
        hi_prev = max(prev_vals)
        h = steps[param]

        at_grid_lower = abs(b - lo_prev) < EPS
        at_grid_upper = abs(b - hi_prev) < EPS
        at_global_lower = abs(b - lo_bound) < EPS
        at_global_upper = abs(b - hi_bound) < EPS

        h_shrunk = max(h / 2.0, min_step_allowed)

        # Case 1: local lower boundary, but not true lower bound
        if at_grid_lower and not at_global_lower:
            pts = [
                round(max(lo_bound, min(hi_bound, b + k * h)), ROUND)
                for k in range(-2, 3)
            ]

        # Case 2: local upper boundary, but not true upper bound
        elif at_grid_upper and not at_global_upper:
            pts = [
                round(max(lo_bound, min(hi_bound, b + k * h)), ROUND)
                for k in range(-2, 3)
            ]

        # Case 3: true global lower bound
        elif at_global_lower:
            pts = [
                round(min(hi_bound, b + k * h_shrunk), ROUND)
                for k in range(N_VALUES)
            ]

        # Case 4: true global upper bound
        elif at_global_upper:
            pts = [
                round(max(lo_bound, b - k * h_shrunk), ROUND)
                for k in range(N_VALUES)
            ]

        # Case 5: interior
        else:
            half = N_VALUES // 2
            pts = [
                round(max(lo_bound, min(hi_bound, b + k * h_shrunk)), ROUND)
                for k in range(-half, half + 1)
            ]

        # Always include the current best
        pts.append(round(b, ROUND))

        # Unique and sorted
        pts = sorted(set(pts))

        # If clipping caused too few points, fill locally around best
        if len(pts) < N_VALUES:
            extra = []
            for k in range(-N_VALUES, N_VALUES + 1):
                x = b + k * h_shrunk
                if lo_bound <= x <= hi_bound:
                    extra.append(round(x, ROUND))
            pts = sorted(set(pts + extra))

        # Keep the N_VALUES closest points to the current best
        if len(pts) > N_VALUES:
            pts = sorted(
                sorted(pts, key=lambda x: abs(x - b))[:N_VALUES]
            )

        grid[param] = pts

    missing = set(PARAM_BOUNDS) - set(grid)
    if missing:
        raise RuntimeError(f"_zoom_grid did not create grids for: {missing}")

    return grid



def _round_summary(sub: pd.DataFrame, best_row: "pd.Series", grid: dict) -> None:
    print(f"\n  Best config ({len(sub)} evaluated this round):")
    for p in ["w_soc_title", "w_dwa", "w_isco", "w_isco_task", "w_occ"]:
        val       = float(best_row[p])
        at_min    = abs(val - min(grid[p])) < 1e-9
        at_max    = abs(val - max(grid[p])) < 1e-9
        boundary  = " ← boundary (min)" if at_min else (" ← boundary (max)" if at_max else "")
        print(f"    {p} = {val:.4f}  [grid: {min(grid[p]):.4f}–{max(grid[p]):.4f}]{boundary}")
    print("  Score breakdown:")
    score_items = [
        ("S5_FINAL_isco_coverage_share",            "coverage",  True),
        ("S5_FINAL_mean_similarity_retained",       "similarity", True),
        ("S5_FINAL_share_tasks_in_overloaded_isco", "overload",  False),
        ("S5_FINAL_gini_tasks_per_isco",            "gini",      False),
    ]
    for col, label, higher in score_items:
        val = best_row.get(col, float("nan"))
        direction = "↑" if higher else "↓"
        print(f"    {label:12s} = {float(val):.4f}  ({direction} better)")


# ══════════════════════════════════════════════════════════════════════════════
# Main
# ══════════════════════════════════════════════════════════════════════════════

def main() -> None:
    sweep_start = time.time()

    print("=" * 70)
    print("  Adaptive Iterative Sweep — ONET29")
    print(f"  {N_VALUES} values/param per round -> zoom to neighbors + midpoints")
    print(f"  Stops when improvement < {CONVERGENCE_THRESHOLD} or after {MAX_ROUNDS} rounds")
    print("=" * 70)

    # Pre-load both caches so cross-round / cross-path deduplication works.
    _load_checkpoint_cache()
    _load_summary_cache()

    grid            = _initial_grid()
    # Record the coarsest step per param so we can refuse convergence until
    # every param has been zoomed at least once below its initial resolution.
    initial_steps = {
        p: round((max(v) - min(v)) / (len(v) - 1), 6) if len(v) > 1 else 0.0
        for p, v in grid.items()
    }
    best_score   = -np.inf   # raw weighted composite, stable across rounds
    summary         = pd.DataFrame()

    for rnum in range(1, MAX_ROUNDS + 1):
        phase_label = f"r{rnum}"
        tag_prefix  = phase_label

        n_raw = sum(1 for _ in itertools.product(*grid.values()))
        print(f"\n{'─'*70}")
        print(f"  Round {rnum}  (tag prefix: {tag_prefix})")
        for k, v in grid.items():
            step = round(v[1] - v[0], 5) if len(v) > 1 else 0.0
            print(f"    {k}: {v}  (step ~{step})")
        print(f"  Full grid: {n_raw} combos before feasibility filter")

        configs = _build_configs(phase_label, grid)
        print(f"  Feasible configs: {len(configs)}")

        rows    = _run_phase(f"Round {rnum}", configs)
        summary = _merge_into_summary(rows)
        print(f"\n  Summary CSV now has {len(summary)} total variants.")

        mask = summary["dataset_name"].str.startswith(tag_prefix, na=False)
        sub  = summary[mask]
        if sub.empty:
            print("  No scored results — stopping.")
            break

        scores       = sub.apply(_sweep_score, axis=1)
        best_row     = sub.loc[scores.idxmax()]
        best_vals    = {p: float(best_row[p]) for p in PARAM_BOUNDS if p in best_row.index}

        _round_summary(sub, best_row, grid)

        round_best   = float(scores.max())
        improvement  = round_best - best_score

        print(f"\n  Round {rnum} best score: {round_best:.6f}  "
              f"(improvement from previous best: {improvement:+.6f})")

        best_score = round_best

        if rnum == MAX_ROUNDS:
            print(f"  Reached MAX_ROUNDS={MAX_ROUNDS}. Stopping.")
            break

        # Check if best falls on the interior of every parameter's grid.
        # A boundary hit means the optimum may lie beyond the current grid —
        # do NOT converge in that case even if improvement is small.
        boundary_params = [
            p for p, vals in grid.items()
            if p in best_vals and (
                abs(best_vals[p] - min(vals)) < 1e-9 or
                abs(best_vals[p] - max(vals)) < 1e-9
            )
        ]
        # Params whose current step is still at the initial (coarsest) resolution.
        def _step(vals):
            return round((max(vals) - min(vals)) / (len(vals) - 1), 6) if len(vals) > 1 else 0.0
        unrefined = [p for p, vals in grid.items() if _step(vals) >= initial_steps[p] - 1e-9]

        if boundary_params:
            print(f"  Best is at grid boundary for: {boundary_params} — continuing.")
        elif unrefined:
            print(f"  Params not yet refined to finer grid: {unrefined} — continuing.")
        elif rnum > 1 and 0 <= improvement < CONVERGENCE_THRESHOLD:
            print(f"  Converged (improvement {improvement:.6f} < {CONVERGENCE_THRESHOLD}). "
                  f"Stopping after round {rnum}.")
            break

        grid = _zoom_grid(best_vals, grid)

    # ── Final report ──────────────────────────────────────────────────────────
    total_time = time.time() - sweep_start
    print(f"\n{'='*70}")
    print(f"  SWEEP COMPLETE  —  total time: {_fmt_time(total_time)}")
    print(f"{'='*70}")

    if summary.empty or "selection_score" not in summary.columns:
        print("  No results available.")
        return

    best = summary.nlargest(1, "selection_score").iloc[0]
    print(f"\n  Best config overall: {best['dataset_name']}")
    print(f"  Score {best['selection_score']:.6f}")
    for p in ["w_soc_title", "w_dwa", "w_isco", "w_isco_task", "w_occ"]:
        if p in best.index:
            print(f"    {p} = {best[p]:.4f}")

    cols  = ["dataset_name", "selection_rank", "selection_score",
             "w_soc_title", "w_dwa", "w_isco", "w_isco_task", "w_occ",
             "S5_FINAL_isco_coverage_share",
             "S5_FINAL_mean_similarity_retained",
             "S5_FINAL_share_tasks_in_overloaded_isco"]
    avail = [c for c in cols if c in summary.columns]
    print(f"\n  Top 10 overall:")
    print(summary.head(10)[avail].to_string(index=False))


if __name__ == "__main__":
    main()
