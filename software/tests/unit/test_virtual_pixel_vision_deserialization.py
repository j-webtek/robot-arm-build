from __future__ import annotations

from copy import deepcopy
from dataclasses import replace
import json
from pathlib import Path
from typing import Any

import pytest

from rocell.application.bootstrap import bootstrap_virtual_workcell
from rocell.application.virtual_pixel_vision import (
    VirtualPixelCaptureMode,
    VirtualPixelVisionAttemptLedger,
    VirtualPixelVisionError,
    VirtualPixelVisionService,
    VirtualPixelVisionStage,
    virtual_pixel_vision_attempt_ledger_from_dict,
)


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def coherent_ledger() -> VirtualPixelVisionAttemptLedger:
    service = VirtualPixelVisionService(bootstrap_virtual_workcell(WORKSPACE).context)
    passed = service.process(sequence=100)
    unavailable = service.process(
        sequence=101,
        capture_mode=VirtualPixelCaptureMode.CAMERA_UNAVAILABLE,
    )
    tag_loss = service.process(
        sequence=102,
        capture_mode=VirtualPixelCaptureMode.TAG_LOSS,
    )
    assert passed.passed
    assert unavailable.stage is VirtualPixelVisionStage.CAPTURE
    assert tag_loss.stage is VirtualPixelVisionStage.POSE
    return (
        VirtualPixelVisionAttemptLedger.create(service.service_definition_sha256)
        .associate(
            passed,
            action_index=0,
            target_id="keyboard:A",
            waypoint_sequence=1000,
        )
        .associate(
            unavailable,
            action_index=1,
            target_id="keyboard:B",
            waypoint_sequence=1001,
        )
        .associate(
            tag_loss,
            action_index=2,
            target_id="phone:home",
            waypoint_sequence=1002,
        )
        .seal()
    )


def _document(ledger: VirtualPixelVisionAttemptLedger) -> dict[str, Any]:
    # Exercise the actual JSON object/array types accepted by the strict wire
    # decoder, independently of sharing any mutable object with the record.
    value = json.loads(json.dumps(ledger.to_dict(), allow_nan=False))
    assert isinstance(value, dict)
    return value


def _set_path(document: dict[str, Any], path: tuple[object, ...], value: object) -> None:
    cursor: Any = document
    for element in path[:-1]:
        cursor = cursor[element]
    cursor[path[-1]] = value


def test_coherent_pass_and_fault_ledger_round_trips_canonically(
    coherent_ledger: VirtualPixelVisionAttemptLedger,
) -> None:
    document = _document(coherent_ledger)
    reconstructed = virtual_pixel_vision_attempt_ledger_from_dict(document)

    assert reconstructed == coherent_ledger
    assert reconstructed.to_dict() == document
    assert reconstructed.passed_attempt_count == 1
    assert not reconstructed.all_attempts_passed
    assert reconstructed.attempts[0].result.pose_observation is not None
    assert reconstructed.attempts[1].result.frame is None
    assert reconstructed.attempts[2].result.detection_batch is not None
    assert reconstructed.attempts[2].result.pose_observation is None


def test_nested_detection_and_pose_tampering_is_rejected(
    coherent_ledger: VirtualPixelVisionAttemptLedger,
) -> None:
    detection_tamper = _document(coherent_ledger)
    detection_tamper["attempts"][0]["result"]["detection_batch"]["detections"][0][
        "detector_accepted"
    ] = False
    with pytest.raises(VirtualPixelVisionError, match="detection batch"):
        virtual_pixel_vision_attempt_ledger_from_dict(detection_tamper)

    pose_tamper = _document(coherent_ledger)
    pose_tamper["attempts"][0]["result"]["pose_observation"]["fit"][
        "inlier_mask"
    ][0] = False
    with pytest.raises(VirtualPixelVisionError, match="pose observation"):
        virtual_pixel_vision_attempt_ledger_from_dict(pose_tamper)


@pytest.mark.parametrize(
    "path",
    (
        ("attempts", 0, "result", "detection_batch_sha256"),
        ("attempts", 0, "result", "pose_observation_sha256"),
        ("attempts", 0, "result", "result_hash"),
        ("attempts", 0, "result_hash"),
        ("attempts", 0, "attempt_hash"),
        ("ledger_hash",),
    ),
)
def test_every_redundant_hash_layer_rejects_tampering(
    coherent_ledger: VirtualPixelVisionAttemptLedger,
    path: tuple[object, ...],
) -> None:
    document = _document(coherent_ledger)
    _set_path(document, path, "0" * 64)
    with pytest.raises(VirtualPixelVisionError, match="hash|sha256"):
        virtual_pixel_vision_attempt_ledger_from_dict(document)


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("attempt_count",), 0),
        (("passed_attempt_count",), 0),
        (("all_attempts_passed",), True),
    ),
)
def test_redundant_counts_and_pass_claims_are_recomputed(
    coherent_ledger: VirtualPixelVisionAttemptLedger,
    path: tuple[object, ...],
    value: object,
) -> None:
    document = _document(coherent_ledger)
    _set_path(document, path, value)
    with pytest.raises(VirtualPixelVisionError, match="count|all_attempts_passed"):
        virtual_pixel_vision_attempt_ledger_from_dict(document)


@pytest.mark.parametrize(
    "path",
    (
        ("authority", "hardware_accessed"),
        ("attempts", 0, "result", "authority", "live_motion_authorized"),
        ("attempts", 0, "result", "frame", "authority", "contact_authorized"),
        (
            "attempts",
            0,
            "result",
            "detection_batch",
            "authority",
            "can_authorize_motion",
        ),
        (
            "attempts",
            0,
            "result",
            "pose_observation",
            "authority",
            "can_authorize_motion",
        ),
    ),
)
def test_every_nested_authority_boundary_rejects_escalation(
    coherent_ledger: VirtualPixelVisionAttemptLedger,
    path: tuple[object, ...],
) -> None:
    document = _document(coherent_ledger)
    _set_path(document, path, True)
    with pytest.raises(VirtualPixelVisionError, match="authority|detection|pose"):
        virtual_pixel_vision_attempt_ledger_from_dict(document)


@pytest.mark.parametrize(
    ("path", "value"),
    (
        (("attempts", 0, "association_timing"), "BEFORE_PROCESSING"),
        (("attempts", 0, "result", "frame", "jpeg_bytes_serialized"), True),
        (("attempts", 0, "result", "frame", "embedded_detection_truth"), True),
        (
            (
                "attempts",
                0,
                "result",
                "quality",
                "robot_frame_correction_applied",
            ),
            True,
        ),
        (
            ("attempts", 0, "result", "target_or_action_received_by_processor"),
            True,
        ),
        (("attempts", 0, "result", "arm_mounted_camera_simulated"), True),
        (("attempts", 0, "result", "robot_frame_correction_applied"), True),
        (("attempts", 0, "result", "jpeg_bytes_serialized"), True),
        (
            ("input_separation", "pixel_processor_received_target_or_action"),
            True,
        ),
        (("input_separation", "association_occurs_after_processing"), False),
        (("arm_mounted_camera_simulated",), True),
        (("robot_frame_correction_applied",), True),
    ),
)
def test_association_oracle_jpeg_and_robot_correction_claims_are_locked(
    coherent_ledger: VirtualPixelVisionAttemptLedger,
    path: tuple[object, ...],
    value: object,
) -> None:
    document = _document(coherent_ledger)
    _set_path(document, path, value)
    with pytest.raises(VirtualPixelVisionError):
        virtual_pixel_vision_attempt_ledger_from_dict(document)


def test_coherently_rehashed_status_and_stage_forgery_is_rejected(
    coherent_ledger: VirtualPixelVisionAttemptLedger,
) -> None:
    passing = coherent_ledger.attempts[0].result
    forged_complete_fault = replace(passing, status="FAULT")
    forged_pose_fault = replace(
        passing,
        status="FAULT",
        stage=VirtualPixelVisionStage.POSE,
        detail_code="PIXEL_BOARD_POSE_FAILED",
    )
    for forged in (forged_complete_fault, forged_pose_fault):
        forged_ledger = (
            VirtualPixelVisionAttemptLedger.create(
                coherent_ledger.service_definition_sha256
            )
            .associate(
                forged,
                action_index=0,
                target_id="keyboard:A",
                waypoint_sequence=1,
            )
            .seal()
        )
        # All hashes are produced by the record itself; rejection therefore
        # demonstrates structural status/stage validation, not a stale hash.
        with pytest.raises(VirtualPixelVisionError, match="status|stage|evidence"):
            virtual_pixel_vision_attempt_ledger_from_dict(forged_ledger.to_dict())


def test_noncanonical_json_container_and_numeric_types_are_rejected(
    coherent_ledger: VirtualPixelVisionAttemptLedger,
) -> None:
    tuple_attempts = _document(coherent_ledger)
    tuple_attempts["attempts"] = tuple(tuple_attempts["attempts"])
    with pytest.raises(VirtualPixelVisionError, match="JSON array"):
        virtual_pixel_vision_attempt_ledger_from_dict(tuple_attempts)

    float_count = _document(coherent_ledger)
    float_count["attempt_count"] = 3.0
    with pytest.raises(VirtualPixelVisionError, match="integer"):
        virtual_pixel_vision_attempt_ledger_from_dict(float_count)
