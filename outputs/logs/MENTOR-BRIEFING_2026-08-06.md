# Mentor briefing — P1 complete, G1.2 fork triggered
2026-08-06 · *What do passive BCI workload decoders actually decode?*

**Ask:** a decision on framing (§5), and a steer on which of four unblocked
paths to run first (§6). Everything in §1–§4 is done and logged; nothing below
needs re-checking before the conversation.

---

## 1. Status

| Gate | | |
|---|---|---|
| G0.1–G0.3 | ✅ | environment, data, pipeline |
| **G0.4** baseline reproduction (hard stop) | ✅ | |
| G1.1 cell table | ✅ | 522 rows, 0 % RSME missing |
| **G1.2** manipulation checks + anomaly (hard stop) | **Part A ✅ / Part B ❌** | **the fork** |
| G1.3 divergence metrics | ✅ | 16 unit tests pass |
| G1.4 variance decomposition | ✅ | **H1b supported** |
| G-LOCK | ⛔ | blocked on §5 |

All 87 subject-sessions are preprocessed under both published preprocessing
variants. Every deviation is in `deviations.md` with its timing relative to
seeing results.

## 2. What replicated

**Part A is exact.** The three published manipulation-check F values match to
four significant figures. That pins condition assignment, the descending N-Back
numbering, and the session mapping — the mapping is not in question anywhere
below.

**MATB reproduces completely**, including the counter-conventional result the
authors flag themselves: posterior alpha *increases* with difficulty. Frontal
and posterior theta reach F = 57 and F = 119.

**The published N-Back theta null replicates** (p = 0.206).

## 3. What did not: N-Back alpha

The published claim is that in N-Back, subjective, behavioural and cardiac
measures track difficulty while theta and alpha do not. Half of it holds. Alpha
does not:

| N-Back alpha | 0-back | 1-back | 2-back | |
|---|---|---|---|---|
| frontal | +0.048 | +0.020 | −0.068 | monotonic ↓ |
| central | +0.047 | +0.025 | −0.072 | monotonic ↓ |
| posterior | +0.056 | +0.030 | −0.085 | monotonic ↓, η²ₚ = 0.36 |

Subject-centred log power. This is the conventional alpha desynchronisation, in
the textbook direction, and it is large.

Applying the rule pre-committed in `deviations.md` **before** the full sample was
run, on its primary combination (ROI = full, reject = none): MATB holds and an
N-Back null fails → **the documented fork of `gates.md` §G1.2**.

## 4. What has been ruled out

The failing criterion is not fragile and is not ours:

| | |
|---|---|
| Parameter dependence | fails in **all six** combinations (3 rejection thresholds × 2 ROI sets), p from 2e-03 to 2e-09 |
| Insensitive pipeline | MATB is a strong positive control on the same code, subjects and sessions |
| Preprocessing variant | ML → descriptive shrank η²ₚ by ~⅓ (0.505 → 0.362); it did not remove it |
| Sample size | n = 29, and 0/2000 bootstrap draws failed elsewhere |
| **Time-on-task / drowsiness** | order is counterbalanced (τ = −0.049, p = 0.33); **no drift exists at all** — all 12 slopes on presentation position n.s.; effect unchanged after residualising position |
| **ICA non-convergence, interpolation** | both fitted **per subject-session across all conditions**, so they are applied identically to all three difficulty levels and cannot manufacture a difference between them |
| Condition mapping | pinned by Part A matching to four significant figures |

Per-subject consistency is the hardest to explain away: **27 of 29 subjects
individually show 2-back alpha below 0-back** (sign test p = 1.6e-06).

**One methodological difference remains untested** (see §6.2): the published
analysis may have used relative power, or power normalised to the resting-state
recordings, where ours is absolute log power.

## 5. Decision needed — framing

`gates.md` §G1.2's playbook: *"a major finding in its own right and a fork…
the paper's framing changes completely; it may become a reproducibility paper."*

| | Option | For | Against |
|---|---|---|---|
| **A** | Reproducibility paper | result is solid; playbook endorses it | abandons the original contribution |
| **B** | Narrow the claim — theta only | theta null replicates cleanly | halves the anomaly's force |
| **C** | Follow the alpha sign reversal | see below | needs new analysis design |

**C is not a consolation prize.** Alpha moves in *opposite* directions in the
two tasks — down with load in N-Back (−0.141), up with load in MATB (+0.268).
Both are called workload manipulations. A band that reverses sign between two
workload tasks is not behaving like a workload index, which is a direct,
quantified answer to RQ3 ("does the construct transfer even when the paradigm
does not") — arguably more direct than the route the PRD planned.

## 6. Four paths that are not blocked on this decision

Ranked by expected value ÷ cost.

**6.1 Email the dataset authors** — cost: one email. Six independent signs say
the reference documents describe an *earlier* COG-BCI revision than the Zenodo
copy in hand (§7). If the published alpha analysis ran on different data, that
explains the one divergent criterion outright. Draft is written and ready.

**6.2 Resting-state baseline / relative power** — the last untested
methodological difference. Each session has four unused resting recordings
(RS_Beg/RS_End × eyes open/closed). Alpha's resting level varies enormously
between people and baseline normalisation is common in this literature. Cost:
one re-sweep (~4–8 h machine time). *Prior: moderate-to-low — theta being flat
while alpha moves already argues against a global gain change.*

**6.3 The second dataset** — Neuroergonomics 2021 Passive BCI Competition
(Zenodo `10.5281/zenodo.5055046`, same group), already in PRD scope as an H2
pooling set. **It has N-Back.** If alpha tracks difficulty there too, the
COG-BCI-revision explanation dies and the finding upgrades to "the published
result does not hold" — a stronger paper. If it does not, the problem localises
to COG-BCI. **Decisive either way.** Cost: 1–2 days.

**6.4 Measurement error in D_subj** — see §8; cost ~half a day, needed under
every branch.

## 7. Six signs of a data-revision mismatch

1. `TP9` absent from all 87 sessions; the ECG channel is `ECG1`
2. extraction is 35.89 GB, not the documented ~50 GB
3. 27 of 29 archives carry an undocumented extra directory level
4. a "2 SD" bad-channel criterion is irreconcilable with the published
   0.34 channels/task on 62 channels
5. **N-Back trial pacing is 2.516 s in session 1 against a documented 2.0 s**
   (2.008 s in session 3), and per-session N-Back accuracy tracks pacing at
   Spearman r = 0.946
6. `gates.md` §G0.2's "assert TP9 is identified as ECG" cannot be satisfied

Item 5 is the strongest: a measurable deviation in an experimental parameter,
not a packaging or documentation slip.

## 8. A second problem, independent of the fork

G1.4 supports H1b — the subject × difficulty slope variance is reliably above
zero (N-Back 35.07, CI [6.67, 62.07]; MATB 48.51, CI [18.06, 75.09]). So H2 and
H2b have a basis.

**But individual divergence cannot be measured precisely enough to use as-is.**
Per-subject bootstrap CIs on D_subj have a median width of 0.773 on a [0, 2]
scale. Only **2 of 29** N-Back subjects — and **0 of 29** MATB subjects — have a
CI that clears the metric's own floor. H2 uses per-subject D as a predictor, so
as specified it would be badly attenuated regardless of how the fork resolves.

`analysis.md` §1 anticipated this and requires the uncertainty to be propagated
into H2. Concretely: use hierarchical shrinkage estimates of D derived from the
G1.4 model rather than raw per-subject τ-b. Must be fixed at G-LOCK.

Two further G-LOCK items surfaced: **ROI channel membership** (still
INTERPRETIVE, and it drives two of the parameter-dependent verdicts), and
**8 subject-sessions flagged `interrupted`** in `notebook.mat` — a ready-made
exclusion candidate that must be decided on what the flag means, not on what it
does to a result.

## 9. Also outstanding

- **N-Back error-rate definition** gives F = 193.82 against a published 52.25.
  D_beh depends on it; must be fixed at G-LOCK.
- **ICA hits `max_iter` in ~90 % of subject-sessions**, in both variants. Ruled
  out as a cause of the fork (§4) but a quality concern in its own right.
- D_subj and D_beh **do not agree** (N-Back ρ = −0.153, MATB +0.311, neither
  significant). `analysis.md` §1: this is a finding, not a defect. It compounds
  the fork — the label is questionable against EEG, *and* the two non-EEG
  criteria for label validity disagree with each other.

---

### Reading order if time is short
§3 (what broke) → §4 (why it is not ours) → §5 (the decision) → §6.3 (the
decisive experiment).
