"""G1.3 — compute the divergence metrics per subject x task.

Reads `data/derived/P1/cells.csv` (G1.1) and writes
`data/derived/P1/divergence.csv`, one row per subject x task with D_subj,
D_beh, D_comp, the two robustness alternatives, and per-subject bootstrap CIs.

Nothing here depends on the EEG preprocessing variant: D_subj is built from
RSME and D_beh from behavioural performance. That is what makes G1.3
computable while G1.2's fork is still open — the metrics are needed under every
framing the mentor might choose, including a reproducibility paper.

Usage:
    python -m analyses.P1_divergence.divergence
    python -m analyses.P1_divergence.divergence --draws 5000
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
from scipy import stats

from analyses.P1_divergence.metrics import (
    FLAT_D,
    N_CELLS,
    bootstrap_ci,
    d_resid,
    d_slope,
    divergence,
    zscore,
)
from src.io.inventory import REPO_ROOT, load_config

CELLS = REPO_ROOT / "data" / "derived" / "P1" / "cells.csv"
OUT = REPO_ROOT / "data" / "derived" / "P1" / "divergence.csv"

TASKS = ("nback", "matb")

#: (column, higher_is_worse) for each measure D is computed on.
MEASURES = {
    "subj": ("rsme", False),
    "beh": ("performance", True),
}


def group_line(table: pd.DataFrame, task: str, column: str) -> tuple[float, float]:
    """Group-level intercept and slope of `column` on difficulty, for D_resid.

    Fitted once across all subjects so every subject is scored against the same
    reference line rather than against their own fit, which would make the
    residual measure nothing.
    """
    block = table[table.task == task][["difficulty", column]].dropna()
    if len(block) < 3:
        return (float("nan"), float("nan"))
    fit = stats.linregress(block.difficulty, block[column])
    return (float(fit.intercept), float(fit.slope))


def build(table: pd.DataFrame, n_draws: int, seed: int) -> pd.DataFrame:
    rows = []
    lines = {(t, col): group_line(table, t, col)
             for t in TASKS for col, _ in MEASURES.values()}

    for task in TASKS:
        for subject in sorted(table.subject.unique()):
            block = table[(table.task == task) & (table.subject == subject)]
            row = {"subject": int(subject), "task": task,
                   "n_cells": int(len(block))}

            for name, (column, higher_is_worse) in MEASURES.items():
                usable = block[["difficulty", column]].dropna()
                d = divergence(usable.difficulty.to_numpy(),
                               usable[column].to_numpy(),
                               higher_is_worse=higher_is_worse)
                # Seed per subject x measure so a CI is reproducible on its own
                # and does not depend on iteration order.
                lo, hi = bootstrap_ci(
                    usable.difficulty.to_numpy(), usable[column].to_numpy(),
                    higher_is_worse=higher_is_worse, n_draws=n_draws,
                    seed=seed + 1000 * int(subject) + hash(name) % 97)
                row[f"D_{name}"] = d
                row[f"D_{name}_lo"] = lo
                row[f"D_{name}_hi"] = hi
                row[f"n_{name}"] = int(len(usable))
                row[f"flat_{name}"] = bool(np.isfinite(d) and d == FLAT_D
                                           and len(usable) >= 3
                                           and usable[column].nunique() == 1)

            rsme = block[["difficulty", "rsme"]].dropna()
            row["D_slope"] = d_slope(rsme.difficulty.to_numpy(),
                                     rsme.rsme.to_numpy())
            intercept, slope = lines[(task, "rsme")]
            row["D_resid"] = d_resid(rsme.difficulty.to_numpy(),
                                     rsme.rsme.to_numpy(), intercept, slope)
            rows.append(row)

    frame = pd.DataFrame(rows)

    # D_comp is z-scored WITHIN task: the two tasks have different cell counts
    # and different behavioural indices, so pooling them before z-scoring would
    # let a task-level mean difference masquerade as subject divergence.
    frame["D_comp"] = np.nan
    for task in TASKS:
        mask = frame.task == task
        frame.loc[mask, "D_comp"] = np.nanmean(
            np.vstack([zscore(frame.loc[mask, "D_subj"].to_numpy()),
                       zscore(frame.loc[mask, "D_beh"].to_numpy())]), axis=0)
    return frame


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--draws", type=int, default=2000,
                        help="bootstrap draws per subject (default: %(default)s)")
    args = parser.parse_args(argv)

    config = load_config()
    seed = int(config.get("seeds", {}).get("bootstrap",
               config.get("seeds", {}).get("global", 0)))
    table = pd.read_csv(CELLS)
    print(f"=== G1.3 divergence metrics ===")
    print(f"cells: {len(table)} rows, seed={seed}, draws={args.draws}")

    frame = build(table, args.draws, seed)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT, index=False)

    print(f"\nrows: {len(frame)} (expected {len(TASKS) * table.subject.nunique()})")
    for task in TASKS:
        block = frame[frame.task == task]
        print(f"\n--- {task} ---")
        for name in ("D_subj", "D_beh", "D_comp", "D_slope", "D_resid"):
            values = block[name].dropna()
            if values.empty:
                print(f"  {name:<8} all missing")
                continue
            print(f"  {name:<8} median {values.median():6.3f}  "
                  f"IQR [{values.quantile(.25):.3f}, {values.quantile(.75):.3f}]  "
                  f"range [{values.min():.3f}, {values.max():.3f}]  n={len(values)}")
        incomplete = int((block.n_cells < N_CELLS).sum())
        print(f"  subjects with < {N_CELLS} cells: {incomplete}")
        for name in ("subj", "beh"):
            flat = int(block[f"flat_{name}"].sum())
            missing = int(block[f"D_{name}"].isna().sum())
            width = (block[f"D_{name}_hi"] - block[f"D_{name}_lo"]).median()
            print(f"  D_{name:<5} flat subjects: {flat}   undefined: {missing}   "
                  f"median CI width: {width:.3f}")

    # Do D_subj and D_beh agree? §1: disagreement is itself a finding.
    print("\n--- D_subj vs D_beh (§1: disagreement is a finding, not a bug) ---")
    for task in TASKS:
        block = frame[frame.task == task][["D_subj", "D_beh"]].dropna()
        if len(block) < 3:
            print(f"  {task}: too few complete subjects")
            continue
        r, p = stats.spearmanr(block.D_subj, block.D_beh)
        print(f"  {task:<6} Spearman rho={r:+.3f}  p={p:.3g}  n={len(block)}")

    print(f"\nwrote {OUT}")

    ok = len(frame) == len(TASKS) * table.subject.nunique()
    print(f"\nG1.3 row count: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


if __name__ == "__main__":
    raise SystemExit(main())
