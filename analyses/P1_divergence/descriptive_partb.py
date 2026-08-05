"""G1.2 Part B, re-tested against the DESCRIPTIVE variant.

The first attempt at Part B failed. That failure was ruled invalid rather than
informative: the band power came from `src/preprocess/pipeline.py`, the
machine-learning variant, while the published N-Back anomaly is a result of the
**descriptive** pipeline (`dataset.md` §7.6). Testing a descriptive-variant
claim against ML-variant observations tests nothing.

This module re-runs the same checks against `src/preprocess/descriptive.py`
output. If the anomaly appears here, the first failure was a variant mismatch
and G1.2 passes. If it does not, the published EEG validation does not
replicate and this is the fork described in `gates.md` §G1.2.

Two parameters are unresolved by the references, so neither is chosen — the
whole test is run under every value and the conclusion is reported as stable or
unstable across them:

* **epoch rejection threshold** — `none` / `ptp150` / `ptp300`. The references
  give the outcome (~16 epochs/task) but not the criterion, and the peak-to-peak
  distribution itself shifts with MATB difficulty, so any fixed threshold
  discards the high-workload condition preferentially.
* **ROI channel set** — the full montage, or the 10-channel subset used by the
  decoding baseline. `dataset.md` does not name the channels.

A conclusion that holds under all six combinations is a property of the data. A
conclusion that flips is a property of my parameter choice, and must be reported
as such rather than resolved by picking the flattering one.

The statistics are deliberately imported from `manipulation_checks`, not
reimplemented: if this variant disagrees with the last one, the difference has
to be the pipeline.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path

import numpy as np
import pandas as pd

from analyses.P1_divergence.manipulation_checks import (
    ALPHA,
    ROIS_ORDER,
    cell_means,
    rm_anova,
)
from src.io.inventory import REPO_ROOT, load_config

POWER_DIR = REPO_ROOT / "data" / "derived" / "P1_descriptive"

#: condition -> (task, difficulty). Matches `cells.csv`, so the two variants'
#: tables are directly comparable.
CONDITIONS = {
    "zero_back": ("nback", 0),
    "one_back": ("nback", 1),
    "two_back": ("nback", 2),
    "matb_easy": ("matb", 0),
    "matb_medium": ("matb", 1),
    "matb_difficult": ("matb", 2),
}

THRESHOLDS = ("none", "ptp150", "ptp300")
ROI_SETS = {"full": "", "subset": "_subset"}
BANDS = ("theta", "alpha")

#: G1.2 attempt 1, ML variant, n=29 (`outputs/logs/G1.2_2026-08-02_attempt1.md`).
#: Kept here so the two variants can be compared on effect size rather than on
#: p values: this pilot has n=7, and F falls with n for a *fixed* effect, so a
#: criterion that flips from significant to null between the two runs may have
#: done so purely through lost power. Comparing partial eta-squared removes
#: that confound; comparing p values invites exactly the wrong conclusion.
ML_VARIANT_F = {
    ("nback", "theta", "frontal"): (1.47, 29),
    ("nback", "theta", "central"): (5.57, 29),
    ("nback", "theta", "posterior"): (4.15, 29),
    ("nback", "alpha", "frontal"): (15.76, 29),
    ("nback", "alpha", "central"): (26.83, 29),
    ("nback", "alpha", "posterior"): (28.62, 29),
}


def partial_eta_sq(f: float, n: int, df1: float = 2.0) -> float:
    """Partial eta-squared from F for a within-subject main effect.

    df_error = df1 * (n - 1), so eta_p^2 = F*df1 / (F*df1 + df2) reduces to
    F / (F + n - 1) and is independent of sample size.
    """
    if not np.isfinite(f) or n < 2:
        return float("nan")
    return float(f * df1 / (f * df1 + df1 * (n - 1)))


def load_power(directory: Path) -> tuple[pd.DataFrame, list[str]]:
    """One row per subject x session x condition, one column per measure."""
    rows, skipped = [], []
    for path in sorted(directory.glob("*_power.json")):
        payload = json.loads(path.read_text(encoding="utf-8"))
        for condition, entry in payload["conditions"].items():
            if condition not in CONDITIONS:
                continue
            task, difficulty = CONDITIONS[condition]
            row = {"subject": payload["subject"], "session": payload["session"],
                   "task": task, "condition": condition, "difficulty": difficulty}
            found = False
            for band in BANDS:
                for roi in ROIS_ORDER:
                    for roi_set, suffix in ROI_SETS.items():
                        for tag in THRESHOLDS:
                            key = f"logpower_{band}_{roi}{suffix}__{tag}"
                            if key in entry:
                                row[measure_name(band, roi, roi_set, tag)] = entry[key]
                                found = True
            if not found:
                # Written by the pre-multi-threshold version of descriptive.py.
                # Silently keeping it would mix two rejection criteria in one
                # ANOVA, so it is excluded and named in the report instead.
                skipped.append(f"sub-{payload['subject']:02d}_"
                               f"ses-S{payload['session']}")
                break
            rows.append(row)
    return pd.DataFrame(rows), sorted(set(skipped))


def measure_name(band: str, roi: str, roi_set: str, tag: str) -> str:
    return f"logpower_{band}_{roi}_{roi_set}_{tag}"


def anomaly_checks(table: pd.DataFrame, roi_set: str, tag: str) -> list[dict]:
    """The six Part B criteria, evaluated for one parameter combination."""
    def name(band: str, roi: str) -> str:
        return measure_name(band, roi, roi_set, tag)

    fits = {(task, band, roi): rm_anova(table, task, name(band, roi))
            for task in ("nback", "matb")
            for band in BANDS for roi in ROIS_ORDER}

    def p(task, band, roi, term="difficulty"):
        return fits[(task, band, roi)].get(f"p_{term}", np.nan)

    def f(task, band, roi, term="difficulty"):
        return fits[(task, band, roi)].get(f"F_{term}", np.nan)

    def worst(task, band, term="difficulty"):
        """ROI with the strongest effect -- a null claim must survive the
        strongest, not the average."""
        return min(ROIS_ORDER, key=lambda r: (p(task, band, r, term)
                                              if np.isfinite(p(task, band, r, term))
                                              else 1.0))

    checks = []

    # --- N-Back: the anomaly. Three null claims.
    for band in BANDS:
        w = worst("nback", band)
        ps = [p("nback", band, r) for r in ROIS_ORDER]
        ok = all(np.isfinite(v) and v >= ALPHA for v in ps)
        checks.append({"check": f"N-Back: NO difficulty effect on {band}", "ok": ok,
                       "detail": f"smallest p={p('nback', band, w):.3g} ({w}, "
                                 f"F={f('nback', band, w):.2f})"})
    w = worst("nback", "alpha", "session")
    ps = [p("nback", "alpha", r, "session") for r in ROIS_ORDER]
    checks.append({"check": "N-Back: NO session effect on alpha",
                   "ok": all(np.isfinite(v) and v >= ALPHA for v in ps),
                   "detail": f"smallest p={p('nback', 'alpha', w, 'session'):.3g} ({w})"})

    # --- MATB: the positive control. The same pipeline must still find effects
    # here, otherwise a null in N-Back is just an insensitive pipeline.
    for roi in ("frontal", "posterior"):
        checks.append({"check": f"MATB: difficulty effect on {roi} theta",
                       "ok": bool(np.isfinite(p("matb", "theta", roi))
                                  and p("matb", "theta", roi) < ALPHA),
                       "detail": f"F={f('matb', 'theta', roi):.2f}, "
                                 f"p={p('matb', 'theta', roi):.3g}"})
    checks.append({"check": "MATB: posterior alpha difficulty effect present",
                   "ok": bool(np.isfinite(p("matb", "alpha", "posterior"))
                              and p("matb", "alpha", "posterior") < ALPHA),
                   "detail": f"F={f('matb', 'alpha', 'posterior'):.2f}, "
                             f"p={p('matb', 'alpha', 'posterior'):.3g}"})
    means = cell_means(table, "matb", name("alpha", "posterior"))
    checks.append({"check": "MATB: posterior alpha INCREASES with difficulty",
                   "ok": bool(np.isfinite(means[2]) and np.isfinite(means[0])
                              and means[2] > means[0]),
                   "detail": f"{means[0]:.3f} -> {means[1]:.3f} -> {means[2]:.3f}"})

    for c in checks:
        c["roi_set"] = roi_set
        c["reject"] = tag
    return checks, fits


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--dir", type=Path, default=POWER_DIR)
    args = parser.parse_args(argv)
    load_config()

    table, skipped = load_power(args.dir)
    if table.empty:
        print(f"no usable power files in {args.dir}")
        return 1
    n_sessions = table.groupby(["subject", "session"]).ngroups
    print(f"{args.dir.name}: {n_sessions} subject-sessions, "
          f"{table.subject.nunique()} subjects, {len(table)} rows")
    if skipped:
        print(f"EXCLUDED (old single-threshold schema, must be recomputed): "
              f"{', '.join(skipped)}")

    all_checks, all_fits = [], []
    for roi_set in ROI_SETS:
        for tag in THRESHOLDS:
            checks, fits = anomaly_checks(table, roi_set, tag)
            all_checks.extend(checks)
            for (task, band, roi), fit in fits.items():
                all_fits.append({**fit, "task": task, "band": band, "roi": roi,
                                 "roi_set": roi_set, "reject": tag})

    frame = pd.DataFrame(all_checks)

    # --- per-combination verdicts
    for roi_set in ROI_SETS:
        for tag in THRESHOLDS:
            block = frame[(frame.roi_set == roi_set) & (frame.reject == tag)]
            passed = bool(block.ok.all())
            print(f"\n=== ROI={roi_set}  reject={tag}  "
                  f"-> {'ANOMALY REPRODUCED' if passed else 'NOT REPRODUCED'} ===")
            for _, r in block.iterrows():
                print(f"  [{'OK  ' if r.ok else 'FAIL'}] {r['check']:<52} {r.detail}")

    # --- stability across the two undetermined parameters
    print("\n=== stability across parameters ===")
    pivot = frame.pivot_table(index="check", columns=["roi_set", "reject"],
                              values="ok", aggfunc="first")
    with pd.option_context("display.width", 200, "display.max_columns", 20):
        print(pivot.to_string())
    # --- power check: is a "pass" a real null, or just a small sample?
    #
    # Every N-Back criterion is a NULL claim, and this pilot has n=7 against the
    # published n=29. A null at n=7 is weak evidence by construction. Comparing
    # effect sizes against the ML-variant run separates "the descriptive variant
    # removed the effect" from "n=7 could not detect it".
    print("\n=== effect size vs the ML variant (N-Back) ===")
    print("partial eta^2 is sample-size free; F is not. A criterion that now")
    print("passes but whose effect size did NOT fall is an underpowered null.")
    fits = pd.DataFrame(all_fits)
    rows = []
    for (task, band, roi), (f_ml, n_ml) in ML_VARIANT_F.items():
        block = fits[(fits.task == task) & (fits.band == band) & (fits.roi == roi)
                     & (fits.roi_set == "full") & (fits.reject == "none")]
        if block.empty:
            continue
        f_desc = float(block.iloc[0]["F_difficulty"])
        n_desc = int(block.iloc[0]["n"])
        eta_ml = partial_eta_sq(f_ml, n_ml)
        eta_desc = partial_eta_sq(f_desc, n_desc)
        rows.append({"measure": f"{band} {roi}", "F_ML": f_ml, "n_ML": n_ml,
                     "eta2_ML": eta_ml, "F_desc": f_desc, "n_desc": n_desc,
                     "eta2_desc": eta_desc,
                     "verdict": "effect shrank" if eta_desc < eta_ml * 0.6
                     else ("effect grew" if eta_desc > eta_ml * 1.4
                           else "effect unchanged")})
    comparison = pd.DataFrame(rows)
    with pd.option_context("display.width", 200):
        print(comparison.to_string(index=False, float_format=lambda v: f"{v:.3f}"))
    comparison.to_csv(REPO_ROOT / "outputs" / "tables" /
                      "G1.2_partB_effectsize_vs_ML.csv", index=False)

    unstable = [c for c in pivot.index if pivot.loc[c].nunique() > 1]
    if unstable:
        print("\nPARAMETER-DEPENDENT (conclusion is not a property of the data):")
        for c in unstable:
            print(f"  - {c}")
    else:
        print("\nEvery criterion gives the same answer under all 6 combinations.")

    out_dir = REPO_ROOT / "outputs" / "tables"
    out_dir.mkdir(parents=True, exist_ok=True)
    frame.to_csv(out_dir / "G1.2_partB_descriptive_checks.csv", index=False)
    pd.DataFrame(all_fits).to_csv(
        out_dir / "G1.2_partB_descriptive_anova.csv", index=False)
    print(f"\nwrote {out_dir / 'G1.2_partB_descriptive_checks.csv'}")

    n_pass = sum(bool(frame[(frame.roi_set == rs) & (frame.reject == t)].ok.all())
                 for rs in ROI_SETS for t in THRESHOLDS)
    print(f"\nPart B (descriptive variant): {n_pass}/6 combinations reproduce "
          "the anomaly")
    return 0 if n_pass == 6 else 1


if __name__ == "__main__":
    raise SystemExit(main())
