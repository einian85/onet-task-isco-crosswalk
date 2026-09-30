"""
update_configs.py
Writes the sweep-selected weights into every configs/config_onet*.yaml.

The selected configuration is the argmax of `selection_score` in
results/summary/sweep_results_metrics_only.csv, i.e. the paper's Appendix A objective
(3*coverage + 2*mean_sim - 2*overload - 2*gini)/9 computed on the final pipeline stage
(S2_TASK_FILTER) for every candidate of the systematic sweep
(sweep/run_systematic_sweep_onet29.py). Selection is deliberately independent of chain/human
validation: those are reported as an out-of-sample check on what the unsupervised objective
selects, so using them to choose would make that check circular (see CONFIG_SELECTION_LOG.md).

Run after the sweep and before run_all_versions.py:
    python update_configs.py
"""
import re
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
SWEEP_SUMMARY_PATH = BASE / "results" / "summary" / "sweep_results_metrics_only.csv"
PARAMS = ["w_soc_title", "w_dwa", "w_isco", "w_isco_task", "w_occ"]


def select_winner() -> tuple[str, dict[str, float]]:
    if not SWEEP_SUMMARY_PATH.exists():
        raise FileNotFoundError(
            f"{SWEEP_SUMMARY_PATH} not found. Run sweep/run_systematic_sweep_onet29.py first."
        )
    df = pd.read_csv(SWEEP_SUMMARY_PATH, low_memory=False)
    df = df[df["selection_score"].notna()]
    best = df.sort_values(["selection_score", "run_id"], ascending=[False, True]).iloc[0]
    return str(best["dataset_name"]), {p: float(best[p]) for p in PARAMS}


def main() -> None:
    label, weights = select_winner()
    print(f"Selected candidate: {label}")
    print(
        f"  w_soc_title={weights['w_soc_title']}, w_dwa={weights['w_dwa']}, "
        f"w_isco={weights['w_isco']}, w_isco_task={weights['w_isco_task']}, w_occ={weights['w_occ']}"
    )

    # Ablation configs deliberately zero out one baseline parameter to isolate its
    # contribution (see PARAM_LABELS in report_publication.py / Appendix G). Blindly
    # overwriting every w_* with the baseline value — as a naive regex replace-all does —
    # silently destroys the ablation (e.g. abl_no_dwa.yaml would end up with the same
    # w_dwa as production). Excluding the ablated parameter's own regex fixes this.
    ABLATION_EXCLUSIONS = {
        "config_onet292_abl_no_dwa.yaml": {"w_dwa"},
        "config_onet292_abl_no_esco.yaml": {"w_isco"},
        "config_onet292_abl_no_soc.yaml": {"w_soc_title"},
        "config_onet292_abl_task_only.yaml": {"w_soc_title", "w_dwa"},
    }

    all_replacements = {
        "w_soc_title": (r"w_soc_title:\s+[\d.]+", f"w_soc_title: {weights['w_soc_title']}"),
        "w_dwa": (r"w_dwa:\s+[\d.]+", f"w_dwa: {weights['w_dwa']}"),
        "w_isco": (r"w_isco:\s+[\d.]+", f"w_isco: {weights['w_isco']}"),
        "w_isco_task": (r"w_isco_task:\s+[\d.]+", f"w_isco_task: {weights['w_isco_task']}"),
        "w_occ": (r"w_occ:\s+[\d.]+", f"w_occ: {weights['w_occ']}"),
    }

    configs = sorted(BASE.glob("configs/config_onet*.yaml"))
    updated = []
    skipped = []
    for cfg_path in configs:
        exclude = ABLATION_EXCLUSIONS.get(cfg_path.name, set())
        replacements = {p: r for name, (p, r) in all_replacements.items() if name not in exclude}
        text = cfg_path.read_text(encoding="utf-8")
        new_text = text
        for pattern, replacement in replacements.items():
            new_text = re.sub(pattern, replacement, new_text)
        if new_text != text:
            cfg_path.write_text(new_text, encoding="utf-8")
            updated.append(cfg_path.name)
        else:
            skipped.append(cfg_path.name)

    print(f"Updated: {len(updated)} files")
    print(f"Unchanged: {len(skipped)} files")
    if skipped:
        print("Skipped:", skipped[:5])


if __name__ == "__main__":
    main()
