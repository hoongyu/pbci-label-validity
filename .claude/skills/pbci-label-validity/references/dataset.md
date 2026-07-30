# Reference — COG-BCI dataset

Source: Hinss, Jahanpour, Somon, Pluchon, Dehais & Roy (2023), *Scientific Data*
10:85. DOI `10.1038/s41597-022-01898-y`.
Data: Zenodo DOI `10.5281/zenodo.6874128`. Licence CC-BY 4.0 — attribution
required, redistribution of derived data permitted.

## Contents

1. Acquisition and integrity
2. Structure
3. Task specifications
4. Behavioural measures
5. Subjective measures
6. Published validation results (replication targets)
7. Known defects and gotchas

---

## 1. Acquisition and integrity

**Before downloading**, verify ~50 GB free. Estimate: 64 ch × 500 Hz × float32
≈ 460 MB per recorded hour; the set exceeds 100 hours.

Download to `data/raw/`. This directory is **read-only** for the rest of the
project — never modify, never write derived files into it.

**Inventory check (part of G0.2).** Expected:
- 29 participant directories, numbered 1–29
- 3 sessions per participant
- Per session: 4 resting-state recordings (RS_Beg/RS_End × EO/EC), plus task
  recordings, plus behavioural outputs and electrode locations
- A notebook file recording task order per session per participant
- A trigger list file mapping LSL triggers to events

Any participant/session with missing task files must be logged, not silently
dropped. Exclusion rules are preregistered at G-LOCK.

**Task numbering in the notebook file:**

| # | Task | # | Task |
|---|---|---|---|
| 1 | PVT | 5 | Zero-Back |
| 2 | Flanker | 6 | MATB-Easy |
| 3 | Two-Back | 7 | MATB-Medium |
| 4 | One-Back | 8 | MATB-Difficult |

Note the N-Back numbering is **descending** (3=Two-Back, 5=Zero-Back). This is a
classic off-by-one source. Assert on it in the loader.

---

## 2. Structure

BIDS format. EEG stored as EEGLAB `.set` + `.fdt` pairs (two files per dataset).
`mne.io.read_raw_eeglab()` reads these directly.

```
data/raw/
└── sub-XX/
    └── ses-S{1,2,3}/
        ├── <task>.set / .fdt
        ├── behavioural outputs
        └── electrode locations
```

Participants numbered 1–29. Sessions spaced one week apart.

---

## 3. Task specifications

### N-Back (in scope)
- Conditions: 0-back, 1-back, 2-back → labelled easy / medium / high
- 48 trials per block, ~2 min per block
- **3 blocks per condition, 9 blocks total per session**
- Digits 1–9, 500 ms presentation, 1500 ms blank
- Hit rate fixed at 1/3 (16 trials per block) across all conditions
- 2-back condition adds 5 "conflict" trials per block (immediate repeats,
  no response required)
- Design intent: identical visual input and motor output across conditions, so
  EEG differences should reflect working memory load rather than sensorimotor
  differences

### MATB-II (in scope)
- Conditions: Easy / Medium / Difficult
- **3 independent runs of 5 min each, one per difficulty, per session**
- Easy = SYSMON + TRACK
- Medium = SYSMON + TRACK + RESMAN
- Difficult = SYSMON + TRACK + RESMAN + COMM, and TRACK made harder
- Note: the manipulation changes *which subtasks are active*, so sensorimotor
  demand is confounded with workload. The published paper suspects this explains
  MATB's higher decoding accuracy. **This is a discussion point, not a defect.**

### PVT, Flanker (out of scope)
No graded workload manipulation. Flanker may be cited in discussion for its ERN
results only.

---

## 4. Behavioural measures

### N-Back
Response and reaction time recorded for every trial, every session. Derive per
cell: accuracy (or error rate) and mean RT on correct trials.

### MATB
Stored as a MATLAB structure with one substructure per subtask:

| Subtask | Fields |
|---|---|
| TRACK | X, Y coordinates at 2 Hz → derive RMS distance from centre |
| SYSMON | alarm onset, reaction time |
| RESMAN | fuel level in relevant reservoirs at 1 Hz |
| COMM | Target, TargetRadio, TargetFrequency, Reacted, Correct |

**Only SYSMON and TRACK are present across all three difficulty levels.** The
published analysis therefore uses only these for performance comparison. Do the
same — using RESMAN or COMM would make Easy incomparable.

Primary behavioural performance index per cell:
- N-Back: accuracy
- MATB: composite of TRACK RMS distance (inverted) and SYSMON RT (inverted),
  z-scored within task. Exact composition preregistered at G-LOCK.

---

## 5. Subjective measure — RSME

**Not NASA-TLX.** The Rating Scale Mental Effort: a 150 mm line with 9 anchor
points from "0 = absolutely no effort" to "130 = extreme effort". Single
dimension. Chosen by the authors for brevity relative to NASA-TLX.

**Granularity: one RSME per task presentation.** Tasks were presented twice in
pseudorandom order, each followed systematically by an RSME. The published
analyses run 3×3 (Session × Difficulty) RMANOVAs on RSME for both N-Back and
MATB, which confirms **one RSME value per difficulty per session per subject**.

Expected: 29 subjects × 2 tasks × 3 sessions × 3 difficulties = **522 RSME
values**. Missingness must be < 10% to pass G1.1.

### Limitation to state in the manuscript
RSME is unidimensional. NASA-TLX would separate mental demand, effort,
frustration and perceived performance. Our "experienced workload" construct is
therefore operationalised as *experienced mental effort* specifically. This is a
genuine limitation and must be named in the Discussion, not buried.

KSS (Karolinska Sleepiness Scale) is also available — at session start, after
PVT, and at session end. Usable as a covariate for state fatigue.

---

## 6. Published validation results — replication targets

These are the numbers P1 must reproduce. Deviation beyond tolerance is a
pipeline problem, not a discovery.

### Manipulation checks (G1.2 targets)

| Effect | Published statistic |
|---|---|
| N-Back RSME × difficulty | F(2,104) = 55.56, p < .005 |
| N-Back RSME × session | F(2,104) = 3.52, p < .05 |
| MATB RSME × difficulty | F(2,104) = 92.73, p < .005 |
| MATB RSME × session | F(2,104) = 17.15, p < .005 |
| N-Back error rate × condition | F(2,56) = 52.25, p < .005 |
| MATB TRACK × difficulty | F(2,56) = 421.99, p < .005 |
| MATB SYSMON × difficulty | F(2,56) = 62.19, p < .005 |

### The anomaly (must be confirmed, G1.2)

**N-Back:** significant session effect on frontal theta (Session 1 vs 3,
t(256) = 2.12, p < .05). **No effect of difficulty on theta power. No effect of
session or difficulty on alpha power.**

**MATB:** significant difficulty effect on frontal and posterior theta
(easy < medium and easy < difficult, all p < .01). Alpha showed a difficulty
effect posteriorly but **in the opposite direction to the established
literature** — the authors flag this explicitly.

### Decoding baseline (G0.4 target)

Within-subject 5-fold CV, 3-class, Riemannian MDM:

| Quantity | Published |
|---|---|
| MATB accuracy | 69.40% ± 12.50% |
| N-Back accuracy | 64.97% ± 12.99% |
| Task effect | F(1,28) = 13.00, p < .001 |
| Alpha band accuracy | 68.41% ± 12.37% |
| Theta band accuracy | 65.97% ± 13.37% |
| Band effect | F(1,28) = 7.95, p < .05 |
| Session 1 / 2 / 3 | 64.30% / 70.30% / 66.96% |
| Session effect | F(2,56) = 4.96, p < .05 |
| Best cell | alpha, session 2 → 70.67% |
| Chance ceiling (95% CI upper, 3-class, ≥60 trials/class) | 41.7% |

---

## 7. Known defects and gotchas

Each of these has a specific failure mode. Assert on them in code.

1. **Cz was not recorded for participants 1–9.** The reference channel subset
   includes FCz and CPz but not Cz, so the 10-channel montage is *probably*
   unaffected — **verify this explicitly rather than assuming**, and decide and
   preregister the handling if any reference channel is missing for any subject.

2. **Reference is Fpz**, not the more common average or mastoid. Full-rank
   average re-referencing is applied before ICA in the published pipeline.

3. **TP9 was sacrificed to record ECG.** It is not an EEG channel. A loader that
   treats all channels as EEG will corrupt the average reference.

4. **No filtering applied at acquisition.** Data is raw, 500 Hz, 24-bit,
   0.05 µV resolution. All filtering is yours.

5. **Impedances started below 25 kΩ** — higher than typical for gel systems.
   Expect more channel rejection than usual. Published averages: 0.34 channels
   interpolated per task, ~7 ICA components rejected per participant-session,
   ~16 epochs (8 s) rejected per task.

6. **Two preprocessing variants exist in the published paper.** The descriptive
   analyses epoch *after* cleaning the continuous signal; the machine-learning
   pipeline epochs *first* and cleans each epoch individually, with automatic
   epoch rejection **disabled**. Reproducing the baseline requires the second
   variant. Mixing them is the single most likely cause of a G0.4 failure.

7. **N-Back numbering is descending in the notebook file** (see §1).

8. **Recording interruptions are documented in the notebook file**, not in the
   data. Read it during inventory.

9. **MATB behavioural data is a MATLAB struct**, not a table, unlike the other
   three tasks. `scipy.io.loadmat` with `struct_as_record=False,
   squeeze_me=True` is the usual entry point.

---

## 8. Pooling dataset (H2 power only)

Neuroergonomics 2021 Passive BCI Competition — cross-session mental workload.
Zenodo DOI `10.5281/zenodo.5055046`. Hinss et al., same group.
15 participants × 3 sessions.

Use **only** to increase n for the H2 subject-level correlation. Do not pool for
any analysis where task or preprocessing differences would confound. Whether it
is pooled at all, and how, is preregistered at G-LOCK — decided before seeing
the COG-BCI H2 result.
