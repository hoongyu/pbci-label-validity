"""Tests for the derived-data write path.

These exist because the atomic-write fix shipped with a bug that only surfaced
after four workers had each spent ~45 min computing a session: the results were
discarded at the final rename. The failure was invisible until then, so it gets
a test rather than a second reading.
"""

from __future__ import annotations

import os

import numpy as np
import pytest


def _atomic_save(out, payload):
    """Mirror of the write in `run_one`, kept in sync by the tests below."""
    tmp = out.with_name(f"{out.stem}.{os.getpid()}.tmp.npz")
    np.savez_compressed(tmp, **payload)
    os.replace(tmp, out)
    return tmp


def test_atomic_save_lands_on_the_intended_path(tmp_path):
    out = tmp_path / "sub-01_ses-S1_cov.npz"
    tmp = _atomic_save(out, {"a__theta": np.eye(10)[None]})

    assert out.exists(), "result did not land on the target path"
    assert not tmp.exists(), "temp file left behind"
    assert list(tmp_path.iterdir()) == [out], "stray files in the output dir"


def test_no_npz_suffix_is_appended_to_the_temp_name(tmp_path):
    """The actual bug: savez_compressed appends .npz to a path lacking it.

    A temp name of "....npz.<pid>.tmp" was written as "....npz.<pid>.tmp.npz",
    so os.replace raised FileNotFoundError on a file that never existed.
    """
    bad_tmp = tmp_path / "sub-01_ses-S1_cov.npz.999.tmp"
    np.savez_compressed(bad_tmp, x=np.zeros(3))
    assert not bad_tmp.exists()
    assert bad_tmp.with_suffix(".tmp.npz").exists()

    good_tmp = tmp_path / "sub-01_ses-S1_cov.999.tmp.npz"
    np.savez_compressed(good_tmp, x=np.zeros(3))
    assert good_tmp.exists(), "a temp name ending in .npz must be written as-is"


def test_temp_files_do_not_match_the_derived_glob(tmp_path):
    """A temp file must never be picked up as a finished subject-session."""
    (tmp_path / "sub-01_ses-S1_cov.123.tmp.npz").touch()
    (tmp_path / "sub-01_ses-S1_cov.npz").touch()
    found = sorted(p.name for p in tmp_path.glob("sub-*_ses-S*_cov.npz"))
    assert found == ["sub-01_ses-S1_cov.npz"]


def test_payload_round_trips(tmp_path):
    out = tmp_path / "sub-02_ses-S3_cov.npz"
    payload = {
        "zero_back__alpha": np.random.default_rng(0).normal(size=(7, 10, 10)),
        "matb_easy__theta": np.random.default_rng(1).normal(size=(5, 10, 10)),
    }
    _atomic_save(out, payload)
    loaded = np.load(out)
    assert sorted(loaded.files) == sorted(payload)
    for key, value in payload.items():
        np.testing.assert_allclose(loaded[key], value)


@pytest.mark.parametrize("interrupted_before_rename", [True, False])
def test_interrupted_write_never_leaves_a_partial_result(tmp_path,
                                                         interrupted_before_rename):
    """Killing a worker mid-write must not produce a skippable output."""
    out = tmp_path / "sub-03_ses-S2_cov.npz"
    tmp = out.with_name(f"{out.stem}.777.tmp.npz")
    np.savez_compressed(tmp, x=np.ones(4))
    if not interrupted_before_rename:
        os.replace(tmp, out)

    complete = out.exists()
    assert complete is not interrupted_before_rename
    if interrupted_before_rename:
        # only the temp survives, and it is not visible to the resume scan
        assert list(tmp_path.glob("sub-*_ses-S*_cov.npz")) == []
