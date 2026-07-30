# Reference — Analysis specification

Read this in full before writing analysis code. Contents:

1. Divergence metrics
2. Variance decomposition (H1b)
3. Relabelling schemes
4. LOSO protocol
5. Leakage rules (mandatory)
6. Primary tests and decision rules
7. Confound battery
8. Cross-task transfer
9. Multiplicity and reporting

---

## 1. Divergence metrics

The central construct. **Definitions are frozen at G-LOCK** — after that, any
change is a deviation requiring a log entry and disclosure in the manuscript.

### D_subj — subjective divergence (PRIMARY)

For each subject *i* and task *t*, compute **Kendall's τ-b** between nominal
difficulty (0/1/2) and RSME across the 9 condition×session cells.

```
D_subj[i,t] = 1 - τ_b(nominal_difficulty, RSME)
```

Range [0, 2]; 0 = perfect rank agreement, 1 = no association, 2 = perfect
inversion.

**Why τ-b and not a slope:** RSME is a 150 mm visual analogue line. People use
analogue scales with wildly different ranges and anchoring. A slope conflates
"the manipulation didn't move them" with "they use a compressed range". A rank
statistic is immune to both. τ-b (not τ-a) because ties are expected.

**Why 9 cells and not 3:** treating session as replicate rather than averaging
over it preserves within-subject noise, which is the thing being measured. Nine
points is thin for a rank statistic — report bootstrap CIs per subject and
propagate that uncertainty into H2 (see §6).

### D_beh — behavioural divergence (SECONDARY)

Identical construction, substituting the per-cell behavioural performance index
(`references/dataset.md` §4) for RSME, with sign oriented so that higher
difficulty predicts worse performance.

D_beh exists because RSME is self-report and carries its own validity problems.
If D_subj and D_beh agree, the divergence claim is much stronger. If they
disagree, that disagreement is itself a finding and must be reported, not
resolved by picking the more convenient one.

### D_comp — composite (EXPLORATORY ONLY)

Mean of z-scored D_subj and D_beh. **Never used for a primary test.** Reported
for descriptive completeness.

### Pre-specified alternatives (robustness, reported in supplement)

- D_slope: within-subject OLS slope of RSME on difficulty, on z-scored RSME
- D_resid: RMS residual from the group-level difficulty→RSME model

If the H2 conclusion flips between D_subj and these alternatives, the result is
fragile and must be reported as such.

---

## 2. Variance decomposition (H1b)

Fit to cell-level RSME, separately per task:

```
RSME ~ 1 + difficulty + (1 + difficulty | subject) + (1 | session)
```

Extract variance components: subject intercept, **subject×difficulty slope**,
session, residual. Bootstrap 95% CIs (subject-level resampling, ≥2000 draws,
seed from `config.yaml`).

**The subject×difficulty slope variance is H1b.** Its CI is the project's
load-bearing quantity — see the pivot at `gates.md` §G1.4.

Report the ICC for subject as a descriptive companion.

---

## 3. Relabelling schemes

Applied per subject, per task, per session.

### Scheme A — Nominal (baseline)
0-back / 1-back / 2-back → low / medium / high.
MATB Easy / Medium / Difficult → low / medium / high.
This is what the field does.

### Scheme B — Experienced (test)
Within subject × task, rank the 9 cells by RSME and split into tertiles → low /
medium / high. All epochs within a cell inherit that cell's label.

Within-subject ranking is deliberate: it removes between-person scale-use
differences, which is the whole point.

**Consequence to anticipate:** for subjects with low divergence, Schemes A and B
produce nearly identical labels. The overall A-vs-B contrast will therefore be
diluted. This is expected and is exactly why **H2b (the divergence ×
scheme interaction) is the sharper test than a marginal A-vs-B comparison.**
State this in the preregistration so it does not read as post-hoc.

### Scheme C — Behavioural (robustness)
As B, using the behavioural performance index.

### Class balance
Tertile splits on 9 cells give 3 cells per class. Cells differ in epoch count
(MATB runs are 5 min; N-Back blocks total ~6 min per condition). Balance classes
by epoch subsampling with a fixed seed, and report the retained epoch counts.

---

## 4. LOSO protocol

### Structure
Leave-one-subject-out. For each held-out subject: train on the remaining 28,
test on all of the held-out subject's epochs. Outcome = per-subject accuracy,
giving 29 values per (task × band × scheme) cell.

### Reference pipeline
Match the published within-subject baseline exactly (`dataset.md` §6), changing
only the CV structure:
- 5 s non-overlapping epochs, resampled to 250 Hz
- Band-pass to theta [4–8] or alpha [8–12]
- Covariance matrices on the 10-channel subset
- Riemannian MDM

### Robustness classifier
One only, pre-specified at G-LOCK. Default: Riemannian tangent-space projection
+ L2 logistic regression. Regularisation chosen by nested CV **within the
training folds only** (see §5).

### Reporting
Always report the per-subject distribution, not just the mean. The claim is
about between-subject heterogeneity; a mean hides it. Every LOSO result gets a
per-subject strip or dot plot.

---

## 5. Leakage rules — MANDATORY

Silent leakage is the most likely way this project produces a wrong answer that
looks right. Every item below is checked at G2.1 and the check is logged.

### Rules

1. **ICA is fit per subject-session, independently.** Never across subjects,
   never across folds. Since it is fit within a subject and the CV splits
   *between* subjects, per-subject ICA is fold-agnostic and therefore safe —
   but it must be verified, not assumed.

2. **Channel rejection and interpolation decisions are made per subject-session**,
   using only that recording. Never using a global threshold computed across the
   whole dataset.

3. **Any normalisation, whitening, or scaling is fit on training subjects only**
   and applied to the held-out subject. This includes tangent-space reference
   points — the Riemannian mean must be computed from training data only.

4. **No hyperparameter is selected using held-out-subject performance.** Nested
   CV inside the training set, always.

5. **Labels for the held-out subject are never used before scoring.** In
   particular, Scheme B labels for the test subject are derived from that
   subject's own RSME — which is legitimate (RSME is an observed covariate, not
   the prediction target's ground truth) **but must be explicitly justified in
   the manuscript**, because a reader will flag it. The justification: the
   research question is whether better labels improve training, so test labels
   define the target being scored against, not information leaked into the model.
   Run the symmetric control in §7.

6. **Epoch-level splits never cross the subject boundary.** Assert that no
   subject ID appears in both train and test.

### Permutation control (hard requirement, G2.1)

Run the complete LOSO pipeline with **subject-wise permuted labels**: within
each subject, shuffle the cell→label mapping, preserving epoch counts. Repeat
≥200 times with seeds from `config.yaml`.

**Acceptance:** the permuted-label accuracy distribution must be centred within
the chance interval, with the observed 95th percentile at or below the 41.7%
ceiling. A pipeline that beats chance on shuffled labels is broken and every
downstream number is void.

Permute labels, **not** epochs. Shuffling epochs destroys temporal
autocorrelation and produces a falsely reassuring null.

---

## 6. Primary tests and decision rules

Each primary test runs **exactly once**, after G-LOCK. Specify everything below
in `prereg/protocol.md` first.

### H2 — divergence predicts decoding failure

Spearman correlation between D_subj[i] and per-subject LOSO accuracy under
Scheme A, computed separately per task, then meta-analytically combined across
tasks.

- Primary metric: D_subj; primary band: alpha (higher published accuracy)
- n = 29; pooled n ≈ 44 if the Hackathon set is included per the preregistered
  rule
- Report ρ with bootstrap 95% CI
- **Decision rule:** support for H2 requires ρ < 0 with a 95% CI excluding zero
  in the primary analysis, and the same sign in the D_beh robustness analysis

**Power, stated honestly and in the preregistration:** at n = 29, power to
detect ρ = 0.5 is ≈ 0.77; at ρ = 0.4, ≈ 0.55. This is underpowered for moderate
effects. Consequences:
- Pool to n ≈ 44 where the preregistered rule permits
- Lead the paper with the within-subject analyses (522 cells), which are amply
  powered
- **A null H2 must be interpreted as inconclusive, not as evidence of absence.**
  Report an equivalence test (TOST) against a smallest effect size of interest
  fixed at G-LOCK.

### H2b — relabelling helps most where divergence is largest

Mixed model on per-subject accuracy:

```
accuracy ~ scheme * D_subj + task + band + (1 | subject)
```

Interaction term is the test. Sharper than the scheme main effect for the
reason in §3.

### H1a
Descriptive: distribution of D_subj across subjects, with per-subject bootstrap
CIs. No null-hypothesis test; the claim is about magnitude and spread.

---

## 7. Confound battery

Run all of these before interpreting H2. Report as a table regardless of
outcome. If any one substantially attenuates the H2 association, say so plainly.

| Confound | Operationalisation | Why it matters |
|---|---|---|
| Data quality | ICA components rejected, channels interpolated, epochs retained | Noisy subjects may look both divergent and hard to decode |
| Scale use | RSME mean and SD per subject | Range restriction can masquerade as divergence |
| Overall ability | Mean behavioural performance | Skilled subjects may find all conditions easy |
| State fatigue | KSS at session start / end | Sleepiness affects both effort ratings and EEG |
| Session order | Task presentation order from the notebook file | Order effects |
| Demographics | Age, sex, handedness, education | Standard reporting |

**Symmetric control for rule 5 (§5).** Re-run H2 with Scheme B labels for the
test subject replaced by labels derived from a *different, randomly matched*
subject's RSME. If the H2 association survives, the concern about test-label
information is answered empirically rather than rhetorically.

---

## 8. Cross-task transfer (H3)

Train on all N-Back epochs from the 28 training subjects; test on the held-out
subject's MATB epochs. Repeat LOSO. Run under Scheme A and Scheme B.

**Primary test:** paired comparison (Wilcoxon signed-rank, 29 pairs) of transfer
accuracy between schemes. Report the median difference with bootstrap CI and a
paired effect size **regardless of significance**.

### Two confounds that must be addressed head-on

1. **Sensorimotor mismatch.** MATB difficulty changes which subtasks are active,
   so motor demand covaries with workload; N-Back holds motor output constant by
   design. Any transfer difference could reflect this rather than workload.
   Mitigation: report the reverse direction (MATB→N-Back) as well. A labelling
   effect that appears in both directions is much harder to explain by
   sensorimotor confound.

2. **Class prior mismatch.** Tertile relabelling changes the label distribution
   across tasks. Balance by subsampling, report retained counts, and report
   balanced accuracy alongside raw accuracy.

---

## 9. Multiplicity and reporting

- **Primary tests (H2, H2b, H3) are three.** Holm correction across them.
  Everything else is explicitly labelled secondary, robustness, or exploratory
  and is reported uncorrected with that label attached.
- Report effect sizes with CIs everywhere. p-values never appear without one.
- Every figure regenerates from a Makefile target.
- Per-subject distributions are shown, not just means.
- Negative and null results appear in the main text, not the supplement.

### Reporting standard for the paper's own credibility

This manuscript argues that a field's measurement practice is inadequate. It
will be read adversarially and it should be. Therefore:

- Preregistration link in the abstract
- Deviation log published verbatim as a supplement
- All code and derived data on OSF
- Power limitations stated in the Results, not only the Discussion
- The RSME unidimensionality limitation (`dataset.md` §5) stated plainly

A paper about construct validity that is itself sloppy about construct validity
will be rejected, and deserve it.
