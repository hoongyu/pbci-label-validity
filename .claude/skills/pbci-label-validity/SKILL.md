---
name: pbci-label-validity
description: Drives the "What do passive BCI workload decoders actually decode?" research project end to end — a three-study construct-validity investigation of task-difficulty labels in EEG mental-workload decoding, using the public COG-BCI dataset. Use this skill for ANY work on this project — setting up the environment, downloading or inspecting COG-BCI data, reproducing the published baseline, building preprocessing or LOSO decoding pipelines, computing divergence metrics, running cross-task transfer, writing the preregistration, drafting the manuscript, or checking whether a phase gate has been passed. Also use it whenever the user mentions COG-BCI, RSME, passive BCI, mental workload decoding, N-Back/MATB transfer, label validity, or asks "what's next" / "can I move on" on this project. Always consult this skill before writing analysis code for this project — the gates and leakage rules are non-negotiable and easy to violate accidentally.
---

# Passive BCI Label Validity — Project Driver

This skill runs a real research project aimed at a peer-reviewed journal. It is
gate-driven: each phase has hard acceptance criteria, and **you do not advance
past a failed gate**. When a gate fails, the job is to diagnose and fix, or to
trigger the documented pivot — not to proceed with a caveat.

## The one-paragraph thesis

Passive BCI mental-workload decoders are trained against experimenter-assigned
task difficulty. The construct of interest is *experienced* workload. These
diverge, and the divergence varies by person. If so, a meaningful share of what
the field calls "cross-subject variability" is label noise arising from a
construct-validity failure — and no amount of domain adaptation fixes a
mislabelled target. Three studies test this on public data.

The opening evidence is already in print: COG-BCI's own validation paper reports
that in the N-Back task, RSME, behaviour and cardiac measures all track
difficulty, but **neither theta nor alpha power shows any difficulty effect** —
while a classifier still reaches ~65% three-class accuracy. Something is being
decoded that is not the canonical workload signature.

## Read these before acting

| File | Read when |
|---|---|
| `PRD.md` | Before any planning, scoping, or writing. Full spec: RQs, hypotheses, studies, scope boundaries, out-of-scope list. |
| `references/dataset.md` | Before touching data. COG-BCI structure, acquisition, known defects. |
| `references/analysis.md` | Before writing any analysis code. Statistical spec, divergence metrics, LOSO protocol, leakage rules. |
| `references/gates.md` | Before declaring any gate passed. Exact numeric criteria and failure playbooks. |
| `references/pitfalls.md` | When something doesn't reproduce, or before P0.4 / P2.1. |

## Phase map and gate summary

Phases are strictly sequential. The preregistration lock between P1 and P2 is
the most important boundary in the project.

| Phase | Name | Hard gate | Criterion (summary) |
|---|---|---|---|
| **P0** | Foundation | **G0.4** | Reproduce published baseline within ±3.0 pp on both tasks |
| **P1** | Study 1 — Divergence | **G1.2**, G1.4 | Replicate manipulation checks; variance components estimated |
| **🔒** | **PREREGISTRATION LOCK** | **G-LOCK** | OSF prereg timestamped before any P2 primary analysis |
| **P2** | Study 2 — Relabel & LOSO | **G2.1**, G2.4 | Leakage audit clean incl. permutation control; H2 executed once |
| **P3** | Study 3 — Cross-task transfer | **G3.3** | H3 executed once; effect size + CI reported regardless of p |
| **P4** | Manuscript & submission | **G4.1** | Clean-clone reproduction of every number in the paper |

Full criteria live in `references/gates.md`. Do not paraphrase them from memory.

## Operating rules

These are not style preferences. Violating any one of them invalidates the
project's central claim, which is a claim about methodological rigour.

1. **No gate skipping.** If asked to "just try the transfer analysis quickly"
   while P0.4 is unmet, decline and explain why. Numbers produced on an
   unvalidated pipeline are worse than no numbers.

2. **Exploratory before the lock, confirmatory after.** Everything in P0–P1 is
   exploratory and may be iterated freely. Everything designated *primary* in
   P2–P3 runs **exactly once**, after the prereg is timestamped. If a primary
   analysis is run and the result is disliked, that is the result.

3. **Every deviation gets logged.** Append to `deviations.md` with date,
   what changed, why, and whether it was decided before or after seeing the
   affected result. An empty deviation log at submission is a red flag, not a
   badge — real projects deviate.

4. **Seeds are fixed and recorded.** Every stochastic step (ICA, CV splits,
   permutation) takes an explicit seed from `config.yaml`.

5. **Derived data is written once and never edited in place.** Regenerate from
   source instead.

6. **The permutation control is mandatory**, not optional (see G2.1). A LOSO
   pipeline that beats chance on shuffled labels is broken, and this failure is
   silent and common.

## Repository layout

Create and maintain exactly this structure. Claude Code should not invent
alternative locations.

```
pbci-label-validity/
├── config.yaml               # seeds, paths, band definitions, channel sets
├── Makefile                  # every artifact regenerable by target
├── deviations.md             # append-only deviation log
├── env/
│   └── requirements.lock     # pinned; generated, not hand-edited
├── data/
│   ├── raw/                  # COG-BCI as downloaded — READ ONLY, never modified
│   └── derived/              # all generated intermediates, versioned by phase
├── src/
│   ├── io/                   # loading, BIDS traversal, inventory
│   ├── preprocess/           # epoching, cleaning, ICA
│   ├── features/             # covariance, band power
│   ├── decode/               # MDM, CV harnesses, LOSO, transfer
│   ├── divergence/           # D_subj, D_beh, composites
│   └── stats/                # variance components, primary tests
├── analyses/
│   ├── P0_baseline/
│   ├── P1_divergence/
│   ├── P2_relabel/
│   └── P3_transfer/
├── outputs/
│   ├── figures/
│   ├── tables/
│   └── logs/                 # one run log per gate attempt, timestamped
└── prereg/
    └── protocol.md           # frozen at G-LOCK; edits after become deviations
```

## Working session protocol

At the start of any session on this project:

1. Read `outputs/logs/` for the most recent gate attempt and its result.
2. State which phase is active and which gate is next.
3. Confirm the gate's exact criterion from `references/gates.md`.
4. Only then start work.

At the end of any session that attempted a gate:

1. Write a timestamped log to `outputs/logs/` recording: gate ID, criterion,
   observed value, PASS/FAIL, and what changed since the last attempt.
2. If FAIL, state the specific next diagnostic — not "try again".

## Phase quick reference

Detail is in `PRD.md` and `references/`. This table is for orientation only.

### P0 — Foundation
Environment pinned → COG-BCI downloaded and inventoried → preprocessing pipeline
runs end-to-end on one subject → **published baseline reproduced**.
Expected duration: 4 weeks part-time. Highest risk of the project.

### P1 — Study 1: Divergence
Extract RSME and behavioural performance into a tidy cell-level table (subject ×
task × session × difficulty) → replicate published manipulation checks →
**confirm the N-Back EEG anomaly is real** → compute divergence metrics →
decompose RSME variance into subject / difficulty / subject×difficulty.

The subject×difficulty variance component is the project's load-bearing
quantity. If its 95% CI includes zero, H2 has no basis — see the pivot in
`references/gates.md` §G1.4.

### 🔒 Preregistration lock
Freeze `prereg/protocol.md`, deposit on OSF, record the timestamp. Primary
analyses, decision rules, exclusion rules and the divergence metric definitions
must all be fixed **before** the first P2 primary run.

### P2 — Study 2: Relabel & cross-subject decoding
Build LOSO harness → **pass leakage audit including permutation control** →
establish nominal-label LOSO baseline (this number does not exist in the
literature; it is itself a contribution) → relabel by within-subject experienced
effort → run H2 and H2b once → confound battery.

### P3 — Study 3: Cross-task transfer
Train on N-Back, test on MATB, under both labelling schemes. H3 is the paper's
strongest claim if it holds: *the construct transfers even when the paradigm
does not.*

### P4 — Manuscript & submission
Reproducibility audit from a clean clone → OSF deposit of code and derived data
→ draft → mentor review → submit.

Target venue and fallbacks are in `PRD.md` §7.

## When the user asks "can I move on?"

Answer only from `references/gates.md`, using the observed number from the most
recent log. Do not answer from impression. If the log is missing, the answer is
"we don't know yet — rerun the gate and log it."
