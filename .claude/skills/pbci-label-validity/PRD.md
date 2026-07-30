# PRD — What do passive BCI workload decoders actually decode?

**Working title:** Construct validity of task-difficulty labels in EEG mental
workload decoding: a three-study re-analysis of COG-BCI

**Status:** Draft v1 · pre-P0
**Owner:** solo first author, part-time (~8 h/week)
**Methodological co-author:** to be secured (embedded/comms PhD mentor covers
signal processing; a construct-validity/psychometrics reader is still needed —
see §8)

---

## 1. Problem statement

Passive BCI (pBCI) research trains classifiers to estimate mental workload from
EEG. In nearly all of this literature the ground-truth label is the
**experimenter-assigned task difficulty** — 0-back vs 1-back vs 2-back, MATB
easy vs medium vs difficult. The construct the field claims to measure is the
operator's **experienced** workload.

These are not the same thing, and the field's own data shows they come apart.

The discipline's acknowledged central obstacle is cross-subject and
cross-session generalisation failure, conventionally attributed to inter-subject
variability and EEG non-stationarity. The proposed reframe:

> A meaningful share of what is called cross-subject variability is **label
> noise arising from a construct-validity failure**. Domain adaptation cannot
> repair a mislabelled target.

### 1.1 The anomaly that motivates this

COG-BCI's own validation paper (Hinss et al., 2023, *Scientific Data*) reports,
for the N-Back task:

- RSME (subjective effort) rises significantly with difficulty
- Behavioural accuracy falls and RT rises with difficulty
- Heart rate rises and HRV falls with difficulty
- **Neither theta nor alpha power shows any significant difficulty effect**

Yet a Riemannian MDM classifier reaches ~65% three-class accuracy on the same
data (chance upper bound 41.7%).

Separately, for MATB, alpha power *was* sensitive to difficulty but moved in the
**opposite direction** to the established literature.

Both anomalies are published, three years old, and unfollowed. They are the
paper's opening.

---

## 2. Research questions

**RQ1** — How large is the divergence between nominal task difficulty and
experienced workload, and how much does it vary between people?

**RQ2** — Does relabelling by experienced workload change cross-subject decoding
performance, and is per-subject divergence predictive of per-subject decoding
failure?

**RQ3** — Does a decoder trained on one paradigm (N-Back) transfer to a more
operationally realistic one (MATB), and does labelling scheme change how well it
transfers?

---

## 3. Hypotheses

Stated with directional predictions and the competing account where one exists.
Formal decision rules are in `references/analysis.md`.

| ID | Hypothesis | Prediction | Competing account |
|---|---|---|---|
| **H1a** | Nominal difficulty and experienced effort diverge | Per-subject rank agreement between difficulty and RSME is well below 1.0 for a non-trivial minority of subjects | Manipulation is strong and uniform; agreement ≈ 1.0 for nearly everyone |
| **H1b** | Divergence is a person-level property, not noise | Subject×difficulty variance component in RSME is reliably > 0 | Divergence is measurement error; component ≈ 0 |
| **H2** | Divergence predicts decoding failure | Per-subject divergence negatively correlates with per-subject LOSO accuracy | Decoding failure is driven by signal quality / anatomy, independent of label fit |
| **H2b** | Relabelling helps most where divergence is largest | Accuracy gain from experienced-effort labels is larger in high-divergence subjects (interaction) | Relabelling helps uniformly or not at all |
| **H3** | The construct transfers even when the paradigm does not | N-Back→MATB transfer is better under experienced-effort labels than nominal labels | Transfer is governed by task-specific sensorimotor confounds; labelling is irrelevant |

**H1b is load-bearing.** If the subject×difficulty variance component is
indistinguishable from zero, H2 and H2b have no basis and the project pivots
(see `references/gates.md` §G1.4).

Note on H2: a *null* result here is publishable and informative — it would
constitute evidence that the field's labels are adequate and that generalisation
failure is genuinely a signal problem. The study is designed so that both
outcomes are reportable. This must be stated in the preregistration.

---

## 4. Studies

### Study 1 — Divergence quantification (Phase P1)

**Unit of analysis:** cell = subject × task × session × difficulty.
Expected N = 29 subjects × 2 tasks × 3 sessions × 3 difficulties = **522 cells**.

**Measures per cell:**
- Nominal difficulty (ordinal, 0/1/2)
- RSME (0–130 continuous)
- Behavioural performance (task-specific; see `references/dataset.md` §4)
- EEG band power (frontal/central/parieto-occipital × theta/alpha)

**Outputs:**
1. Replication of published manipulation checks (RSME, behaviour, cardiac)
2. **Confirmation of the N-Back EEG anomaly**
3. Per-subject divergence metrics D_subj and D_beh
4. Variance decomposition of RSME: subject / difficulty / subject×difficulty /
   session / residual, with bootstrap CIs

### Study 2 — Relabelling and cross-subject decoding (Phase P2)

**Design:** 2 (labelling scheme: nominal vs experienced) × 2 (task) LOSO
decoding, with per-subject accuracy as the outcome.

**Key contribution independent of the hypotheses:** the published baseline used
*within-subject* 5-fold CV. A LOSO baseline for COG-BCI does not exist in the
literature. Producing it is a standalone deliverable.

**Primary test (H2):** correlation between per-subject D_subj and per-subject
LOSO accuracy under nominal labels.

**Secondary (H2b):** mixed model with labelling scheme × divergence interaction.

### Study 3 — Cross-task transfer (Phase P3)

**Design:** train on N-Back, test on MATB, under both labelling schemes.
Within-subject where the same subject appears in both (all 29 do).

**Primary test (H3):** paired comparison of transfer accuracy between labelling
schemes.

This is the paper's strongest claim if it holds. The dataset was explicitly
built to enable N-Back↔MATB transfer work, so the design is welcomed by the data
providers — but that also means competing groups may be working on the plain
version. **Our differentiator is the labelling manipulation, not the transfer
itself.** Frame accordingly.

---

## 5. Scope boundaries

### In scope
- COG-BCI (Zenodo `10.5281/zenodo.6874128`), N-Back and MATB tasks
- Neuroergonomics 2021 Passive BCI Competition dataset (Zenodo
  `10.5281/zenodo.5055046`) as a **pooling dataset for H2 power only**
- Riemannian MDM as the reference classifier (matches published baseline)
- One additional modern classifier for robustness (see §6)

### Explicitly out of scope
Do not let these creep in. Each has killed a comparable project.

- **Deep learning architecture search.** We are not competing on accuracy. One
  modern baseline for robustness, no more.
- **New data collection.** Zero human subjects. If a question requires new data,
  it belongs in a follow-up.
- **PVT and Flanker tasks.** They do not have a graded workload manipulation.
  Flanker may be referenced for the ERN anomaly in discussion only.
- **fNIRS, cardiac-based decoding.** Cardiac is used as a validity criterion in
  Study 1, never as a decoding input.
- **Source localisation, connectivity analyses.** Out of scope entirely.
- **Any claim that divergence *causes* decoding failure.** The design is
  observational at the subject level. Language must stay associational.

---

## 6. Technical baseline

Reproduce exactly before deviating. Full detail in `references/dataset.md` and
`references/analysis.md`.

| Element | Specification |
|---|---|
| Reference classifier | Riemannian MDM (`pyriemann`) on covariance matrices |
| Channel subset | F3, Fz, F4, FCz, C3, C4, CPz, P3, Pz, P4 (10 channels) |
| Epoching | 5 s non-overlapping |
| Resampling | 250 Hz |
| Bands | theta [4–8] Hz, alpha [8–12] Hz |
| Cleaning | auto bad-channel rejection + interpolation (2 SD), full-rank average reference, ICA + ICLabel (eye/muscle/heart at >90% confidence) |
| Published within-subject 5-fold CV | MATB 69.40% ± 12.50%; N-Back 64.97% ± 12.99% |
| Chance ceiling (3-class, ≥60 trials/class) | 41.7% |
| Robustness classifier | one modern alternative, pre-specified at G-LOCK; default is Riemannian tangent-space + logistic regression |

---

## 7. Target venue

| Priority | Venue | Rationale |
|---|---|---|
| 1 | *Journal of Neural Engineering* | The field's methods home; publishes pBCI critique |
| 2 | *Human Factors* | Construct-validity framing lands; the workload literature lives here |
| 3 | *Frontiers in Neuroergonomics* | Fast, in-community, open access |
| 4 | *IEEE TNSRE* | If the transfer result carries the paper |

Decide at P4 based on which study carries the strongest result. Do not decide
earlier — venue-driven framing before results is a form of outcome bias.

---

## 8. Team and authorship

| Role | Status | Need |
|---|---|---|
| First author | Confirmed | — |
| Signal processing / methods | PhD mentor, embedded & electronics — confirmed | Covers pipeline, decoding, reproducibility |
| Construct validity / psychometrics | **Not secured** | Needed for Study 1 framing and reviewer credibility |
| Senior/last author | **Not secured** | Needed for desk-rejection survival |

**Sequencing decision (already made):** approach the TU Berlin Neurotechnology
chair *after* P1 produces results, not before. Walking in with a reproduced
baseline and a confirmed anomaly is a categorically different conversation than
walking in with a proposal.

**Do not delay P0–P1 waiting on co-author recruitment.** Those phases are
executable solo and are exactly the currency needed for recruitment.

---

## 9. Timeline

Part-time, ~8 h/week. Months are indicative; gates are binding.

| Month | Phase | Exit condition |
|---|---|---|
| 1 | P0 Foundation | G0.4 baseline reproduced |
| 2 | P1 Study 1 | G1.2 + G1.4 |
| 2–3 | 🔒 Prereg lock | G-LOCK timestamped |
| 3–4 | P2 Study 2 | G2.1 + G2.4 |
| 5 | P3 Study 3 | G3.3 |
| 6 | P4 Draft | Manuscript complete |
| 7 | P4 Submit | G4.1 + mentor review + submission |

**Schedule risk is the dominant risk.** Three consecutive weeks below 4 h is a
signal to re-plan the timeline, not to work harder. Record weekly hours in
`outputs/logs/hours.md`.

---

## 10. Known risks

| Risk | Severity | Mitigation |
|---|---|---|
| Baseline does not reproduce | **Critical** | G0.4 is a hard stop; playbook in `references/pitfalls.md` |
| H1b variance component ≈ 0 | **Critical** | Documented pivot at G1.4 |
| H2 underpowered at n=29 | High | Pool with Hackathon dataset (n≈44); lead with within-subject analyses which have ample power |
| Silent leakage in LOSO | High | Mandatory permutation control at G2.1 |
| Scooped on plain N-Back→MATB transfer | Medium | Differentiator is the labelling manipulation; OSF prereg establishes timestamp |
| No senior author secured | Medium | P1 results are the recruitment instrument; do not stall on this |
| Disk/compute for 100+ h of 64-ch 500 Hz data | Low | ~50 GB; verify before download |

---

## 11. Definition of done

The project is complete when:

1. Every number in the manuscript regenerates from a clean clone (G4.1)
2. Protocol, code, and derived data are deposited on OSF
3. The deviation log is complete and honest
4. A senior co-author has read and signed off
5. The manuscript is submitted

Not when the results are good. The design deliberately makes null results
publishable; a null H2 that is rigorously established and honestly reported is a
successful outcome of this project.
