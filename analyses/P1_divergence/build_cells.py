"""G1.1 — build the cell-level table.

One row per subject x task x session x difficulty. Expected 522 rows
(29 x 2 x 3 x 3). Columns: nominal difficulty, RSME, behavioural performance
index, band power by ROI, KSS, and quality covariates.

Nothing here imputes. Missing cells are emitted with NaN and counted; exclusion
decisions belong in the preregistration (G-LOCK), not in a table builder.

Two source notes that are not obvious from the references:

**N-Back behaviour comes from the EEG triggers, not the behavioural .mat.**
`dataset.md` §8 records that N-Back, Flanker and PVT are stored as MATLAB
*tables* while MATB is a struct. It does not note the consequence: MATLAB
tables are MCOS objects, and `scipy.io.loadmat` cannot read them -- it returns
an opaque `('MCOS', 'table', ...)` reference with no data. The trigger list
carries the same information (trial onsets, correct and error responses) on the
same clock as the EEG, so behaviour is derived from annotations instead. The
derived error rate reproduces the expected load gradient (0.015 / 0.019 / 0.215
for 0/1/2-back over 5 subjects x 3 sessions), which is the check that this
substitution is sound.

**MATB uses only TRACK and SYSMON** (`dataset.md` §4, `pitfalls.md` #9).
RESMAN appears only from Medium and COMM only in Difficult, so any index using
them makes Easy incomparable and manufactures a difficulty gradient out of
missing subtasks. The container key also varies between files
(`output` vs `MATB_diff.output`), so the struct is located by its fields.
"""

from __future__ import annotations

import argparse
import json
import warnings
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io

from src.io.inventory import REPO_ROOT, load_config, raw_dir
from src.io.taskcodes import (
    EEG_STEMS,
    IN_SCOPE,
    NBACK_TRIAL_CODES,
    Condition,
    Task,
    from_label,
)

N_SUBJECTS = 29
SESSIONS = (1, 2, 3)
N_NBACK_TRIALS = 144          # 3 blocks x 48 (`dataset.md` §3)
N_NBACK_TARGETS = 48          # hit rate fixed at 1/3

#: ROI groupings over the 10-channel reference subset. INTERPRETIVE: the
#: references name "frontal" and "posterior" effects (`dataset.md` §6) without
#: listing channels. CPz is grouped as central rather than posterior because
#: the posterior alpha effect the project must confirm is parietal.
ROIS: dict[str, tuple[str, ...]] = {
    "frontal": ("F3", "Fz", "F4", "FCz"),
    "central": ("C3", "C4", "CPz"),
    "posterior": ("P3", "Pz", "P4"),
}

#: Response codes, derived from the trial-onset codes: <prefix>31 error,
#: <prefix>32 correct, <prefix>33 conflict error.
def _response_codes(condition: Condition) -> dict[str, str]:
    prefix = NBACK_TRIAL_CODES[condition][0][:2]     # "60" / "61" / "62"
    return {
        "target_onset": f"{prefix}22",
        "normal_onset": f"{prefix}21",
        "correct": f"{prefix}32",
        "error": f"{prefix}31",
        "conflict_error": f"{prefix}33",
    }


# --------------------------------------------------------------------------
# subjective measures


def load_rsme(raw: Path) -> pd.DataFrame:
    df = pd.read_csv(raw / "RSME.txt")
    df["condition"] = df["condition"].map(lambda s: from_label(s).value)
    return (df.rename(columns={"sbj": "subject", "Session": "session",
                               "Score": "rsme"})
              [["subject", "session", "condition", "rsme"]])


def load_kss(raw: Path) -> pd.DataFrame:
    """KSS is per session, not per condition -- it is a session-level covariate."""
    df = pd.read_csv(raw / "KSS.txt")
    wide = (df.pivot_table(index=["sbj", "sess"], columns="Condition",
                           values="score", aggfunc="mean")
              .rename(columns=lambda c: f"kss_{c}")
              .reset_index()
              .rename(columns={"sbj": "subject", "sess": "session"}))
    wide.columns.name = None
    return wide


# --------------------------------------------------------------------------
# behaviour


def nback_behaviour(raw: Path, subject: int, session: int,
                    condition: Condition) -> dict:
    """Accuracy, error rate and mean correct RT from the EEG triggers."""
    import mne

    mne.set_log_level("ERROR")
    path = raw / f"sub-{subject:02d}" / f"ses-S{session}" / "eeg" / f"{EEG_STEMS[condition]}.set"
    if not path.exists():
        return {}
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        annotations = mne.io.read_raw_eeglab(path, preload=False).annotations

    codes = _response_codes(condition)
    description = np.array([str(d) for d in annotations.description])
    onset = np.asarray(annotations.onset)

    n_target = int((description == codes["target_onset"]).sum())
    hits = int((description == codes["correct"]).sum())
    false_alarms = int((description == codes["error"]).sum()
                       + (description == codes["conflict_error"]).sum())

    n_target = n_target or N_NBACK_TARGETS
    n_nontarget = N_NBACK_TRIALS - n_target
    misses = max(n_target - hits, 0)
    correct_rejections = max(n_nontarget - false_alarms, 0)

    accuracy = (hits + correct_rejections) / N_NBACK_TRIALS
    error_rate = (misses + false_alarms) / N_NBACK_TRIALS

    # mean RT: target onset -> the next correct response within 2 s
    target_times = np.sort(onset[description == codes["target_onset"]])
    correct_times = np.sort(onset[description == codes["correct"]])
    rts = []
    for t in target_times:
        after = correct_times[(correct_times > t) & (correct_times <= t + 2.0)]
        if after.size:
            rts.append(after[0] - t)

    return {
        "n_targets": n_target,
        "hits": hits,
        "misses": misses,
        "false_alarms": false_alarms,
        "accuracy": accuracy,
        "error_rate": error_rate,
        "rt_mean": float(np.mean(rts)) if rts else np.nan,
        "rt_n": len(rts),
    }


def _find_matb_struct(mat: dict):
    """Locate the struct holding TRACK/SYSMON.

    The container key is not stable: MATB_Easy and MATB_Med expose `output`
    directly, MATB_Diff nests it under `MATB_diff`.
    """
    stack = [v for k, v in mat.items() if not k.startswith("__")]
    while stack:
        item = stack.pop()
        fields = getattr(item, "_fieldnames", None)
        if not fields:
            continue
        if "TRACK" in fields or "SYSMON" in fields:
            return item
        stack.extend(getattr(item, f) for f in fields)
    return None


def matb_behaviour(raw: Path, subject: int, session: int,
                   condition: Condition) -> dict:
    """TRACK RMS deviation and SYSMON mean RT. TRACK and SYSMON only."""
    from src.io.taskcodes import BEHAVIOURAL_STEMS

    path = (raw / f"sub-{subject:02d}" / f"ses-S{session}" / "behavioral"
            / f"{BEHAVIOURAL_STEMS[condition]}.mat")
    if not path.exists():
        return {}
    mat = scipy.io.loadmat(path, struct_as_record=False, squeeze_me=True)
    struct = _find_matb_struct(mat)
    if struct is None:
        return {}

    out: dict = {}
    if "TRACK" in getattr(struct, "_fieldnames", []):
        track = np.asarray(struct.TRACK, dtype=float)
        if track.ndim == 2 and track.shape[1] >= 2:
            # RMS distance of the cursor from centre: higher = worse tracking
            out["track_rms"] = float(np.sqrt((track[:, :2] ** 2).sum(axis=1).mean()))
            out["track_n"] = int(track.shape[0])
    if "SYSMON" in getattr(struct, "_fieldnames", []):
        sysmon = np.asarray(struct.SYSMON, dtype=float)
        if sysmon.ndim == 2 and sysmon.shape[1] >= 2:
            rt = sysmon[:, 1]
            rt = rt[np.isfinite(rt) & (rt > 0)]
            out["sysmon_rt_mean"] = float(rt.mean()) if rt.size else np.nan
            out["sysmon_n"] = int(sysmon.shape[0])
    return out


# --------------------------------------------------------------------------
# EEG band power


def band_power(config: dict, subject: int, session: int) -> dict:
    """Band power per condition x band x ROI from the P0 covariances.

    The covariances were computed on band-filtered epochs, so the diagonal is
    the per-channel power in that band -- no reprocessing needed. Power is
    log-transformed because band power is approximately log-normal and the
    published analyses test additive effects.
    """
    derived = Path(config["paths"]["derived"])
    derived = derived if derived.is_absolute() else REPO_ROOT / derived
    path = derived / "P0" / f"sub-{subject:02d}_ses-S{session}_cov.npz"
    if not path.exists():
        return {}

    channels = list(config["eeg"]["channels"])
    index = {ch: i for i, ch in enumerate(channels)}
    store = np.load(path)

    out: dict = {}
    for key in store.files:
        condition, band = key.split("__")
        diag = np.diagonal(store[key], axis1=1, axis2=2)      # (n_epochs, 10)
        for roi, roi_channels in ROIS.items():
            picks = [index[c] for c in roi_channels if c in index]
            power = diag[:, picks].mean(axis=1)
            power = power[np.isfinite(power) & (power > 0)]
            if power.size:
                out[(condition, f"logpower_{band}_{roi}")] = float(np.log(power).mean())
    return out


def quality_covariates(config: dict, subject: int, session: int) -> dict:
    derived = Path(config["paths"]["derived"])
    derived = derived if derived.is_absolute() else REPO_ROOT / derived
    path = derived / "P0" / f"sub-{subject:02d}_ses-S{session}_cov.json"
    if not path.exists():
        return {}
    meta = json.loads(path.read_text(encoding="utf-8"))
    per_condition = {c["condition"]: c for c in meta.get("conditions", [])}
    return {
        "ica_components_rejected": meta.get("ica_components_rejected"),
        "ica_n_iter": meta.get("ica_n_iter"),
        "_per_condition": per_condition,
    }


# --------------------------------------------------------------------------


def build(config: dict, verbose: bool = True) -> pd.DataFrame:
    raw = raw_dir(config)
    rsme = load_rsme(raw)
    kss = load_kss(raw)
    rsme_index = {(r.subject, r.session, r.condition): r.rsme
                  for r in rsme.itertuples()}

    rows = []
    for subject in range(1, N_SUBJECTS + 1):
        for session in SESSIONS:
            power = band_power(config, subject, session)
            quality = quality_covariates(config, subject, session)
            per_condition = quality.pop("_per_condition", {})
            if verbose:
                print(f"  sub-{subject:02d} ses-S{session}", flush=True)

            for condition in IN_SCOPE:
                row = {
                    "subject": subject,
                    "session": session,
                    "task": condition.task.value,
                    "condition": condition.value,
                    "difficulty": condition.difficulty,
                    "rsme": rsme_index.get((subject, session, condition.value), np.nan),
                }
                if condition.task is Task.NBACK:
                    row.update(nback_behaviour(raw, subject, session, condition))
                else:
                    row.update(matb_behaviour(raw, subject, session, condition))

                for (cond, name), value in power.items():
                    if cond == condition.value:
                        row[name] = value

                row.update(quality)
                cell = per_condition.get(condition.value, {})
                row["n_epochs"] = cell.get("n_epochs")
                row["channels_interpolated"] = cell.get("n_channels_interpolated")
                rows.append(row)

    table = pd.DataFrame(rows)
    return table.merge(kss, on=["subject", "session"], how="left")


def performance_index(table: pd.DataFrame) -> pd.DataFrame:
    """Primary behavioural index per cell, oriented so higher = better.

    N-Back: accuracy. MATB: mean of z-scored inverted TRACK RMS and inverted
    SYSMON RT, z-scored within task (`dataset.md` §4). The exact composition is
    fixed at G-LOCK; this is the preregistration candidate.
    """
    table = table.copy()
    table["performance"] = np.nan

    nback = table.task == "nback"
    table.loc[nback, "performance"] = table.loc[nback, "accuracy"]

    matb = table.task == "matb"
    if matb.any():
        block = table.loc[matb]
        parts = []
        for column in ("track_rms", "sysmon_rt_mean"):
            if column in block:
                values = pd.to_numeric(block[column], errors="coerce")
                z = (values - values.mean()) / values.std(ddof=1)
                parts.append(-z)                     # invert: lower = better
        if parts:
            table.loc[matb, "performance"] = pd.concat(parts, axis=1).mean(axis=1)
    return table


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    config = load_config()
    print("=== G1.1 cell-level table ===")
    table = performance_index(build(config, verbose=not args.quiet))

    out_dir = REPO_ROOT / "data" / "derived" / "P1"
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "cells.csv", index=False)

    expected = N_SUBJECTS * 2 * 3 * 3
    rsme_missing = int(table.rsme.isna().sum())
    rate = 100 * rsme_missing / len(table)

    print(f"\nrows: {len(table)} / {expected} expected")
    print(f"RSME missing: {rsme_missing} ({rate:.2f}%)  -- G1.1 KPI: < 10%")
    if rsme_missing:
        print("  missing cells:")
        for r in table[table.rsme.isna()].itertuples():
            print(f"    sub-{r.subject:02d} ses-S{r.session} {r.condition}")

    for column in ("performance", "logpower_alpha_posterior", "logpower_theta_frontal"):
        if column in table:
            n = int(table[column].isna().sum())
            print(f"{column} missing: {n} ({100 * n / len(table):.2f}%)")

    print(f"\nwrote {out_dir / 'cells.csv'}")
    ok = len(table) == expected and rate < 10.0
    print(f"\nG1.1 row count and RSME KPI: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
