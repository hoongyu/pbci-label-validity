"""G1.4 — variance decomposition of RSME (H1b).

`analysis.md` §2 specifies, per task:

    RSME ~ 1 + difficulty + (1 + difficulty | subject) + (1 | session)

and requires the variance components with bootstrap 95% CIs (subject-level
resampling, >= 2000 draws, seed from config.yaml), plus the subject ICC.

**The subject x difficulty slope variance is H1b** and is the project's
load-bearing quantity (`gates.md` §G1.4):

    CI excludes zero -> H1b supported, proceed to G-LOCK
    CI includes zero -> H2 and H2b have no basis; do not preregister them,
                        and take the documented pivot instead

Two implementation notes that matter for whether the number means anything:

* **The model is crossed, not nested.** subject and session are separate
  grouping factors -- every subject sees all three sessions. statsmodels'
  natural idiom (`groups=subject`) can only nest, which would estimate
  session-within-subject and answer a different question. The crossed form is
  built with a single dummy group and explicit variance components, which is
  the documented statsmodels approach for crossed effects.
* **A variance is bounded below by zero**, so a percentile CI can never exclude
  zero from below, and the usual "CI excludes zero" phrasing needs care. The
  decision rule is therefore applied to the *lower* bound: H1b is supported
  when the lower bound is meaningfully above zero. `LOWER_BOUND_TOL` makes the
  threshold explicit rather than letting floating-point noise decide.

Usage:
    python -m analyses.P1_divergence.variance
    python -m analyses.P1_divergence.variance --draws 2000
    python -m analyses.P1_divergence.variance --simulate   # validate the fitter
"""

from __future__ import annotations

import argparse
import warnings

import numpy as np
import pandas as pd
import statsmodels.formula.api as smf

from src.io.inventory import REPO_ROOT, load_config

CELLS = REPO_ROOT / "data" / "derived" / "P1" / "cells.csv"
OUT = REPO_ROOT / "outputs" / "tables" / "G1.4_variance_components.csv"

TASKS = ("nback", "matb")

#: A variance estimate below this counts as zero. Chosen relative to RSME's
#: scale (0-130 mm), so this is ~0.008% of the outcome variance -- small enough
#: to be numerical noise, large enough that a boundary estimate is not read as
#: a real effect.
LOWER_BOUND_TOL = 1e-4


def fit_components(frame: pd.DataFrame) -> dict:
    """Fit the crossed model and return the variance components.

    Returns NaNs rather than raising if the fit fails to converge: a bootstrap
    draw that cannot be fitted must not abort the whole run, and the caller
    reports how many draws were lost.
    """
    data = frame.dropna(subset=["rsme", "difficulty", "subject", "session"]).copy()
    if data.subject.nunique() < 3:
        return {k: np.nan for k in
                ("subject_intercept", "subject_slope", "session", "residual",
                 "icc_subject", "beta_difficulty")}

    data["subject"] = data.subject.astype(str)
    data["session"] = data.session.astype(str)
    data["grp"] = 1

    # Crossed random effects via one dummy group plus explicit components.
    # "0 + C(x)" gives one i.i.d. random effect per level of x, sharing a single
    # variance -- which is exactly a random intercept for that factor.
    vc = {
        "subject_intercept": "0 + C(subject)",
        "subject_slope": "0 + C(subject):difficulty",
        "session": "0 + C(session)",
    }
    with warnings.catch_warnings():
        warnings.simplefilter("ignore")
        try:
            model = smf.mixedlm("rsme ~ 1 + difficulty", data, groups=data["grp"],
                                vc_formula=vc, re_formula="0")
            fit = model.fit(reml=True, method="lbfgs", maxiter=200)
        except Exception:
            return {k: np.nan for k in
                    ("subject_intercept", "subject_slope", "session", "residual",
                     "icc_subject", "beta_difficulty")}

    scale = float(fit.scale)
    # `fit.vcomp` is ALREADY in the outcome's variance units here -- do not
    # rescale by `fit.scale`. The docs describe variance parameters as being in
    # units of the residual variance, which is true of `cov_re` but not of
    # `vcomp` as returned by this version; multiplying inflated every component
    # by a factor of `scale` (~40x on this data) while leaving the residual
    # correct, which is invisible in the output and fatal to the H1b decision.
    # Caught by `--simulate`; that check is the reason this line is right.
    names = list(model.exog_vc.names) if hasattr(model, "exog_vc") else list(vc)
    comps = {name: float(v) for name, v in zip(names, fit.vcomp)}

    subject_intercept = comps.get("subject_intercept", np.nan)
    subject_slope = comps.get("subject_slope", np.nan)
    session = comps.get("session", np.nan)
    total = subject_intercept + subject_slope + session + scale
    return {
        "subject_intercept": subject_intercept,
        "subject_slope": subject_slope,
        "session": session,
        "residual": scale,
        "icc_subject": subject_intercept / total if total > 0 else np.nan,
        "beta_difficulty": float(fit.fe_params.get("difficulty", np.nan)),
    }


def bootstrap(frame: pd.DataFrame, n_draws: int, seed: int) -> pd.DataFrame:
    """Subject-level resampling: draw subjects with replacement, refit.

    Resampling subjects rather than rows is what makes the CI a statement about
    the population of people, which is what H1b is about.
    """
    subjects = np.asarray(sorted(frame.subject.unique()))
    rng = np.random.default_rng(seed)
    rows = []
    for b in range(n_draws):
        picked = rng.choice(subjects, size=subjects.size, replace=True)
        parts = []
        for new_id, old_id in enumerate(picked):
            block = frame[frame.subject == old_id].copy()
            # Relabel: the same subject drawn twice must act as two people, or
            # the resample silently halves the effective subject count.
            block["subject"] = f"b{new_id}"
            parts.append(block)
        rows.append(fit_components(pd.concat(parts, ignore_index=True)))
        if (b + 1) % 100 == 0:
            print(f"    {b + 1}/{n_draws} draws", flush=True)
    return pd.DataFrame(rows)


def simulate_check(seed: int = 0) -> int:
    """Recover known variance components from synthetic data.

    The crossed-effects idiom above is easy to get subtly wrong -- a nested fit
    returns plausible numbers for the wrong model, and nothing in the output
    says so. This generates data with variances the fitter has never seen and
    checks the estimates land near them.
    """
    rng = np.random.default_rng(seed)
    true = {"subject_intercept": 100.0, "subject_slope": 25.0,
            "session": 16.0, "residual": 36.0}
    n_subjects = 60

    rows = []
    session_effect = rng.normal(0, np.sqrt(true["session"]), size=3)
    for s in range(n_subjects):
        intercept = rng.normal(0, np.sqrt(true["subject_intercept"]))
        slope = rng.normal(0, np.sqrt(true["subject_slope"]))
        for session in range(3):
            for difficulty in (0, 1, 2):
                rows.append({
                    "subject": s, "session": session, "difficulty": difficulty,
                    "rsme": (50.0 + 10.0 * difficulty + intercept
                             + slope * difficulty + session_effect[session]
                             + rng.normal(0, np.sqrt(true["residual"]))),
                })
    got = fit_components(pd.DataFrame(rows))

    print("=== fitter validation on synthetic data (n=60 subjects) ===")
    print(f"  {'component':<20}{'true':>10}{'estimated':>12}{'ratio':>9}")
    ok = True
    for name, value in true.items():
        estimate = got[name]
        ratio = estimate / value if value else np.nan
        # Session has only 3 levels, so its variance is barely identified --
        # judged loosely on purpose. The two subject components are what H1b
        # depends on and are held to +/-40%.
        tol = (0.2, 5.0) if name == "session" else (0.6, 1.4)
        good = tol[0] <= ratio <= tol[1]
        ok &= good
        print(f"  {name:<20}{value:10.1f}{estimate:12.2f}{ratio:9.2f}"
              f"   {'ok' if good else 'OUT OF RANGE'}")
    print(f"  fixed slope           true 10.0  estimated "
          f"{got['beta_difficulty']:.2f}")
    ok &= abs(got["beta_difficulty"] - 10.0) < 2.0

    # A zero-slope-variance world must come back at (or near) zero, or the
    # decision rule can never fire in the direction of the pivot.
    rows0 = []
    for s in range(n_subjects):
        intercept = rng.normal(0, 10.0)
        for session in range(3):
            for difficulty in (0, 1, 2):
                rows0.append({"subject": s, "session": session,
                              "difficulty": difficulty,
                              "rsme": 50.0 + 10.0 * difficulty + intercept
                                      + rng.normal(0, 6.0)})
    null = fit_components(pd.DataFrame(rows0))
    print(f"\n  zero-slope-variance control: subject_slope = "
          f"{null['subject_slope']:.4f}  (should be ~0)")
    ok &= null["subject_slope"] < 2.0

    print(f"\nfitter validation: {'PASS' if ok else 'FAIL'}")
    return 0 if ok else 1


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description=__doc__.splitlines()[0])
    parser.add_argument("--draws", type=int, default=2000)
    parser.add_argument("--simulate", action="store_true",
                        help="validate the fitter against known variances and exit")
    args = parser.parse_args(argv)

    config = load_config()
    seed = int(config.get("seeds", {}).get("bootstrap", 0))
    if args.simulate:
        return simulate_check(seed)

    table = pd.read_csv(CELLS)
    print("=== G1.4 variance decomposition (H1b) ===")
    print(f"cells: {len(table)} rows, seed={seed}, draws={args.draws}")

    results = []
    for task in TASKS:
        block = table[table.task == task]
        print(f"\n--- {task}: point estimate ---")
        point = fit_components(block)
        for name, value in point.items():
            print(f"  {name:<20} {value:12.4f}")

        print(f"--- {task}: bootstrap ({args.draws} subject-level draws) ---",
              flush=True)
        draws = bootstrap(block, args.draws, seed)
        failed = int(draws.subject_slope.isna().sum())
        print(f"  draws that failed to converge: {failed}/{args.draws}")

        for name in ("subject_intercept", "subject_slope", "session",
                     "residual", "icc_subject"):
            values = draws[name].dropna()
            lo, hi = (np.percentile(values, [2.5, 97.5])
                      if len(values) > 10 else (np.nan, np.nan))
            results.append({"task": task, "component": name,
                            "estimate": point[name], "ci_lo": lo, "ci_hi": hi,
                            "n_draws_ok": len(values), "n_draws": args.draws})

    frame = pd.DataFrame(results)
    OUT.parent.mkdir(parents=True, exist_ok=True)
    frame.to_csv(OUT, index=False)

    print("\n=== variance components ===")
    with pd.option_context("display.width", 200):
        print(frame.to_string(index=False, float_format=lambda v: f"{v:.4f}"))

    print("\n=== H1b decision (gates.md §G1.4) ===")
    verdicts = {}
    for task in TASKS:
        row = frame[(frame.task == task) & (frame.component == "subject_slope")]
        if row.empty:
            continue
        row = row.iloc[0]
        supported = bool(row.ci_lo > LOWER_BOUND_TOL)
        verdicts[task] = supported
        print(f"  {task:<6} subject x difficulty slope variance = "
              f"{row.estimate:.4f}  95% CI [{row.ci_lo:.4f}, {row.ci_hi:.4f}]"
              f"   -> H1b {'SUPPORTED' if supported else 'NOT supported'}")

    if all(verdicts.values()):
        print("\n  Both tasks support H1b. Per gates.md: proceed to G-LOCK.")
    elif not any(verdicts.values()):
        print("\n  Neither task supports H1b. Per gates.md §G1.4: H2 and H2b have\n"
              "  NO BASIS and must not be preregistered. Take the documented\n"
              "  pivot and re-plan with the mentor.")
    else:
        print("\n  Tasks disagree. This is not covered by the decision rule as\n"
              "  written and is a question for the mentor, not something to\n"
              "  resolve by picking the task that agrees with the hypothesis.")
    print(f"\nwrote {OUT}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
