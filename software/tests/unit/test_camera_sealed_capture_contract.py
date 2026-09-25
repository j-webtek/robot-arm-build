"""Exact original-permit joins with incapable producers; no device effects."""

from dataclasses import replace

import pytest

from rocell.application import camera_sealed_capture_contract as module
from rocell.application.camera_activation_campaign_contract import (
    SEALED_CONFIGURATION_CAPTURE_ACTION_ID as ACTION,
    SEALED_CONFIGURATION_CAPTURE_WORKER_ID as WORKER,
    validate_camera_activation_binding,
    validate_camera_activation_permit,
)
from rocell.application.camera_capture_checksum import (
    build_capture_checksum,
    capture_metadata,
)
from rocell.application.camera_sealed_capture_evidence import (
    SealedCameraCaptureEvidence,
    MAX_SEALED_CAPTURE_BYTES,
)
from rocell.application.cell_commissioning_coordinator import (
    PhysicalCameraAcquisitionCoordinator,
    RegisteredActionRequest,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.providers.windows.camera_worker_client import NativeFrameArtifact
from rocell.safety.effects import EffectCertainty
from test_camera_activation_campaign_contract import (
    profile,
    build_execution,
    CameraV2Store,
    ModeledCameraV2Worker,
)
from test_physical_camera_coordinator import admission, CELL, SESSION
from test_native_camera_activation_supervisor import Clock, no_physical_owner
from test_physical_camera_configuration import forbid_process_and_devices


def sealed_profile():
    old = profile("capture")
    return replace(
        old,
        action_id=ACTION,
        worker_id=WORKER,
        stage=STAGE_ORDER[4],
        budget=replace(old.budget, maximum_output_bytes=MAX_SEALED_CAPTURE_BYTES),
    )


def sealed_execution(
    directory,
    monkeypatch,
    permit,
    deadline,
    *,
    status="CAPTURE_BYTES_HASHED",
    fault=None,
    clock=None,
    current=lambda exact: None,
):
    legacy = build_execution(
        directory,
        monkeypatch,
        permit,
        deadline,
        purpose="capture",
        fault=fault,
        clock=clock,
        current=current,
    )
    checked, _, metadata = capture_metadata(legacy.evidence)
    tick = (checked.run.to_dict()["finished_ns"] or permit.issued_at_ns) + 1
    if metadata is None:
        status = "NATIVE_CAPTURE_NOT_COMPLETE"
    checksum = build_capture_checksum(
        legacy.evidence,
        request_key=permit.request.request_key,
        status=status,
        frame=(
            NativeFrameArtifact(**metadata, sha256="e" * 64)
            if status == "CAPTURE_BYTES_HASHED"
            else None
        ),
        read_started_ns=(
            None if metadata is None or status == "PIXEL_READ_NOT_ATTESTED" else tick
        ),
        read_finished_ns=(
            None
            if metadata is None or status == "PIXEL_READ_NOT_ATTESTED"
            else (deadline if status == "PIXEL_READ_INTERRUPTED" else tick)
        ),
    )
    return module.sealed_capture_execution(
        permit,
        SealedCameraCaptureEvidence(legacy.evidence, checksum),
        expected_deadline_ns=deadline,
    )


@pytest.fixture
def fixture(tmp_path, monkeypatch):
    reg, clock = sealed_profile(), Clock()
    store = CameraV2Store(admission(stage=reg.stage))
    worker = ModeledCameraV2Worker(tmp_path, monkeypatch, clock, "capture")
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=store,
        registrations=(reg,),
        workers={reg.worker_id: worker},
        retained_campaign_actions=(reg.action_id,),
        scoped_campaign_actions=(reg.action_id,),
        monotonic_ns=clock,
    )
    request = RegisteredActionRequest(
        CELL, SESSION, ACTION, "sealed-capture-test", store.snapshot.challenge_sha256
    )
    permit = core.prepare(request)
    deadline = permit.issued_at_ns + reg.budget.timeout_ms * 1_000_000
    return permit, sealed_execution(tmp_path, monkeypatch, permit, deadline), deadline


def test_original_request_binds_checksum_without_changing_native_counts(fixture):
    permit, execution, deadline = fixture
    assert validate_camera_activation_permit(permit) == "capture"
    module.validate_sealed_capture_execution(
        execution, permit, expected_deadline_ns=deadline
    )
    module.validate_sealed_capture_receipt(
        execution.receipt, permit, execution.evidence, expected_deadline_ns=deadline
    )
    assert execution.receipt.evidence_sha256s == execution.evidence.evidence_sha256s
    assert len(execution.receipt.evidence_sha256s) == 3
    assert execution.receipt.output_bytes == execution.evidence.payload_bytes
    assert (
        execution.receipt.frames
        == execution.receipt.opens
        == execution.receipt.closes
        == 1
    )
    assert execution.receipt.effect_certainty is EffectCertainty.CONFIRMED
    with pytest.raises(ValueError, match="LEGACY_PAIR"):
        validate_camera_activation_binding(permit, execution.evidence.native)


@pytest.mark.parametrize(
    "field,value",
    [
        ("opens", True),
        ("frames", False),
        ("reads", 0),
        ("writes", 1),
        ("closes", 0),
        ("cleanup_confirmed", 1),
        ("output_bytes", 0),
        ("evidence_sha256s", ("a" * 64,)),
        ("effect_certainty", "CONFIRMED"),
        ("final_power_state", "UNKNOWN"),
    ],
)
def test_receipt_accounting_cannot_drop_checksum_or_change_counts(
    fixture, field, value
):
    permit, execution, deadline = fixture
    changed = replace(execution, receipt=replace(execution.receipt, **{field: value}))
    with pytest.raises(ValueError):
        module.validate_sealed_capture_execution(
            changed, permit, expected_deadline_ns=deadline
        )
    with pytest.raises(ValueError):
        module.validate_sealed_capture_receipt(
            changed.receipt, permit, changed.evidence, expected_deadline_ns=deadline
        )


def test_checksum_request_key_must_match_original_permit(fixture):
    import json
    from rocell.application.camera_capture_checksum import CameraCaptureChecksum
    from rocell.providers.windows.native_camera_protocol import canonical

    permit, execution, deadline = fixture
    data = execution.evidence.checksum.to_dict()
    data["request_key"] = "another-request"
    changed = SealedCameraCaptureEvidence(
        execution.evidence.native, CameraCaptureChecksum(canonical(data))
    )
    with pytest.raises(ValueError):
        module.sealed_capture_execution(permit, changed, expected_deadline_ns=deadline)


@pytest.mark.parametrize(
    "fault", ["native-roster", "native-bytes", "checksum-binding", "checksum-type"]
)
def test_permit_verifier_rebuilds_even_a_mutated_frozen_collection(fixture, fault):
    from copy import copy
    from rocell.application.camera_activation_campaign_evidence import (
        CameraActivationArtifact,
    )
    from rocell.application.camera_capture_checksum import CameraCaptureChecksum
    from rocell.providers.windows.native_camera_protocol import canonical

    permit, execution, deadline = fixture
    changed = copy(execution.evidence)
    # Deliberately bypass Python's frozen assignment protection in this negative
    # test. Validation must never trust a constructor having run in the past.
    if fault == "native-roster":
        object.__setattr__(changed, "native", changed.native[:1])
    elif fault == "native-bytes":
        object.__setattr__(
            changed,
            "native",
            (
                CameraActivationArtifact("run", b" " + changed.native[0].payload),
                changed.native[1],
            ),
        )
    elif fault == "checksum-binding":
        data = changed.checksum.to_dict()
        data["preparation_sha256"] = "f" * 64
        object.__setattr__(changed, "checksum", CameraCaptureChecksum(canonical(data)))
    else:
        object.__setattr__(changed, "checksum", changed.checksum.to_dict())
    with pytest.raises(ValueError):
        module.validate_sealed_capture_binding(
            permit, changed, expected_deadline_ns=deadline
        )


@pytest.mark.parametrize(
    "field,value",
    [
        ("receipt", None),
        ("receipt", "untrusted"),
        ("evidence", {}),
        ("reason_codes", []),
        ("reason_codes", ("UNTRUSTED_REASON",)),
        ("reason_codes", (True,)),
    ],
)
def test_execution_reconstruction_does_not_trust_a_past_constructor(
    fixture, field, value
):
    from copy import copy

    permit, execution, deadline = fixture
    changed = copy(execution)
    object.__setattr__(changed, field, value)
    with pytest.raises(ValueError):
        module.validate_sealed_capture_execution(
            changed, permit, expected_deadline_ns=deadline
        )


@pytest.mark.parametrize(
    "status", ["PIXEL_READ_FAILED", "PIXEL_READ_INTERRUPTED", "PIXEL_READ_NOT_ATTESTED"]
)
def test_failed_read_does_not_invent_zero_camera_effects(
    tmp_path, monkeypatch, fixture, status
):
    permit, _, deadline = fixture
    # Separate synthetic evidence construction, not a dispatched physical retry.
    execution = sealed_execution(tmp_path, monkeypatch, permit, deadline, status=status)
    module.validate_sealed_capture_execution(
        execution, permit, expected_deadline_ns=deadline
    )
    module.validate_sealed_capture_receipt(
        execution.receipt, permit, execution.evidence, expected_deadline_ns=deadline
    )
    assert execution.receipt.effect_certainty is EffectCertainty.UNCERTAIN
    assert execution.receipt.cleanup_confirmed is False
    assert (
        execution.receipt.frames
        == execution.receipt.opens
        == execution.receipt.closes
        == 1
    )
    assert execution.evidence.checksum.to_dict()["verified_pixel_bytes"] == 0
