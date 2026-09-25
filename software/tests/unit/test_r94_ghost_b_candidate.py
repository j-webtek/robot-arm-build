"""The B-cycle app is compiled, source-bound, finite and manually gated."""
from pathlib import Path
import sys

import pytest

from rocell.application.ghost_typing_resume_preview import TARGETS

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))
from review_r94_ghost_b_candidate import COMPILE_ID, review
from run_r94_ghost_b_leg import _source, main


def test_compiled_candidate_has_dedicated_nonautomatic_surface():
    report = review(ROOT, COMPILE_ID)
    assert report["status"] == "COMPILED_NOT_INSTALLED"
    assert report["maximum_legs"] == len(TARGETS) == 5
    assert not report["automatic_progression"]
    assert not report["gripper_writes"]
    board = (ROOT / "firmware/diagnostics/ghost_typing_b_board.h").read_text()
    for target in TARGETS:
        assert "{" + ",".join(map(str, target)) + "}" in board


def test_no_clearance_or_prior_leg_cannot_dispatch(tmp_path):
    with pytest.raises(ValueError, match="clearance confirmation"):
        main(leg=1, catch_removed_and_path_clear=False)
    with pytest.raises(ValueError, match="Prior leg has no durable reservation"):
        _source(tmp_path, 2, "a" * 32)
