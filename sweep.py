from __future__ import annotations

import argparse
from dataclasses import replace
from pathlib import Path
from typing import Any

import numpy as np
import pandas as pd

from config import RunConfig, load_yaml_or_json, stable_hash
from pipeline import run_pipeline
from stability import compare_runs_links, compare_runs_topk


def _apply_updates(cfg: RunConfig, updates: dict[str, Any]) -> RunConfig:
    return replace(cfg, **updates)


def generate_oat_configs(baseline_cfg: RunConfig, sweep_spec: dict[str, Any]) -> list[RunConfig]:
    configs = [baseline_cfg]
    for item in sweep_spec.get("parameters", []):
        param = item["parameter"]
        values = item.get("values", [])
        derived = item.get("derived", {})
        for value in values:
            updates = {param: value}
            for key, expr in derived.items():
                updates[key] = expr
            configs.append(_apply_updates(baseline_cfg, updates))
    return configs


def generate_random_configs(baseline_cfg: RunConfig, sweep_spec: dict[str, Any], n: int, seed: int) -> list[RunConfig]:
    import random

    rng = random.Random(seed)
    configs = []
    for _ in range(n):
        updates: dict[str, Any] = {}
        for item in sweep_spec.get("parameters", []):
            param = item["parameter"]
            low, high = item["range"]
            kind = item.get("kind", "float")
            if kind == "int":
                updates[param] = rng.randint(int(low), int(high))
            elif kind == "bool":
                updates[param] = bool(rng.choice([False, True]))
            else:
                updates[param] = round(rng.uniform(float(low), float(high)), 6)
        configs.append(_apply_updates(baseline_cfg, updates))
    return configs


def _flatten_config(cfg: RunConfig) -> dict[str, Any]:
    return cfg.to_dict()


def _load_metrics(run_output: dict[str, Any]) -> pd.DataFrame:
    metrics_path = Path(run_output["metrics_path"]).with_name("metrics.csv")
    return pd.read_csv(metrics_path)


def _add_baseline_deltas(results: pd.DataFrame, baseline_run_id: str) -> pd.DataFrame:
    if results.empty or baseline_run_id not in set(results["run_id"].astype(str)):
        return results
    out = results.copy()
    baseline_row = out.loc[out["run_id"].astype(str) == str(baseline_run_id)].iloc[0]
    excluded = {
        "run_id",
        "dataset_name",
        "checkpoint_prefix",
        "output_dir",
        "final_output_path",
        "onet_tasks_path",
        "onet_tasks_dwa_path",
        "onet_tasks_cat_path",
        "esco_skills_path",
        "esco_occupation_rel_path",
        "esco_occupations_path",
        "coverage_backfill_strategy",
        "embedding_cache_dir",
        "faiss_index_type",
    }
    numeric_cols = [
        col for col in out.columns
        if col not in excluded
        and pd.api.types.is_numeric_dtype(out[col])
        and not pd.api.types.is_bool_dtype(out[col])
    ]
    for col in numeric_cols:
        baseline_value = baseline_row[col]
        if pd.isna(baseline_value):
            continue
        out[f"delta_{col}"] = out[col] - baseline_value
    return out


def _add_composite_score(results: pd.DataFrame) -> pd.DataFrame:
    """Paper's Appendix A sweep score: (3*cov + 2*sim - 2*overload - 2*gini) / 9, raw (not
    min-max normalized), computed only from S5_FINAL (final-assignment stage) metrics.

    This must stay numerically identical to sweep/run_systematic_sweep_onet29.py::_sweep_score
    and validation/score_candidates.py, which independently compute the same formula. A prior
    version of this function used a different, min-max-normalized 9-metric blend that never
    matched the paper's stated formula — see project_config_selection_bug memory / Phase A of
    REVISION_TASKS_SJI.md for how that produced a wrong "selected configuration" in the paper.
    """
    if results.empty:
        return results
    out = results.copy()
    required = [
        "S5_FINAL_isco_coverage_share",
        "S5_FINAL_mean_similarity_retained",
        "S5_FINAL_share_tasks_in_overloaded_isco",
        "S5_FINAL_gini_tasks_per_isco",
    ]
    if not all(col in out.columns for col in required):
        out["selection_score"] = np.nan
        out["selection_rank"] = np.nan
        return out

    cov = pd.to_numeric(out["S5_FINAL_isco_coverage_share"], errors="coerce").fillna(0.0)
    sim = pd.to_numeric(out["S5_FINAL_mean_similarity_retained"], errors="coerce").fillna(0.0)
    overload = pd.to_numeric(out["S5_FINAL_share_tasks_in_overloaded_isco"], errors="coerce").fillna(0.0)
    gini = pd.to_numeric(out["S5_FINAL_gini_tasks_per_isco"], errors="coerce").fillna(0.0)

    out["selection_score"] = (3 * cov + 2 * sim - 2 * overload - 2 * gini) / 9
    out["selection_rank"] = out["selection_score"].rank(method="dense", ascending=False).astype(int)
    return out


def _is_pareto_efficient(values: np.ndarray, maximize: list[bool]) -> np.ndarray:
    n = values.shape[0]
    efficient = np.ones(n, dtype=bool)
    oriented = values.copy().astype(float)
    for idx, keep_high in enumerate(maximize):
        if not keep_high:
            oriented[:, idx] = -oriented[:, idx]
    for i in range(n):
        if not efficient[i]:
            continue
        dominating_rows = np.all(oriented >= oriented[i], axis=1) & np.any(oriented > oriented[i], axis=1)
        dominating_rows[i] = False
        if dominating_rows.any():
            efficient[i] = False
    return efficient


def _add_pareto_flag(results: pd.DataFrame) -> pd.DataFrame:
    if results.empty:
        return results
    out = results.copy()
    objective_spec = [
        ("S5_FINAL_isco_coverage_share", True),
        ("S5_FINAL_mean_similarity_retained", True),
        ("S5_FINAL_share_tasks_in_overloaded_isco", False),
        ("S5_FINAL_gini_tasks_per_isco", False),
        ("S5_best_link_agreement", True),
        ("S5_jaccard_links", True),
    ]
    available = [(col, maximize) for col, maximize in objective_spec if col in out.columns]
    if not available:
        out["pareto_candidate"] = False
        return out

    clean = out.copy()
    for col, maximize in available:
        clean[col] = pd.to_numeric(clean[col], errors="coerce")
        fill_value = -np.inf if maximize else np.inf
        clean[col] = clean[col].fillna(fill_value)
    values = clean[[col for col, _ in available]].to_numpy(dtype=float)
    out["pareto_candidate"] = _is_pareto_efficient(values, [maximize for _, maximize in available])
    return out


def run_sweep(configs: list[RunConfig], baseline_run_id: str | None = None) -> pd.DataFrame:
    seen = set()
    run_outputs: list[dict[str, Any]] = []
    for cfg in configs:
        key = stable_hash(cfg.to_dict())
        if key in seen:
            continue
        seen.add(key)
        run_outputs.append(run_pipeline(cfg))

    if not run_outputs:
        return pd.DataFrame()

    baseline_output = run_outputs[0]
    if baseline_run_id is not None:
        matches = [r for r in run_outputs if r["run_id"] == baseline_run_id]
        if matches:
            baseline_output = matches[0]

    baseline_s1 = baseline_output["s1"]
    baseline_s5 = baseline_output["s5"]

    rows = []
    for run_output in run_outputs:
        metrics_df = _load_metrics(run_output)
        cfg = run_output.get("config")
        if cfg is None:
            cfg_data = load_yaml_or_json(Path(run_output["manifest_path"]).parent / "config.json")
        else:
            cfg_data = cfg.to_dict()
        flat_cfg = cfg_data if isinstance(cfg_data, dict) else _flatten_config(cfg)
        metric_map = {row["stage"]: row for _, row in metrics_df.iterrows()}
        row = {"run_id": run_output["run_id"]}
        row.update(flat_cfg)
        for stage_name, metric_row in metric_map.items():
            for key, value in metric_row.items():
                if key in {"run_id", "stage"}:
                    continue
                row[f"{stage_name}_{key}"] = value
        current_s1 = run_output["s1"]
        current_s5 = run_output["s5"]
        row.update({f"S1_{k}": v for k, v in compare_runs_topk(baseline_s1, current_s1, k=int(flat_cfg["k_retrieve"])).items()})
        row.update({f"S5_{k}": v for k, v in compare_runs_links(baseline_s5, current_s5).items()})
        rows.append(row)

    results = pd.DataFrame(rows)
    results = _add_baseline_deltas(results, baseline_output["run_id"])
    results = _add_composite_score(results)
    results = _add_pareto_flag(results)
    if "selection_score" in results.columns:
        results = results.sort_values(
            ["pareto_candidate", "selection_score", "run_id"],
            ascending=[False, False, True],
        ).reset_index(drop=True)
    summary_path = Path(run_outputs[0]["manifest_path"]).parents[2] / "summary" / "sweep_results.csv"
    summary_path.parent.mkdir(parents=True, exist_ok=True)
    results.to_csv(summary_path, index=False)
    return results


def main(argv: list[str] | None = None) -> None:
    parser = argparse.ArgumentParser(description="Run a parameter sweep.")
    parser.add_argument(
        "mode",
        nargs="?",
        choices=["oat", "random"],
        default="oat",
        help="Sweep mode. Defaults to oat.",
    )
    parser.add_argument(
        "--config",
        default=str(Path(__file__).resolve().with_name("config_onet292.yaml")),
        help="Path to the baseline YAML or JSON config. Defaults to config_onet292.yaml.",
    )
    parser.add_argument(
        "--spec",
        default=None,
        help="Optional path to a sweep spec. Defaults to sweep/sweep_<mode>.yaml.",
    )
    args = parser.parse_args(argv)

    baseline_cfg = RunConfig(**load_yaml_or_json(args.config))
    spec_path = Path(args.spec) if args.spec else Path(__file__).resolve().with_name("sweep") / f"sweep_{args.mode}.yaml"
    sweep_spec = load_yaml_or_json(spec_path)
    if args.mode == "oat":
        configs = generate_oat_configs(baseline_cfg, sweep_spec)
    else:
        configs = generate_random_configs(
            baseline_cfg,
            sweep_spec,
            n=int(sweep_spec.get("n", 10)),
            seed=int(sweep_spec.get("seed", 42)),
        )
    results = run_sweep(configs)
    print(results.head().to_string(index=False))


if __name__ == "__main__":
    main()
