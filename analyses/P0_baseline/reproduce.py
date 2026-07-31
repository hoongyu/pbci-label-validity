"""G0.4 — reproduce the published within-subject decoding baseline.

Within-subject 5-fold CV, 3-class, Riemannian MDM on 10-channel covariances.

**Unit of analysis.** One accuracy per *subject x session x task x band*. This
is inferred from the published inferential statistics rather than assumed: the
paper reports a task effect F(1,28), a band effect F(1,28) and a session effect
F(2,56). With n = 29 subjects those degrees of freedom are exactly a
repeated-measures design over subjects with factors task (2), band (2) and
session (3) -- so accuracy must be computed within a session, not pooled across
them. The reported session means (64.30 / 70.30 / 66.96) confirm it.

Acceptance (`gates.md` §G0.4), all must hold:

    MATB    69.40% published, accept 66.40-72.40%
    N-Back  64.97% published, accept 61.97-67.97%

plus three directional criteria: alpha > theta, MATB > N-Back, session 2
highest of the three.

This is a HARD STOP. Do not widen the tolerance to pass.
"""

from __future__ import annotations

import argparse
import json
import re
from pathlib import Path

import numpy as np
import pandas as pd
from pyriemann.classification import MDM
from sklearn.model_selection import StratifiedKFold, cross_val_score

from src.io.inventory import load_config, REPO_ROOT
from src.io.taskcodes import IN_SCOPE, Condition

DERIVED_RE = re.compile(r"sub-(\d+)_ses-S(\d)_cov\.npz$")

PUBLISHED = {
    "matb": {"mean": 69.40, "lo": 66.40, "hi": 72.40},
    "nback": {"mean": 64.97, "lo": 61.97, "hi": 67.97},
}
CHANCE_CEILING = 41.7


def derived_files(config: dict, phase: str = "P0") -> list[Path]:
    base = Path(config["paths"]["derived"])
    base = base if base.is_absolute() else REPO_ROOT / base
    return sorted((base / phase).glob("sub-*_ses-S*_cov.npz"))


def score_cell(covs: np.ndarray, labels: np.ndarray, seed: int) -> dict:
    """5-fold stratified CV with Riemannian MDM.

    MDM computes its class means inside `fit`, so scikit-learn's CV machinery
    keeps them on training folds only -- no leakage across the split.
    """
    cv = StratifiedKFold(n_splits=5, shuffle=True, random_state=seed)
    scores = cross_val_score(MDM(), covs, labels, cv=cv, scoring="accuracy")
    balanced = cross_val_score(MDM(), covs, labels, cv=cv,
                               scoring="balanced_accuracy")
    return {
        "accuracy": float(scores.mean()) * 100,
        "accuracy_sd": float(scores.std()) * 100,
        "balanced_accuracy": float(balanced.mean()) * 100,
        "n_epochs": int(len(labels)),
        # labels are the ordinal difficulties 0/1/2, so bincount must not be
        # sliced -- doing so silently dropped the easiest class from the report
        "n_per_class": "|".join(str(int(c)) for c in np.bincount(labels)),
    }


def run(config: dict, phase: str = "P0", verbose: bool = True) -> pd.DataFrame:
    seed = int(config["seeds"]["cv_split"])
    bands = list(config["bands"].keys())
    by_task: dict[str, list[Condition]] = {}
    for condition in IN_SCOPE:
        by_task.setdefault(condition.task.value, []).append(condition)

    rows = []
    for path in derived_files(config, phase):
        match = DERIVED_RE.search(path.name)
        if not match:
            continue
        subject, session = int(match.group(1)), int(match.group(2))
        store = np.load(path)

        for task, conditions in by_task.items():
            for band in bands:
                covs, labels = [], []
                missing = False
                for condition in conditions:
                    key = f"{condition.value}__{band}"
                    if key not in store:
                        missing = True
                        break
                    block = store[key]
                    covs.append(block)
                    labels.append(np.full(len(block), condition.difficulty))
                if missing:
                    print(f"  skip sub-{subject:02d}/S{session} {task}/{band}"
                          " -- missing condition")
                    continue

                X = np.concatenate(covs, axis=0)
                y = np.concatenate(labels).astype(int)
                result = score_cell(X, y, seed)
                result.update(subject=subject, session=session, task=task,
                              band=band)
                rows.append(result)
                if verbose:
                    print(f"  sub-{subject:02d}/S{session} {task:<5} {band:<5} "
                          f"acc={result['accuracy']:5.2f}%  "
                          f"n={result['n_epochs']}", flush=True)

    return pd.DataFrame(rows)


def summarise(table: pd.DataFrame) -> dict:
    out: dict = {"n_cells": len(table), "n_subjects": table.subject.nunique()}
    for task in ("matb", "nback"):
        sub = table[table.task == task]
        if sub.empty:
            continue
        # marginal mean over band and session, averaged within subject first so
        # every subject weighs equally regardless of missing cells
        per_subject = sub.groupby("subject").accuracy.mean()
        out[task] = {
            "mean": float(per_subject.mean()),
            "sd": float(per_subject.std()),
            "published": PUBLISHED[task]["mean"],
            "window": [PUBLISHED[task]["lo"], PUBLISHED[task]["hi"]],
            "in_window": bool(PUBLISHED[task]["lo"] <= per_subject.mean()
                              <= PUBLISHED[task]["hi"]),
        }
    out["by_band"] = {b: float(g.accuracy.mean())
                      for b, g in table.groupby("band")}
    out["by_session"] = {int(s): float(g.accuracy.mean())
                         for s, g in table.groupby("session")}

    band = out["by_band"]
    sess = out["by_session"]
    out["directional"] = {
        "alpha_gt_theta": bool(band.get("alpha", 0) > band.get("theta", 0)),
        "matb_gt_nback": bool(out.get("matb", {}).get("mean", 0)
                              > out.get("nback", {}).get("mean", 0)),
        "session2_highest": bool(sess and max(sess, key=sess.get) == 2),
    }
    return out


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--phase", default="P0")
    parser.add_argument("--quiet", action="store_true")
    args = parser.parse_args(argv)

    config = load_config()
    print("=== G0.4 baseline reproduction ===")
    table = run(config, args.phase, verbose=not args.quiet)
    if table.empty:
        print("no derived covariance files found -- run src.preprocess.run first")
        return 1

    out_dir = REPO_ROOT / "outputs" / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "G0.4_baseline.csv", index=False)

    summary = summarise(table)
    print("\n" + json.dumps(summary, indent=2))

    print(f"\n{'task':<8}{'observed':>10}{'published':>11}{'window':>18}{'':>6}")
    ok = True
    for task in ("matb", "nback"):
        if task not in summary:
            continue
        s = summary[task]
        mark = "OK" if s["in_window"] else "OUT"
        ok &= s["in_window"]
        window = f"{s['window'][0]:.2f}-{s['window'][1]:.2f}%"
        print(f"{task:<8}{s['mean']:>9.2f}%{s['published']:>10.2f}%"
              f"{window:>18}{mark:>6}")
    for name, value in summary["directional"].items():
        print(f"  {name:<20} {'OK' if value else 'FAIL'}")
        ok &= value

    n_sub = summary["n_subjects"]
    print(f"\nsubjects processed: {n_sub}/29")
    if n_sub < 29:
        print("PRELIMINARY -- not a G0.4 verdict. The acceptance windows are "
              "defined on all 29 subjects.")
        return 0

    print(f"\nG0.4: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
