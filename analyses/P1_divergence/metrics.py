"""Divergence metrics (G1.3), defined exactly as `analysis.md` §1.

The central construct of the project: how far a subject's *experience* of
difficulty departs from the nominal difficulty label the experimenter assigned.

    D_subj[i,t] = 1 - tau_b(nominal_difficulty, RSME)      PRIMARY
    D_beh [i,t] = 1 - tau_b(nominal_difficulty, -performance)   SECONDARY
    D_comp      = mean of z-scored D_subj and D_beh        EXPLORATORY ONLY
    D_slope     = within-subject OLS slope of z(RSME) on difficulty  robustness
    D_resid     = RMS residual from the group difficulty->RSME model  robustness

Range of D is [0, 2]: 0 = perfect rank agreement, 1 = no association, 2 =
perfect inversion.

Three points from `analysis.md` §1 that the code has to honour and that are easy
to get wrong:

* **tau-b, not tau-a, and not a slope.** RSME is a 150 mm analogue line; people
  use analogue scales with wildly different ranges and anchoring. A slope
  conflates "the manipulation did not move them" with "they use a compressed
  range". Ties are expected, hence tau-b.
* **Nine cells, not three.** Session is a replicate, not something to average
  over: averaging would remove the within-subject noise that is the quantity
  being measured.
* **D_beh is sign-oriented.** The performance index is oriented higher = better
  (`build_cells.performance_index`), so perfect agreement with difficulty is
  tau = -1, not +1. Negating performance puts D_beh on the same scale as
  D_subj, where 0 means "tracks the label perfectly".

**D = 0 is unattainable in practice, and this must not be read past.** tau-b's
denominator is sqrt((n0-n1)(n0-n2)), which penalises a *mismatch* in tie
structure, not just a mismatch in ordering. Nominal difficulty always has three
ties of three. A subject whose nine values are perfectly ordered across
difficulty levels but differ within a level therefore scores tau_b = 0.866, so
D = 0.134 -- not 0. Since §1 deliberately keeps session as a replicate rather
than averaging over it, *every* real subject has within-level variation, so the
whole observed D distribution sits above zero. Anything compared against 0 (a
threshold, an effect size, a "perfect tracking" reference) inherits that offset.
Pinned by `test_d_zero_is_unreachable_once_cells_differ_within_a_difficulty`.

**INTERPRETIVE, must be confirmed at G-LOCK.** A subject whose RSME is constant
across all nine cells makes tau-b undefined (zero variance in one margin).
`FLAT_D` maps that case to 1.0 — "no association" — on the reasoning that a
subject who gave the same answer nine times did respond, and their response
carries no rank information about difficulty. The alternative reading is that
the metric is undefined and the subject should be excluded. The choice changes
which subjects enter H2, so it is preregistered rather than decided here; the
count of affected subjects is reported by the runner.
"""

from __future__ import annotations

import numpy as np
from scipy import stats

#: D for a subject with no variance in the dependent measure. See module note.
FLAT_D = 1.0

#: Cells expected per subject x task: 3 difficulties x 3 sessions.
N_CELLS = 9


def _has_variance(values: np.ndarray) -> bool:
    finite = values[np.isfinite(values)]
    return finite.size > 1 and not np.allclose(finite, finite[0])


def divergence(difficulty: np.ndarray, measure: np.ndarray, *,
               higher_is_worse: bool = False) -> float:
    """1 - tau_b between nominal difficulty and `measure`.

    `higher_is_worse=True` negates the measure first, for indices oriented so
    that a higher value means better performance. Returns NaN when there are
    too few usable cells, and FLAT_D when the measure has no variance.
    """
    difficulty = np.asarray(difficulty, dtype=float)
    measure = np.asarray(measure, dtype=float)
    keep = np.isfinite(difficulty) & np.isfinite(measure)
    difficulty, measure = difficulty[keep], measure[keep]
    if difficulty.size < 3:
        return float("nan")
    if higher_is_worse:
        measure = -measure
    # A constant margin makes tau_b's denominator zero; scipy returns NaN.
    # Distinguish that from missing data, which stays NaN.
    if not _has_variance(measure) or not _has_variance(difficulty):
        return FLAT_D
    tau = stats.kendalltau(difficulty, measure, variant="b").statistic
    if not np.isfinite(tau):
        return FLAT_D
    return float(1.0 - tau)


def bootstrap_ci(difficulty: np.ndarray, measure: np.ndarray, *,
                 higher_is_worse: bool = False, n_draws: int = 2000,
                 alpha: float = 0.05, seed: int = 0) -> tuple[float, float]:
    """Percentile CI for `divergence`, resampling the nine cells.

    Nine points is thin for a rank statistic -- `analysis.md` §1 requires this
    uncertainty to be reported per subject and propagated into H2 rather than
    treating each D as a point estimate.
    """
    difficulty = np.asarray(difficulty, dtype=float)
    measure = np.asarray(measure, dtype=float)
    keep = np.isfinite(difficulty) & np.isfinite(measure)
    difficulty, measure = difficulty[keep], measure[keep]
    if difficulty.size < 3:
        return (float("nan"), float("nan"))

    rng = np.random.default_rng(seed)
    n = difficulty.size
    draws = np.empty(n_draws, dtype=float)
    for b in range(n_draws):
        idx = rng.integers(0, n, size=n)
        draws[b] = divergence(difficulty[idx], measure[idx],
                              higher_is_worse=higher_is_worse)
    draws = draws[np.isfinite(draws)]
    if draws.size == 0:
        return (float("nan"), float("nan"))
    lo, hi = np.percentile(draws, [100 * alpha / 2, 100 * (1 - alpha / 2)])
    return (float(lo), float(hi))


def d_slope(difficulty: np.ndarray, measure: np.ndarray) -> float:
    """Within-subject OLS slope of the z-scored measure on difficulty.

    Robustness alternative to D_subj. z-scoring is within subject, so this
    still removes each person's overall level, but -- unlike tau-b -- it does
    not remove differences in how much of the scale they use. That is exactly
    the property that makes it a *check* on D_subj rather than a replacement.
    """
    difficulty = np.asarray(difficulty, dtype=float)
    measure = np.asarray(measure, dtype=float)
    keep = np.isfinite(difficulty) & np.isfinite(measure)
    difficulty, measure = difficulty[keep], measure[keep]
    if difficulty.size < 3 or not _has_variance(measure) or not _has_variance(difficulty):
        return float("nan")
    z = (measure - measure.mean()) / measure.std(ddof=1)
    return float(stats.linregress(difficulty, z).slope)


def d_resid(difficulty: np.ndarray, measure: np.ndarray,
            group_intercept: float, group_slope: float) -> float:
    """RMS residual of a subject around the GROUP difficulty->measure model.

    Robustness alternative capturing "this subject is noisy about the label"
    rather than "this subject ranks the label differently". The group
    coefficients are passed in so every subject is scored against the same
    reference line.
    """
    difficulty = np.asarray(difficulty, dtype=float)
    measure = np.asarray(measure, dtype=float)
    keep = np.isfinite(difficulty) & np.isfinite(measure)
    difficulty, measure = difficulty[keep], measure[keep]
    if difficulty.size < 2:
        return float("nan")
    predicted = group_intercept + group_slope * difficulty
    return float(np.sqrt(np.mean((measure - predicted) ** 2)))


def zscore(values: np.ndarray) -> np.ndarray:
    values = np.asarray(values, dtype=float)
    finite = values[np.isfinite(values)]
    if finite.size < 2 or np.allclose(finite, finite[0]):
        return np.full_like(values, np.nan)
    return (values - finite.mean()) / finite.std(ddof=1)
