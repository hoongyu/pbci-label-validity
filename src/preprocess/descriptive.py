"""Descriptive-variant preprocessing — band power for G1.2 Part B.

`dataset.md` §7.6 and `pitfalls.md` #1: the published paper runs **two**
pipelines. The machine-learning one epochs first and cleans each epoch with
automatic epoch rejection disabled — that is `pipeline.py`, and G0.4 passed on
it. The **descriptive** analyses clean the continuous signal and epoch
afterwards, and the published band-power results — including the N-Back anomaly
this project is built on — come from that one.

G1.2 attempt 1 tested descriptive-variant published claims against
ML-variant observations and unsurprisingly disagreed. This module supplies the
missing half.

Differences from the ML variant, each traceable to a reference:

| | ML (`pipeline.py`) | Descriptive (here) |
|---|---|---|
| order | epoch, then clean each epoch | clean continuous, then epoch |
| ICA fit on | epochs | continuous |
| epoch length | 5 s (`gates.md` §G0.3) | **8 s** (`dataset.md` §7.5) |
| epoch rejection | disabled (`dataset.md` §7.6) | **enabled** (~16/task, §7.5) |
| alpha band | 8–12 (`pitfalls.md` #6) | **8–13** (#6) |

**The ML pipeline is not modified.** G0.4 passed on it and its derived data
stays in `data/derived/P0/`. This writes to `data/derived/P1_descriptive/`.
"""

from __future__ import annotations

import argparse
import gc
import json
import os
import time
import warnings
from pathlib import Path

import numpy as np

from src.io.inventory import REPO_ROOT, load_config, raw_dir
from src.io.taskcodes import EEG_STEMS, IN_SCOPE
from src.preprocess.resources import (
    DEFAULT_MIN_FREE_GB,
    describe,
    require_free_memory,
)
from src.preprocess.pipeline import (
    ICA_FIT_DECIM,
    ICLABEL_CLASSES,
    ORIGINAL_REFERENCE,
    _detect_bad_channels,
    _place_reference_channel,
)

#: Descriptive-variant epoch length. **0.5 s, from the paper itself**:
#: "The data were then epoched into 0.5-second segments and an automatic epoch
#: rejection using a 2 standard deviation criterion was applied."
#: (Hinss et al. 2023, Technical Validation.)
#:
#: This was 8.0 s until 2026-08-06, and that was my error. `dataset.md` §7.5
#: lists published averages of *rejected* quantities -- "0.34 channels
#: interpolated per task, ~7 ICA components rejected per participant-session,
#: ~16 epochs (8 s) rejected per task" -- and I read the parenthetical as the
#: epoch length rather than as the total duration those 16 epochs represent.
#: 16 x 0.5 s = 8.0 s exactly, which settles the reading. The consequence was a
#: descriptive variant with epochs 16x too long, and G1.2 Part B was decided on
#: it. See `deviations.md`.
EPOCH_LENGTH_S = 0.5

#: Bands for the descriptive analyses. Alpha is 8-13 here, not the 8-12 used
#: for anything compared against the decoding baseline (`pitfalls.md` #6).
BANDS = {"theta": (4.0, 8.0), "alpha": (8.0, 13.0)}

#: Epoch-rejection modes evaluated in parallel.
#:
#: `sd2` is the PUBLISHED criterion, quoted above: a 2 standard deviation
#: automatic epoch rejection. I previously recorded the criterion as
#: "INTERPRETIVE, and irreducibly so", which was wrong -- it is stated in the
#: paper's Technical Validation section, which I had not read, having worked
#: from the project's reference summaries instead.
#:
#: The criterion is applied to ONE statistic per epoch, not per channel. With
#: 62 channels, rejecting whenever any single channel exceeds 2 SD would
#: discard almost everything; a single global statistic thresholded at +2 SD
#: discards ~2.3% of a normal distribution, which on a ~6.6 min N-Back
#: recording (~790 epochs at 0.5 s) is ~18 epochs -- against the published ~16
#: per task. That arithmetic is the reason for reading it this way, and
#: `n_kept` in the output records the achieved count so the reading stays
#: checkable rather than assumed.
#:
#: The fixed peak-to-peak thresholds are kept alongside it as a sensitivity
#: check, and `none` as the criterion that cannot bias the difficulty axis:
#: measured on sub-01/ses-S1, median PTP is 98 / 162 / 219 uV for MATB easy /
#: medium / difficult, so the amplitude distribution shifts with difficulty and
#: any amplitude-based rejection preferentially discards the high-workload
#: condition. That concern applies to `sd2` too, and is exactly why it is
#: reported next to `none` rather than instead of it.
SD_CRITERION = 2.0

REJECT_THRESHOLDS: dict[str, float | None] = {
    "none": None,
    "sd2": None,          # data-dependent; see `_keep_mask`
    "ptp150": 150e-6,
    "ptp300": 300e-6,
}


def _keep_mask(tag: str, ptp: np.ndarray, threshold_v: float | None) -> np.ndarray:
    """Which epochs survive rejection mode `tag`."""
    if tag == "none":
        return np.ones(ptp.size, bool)
    if tag == "sd2":
        # Global statistic per epoch, one-sided: only unusually LARGE epochs are
        # artefacts. A two-sided cut would also discard the quietest epochs,
        # which is where alpha lives.
        return ptp <= ptp.mean() + SD_CRITERION * ptp.std(ddof=1)
    return ptp <= threshold_v

#: ROIs over the full montage. The 10-channel subset exists for the decoding
#: baseline; a descriptive band-power analysis has no reason to be restricted
#: to it. Both are computed so that a pipeline-variant difference can be told
#: apart from a channel-set difference.
def _roi_of(channel: str) -> str | None:
    name = channel.upper()
    if name.startswith(("FP", "AF")) or (name.startswith("F") and
                                         not name.startswith(("FC", "FT"))):
        return "frontal"
    if name.startswith(("FC", "FT", "C", "T7", "T8")) and not name.startswith("CP"):
        return "central"
    if name.startswith(("CP", "TP", "P", "PO", "O")):
        return "posterior"
    return None


#: The PUBLISHED electrode clusters, quoted verbatim from the paper's Technical
#: Validation section:
#:
#:   "For the frontal area, a cluster of 10 electrodes was averaged: F3, F1,
#:    Fz, F2, F4, FC3, FC1, FCz, FC2, FC4; for the central area, 10 electrodes
#:    were averaged: C3, C1, Cz, C2, C4, CP3, CP1, CPz, CP2, CP4; and for the
#:    parieto-occipital area, a cluster of 11 electrodes was averaged: P3, P1,
#:    Pz, P2, P4, PO3, POz, PO4, O1, Oz, O2."
#:
#: `build_cells.ROIS` carries a note that ROI membership is INTERPRETIVE
#: because "dataset.md does not name the ROI channels". The paper does. These
#: lists replace guesswork for the purpose of REPRODUCING the published
#: analysis; the project's own preregistered ROIs are still a G-LOCK decision
#: and are not settled by this.
#:
#: Note "central" here includes Cz, which is absent for participants 1-9
#: (`dataset.md` §7.7) -- so that cluster is one electrode short for those
#: subjects, in the published analysis as well as in this reproduction.
PUBLISHED_ROIS = {
    "frontal": ("F3", "F1", "Fz", "F2", "F4", "FC3", "FC1", "FCz", "FC2", "FC4"),
    "central": ("C3", "C1", "Cz", "C2", "C4", "CP3", "CP1", "CPz", "CP2", "CP4"),
    "posterior": ("P3", "P1", "Pz", "P2", "P4", "PO3", "POz", "PO4",
                  "O1", "Oz", "O2"),
}

SUBSET_ROIS = {
    "frontal": ("F3", "Fz", "F4", "FCz"),
    "central": ("C3", "C4", "CPz"),
    "posterior": ("P3", "Pz", "P4"),
}


def preprocess_session_descriptive(raw_root: Path, config: dict, *, subject: int,
                                   session: int, verbose: bool = True) -> dict:
    """Clean continuous, then epoch; return band power per condition x ROI."""
    import mne
    from mne_icalabel import label_components

    mne.set_log_level("ERROR")
    eeg = config["eeg"]
    cleaning = config["cleaning"]
    sfreq_target = float(eeg["sfreq_target"])
    reject_labels = set(cleaning["iclabel_reject"])
    threshold = float(cleaning["iclabel_threshold"])
    seed = int(config["seeds"]["ica"])

    def say(msg: str) -> None:
        if verbose:
            print(f"    {msg}", flush=True)

    eeg_dir = raw_root / f"sub-{subject:02d}" / f"ses-S{session}" / "eeg"
    raws, boundaries = [], []
    for condition in IN_SCOPE:
        path = eeg_dir / f"{EEG_STEMS[condition]}.set"
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            raw = mne.io.read_raw_eeglab(path, preload=True)
        raw.drop_channels([c for c in raw.ch_names if "ECG" in c.upper()])
        # Resample immediately, before the next recording is loaded. Holding
        # all six at the acquisition rate first is what made this pipeline's
        # startup peak twice its steady state, and that peak is what pushed the
        # machine into dirty-page congestion on 2026-08-03.
        raw.resample(sfreq_target)
        raw.filter(1.0, 45.0, fir_design="firwin")
        boundaries.append((condition, raw.n_times / raw.info["sfreq"]))
        raws.append(raw)

    # --- clean the CONTINUOUS signal, before any epoching
    combined = mne.concatenate_raws(raws)
    raws.clear()                     # release the per-recording copies
    gc.collect()
    # concatenate_raws consumes the list but the local reference keeps every
    # source Raw alive -- ~265 MB that is never used again. Dropping it matters
    # on a machine that bluescreened under memory pressure.
    raws.clear()
    del raws
    say(f"continuous: {combined.n_times / combined.info['sfreq']:.0f}s, "
        f"{len(combined.ch_names)} channels")

    # bad channels on the continuous recording, then interpolate
    events_tmp = mne.make_fixed_length_events(combined, duration=EPOCH_LENGTH_S)
    probe = mne.Epochs(combined, events_tmp, tmin=0.0, tmax=EPOCH_LENGTH_S,
                       baseline=None, preload=True, reject=None)
    bads = _detect_bad_channels(probe, float(cleaning["bad_channel_sd"]),
                                statistic=cleaning.get("bad_channel_statistic",
                                                       "kurtosis"))
    del probe
    combined.info["bads"] = bads
    if bads:
        combined.interpolate_bads(reset_bads=True)
    say(f"interpolated {len(bads)}: {bads or 'none'}")

    if ORIGINAL_REFERENCE not in combined.ch_names:
        combined = mne.add_reference_channels(combined, ORIGINAL_REFERENCE)
        _place_reference_channel(combined, ORIGINAL_REFERENCE)
    combined.set_eeg_reference("average", projection=False)

    # --- ICA on the continuous signal
    rank = mne.compute_rank(combined, rank=None).get("eeg", len(combined.ch_names))
    n_components = max(1, min(rank, len(combined.ch_names) - 1))
    ica = mne.preprocessing.ICA(n_components=n_components, method="infomax",
                                fit_params=dict(extended=True),
                                random_state=seed, max_iter="auto")
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ica.fit(combined, decim=ICA_FIT_DECIM)
        labels = label_components(combined, ica, method="iclabel")

    probs = np.asarray(labels["y_pred_proba"]).ravel()
    names = list(labels["labels"])
    exclude = [i for i, (n, p) in enumerate(zip(names, probs))
               if ICLABEL_CLASSES.get(n) in reject_labels and p > threshold]
    ica.exclude = exclude
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ica.apply(combined)
    n_iter = int(getattr(ica, "n_iter_", -1))
    say(f"ICA {n_components} comps, rejected {len(exclude)}, {n_iter} iterations")

    # --- epoch AFTER cleaning, with automatic rejection enabled
    out: dict = {"subject": subject, "session": session,
                 "n_components": n_components, "n_components_rejected": len(exclude),
                 "n_iter": n_iter, "channels_interpolated": len(bads),
                 "interpolated": bads, "conditions": {}}

    offset = 0.0
    for condition, duration in boundaries:
        picks_all = [c for c in combined.ch_names if _roi_of(c)]
        starts = []
        t = offset
        while t + EPOCH_LENGTH_S <= offset + duration:
            starts.append(int(round(t * combined.info["sfreq"])) + combined.first_samp)
            t += EPOCH_LENGTH_S
        offset += duration
        if not starts:
            continue
        events = np.column_stack([np.asarray(starts, dtype=int),
                                  np.zeros(len(starts), dtype=int),
                                  np.ones(len(starts), dtype=int)])
        # Build unrejected first so the peak-to-peak distribution can be
        # recorded. A fixed threshold rejects far more of the harder MATB
        # conditions (more active subtasks, more EMG), and differential loss
        # along the very axis under test would bias the difficulty comparison.
        # Recording percentiles lets the threshold be calibrated offline
        # against the published ~16/task without re-running ICA.
        epochs = mne.Epochs(combined, events, tmin=0.0, tmax=EPOCH_LENGTH_S,
                            baseline=None, preload=True, reject=None,
                            reject_by_annotation=False)
        n_made = len(epochs)
        if n_made == 0:
            continue
        raw_data = epochs.get_data(picks="eeg", copy=False)
        ptp = (raw_data.max(axis=2) - raw_data.min(axis=2)).max(axis=1)  # per epoch
        entry: dict = {
            "n_epochs_made": n_made,
            "ptp_percentiles_uV": {
                str(q): float(np.percentile(ptp, q) * 1e6)
                for q in (10, 25, 50, 75, 90, 95, 99)
            },
            "n_kept_at_uV": {
                str(int(th * 1e6)): int((ptp <= th).sum())
                for th in (75e-6, 100e-6, 150e-6, 200e-6, 300e-6, 500e-6, 1e-3)
            },
        }
        picked = epochs.copy().pick(picks_all)
        data_all = np.ascontiguousarray(picked.get_data(copy=True))
        names_all = picked.ch_names
        sfreq = float(epochs.info["sfreq"])

        # Band-filter once, then evaluate every rejection threshold on the
        # result. No fixed peak-to-peak threshold can both match the published
        # ~16 epochs/task and avoid difficulty-graded loss in MATB: the PTP
        # distribution itself shifts with difficulty (median 98 / 162 / 219 uV
        # for easy / medium / difficult) because harder MATB activates more
        # subtasks and so produces more EMG. That is a property of the
        # paradigm, not noise. Computing power under each threshold turns an
        # unresolvable parameter choice into a sensitivity analysis.
        for band, (lo, hi) in BANDS.items():
            filtered = mne.filter.filter_data(data_all.copy(), sfreq, lo, hi,
                                              fir_design="firwin", verbose=False)
            power = filtered.var(axis=2)                     # (n_epochs, n_ch)
            for tag, threshold_v in REJECT_THRESHOLDS.items():
                keep = _keep_mask(tag, ptp, threshold_v)
                if keep.sum() < 3:
                    continue
                entry.setdefault("n_kept", {})[tag] = int(keep.sum())
                block = power[keep]
                for roi in ("frontal", "central", "posterior"):
                    for label, channels in (("", None),
                                            ("_published", PUBLISHED_ROIS[roi]),
                                            ("_subset", SUBSET_ROIS[roi])):
                        picks = [i for i, c in enumerate(names_all)
                                 if (_roi_of(c) == roi if channels is None
                                     else c in channels)]
                        if not picks:
                            continue
                        v = block[:, picks].mean(axis=1)
                        v = v[np.isfinite(v) & (v > 0)]
                        if v.size:
                            entry[f"logpower_{band}_{roi}{label}__{tag}"] = \
                                float(np.log(v).mean())
        out["conditions"][condition.value] = entry
        kept = entry.get("n_kept", {})
        say(f"  {condition.value:<15} {n_made} epochs, kept "
            + ", ".join(f"{tag}={kept[tag]}" for tag in REJECT_THRESHOLDS
                        if tag in kept))

    return out


#: Output directory. The corrected run writes somewhere new rather than over
#: the 8 s results: those took ~20 h of compute, they are what G1.2 attempt 3
#: was decided on, and keeping them makes the effect of the epoch-length
#: correction measurable instead of merely asserted.
VARIANT_DIR = "P1_published"


def derived_dir(config: dict) -> Path:
    base = Path(config["paths"]["derived"])
    base = base if base.is_absolute() else REPO_ROOT / base
    out = base / VARIANT_DIR
    out.mkdir(parents=True, exist_ok=True)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subject", type=int, default=None)
    parser.add_argument("--subjects", type=int, nargs=2, default=None,
                        metavar=("FIRST", "LAST"))
    parser.add_argument("--session", type=int, default=None)
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--force", action="store_true")
    parser.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB,
                        help="refuse to start a session below this much free RAM")
    parser.add_argument("--wait-hours", type=float, default=8.0,
                        help="how long to wait for memory before giving up "
                             "(default: %(default)s). A full sweep is ~10 h of "
                             "unattended compute on a machine someone is also "
                             "using, so the guard's 30 min default is too short: "
                             "any application the user opens for an evening kills "
                             "the worker and the sweep silently stops. Waiting is "
                             "free and the run is resumable either way.")
    args = parser.parse_args(argv)

    print(f"memory: {describe()}", flush=True)
    config = load_config()
    raw = raw_dir(config)
    out_dir = derived_dir(config)

    if args.subject:
        subjects = [args.subject]
    elif args.subjects:
        subjects = list(range(args.subjects[0], args.subjects[1] + 1))
    else:
        subjects = list(range(1, 30))
    sessions = [args.session] if args.session else [1, 2, 3]

    for subject in subjects:
        for session in sessions:
            target = out_dir / f"sub-{subject:02d}_ses-S{session}_power.json"
            if target.exists() and not args.force:
                print(f"=== sub-{subject:02d} ses-S{session} === done, skipping",
                      flush=True)
                continue
            print(f"=== sub-{subject:02d} ses-S{session} ===", flush=True)
            # Do not begin a session unless there is room for it. Allocating
            # into an already-short system is what produced the 0xFD bugcheck.
            require_free_memory(args.min_free_gb,
                                timeout_s=args.wait_hours * 3600.0,
                                label=f"sub-{subject:02d} ses-S{session}")
            started = time.time()
            result = preprocess_session_descriptive(
                raw, config, subject=subject, session=session,
                verbose=not args.quiet)
            result["elapsed_s"] = round(time.time() - started, 1)
            tmp = target.with_suffix(f".{os.getpid()}.tmp")
            tmp.write_text(json.dumps(result, indent=2), encoding="utf-8")
            os.replace(tmp, target)
            print(json.dumps({k: v for k, v in result.items() if k != "conditions"},
                             indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
