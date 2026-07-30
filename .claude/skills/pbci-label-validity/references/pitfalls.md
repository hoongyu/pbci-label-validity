# Reference — Pitfalls

Failure modes ordered by how often they sink projects of this shape. Consult
before G0.4 and G2.1, and whenever something does not reproduce.

---

## Tier 1 — Will silently produce wrong answers

### 1. Preprocessing order (the G0.4 killer)

COG-BCI's paper describes **two different pipelines**. The descriptive analyses
clean the continuous signal and then epoch. The machine-learning pipeline
**epochs first, cleans each epoch individually, and disables automatic epoch
rejection**.

Using the descriptive variant will not reproduce the published accuracies, and
the discrepancy will look like a subtle bug rather than a structural mismatch.
Check this first, always.

### 2. Normalisation fit across the full dataset

Any scaler, whitener, or Riemannian reference mean computed on all subjects
leaks test-subject information into training. The symptom is LOSO accuracy that
looks suspiciously close to within-subject accuracy — which should not happen,
because cross-subject decoding is genuinely much harder.

**If your LOSO numbers are close to 65–70%, suspect a leak before celebrating.**

### 3. Permuting epochs instead of labels

Epoch-level shuffling destroys temporal autocorrelation and produces a null
distribution that is too tight, making a leaky pipeline look clean. Permute the
**cell → label mapping within subject**, preserving epoch counts and structure.

### 4. The descending N-Back numbering

In the notebook file: 3 = Two-Back, 4 = One-Back, 5 = Zero-Back. Ascending
assumption inverts the entire difficulty axis, which will still produce
above-chance decoding (the classes are still separable) while reversing every
sign in the paper. Assert on it.

### 5. TP9 treated as EEG

TP9 was sacrificed to record ECG. Including it in an average reference injects
cardiac signal into every channel.

### 6. Confusing 8–12 and 8–13 Hz alpha

The ML pipeline uses [8–12]; the descriptive analysis uses [8–13]. Use 8–12 for
anything compared against the decoding baseline.

---

## Tier 2 — Will cost time

### 7. Cz missing for participants 1–9

The 10-channel reference subset contains FCz and CPz but not Cz, so it is
*probably* unaffected. Verify explicitly per subject rather than assuming, and
preregister the handling if any reference channel turns out to be missing.

### 8. MATB behavioural data is a MATLAB struct

Unlike N-Back, Flanker and PVT, which are tables. Use
`scipy.io.loadmat(..., struct_as_record=False, squeeze_me=True)`.

### 9. Using RESMAN or COMM for MATB performance

They are not present in the Easy condition. Any performance index built from
them makes Easy incomparable and will produce a nonsense difficulty gradient.
TRACK and SYSMON only.

### 10. Download and disk

100+ hours at 64 channels and 500 Hz. Verify ~50 GB free before starting and
expect a long transfer. Resume support matters.

### 11. Higher-than-usual impedances

Acquisition started below 25 kΩ, which is loose by gel-system standards. Expect
more channel rejection and more ICA components removed than you might in a
cleaner dataset. This is normal here; do not tighten thresholds to "fix" it,
because that departs from the published pipeline.

---

## Tier 3 — Will weaken the paper

### 12. Reporting only means for LOSO

The entire claim is about between-subject heterogeneity. A mean accuracy hides
exactly the thing under study. Every LOSO result needs a per-subject
distribution plot.

### 13. Letting the divergence metric drift

D_subj is frozen at G-LOCK. Trying alternatives after seeing H2 is the classic
garden of forking paths, and in a paper *about* measurement validity it is fatal
to credibility. The robustness alternatives are preregistered precisely so that
trying them is legitimate.

### 14. Overclaiming causality

The design is observational at the subject level. Divergence is not
manipulated. Every claim stays associational: "divergence was associated with
lower cross-subject accuracy", never "divergence caused decoding failure".

### 15. Ignoring the sensorimotor confound in MATB

MATB difficulty changes which subtasks are active, so motor demand covaries with
workload — while N-Back is explicitly designed to hold motor output constant.
Reviewers will raise this. Run the reverse transfer direction and address it
directly rather than defensively.

### 16. Burying the RSME limitation

RSME is unidimensional mental effort, not multidimensional workload. Our
construct is "experienced mental effort". Say so in the Discussion in plain
language. A reviewer who finds it themselves will trust the rest of the paper
less.

---

## Tier 4 — Project management

### 17. Recruiting a co-author too early

The sequencing decision is deliberate: approach the Neurotechnology chair after
P1, with a reproduced baseline and a confirmed anomaly in hand. A proposal is a
request; results are an offer.

### 18. Stalling P0–P1 while waiting on a co-author

Both phases are fully executable solo and are the currency for recruitment.

### 19. Working harder instead of re-planning

Three consecutive weeks below 4 hours means the timeline is wrong, not that
effort is insufficient. Re-plan the schedule. Log hours weekly in
`outputs/logs/hours.md`.

### 20. Treating a null result as failure

The design deliberately makes a null H2 informative — it would be evidence that
the field's labels are adequate and that generalisation failure is genuinely a
signal problem. That is a real contribution. It is stated in the preregistration
for exactly this reason: so that when the result arrives, the incentive to
salvage it does not exist.

---

## Diagnostic: my LOSO accuracy is much higher than expected

Work in order:

1. Assert no subject appears in both splits
2. Check where every scaler/whitener/Riemannian mean is fit
3. Check hyperparameter selection is nested inside the training folds
4. Run the permutation control — this catches most leaks directly
5. Check class balancing did not accidentally align with subject identity

## Diagnostic: G0.4 will not reproduce

Work the seven-step list in `gates.md` §G0.4 in order. If all seven pass and the
numbers still miss, stop and consult the mentor before touching P1. Contacting
the dataset authors is legitimate and appropriate — reproducibility questions
are what open data is for.
