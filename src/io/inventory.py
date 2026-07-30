"""COG-BCI inventory and integrity assertions (G0.2).

Walks `data/raw`, records one row per subject x session x in-scope condition,
and runs the assertions `gates.md` §G0.2 names. Writes
`outputs/tables/inventory.csv`.

Nothing here imputes or repairs. Missing cells are recorded and counted;
exclusion decisions belong in the preregistration (G-LOCK), not in a loader.

Usage:
    python -m src.io.inventory
    python -m src.io.inventory --subjects 1 2 3   # subset, for iteration
"""

from __future__ import annotations

import argparse
import sys
import warnings
from dataclasses import asdict, dataclass
from pathlib import Path

import numpy as np
import pandas as pd
import scipy.io
import yaml

from src.io.taskcodes import (
    BEHAVIOURAL_STEMS,
    EEG_STEMS,
    IN_SCOPE,
    RESTING_STEMS,
    Condition,
    assert_schemes_are_distinct,
    from_notebook,
)

REPO_ROOT = Path(__file__).resolve().parents[2]
N_SUBJECTS = 29
SESSIONS = (1, 2, 3)


class InventoryError(AssertionError):
    """A G0.2 assertion failed. Not recoverable by retrying."""


@dataclass
class Cell:
    subject: int
    session: int
    condition: str
    task: str
    difficulty: int
    eeg_set: bool
    eeg_fdt: bool
    behavioural: bool
    eeg_path: str


def load_config() -> dict:
    with open(REPO_ROOT / "config.yaml", encoding="utf-8") as fh:
        return yaml.safe_load(fh)


def raw_dir(config: dict) -> Path:
    p = Path(config["paths"]["raw"])
    return p if p.is_absolute() else REPO_ROOT / p


def find_ci(directory: Path, stem: str, suffix: str) -> Path | None:
    """Case-insensitive file lookup.

    The dataset mixes case within a single directory (RS_Beg_EC vs RS_End_Ec),
    so exact-case matching silently fails on Linux while passing on Windows.
    """
    if not directory.is_dir():
        return None
    want = f"{stem}{suffix}".lower()
    for path in directory.iterdir():
        if path.name.lower() == want:
            return path
    return None


# --------------------------------------------------------------------------
# notebook.mat


def parse_notebook(raw: Path) -> pd.DataFrame:
    """Task order and interruption flag per subject-session (G0.2)."""
    path = raw / "notebook.mat"
    if not path.exists():
        raise InventoryError(f"notebook.mat missing at {path}")

    mat = scipy.io.loadmat(path, struct_as_record=False, squeeze_me=True)
    notebook = mat["notebook"]

    rows = []
    for s in range(1, N_SUBJECTS + 1):
        subject = getattr(notebook, f"SBJ_{s}", None)
        if subject is None:
            raise InventoryError(f"notebook.mat has no SBJ_{s}")
        for ses in SESSIONS:
            sess = getattr(subject, f"SESS_{ses}", None)
            if sess is None:
                raise InventoryError(f"notebook.mat has no SBJ_{s}.SESS_{ses}")
            order = np.asarray(sess.Order).ravel().tolist()
            conditions = [from_notebook(c) for c in order]
            if set(conditions) != set(Condition):
                raise InventoryError(
                    f"sub-{s:02d} ses-S{ses}: task order {order} is not a "
                    "permutation of all eight conditions"
                )
            rows.append({
                "subject": s,
                "session": ses,
                "interrupted": bool(np.asarray(sess.interrupted).ravel()[0]),
                "order": "|".join(c.value for c in conditions),
            })
    return pd.DataFrame(rows)


def parse_triggerlist(raw: Path) -> pd.DataFrame:
    """Trigger code -> event mapping (G0.2)."""
    path = raw / "triggerlist.txt"
    if not path.exists():
        raise InventoryError(f"triggerlist.txt missing at {path}")
    df = pd.read_csv(path)
    if list(df.columns) != ["code", "content"]:
        raise InventoryError(f"unexpected triggerlist columns: {list(df.columns)}")
    if df["code"].duplicated().any():
        dupes = df.loc[df["code"].duplicated(), "code"].tolist()
        raise InventoryError(f"duplicate trigger codes: {dupes}")
    return df


# --------------------------------------------------------------------------
# channels


def channel_report(config: dict, raw: Path, subjects: list[int]) -> pd.DataFrame:
    """Per subject-session channel checks (G0.2).

    Reads headers only (`preload=False`), so this is cheap.
    """
    import mne

    mne.set_log_level("ERROR")
    reference = list(config["eeg"]["channels"])
    configured_ecg = config["eeg"]["ecg_channel"]

    rows = []
    for s in subjects:
        for ses in SESSIONS:
            eeg_dir = raw / f"sub-{s:02d}" / f"ses-S{ses}" / "eeg"
            probe = None
            for condition in IN_SCOPE:
                probe = find_ci(eeg_dir, EEG_STEMS[condition], ".set")
                if probe is not None:
                    break
            if probe is None:
                rows.append({
                    "subject": s, "session": ses, "readable": False,
                    "n_channels": None, "sfreq": None,
                    "missing_reference": None, "has_cz": None,
                    "configured_ecg_present": None, "ecg_typed": None,
                    "ecg_typed_as_eeg": None,
                })
                continue

            with warnings.catch_warnings():
                warnings.simplefilter("ignore")
                info = mne.io.read_raw_eeglab(probe, preload=False).info

            names = info["ch_names"]
            types = {ch: t for ch, t in
                     zip(names, [mne.io.pick.channel_type(info, i)
                                 for i in range(len(names))])}
            ecg_typed = [ch for ch, t in types.items() if t == "ecg"]
            ecg_named = [ch for ch in names if "ECG" in ch.upper()]
            mis_typed = [ch for ch in ecg_named if types[ch] == "eeg"]

            rows.append({
                "subject": s,
                "session": ses,
                "readable": True,
                "n_channels": len(names),
                "sfreq": info["sfreq"],
                "missing_reference": "|".join(c for c in reference if c not in names),
                "has_cz": "Cz" in names,
                "configured_ecg_present": configured_ecg in names,
                "ecg_typed": "|".join(ecg_typed),
                "ecg_typed_as_eeg": "|".join(mis_typed),
            })
    return pd.DataFrame(rows)


def assert_channels(report: pd.DataFrame, config: dict) -> list[str]:
    """Run the G0.2 channel assertions. Returns notes; raises on hard failures."""
    notes: list[str] = []
    readable = report[report["readable"]]
    if readable.empty:
        raise InventoryError("no readable EEG files found")

    # --- all 10 reference channels present, every subject-session
    bad = readable[readable["missing_reference"] != ""]
    if not bad.empty:
        detail = ", ".join(
            f"sub-{r.subject:02d} ses-S{r.session} missing {r.missing_reference}"
            for r in bad.itertuples()
        )
        raise InventoryError(f"reference channels missing: {detail}")
    notes.append(
        f"all 10 reference channels present in {len(readable)} subject-sessions"
    )

    # --- ECG must never be typed as EEG (dataset.md 7.3)
    mistyped = readable[readable["ecg_typed_as_eeg"] != ""]
    if not mistyped.empty:
        detail = ", ".join(
            f"sub-{r.subject:02d} ses-S{r.session}: {r.ecg_typed_as_eeg}"
            for r in mistyped.itertuples()
        )
        raise InventoryError(
            "ECG channel typed as EEG -- average reference would be corrupted: "
            + detail
        )
    no_ecg = readable[readable["ecg_typed"] == ""]
    if not no_ecg.empty:
        detail = ", ".join(
            f"sub-{r.subject:02d} ses-S{r.session}" for r in no_ecg.itertuples()
        )
        raise InventoryError(f"no ECG-typed channel found in: {detail}")
    found = sorted({n for v in readable["ecg_typed"] for n in v.split("|") if n})
    notes.append(f"ECG channel(s) present and typed 'ecg': {found}")

    # --- the configured ecg_channel must actually exist, or the pin is stale
    configured = config["eeg"]["ecg_channel"]
    if not readable["configured_ecg_present"].any():
        raise InventoryError(
            f"config.yaml eeg.ecg_channel is {configured!r}, which appears in no "
            f"recording. This release names the ECG channel {found}. A drop step "
            f"keyed on {configured!r} would silently remove nothing. Update "
            "config.yaml (and log it in deviations.md) before preprocessing."
        )

    # --- Cz: absent for participants 1-9 per dataset.md 7.1; verify, don't assume
    cz = readable.groupby("subject")["has_cz"].all()
    without = sorted(cz[~cz].index.tolist())
    notes.append(f"subjects without Cz: {without or 'none'}")
    notes.append(
        "Cz is not in the 10-channel reference subset, so its absence does not "
        "affect the baseline montage (verified above, not assumed)."
    )
    return notes


# --------------------------------------------------------------------------


def build_inventory(config: dict, subjects: list[int]) -> pd.DataFrame:
    raw = raw_dir(config)
    rows: list[Cell] = []
    for s in subjects:
        for ses in SESSIONS:
            session_dir = raw / f"sub-{s:02d}" / f"ses-S{ses}"
            eeg_dir, beh_dir = session_dir / "eeg", session_dir / "behavioral"
            for condition in IN_SCOPE:
                set_path = find_ci(eeg_dir, EEG_STEMS[condition], ".set")
                fdt_path = find_ci(eeg_dir, EEG_STEMS[condition], ".fdt")
                beh_path = find_ci(beh_dir, BEHAVIOURAL_STEMS[condition], ".mat")
                rows.append(Cell(
                    subject=s,
                    session=ses,
                    condition=condition.value,
                    task=condition.task.value,
                    difficulty=condition.difficulty,
                    eeg_set=set_path is not None,
                    eeg_fdt=fdt_path is not None,
                    behavioural=beh_path is not None,
                    eeg_path=str(set_path.relative_to(raw)) if set_path else "",
                ))
    return pd.DataFrame([asdict(r) for r in rows])


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subjects", type=int, nargs="+", default=None,
                        help="subset of subject numbers (default: all 29)")
    args = parser.parse_args(argv)

    config = load_config()
    raw = raw_dir(config)
    subjects = args.subjects or list(range(1, N_SUBJECTS + 1))

    print("=== G0.2 inventory ===")
    print(f"raw: {raw}\n")

    assert_schemes_are_distinct()
    print("[ok] condition numbering schemes verified distinct "
          "(notebook descending, questionnaire ascending)")

    present = sorted(int(p.name[4:]) for p in raw.glob("sub-*")
                     if p.is_dir() and p.name[4:].isdigit())
    missing_dirs = [s for s in range(1, N_SUBJECTS + 1) if s not in present]
    print(f"[{'ok' if not missing_dirs else '--'}] participant directories: "
          f"{len(present)}/{N_SUBJECTS}"
          + (f" -- missing {missing_dirs}" if missing_dirs else ""))

    nested = [p.name for p in raw.glob("sub-*")
              if p.is_dir() and not (p / "ses-S1").is_dir()]
    if nested:
        print(f"[!!] {len(nested)} directories are not normalised: {nested[:5]}...")
        print("     run: python -m src.io.download --normalise")
        return 1

    notebook = parse_notebook(raw)
    print(f"[ok] notebook.mat parsed: {len(notebook)} subject-sessions, "
          f"{int(notebook.interrupted.sum())} interrupted")

    triggers = parse_triggerlist(raw)
    print(f"[ok] triggerlist.txt parsed: {len(triggers)} codes")

    inventory = build_inventory(config, subjects)
    complete = inventory.eeg_set & inventory.eeg_fdt
    n_expected = len(inventory)
    n_missing = int((~complete).sum())
    rate = 100 * n_missing / n_expected if n_expected else 0.0

    print(f"\n[  ] EEG cells: {n_expected - n_missing}/{n_expected} complete "
          f"(.set + .fdt), missing rate {rate:.2f}% -- G0.2 KPI: < 5%")
    if n_missing:
        print("     missing cells:")
        for r in inventory[~complete].itertuples():
            what = []
            if not r.eeg_set:
                what.append(".set")
            if not r.eeg_fdt:
                what.append(".fdt")
            print(f"       sub-{r.subject:02d} ses-S{r.session} "
                  f"{r.condition} -- missing {'+'.join(what)}")

    beh_missing = int((~inventory.behavioural).sum())
    print(f"[  ] behavioural files: {n_expected - beh_missing}/{n_expected} present")

    print("\n--- channel checks ---")
    report = channel_report(config, raw, subjects)
    for note in assert_channels(report, config):
        print(f"[ok] {note}")

    out_dir = REPO_ROOT / "outputs" / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    inventory.to_csv(out_dir / "inventory.csv", index=False)
    notebook.to_csv(out_dir / "notebook_sessions.csv", index=False)
    report.to_csv(out_dir / "channel_report.csv", index=False)
    print(f"\nwrote {out_dir / 'inventory.csv'} ({len(inventory)} rows)")
    print(f"wrote {out_dir / 'notebook_sessions.csv'}")
    print(f"wrote {out_dir / 'channel_report.csv'}")

    passed = rate < 5.0 and not missing_dirs
    print(f"\nG0.2 file-completeness KPI: {'PASS' if passed else 'FAIL'}")
    return 0 if passed else 1


if __name__ == "__main__":
    raise SystemExit(main())
