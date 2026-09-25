from __future__ import annotations

import inspect
from pathlib import Path
from typing import Iterator

import pytest

from rocell.application.bootstrap import bootstrap_virtual_workcell
from rocell.application.virtual_pixel_vision import (
    VirtualPixelCaptureMode,
    VirtualPixelVisionAttemptLedger,
    VirtualPixelVisionError,
    VirtualPixelVisionService,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def _nested_values(value: object) -> Iterator[object]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _nested_values(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _nested_values(child)


@pytest.fixture(scope="module")
def service() -> VirtualPixelVisionService:
    return VirtualPixelVisionService(
        bootstrap_virtual_workcell(WORKSPACE).context
    )


def test_processor_signature_cannot_receive_plan_or_corner_oracle() -> None:
    assert tuple(inspect.signature(VirtualPixelVisionService.process).parameters) == (
        "self",
        "sequence",
        "capture_mode",
    )


def test_normal_pixels_decode_six_tags_and_recover_bounded_board_pose(
    service: VirtualPixelVisionService,
) -> None:
    result = service.process(sequence=7)

    assert result.passed
    assert result.detail_code == "PIXEL_BOARD_POSE_ACCEPTED"
    assert result.frame is not None
    assert result.detection_batch is not None
    assert result.pose_observation is not None
    assert result.quality is not None and result.quality.passed
    assert [tag.tag_id for tag in result.detection_batch.accepted_tags] == list(
        range(6)
    )
    assert [tag.tag_id for tag in result.pose_observation.used_tags] == list(range(6))
    assert result.pose_observation.pose.parent_frame == "camera_overview_optical"
    assert result.pose_observation.pose.child_frame == "board"
    assert result.quality.inlier_rmse_px < 1.0
    assert result.quality.translation_error_mm < 1.0
    assert result.quality.rotation_error_deg < 0.1

    document = result.to_dict()
    assert document["target_or_action_received_by_processor"] is False
    assert document["jpeg_bytes_serialized"] is False
    assert document["robot_frame_correction_applied"] is False
    assert not any(isinstance(value, bytes) for value in _nested_values(document))


def test_pixel_tag_loss_is_rendered_then_naturally_rejected(
    service: VirtualPixelVisionService,
) -> None:
    result = service.process(
        sequence=8,
        capture_mode=VirtualPixelCaptureMode.TAG_LOSS,
    )

    assert not result.passed
    assert result.stage.value == "POSE"
    assert result.detail_code == "PIXEL_BOARD_POSE_FAILED"
    assert result.frame is not None
    assert result.detection_batch is not None
    assert [tag.tag_id for tag in result.detection_batch.accepted_tags] == [4, 5]
    assert result.pose_observation is None


def test_camera_unavailable_produces_no_synthetic_frame(
    service: VirtualPixelVisionService,
) -> None:
    result = service.process(
        sequence=9,
        capture_mode=VirtualPixelCaptureMode.CAMERA_UNAVAILABLE,
    )

    assert not result.passed
    assert result.stage.value == "CAPTURE"
    assert result.frame is None
    assert result.detection_batch is None
    assert result.pose_observation is None


def test_association_ledger_is_post_process_ordered_fresh_and_sealed(
    service: VirtualPixelVisionService,
) -> None:
    first = service.process(sequence=10)
    second = service.process(sequence=20)
    ledger = VirtualPixelVisionAttemptLedger.create(
        service.service_definition_sha256
    )
    ledger = ledger.associate(
        first,
        action_index=0,
        target_id="keyboard:A",
        waypoint_sequence=10,
    )
    ledger = ledger.associate(
        second,
        action_index=1,
        target_id="keyboard:B",
        waypoint_sequence=20,
    ).seal()

    assert ledger.sealed
    assert ledger.passed_attempt_count == 2
    assert ledger.all_attempts_passed
    assert ledger.to_dict()["input_separation"] == {
        "pixel_processor_received_target_or_action": False,
        "association_occurs_after_processing": True,
    }
    assert ledger.attempts[0].result.frame is not None
    assert ledger.attempts[1].result.frame is not None
    assert (
        ledger.attempts[0].result.frame.freshness_token
        != ledger.attempts[1].result.frame.freshness_token
    )
    with pytest.raises(VirtualPixelVisionError, match="sealed"):
        ledger.associate(
            service.process(sequence=30),
            action_index=2,
            target_id="keyboard:C",
            waypoint_sequence=30,
        )


def test_ledger_rejects_reusing_one_captured_result(
    service: VirtualPixelVisionService,
) -> None:
    result = service.process(sequence=40)
    ledger = VirtualPixelVisionAttemptLedger.create(
        service.service_definition_sha256
    ).associate(
        result,
        action_index=0,
        target_id="keyboard:A",
        waypoint_sequence=40,
    )
    with pytest.raises(
        VirtualPixelVisionError,
        match="capture sequences must be strictly increasing",
    ):
        ledger.associate(
            result,
            action_index=1,
            target_id="keyboard:B",
            waypoint_sequence=41,
        )
