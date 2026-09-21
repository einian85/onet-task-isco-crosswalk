"""
update_configs.py
Updates all config_onet*.yaml files with the weight parameters of whichever candidate in
validation/compare_onet29_candidates.py's CANDIDATES list currently has the best validated
performance (highest chain-exact agreement, tie-broken by human-exact agreement) in
validation/results/onet29_candidate_comparison.csv.

This intentionally does NOT use the raw unsupervised sweep_score to pick the winner: a 2026-09-21
investigation (see CONFIG_SELECTION_LOG.md) found that a config with a much higher sweep_score
(the true systematic-sweep round-6 optimum) validates far *worse* against ground truth (chain-exact
68.0%, human-exact 36.1%) than the jf_* shortlist (81.6-82.0% / 54.6%). The unsupervised composite
score is not a reliable enough proxy on its own — ground-truth validation must decide.

Before running this: make sure validation/compare_onet29_candidates.py has been run recently enough
that onet29_candidate_comparison.csv reflects every candidate you want considered.
"""
import re
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "validation"))

from compare_onet29_candidates import CANDIDATES  # noqa: E402

COMPARISON_PATH = BASE / "validation" / "results" / "onet29_candidate_comparison.csv"
SWEEP_SCORE_PATH = BASE / "validation" / "results" / "candidate_sweep_scores.csv"


def select_winner() -> tuple[str, dict[str, float]]:
    if not COMPARISON_PATH.exists():
        raise FileNotFoundError(
            f"{COMPARISON_PATH} not found. Run validation/compare_onet29_candidates.py first."
        )
    comparison = pd.read_csv(COMPARISON_PATH)
    weights_by_label = {str(c["label"]): c["overrides"] for c in CANDIDATES}
    comparison = comparison[comparison["candidate_label"].isin(weights_by_label)]
    if comparison.empty:
        raise ValueError("No rows in onet29_candidate_comparison.csv match CANDIDATES labels.")

    # Ground truth (chain-exact, then human-exact) decides first. Only when both are tied does
    # the unsupervised sweep_score break the tie — see CONFIG_SELECTION_LOG.md for why sweep_score
    # is deliberately NOT the primary criterion (it picked a config that validates far worse).
    if SWEEP_SCORE_PATH.exists():
        sweep_scores = pd.read_csv(SWEEP_SCORE_PATH)[["candidate_label", "sweep_score"]]
        comparison = comparison.merge(sweep_scores, on="candidate_label", how="left")
        comparison["sweep_score"] = comparison["sweep_score"].fillna(-1.0)
    else:
        comparison["sweep_score"] = -1.0

    best = comparison.sort_values(
        ["chain_pct_exact", "human_pct_exact", "sweep_score"],
        ascending=[False, False, False],
    ).iloc[0]
    label = str(best["candidate_label"])
    return label, weights_by_label[label]


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
