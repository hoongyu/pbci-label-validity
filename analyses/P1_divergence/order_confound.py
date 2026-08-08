"""Is the N-Back alpha effect a time-on-task artefact rather than a load effect?

G1.2 Part B failed on one criterion: N-Back alpha tracks difficulty, where the
published analyses report no effect. Before that failure is taken to the mentor
as a fork, the most plausible way for it to be an artefact of *our* processing
or of the design has to be ruled out.

The candidate is time-on-task. Alpha rises with drowsiness and drifts over a
recording session. If harder N-Back blocks were systematically run later (or
earlier), a session-wide alpha drift would masquerade as a monotonic difficulty
effect -- and it would do so without touching theta, and without touching MATB
if that task's order differed. That is the only mechanism I could construct
that survives all three of the arguments already made against a pipeline bug.

`notebook.mat` records the actual presentation order of all 8 tasks for every
subject-session, so this is directly testable rather than a matter of argument.

Three tests, in increasing strength:

1. **Is difficulty confounded with position at all?** Kendall's tau between
   nominal difficulty and presentation position (1-8).
2. **Is there a time-on-task effect on alpha to begin with?** Regress
   subject-centred alpha on position. If alpha does not drift with position,
   there is no drift available to confound anything.
3. **Does the difficulty effect survive adjustment?** Refit the difficulty
   contrast on alpha residualised against position, within subject.

A "no" at step 1 means the confound cannot be systematic. A "no" at step 2 means
it does not exist. Step 3 is the direct test and is what gets reported.

Usage:
    python -m analyses.P1_divergence.order_confound
"""

from __future__ import annotations

import argparse

import numpy as np
import pandas as pd
import scipy.io
from scipy import stats

from analyses.P1_divergence.descriptive_partb import (
    POWER_DIR,
    load_power,
    measure_name,
)
from src.io.inventory import REPO_ROOT, load_config, raw_dir
from src.io.taskcodes import IN_SCOPE, NOTEBOOK_CODES

BANDS = ("alpha", "theta")
ROIS = ("frontal", "central", "posterior")


def load_order(raw) -> pd.DataFrame:
    """Presentation position (1-8) per subject x session x condition."""
    mat = scipy.io.loadmat(raw / "notebook.mat", struct_as_record=False,
                           squeeze_me=True)
    notebook = mat["notebook"]
    in_scope = {c.value for c in IN_SCOPE}
    rows = []
    for subject in range(1, 30):
        subject_struct = getattr(notebook, f"SBJ_{subject}", None)
        if subject_struct is None:
            continue
        for session in (1, 2, 3):
            session_struct = getattr(subject_struct, f"SESS_{session}", None)
            if session_struct is None:
                continue
            order = np.asarray(getattr(session_struct, "Order")).ravel()
            interrupted = int(np.asarray(getattr(session_struct, "interrupted", 0)))
            for position, code in enumerate(order, start=1):
                condition = NOTEBOOK_CODES.get(int(code))
                if condition is None or condition.value not in in_scope:
                    continue
                rows.append({"subject": subject, "session": session,
                             "condition": condition.value, "position": position,
                             "interrupted": interrupted})
    return pd.DataFrame(rows)


def within_subject_centre(frame: pd.DataFrame, column: str) -> pd.Series:
    return frame[column] - frame.groupby("subject")[column].transform("mean")


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--reject", default="none")
    parser.add_argument("--roi-set", default="full")
    args = parser.parse_args(argv)

    config = load_config()
    power, _ = load_power(POWER_DIR)
    order = load_order(raw_dir(config))
    table = power.merge(order, on=["subject", "session", "condition"], how="left")

    missing = int(table.position.isna().sum())
    print(f"merged: {len(table)} rows, position missing for {missing}")
    print(f"sessions flagged interrupted in notebook.mat: "
          f"{int(order.groupby(['subject', 'session']).interrupted.first().sum())}")

    # ---- test 1: is difficulty confounded with position?
    print("\n=== 1. difficulty vs presentation position ===")
    for task in ("nback", "matb"):
        block = table[table.task == task]
        tau, p = stats.kendalltau(block.difficulty, block.position)
        means = [block[block.difficulty == d].position.mean() for d in (0, 1, 2)]
        print(f"  {task:<6} mean position {means[0]:.2f} / {means[1]:.2f} / "
              f"{means[2]:.2f}   tau={tau:+.3f}  p={p:.3g}")

    # ---- test 2: does alpha drift with position at all?
    print(f"\n=== 2. time-on-task effect on band power "
          f"(reject={args.reject}, ROI={args.roi_set}) ===")
    print("  regression of subject-centred log power on position (1-8)")
    print(f"  {'task':<6} {'band':<6} {'roi':<10} {'slope/step':>11} {'p':>10}")
    drift = {}
    for task in ("nback", "matb"):
        for band in BANDS:
            for roi in ROIS:
                column = measure_name(band, roi, args.roi_set, args.reject)
                block = table[(table.task == task)][
                    ["subject", "position", "difficulty", column]].dropna()
                if block.empty:
                    continue
                y = within_subject_centre(block, column)
                res = stats.linregress(block.position, y)
                drift[(task, band, roi)] = res
                flag = " *" if res.pvalue < 0.05 else ""
                print(f"  {task:<6} {band:<6} {roi:<10} {res.slope:+11.5f} "
                      f"{res.pvalue:10.3g}{flag}")

    # ---- test 3: does the difficulty effect survive adjustment for position?
    print("\n=== 3. difficulty effect before vs after removing position ===")
    print("  paired t on the (hard - easy) within-subject contrast")
    print(f"  {'task':<6} {'band':<6} {'roi':<10} {'raw diff':>10} {'t':>7} "
          f"{'p':>10}  |  {'adj diff':>9} {'t':>7} {'p':>10}")
    for task in ("nback",):
        for band in BANDS:
            for roi in ROIS:
                column = measure_name(band, roi, args.roi_set, args.reject)
                block = table[table.task == task][
                    ["subject", "session", "position", "difficulty", column]].dropna()
                if block.empty:
                    continue
                # Residualise against position within subject, so any linear
                # drift over the session is removed before the contrast.
                y = within_subject_centre(block, column)
                fit = stats.linregress(block.position, y)
                block = block.assign(
                    raw=y, adj=y - (fit.intercept + fit.slope * block.position))

                out = []
                for col in ("raw", "adj"):
                    per = block.groupby(["subject", "difficulty"])[col].mean().unstack()
                    if not {0, 2}.issubset(per.columns):
                        out.append((np.nan, np.nan, np.nan))
                        continue
                    contrast = (per[2] - per[0]).dropna()
                    t, p = stats.ttest_1samp(contrast, 0.0)
                    out.append((contrast.mean(), t, p))
                (rd, rt, rp), (ad, at, ap) = out
                print(f"  {task:<6} {band:<6} {roi:<10} {rd:+10.4f} {rt:+7.2f} "
                      f"{rp:10.3g}  |  {ad:+9.4f} {at:+7.2f} {ap:10.3g}")

    # ---- how many subjects individually show the decline?
    print("\n=== 4. per-subject consistency of the N-Back alpha decline ===")
    for roi in ROIS:
        column = measure_name("alpha", roi, args.roi_set, args.reject)
        block = table[table.task == "nback"][
            ["subject", "difficulty", column]].dropna()
        per = block.groupby(["subject", "difficulty"])[column].mean().unstack()
        if not {0, 2}.issubset(per.columns):
            continue
        contrast = (per[2] - per[0]).dropna()
        n_down = int((contrast < 0).sum())
        print(f"  alpha {roi:<10} {n_down}/{len(contrast)} subjects show "
              f"2-back < 0-back   (sign test p="
              f"{stats.binomtest(n_down, len(contrast), 0.5).pvalue:.3g})")

    out_dir = REPO_ROOT / "outputs" / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    table.to_csv(out_dir / "G1.2_order_confound.csv", index=False)
    print(f"\nwrote {out_dir / 'G1.2_order_confound.csv'}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
