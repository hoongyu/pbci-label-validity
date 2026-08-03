"""G1.2 — manipulation checks and anomaly confirmation (HARD STOP).

Part A replicates the published manipulation checks. Part B confirms the
anomaly the whole project rests on: that in N-Back, RSME, behaviour and cardiac
measures track difficulty while **theta and alpha power do not**.

Design: 3 (Session) x 3 (Difficulty) repeated-measures ANOVA per task, which is
what `dataset.md` §5 states the published analyses used.

Missing cells are handled by **listwise deletion of subjects**, not imputation:
a subject missing any cell for a task is dropped from that task's ANOVA, and
the retained n is reported. RM-ANOVA requires complete data, and imputing the
dependent variable of a manipulation check would manufacture the effect being
tested.

If Part B fails, this is a fork in the project rather than a bug — see
`gates.md` §G1.2. Do not proceed as though the anomaly held.
"""

from __future__ import annotations

import argparse
import warnings

import numpy as np
import pandas as pd
from statsmodels.stats.anova import AnovaRM

from src.io.inventory import REPO_ROOT, load_config

CELLS = REPO_ROOT / "data" / "derived" / "P1" / "cells.csv"

#: Published targets (`dataset.md` §6). Tolerance for the RSME F values is
#: +/-20% per `gates.md` §G1.2.
PUBLISHED_F = {
    ("nback", "rsme"): 55.56,
    ("matb", "rsme"): 92.73,
}
F_TOLERANCE = 0.20
ALPHA = 0.05


def complete_cases(table: pd.DataFrame, task: str, measure: str) -> pd.DataFrame:
    """Subjects with all 9 session x difficulty cells present for `measure`."""
    block = table[table.task == task][
        ["subject", "session", "difficulty", measure]
    ].dropna()
    counts = block.groupby("subject").size()
    keep = counts[counts == 9].index
    return block[block.subject.isin(keep)]


def rm_anova(table: pd.DataFrame, task: str, measure: str) -> dict:
    """3x3 RM-ANOVA; returns the difficulty and session effects."""
    block = complete_cases(table, task, measure)
    n = block.subject.nunique()
    if n < 3:
        return {"measure": measure, "task": task, "n": n, "error": "too few subjects"}

    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        fit = AnovaRM(block, depvar=measure, subject="subject",
                      within=["session", "difficulty"]).fit()
    anova = fit.anova_table

    out = {"task": task, "measure": measure, "n": n}
    for term, label in (("difficulty", "difficulty"), ("session", "session")):
        if term in anova.index:
            row = anova.loc[term]
            out[f"F_{label}"] = float(row["F Value"])
            out[f"df1_{label}"] = float(row["Num DF"])
            out[f"df2_{label}"] = float(row["Den DF"])
            out[f"p_{label}"] = float(row["Pr > F"])
    return out


def cell_means(table: pd.DataFrame, task: str, measure: str) -> list[float]:
    block = table[table.task == task]
    return [float(block[block.difficulty == d][measure].mean()) for d in (0, 1, 2)]


def report(results: list[dict], title: str) -> pd.DataFrame:
    frame = pd.DataFrame(results)
    print(f"\n=== {title} ===")
    cols = [c for c in ("task", "measure", "n", "F_difficulty", "df1_difficulty",
                        "df2_difficulty", "p_difficulty", "F_session", "p_session")
            if c in frame.columns]
    with pd.option_context("display.width", 200, "display.max_columns", 40):
        print(frame[cols].to_string(index=False,
                                    float_format=lambda v: f"{v:.4g}"))
    return frame


def main(argv: list[str] | None = None) -> int:
    argparse.ArgumentParser(description=__doc__.splitlines()[0]).parse_args(argv)
    load_config()
    table = pd.read_csv(CELLS)
    print(f"cells: {len(table)} rows")

    # ---------------- Part A: replication ----------------
    part_a = [
        rm_anova(table, "nback", "rsme"),
        rm_anova(table, "matb", "rsme"),
        rm_anova(table, "nback", "error_rate"),
        rm_anova(table, "matb", "track_rms"),
        rm_anova(table, "matb", "sysmon_rt_mean"),
    ]
    frame_a = report(part_a, "Part A — manipulation checks")

    checks_a = []
    for task in ("nback", "matb"):
        row = next(r for r in part_a if r["task"] == task and r["measure"] == "rsme")
        published = PUBLISHED_F[(task, "rsme")]
        f = row.get("F_difficulty", np.nan)
        lo, hi = published * (1 - F_TOLERANCE), published * (1 + F_TOLERANCE)
        ok = bool(np.isfinite(f) and lo <= f <= hi and row.get("p_difficulty", 1) < ALPHA)
        checks_a.append((f"{task} RSME x difficulty F within +/-20% of {published}",
                         ok, f"F={f:.2f}, accept {lo:.2f}-{hi:.2f}, "
                             f"p={row.get('p_difficulty', float('nan')):.2e}"))
    for task, measure, label in (("nback", "error_rate", "N-Back error rate"),
                                 ("matb", "track_rms", "MATB TRACK"),
                                 ("matb", "sysmon_rt_mean", "MATB SYSMON")):
        row = next(r for r in part_a if r["task"] == task and r["measure"] == measure)
        p = row.get("p_difficulty", 1.0)
        checks_a.append((f"{label} x difficulty significant", bool(p < ALPHA),
                         f"F={row.get('F_difficulty', float('nan')):.2f}, p={p:.2e}"))

    # ---------------- Part B: the anomaly ----------------
    power_measures = [f"logpower_{band}_{roi}"
                      for band in ("theta", "alpha")
                      for roi in ("frontal", "central", "posterior")]
    part_b = [rm_anova(table, task, m)
              for task in ("nback", "matb") for m in power_measures]
    frame_b = report(part_b, "Part B — EEG band power")

    def get(task, measure):
        return next(r for r in part_b if r["task"] == task and r["measure"] == measure)

    checks_b = []
    # N-Back: no difficulty effect on theta, any ROI
    nb_theta = [get("nback", f"logpower_theta_{r}") for r in ROIS_ORDER]
    worst = min(nb_theta, key=lambda r: r.get("p_difficulty", 1.0))
    checks_b.append(("N-Back: NO difficulty effect on theta",
                     all(r.get("p_difficulty", 1) >= ALPHA for r in nb_theta),
                     f"smallest p={worst.get('p_difficulty', float('nan')):.3f} "
                     f"({worst['measure'].split('_')[-1]})"))
    # N-Back: no difficulty or session effect on alpha
    nb_alpha = [get("nback", f"logpower_alpha_{r}") for r in ROIS_ORDER]
    worst_d = min(nb_alpha, key=lambda r: r.get("p_difficulty", 1.0))
    worst_s = min(nb_alpha, key=lambda r: r.get("p_session", 1.0))
    checks_b.append(("N-Back: NO difficulty effect on alpha",
                     all(r.get("p_difficulty", 1) >= ALPHA for r in nb_alpha),
                     f"smallest p={worst_d.get('p_difficulty', float('nan')):.3f} "
                     f"({worst_d['measure'].split('_')[-1]})"))
    checks_b.append(("N-Back: NO session effect on alpha",
                     all(r.get("p_session", 1) >= ALPHA for r in nb_alpha),
                     f"smallest p={worst_s.get('p_session', float('nan')):.3f} "
                     f"({worst_s['measure'].split('_')[-1]})"))
    # MATB: significant difficulty effect on frontal and posterior theta
    for roi in ("frontal", "posterior"):
        row = get("matb", f"logpower_theta_{roi}")
        checks_b.append((f"MATB: difficulty effect on {roi} theta",
                         bool(row.get("p_difficulty", 1) < ALPHA),
                         f"F={row.get('F_difficulty', float('nan')):.2f}, "
                         f"p={row.get('p_difficulty', float('nan')):.2e}"))
    # MATB: posterior alpha effect, opposite in sign to the conventional literature
    row = get("matb", "logpower_alpha_posterior")
    means = cell_means(table, "matb", "logpower_alpha_posterior")
    increases = means[2] > means[0]
    checks_b.append(("MATB: posterior alpha difficulty effect present",
                     bool(row.get("p_difficulty", 1) < ALPHA),
                     f"F={row.get('F_difficulty', float('nan')):.2f}, "
                     f"p={row.get('p_difficulty', float('nan')):.2e}"))
    checks_b.append(("MATB: posterior alpha INCREASES with difficulty "
                     "(opposite to convention)", bool(increases),
                     f"means {means[0]:.3f} -> {means[1]:.3f} -> {means[2]:.3f}"))

    # ---------------- verdict ----------------
    print("\n=== Part A verdict ===")
    for label, ok, detail in checks_a:
        print(f"  [{'OK ' if ok else 'FAIL'}] {label:<58} {detail}")
    print("\n=== Part B verdict ===")
    for label, ok, detail in checks_b:
        print(f"  [{'OK ' if ok else 'FAIL'}] {label:<58} {detail}")

    out_dir = REPO_ROOT / "outputs" / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    pd.concat([frame_a.assign(part="A"), frame_b.assign(part="B")]).to_csv(
        out_dir / "G1.2_manipulation_checks.csv", index=False)
    print(f"\nwrote {out_dir / 'G1.2_manipulation_checks.csv'}")

    a_ok = all(ok for _, ok, _ in checks_a)
    b_ok = all(ok for _, ok, _ in checks_b)
    print(f"\nPart A (replication): {'PASS' if a_ok else 'FAIL'}")
    print(f"Part B (anomaly)    : {'PASS' if b_ok else 'FAIL'}")
    print(f"\nG1.2: {'PASS' if a_ok and b_ok else 'FAIL'}")
    if not b_ok:
        print("\nPart B failing is a FORK, not a bug (gates.md §G1.2): it would mean\n"
              "the published EEG validation does not replicate. Stop and re-plan\n"
              "with the mentor before proceeding.")
    return 0 if (a_ok and b_ok) else 1


ROIS_ORDER = ("frontal", "central", "posterior")


if __name__ == "__main__":
    raise SystemExit(main())
