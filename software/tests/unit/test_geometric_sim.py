from __future__ import annotations

from pathlib import Path

import pytest

from rocell.models.actions import ActionPlan, Device, PressKey, TapPhoneTarget, VerifyPhoneState
from rocell.motion import (
    GeometricDryRunEngine,
    GeometricSimulationError,
    GeometricSimulationSettings,
    MotionPhase,
)
from rocell.rc03 import BuildSnapshot
from rocell.simulation import load_rc03_nominal_scene, load_simulation_hardware_profile
from rocell.targets import load_nominal_target_catalog
from rocell.typing import KEYBOARD_SEMANTIC_PROFILE_ID, PHONE_SEMANTIC_PROFILE_ID


@pytest.fixture
def workspace_root() -> Path:
    return Path(__file__).resolve().parents[3]


def _actual_sources(workspace: Path):
    """Load geometry under test with a hermetic simulation-only snapshot.

    Manifest/source integrity is covered by importer and repository-contract
    tests. Unit tests for the geometric engine must not become coupled to a
    hardware package that is legitimately being revised in parallel.
    """

    profile = load_simulation_hardware_profile(workspace)
    snapshot = BuildSnapshot(
        manifest_id=profile.source_freeze_id,
        manifest_sha256=profile.source_manifest_sha256,
        design_revision=profile.design_revision,
        active_build_id="GEOMETRY-UNIT-TEST",
        source_hashes={},
        selected_routes={
            "keyboard_rod_route": True,
            "phone_stylus_route": True,
        },
        gate_statuses={},
        hard_blockers=(),
        physical_release_status="UNRELEASED",
        tag_coordinate_source="nominal_layout",
        camera_exact_model=None,
        camera_state="OPEN_BLOCKING",
        safe_to_power_robot=False,
        contact_enabled=False,
    )
    scene = load_rc03_nominal_scene(workspace / "active-project/RoCell_v0_3")
    targets = load_nominal_target_catalog(workspace)
    return snapshot, profile, scene, targets


def test_keyboard_nominal_tip_path_is_checked_and_nonexecuting(workspace_root: Path) -> None:
    snapshot, profile, scene, targets = _actual_sources(workspace_root)
    plan = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id=KEYBOARD_SEMANTIC_PROFILE_ID,
        text="az",
        actions=(PressKey("A"), PressKey("Z")),
        required_calibrations=(),
    )

    report = GeometricDryRunEngine().run(plan, snapshot, profile, scene, targets)

    assert report.all_checks_pass is True
    assert report.to_dict()["hardware_commands_generated"] == 0
    assert report.to_dict()["execution_authorized"] is False
    assert any(step.phase is MotionPhase.CONTACT for step in report.steps)
    assert all(check.status == "PASS" for check in report.checks)


def test_phone_verify_and_tap_path_is_deterministic(workspace_root: Path) -> None:
    snapshot, profile, scene, targets = _actual_sources(workspace_root)
    plan = ActionPlan.from_text(
        device=Device.PHONE,
        profile_id=PHONE_SEMANTIC_PROFILE_ID,
        text="a",
        actions=(VerifyPhoneState("KEYBOARD_LOWER"), TapPhoneTarget("key_a", "KEYBOARD_LOWER")),
        required_calibrations=(),
    )
    engine = GeometricDryRunEngine()

    first = engine.run(plan, snapshot, profile, scene, targets)
    second = engine.run(plan, snapshot, profile, scene, targets)

    assert first.report_hash == second.report_hash
    assert first.steps[1].phase is MotionPhase.VERIFY
    assert first.all_checks_pass is True


def test_revision_mismatch_fails_closed(workspace_root: Path) -> None:
    snapshot, profile, scene, targets = _actual_sources(workspace_root)
    object.__setattr__(targets, "design_revision", "WRONG")
    plan = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id=KEYBOARD_SEMANTIC_PROFILE_ID,
        text="a",
        actions=(PressKey("A"),),
        required_calibrations=(),
    )

    with pytest.raises(GeometricSimulationError, match="different design revisions"):
        GeometricDryRunEngine().run(plan, snapshot, profile, scene, targets)


def test_unmapped_target_fails_before_pose_use(workspace_root: Path) -> None:
    snapshot, profile, scene, targets = _actual_sources(workspace_root)
    plan = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id=KEYBOARD_SEMANTIC_PROFILE_ID,
        text="?",
        actions=(PressKey("NOT_A_KEY"),),
        required_calibrations=(),
    )

    with pytest.raises(GeometricSimulationError, match="Unknown keyboard target"):
        GeometricDryRunEngine().run(plan, snapshot, profile, scene, targets)


def test_semantic_profile_must_be_explicitly_bound_to_target_geometry(
    workspace_root: Path,
) -> None:
    snapshot, profile, scene, targets = _actual_sources(workspace_root)
    plan = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id="unbound-keyboard-profile",
        text="a",
        actions=(PressKey("A"),),
        required_calibrations=(),
    )

    with pytest.raises(GeometricSimulationError, match="not bound"):
        GeometricDryRunEngine().run(plan, snapshot, profile, scene, targets)


def test_expected_collision_returns_failed_evidence_instead_of_losing_report(
    workspace_root: Path,
) -> None:
    snapshot, profile, scene, targets = _actual_sources(workspace_root)
    plan = ActionPlan.from_text(
        device=Device.KEYBOARD,
        profile_id=KEYBOARD_SEMANTIC_PROFILE_ID,
        text="a",
        actions=(PressKey("A"),),
        required_calibrations=(),
    )
    engine = GeometricDryRunEngine(
        GeometricSimulationSettings(segment_clearance_mm=100.0)
    )

    report = engine.run(plan, snapshot, profile, scene, targets)

    assert report.all_checks_pass is False
    assert any(check.status == "FAIL" for check in report.checks)
    assert any(check.collisions for check in report.checks if check.status == "FAIL")
