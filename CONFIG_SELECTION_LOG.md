# Config selection log

Dated record of what changed in the config-selection process and why, so this investigation
doesn't have to be re-derived from scratch in a future session. See `REVISION_TASKS_SJI.md` Phase A
for the task list this closes out.

## 2026-09-21

**What was wrong:** `update_configs.py` hardcoded `jf_d030_s675_i80_t60_o60` as "the joint sweep
marginal optimum," but it was not the best of the 4 phase-6 candidates on the paper's own sweep-score
formula, nor on chain/human validation.

**What was found while investigating, beyond the original bug report:**

1. Added `validation/score_candidates.py` — a durable, reusable script that recomputes the paper's
   Appendix A formula `(3*cov + 2*sim - 2*overload - 2*gini)/9` directly from materialized candidate
   output files. It reproduces the manually-computed table in the original bug report exactly.

2. **Deeper bug found:** `sweep.py::_add_composite_score` computed `selection_score` using a
   different, undocumented, min-max-normalized formula over 9 metrics (weights 3/2/2/2/1/2/2/1/1,
   including retrieval-stage confidence metrics never mentioned in the paper) — not the paper's
   stated formula. `report_publication.py::build_sweep_tables()` and `export_latex.py::_sweep_top()`
   used this wrong `selection_score` to generate the paper's own "Table: top configurations by sweep
   score," and additionally displayed `S3_COVERAGE` (an intermediate pipeline stage) metrics as if
   they were final (`S5_FINAL`) — this is the source of the paper's "coverage 100%" claim in Appendix
   A vs. the real final coverage of ~92%. **Fixed:** `_add_composite_score` now computes the paper's
   raw formula directly; `build_sweep_tables`/`_sweep_top` now read `S5_FINAL_*` columns.
   `results/summary/sweep_results_metrics_only.csv` (the real, complete 16,000-candidate systematic
   sweep — round sizes 1250/3000/2375/3125/3125/3125 match the paper exactly) had its
   `selection_score`/`selection_rank` columns recomputed in place with the corrected formula.

3. **Replaying the real systematic sweep with the corrected formula**, round by round (matching
   `sweep/run_systematic_sweep_onet29.py`'s own per-round logic, which was already correct — only the
   script's final summary print used the wrong metric), converges smoothly
   (0.3866→0.3889→0.3898→0.3906→0.3907→0.3907) to
   **w_soc_title=0.375, w_dwa=0.2656, w_isco=0.375, w_isco_task=0.7344, w_occ=0.1562**.

4. **Git history confirms this is not a coincidence:** commit `1d3ac47` ("Correct config weights,"
   2026-06-23, same day as `d1bc502`) replaced exactly these values, across all 63 config files
   simultaneously, with the values used ever since (0.675/0.030/0.80/0.60/0.60). No reasoning is
   recorded in the commit message. A prior Claude session's memory (`project_paper_revision.md`,
   now marked superseded) shows the change was made in the belief that "config_onet292.yaml was
   never updated after the sweep" — i.e. a belief that 0.675/etc. *was* the sweep's real answer.
   That belief was wrong.

5. **Decisive test:** materialized the true round-6-optimum config as candidate
   `sw_s375_d266_i38_t73_o16` and ran it through the same chain + human validation as the `jf_*`
   shortlist. Result: it has the *highest* unsupervised sweep_score of any candidate tested
   (0.38477 vs. 0.354 for the `jf_*` candidates) but **catastrophically worse ground-truth
   validation** — chain-exact 68.0% vs. 81.6-82.0%, human-exact 36.1% vs. 54.6%. The unsupervised
   composite score, even correctly computed, is not a reliable enough proxy for real crosswalk
   quality on its own; it rewards spreading task assignments across more ISCO groups regardless of
   whether they're the *correct* groups.

**Decision:** keep `jf_d050_s675_i75_t60_o60`
(`w_dwa=0.050, w_soc_title=0.675, w_isco=0.75, w_isco_task=0.60, w_occ=0.60`) as the production
config — this matches the original bug report's recommendation, now confirmed by a much stronger
argument: it's not just the best of 4 nearby candidates by sweep-score, it's validated against
ground truth to be far better than the config the "correct" formula would mechanically pick.
`jf_d050` and `jf_d030_s675_i75_t60_o60` are statistically tied on chain-exact (82.0/82.0) and
human-exact (54.6/54.6); `jf_d050` wins the tie on sweep_score (0.35411 vs 0.35342) and mean
similarity (0.701 vs 0.700).

**What changed in code:**
- `validation/score_candidates.py` — new, durable sweep-score recomputation.
- `sweep.py::_add_composite_score` — now computes the paper's actual formula; old normalized
  9-metric version and its helper `_normalized_series` removed.
- `report_publication.py::build_sweep_tables()`, `export_latex.py::_sweep_top()` — read `S5_FINAL_*`
  instead of `S3_COVERAGE_*`.
- `results/summary/sweep_results_metrics_only.csv` — `selection_score`/`selection_rank` recomputed
  in place (no pipeline rerun; same underlying per-candidate metrics, corrected formula only).
- `validation/compare_onet29_candidates.py` — added candidate `sw_s375_d266_i38_t73_o16` (the true
  sweep optimum) to the shortlist, kept permanently for Phase C3 (reviewer #5 sensitivity analysis)
  since it's now a directly relevant data point: it shows sweep-score and validation can disagree
  sharply.
- `update_configs.py` — rewritten to select the config with the best validated (chain-exact, then
  human-exact, then sweep_score as tiebreak) performance from
  `validation/results/onet29_candidate_comparison.csv`, instead of a hardcoded label. Also fixed a
  latent bug where it blindly overwrote every `w_*` parameter including the deliberately-ablated one
  in `config_onet292_abl_*.yaml` files, silently turning each ablation into a no-op copy of
  production. Ablation configs' deliberately-zeroed parameters were restored
  (`abl_no_dwa`: w_dwa=0.0, `abl_no_esco`: w_isco=1.0, `abl_no_soc`: w_soc_title=0.0,
  `abl_task_only`: both zeroed) and excluded from future baseline overwrites.
- All 69 `configs/config_onet*.yaml` files (including `_abl_*`, `_bge`, `_gte`) updated to
  `jf_d050`'s weights via the corrected `update_configs.py`.

**Not yet done (Phase B, blocked on nothing further from Phase A):** re-run `run_all_versions.py`,
`run_ablation.py`, `run_embedding_comparison.py`, and regenerate all publication tables/figures under
`results/publication/` — every one of them currently reflects the old (wrong) config. See Phase B in
`REVISION_TASKS_SJI.md`.
