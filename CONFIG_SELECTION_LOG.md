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

**Initial decision (SUPERSEDED same day — see below):** kept `jf_d050_s675_i75_t60_o60` as production,
selecting it by validation performance. This was reverted a few hours later; kept here, struck
through in spirit, for provenance.

---

## 2026-09-21 (revised, same day)

**Why the initial decision was wrong:** picking the production config by which candidate validates
best against chain/human ground truth, then reporting that same validation as "the result," is
circular — it's no longer an independent test, it's the selection criterion. The paper's design
(Appendix A) is explicit that parameter selection happens via the unsupervised sweep_score alone,
precisely so the later validation numbers are a genuine out-of-sample check. Flagged directly by the
user: "the parameter selection was supposed to be independent of validation."

**Additional, more fundamental point (also from the user):** the paper's actual thesis is that
occupation-level chain crosswalks *hide* genuine task-level heterogeneity — a task-based crosswalk
disagreeing with the chain baseline is not automatically wrong. Lower chain-agreement is not, by
itself, evidence against a config; it can equally be evidence the config is doing its job. Judging a
config by how well it reproduces occupation-level chain agreement is in tension with the paper's own
premise.

**Follow-up investigation before finalizing:**
- Built `validation/audit_chain_disagreements.py`: for the sweep-optimal config, of the 18,773 tasks
  covered by the chain crosswalk, 6,010 (32.0%) disagree with it — 4,201 of those at similarity ≥0.70.
  Manual review of a stratified sample (`validation/results/chain_disagreements_sample_for_review.csv`)
  found a **genuinely mixed picture**: some disagreements look like real task-level signal the
  occupation-level chain can't see (e.g. a "Camera Repairer" task about precision metal machining
  correctly reads as Toolmaking work, not photographic-equipment repair); others look like plain
  retrieval errors, particularly skill-level mismatches (a Urologist "directing nursing staff" mapped
  to Health Care Assistant; a Recycling Coordinator "negotiating contracts" mapped to Garbage
  Collector). This is not a clean confirmation either way — see the CSV for the full 6,010 cases and
  keep reviewing.
- Also checked (per user's question) whether reweighting the composite score's coverage/similarity/
  overload/gini terms would favor higher `w_soc_title`. It does not: even removing the Gini term
  entirely only moves the optimum from 0.375 to 0.41; a pure-similarity objective still picks 0.375.
  The real driver is that raw retrieval similarity itself peaks around `w_soc_title≈0.5` and *declines*
  beyond that (0.754 → 0.718 at 0.75) — a property of the retrieval mechanics (the ISCO target side is
  73%-weighted toward task-level descriptions, so a query that becomes mostly occupation-title text
  as `w_soc_title→1` increasingly mismatches what it's being matched against), not an artifact of how
  the four metrics are weighted against each other. Also noteworthy: `w_soc_title=0.675` (the old,
  now-confirmed-spurious production value) was never even a grid point in the sweep — round 1 only
  tested {0, 0.25, 0.5, 0.75}.
- User's judgment on this, explicitly: 0.675 "is just rubbish some AI did," not something to chase
  back toward, and a config that lets occupation title dominate the query representation is not what's
  wanted here — task-level content should drive the match. This aligns with, not against, keeping the
  low-`w_soc_title` sweep optimum.

**Final decision:** `sw_s375_d266_i38_t73_o16`
(`w_soc_title=0.375, w_dwa=0.2656, w_isco=0.375, w_isco_task=0.7344, w_occ=0.1562`) is the production
config — selected by unsupervised sweep_score alone (0.38477, highest of any candidate tested), with
no validation input into the selection. Chain/human validation numbers for this config (chain-exact
68.0%, human-exact 36.1%) should be reported honestly as an out-of-sample check, not treated as a
selection failure — and the disagreement audit above is the start of characterizing what that lower
agreement actually consists of, which is more nuanced than either "it's all noise" or "it's all
signal."

**Follow-up (2026-09-22): considered and rejected raising `w_soc_title` toward 0.50.** Materialized a
scratch candidate at the sweep's best co-tuned point for `w_soc_title=0.50`
(`w_dwa=0.3125, w_isco=0.375, w_isco_task=0.75, w_occ=0.25`; not added to `CANDIDATES`, not
propagated to any config — exploration only, `output/candidates/ONET29_sw_s500_d313_i38_t75_o25_task_to_ISCO_crosswalk.csv`).
Checked whether reweighting the composite score could get there on unsupervised grounds alone: no —
confirmed again that de-emphasizing Gini barely moves the optimum (halving its weight: 0.375→0.391;
removing it entirely: →0.406). Then checked whether the paper's own stated rationale for Gini/overload
("penalises... excessive task concentration... which arise at extreme parameter values") could license
treating 0.34–0.50 as an interchangeable plateau and picking a point within it using case-level
disagreement review as a tie-breaker (of 60 sampled `w_soc=0.375` disagreements, 37% were fixed at
`w_soc=0.50`, 47% were completely unaffected, 17% changed to a different wrong answer).

**Rejected, correctly, by the user:** this is still circular. Judging "fixed" by whether a prediction
now matches chain is chain-informed selection at the case level, not the aggregate level — same
problem, finer grain. Doing this properly would require a genuine train/held-out split of the chain
data (select using judgment on one part, validate against the other, never let the same data do both
jobs) — which is real scope creep for this revision cycle, not a bug fix. **Decision: stay at
`w_soc_title=0.375`, the actual unsupervised sweep optimum, with no case-level or aggregate validation
input into the selection at all.** This is now settled; don't re-open it without proposing the
train/held-out-split redesign explicitly as its own piece of work.

**What changed in code (final state):**
- `validation/score_candidates.py` — durable sweep-score recomputation from real output files.
- `sweep.py::_add_composite_score` — computes the paper's actual raw formula (not the old normalized
  9-metric version, removed along with its `_normalized_series` helper).
- `report_publication.py::build_sweep_tables()`, `export_latex.py::_sweep_top()` — read `S5_FINAL_*`
  instead of `S3_COVERAGE_*`.
- `results/summary/sweep_results_metrics_only.csv` — `selection_score`/`selection_rank` recomputed
  in place with the corrected formula (no pipeline rerun needed).
- `validation/compare_onet29_candidates.py` — added candidate `sw_s375_d266_i38_t73_o16` as the
  selected config; `jf_*`/`fg_*` candidates relabeled "not selected," kept for comparison (useful for
  Phase C3, reviewer #5's objective-function-sensitivity response — this whole episode *is* that
  sensitivity analysis).
- `update_configs.py` — selects strictly by `sweep_score` from `validation/results/candidate_sweep_scores.csv`,
  no validation input. Also fixed a latent bug where it blindly overwrote every `w_*` parameter
  including the deliberately-ablated one in `config_onet292_abl_*.yaml` files, silently turning each
  ablation into a no-op copy of production. Ablation configs' deliberately-zeroed parameters were
  restored (`abl_no_dwa`: w_dwa=0.0, `abl_no_esco`: w_isco=1.0, `abl_no_soc`: w_soc_title=0.0,
  `abl_task_only`: both zeroed) and excluded from future baseline overwrites.
- `validation/audit_chain_disagreements.py` — new; produces the full disagreement set, a stratified
  review sample, and Reviewer #1's within-SOC heterogeneity table (96.6% of SOC occupations' tasks
  span >1 ISCO group, mean 6.52 distinct groups per SOC) in one run.
- All 69 `configs/config_onet*.yaml` files (including `_abl_*`, `_bge`, `_gte`) updated to the final
  sweep-optimal weights via the corrected `update_configs.py`.

**Not yet done (Phase B, blocked on nothing further from Phase A):** re-run `run_all_versions.py`,
`run_ablation.py`, `run_embedding_comparison.py`, and regenerate all publication tables/figures under
`results/publication/` — every one of them currently reflects the old (wrong) config. See Phase B in
`REVISION_TASKS_SJI.md`. The disagreement audit should also continue — 6,010 cases is far more than
was manually reviewed here, and the mix of genuine-signal vs. genuine-error cases isn't yet
characterized well enough to describe in the paper.

---

## 2026-09-30 — second correction: `sw_s375_d266_i38_t73_o16` was itself selected on stale metrics

**What was wrong:** the 2026-09-21 "final decision" above is superseded. It was reached by recomputing
`sweep_score` from `S5_FINAL_*` columns in `results/summary/sweep_results_metrics_only.csv` — but
`pipeline.py`'s `STAGES` tuple has been `("S1_RETRIEVE", "S2_TASK_FILTER")` only since the "Simplify
the pipeline." (`b6ae989`) and "dead code removal cleanup" (`310cda2`) commits, both from well before
this whole investigation. `S2_TASK_FILTER` is the real final stage — `final_output_path` is written
from it directly. `S3_COVERAGE`/`S4_OVERLOAD`/`S5_FINAL` do not exist anywhere in the current pipeline.

Checked what the `S5_FINAL_*` columns in the sweep file actually were: for every one of the 16,000
rows, `S1_RETRIEVE_isco_coverage_share == S3_COVERAGE_... == S4_OVERLOAD_... == S5_FINAL_...`,
bit-identical. These are frozen copies of the S1 retrieval-stage metrics, not independently computed
final-stage metrics — the sweep file predates the pipeline simplification and was never regenerated
after it. `S2_TASK_FILTER_*`, the columns the corrected formula should have used, were sitting in the
same file the whole time, genuinely distinct from S1, unused.

**Consequence:** re-scoring the full sweep on `S2_TASK_FILTER_*` (the real final stage), `sw_s375_d266_i38_t73_o16`
ranks **137th of 16,750**, not 1st. The true argmax under the corrected, pipeline-consistent formula is
a different point in parameter space.

**How this was caught:** not by a script — by a human-requested self-consistency re-read of the
manuscript against its own tables, which surfaced a coverage figure (Table~sweep-top showing 99.8%
uniformly) that didn't match Appendix A's prose (97.0%). Tracing that down to its root cause, rather
than patching the table, found the stage-confusion bug above.

**What was fixed (see the commits on `master` dated 2026-09-30 for the full diff):**
- `sweep.py::_add_composite_score`, `sweep/run_systematic_sweep_onet29.py::_sweep_score` — now read
  `S2_TASK_FILTER_*`, with the stage history documented inline so this doesn't get silently re-broken
  by a future pipeline refactor.
- `report_publication.py` (`STAGE_ORDER`, `build_sweep_tables`), `export_latex.py` (`STAGE_LABELS`,
  every table-generation function reading stage-prefixed columns), `report_occupation.py`,
  `verify_paper_numbers.py`, `validation/shared.py::load_pipeline`,
  `validation/compare_onet29_candidates.py`, `validation/score_candidates.py`'s docstring,
  `validation/reviewer_c3_objective_sensitivity.py`, `validation/validate_chain.py`,
  `validation/audit_chain_disagreements.py`, and five debug scripts under `sweep/` (`_best_config.py`,
  `_check_wisco.py`, `_sweep_stats.py`, `_trace_rounds.py`, `plot_sweep_params.py`) — every
  `S3_COVERAGE`/`S4_OVERLOAD`/`S5_FINAL` reference repointed to `S2_TASK_FILTER`.
- `generate_configs.py` — removed the `enforce_isco_coverage`/`coverage_backfill_strategy` default
  keys; `pipeline.py` never implements them (confirmed by a repo-wide grep finding zero consumers),
  so they were dead config that made it look like a backfill step existed when it didn't.
- Two stale paths: `sweep/run_systematic_sweep_onet29.py`'s `BASE_CONFIG` and
  `verify_paper_numbers.py` both pointed at a repo-root `config_onet292.yaml` that doesn't exist (the
  real file is `configs/config_onet292.yaml`) — would have failed outright on the next fresh run.

**Re-ran the full systematic sweep from scratch** under the corrected scoring (parallelized across 8
worker processes this time — candidates within a round are independent, only round-to-round is
sequential — cutting wall-clock time from an estimated ~33 hours to ~7.5; see `sweep/plot_sweep_params.py`
and the `ProcessPoolExecutor` addition in `run_systematic_sweep_onet29.py`). Converged after 6 rounds,
16,750 candidates total (round sizes 1250/3000/3125/3125/3125/3125 — round 3 differs from the original
16,000-candidate run's 2,375 because the adaptive zoom took a genuinely different path under correct
scoring from round 1 onward, not because of any remaining bug).

**New final decision:** `sw_r6_s234_d203_i43_t96_o02`
(`w_soc_title=0.2344, w_dwa=0.2030, w_isco=0.4296, w_isco_task=0.9610, w_occ=0.0157`) — selection score
0.3887, final-stage coverage 98.9% (431/436). Same independence principle re-confirmed explicitly by
the user when presented with the three options this reopened (keep pure unsupervised selection /
revise the objective function itself / select via validation with a held-out split): **stay pure
unsupervised** — there is no principled a priori rule for revising the objective now, and
validation-informed selection is the exact circularity already rejected on 2026-09-21. Chain-exact
drops further, from 68.0% to 53.7%; human-exact from 33.3% to 24.4%. Five nearby candidates
(C1–C4, B0) again validate substantially better (80.7–82.1% chain-exact, 50.0–53.3% human-exact) and
are again not adopted, for the same circularity reason as before — this is now the second time this
project has independently arrived at "the unsupervised optimum validates worse than nearby
alternatives, and that's not a reason to pick the alternative."

**Downstream regeneration, all committed 2026-09-30:** `update_configs.py` rewritten to select
directly from `results/summary/sweep_results_metrics_only.csv`'s `selection_score` rather than a
hand-maintained shortlist; all 63 `configs/config_onet*.yaml` regenerated; all 63
`output/*_task_to_ISCO_crosswalk.csv` regenerated via `run_all_versions.py --force`; ablation and
embedding-comparison re-run; every `validation/results/*` file regenerated; sweep heatmap figures
regenerated (they hadn't been touched since before the pipeline simplification and still showed the
selected-configuration marker on stale data). The old `sw_s375_d266_i38_t73_o16` candidate was removed
from `validation/compare_onet29_candidates.py`'s `CANDIDATES` entirely rather than kept as a labeled
comparison row — it was never a principled candidate, only an artifact of this bug, and keeping it
around read as more confusing than informative once removed from the paper's own narrative.

**Lesson for next time:** a metrics file that predates a pipeline refactor can carry column names that
look current but aren't. The tell here was two identically-named-seeming things (`S5_FINAL` stage,
"final assignment") that had silently stopped being the same thing. Grepping for a stage name's
existence in the *current* pipeline code, not just in the data file, would have caught this
immediately — worth doing as a standing check before trusting any `results/summary/*.csv` file that
wasn't generated in the current session.
