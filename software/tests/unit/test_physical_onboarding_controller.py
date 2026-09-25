from __future__ import annotations

import builtins
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import shutil

import pytest

import rocell.application.physical_onboarding_controller as controller_module
import rocell.vision.camera_profile as camera_profile_module
from rocell.application.physical_host_readiness import (
    PhysicalHostReadinessReport,
)
from rocell.application.physical_onboarding import (
    PhysicalOnboardingStage,
    StageState,
)
from rocell.application.physical_onboarding_controller import (
    PhysicalOnboardingController,
    PhysicalOnboardingControllerError,
)
from rocell.application.physical_onboarding_policy import (
    load_physical_onboarding_policy,
)
from rocell.rc03 import BuildSnapshot, import_build_snapshot


WORKSPACE = Path(__file__).resolve().parents[3]


def _snapshot() -> BuildSnapshot:
    return import_build_snapshot(
        WORKSPACE, WORKSPACE / "software/config/system_manifest.json"
    )


def _copy_controlled_workspace(destination: Path) -> None:
    policy = load_physical_onboarding_policy(WORKSPACE)
    destination.mkdir()
    for relative in (policy.policy_relative_path, *policy.controlled_sources):
        source = WORKSPACE / relative
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        shutil.copy2(source, target)
    for relative_root in policy.controlled_source_roots:
        source_root = WORKSPACE / relative_root
        for source in source_root.rglob("*.py"):
            target = destination / source.relative_to(WORKSPACE)
            target.parent.mkdir(parents=True, exist_ok=True)
            shutil.copy2(source, target)


def _ready_report(workspace: Path, snapshot: BuildSnapshot) -> PhysicalHostReadinessReport:
    return PhysicalHostReadinessReport(
        platform_system="Windows",
        platform_release="test",
        python_version="3.12.0",
        python_64_bit=True,
        workspace=str(workspace.resolve()),
        active_build_id=snapshot.active_build_id,
        manifest_id=snapshot.manifest_id,
        build_snapshot_sha256=snapshot.snapshot_hash,
        static_camera_plan_selected=True,
        static_camera_freeze_promoted=False,
        runtime_fail_closed=True,
        launcher_present=True,
        bootstrap_script_present=True,
        workspace_venv_present=False,
        running_from_workspace_venv=False,
        device_access_environment_ready=False,
        dependencies=(),
        base_software_ready=True,
        camera_diagnostics_dependencies_ready=False,
        arm_diagnostics_dependencies_ready=False,
        development_dependencies_ready=False,
        blockers=(
            "WORKSPACE_VIRTUAL_ENVIRONMENT_MISSING",
            "SUPERSEDING_STATIC_CAMERA_FREEZE_NOT_PROMOTED",
        ),
    )


class _Clock:
    def __init__(self, start: int = 1_000_000) -> None:
        self.value = start

    def __call__(self) -> int:
        self.value += 10
        return self.value


def _create(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> tuple[PhysicalOnboardingController, Path, BuildSnapshot, _Clock]:
    workspace = tmp_path / "workspace"
    _copy_controlled_workspace(workspace)
    snapshot = _snapshot()
    clock = _Clock()
    monkeypatch.setattr(controller_module, "_time_ns", clock)
    monkeypatch.setattr(
        controller_module,
        "assess_physical_host_readiness",
        lambda selected, current: _ready_report(selected, current),
    )
    controller = PhysicalOnboardingController.create(
        workspace,
        snapshot,
        session_id="arrival-001",
        cell_id="cell-a",
    )
    return controller, workspace, snapshot, clock


def _execute(controller: PhysicalOnboardingController) -> None:
    preview = controller.preview_next()
    assert preview.executable is True
    controller.execute_next(
        expected_challenge_sha256=preview.challenge.challenge_sha256
    )


def test_create_is_policy_rooted_and_identifiers_are_portable(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, workspace, snapshot, _ = _create(tmp_path, monkeypatch)

    assert controller.session_directory == (
        workspace
        / "software/runs/physical-onboarding/onboarding-arrival-001"
    ).resolve()
    reopened = PhysicalOnboardingController.open(
        workspace, snapshot, session_id="arrival-001"
    )
    assert reopened.status().snapshot.header.cell_id == "cell-a"

    with pytest.raises(PhysicalOnboardingControllerError, match="portable"):
        PhysicalOnboardingController.create(
            workspace,
            snapshot,
            session_id="../escape",
            cell_id="cell-b",
        )
    with pytest.raises(PhysicalOnboardingControllerError, match="reserved"):
        PhysicalOnboardingController.create(
            workspace,
            snapshot,
            session_id="CON.txt",
            cell_id="cell-b",
        )


def test_only_two_zero_io_stages_complete_automatically_and_status_is_full(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, _, _, _ = _create(tmp_path, monkeypatch)
    original_import = builtins.__import__

    def guarded_import(name: str, *args: object, **kwargs: object) -> object:
        if name.split(".", 1)[0] in {"cv2", "serial"}:
            raise AssertionError(f"device backend imported: {name}")
        return original_import(name, *args, **kwargs)

    monkeypatch.setattr(builtins, "__import__", guarded_import)
    _execute(controller)
    _execute(controller)

    status = controller.verify()
    document = status.to_dict()
    assert status.snapshot.state_for(
        PhysicalOnboardingStage.WORKSPACE_SOURCES
    ) is StageState.PASS
    assert status.snapshot.state_for(
        PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT
    ) is StageState.PASS
    assert status.snapshot.next_action.stage is PhysicalOnboardingStage.CAMERA_RECEIPT
    assert status.snapshot.next_action.stage_state is StageState.PENDING
    assert len(status.snapshot.events) == 4
    assert len(status.snapshot.evidence) == 2
    workspace_evidence = next(
        item
        for item in status.snapshot.evidence
        if item.stage is PhysicalOnboardingStage.WORKSPACE_SOURCES
    )
    workspace_document = json.loads(
        (
            controller.session_directory
            / "evidence"
            / workspace_evidence.evidence_id
            / "payload.bin"
        ).read_text(encoding="utf-8")
    )
    workspace_check = workspace_document["check"]
    assert workspace_check["foundation_id"] == (
        "ROCELL-PHYSICAL-ONBOARDING-FOUNDATION-001"
    )
    assert workspace_check["foundation_contract_count"] == 6
    assert workspace_check["foundation_runtime_activation"] is False
    assert workspace_check["foundation_zero_physical_authority"] is True
    assert len(workspace_check["foundation_open_implementation_gates"]) == 10
    static_evidence = next(
        item
        for item in status.snapshot.evidence
        if item.stage is PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT
    )
    static_document = json.loads(
        (
            controller.session_directory
            / "evidence"
            / static_evidence.evidence_id
            / "payload.bin"
        ).read_text(encoding="utf-8")
    )
    static_check = static_document["check"]
    assert static_check["verification_scope"] == (
        "STRICT_STATIC_CAMERA_PLANNING_INPUTS_ONLY"
    )
    assert static_check["contract_verified_without_device_access"] is True
    assert static_check["physical_qualification_complete"] is False
    assert static_check["physical_release_ready"] is False
    assert static_check["failed_cross_checks"] == []
    assert all(static_check["cross_checks"].values())
    assert all(static_check["support_source_binding_checks"].values())
    assert static_check["camera_profile"]["source_file_sha256"] == (
        hashlib.sha256(
            (
                controller.workspace
                / "software/config/camera_profiles/arducam_b0477_imx283_16mm.json"
            ).read_bytes()
        ).hexdigest()
    )
    assert static_check["architecture"]["source_sha256"] == (
        hashlib.sha256(
            (
                controller.workspace
                / "software/config/camera_architecture_plan.json"
            ).read_bytes()
        ).hexdigest()
    )
    assert static_check["support_design"]["content_sha256"] == (
        hashlib.sha256(
            (
                controller.workspace
                / "hardware/static_overhead_camera/config/support_design.json"
            ).read_bytes()
        ).hexdigest()
    )
    assert static_check["selected_published_mode"] == {
        "host_bus": "USB_3_2_GEN_1",
        "width_px": 5472,
        "height_px": 3648,
        "maximum_fps": 9.0,
        "pixel_format": "YUY2",
        "evidence_state": "MANUFACTURER_PUBLISHED_UNMEASURED",
    }
    assert document["journal"]["head_event_sha256"] == (
        status.snapshot.events[-1].event_sha256
    )
    assert document["journal"]["high_water_sha256"] == (
        status.snapshot.high_water_sha256
    )
    assert document["physical_effect_counters"] == {
        "device_enumerations": 0,
        "device_opens": 0,
        "camera_frames_captured": 0,
        "serial_transactions": 0,
        "robot_power_operations": 0,
        "robot_commands": 0,
        "motion_commands": 0,
        "contact_commands": 0,
    }
    json.dumps(document, allow_nan=False)


def test_foundation_rejects_semantically_invalid_architecture_at_stage_one(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    workspace = tmp_path / "workspace"
    _copy_controlled_workspace(workspace)
    architecture_path = workspace / "software/config/camera_architecture_plan.json"
    architecture = json.loads(architecture_path.read_text(encoding="utf-8"))
    # Keep the shallow readiness fields intact while invalidating a field that
    # only the strict architecture loader verifies.
    architecture["primary"]["architecture"] = "arm_mounted_camera"
    architecture_path.write_text(json.dumps(architecture), encoding="utf-8")

    snapshot = _snapshot()
    clock = _Clock()
    monkeypatch.setattr(controller_module, "_time_ns", clock)
    monkeypatch.setattr(
        controller_module,
        "assess_physical_host_readiness",
        lambda selected, current: _ready_report(selected, current),
    )
    controller = PhysicalOnboardingController.create(
        workspace,
        snapshot,
        session_id="invalid-camera-plan",
        cell_id="cell-a",
    )
    preview = controller.preview_next()

    with pytest.raises(
        PhysicalOnboardingControllerError,
        match="foundation failed strict zero-I/O validation",
    ):
        controller.execute_next(
            expected_challenge_sha256=preview.challenge.challenge_sha256
        )

    status = controller.status()
    assert status.snapshot.state_for(
        PhysicalOnboardingStage.WORKSPACE_SOURCES
    ) is StageState.PENDING
    assert len(status.snapshot.events) == 0
    assert len(status.snapshot.evidence) == 0


def test_static_camera_cross_check_blocks_and_reports_loaded_identity_mismatch(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, _, _, _ = _create(tmp_path, monkeypatch)
    real_loader = camera_profile_module.load_camera_profile

    def load_mismatched_profile(path: Path):
        return replace(real_loader(path), manufacturer="Altered catalog identity")

    monkeypatch.setattr(
        camera_profile_module,
        "load_camera_profile",
        load_mismatched_profile,
    )
    _execute(controller)
    _execute(controller)

    status = controller.status()
    assert status.snapshot.state_for(
        PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT
    ) is StageState.BLOCKED
    static_evidence = next(
        item
        for item in status.snapshot.evidence
        if item.stage is PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT
    )
    document = json.loads(
        (
            controller.session_directory
            / "evidence"
            / static_evidence.evidence_id
            / "payload.bin"
        ).read_text(encoding="utf-8")
    )
    check = document["check"]
    assert check["camera_profile"]["manufacturer"] == "Altered catalog identity"
    assert check["contract_verified_without_device_access"] is False
    assert check["cross_checks"]["profile_and_support_identity_match"] is False
    assert "profile_and_support_identity_match" in check["failed_cross_checks"]


def test_physical_stage_can_only_wait_and_evidence_cannot_pass_it(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, workspace, _, clock = _create(tmp_path, monkeypatch)
    _execute(controller)
    _execute(controller)

    pending = controller.preview_next()
    assert pending.operation == "MARK_WAITING_OPERATOR"
    _execute(controller)
    waiting = controller.status()
    assert waiting.snapshot.next_action.stage is PhysicalOnboardingStage.CAMERA_RECEIPT
    assert waiting.snapshot.next_action.stage_state is StageState.WAITING_OPERATOR
    assert controller.preview_next().executable is False
    assert not hasattr(controller, "commit_stage_state")

    source = workspace / "incoming/camera-receipt.txt"
    source.parent.mkdir()
    payload = b"camera receipt evidence\n"
    source.write_bytes(payload)
    expected = hashlib.sha256(payload).hexdigest()
    challenge = controller.expected_challenge()
    tail = waiting.snapshot.events[-1].occurred_at_ns
    captured = tail + 5
    # The strict caller timestamp is after the stage event and before the
    # controller's next real-time observation.
    clock.value = tail + 5
    evidence = controller.record_evidence_file(
        stage=PhysicalOnboardingStage.CAMERA_RECEIPT,
        source_path=source.relative_to(workspace),
        expected_payload_sha256=expected,
        captured_at_ns=captured,
        label="camera purchase receipt",
        media_type="text/plain",
        expected_challenge_sha256=challenge.challenge_sha256,
    )
    after = controller.status()
    assert evidence.payload_sha256 == expected
    assert after.snapshot.next_action.stage_state is StageState.WAITING_OPERATOR
    assert after.snapshot.state_for(
        PhysicalOnboardingStage.CAMERA_RECEIPT
    ) is StageState.WAITING_OPERATOR

    with pytest.raises(PhysicalOnboardingControllerError, match="stale"):
        controller.record_evidence_file(
            stage=PhysicalOnboardingStage.CAMERA_RECEIPT,
            source_path=source,
            expected_payload_sha256=expected,
            captured_at_ns=captured,
            label="duplicate",
            media_type="text/plain",
            expected_challenge_sha256=challenge.challenge_sha256,
        )


def test_source_binding_drift_is_visible_and_blocks_execution(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, workspace, _, _ = _create(tmp_path, monkeypatch)
    controlled = workspace / "software/config/arm_connection.json"
    controlled.write_bytes(controlled.read_bytes() + b"\n")

    status = controller.status()
    preview = controller.preview_next()
    assert status.source_binding_current is False
    assert preview.operation == "BLOCKED_SOURCE_BINDING_DRIFT"
    assert preview.executable is False
    with pytest.raises(PhysicalOnboardingControllerError, match="binding drifted"):
        controller.verify()
    with pytest.raises(PhysicalOnboardingControllerError, match="binding drifted"):
        controller.execute_next(
            expected_challenge_sha256=preview.challenge.challenge_sha256
        )


def test_generated_diagnostic_evidence_is_retained_without_passing_stage(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, _, _, _ = _create(tmp_path, monkeypatch)
    _execute(controller)
    _execute(controller)
    _execute(controller)
    challenge = controller.expected_challenge().challenge_sha256

    evidence = controller.record_generated_evidence_document(
        stage=PhysicalOnboardingStage.CAMERA_RECEIPT,
        document={
            "schema": "test.generated_diagnostic.v1",
            "observed": True,
            "authority": "ZERO",
        },
        label="generated diagnostic",
        expected_challenge_sha256=challenge,
    )

    status = controller.status()
    assert evidence.stage is PhysicalOnboardingStage.CAMERA_RECEIPT
    assert status.snapshot.state_for(
        PhysicalOnboardingStage.CAMERA_RECEIPT
    ) is StageState.WAITING_OPERATOR
    assert status.snapshot.next_action.stage_state is StageState.WAITING_OPERATOR


def test_old_stage_and_head_challenge_cannot_execute_twice(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, _, _, _ = _create(tmp_path, monkeypatch)
    preview = controller.preview_next()
    controller.execute_next(
        expected_challenge_sha256=preview.challenge.challenge_sha256
    )

    with pytest.raises(PhysicalOnboardingControllerError, match="stale"):
        controller.execute_next(
            expected_challenge_sha256=preview.challenge.challenge_sha256
        )


def test_clock_rollback_is_rejected_without_manufacturing_a_timestamp(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, _, _, clock = _create(tmp_path, monkeypatch)
    created = controller.status().snapshot.header.created_at_ns
    clock.value = created - 10  # next call returns exactly the persisted time
    preview = controller.preview_next()

    with pytest.raises(PhysicalOnboardingControllerError, match="clock did not advance"):
        controller.execute_next(
            expected_challenge_sha256=preview.challenge.challenge_sha256
        )
    assert controller.status().snapshot.events == ()


def test_evidence_requires_workspace_regular_file_hash_and_strict_time(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    controller, workspace, _, clock = _create(tmp_path, monkeypatch)
    _execute(controller)
    _execute(controller)
    _execute(controller)
    status = controller.status()
    challenge = controller.expected_challenge().challenge_sha256
    tail = status.snapshot.events[-1].occurred_at_ns
    outside = tmp_path / "outside.bin"
    outside.write_bytes(b"outside")
    clock.value = tail + 10

    with pytest.raises(PhysicalOnboardingControllerError, match="outside the workspace"):
        controller.record_evidence_file(
            stage=PhysicalOnboardingStage.CAMERA_RECEIPT,
            source_path=outside,
            expected_payload_sha256=hashlib.sha256(b"outside").hexdigest(),
            captured_at_ns=tail + 1,
            label="outside",
            media_type="application/octet-stream",
            expected_challenge_sha256=challenge,
        )

    source = workspace / "incoming.bin"
    source.write_bytes(b"inside")
    clock.value = tail + 20
    with pytest.raises(PhysicalOnboardingControllerError, match="SHA-256 differs"):
        controller.record_evidence_file(
            stage=PhysicalOnboardingStage.CAMERA_RECEIPT,
            source_path=source,
            expected_payload_sha256="f" * 64,
            captured_at_ns=tail + 1,
            label="wrong hash",
            media_type="application/octet-stream",
            expected_challenge_sha256=challenge,
        )

    clock.value = tail + 30
    with pytest.raises(PhysicalOnboardingControllerError, match="must not be in the future"):
        controller.record_evidence_file(
            stage=PhysicalOnboardingStage.CAMERA_RECEIPT,
            source_path=source,
            expected_payload_sha256=hashlib.sha256(b"inside").hexdigest(),
            captured_at_ns=tail + 100,
            label="future",
            media_type="application/octet-stream",
            expected_challenge_sha256=challenge,
        )
