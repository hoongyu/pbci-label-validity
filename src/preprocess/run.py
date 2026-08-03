"""Run the preprocessing pipeline and persist derived data.

G0.3 runs this for a single subject-session as a smoke test. Later phases run
it across the dataset.

Derived data is written once and never edited in place (`SKILL.md` operating
rule 5) — rerunning overwrites the whole file for that subject-session.

Usage:
    python -m src.preprocess.run --subject 1 --session 1     # G0.3 smoke
    python -m src.preprocess.run                             # all subjects
"""

from __future__ import annotations

import argparse
import json
import os
import time
from pathlib import Path

import numpy as np

from src.io.inventory import load_config, raw_dir
from src.preprocess.pipeline import preprocess_session
from src.preprocess.resources import (
    DEFAULT_MIN_FREE_GB,
    describe,
    require_free_memory,
)
from src.preprocess.resources import (
    DEFAULT_MIN_FREE_GB,
    describe,
    require_free_memory,
)

REPO_ROOT = Path(__file__).resolve().parents[2]


def derived_dir(config: dict, phase: str) -> Path:
    base = Path(config["paths"]["derived"])
    base = base if base.is_absolute() else REPO_ROOT / base
    out = base / phase
    out.mkdir(parents=True, exist_ok=True)
    return out


def run_one(config: dict, subject: int, session: int, phase: str,
            verbose: bool = True) -> dict:
    raw = raw_dir(config)
    started = time.time()
    results = preprocess_session(raw, config, subject=subject,
                                 session=session, verbose=verbose)
    elapsed = time.time() - started

    payload, summary = {}, []
    for r in results:
        for band, cov in r.covariances.items():
            payload[f"{r.condition}__{band}"] = cov.astype(np.float64)
        summary.append(r.summary())

    # Write to a process-unique temp file, then rename. os.replace is atomic on
    # the same filesystem, so two workers racing on one subject-session can only
    # duplicate work -- never leave a half-written .npz that the skip-existing
    # check would later treat as complete.
    out = derived_dir(config, phase) / f"sub-{subject:02d}_ses-S{session}_cov.npz"
    # The temp name must itself end in .npz: np.savez_compressed silently
    # appends .npz to any path lacking it, so a name like "....npz.1234.tmp"
    # gets written as "....npz.1234.tmp.npz" and the rename then fails on a
    # file that was never created.
    tmp = out.with_name(f"{out.stem}.{os.getpid()}.tmp.npz")
    np.savez_compressed(tmp, **payload)
    os.replace(tmp, out)

    meta = {
        "subject": subject,
        "session": session,
        "elapsed_s": round(elapsed, 1),
        "n_conditions": len(results),
        "total_epochs": sum(r.n_epochs for r in results),
        "channels_interpolated_total": sum(r.n_channels_interpolated for r in results),
        "channels_interpolated_per_task": round(
            sum(r.n_channels_interpolated for r in results) / max(len(results), 1), 3),
        "ica_components": results[0].n_components if results else None,
        "ica_components_rejected": results[0].n_components_rejected if results else None,
        "ica_n_iter": results[0].n_iter if results else None,
        "ica_rejected_labels": results[0].rejected_labels if results else [],
        "ica_component_labels": results[0].component_labels if results else [],
        # paths.derived may legitimately sit outside the repo (config.yaml
        # allows pointing at another drive), in which case relative_to raises.
        "covariance_file": str(
            out.relative_to(REPO_ROOT) if out.is_relative_to(REPO_ROOT) else out
        ),
        "conditions": summary,
    }
    (out.with_suffix(".json")).write_text(json.dumps(meta, indent=2), encoding="utf-8")
    return meta


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--subject", type=int, default=None)
    parser.add_argument("--subjects", type=int, nargs=2, default=None,
                        metavar=("FIRST", "LAST"),
                        help="inclusive subject range; lets several workers "
                             "split the sweep. Safe to run concurrently -- "
                             "each subject-session is independent, seeds are "
                             "fixed, and outputs go to distinct files.")
    parser.add_argument("--session", type=int, default=None)
    parser.add_argument("--phase", default="P0")
    parser.add_argument("--quiet", action="store_true")
    parser.add_argument("--force", action="store_true",
                        help="recompute subject-sessions that already exist")
    parser.add_argument("--min-free-gb", type=float, default=DEFAULT_MIN_FREE_GB,
                        help="stop rather than start a session with less free "
                             "RAM than this (default: %(default)s)")
    args = parser.parse_args(argv)

    config = load_config()
    if args.subject:
        subjects = [args.subject]
    elif args.subjects:
        subjects = list(range(args.subjects[0], args.subjects[1] + 1))
    else:
        subjects = list(range(1, 30))
    sessions = [args.session] if args.session else [1, 2, 3]

    for subject in subjects:
        for session in sessions:
            out = (derived_dir(config, args.phase)
                   / f"sub-{subject:02d}_ses-S{session}_cov.npz")
            # Require the sidecar too: a worker killed between the two writes
            # would otherwise leave a session that looks complete but has no
            # metadata, and it would be skipped forever.
            if out.exists() and out.with_suffix(".json").exists() and not args.force:
                print(f"=== sub-{subject:02d} ses-S{session} === already done, "
                      "skipping", flush=True)
                continue
            print(f"=== sub-{subject:02d} ses-S{session} ===", flush=True)
            # Do not allocate into an already-short system: that is what
            # produced the 0xFD bugcheck on 2026-08-03.
            require_free_memory(args.min_free_gb,
                                label=f"sub-{subject:02d} ses-S{session}")
            meta = run_one(config, subject, session, args.phase,
                           verbose=not args.quiet)
            print(json.dumps({k: v for k, v in meta.items() if k != "conditions"},
                             indent=2), flush=True)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
