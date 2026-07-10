# Fact Audit Table — "Mapping O*NET Tasks to ISCO Occupations using Text Similarity"

All stated facts from the main paper and supplementary material (Online Appendix).
Facts are listed in document order. Numbers are not reproduced; only the nature of each claim is described.

---

## Main Paper

| # | Fact | Location | Verification source |My Note|
|---|------|----------|---------------------|-------|
| 1 | O*NET is organized under the U.S. Standard Occupational Classification (SOC) | Abstract; Introduction | O*NET documentation / `onetcenter.org` |ok|
| 2 | International labour statistics use ISCO, not SOC | Abstract; Introduction | ILO ISCO-08 documentation |ok|
| 3 | Existing SOC–ISCO concordances operate at the occupation level | Abstract; Introduction | The four institutional crosswalks cited (ESCO–SOC18, BLS–SOC10, ESCO–O*NET) |ok|
| 4 | O*NET task range across SOC 2018 releases: 18,796–19,281 tasks (O*NET 29.2 specifically: 18,796) | Abstract; Conclusion | `output/ONET292_task_to_ISCO_crosswalk.csv` (row count); range from all SOC 2018 outputs |Abstract now gives a range for all SOC 2018 releases. ONET29.2 = 18,796. ok|
| 5 | ISCO-08 groups covered: 401–402 for SOC 2018 releases; 403–404 for SOC 2010 releases; 401–404 overall (of 436) | Abstract; Conclusion | `output/ONET292_task_to_ISCO_crosswalk.csv` (distinct ISCO codes); range across all releases |Abstract gives 401–402 (SOC 2018). Conclusion: 401–404 across all 50 SOC2010+SOC2018 releases. ok|
| 6 | Exact four-digit validation agreement rate: 81.5–81.7% for SOC 2018 releases (O*NET 29.2 lenient A4 = 81.7%) | Abstract; Section 4 | App. C, Table C1 (A4 – Lenient union row for each SOC 2018 release) |ok|
| 7 | Major-group validation agreement rate: 94.0–94.2% for SOC 2018 releases (O*NET 29.2 lenient A4 = 94.2%) | Abstract; Section 4 | App. C, Table C1 |ok|
| 8 | O*NET task data widely used to measure technology exposure, skill demand, and occupational change | Introduction | Autor et al. 2003; Acemoglu & Autor 2011; Frey & Osborne 2017 |ok|
| 9 | Recent AI-exposure datasets are published at the O*NET task level | Introduction | Eloundou et al. 2024 (GPTs paper) |ok|
| 10 | AI-exposure indices exist for both SOC 2010 and SOC 2018 versions of O*NET | Introduction | Eloundou et al. 2024 |ok|
| 11 | Existing occupation-level crosswalks remove within-occupation task variation | Introduction | Structural argument; confirmed by inspecting cited concordances |ok|
| 11a | Two of the four institutional crosswalks were constructed using text similarity (O*NET–ESCO and Matysiak et al.), but all four match occupation titles rather than individual tasks | Introduction (added 2026-06-26, M3) | Crosswalk documentation (onetcenter2022esco_to_soc18, matysiak2024esco_onet_mhv) |ok|
| 12 | O*NET 29.2 described as "the most recent SOC 2018 release at the time of parameter selection" | Section 2 | O*NET version history at `onetcenter.org` |FIXED 2026-06-26: added qualifier "at the time of parameter selection" to resolve the ambiguity (O*NET 30.3 is now the true latest). ok|
| 13 | O*NET 29.2 task count: 18,796 task statements | Section 2 | `output/ONET292_task_to_ISCO_crosswalk.csv` (distinct task IDs) |ok|
| 14 | O*NET 25.0 is the final release under SOC 2010 | Section 2 | O*NET version history |ok|
| 15 | O*NET 25.0 task count: 19,735 | Section 2 (via Conclusion range 18,783–19,735) | `output/ONET250_task_to_ISCO_crosswalk.csv` — confirmed 19,735 unique task_ids |ok — consistent with Conclusion upper bound for SOC 2010 range|
| 16 | Crosswalk files provided for all 63 O*NET releases from v4.0 to v30.3 | Section 2; App. C | `output/` directory (all ONET*_task_to_ISCO_crosswalk.csv files) |ok|
| 17 | Total releases covered: 63 (all generations, v4.0–v30.3); 50 for SOC 2010+SOC 2018 era (v15.1–v30.3) | Section 2; Abstract | `output/` directory file count |Abstract says "50 O*NET releases from v15.1 to v30.3" (SOC2010+2018 only); Section 2 and App. C say "63 releases from v4.0 to v30.3" (all generations). Both numbers are correct for their respective scopes. ok|
| 18 | Official ISCO-08 task descriptions available for 435 of the 436 unit groups | Section 2 | ILO ISCO-08 official task descriptions (ISCO-08 database) |Section 2 says "435 of the 436 unit groups" — this refers to target-side ISCO task description availability (still correct). Figure 1 data flow box previously said "435/436" (wrong — that was pipeline output) and was corrected to "401/436" on 2026-06-26. ok|
| 19 | ISCO-08 unit group 1113 (Traditional Chiefs and Heads of Village) has no clear U.S. counterpart and therefore no ISCO-08 task descriptions | Section 2; Conclusion | ISCO-08 documentation; absence in O*NET occupations |Section 2 confirms this is the ONE group without official ISCO-08 task descriptions. ok|
| 20 | ESCO includes approximately 3,000 occupation concepts linked to ISCO-08 | Section 2 | ESCO dataset (`european_commission_esco_2019`) |Figure 1 shows exactly 3,039. Text says "approximately 3,000". ok|
| 21 | ESCO adds skill and competence information complementing official ISCO-08 descriptions | Section 2 | ESCO database |ok|
| 22 | Four institutional SOC–ISCO-08 concordances used for validation only | Section 2.2 | O*NET–ESCO (O*NET Center, 2022), ESCO–SOC2018 (ESCO Secretariat, 2022), BLS SOC2010–ISCO-08 (BLS, 2015), ESCO–O*NET (Matysiak et al., 2024) |Names confirmed in Section 2.2. SOC2018: O*NET–ESCO crosswalk and ESCO–SOC 2018 crosswalk. SOC2010: BLS SOC2010–ISCO-08 and ESCO–O*NET crosswalk. ok|
| 23 | Sentence encoder model used (`all-mpnet-base-v2`) | Section 3 | Reimers & Gurevych 2019; Hugging Face model card |ok|
| 24 | Embedding vectors dimension: 768 (e ∈ ℝ^768) | Section 3 | `all-mpnet-base-v2` model documentation |Confirmed in Section 3.2. ok|
| 25 | Task representations are unit-normalised real-valued vectors (‖e‖₂ = 1) | Section 3 | `pipeline.py` |ok|
| 26 | Task query combines task text, DWA labels, and SOC occupation title via convex weighting (Eq. 1) | Section 3, Eq. 1 | `pipeline.py` |ok|
| 27 | ISCO-08 occupation representation combines ISCO task descriptions and ISCO title (Eq. 2) | Section 3, Eq. 2 | `pipeline.py` |ok|
| 28 | ESCO occupation representation combines ESCO occupation descriptions and ESCO skill texts (Eq. 3) | Section 3, Eq. 3 | `pipeline.py` |ok|
| 29 | Multiple ESCO occupations mapping to same ISCO unit group have their embeddings averaged | Section 3 | `pipeline.py` |ok|
| 30 | Final occupation representation combines ISCO and ESCO components (Eq. 4) | Section 3, Eq. 4 | `pipeline.py` |ok|
| 31 | Each task assigned to the single ISCO-08 group with highest cosine similarity | Section 3 | `pipeline.py` |ok|
| 32 | Minimum similarity threshold (0.45) and margin (0.03) used to assess confidence; all tasks still receive an assignment | Section 3; Section 5 | `pipeline.py`; `configs/config_onet292.yaml` |ok|
| 32a | Computational complexity: embedding ~19,000 tasks takes ~30 min on standard CPU (~2 GB peak memory); embeddings cached by text hash so subsequent releases complete in minutes; FAISS retrieval over 436 targets adds negligible overhead | Section 3 (added 2026-06-26, R5) | Runtime observation during pipeline runs; `pipeline.py` caching logic |ok|
| 33 | Validation uses institutional occupation-level SOC–ISCO crosswalks as external benchmark | Section 4 | Methodology description |ok|
| 34 | Exact four-digit agreement rate for O*NET 29.2 (lenient benchmark A4): 81.7% | Section 4 | App. C, Table C1 (A4 row for ONET29.2) |ok|
| 35 | Major-group agreement rate for O*NET 29.2 (lenient A4): 94.2% | Section 4 | App. C, Table C1 |ok|
| 36 | Number of tasks shared between O*NET 29.2 and O*NET 25.0: 16,049 | Section 4 | Crosswalk output files (task ID overlap) |ok|
| 37 | Cross-version assignment agreement rate between O*NET 29.2 and O*NET 25.0: 97.7% | Section 4 | Crosswalk output files |ok|
| 38 | Agreement rates robust to choice of reference crosswalk; detailed tables in Online Appendix C | Section 4 | App. C, Tables C1–C2 |Paper previously said "Appendix B" (wrong — B is the framework, not the tables). Corrected to "Appendix C" on 2026-06-26. ok|
| 38b | SOC 2010 validation (all 27 releases, O*NET 15.1–25.0, lenient union B3): 63.2% exact, 82.8% major | Section 4 | App. C, Table C1 (B3 rows) |New fact explicitly stated in Section 4. ok|
| 38c | Cross-references to Online Appendices in Section 4 and Section 5 are correct: A = parameter selection, C = validation tables, F = embedding models, G = ablation | Section 4; Section 5 | paper_full.tex |Previously corrected from wrong "Appendix D/B" references (2026-06-26). App G reference added 2026-06-26 (R3). ok|
| 38d | 95% Wilson CIs for all reported agreement rates are within ±0.6 percentage points (n≈18,800 tasks) | Section 4 (added 2026-06-26, R2) | `compute_cis.py` output |ok|
| 38e | App F: three sentence encoders compared (all-mpnet-base-v2, BAAI/bge-large-en-v1.5, thenlper/gte-large) with same production weights; exact agreement 81.7%–84.7% (3.0 pp range); major-group 94.2%–96.0% (1.8 pp) | Section 4 (added 2026-06-26, R1) | `validation/results/embedding_model_comparison.csv` |ok|
| 38f | Key validation limitation: benchmark is indirect — confirms occupation-level consistency with institutional concordances but cannot evaluate within-occupation task-level precision; no task-level ground truth exists | Section 4 (added 2026-06-26, R7) | Methodological statement |ok|
| 39 | Main parameter values: w_dwa=0.030, w_soc=0.675, w_isco=0.80, w_isco,task=0.60, w_occ=0.60 | Section 5 | `pipeline.py`; `configs/config_onet292.yaml` |CONFIRMED CORRECT. Matches production YAML exactly. ok|
| 40 | Similarity threshold=0.45 and margin=0.03 | Section 5 | `pipeline.py`; `configs/config_onet292.yaml` |ok|
| 41 | Low task-concentration share in the selected configuration: 2.9% | Section 5 | App. A sweep output; App. E, Table E3 |ok|
| 42 | Two overloaded groups each draw over 75% of tasks from a single SOC major group (ISCO 2310, ISCO 1345) | Section 5 | App. E, Table E3 (`table_overload_examples.tex`) |ok|
| 43 | DWA weight is near zero (w_dwa=0.030); ablation study confirms that removing DWA entirely has NO measurable effect on validation agreement; large DWA weights reduce performance | Section 5 (corrected 2026-06-26 — previous version incorrectly stated "improves performance over excluding DWA entirely") | `validation/results/ablation_comparison.csv`; App. A sweep (w_dwa=0 and w_dwa=0.030 both score 0.832) |ok|
| 44 | Large DWA weights reduce performance | Section 5 | App. A sweep results (Figure A2) |ok|
| 44a | Ablation: removing SOC title drops exact agreement by 38 pp (81.7%→43.6%); removing ESCO drops 2.2 pp; DWA has no measurable effect at w_dwa=0.030 | Section 5; App. G (added 2026-06-26, R3) | `validation/results/ablation_comparison.csv` |ok|
| 45 | High SOC occupation title weight (w_soc=0.675) produces more stable assignments | Section 5 | App. A sweep results (Figures A1–A2) |ok|
| 46 | Combining ISCO-08 task descriptions with ESCO text improves retrieval over either source alone | Section 5 | App. A sweep results (Figure A1) |ok|
| 47 | The crosswalk covers 401–402 ISCO-08 four-digit unit groups (SOC 2018); 403–404 for SOC 2010 | Conclusion | `output/ONET292_task_to_ISCO_crosswalk.csv`; range across releases |Verification source previously listed ONET110 — corrected to ONET292. ok|
| 47a | Variation in group count across releases reflects minor additions and removals of SOC occupations between O*NET versions | Conclusion (added 2026-06-26, M2) | O*NET version history |ok|
| 47b | Guidance on crosswalk preference: prefer task-level when analysis depends on within-occupation variation (e.g., comparing AI exposure within occupation, task-weighted indices); occupation-level concordance suffices when all tasks in a SOC get the same value | Conclusion (added 2026-06-26, M4) | Methodological statement |ok|
| 48 | Limitation: ISCO groups without a functional U.S. counterpart cannot be matched | Conclusion | Structural argument; ISCO-08 documentation |ok|
| 49 | ISCO 1113 is the most notable structurally unmatched group (no U.S. counterpart) | Conclusion | ISCO-08 documentation |Distinct from the UNASSIGNED output group (ISCO 7516, see fact #111). This is about structural incompatibility. ok|
| 50 | Dataset and replication materials available at Zenodo DOI (https://doi.org/10.5281/zenodo.20359118) | Conclusion; Data Availability | Zenodo repository |ok|
| 50b | DWA labels: cross-occupation vocabulary of 2,082 granular activity descriptors | Section 2 | O*NET `Tasks to DWAs.xlsx` — confirmed 2,082 unique DWA Title values |ok|

---

## Online Appendix (Supplementary Material)

> **Note on supp PDF**: The `supplementary_material.tex` source has been corrected (2026-06-25). Recompile the PDF from `results/publication/` before submission.

### Appendix A — Parameter Selection

| # | Fact | Location | Verification source | My Note |
|---|------|----------|---------------------|---------|
| 51 | Parameter sweep conducted on O*NET 29.2 (most recent SOC 2018 release at time of selection) | App. A | `pipeline.py` sweep logs |ok|
| 52 | Five blend weights swept: w_soc, w_dwa, w_isco, w_isco-task, w_occ, each in [0, 1] | App. A | `pipeline.py` / `config.py` |ok|
| 53 | Component embeddings are pre-computed and shared across all candidate configurations | App. A | `pipeline.py` (embedding cache) |ok|
| 54 | Query-weight feasibility constraint (w_soc + w_dwa ≤ 0.90) | App. A | `pipeline.py` |ok|
| 55 | Round 1 initial grid: 5^5 = 3,125 candidates reduced to 1,250 feasible after query-weight constraint | App. A | Sweep log / pipeline output |ok|
| 56 | Total candidate configurations across six rounds: 16,000 | App. A | Sweep log |ok|
| 57 | Per-round configuration counts: 1,250 (R1), 3,000 (R2), 2,375 (R3), 3,125 (R4), 3,125 (R5), 3,125 (R6) | App. A | Sweep log |ok — confirmed in supp text|
| 58 | Adaptive zoom trust-region strategy for re-gridding between rounds | App. A | `pipeline.py` (sweep algorithm) |ok|
| 59 | Sweep terminates when improvement is below threshold AND all parameters interior AND all steps below Round 1 size | App. A | `pipeline.py` (termination condition) |ok|
| 60 | Improvement threshold corresponds approximately to 0.15 pp change in coverage | App. A | Mathematical approximation; sweep log |ok|
| 61 | Sweep score formula: (3·cov + 2·sim − 2·overload − 2·gini) / 9 | App. A, Eq. | `pipeline.py` |ok|
| 62 | Overload threshold definition: T = max(200, Q_0.95) | App. A | `pipeline.py` |ok|
| 63 | Sweep score range bounds: −4/9 ≈ −0.44 (min) to 5/9 ≈ 0.56 (max) | App. A | Mathematical derivation from formula |ok|
| 64 | Overload share range across all 16,000 candidate configurations: 1.2% to 31.0% (std 2.9 pp) | App. A | Sweep log |ok|
| 65 | Selected configuration selection score=0.832 (from Table A2); sweep metrics: coverage 100%, mean similarity 0.718, Gini 0.446, overloaded share 2.9% | App. A | `results/publication/tables/table_sweep_top_configs.tex` |Supp tex updated 2026-06-25. ok|
| 66 | Selected configuration parameter values: w_soc=0.675, w_dwa=0.030, w_isco=0.80, w_isco_task=0.60, w_occ=0.60 | App. A | `configs/config_onet292.yaml`; `results/publication/tables/table_candidate_selection_parameters.tex` |Supp tex corrected 2026-06-25. ok|
| 67 | Two overloaded groups (ISCO 2310, ISCO 1345) each draw over 75% of tasks from a single SOC major group | App. A | App. E, Table E3 |ok|
| 68 | Top candidate configurations all achieve near-complete ISCO-08 coverage (99.8–100%) | App. A | `table_sweep_top_configs.tex` |ok — Table A2 shows 1.000 S3 coverage for all top configs|
| 69 | Effective query-side contributions: SOC title 67.5%, raw task text 31.5%, DWA labels 1.0% | App. A | Mathematical derivation from w_soc=0.675, w_dwa=0.030 |Supp tex corrected 2026-06-25. ok|
| 70 | ISCO task items are the single largest contributor to the target embedding (48%) | App. A | Mathematical derivation from w_isco=0.80, w_isco_task=0.60, w_occ=0.60 |Supp tex corrected: ISCO task items 48%, ISCO info text 32%, ESCO occ 12%, ESCO skills 8%. ok|
| 71 | Nominal target-side weight breakdown: ISCO task items 48%, ISCO info text 32%, ESCO occ text 12%, ESCO skills 8% | App. A | Mathematical derivation from production config weights |Supp tex corrected 2026-06-25. ok|
| 72 | DWA labels provide small positive contribution at w_dwa=0.030 (~1.0% of query vector); SOC title (67.5%) and raw task (31.5%) dominate | App. A | Sweep results (Figure A2); production config |Supp tex corrected 2026-06-25. ok|
| 73 | Combining ISCO-08 descriptions with ESCO occupation text improves retrieval over either source alone | App. A | Sweep results (Figure A1) |ok|
| 74 | High weight on ISCO-08 text (w_isco=0.80) reflects discriminative power of official task descriptions | App. A | Production config; sweep results |Supp tex corrected 2026-06-25. ok|
| 75 | Sweep is fully deterministic (embeddings cached and reloaded identically) | App. A | `pipeline.py` (caching logic) |ok|
| 76 | No ties in best configuration arose across the six rounds | App. A | Sweep log |ok|
| 77 | High-score configurations cluster in a narrow region of parameter space | App. A | `table_sweep_top_configs.tex` |ok — Table A2 shows scores within 0.832–0.827|
| 77a | The value 3 in the 3-2-2-2 scheme is the smallest integer strictly greater than 2 (the equal weight of all other criteria); any value in (2,∞) achieves the same strict priority ordering | App. A (added 2026-06-26, R8) | Mathematical argument |ok|

### Appendix B — Validation Framework

| # | Fact | Location | Verification source | My Note |
|---|------|----------|---------------------|---------|
| 78 | Task-level assignments aggregated to SOC occupation level by taking the modal ISCO group | App. B | `pipeline.py` / `report_publication.py` |ok|
| 79 | Strict benchmark definition: pipeline assignment must fall in every available crosswalk's set | App. B | Methodology; `report_publication.py` |ok|
| 80 | Lenient benchmark definition: pipeline assignment must fall in at least one crosswalk's set | App. B | Methodology; `report_publication.py` |ok|
| 81 | Main text reports lenient benchmark results | App. B | Matches Section 4 of main paper |ok|
| 82 | Institutional crosswalks are used only for validation, not for constructing the mapping | App. B | Methodology description |ok|

### Appendix C — Full Validation Results

| # | Fact | Location | Verification source | My Note |
|---|------|----------|---------------------|---------|
| 83 | Pipeline applied to all O*NET releases from v4.0 (2001) through v30.3 (2025), 63 releases total | App. C | `output/` directory; sweep/pipeline logs |ok|
| 84 | Five SOC taxonomy generations covered: pre-2006, SOC 2006, SOC 2009, SOC 2010, SOC 2018 | App. C | O*NET version documentation |ok|
| 85 | ESCO–ONET-SOC chain crosswalks cover SOC 2018 (O*NET 25.1 onward) | App. C | Institutional crosswalk documentation |ok|
| 86 | ESCO–O*NET and BLS–ISCO crosswalks cover SOC 2010 | App. C | Institutional crosswalk documentation |ok|
| 87 | Occupation-level comparison uses modal ISCO per SOC occupation | App. C | `report_publication.py` |ok|
| 88 | Pair precision is structurally low because pipeline assigns one ISCO per SOC while institutional crosswalks list several | App. C | Structural argument; `table_occupation_level_comparison.tex` |ok|
| 89 | In-set rate is the appropriate primary accuracy measure | App. C | Methodology reasoning |ok|
| 90 | Pair precision, pair recall, and F1 reported for completeness (Table C2) | App. C | `table_occupation_level_comparison.tex` |ok|
| 91 | SOC 2010 and SOC 2018 pair precision / in-set rates not directly comparable (different instrument cardinalities) | App. C | Methodology caveat |ok|
| 92 | Mismatch example: Proofreaders and Copy Markers (SOC 43-9081) — pipeline assigns ISCO 4413, ESCO-SOC18 crosswalk assigns ISCO 2642 | App. C | `table_mismatch_examples.tex` (Table C4) |ok|
| 93 | Mismatch example: Survey Researchers (SOC 19-3022) — pipeline assigns ISCO 4227, BLS crosswalk assigns ISCO 2120 | App. C | `table_mismatch_examples.tex` (Table C4) |ok|
| 94 | In-set rate is a lower bound on true quality when the reference crosswalk contains errors | App. C | Methodology argument |ok|
| 94a | 95% Wilson CIs for O*NET 29.2 A4 headline rows (Table C1 footnote, added 2026-06-26, R2): exact [81.1%, 82.2%], sub-major [89.7%, 90.5%], major [93.9%, 94.5%] | App. C | `compute_cis.py` output |ok|

### Appendix D — Author Annotation

| # | Fact | Location | Verification source | My Note |
|---|------|----------|---------------------|---------|
| 95 | Number of O*NET 29.2 tasks annotated by the author: 108 | App. D | Annotation workbook |ok|
| 96 | Tasks drawn from 36 SOC occupations covering all nine ISCO major groups | App. D | Annotation workbook |ok|
| 97 | Occupations selected by combined U.S. and Nordic employment within each major group | App. D | Annotation workbook; employment data |ok|
| 98 | Tasks selected by O*NET importance score (top three per occupation) | App. D | Annotation workbook; O*NET task importance ratings |ok|
| 99 | Author assigned ISCO-08 four-digit unit groups independently of pipeline predictions | App. D | Methodology |ok|
| 100 | Selected configuration's exact four-digit agreement with author annotations: 54.6% | App. D | Annotation workbook vs. pipeline output |Supp tex corrected 2026-06-25 (was 36.1%). ok|
| 101 | Selected configuration's two-digit sub-major agreement with author annotations: 71.3% | App. D | Annotation workbook vs. pipeline output |Supp tex corrected 2026-06-25 (was 57.4%). ok|
| 102 | Selected configuration's one-digit major-group agreement with author annotations: 81.5% | App. D | Annotation workbook vs. pipeline output |Supp tex corrected 2026-06-25 (was 72.2%). ok|
| 103 | Selected configuration's mean cosine similarity on annotated tasks: 0.699 | App. D | Pipeline output for annotated task subset |Supp tex corrected 2026-06-25 (was 0.739). ok|
| 104 | Selected configuration's exact agreement on the automated chain-crosswalk benchmark (lenient union A4) for the annotated task subset: 85.2% (sub-major 97.2%, major-group 99.1%) | App. D | `check_facts.py` via `shared.evaluate_match` + `shared.summarise_match` on production config output |CORRECTED 2026-06-26: was 68.0% (from old wrong config). Production config verified at 85.2%. Supp tex updated.|
| 105 | Author annotation performed by the author as the sole annotator; absence of inter-rater reliability evidence means results are indicative rather than definitive | App. D (strengthened 2026-06-26, R4) | Methodology caveat |ok|
| 105a | 95% Wilson CIs for annotation (n=108): exact [45.2%, 63.7%], sub-major [62.2%, 79.0%], major [73.1%, 87.7%] | App. D (added 2026-06-26, R2) | `compute_cis.py` output |ok|

### Appendix E — Coverage and Example Matches

| # | Fact | Location | Verification source | My Note |
|---|------|----------|---------------------|---------|
| 106 | O*NET releases prior to v20.1 distributed data in text format only | App. E | O*NET version archives |ok|
| 107 | Excel format available from O*NET v20.1 onward | App. E | O*NET version archives |ok|
| 108 | Occupation titles merged from `Occupation Data.txt` for pre-v20.1 releases | App. E | `pipeline.py` (data loading logic) |ok|
| 109 | All parameters and thresholds are identical across O*NET versions (only input data differs) | App. E | `pipeline.py` / `config.py` |ok|
| 110 | For O*NET 29.2, mapping assigns tasks to 401 of the 436 ISCO-08 unit groups | App. E | `output/ONET292_task_to_ISCO_crosswalk.csv` (distinct ISCO codes) |Supp tex corrected 2026-06-25 (was "435 of 436"). Consistent with abstract (401–402) and Table E2 (cov=0.920). ok|
| 111 | Groups without task assignments typically lack a U.S. counterpart; most notable: ISCO 1113 (no ISCO-08 task descriptions available) | App. E | `output/ONET292_task_to_ISCO_crosswalk.csv`; ISCO-08 documentation |Supp tex corrected 2026-06-25. Old claim "only ISCO 7516 unmatched" was from the old pipeline (with coverage backfill). Current pipeline: ~35 groups receive no tasks. ISCO 7516 language removed; ISCO 1113 highlighted as per main paper Conclusion. ok|
| 112 | Differences in task counts across ISCO groups reflect SOC–ISCO taxonomy asymmetry, not assignment errors | App. E | Structural argument; Table E3 |ok|
| 113 | High-concentration ISCO groups draw over 75% of tasks from a single SOC major group | App. E | `table_overload_examples.tex` (Table E3) |ok|
| 114 | Coverage and mean similarity evolution across pipeline stages (S1–S2) documented for all releases | App. E | Figure E1 (`figure_stage_progression.pgf`) |Note: dead code removal reduced stages to S1_RETRIEVE and S2_TASK_FILTER; S3_COVERAGE stage was eliminated. Figure E1 shows S1–S3 but S2 = S3 in current pipeline. ok|
| 115 | Retrieval stage (S1) achieves broad coverage at cost of many candidates per task; filtering stage (S2) tightens precision | App. E | Figure E1; `table_baseline_stage_metrics.tex` |ok|

### Appendix F — Embedding Model Robustness (added 2026-06-26, R1)

| # | Fact | Location | Verification source | My Note |
|---|------|----------|---------------------|---------|
| 116 | Three sentence encoders compared: all-mpnet-base-v2 (production), BAAI/bge-large-en-v1.5, thenlper/gte-large | App. F | `run_embedding_comparison.py`; `configs/config_onet292_bge.yaml`, `config_onet292_gte.yaml` |ok|
| 117 | All three encoders use identical production weights (w_soc=0.675, w_dwa=0.030, w_isco=0.80, w_isco_task=0.60, w_occ=0.60) | App. F | Config files |ok|
| 118 | Exact agreement (A4): all-mpnet-base-v2 = 81.7%, bge-large = 83.7%, gte-large = 84.7% | App. F | `validation/results/embedding_model_comparison.csv` |ok|
| 119 | Range across encoders: 3.0 pp (exact), 1.8 pp (major-group 94.2%–96.0%) | App. F | `validation/results/embedding_model_comparison.csv` |ok|
| 120 | Alternative encoders score marginally higher despite being evaluated with MPNet-optimised weights | App. F | `validation/results/embedding_model_comparison.csv` |ok|
| 121 | Task-level disagreement between any two models ~25% (task counts to ~25% of tasks assigned to a different ISCO group) | App. F | `compare_crosswalk_agreement.py` output |ok — MPNet vs BGE 73.4% exact task-level agreement, MPNet vs GTE 75.0%, BGE vs GTE 87.6%|
| 122 | Production model (all-mpnet-base-v2) retained because weights were optimised for it and switching would change ~25% of task assignments | App. F | Methodological decision |ok|

### Appendix G — Ablation Study (added 2026-06-26, R3)

| # | Fact | Location | Verification source | My Note |
|---|------|----------|---------------------|---------|
| 123 | Four ablation variants tested: no SOC title (w_soc=0), no DWA (w_dwa=0), no ESCO (w_isco=1.0), task text only (w_soc=0, w_dwa=0) | App. G | `run_ablation.py`; configs in `configs/config_onet292_abl_*.yaml` |ok|
| 124 | Removing SOC title: exact agreement drops 38.1 pp (81.7% → 43.6%) | App. G | `validation/results/ablation_comparison.csv` |ok|
| 125 | Removing ESCO (ISCO-08 only target): exact agreement drops 2.2 pp | App. G | `validation/results/ablation_comparison.csv` |ok|
| 126 | Removing DWA labels: no measurable effect on exact agreement at production w_dwa=0.030 (confirmed 0.0 pp change) | App. G | `validation/results/ablation_comparison.csv` |ok — also confirmed by sweep: w_dwa=0 and w_dwa=0.030 both score 0.832|
| 127 | Task-text-only variant (no SOC title, no DWA): same as no SOC title result (~43.6%) — DWA adds nothing when SOC title also absent | App. G | `validation/results/ablation_comparison.csv` |ok|

---

*Updated 2026-06-26. Verification paths point to files in the `output/` directory of the `onet-task-isco-crosswalk` repo or to external data sources.*

**Edits completed 2026-06-25 (supplementary):** `supplementary_material.tex` corrected: Appendix A production config values and derived percentages; Appendix D annotation statistics (facts #100–104); Appendix E coverage claim (fact #110). Supplementary PDF recompiled.

**Edits completed 2026-06-26 (main paper, round 1):** `data_flow_fig.tex` Figure 1 node corrected "435/436" → "401/436" (fact #18). `paper_full.tex` corrected three cross-reference errors (fact #38c). `paper_full.pdf` and `fig_standalone.pdf` recompiled.

**Edits completed 2026-06-26 (main paper, round 2 — reviewer checklist R1–R8, M1–M4):**
- Figure 1 fully redesigned to show algorithmic flow: SBERT encoder → weighted formulas for q and e_i → cosine similarity → top-1 + threshold → output (R6)
- Computational complexity parenthetical added to Section 3 Assignment rule (R5, fact #32a)
- Wilson CI sentence added to Section 4 (R2, fact #38d)
- Indirect evaluation limitation sentence added to Section 4 (R7, fact #38f)
- App F embedding model comparison reference added to Section 4 (R1, fact #38e)
- DWA claim corrected in Section 5: was "improves over excluding DWA" → now "no measurable effect" (fact #43 corrected)
- Ablation reference added to Section 5 with specific numbers (R3, fact #44a)
- Variation in group count explained in Conclusion (M2, fact #47a)
- Related work sentence added to Introduction (M3, fact #11a)
- Crosswalk preference guidance added to Conclusion (M4, fact #47b)
- App A: "3 is smallest integer > 2" sentence added (R8, fact #77a)
- App C: Wilson CI footnote added to Table C1 (R2, fact #94a)
- App D: Single-annotator caveat strengthened; CIs added (R4/R2, facts #105, #105a)
- App F added: embedding model comparison table and prose (R1, facts #116–#122)
- App G added: ablation study table and prose (R3, facts #123–#127)

**Corrections made 2026-06-26 (second pass):**
- Fact #12: Added qualifier "at the time of parameter selection" to O*NET 29.2 reference in Section 2.
- Fact #15: Verified ONET 25.0 task count = 19,735 (ok).
- Fact #50b: Verified DWA count = 2,082 (ok).
- Fact #104 CORRECTED: was 68.0% (old wrong config). Production config verified at **85.2%** exact (sub-major 97.2%, major 99.1%) on annotation subset. Supplementary Appendix D updated.
- Fact #114: S2=S3 figure discrepancy is cosmetic (overlapping lines); accepted as ok.
