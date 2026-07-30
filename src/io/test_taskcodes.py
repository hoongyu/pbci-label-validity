"""Tests for the two COG-BCI condition-numbering schemes.

These tests are checked against the real data files in `data/raw` where those
files are present, so the encoded schemes cannot drift from the dataset.
"""

from __future__ import annotations

from pathlib import Path

import pytest

from src.io.taskcodes import (
    IN_SCOPE,
    Condition,
    Task,
    assert_schemes_are_distinct,
    from_label,
    from_notebook,
    from_questionnaire,
)

RAW = Path(__file__).resolve().parents[2] / "data" / "raw"


def test_schemes_are_distinct():
    assert_schemes_are_distinct()


def test_no_code_means_the_same_thing_in_both_files():
    clashes = [c for c in range(1, 9) if from_notebook(c) is from_questionnaire(c)]
    assert clashes == []


def test_nback_numbering_runs_opposite_ways():
    """The trap: code order implies opposite difficulty order per file."""
    notebook_nback = [from_notebook(c).difficulty for c in (3, 4, 5)]
    quest_nback = [from_questionnaire(c).difficulty for c in (4, 5, 6)]
    assert notebook_nback == [2, 1, 0], "notebook N-Back is descending"
    assert quest_nback == [0, 1, 2], "questionnaire N-Back is ascending"
    assert notebook_nback == list(reversed(quest_nback))


def test_reading_rsme_with_the_notebook_scheme_inverts_nback():
    """Demonstrates the silent corruption, so the guard is never relaxed.

    An RSME row labelled ZeroBack carries code 4. Read with the notebook
    scheme, code 4 is One-Back; code 6 (TwoBack) becomes MATB-Easy. The
    difficulty ordering that reaches D_subj is wrong, and nothing raises.
    """
    correct = [from_label(l).difficulty for l in ("ZeroBack", "OneBack", "TwoBack")]
    codes = (4, 5, 6)
    wrong = [from_notebook(c).difficulty for c in codes]
    assert correct == [0, 1, 2]
    assert wrong == [1, 0, 0]          # One-Back, Zero-Back, MATB-Easy
    assert wrong != correct


@pytest.mark.parametrize(
    "label,condition,difficulty",
    [
        ("ZeroBack", Condition.ZERO_BACK, 0),
        ("OneBack", Condition.ONE_BACK, 1),
        ("TwoBack", Condition.TWO_BACK, 2),
        ("MATB_easy", Condition.MATB_EASY, 0),
        ("MATB_med", Condition.MATB_MEDIUM, 1),
        ("MATB_diff", Condition.MATB_DIFFICULT, 2),
    ],
)
def test_labels_resolve_with_correct_difficulty(label, condition, difficulty):
    assert from_label(label) is condition
    assert condition.difficulty == difficulty


def test_out_of_scope_conditions_have_no_difficulty():
    """PVT and Flanker are ungraded and out of scope (PRD 5)."""
    for c in (Condition.PVT, Condition.FLANKER):
        assert c.difficulty is None
        assert not c.in_scope
    assert len(IN_SCOPE) == 6
    assert all(c.in_scope for c in IN_SCOPE)


def test_task_grouping():
    assert Condition.TWO_BACK.task is Task.NBACK
    assert Condition.MATB_DIFFICULT.task is Task.MATB
    assert sum(c.task is Task.NBACK for c in IN_SCOPE) == 3
    assert sum(c.task is Task.MATB for c in IN_SCOPE) == 3


@pytest.mark.parametrize("bad", [0, 9, -1, "nback"])
def test_invalid_codes_raise(bad):
    with pytest.raises(ValueError):
        from_notebook(bad)
    with pytest.raises(ValueError):
        from_questionnaire(bad)


def test_surrounding_whitespace_is_tolerated():
    assert from_label("  TwoBack ") is Condition.TWO_BACK


@pytest.mark.parametrize("bad", ["3-back", "twoback", "TWOBACK", "MATB_hard", ""])
def test_unknown_label_raises(bad):
    with pytest.raises(ValueError):
        from_label(bad)


# --- checked against the real files, skipped when absent -------------------

@pytest.mark.skipif(not (RAW / "RSME.txt").exists(), reason="RSME.txt not downloaded")
def test_questionnaire_scheme_matches_the_actual_rsme_file():
    """The code->label pairing in RSME.txt must match QUESTIONNAIRE_CODES."""
    import pandas as pd

    df = pd.read_csv(RAW / "RSME.txt")
    pairs = df.drop_duplicates("Condition").set_index("Condition")["condition"].to_dict()
    assert len(pairs) == 8
    for code, label in pairs.items():
        assert from_questionnaire(code) is from_label(label), (
            f"RSME.txt pairs code {code} with {label!r}, "
            f"but QUESTIONNAIRE_CODES says {from_questionnaire(code)}"
        )


@pytest.mark.skipif(not (RAW / "notebook.mat").exists(), reason="notebook.mat not downloaded")
def test_every_notebook_order_is_a_permutation_of_all_eight_conditions():
    import numpy as np
    import scipy.io

    m = scipy.io.loadmat(RAW / "notebook.mat", struct_as_record=False, squeeze_me=True)
    nb = m["notebook"]
    seen = 0
    for s in range(1, 30):
        sbj = getattr(nb, f"SBJ_{s}")
        for ses in range(1, 4):
            order = np.asarray(getattr(getattr(sbj, f"SESS_{ses}"), "Order")).ravel()
            conditions = {from_notebook(c) for c in order}
            assert conditions == set(Condition), f"sub-{s:02d} ses-S{ses} order={order}"
            seen += 1
    assert seen == 87, "expected 29 subjects x 3 sessions"
