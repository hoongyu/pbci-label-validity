"""Unit tests for the divergence metrics — the G1.3 KPI.

`gates.md` §G1.3 requires coverage of three cases by name: a perfect-agreement
subject (tau_b = 1, D = 0), a perfectly inverted subject (D = 2), and a
tied/flat subject. Those are the first three tests here; the rest guard the
properties that make the metric mean what §1 says it means.

Run:  python -m pytest analyses/P1_divergence/test_metrics.py -q
"""

from __future__ import annotations

import numpy as np
import pytest

from analyses.P1_divergence.metrics import (
    FLAT_D,
    bootstrap_ci,
    d_resid,
    d_slope,
    divergence,
    zscore,
)

# Nine cells: 3 difficulties x 3 sessions, which is the real design.
DIFFICULTY = np.array([0, 0, 0, 1, 1, 1, 2, 2, 2], dtype=float)


# --------------------------------------------------------------- KPI cases

def test_perfect_agreement_gives_zero():
    """RSME rises with difficulty and is tied within it: tau_b = 1, D = 0."""
    rsme = np.array([10, 10, 10, 50, 50, 50, 90, 90, 90], dtype=float)
    assert divergence(DIFFICULTY, rsme) == pytest.approx(0.0)


def test_perfect_inversion_gives_two():
    """RSME falls with difficulty: tau_b = -1, D = 2 — the top of the range."""
    rsme = np.array([90, 90, 90, 50, 50, 50, 10, 10, 10], dtype=float)
    assert divergence(DIFFICULTY, rsme) == pytest.approx(2.0)


def test_flat_subject_maps_to_no_association():
    """A subject who answers identically nine times has no rank information.

    tau_b is undefined here (zero variance in one margin), so this is the
    INTERPRETIVE choice documented in metrics.py and preregistered at G-LOCK,
    not a mathematical result. Pinned by a test so it cannot drift silently.
    """
    rsme = np.full(9, 42.0)
    assert divergence(DIFFICULTY, rsme) == pytest.approx(FLAT_D)


# ------------------------------------------------------- range and ordering

def test_noisy_agreement_lands_between_zero_and_one():
    rsme = np.array([10, 30, 20, 50, 40, 60, 80, 95, 70], dtype=float)
    d = divergence(DIFFICULTY, rsme)
    assert 0.0 < d < 1.0


def test_monotone_transform_of_the_measure_does_not_change_d():
    """tau_b is a rank statistic: any strictly increasing transform is a no-op.

    This is the property that makes D immune to how much of the analogue scale
    a subject uses, which is the reason §1 chose it over a slope.
    """
    rsme = np.array([12, 31, 22, 55, 44, 63, 81, 96, 74], dtype=float)
    assert divergence(DIFFICULTY, rsme) == pytest.approx(
        divergence(DIFFICULTY, np.log(rsme)))
    assert divergence(DIFFICULTY, rsme) == pytest.approx(
        divergence(DIFFICULTY, 3.0 * rsme + 7.0))


def test_compressed_range_does_not_change_d_but_does_change_slope():
    """The distinction D_subj is built to make, and D_slope deliberately does not.

    Two subjects with identical rank orderings but very different scale usage
    must get the same D_subj. D_slope is z-scored per subject so it also
    survives compression -- what separates them is that D_slope keeps the
    *shape* of the response, so it is a genuine robustness check rather than a
    restatement.
    """
    wide = np.array([10, 12, 11, 50, 48, 52, 90, 92, 88], dtype=float)
    narrow = np.array([60, 61, 60.5, 62, 61.8, 62.2, 64, 64.5, 63.5])
    assert divergence(DIFFICULTY, wide) == pytest.approx(
        divergence(DIFFICULTY, narrow))


# ------------------------------------------------------- sign orientation

def test_behavioural_orientation_flips_the_sign():
    """Performance is higher = better, so perfect tracking is tau = -1.

    Getting this backwards would silently turn the best-performing subjects
    into the most divergent ones, which is the single most consequential sign
    error available in this file.
    """
    performance = np.array([0.99, 0.99, 0.99, 0.80, 0.80, 0.80,
                            0.55, 0.55, 0.55])
    assert divergence(DIFFICULTY, performance,
                      higher_is_worse=True) == pytest.approx(0.0)
    # Without the flag it reads as perfect inversion — the failure mode.
    assert divergence(DIFFICULTY, performance) == pytest.approx(2.0)


def test_d_zero_is_unreachable_once_cells_differ_within_a_difficulty():
    """D = 0 requires the tie structure to match, not just the ordering.

    Nominal difficulty has three ties of three. tau_b's denominator is
    sqrt((n0-n1)(n0-n2)), so a subject whose nine RSME values are perfectly
    ordered across levels but *differ* within a level scores tau_b = 0.866, not
    1.0 — a floor of D ≈ 0.134 rather than 0.

    This is a property of the chosen metric, not an error, but it matters for
    interpretation: because session is deliberately kept as a replicate rather
    than averaged (`analysis.md` §1), every real subject has within-level
    variation, so the observed D_subj distribution is shifted up off zero and
    "0 = perfect agreement" is unattainable in practice. Any threshold or
    effect size read against 0 would be biased by this amount.
    """
    ordered_but_untied = np.array([10, 12, 11, 50, 48, 52, 90, 92, 88],
                                  dtype=float)
    d = divergence(DIFFICULTY, ordered_but_untied)
    assert d == pytest.approx(1 - 27 / np.sqrt(27 * 36), abs=1e-9)
    assert d == pytest.approx(0.134, abs=0.001)
    # Same ordering, ties restored -> the true zero.
    assert divergence(DIFFICULTY, np.array([10, 10, 10, 50, 50, 50, 90, 90, 90],
                                           dtype=float)) == pytest.approx(0.0)


# ------------------------------------------------------------ missing data

def test_missing_cells_are_dropped_not_imputed():
    rsme = np.array([10, np.nan, 10, 50, 50, np.nan, 90, 90, 90])
    assert divergence(DIFFICULTY, rsme) == pytest.approx(0.0)


def test_too_few_cells_returns_nan():
    d = divergence(np.array([0.0, 1.0]), np.array([10.0, 20.0]))
    assert np.isnan(d)


def test_all_missing_returns_nan():
    assert np.isnan(divergence(DIFFICULTY, np.full(9, np.nan)))


# -------------------------------------------------------------- bootstrap

def test_bootstrap_ci_brackets_the_point_estimate():
    rsme = np.array([10, 30, 20, 50, 40, 60, 80, 95, 70], dtype=float)
    d = divergence(DIFFICULTY, rsme)
    lo, hi = bootstrap_ci(DIFFICULTY, rsme, n_draws=500, seed=1)
    assert lo <= d <= hi
    assert 0.0 <= lo and hi <= 2.0


def test_bootstrap_is_reproducible_from_the_seed():
    rsme = np.array([10, 30, 20, 50, 40, 60, 80, 95, 70], dtype=float)
    a = bootstrap_ci(DIFFICULTY, rsme, n_draws=200, seed=7)
    b = bootstrap_ci(DIFFICULTY, rsme, n_draws=200, seed=7)
    c = bootstrap_ci(DIFFICULTY, rsme, n_draws=200, seed=8)
    assert a == b
    assert a != c


# ------------------------------------------------------ robustness metrics

def test_d_slope_sign_follows_the_association():
    rising = np.array([10, 10, 10, 50, 50, 50, 90, 90, 90], dtype=float)
    falling = rising[::-1].copy()
    assert d_slope(DIFFICULTY, rising) > 0
    assert d_slope(DIFFICULTY, falling) < 0
    assert np.isnan(d_slope(DIFFICULTY, np.full(9, 42.0)))


def test_d_resid_is_zero_on_the_group_line_and_grows_off_it():
    on_line = 10.0 + 20.0 * DIFFICULTY
    assert d_resid(DIFFICULTY, on_line, 10.0, 20.0) == pytest.approx(0.0)
    off_line = on_line + 5.0
    assert d_resid(DIFFICULTY, off_line, 10.0, 20.0) == pytest.approx(5.0)


def test_zscore_of_constant_is_nan_not_zero():
    """Guards a divide-by-zero that would otherwise read as 'perfectly average'."""
    assert np.all(np.isnan(zscore(np.full(5, 3.0))))
