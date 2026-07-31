"""Preprocessing pipeline — the ML variant (G0.3).

`dataset.md` §7.6 and `pitfalls.md` #1: the published paper describes **two**
pipelines. The descriptive analyses clean the continuous signal and then epoch.
The machine-learning pipeline **epochs first, cleans each epoch, and disables
automatic epoch rejection**. Only the second reproduces the published
accuracies, and using the wrong one looks like a subtle bug rather than a
structural mismatch. This module implements the second, and never drops an
epoch.

Order implemented, in full:

    1. read .set/.fdt                       (ECG1 excluded -- pitfalls #5)
    2. resample to 250 Hz
    3. restore the Fpz reference channel, then full-rank average reference
    4. broadband filter for ICA                (1-45 Hz)
    5. EPOCH: 5 s non-overlapping, reject=None, no epoch is ever dropped
    6. bad-channel detection at 2 SD + interpolation
    7. ICA (extended Infomax) + ICLabel, reject eye/muscle/heart at >0.90
    8. per band [theta 4-8 | alpha 8-12]: filter, pick the 10-channel subset,
       compute one covariance matrix per epoch

Every numbered step is a knob for the G0.4 seven-step playbook
(`gates.md` §G0.4). Where a choice was interpretive rather than dictated by the
references, it is flagged INTERPRETIVE in a comment so the playbook has
somewhere to look.
"""

from __future__ import annotations

import warnings
from dataclasses import dataclass, field
from pathlib import Path

import numpy as np

REPO_ROOT = Path(__file__).resolve().parents[2]

#: Original recording reference (`dataset.md` §7.2). Restored before
#: average-referencing so the re-reference is full rank.
ORIGINAL_REFERENCE = "Fpz"

#: Decimation used when *fitting* ICA (never when applying it). Safe because
#: the signal is low-passed at 45 Hz before epoching: 250/2 = 125 Hz leaves
#: Nyquist at 62.5 Hz, above the passband, so nothing in the retained band is
#: lost. Set to 1 to fit at full rate if a G0.4 diagnostic calls for it.
ICA_FIT_DECIM = 2

#: ICLabel class names -> the config's short keys.
ICLABEL_CLASSES = {
    "eye blink": "eye",
    "muscle artifact": "muscle",
    "heart beat": "heart",
}


@dataclass
class PreprocessResult:
    subject: int
    session: int
    condition: str
    n_epochs: int
    n_channels_interpolated: int
    interpolated: list[str]
    n_components: int
    n_components_rejected: int
    rejected_labels: list[str] = field(default_factory=list)
    covariances: dict[str, np.ndarray] = field(default_factory=dict)
    sfreq: float = 0.0
    duration_s: float = 0.0

    def summary(self) -> dict:
        d = {k: v for k, v in self.__dict__.items() if k != "covariances"}
        d["cov_shapes"] = {b: list(c.shape) for b, c in self.covariances.items()}
        return d


def _place_reference_channel(inst, name: str) -> None:
    """Give a restored reference channel a real position.

    `mne.add_reference_channels` leaves `loc` as NaN. That NaN propagates into
    spherical-spline interpolation and into the topographies ICLabel
    classifies, so it must be filled. The standard_1005 position is rescaled to
    the mean head radius of the montage actually in the file, so the restored
    electrode sits on the same sphere as the measured ones rather than on the
    template's.
    """
    import mne

    idx = inst.ch_names.index(name)
    template = mne.channels.make_standard_montage("standard_1005")
    pos = template.get_positions()["ch_pos"][name]

    existing = np.array([
        ch["loc"][:3] for i, ch in enumerate(inst.info["chs"])
        if i != idx and np.isfinite(ch["loc"][:3]).all()
        and np.linalg.norm(ch["loc"][:3]) > 0
    ])
    if len(existing):
        radius = np.linalg.norm(existing, axis=1).mean()
        pos = pos / np.linalg.norm(pos) * radius
    inst.info["chs"][idx]["loc"][:3] = pos


def channel_statistic(epochs, statistic: str) -> tuple[np.ndarray, list[str]]:
    """Per-channel badness statistic, z-scored across channels.

    Two are offered because the references say "2 SD" without naming the
    measure, and the choice changes the flagged count by an order of magnitude:

    - ``log_variance``: log of mean per-epoch variance. Sensitive to both
      broken channels and to channels merely carrying strong ocular activity.
    - ``kurtosis``: the classic EEGLAB channel-rejection statistic
      (``pop_rejchan``). Ordinary EEG is near-Gaussian, so kurtosis is tight
      across good channels and spikes for genuinely defective ones -- it does
      not flag frontopolar channels simply for containing blinks.
    """
    data = epochs.get_data(picks="eeg", copy=False)            # (n_ep, n_ch, n_t)
    names = [epochs.ch_names[i] for i in range(data.shape[1])]

    if statistic == "log_variance":
        var = data.var(axis=2).mean(axis=0)
        var = np.where(var <= 0, np.finfo(float).tiny, var)
        value = np.log(var)
    elif statistic == "kurtosis":
        from scipy.stats import kurtosis as _kurt
        flat = data.transpose(1, 0, 2).reshape(data.shape[1], -1)
        value = _kurt(flat, axis=1, fisher=True, bias=False)
    else:
        raise ValueError(f"unknown bad-channel statistic: {statistic!r}")

    z = (value - value.mean()) / (value.std() or 1.0)
    return z, names


def _detect_bad_channels(epochs, sd: float, statistic: str = "kurtosis") -> list[str]:
    """Flag channels whose badness statistic deviates by more than `sd` SDs.

    INTERPRETIVE -- and the most consequential interpretive choice here. The
    references specify "automatic bad-channel rejection and interpolation
    (2 SD)" without naming the statistic; the published KPI is ~0.34 channels
    interpolated per task (`gates.md` §G0.3).

    Note that *any* pure z-threshold flags a roughly fixed fraction: |z| > 2 on
    62 near-normal values is ~3 channels by construction, an order of magnitude
    above 0.34. Matching the published rate therefore requires a statistic that
    is tight across good channels, not a tighter threshold. Kurtosis is such a
    statistic; log-variance is not, because frontopolar channels legitimately
    carry large ocular variance and get flagged for it -- and interpolating
    them would destroy the very signal ICLabel needs to find eye components.

    The threshold is applied per recording, not per epoch, because the
    published quantity is expressed *per task*.
    """
    z, names = channel_statistic(epochs, statistic)
    return [n for n, zi in zip(names, z) if abs(zi) > sd]


def prepare_epochs(set_path: Path, config: dict, *, verbose: bool = True):
    """Steps 1-6 for one task recording: everything up to (not incl.) ICA.

    Returns `(epochs, bads)`. ICA is deliberately *not* run here — it is fit
    once per subject-session over all of that session's recordings, per
    `analysis.md` §5 rule 1.
    """
    import mne

    mne.set_log_level("ERROR")

    eeg = config["eeg"]
    cleaning = config["cleaning"]
    sfreq_target = float(eeg["sfreq_target"])
    epoch_len = float(eeg["epoch_length_s"])

    def say(msg: str) -> None:
        if verbose:
            print(f"      {msg}", flush=True)

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        raw = mne.io.read_raw_eeglab(set_path, preload=True)

    # --- 1. ECG must never enter the average reference (pitfalls #5).
    ecg_name = eeg["ecg_channel"]
    drop = [ch for ch in raw.ch_names if ch == ecg_name or "ECG" in ch.upper()]
    if drop:
        raw.drop_channels(drop)
    say(f"dropped non-EEG: {drop or 'none'} -> {len(raw.ch_names)} EEG channels")

    # --- 2. resample
    raw.resample(sfreq_target)

    # --- 3. broadband filter for ICA. ICLabel was trained on 1-100 Hz data;
    # at 250 Hz the Nyquist is 125, so the top of that range is unavailable.
    # INTERPRETIVE: 1-45 Hz. Band-specific filtering happens at step 8.
    raw.filter(1.0, 45.0, fir_design="firwin")

    # --- 4. EPOCH FIRST. reject=None and no drop, per dataset.md §7.6.
    assert cleaning["epoch_rejection"] is False, (
        "config.yaml cleaning.epoch_rejection must be false -- the ML variant "
        "disables automatic epoch rejection (dataset.md §7.6, pitfalls #1)"
    )
    events = mne.make_fixed_length_events(raw, duration=epoch_len, overlap=0.0)
    epochs = mne.Epochs(
        raw, events, tmin=0.0, tmax=epoch_len, baseline=None,
        preload=True, reject=None, flat=None, reject_by_annotation=False,
    )
    n_epochs_made = len(epochs)
    say(f"epoched: {n_epochs_made} x {epoch_len}s, reject=None")

    # --- 5. bad channels at 2 SD, then interpolate. Before the average
    # reference, per the order in `gates.md` §G0.3, and before Fpz is restored
    # so that a reconstructed channel can never be flagged as a bad measured
    # one.
    bads = _detect_bad_channels(epochs, float(cleaning["bad_channel_sd"]))
    epochs.info["bads"] = bads
    if bads:
        epochs.interpolate_bads(reset_bads=True)
    say(f"interpolated {len(bads)} channel(s): {bads or 'none'}")

    # --- 6. restore Fpz, then full-rank average reference (dataset.md §7.2).
    # Average-referencing an N-channel montage costs one rank. Adding the
    # original reference back as an explicit zero channel first means the
    # re-reference is full rank, which is what the published pipeline does and
    # what ICA needs to decompose cleanly.
    #
    # add_reference_channels leaves the new channel's position as NaN, which
    # propagates into any spherical-spline interpolation and into the
    # topographies ICLabel classifies on. Fpz is therefore given its
    # standard_1005 position, rescaled to this montage's own head radius so it
    # sits on the same sphere as the measured electrodes.
    if ORIGINAL_REFERENCE not in epochs.ch_names:
        epochs = mne.add_reference_channels(epochs, ORIGINAL_REFERENCE)
        _place_reference_channel(epochs, ORIGINAL_REFERENCE)
    epochs.set_eeg_reference("average", projection=False)
    say(f"full-rank average reference incl. restored {ORIGINAL_REFERENCE}")

    assert len(epochs) == n_epochs_made, (
        f"epoch count changed from {n_epochs_made} to {len(epochs)} -- the ML "
        "variant must not drop epochs (dataset.md §7.6)"
    )
    return epochs, bads


def _covariances(epochs, config, subset: list[str]) -> dict[str, np.ndarray]:
    """One covariance matrix per epoch, per band, on the 10-channel subset."""
    import mne

    missing = [c for c in subset if c not in epochs.ch_names]
    if missing:
        raise RuntimeError(f"reference channels missing after cleaning: {missing}")

    # Pick the subset first, then filter the ndarray directly. Filtering via
    # Epochs.filter raises "Unable to avoid creating a copy while reshaping" on
    # this numpy/MNE combination once channels have been added and
    # interpolated; going through the array does the same thing on a smaller
    # matrix and sidesteps it.
    picked = epochs.copy().pick(subset)
    if picked.ch_names != subset:
        raise RuntimeError(
            f"channel order changed: expected {subset}, got {picked.ch_names}"
        )
    base = np.ascontiguousarray(picked.get_data(copy=True))
    sfreq = float(picked.info["sfreq"])

    out: dict[str, np.ndarray] = {}
    for band, (lo, hi) in config["bands"].items():
        filtered = mne.filter.filter_data(
            base.copy(), sfreq, float(lo), float(hi),
            fir_design="firwin", verbose=False,
        )
        centred = filtered - filtered.mean(axis=2, keepdims=True)
        out[band] = np.einsum("eit,ejt->eij", centred, centred) / (filtered.shape[2] - 1)
    return out


def preprocess_session(
    raw_root: Path,
    config: dict,
    *,
    subject: int,
    session: int,
    conditions=None,
    verbose: bool = True,
) -> list[PreprocessResult]:
    """Run the ML-variant pipeline over one subject-session.

    **One ICA per subject-session**, fit over that session's recordings
    concatenated, per `analysis.md` §5 rule 1 ("ICA is fit per subject-session,
    independently"). Bad-channel detection stays per recording, because the
    published KPI is expressed per *task*.

    Fitting ICA per recording instead would be both a leakage-rule violation
    and a KPI mismatch: the published figure is ~7 components rejected per
    participant-session, which only makes sense if one decomposition covers
    the session.
    """
    import mne
    from mne_icalabel import label_components
    from src.io.taskcodes import EEG_STEMS, IN_SCOPE

    mne.set_log_level("ERROR")
    conditions = list(conditions or IN_SCOPE)
    cleaning = config["cleaning"]
    reject_labels = set(cleaning["iclabel_reject"])
    threshold = float(cleaning["iclabel_threshold"])
    seed = int(config["seeds"]["ica"])
    subset = list(config["eeg"]["channels"])

    def say(msg: str) -> None:
        if verbose:
            print(msg, flush=True)

    eeg_dir = raw_root / f"sub-{subject:02d}" / f"ses-S{session}" / "eeg"
    per_condition, bads_by_condition = [], {}
    for condition in conditions:
        say(f"  {condition.value}")
        epochs, bads = prepare_epochs(
            eeg_dir / f"{EEG_STEMS[condition]}.set", config, verbose=verbose
        )
        per_condition.append((condition, epochs))
        bads_by_condition[condition.value] = bads

    # --- one ICA for the whole session
    counts = [len(e) for _, e in per_condition]
    combined = mne.concatenate_epochs([e for _, e in per_condition], verbose=False)
    rank = mne.compute_rank(combined, rank=None).get("eeg", len(combined.ch_names))
    n_components = max(1, min(rank, len(combined.ch_names) - 1))
    say(f"  session ICA: {sum(counts)} epochs, {n_components} components")

    ica = mne.preprocessing.ICA(
        n_components=n_components,
        method="infomax",
        fit_params=dict(extended=True),
        random_state=seed,
        max_iter="auto",
    )
    # Fit on every 2nd sample. The signal is low-passed at 45 Hz above, so
    # decimating 250 -> 125 Hz leaves Nyquist at 62.5 Hz and discards no
    # information in the retained band; it is a compute saving, not an
    # approximation. ICA is applied to the full-rate data regardless.
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        ica.fit(combined, decim=ICA_FIT_DECIM)
        labels = label_components(combined, ica, method="iclabel")

    probs = np.asarray(labels["y_pred_proba"]).ravel()
    names = list(labels["labels"])
    exclude, excluded_labels = [], []
    for idx, (name, prob) in enumerate(zip(names, probs)):
        if ICLABEL_CLASSES.get(name) in reject_labels and prob > threshold:
            exclude.append(idx)
            excluded_labels.append(f"{name}:{prob:.2f}")
    ica.exclude = exclude
    say(f"  rejected {len(exclude)} component(s): "
        f"{', '.join(excluded_labels) or 'none'}")

    # --- apply the session decomposition to each recording, then covariances
    results = []
    for condition, epochs in per_condition:
        n_before = len(epochs)
        with warnings.catch_warnings():
            warnings.simplefilter("ignore")
            ica.apply(epochs)
        assert len(epochs) == n_before, "ICA application must not drop epochs"
        covs = _covariances(epochs, config, subset)
        results.append(PreprocessResult(
            subject=subject,
            session=session,
            condition=condition.value,
            n_epochs=len(epochs),
            n_channels_interpolated=len(bads_by_condition[condition.value]),
            interpolated=bads_by_condition[condition.value],
            n_components=n_components,
            n_components_rejected=len(exclude),
            rejected_labels=excluded_labels,
            covariances=covs,
            sfreq=float(epochs.info["sfreq"]),
            duration_s=len(epochs) * float(config["eeg"]["epoch_length_s"]),
        ))
    return results
