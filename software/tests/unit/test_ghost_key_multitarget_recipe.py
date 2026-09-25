"""The ghost-key path is source-bound, finite, noncontact and offline only."""
from pathlib import Path

from rocell.application.ghost_key_multitarget_recipe import (
    PHASES,SOURCE_GOALS,TARGETS,preview,review_source,validate_recipe,
)


ROOT = Path(__file__).resolve().parents[2]


def test_fixed_two_cycle_recipe_is_source_bound():
    assert validate_recipe()
    assert len(PHASES) == len(TARGETS) == 16
    assert TARGETS[:8] == TARGETS[8:]
    assert SOURCE_GOALS == TARGETS[3]
    assert len(review_source(ROOT/"runs/wizard-exports")) == 64


def test_full_interpolated_model_sweep_does_not_authorize_motion():
    report = preview(ROOT/"models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf")
    assert report["status"] == "OFFLINE_GHOST_KEY_SWEEP_PASS_NOT_EXECUTABLE"
    assert len(report["legs"]) == 16
    assert report["key_order"] == ["A","B","A","B"]
    assert not report["motion_authorized"]
