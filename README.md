# What do passive BCI workload decoders actually decode?

English | [简体中文](README.zh-CN.md)

A gate-driven reproduction and construct-validity study of EEG mental-workload
decoding, built on the public COG-BCI dataset. The question is whether nominal
**task difficulty** is a valid training target for passive BCI workload
decoders, or whether decoders trained on it are learning something else that
merely correlates with the label.

> **Status: halted, archived as a record.** Work stopped at gate G1.2, which the
> project's own rules define as a hard stop requiring a change of plan rather
> than a workaround. The analyses below ran to completion and their verdicts are
> logged; nothing downstream of G1.2 was started. See
> [Gate status](#gate-status).

## Why the question

Published workload decoders are trained on the experimenter's difficulty label.
If EEG does not actually track that label, a decoder trained on it can still
score above chance by learning task-specific features, eye or muscle activity,
or anything else that differs between conditions. This project therefore
measures the gap between *nominal* difficulty and *experienced* workload, and
asks what that gap does to decoding.

Four hypotheses carry the design:

| ID | Claim |
|---|---|
| H1a | Nominal difficulty and experienced effort diverge |
| H1b | That divergence is a person-level property, not noise |
| H2 / H2b | Divergence predicts decoding failure, and relabelling helps most where divergence is largest |
| H3 | The construct transfers across paradigms even when the task does not |

H1b is load-bearing: if the subject-by-difficulty variance component is
indistinguishable from zero, H2 and H2b have no basis.

## Data

**COG-BCI** — 29 participants, 3 sessions each, 4 cognitive tasks, over 100
hours of EEG and ECG in BIDS format.

- Dataset: Zenodo [`10.5281/zenodo.6874128`](https://doi.org/10.5281/zenodo.6874128) (concept DOI, resolves to the latest version), CC-BY 4.0
- Paper: Hinss, Jahanpour, Somon, Pluchon, Dehais and Roy (2023), *Scientific Data* 10:85, [`10.1038/s41597-022-01898-y`](https://doi.org/10.1038/s41597-022-01898-y)
- In scope here: **N-Back** and **MATB** only, the two tasks with a graded
  workload manipulation. PVT and Flanker are out of scope.

No data is redistributed. `data/raw` is gitignored and is fetched from Zenodo by
`make download`.

A version note that matters for reproduction: the Zenodo record is at version 4,
whose changelog states that it *"corrected an electrode name mismatch"*.
Version 1 (`10.5281/zenodo.6874129`) was downloaded and compared against
version 4 for `sub-01`: all 12 recordings carry **identical channel names** and
every `.fdt` payload is **byte-identical**. For that subject the two versions do
not differ.

## Gate status

Every gate has a log in `outputs/logs/` recording its criteria, its numbers and
its verdict, including failed attempts.

| Gate | What it checks | Result |
|---|---|---|
| G0.1 | Environment reproducible from the lockfile | pass |
| G0.2 | Data acquired and inventoried | pass |
| G0.3 | Preprocessing runs end to end | pass |
| **G0.4** | **Baseline reproduction** (hard stop) | **pass** |
| G1.1 | Cell-level table complete | pass |
| **G1.2** | **Manipulation checks and anomaly confirmation** (hard stop) | **Part A pass, Part B fail** |
| G1.3 | Divergence metrics | pass |
| G1.4 | Variance decomposition (H1b) | pass |
| G-LOCK | Preregistration frozen | **not reached** |
| P2 to P4 | Relabelling, transfer, manuscript | not started |

### G0.4, the published decoding baseline reproduces

Within-subject 5-fold cross-validation, 3-class, Riemannian MDM on 10-channel
covariance matrices, over 87/87 subject-sessions (348 cells).

| Task | Observed | Published | Acceptance window |
|---|---|---|---|
| MATB | **71.88%** | 69.40% | 66.40 to 72.40 (±3.0 pp) |
| N-Back | **64.30%** | 64.97% | 61.97 to 67.97 (±3.0 pp) |

All three directional criteria also held, including the non-monotonic peak at
session 2, reproduced to within 1.4 pp on every session.

### G1.1, cell table

522/522 expected rows (29 subjects × 2 tasks × 3 sessions × 3 difficulties),
32 columns. RSME is missing in **8/522 cells (1.53%)** against a threshold of
less than 10%.

### G1.2, Part A reproduces and Part B does not

**Part A** replicates the published manipulation checks: three F statistics
agree with the published values to four significant figures, which pins
condition assignment, the descending N-Back numbering and the session mapping.

**Part B** has to confirm the anomaly the project was built on, that in N-Back
the subjective, behavioural and cardiac measures track difficulty while theta
and alpha power do not. Half of it holds.

Measured across 12 combinations of 3 ROI definitions and 4 epoch-rejection
criteria, with 29 subjects:

| Criterion | Holds in |
|---|---|
| MATB: difficulty effect on frontal theta | 12/12 |
| MATB: difficulty effect on posterior theta | 12/12 |
| MATB: posterior alpha effect present | 12/12 |
| MATB: posterior alpha *increases* with difficulty | 12/12 |
| N-Back: no session effect on alpha | 12/12 |
| N-Back: no difficulty effect on theta | 7/12, parameter-dependent |
| **N-Back: no difficulty effect on alpha** | **0/12** |

The published N-Back **theta** null replicates. The N-Back **alpha** null does
not, under any combination tried, including the paper's own electrode clusters
and its own 2 SD rejection criterion. Alpha falls monotonically with load across
all three ROIs, and **26/29, 27/29 and 25/29 subjects individually** show
2-back alpha below 0-back.

Candidate explanations tested and excluded by measurement rather than by
argument: preprocessing variant, epoch length, four rejection criteria, three
ROI definitions, band and power definitions, time-on-task and presentation
order, ICA non-convergence, bad-channel interpolation, sample size,
condition-to-file mapping, and the dataset version. An insensitive pipeline is
excluded by MATB reaching F = 166 on the same data.

Alpha also moves in **opposite directions in the two tasks**, falling with load
in N-Back and rising with load in MATB. Both are described as workload
manipulations.

### G1.3, divergence metrics

58/58 rows (29 subjects × 2 tasks). D_subj and D_beh are `1 − τ_b` between
nominal difficulty and either RSME or behavioural performance, over the 9 cells
per subject and task, with per-subject bootstrap confidence intervals.

Three results beyond the checklist:

- **D = 0 is unattainable.** τ_b penalises a mismatch in tie structure, not only
  in ordering, and nominal difficulty always has three ties of three. A subject
  ordered perfectly across levels but varying within one scores D = 0.134.
- **Per-subject intervals are wide**, median width 0.773 on a [0, 2] scale for
  N-Back D_subj. Only 2/29 N-Back subjects and 0/29 MATB subjects have an
  interval clearing the metric's own floor.
- **D_subj and D_beh do not agree** (N-Back ρ = −0.153, MATB ρ = +0.311, neither
  significant). The specification treats this as a finding rather than a defect.

### G1.4, variance decomposition, H1b supported

`RSME ~ 1 + difficulty + (1 + difficulty | subject) + (1 | session)`, fitted per
task with crossed random effects and 2000 subject-level bootstrap draws.

| Task | Subject × difficulty slope variance | 95% CI | H1b |
|---|---|---|---|
| N-Back | 35.07 | [6.67, 62.07] | supported |
| MATB | 48.51 | [18.06, 75.09] | supported |

0/2000 draws failed to converge in either task. Subject ICC is 0.435 for N-Back
and 0.480 for MATB.

`variance.py --simulate` recovers known variance components from synthetic data
and is worth running before trusting the fitter. It caught an error that
inflated every component by a factor of about 40 while leaving the residual
correct, which nothing in the output would have revealed.

## Two preprocessing variants

The published work uses two pipelines, and mixing them is the most likely cause
of a failed baseline reproduction. Both are implemented:

| | ML variant (`src/preprocess/run.py`) | Descriptive variant (`src/preprocess/descriptive.py`) |
|---|---|---|
| Order | epoch first, clean each epoch | clean the continuous signal, then epoch |
| Epoch length | 5 s | 0.5 s |
| Epoch rejection | disabled | enabled |
| Alpha band | 8 to 12 Hz | 8 to 13 Hz |
| Used for | G0.4 decoding baseline | G1.2 band-power analyses |

Band power in the descriptive variant is computed by filtering the
**continuous** signal before epoching. At 0.5 s an epoch is 126 samples while an
FIR bandpass for theta needs a 413-sample kernel, so filtering each epoch
distorts the result.

## Preregistration

`prereg/protocol.md` is **a placeholder, not a protocol.** It is authored during
P1 and frozen at G-LOCK, which this project never reached. Nothing here is
preregistered.

What does exist is `deviations.md`: every departure from the plan, each recorded
with its timing relative to seeing a result. It includes decision rules
committed to in advance, and one case where such a rule was replaced because it
was biased toward confirming the hypothesis.

## Reproducing

Python 3.12. Dependencies are pinned in `env/requirements.lock` (72 packages,
including MNE-Python, mne-icalabel, pyriemann and statsmodels).

```bash
python -m venv .venv
.venv/Scripts/pip install -r env/requirements.lock   # Windows
# .venv/bin/pip install -r env/requirements.lock     # POSIX

make download-check    # preflight: disk space and record metadata, downloads nothing
make download          # about 29.5 GB from Zenodo, resumable
make verify-raw        # md5 every local file against the Zenodo API
make extract           # unzip sub-*.zip in place

make inventory         # G0.2
make baseline          # G0.4   decoding baseline
make cells             # G1.1   cell-level table
make manipulation      # G1.2 Part A
make anomaly           # G1.2 Part B, runs the descriptive-variant sweep first
make confound          # presentation-order control for G1.2
make divergence        # G1.3
make variance          # G1.4
make test              # pytest
```

`make all` runs the analysis chain without re-downloading. Preprocessing the
full dataset takes many hours per variant. `sweep.ps1` and `supervise.ps1` exist
because a worker on the original machine was killed under memory pressure
mid-sweep, leaving the sweep idle while still looking busy.

All seeds are fixed in `config.yaml`, which also carries the channel set, the
band edges and the cleaning thresholds. Every value in it that departs from the
reference documents has an entry in `deviations.md`.

## Repository layout

```
src/io/            dataset download, verification, inventory, task-code guards
src/preprocess/    the two preprocessing variants and a memory guard
analyses/P0_*/     G0.4 decoding baseline
analyses/P1_*/     cell table, manipulation checks, divergence metrics,
                   variance decomposition, order-confound control
outputs/logs/      one log per gate attempt, including failures
outputs/tables/    the numbers behind each verdict
deviations.md      every departure from the plan, with timing
prereg/            placeholder protocol, never frozen
```

`.claude/skills/pbci-label-validity/` holds the project's own operating rules,
the PRD, the gate definitions, and reference notes on the dataset and the
analysis specification.

## Citing the dataset

```bibtex
@article{hinss2023cogbci,
  title   = {Open multi-session and multi-task EEG cognitive Dataset for
             passive brain-computer Interface Applications},
  author  = {Hinss, Marcel F. and Jahanpour, Emilie S. and Somon, Bertille and
             Pluchon, Lou and Dehais, Frederic and Roy, Raphaelle N.},
  journal = {Scientific Data},
  volume  = {10},
  pages   = {85},
  year    = {2023},
  doi     = {10.1038/s41597-022-01898-y}
}
```

## License

Code in this repository is licensed under the **Apache License 2.0**; see
[LICENSE](LICENSE).

The COG-BCI dataset is **not** included or redistributed here. It carries its
own licence, CC-BY 4.0, granted by its authors, and `make download` fetches it
from Zenodo under those terms. Attribution for the dataset belongs to Hinss et
al. (2023); see [Citing the dataset](#citing-the-dataset).
