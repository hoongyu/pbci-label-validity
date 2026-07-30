# Reference — Acceptance gates

Every gate has: an ID, a criterion stated as a checkable proposition, an
artifact that must exist, and a failure playbook.

**A gate is passed only when a timestamped log in `outputs/logs/` records the
observed value against the criterion.** "It looked right" is not a pass.

Gates in **bold** are hard stops. Do not proceed past a failed hard stop under
any framing, including "just to see".

---

## Phase P0 — Foundation

### G0.1 — Environment reproducible
**Artifact:** `env/requirements.lock`, `config.yaml`

- [ ] Python environment pinned and lockfile committed
- [ ] `mne`, `mne-bids`, `pyriemann`, `scikit-learn`, `scipy`, `statsmodels`, `pandas`, `numpy` installed with versions recorded
- [ ] `config.yaml` exists with: seeds, data paths, band definitions, channel subset, epoch length
- [ ] A fresh environment build from the lockfile succeeds

**KPI:** clean rebuild succeeds in one attempt.

---

### G0.2 — Data acquired and inventoried
**Artifact:** `outputs/tables/inventory.csv`, `outputs/logs/G0.2_*.md`

- [ ] ~50 GB free verified before download
- [ ] 29 participant directories present
- [ ] 3 sessions per participant, or documented exceptions
- [ ] N-Back and MATB task files present for every participant-session, or documented exceptions
- [ ] Notebook file parsed; task order and interruptions extracted
- [ ] Trigger list parsed
- [ ] Assertion passes: N-Back notebook numbering is descending (3=Two-Back, 4=One-Back, 5=Zero-Back)
- [ ] Assertion passes: TP9 identified as ECG, not EEG
- [ ] Channel presence verified per subject for all 10 reference channels; participants 1–9 checked explicitly for the Cz issue

**KPI:** missing-file rate < 5% of expected participant-session-task cells, and
every missing cell individually logged.

**Failure playbook:** missing files are a data problem, not a pipeline problem.
Document, decide exclusions, and carry the decision into the preregistration.
Do not silently impute.

---

### G0.3 — Preprocessing runs end to end
**Artifact:** `data/derived/P0/sub-01_pipeline_smoke.nc` (or equivalent), log

- [ ] Loads one participant-session from `.set`/`.fdt` via MNE
- [ ] ML-variant order confirmed: **epoch first, then clean each epoch, automatic epoch rejection disabled** (see `dataset.md` §7.6)
- [ ] Resample 250 Hz, band-pass applied
- [ ] Bad-channel rejection + interpolation at 2 SD
- [ ] Full-rank average reference
- [ ] ICA + ICLabel, eye/muscle/heart rejected at >90% confidence
- [ ] Covariance matrices produced on the 10-channel subset
- [ ] Runs without error and produces plausible epoch counts

**KPI:** channels interpolated and components rejected fall in the neighbourhood
of published averages (~0.34 channels/task, ~7 components/participant-session).
Order-of-magnitude agreement is enough here; exact match is not expected.

---

### **G0.4 — Baseline reproduction (HARD STOP)**
**Artifact:** `outputs/tables/G0.4_baseline.csv`, `outputs/logs/G0.4_*.md`

Within-subject 5-fold CV, 3-class, Riemannian MDM, 10-channel covariance.

**Primary criterion — both must hold:**

| Task | Published | Accept if observed mean is within |
|---|---|---|
| MATB | 69.40% | **66.40% – 72.40%** (±3.0 pp) |
| N-Back | 64.97% | **61.97% – 67.97%** (±3.0 pp) |

**Secondary directional criteria — all three must hold:**
- [ ] Alpha band accuracy > theta band accuracy
- [ ] MATB accuracy > N-Back accuracy
- [ ] Session 2 accuracy highest of the three sessions

**KPI:** primary criterion met for both tasks, all three directional criteria
met.

**Failure playbook.** Work this list in order; each step is cheap relative to
the next.

1. **Preprocessing order.** By far the most likely cause. The paper describes
   two variants; the ML pipeline epochs *before* cleaning and disables automatic
   epoch rejection. Using the descriptive variant will not reproduce.
2. **Channel subset.** Exactly F3, Fz, F4, FCz, C3, C4, CPz, P3, Pz, P4. Verify
   these resolve to the same electrodes in your montage, especially for
   participants 1–9.
3. **Reference handling.** Original reference is Fpz. Full-rank average
   re-reference before ICA. TP9 excluded as ECG.
4. **Epoch length and resampling.** 5 s non-overlapping, 250 Hz.
5. **Band definitions.** theta [4–8], alpha [8–12] — note alpha is 8–12 in the
   ML pipeline but 8–13 in the descriptive analysis. Use 8–12.
6. **CV structure.** 5-fold, within subject, stratified by class.
7. **Class balance and trial counts.** Verify ≥60 trials per class per subject.
8. If still failing after all seven: **stop and consult the mentor.** Do not
   proceed to P1. Consider contacting the dataset authors — they are responsive
   and this is a legitimate reproducibility question.

**Do not widen the tolerance to pass.** If ±3 pp cannot be met, the pipeline
differs from the published one in a way that will contaminate every downstream
comparison.

---

## Phase P1 — Study 1: Divergence

### G1.1 — Cell-level table complete
**Artifact:** `data/derived/P1/cells.csv`

- [ ] One row per subject × task × session × difficulty
- [ ] Expected 522 rows (29 × 2 × 3 × 3); shortfall documented row by row
- [ ] Columns: nominal difficulty, RSME, behavioural performance index, band power by ROI, KSS, quality covariates
- [ ] MATB behavioural index uses **only TRACK and SYSMON** (`dataset.md` §4)

**KPI:** RSME missingness < 10%. Above that, the H1 analyses are compromised —
document and re-plan.

---

### **G1.2 — Manipulation checks and anomaly confirmation (HARD STOP)**
**Artifact:** `outputs/tables/G1.2_manipulation_checks.csv`

**Part A — replication.** All must hold:
- [ ] N-Back RSME × difficulty significant, F within ±20% of F(2,104) = 55.56
- [ ] MATB RSME × difficulty significant, F within ±20% of F(2,104) = 92.73
- [ ] N-Back error rate × condition significant
- [ ] MATB TRACK and SYSMON × difficulty both significant

**Part B — the anomaly.** All must hold:
- [ ] N-Back: **no** significant difficulty effect on theta power
- [ ] N-Back: **no** significant difficulty or session effect on alpha power
- [ ] MATB: significant difficulty effect on frontal and posterior theta
- [ ] MATB: posterior alpha difficulty effect present and **opposite in sign** to the conventional literature

**KPI:** Part A fully replicated and Part B fully confirmed.

**Failure playbook.**
- *Part A fails:* the behavioural/subjective extraction is wrong. These are
  robust effects. Check cell assignment, the descending N-Back numbering, and
  the session mapping.
- *Part B fails — anomaly does not appear:* **this is a major finding in its own
  right and a fork in the project.** It would mean the published EEG validation
  does not replicate. Stop, log carefully, and re-plan with the mentor before
  proceeding. The paper's framing changes completely; it may become a
  reproducibility paper. Do not quietly proceed as if the anomaly held.

---

### G1.3 — Divergence metrics computed
**Artifact:** `data/derived/P1/divergence.csv`

- [ ] D_subj computed per subject × task via Kendall's τ-b over 9 cells
- [ ] D_beh computed identically on the behavioural index, sign-oriented
- [ ] Per-subject bootstrap CIs on both
- [ ] D_slope and D_resid computed as preregistered robustness alternatives
- [ ] Definitions match `analysis.md` §1 exactly

**KPI:** metric code has unit tests covering a perfect-agreement subject
(τ-b = 1, D = 0), a perfectly inverted subject (D = 2), and a tied/flat subject.

---

### G1.4 — Variance decomposition
**Artifact:** `outputs/tables/G1.4_variance_components.csv`

- [ ] Mixed model fitted per task per `analysis.md` §2
- [ ] Variance components extracted with bootstrap 95% CIs (≥2000 subject-level draws)
- [ ] Subject ICC reported

**KPI — the project's load-bearing quantity:** the **subject×difficulty slope
variance component** and its 95% CI.

**Decision rule:**
- CI **excludes zero** → H1b supported. Proceed to G-LOCK.
- CI **includes zero** → **H2 and H2b have no basis. Do not preregister them.**

**Documented pivot if the CI includes zero.** Do not force the original
hypotheses. The project becomes a Study-1-plus-Study-3 paper:
*"Task difficulty labels are adequate at the group level but EEG workload
markers do not track them: the N-Back anomaly and its consequences for
cross-task transfer."* This is still publishable and still original, and it uses
the same pipeline. Re-plan with the mentor, log the pivot, then proceed to a
revised G-LOCK.

---

## 🔒 G-LOCK — Preregistration lock (HARD STOP)

**Artifact:** `prereg/protocol.md`, OSF registration with timestamp recorded in
`outputs/logs/G-LOCK.md`

Must be fixed before any P2 primary analysis runs:
- [ ] Hypotheses and directional predictions
- [ ] Divergence metric definitions (primary, secondary, robustness)
- [ ] Relabelling schemes
- [ ] LOSO protocol and reference classifier
- [ ] Robustness classifier named
- [ ] Primary tests, decision rules, and the Holm family
- [ ] Smallest effect size of interest for the H2 equivalence test
- [ ] Exclusion rules, including anything found at G0.2 and G1.1
- [ ] Pooling rule for the Hackathon dataset — decided **before** seeing the COG-BCI H2 result
- [ ] Confound battery
- [ ] Explicit statement that a null H2 is a reportable outcome

**KPI:** OSF timestamp precedes the first commit that runs a P2 primary analysis.
This is verifiable by anyone and will be checked by reviewers.

---

## Phase P2 — Study 2: Relabel & LOSO

### **G2.1 — Leakage audit (HARD STOP)**
**Artifact:** `outputs/logs/G2.1_leakage_audit.md`, permutation distribution plot

Checklist — all must pass, each with the verifying assertion named:
- [ ] ICA fit per subject-session, never across subjects
- [ ] Channel rejection decided per subject-session, no global thresholds
- [ ] All normalisation and Riemannian reference points fit on training subjects only
- [ ] No hyperparameter selected using held-out-subject performance
- [ ] Assertion: no subject ID appears in both train and test in any fold
- [ ] Symmetric control for test-set labels implemented (`analysis.md` §7)

**Permutation control — mandatory:**
- [ ] ≥200 runs with subject-wise permuted labels, seeds from `config.yaml`
- [ ] Labels permuted, **not** epochs
- [ ] **Criterion: 95th percentile of the permuted accuracy distribution ≤ 41.7%**

**KPI:** permutation 95th percentile at or below the chance ceiling, and every
checklist item verified by a named assertion in code — not by inspection.

**Failure playbook.** If permuted labels beat chance, the leak is almost always
one of: a normaliser fit on all data; a Riemannian mean computed across the full
set; epochs from one subject appearing in both splits; or label permutation
applied at epoch level rather than cell level. Fix and rerun the full control.
**Every P2 and P3 number produced before the fix is void and must be deleted,
not adjusted.**

---

### G2.2 — Nominal-label LOSO baseline
**Artifact:** `outputs/tables/G2.2_loso_nominal.csv`

- [ ] Per-subject LOSO accuracy for both tasks × both bands under Scheme A
- [ ] Per-subject distributions plotted, not only means
- [ ] Balanced accuracy reported alongside raw

**KPI:** this table is a standalone contribution — a LOSO baseline for COG-BCI
does not exist in the literature. It must be clean enough to cite on its own.
Expect it to be substantially below the within-subject baseline; that gap is the
cross-subject problem made visible.

---

### G2.3 — Relabelled LOSO
**Artifact:** `outputs/tables/G2.3_loso_relabelled.csv`

- [ ] Scheme B and Scheme C implemented per `analysis.md` §3
- [ ] Class balancing by epoch subsampling, seed recorded, retained counts reported

**KPI:** retained epoch counts reported per cell; no cell silently dropped.

---

### G2.4 — Primary tests H2 and H2b (RUN ONCE)
**Artifact:** `outputs/tables/G2.4_primary.csv`, log recording the run timestamp

- [ ] Preregistration timestamp verified as preceding this run
- [ ] H2: Spearman ρ between D_subj and Scheme-A LOSO accuracy, per task, meta-combined
- [ ] Bootstrap 95% CI reported
- [ ] Equivalence test (TOST) against the preregistered smallest effect size of interest
- [ ] H2b: mixed model interaction term with CI
- [ ] Holm correction applied across the three primary tests
- [ ] D_beh robustness analysis run and sign agreement reported
- [ ] Full confound battery run and tabulated

**KPI:** the analysis executed matches the preregistration exactly, or every
deviation is logged with its date and whether it was decided before or after
seeing the result.

**This runs once.** A disliked result is the result.

---

## Phase P3 — Study 3: Cross-task transfer

### G3.1 / G3.2 — Transfer pipelines
**Artifact:** `outputs/tables/G3_transfer.csv`

- [ ] N-Back → MATB LOSO transfer under Scheme A
- [ ] Same under Scheme B
- [ ] **Reverse direction (MATB → N-Back) also run**, per `analysis.md` §8
- [ ] Class prior mismatch handled; balanced accuracy reported

**KPI:** both directions complete. A labelling effect appearing in only one
direction is much weaker evidence and must be reported as such.

---

### G3.3 — Primary test H3 (RUN ONCE)
**Artifact:** `outputs/tables/G3.3_primary.csv`

- [ ] Wilcoxon signed-rank on 29 paired differences
- [ ] Median difference with bootstrap CI
- [ ] Paired effect size **reported regardless of significance**
- [ ] Holm correction applied within the primary family
- [ ] Sensorimotor confound addressed explicitly using the reverse-direction result

**KPI:** effect size and CI present in the output table whether or not the test
is significant. A non-significant H3 with a tight CI around zero is a clean,
reportable result.

---

## Phase P4 — Manuscript and submission

### **G4.1 — Reproducibility audit (HARD STOP)**
**Artifact:** `outputs/logs/G4.1_repro_audit.md`

- [ ] Fresh clone into an empty directory
- [ ] Environment rebuilt from `env/requirements.lock`
- [ ] `make all` runs to completion without manual intervention
- [ ] Every figure and table in the manuscript regenerates
- [ ] Stochastic outputs match exactly given fixed seeds; any tolerance is documented

**KPI:** zero manual steps between clean clone and full manuscript figure set.

---

### G4.2 — OSF deposit
- [ ] Protocol, code, derived data, deviation log deposited
- [ ] Licence and attribution for COG-BCI (CC-BY 4.0) correct
- [ ] Links live and included in the manuscript

### G4.3 — Senior review
- [ ] Methodological co-author has read the full manuscript
- [ ] Confound-control strategy specifically reviewed
- [ ] Sign-off recorded

**If no senior co-author has been secured by this point, do not submit.** Desk
rejection risk for a solo master's-student submission to a top-tier methods
journal is high, and a desk rejection burns the timestamp advantage. Use the
completed manuscript as the recruitment instrument — it is far stronger than the
P1 results were.

### G4.4 — Submission
- [ ] Venue selected per `PRD.md` §7 based on which study carries the result
- [ ] Preregistration link in the abstract
- [ ] Deviation log attached as a supplement
- [ ] Power limitations stated in Results, not only Discussion
- [ ] RSME unidimensionality limitation stated plainly

---

## Gate status template

Copy into each log file.

```markdown
# Gate <ID> — attempt <n>
Date: YYYY-MM-DD
Criterion: <verbatim from gates.md>
Observed: <value>
Result: PASS | FAIL
Changed since last attempt: <what>
Next action: <specific diagnostic, not "try again">
Artifacts: <paths>
```
