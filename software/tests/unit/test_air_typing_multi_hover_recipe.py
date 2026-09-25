"""Offline hover proposal is bounded and tied to the last verified endpoint."""
from pathlib import Path

from rocell.application.air_typing_multi_hover_recipe import (
    PHASES, SOURCE_GOALS, TARGETS, preview, review_source, validate_recipe,
)


ROOT = Path(__file__).resolve().parents[2]


def test_fixed_multijoint_hover_recipe_and_retained_source():
    assert validate_recipe()
    assert len(PHASES) == len(TARGETS) == 5
    assert SOURCE_GOALS[3] == 2620
    assert len(review_source(ROOT / "runs/wizard-exports")) == 64


def test_model_screens_every_interpolated_leg_without_authorizing_motion():
    report = preview(ROOT / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf")
    assert report["status"] == "OFFLINE_MULTI_HOVER_SWEEP_PASS_NOT_EXECUTABLE"
    assert [row["selected_joints"] for row in report["legs"]] == [
        [3], [0, 1, 2, 3, 4], [0, 1, 2, 3, 4], [0, 1, 2, 3, 4], [0, 1, 2, 3, 4]]
    assert not report["motion_authorized"]
