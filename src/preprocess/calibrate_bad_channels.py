"""Calibrate the bad-channel threshold against the published rate (G0.3).

`config.yaml`'s `bad_channel_sd` and the ~0.34 channels/task KPI in
`gates.md` §G0.3 cannot both hold under a z-threshold reading: on 62 channels,
|z| > 2 flags ≈ 5% ≈ 3 channels by construction. This script measures the
achieved rate as a function of statistic and threshold so the choice is made
from data and is reproducible, rather than eyeballed.

**This is calibration against a target, and that is a deviation.** It is
recorded in `deviations.md`. Two things limit the circularity:

- Calibration uses a *subset* of subjects (default 1–10), not the whole
  dataset, so the threshold is not fitted to the data it will be judged on.
- The quantity calibrated is a preprocessing nuisance parameter, fixed before
  any decoding is run, and it is not adjusted again afterwards.

Usage:
    python -m src.preprocess.calibrate_bad_channels --subjects 1 10
"""

from __future__ import annotations

import argparse
import warnings
from pathlib import Path

import numpy as np
import pandas as pd

from src.io.inventory import load_config, raw_dir, REPO_ROOT
from src.io.taskcodes import EEG_STEMS, IN_SCOPE
from src.preprocess.pipeline import channel_statistic

PUBLISHED_RATE = 0.34
STATISTICS = ("log_variance", "kurtosis")
THRESHOLDS = np.round(np.arange(2.0, 8.01, 0.25), 2)


def collect(config: dict, subjects: range, session: int) -> dict[str, list[np.ndarray]]:
    import mne

    mne.set_log_level("ERROR")
    raw_root = raw_dir(config)
    sfreq = float(config["eeg"]["sfreq_target"])
    epoch_len = float(config["eeg"]["epoch_length_s"])

    out: dict[str, list[np.ndarray]] = {s: [] for s in STATISTICS}
    for subject in subjects:
        for condition in IN_SCOPE:
            path = (raw_root / f"sub-{subject:02d}" / f"ses-S{session}" / "eeg"
                    / f"{EEG_STEMS[condition]}.set")
            if not path.exists():
                print(f"  skip missing {path.name} for sub-{subject:02d}")
                continue
            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                raw = mne.io.read_raw_eeglab(path, preload=True)
                raw.drop_channels([c for c in raw.ch_names if "ECG" in c.upper()])
                raw.resample(sfreq)
                raw.filter(1.0, 45.0, fir_design="firwin")
                events = mne.make_fixed_length_events(raw, duration=epoch_len,
                                                      overlap=0.0)
                epochs = mne.Epochs(raw, events, tmin=0.0, tmax=epoch_len,
                                    baseline=None, preload=True, reject=None)
            for statistic in STATISTICS:
                out[statistic].append(channel_statistic(epochs, statistic)[0])
        print(f"  sub-{subject:02d} done "
              f"({len(out['kurtosis'])} recordings so far)", flush=True)
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subjects", type=int, nargs=2, default=[1, 10],
                        metavar=("FIRST", "LAST"))
    parser.add_argument("--session", type=int, default=1)
    args = parser.parse_args(argv)

    config = load_config()
    subjects = range(args.subjects[0], args.subjects[1] + 1)
    print(f"calibrating on sub-{subjects.start:02d}..sub-{subjects.stop - 1:02d}, "
          f"ses-S{args.session}")

    z_by_statistic = collect(config, subjects, args.session)
    n = len(z_by_statistic["kurtosis"])

    rows = []
    for statistic, zs in z_by_statistic.items():
        for threshold in THRESHOLDS:
            rate = float(np.mean([(np.abs(z) > threshold).sum() for z in zs]))
            rows.append({"statistic": statistic, "threshold": float(threshold),
                         "channels_per_task": rate,
                         "abs_error": abs(rate - PUBLISHED_RATE)})
    table = pd.DataFrame(rows)

    out_dir = REPO_ROOT / "outputs" / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "G0.3_bad_channel_calibration.csv", index=False)

    print(f"\n{n} recordings. Published target: {PUBLISHED_RATE} channels/task\n")
    for statistic in STATISTICS:
        sub = table[table.statistic == statistic].sort_values("abs_error")
        best = sub.iloc[0]
        print(f"{statistic:>14}: best threshold {best.threshold:.2f} SD "
              f"-> {best.channels_per_task:.3f} channels/task "
              f"(error {best.abs_error:.3f})")
    print(f"\nwrote {out_dir / 'G0.3_bad_channel_calibration.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
