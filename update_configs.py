"""
update_configs.py
Updates all config_onet*.yaml files with the weight parameters of whichever candidate in
validation/compare_onet29_candidates.py's CANDIDATES list has the highest unsupervised sweep_score
in validation/results/candidate_sweep_scores.csv (the paper's Appendix A formula, computed by
validation/score_candidates.py).

Parameter selection is deliberately independent of chain/human validation. Chain and human agreement
are reported as an out-of-sample check on whatever the unsupervised objective selects — using them to
also pick among candidates would make that check circular (the reported agreement rate would just
reflect which candidate was chosen to look best on it, not a genuine independent result). An earlier
version of this script picked the candidate with the best chain/human validation instead; that was
reverted on 2026-09-21 — see CONFIG_SELECTION_LOG.md.

A 2026-09-21 investigation found the true systematic-sweep optimum (highest sweep_score) validates
far worse against chain/human ground truth than the previously-used jf_* shortlist (chain-exact 68.0%
vs 81.6-82.0%, human-exact 36.1% vs 54.6%). That is not, on its own, a reason to reject the
unsupervised objective's answer — see CONFIG_SELECTION_LOG.md for why, and
validation/audit_chain_disagreements.py for the follow-up: checking whether the disagreements with
the (occupation-level) chain crosswalk are actually task-level information the chain crosswalk
cannot see, rather than errors.

Before running this: make sure validation/score_candidates.py has been run recently enough that
candidate_sweep_scores.csv reflects every candidate you want considered.
"""
import re
import sys
from pathlib import Path

import pandas as pd

BASE = Path(__file__).parent
sys.path.insert(0, str(BASE))
sys.path.insert(0, str(BASE / "validation"))

from compare_onet29_candidates import CANDIDATES  # noqa: E402

SWEEP_SCORE_PATH = BASE / "validation" / "results" / "candidate_sweep_scores.csv"


def select_winner() -> tuple[str, dict[str, float]]:
    if not SWEEP_SCORE_PATH.exists():
        raise FileNotFoundError(
            f"{SWEEP_SCORE_PATH} not found. Run validation/score_candidates.py first."
        )
    scores = pd.read_csv(SWEEP_SCORE_PATH)
    weights_by_label = {str(c["label"]): c["overrides"] for c in CANDIDATES}
    scores = scores[scores["candidate_label"].isin(weights_by_label)]
    if scores.empty:
        raise ValueError("No rows in candidate_sweep_scores.csv match CANDIDATES labels.")

    best = scores.sort_values("sweep_score", ascending=False).iloc[0]
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
