from pathlib import Path

from rocell.application.reviewed_hover_recovery_recipe import (
    NAMES, SOURCE_GOALS, TARGETS, preview, validate_recipe,
)


ROOT = Path(__file__).resolve().parents[2]


def test_exact_finite_recovery_cycle():
    assert validate_recipe()
    assert NAMES == ("A_CLEAR", "A_HOVER", "A_DOWN", "A_HOVER", "A_CLEAR")
    assert TARGETS[-1] != SOURCE_GOALS
    assert [b - a for a, b in zip(SOURCE_GOALS, TARGETS[0])] == [
        0, -18, 18, -18, 36, 0, 0]


def test_recovery_model_screen_is_not_motion_authority():
    report = preview(ROOT / "models/roarm_m3/roarm_m3_kinematic_40dbd84.urdf")
    assert report["status"] == "OFFLINE_MODEL_SCREEN_PASS_NOT_EXECUTABLE"
    assert len(report["legs"]) == 5
    assert not report["hardware_access"]
    assert not report["motion_authorized"]
