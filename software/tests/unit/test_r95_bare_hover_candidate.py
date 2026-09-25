"""r95 is a pinned app-only, manually gated hover candidate."""
from pathlib import Path
import sys

import pytest

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT / "scripts"))

from stage_r95_bare_hover import sources, stage
from review_r95_bare_hover import APP_SHA, review
from deploy_r95_bare_hover import prepare, install
from run_r95_bare_hover_leg import _source, main


def test_staged_and_linked_image_has_only_dedicated_hover_surface():
    assert stage(ROOT)["status"] == "STAGED_OFFLINE_NOT_INSTALLED"
    generated = sources(ROOT)
    board = generated["bare_gripper_hover_board.h"]
    assert b"rocell.bare_gripper_hover.v1" in board
    assert b"/rocell/hover-two-region/capabilities" in board
    assert b"SyncWritePosEx(ids,uint8_t(count)" in board
    assert b"if(i==6||" in board
    assert b"automatic_progression\\\":false" in board
    result = review(ROOT)
    assert result["app_sha256"] == APP_SHA
    assert result["maximum_legs"] == 5
    assert not result["startup_motion"]
    assert not result["generic_motion_parser"]


def test_installer_prepare_is_read_only_and_catch_is_required():
    # After the one permitted install, prepare() must refuse a retry.
    journal = ROOT / "private-backups/controller-20260918-session1/app-r95-deployment-events.jsonl"
    assert journal.exists()
    with pytest.raises(ValueError, match="already attempted"):
        prepare(ROOT)
    with pytest.raises(ValueError, match="catch must be in place"):
        install(ROOT, {}, catch_in_place=False)


def test_no_clearance_or_prior_completion_cannot_dispatch(tmp_path):
    with pytest.raises(ValueError, match="clearance confirmation"):
        main(leg=1, catch_removed_and_path_clear=False)
    with pytest.raises(ValueError, match="Prior leg lacks durable"):
        _source(tmp_path, 2, "a"*32)
