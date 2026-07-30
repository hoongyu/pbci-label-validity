"""Task condition codes — and the two incompatible numbering schemes.

COG-BCI numbers its eight task conditions **twice, differently**:

    code  notebook.mat      RSME.txt / KSS.txt
    ----  ----------------  ------------------
     1    PVT               MATB_easy
     2    Flanker           MATB_med
     3    Two-Back          MATB_diff
     4    One-Back          ZeroBack
     5    Zero-Back         OneBack
     6    MATB-Easy         TwoBack
     7    MATB-Medium       PVT
     8    MATB-Difficult    Flanker

No code means the same thing in both files. `dataset.md` §1 and §7.7 document
the notebook scheme and warn that its N-Back numbering is descending
(3=Two-Back, 5=Zero-Back); it does not mention that the questionnaire files use
a different scheme in which N-Back is **ascending** (4=ZeroBack, 6=TwoBack).

The failure mode this module exists to prevent: joining RSME scores to EEG
epochs on the raw integer code. That silently reverses N-Back difficulty, which
inverts the sign of Kendall's tau-b in D_subj for every subject — corrupting
the project's load-bearing quantity (`gates.md` §G1.4) in a way that produces
plausible-looking numbers and no error.

Rule: never join on a raw integer. Resolve to a Condition first.
"""

from __future__ import annotations

from enum import Enum


class Task(str, Enum):
    NBACK = "nback"
    MATB = "matb"
    PVT = "pvt"
    FLANKER = "flanker"


class Condition(str, Enum):
    """Canonical condition identity, independent of either file's numbering."""

    ZERO_BACK = "zero_back"
    ONE_BACK = "one_back"
    TWO_BACK = "two_back"
    MATB_EASY = "matb_easy"
    MATB_MEDIUM = "matb_medium"
    MATB_DIFFICULT = "matb_difficult"
    PVT = "pvt"
    FLANKER = "flanker"

    @property
    def task(self) -> Task:
        return _TASK_OF[self]

    @property
    def difficulty(self) -> int | None:
        """Ordinal difficulty 0/1/2 within task; None for ungraded tasks.

        PVT and Flanker have no graded workload manipulation and are out of
        scope (`PRD.md` §5).
        """
        return _DIFFICULTY_OF.get(self)

    @property
    def in_scope(self) -> bool:
        return self.difficulty is not None


_TASK_OF: dict[Condition, Task] = {
    Condition.ZERO_BACK: Task.NBACK,
    Condition.ONE_BACK: Task.NBACK,
    Condition.TWO_BACK: Task.NBACK,
    Condition.MATB_EASY: Task.MATB,
    Condition.MATB_MEDIUM: Task.MATB,
    Condition.MATB_DIFFICULT: Task.MATB,
    Condition.PVT: Task.PVT,
    Condition.FLANKER: Task.FLANKER,
}

_DIFFICULTY_OF: dict[Condition, int] = {
    Condition.ZERO_BACK: 0,
    Condition.ONE_BACK: 1,
    Condition.TWO_BACK: 2,
    Condition.MATB_EASY: 0,
    Condition.MATB_MEDIUM: 1,
    Condition.MATB_DIFFICULT: 2,
}

#: Task order codes in notebook.mat (`dataset.md` §1). N-Back DESCENDING.
NOTEBOOK_CODES: dict[int, Condition] = {
    1: Condition.PVT,
    2: Condition.FLANKER,
    3: Condition.TWO_BACK,
    4: Condition.ONE_BACK,
    5: Condition.ZERO_BACK,
    6: Condition.MATB_EASY,
    7: Condition.MATB_MEDIUM,
    8: Condition.MATB_DIFFICULT,
}

#: Condition codes in RSME.txt and KSS.txt. N-Back ASCENDING. Undocumented.
QUESTIONNAIRE_CODES: dict[int, Condition] = {
    1: Condition.MATB_EASY,
    2: Condition.MATB_MEDIUM,
    3: Condition.MATB_DIFFICULT,
    4: Condition.ZERO_BACK,
    5: Condition.ONE_BACK,
    6: Condition.TWO_BACK,
    7: Condition.PVT,
    8: Condition.FLANKER,
}

#: The text labels in the `condition` column of RSME.txt.
QUESTIONNAIRE_LABELS: dict[str, Condition] = {
    "MATB_easy": Condition.MATB_EASY,
    "MATB_med": Condition.MATB_MEDIUM,
    "MATB_diff": Condition.MATB_DIFFICULT,
    "ZeroBack": Condition.ZERO_BACK,
    "OneBack": Condition.ONE_BACK,
    "TwoBack": Condition.TWO_BACK,
    "PVT": Condition.PVT,
    "Flanker": Condition.FLANKER,
}

IN_SCOPE: tuple[Condition, ...] = (
    Condition.ZERO_BACK, Condition.ONE_BACK, Condition.TWO_BACK,
    Condition.MATB_EASY, Condition.MATB_MEDIUM, Condition.MATB_DIFFICULT,
)


def from_notebook(code: int) -> Condition:
    """Resolve a notebook.mat task-order code."""
    try:
        return NOTEBOOK_CODES[int(code)]
    except KeyError:
        raise ValueError(f"not a notebook task code (expected 1-8): {code!r}") from None


def from_questionnaire(code: int) -> Condition:
    """Resolve an RSME.txt / KSS.txt numeric condition code.

    Prefer `from_label` when the text column is available — it cannot be
    confused with the notebook scheme.
    """
    try:
        return QUESTIONNAIRE_CODES[int(code)]
    except KeyError:
        raise ValueError(f"not a questionnaire code (expected 1-8): {code!r}") from None


def from_label(label: str) -> Condition:
    """Resolve the text label in the RSME.txt `condition` column."""
    try:
        return QUESTIONNAIRE_LABELS[str(label).strip()]
    except KeyError:
        raise ValueError(f"unknown condition label: {label!r}") from None


def assert_schemes_are_distinct() -> None:
    """Guard the premise this module exists for (G0.2).

    Also asserts the direction of each scheme's N-Back numbering: descending in
    the notebook (the check `gates.md` §G0.2 names), ascending in the
    questionnaires. If a future data release renumbers either file, this fails
    loudly instead of corrupting D_subj silently.
    """
    nb = {c: NOTEBOOK_CODES[c] for c in range(1, 9)}
    q = {c: QUESTIONNAIRE_CODES[c] for c in range(1, 9)}

    assert set(nb.values()) == set(Condition), "notebook scheme must cover all 8 conditions"
    assert set(q.values()) == set(Condition), "questionnaire scheme must cover all 8 conditions"

    agreeing = [c for c in range(1, 9) if nb[c] == q[c]]
    assert not agreeing, (
        f"codes {agreeing} now agree between notebook.mat and RSME.txt. The two "
        "schemes were wholly disjoint when this project was written; a change "
        "means the data release differs from the one analysed."
    )

    # notebook: N-Back descending -> larger code, lower load
    assert nb[3].difficulty == 2 and nb[4].difficulty == 1 and nb[5].difficulty == 0, (
        "notebook N-Back numbering is no longer descending (3=Two, 4=One, 5=Zero)"
    )
    # questionnaires: N-Back ascending -> larger code, higher load
    assert q[4].difficulty == 0 and q[5].difficulty == 1 and q[6].difficulty == 2, (
        "questionnaire N-Back numbering is no longer ascending (4=Zero, 5=One, 6=Two)"
    )
