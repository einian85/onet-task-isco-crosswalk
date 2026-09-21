# Types of chain-crosswalk disagreement — descriptive notes

Based on reading a random sample of 40 disagreements (`chain_disagreements_random_sample.csv`, seed 7,
drawn from the full 6,010-case set at the production config `w_soc_title=0.375`). This is descriptive
prose from one read-through, not a validated or quantified categorization — see discussion in this
project's memory about why a rigorous count-by-category claim would need proper human annotation, not
this. Treat this as a first draft of language for the paper's discussion of the chain-disagreement
rate, to be refined, not a finished result.

Six recurring patterns showed up, in no particular order of frequency:

**1. Generic task text that spans many occupations.** A number of O*NET task statements are close to
boilerplate and appear, in near-identical wording, across dozens of unrelated SOC occupations —
"maintain records," "review blueprints, building codes, or specifications," "repair parts or
equipment," "keep abreast of developments in the field." The task text alone often genuinely doesn't
carry occupation-distinguishing content. E.g. a Plumber's "review blueprints or specifications" task
(task 23475) matches Civil Engineering Technicians rather than a plumbing trade code — both plausibly
review blueprints; the task text doesn't say which.

**2. Genuine task-level heterogeneity, correctly captured.** Cases where a SOC occupation's task list
includes duties that are legitimately outside its "typical" profile, and the task-level match reflects
that correctly while the occupation-level chain crosswalk can't. A Crane Operator's task "inspect
bundle packaging for conformance... and batch packaging tickets" (task 10777) reads as clerical
inspection work, not crane operation, and matches Production Clerks. A restaurant Cook's task
"coordinate and supervise work of kitchen staff" (task 2180) reads as supervisory/management work and
matches Restaurant Managers. A Chief Executive's task "direct human resources activities... selection
of directors" (task 8832) matches HR Managers — plausible, since a CEO's tasks span many functional
domains. This is the category the paper's "chain hides information" argument is actually about.

**3. Skill-level mismatches.** The predicted occupation sits at a different skill/seniority tier than
the task implies — usually predicting a support/elementary role for professional or managerial content,
occasionally the reverse. A Pediatric Surgeon's task "manage surgery services... determination of
procedures" (task 22771) matches Medical Assistants, a support role, not a physician-tier code. A
Writer's task about crafting customer-facing advertising copy (task 22672) matches generic Clerical
Support Workers. "Odd Job Persons" (an elementary/unskilled catch-all) came up twice independently in
this sample of 40 for what are clearly skilled-trade repair tasks (a Mechanical Door Repairer, task
8393; a Home Appliance Repairer, task 13811) — worth checking whether this ISCO code is acting as an
over-broad attractor for generic "fix things" task text. One case ran the other direction: an
Electrical/Electronics *Drafter's* task "design electrical systems" (task 21954) matched Electrical
Engineers rather than the (correct, lower-tier) Draughtspersons code.

**4. Domain confusion from lexical/semantic false friends.** A word or phrase ambiguous across trades
pulls the match toward an unrelated field. A Prepress Technician's task about selecting "plates"
according to "press run lengths" (task 10425) matched Blacksmiths/Forging Press Workers — "press" means
something different in printing than in metalworking. A Retail Loss Prevention Specialist's task about
"security-related incidents" (task 17567) matched IT/database security professionals, not retail
security. A civilian transport Dispatcher's task "oversee all communications within... territories"
(task 2729) matched a military officer code. A Veterinary Assistant's task "collect laboratory
specimens, such as blood, urine, or feces" (task 4315) matched a *human* Medical and Pathology
Laboratory Technician — the task text for collecting animal vs. human specimens is nearly identical,
and nothing in the bare task text signals which species.

**5. Chain crosswalk coverage/granularity gaps.** Cases where the pipeline's answer looks plausible or
even clearly reasonable, but the institutional SOC→ISCO crosswalk's accepted-ISCO list for that SOC
code looks narrow or oddly assembled. A Web Administrator's task "evaluate or recommend server hardware
or software" (task 14757) matched Systems Administrators — sensible — but the chain's 25-code
acceptable list for this SOC, while broad, doesn't include it. A Genetic Counselor's task about
analyzing genetic risk (task 17500) matched Specialist Medical Practitioners, but chain's list for this
SOC has no medical-practitioner code at all. A Digital Forensics Analyst's task about preserving
forensic evidence (task 21799) matched Police Inspectors and Detectives — a reasonable reading of
"forensic evidence" — but chain's list is entirely IT-occupation codes, missing the investigative side
of this hybrid occupation entirely.

**6. Near-misses within the right occupational family.** The prediction lands in the correct broad
skill tier and occupational family but picks an adjacent specific code rather than chain's preferred
one — a granularity mismatch more than an error. A Small Engine Mechanic's task matched a different but
closely related mechanic code (7233 vs. chain's 7412). A Chemistry Teacher's task about advising
students matched the generic "Teaching Professionals NEC" code rather than the specific postsecondary
code chain wants — still clearly in the teaching family.

## Caveats

- This is one read-through of 40 cases by one (non-independent) reader — see this project's memory on
  why this shouldn't be reported as a validated, quantified breakdown without proper human annotation.
- The categories are not mutually exclusive — several cases plausibly belong to more than one (e.g. the
  door-repairer cases are both a skill-level mismatch *and* arguably generic-task-text driven).
- No attempt was made to estimate the relative frequency of each category from this sample; 40 cases
  out of 6,010 is not enough to support a percentage claim, and doing so would invite exactly the kind
  of false precision this project has been trying to avoid elsewhere.
