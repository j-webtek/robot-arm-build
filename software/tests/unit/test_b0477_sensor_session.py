from __future__ import annotations

import base64
from dataclasses import FrozenInstanceError, replace
import hashlib
from pathlib import Path
from typing import Any, Iterator, Mapping, cast

import pytest

import rocell.application as application
from rocell.application.b0477_sensor_session import (
    B0477_FULL_FRAME_RECTIFIER_SCHEMA,
    B0477_RECTIFICATION_MESH_STEP_PX,
    B0477_SENSOR_DETECTOR_RECORD_SCHEMA,
    B0477_SENSOR_POSE_RECORD_SCHEMA,
    B0477_SENSOR_SESSION_BRIDGE_SCHEMA,
    B0477_SOURCE_BOUND_REPLAY_STATUS,
    MAX_B0477_DETECTOR_INPUT_JPEG_BYTES,
    MAX_B0477_JPEG_BASE64_CHUNK_CHARS,
    MAX_B0477_RECTIFICATION_MESH_CELLS,
    B0477RecordedSensorSession,
    B0477SensorSessionBridgeError,
    B0477SyntheticSensorSession,
    build_b0477_synthetic_sensor_session,
    record_and_replay_b0477_synthetic_sensor_session,
)
from rocell.application.b0477_static_vision import (
    B0477StaticVisionCapture,
    B0477StaticVisionError,
    B0477StaticVisionMode,
    run_b0477_static_vision_capture_rehearsal,
    run_b0477_static_vision_rehearsal,
)
from rocell.arm.protocol import decode_line
from rocell.evidence.sensor_session import (
    record_sensor_session,
    replay_sensor_session,
)


WORKSPACE = Path(__file__).resolve().parents[3]


def test_b0477_sensor_bridge_is_intentionally_exported() -> None:
    assert application.build_b0477_synthetic_sensor_session is (
        build_b0477_synthetic_sensor_session
    )
    assert application.record_and_replay_b0477_synthetic_sensor_session is (
        record_and_replay_b0477_synthetic_sensor_session
    )
    assert application.run_b0477_static_vision_capture_rehearsal is (
        run_b0477_static_vision_capture_rehearsal
    )


def _nested_values(value: object) -> Iterator[object]:
    yield value
    if isinstance(value, dict):
        for child in value.values():
            yield from _nested_values(child)
    elif isinstance(value, (list, tuple)):
        for child in value:
            yield from _nested_values(child)


def _plain_json(value: object) -> Any:
    if isinstance(value, Mapping):
        return {str(key): _plain_json(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_plain_json(child) for child in value]
    return value


@pytest.fixture(scope="module")
def bridge_session() -> B0477SyntheticSensorSession:
    pytest.importorskip("PIL")
    return build_b0477_synthetic_sensor_session(WORKSPACE, sequence=211)


def test_public_capture_helper_preserves_established_report_api(
    bridge_session: B0477SyntheticSensorSession,
) -> None:
    capture = bridge_session.capture
    assert isinstance(capture, B0477StaticVisionCapture)
    assert capture.report.status == "PASS"
    assert capture.jpeg_sha256 == capture.report.pixel_statistics.jpeg_sha256
    assert capture.raw_detection_batch.content_hash == dict(
        capture.report.source_hashes
    )["raw_detected_batch"]
    assert capture.rectified_detection_batch.content_hash == dict(
        capture.report.source_hashes
    )["rectified_detection_batch"]
    assert capture.pose_observation is not None
    assert capture.pose_observation.content_hash == dict(
        capture.report.source_hashes
    )["pose_observation"]
    assert not any(
        isinstance(value, bytes) for value in _nested_values(capture.to_dict())
    )

    legacy = run_b0477_static_vision_rehearsal(WORKSPACE, sequence=211)
    assert legacy == capture.report
    assert run_b0477_static_vision_capture_rehearsal(
        WORKSPACE, sequence=211
    ).report == legacy


def test_bridge_builds_exact_yuy2_and_rgb8_layouts(
    bridge_session: B0477SyntheticSensorSession,
) -> None:
    session = bridge_session.session
    mode = session.mode
    assert (mode.width_px, mode.height_px, mode.pixel_format) == (
        2736,
        1824,
        "YUY2",
    )
    assert len(session.raw_frame_bytes) == 9_980_928
    assert len(session.decoded_frame_bytes) == 14_971_392
    assert len(session.undistorted_frame_bytes) == 14_971_392
    assert session.controls.exposure_us == 8_000
    assert session.controls.gain_milli_db == 0
    assert session.controls.white_balance_kelvin == 5_000
    assert session.controls.auto_exposure is False
    assert session.controls.auto_white_balance is False
    assert (
        len(session.raw_frame_bytes)
        == mode.pixel_layouts.raw.expected_byte_length
    )
    assert (
        len(session.decoded_frame_bytes)
        == mode.pixel_layouts.decoded.expected_byte_length
    )
    assert (
        len(session.undistorted_frame_bytes)
        == mode.pixel_layouts.undistorted.expected_byte_length
    )

    # Neutral chroma and replicated grayscale make the synthetic conversion
    # exact and easy to audit without allocating another full-frame buffer.
    for pixel in (0, 1, 2, 10_001, 4_990_463):
        rgb_offset = pixel * 3
        red, green, blue = session.decoded_frame_bytes[
            rgb_offset : rgb_offset + 3
        ]
        assert red == green == blue
        pair_offset = (pixel // 2) * 4
        luminance_offset = pair_offset + (0 if pixel % 2 == 0 else 2)
        assert session.raw_frame_bytes[luminance_offset] == red
        assert session.raw_frame_bytes[pair_offset + 1] == 128
        assert session.raw_frame_bytes[pair_offset + 3] == 128
    assert hashlib.sha256(session.decoded_frame_bytes).digest() != hashlib.sha256(
        session.undistorted_frame_bytes
    ).digest()


def test_original_detector_jpeg_and_every_derived_hash_are_retained(
    bridge_session: B0477SyntheticSensorSession,
) -> None:
    detector = bridge_session.session.detector_record
    assert detector["schema"] == B0477_SENSOR_DETECTOR_RECORD_SCHEMA
    encoded = detector["detector_input_jpeg"]
    assert isinstance(encoded, dict) or hasattr(encoded, "get")
    chunks = encoded["chunks"]
    assert isinstance(chunks, tuple)
    assert chunks
    assert all(
        isinstance(chunk, str)
        and len(chunk) <= MAX_B0477_JPEG_BASE64_CHUNK_CHARS
        for chunk in chunks
    )
    restored = base64.b64decode("".join(chunks), validate=True)
    assert restored == bridge_session.capture.jpeg_bytes
    assert encoded["decoded_byte_count"] == len(restored)
    assert encoded["decoded_sha256"] == hashlib.sha256(restored).hexdigest()

    expected_hashes = {
        "jpeg": bridge_session.capture.jpeg_sha256,
        "raw_yuy2": hashlib.sha256(
            bridge_session.session.raw_frame_bytes
        ).hexdigest(),
        "decoded_rgb8": hashlib.sha256(
            bridge_session.session.decoded_frame_bytes
        ).hexdigest(),
        "rectified_rgb8": hashlib.sha256(
            bridge_session.session.undistorted_frame_bytes
        ).hexdigest(),
    }
    assert dict(detector["raster_sha256"]) == expected_hashes
    assert detector["raw_detection_batch_sha256"] == (
        bridge_session.capture.raw_detection_batch.content_hash
    )
    assert detector["rectified_detection_batch_sha256"] == (
        bridge_session.capture.rectified_detection_batch.content_hash
    )


def test_full_frame_rectification_is_bounded_honest_and_not_pose_input(
    bridge_session: B0477SyntheticSensorSession,
) -> None:
    rectifier = bridge_session.full_frame_rectifier
    assert rectifier["schema"] == B0477_FULL_FRAME_RECTIFIER_SCHEMA
    assert rectifier["mesh_step_px"] == B0477_RECTIFICATION_MESH_STEP_PX
    mesh_cell_count = rectifier["mesh_cell_count"]
    assert isinstance(mesh_cell_count, int) and not isinstance(mesh_cell_count, bool)
    assert 0 < mesh_cell_count <= MAX_B0477_RECTIFICATION_MESH_CELLS
    assert rectifier["raw_encoding"] == "YUY2_Y0_U0_Y1_V0_NEUTRAL_CHROMA"
    assert dict(rectifier["raw_colorimetry"]) == {
        "color_primaries": "SRGB_BT709",
        "transfer_characteristics": "SRGB",
        "matrix_coefficients": "BT601_YCBCR",
        "quantization_range": "FULL_Y0_255_C0_255",
        "chroma_siting": "COSITED_LEFT_422",
        "row_origin": "TOP_LEFT",
    }
    assert rectifier["decoded_encoding"] == "RGB8_INTERLEAVED_ROW_MAJOR"
    assert rectifier["rectified_encoding"] == "RGB8_INTERLEAVED_ROW_MAJOR"
    assert dict(rectifier["derived_rgb_colorimetry"]) == {
        "color_primaries": "SRGB_BT709",
        "transfer_characteristics": "SRGB",
        "matrix_coefficients": "IDENTITY_RGB",
        "quantization_range": "FULL_0_255",
        "chroma_siting": "NOT_APPLICABLE_RGB",
        "row_origin": "TOP_LEFT",
    }
    assert rectifier["used_for_pose_estimation"] is False
    assert rectifier["pose_rectification_path"] == (
        "ANALYTIC_PER_DETECTION_CORNER"
    )
    assert rectifier["physical_calibration_claim"] is False
    assert rectifier["optical_contract_sha256"] == (
        bridge_session.capture.optical_contract.content_sha256
    )


def test_wire_evidence_is_one_unsent_t105_and_synthetic_t1051_only(
    bridge_session: B0477SyntheticSensorSession,
) -> None:
    request = decode_line(bridge_session.session.t105_request_line)
    response = decode_line(bridge_session.session.t1051_response_line)
    assert request == {"T": 105}
    assert response["T"] == 1051
    assert response["simulation_fixture"] == B0477_SENSOR_SESSION_BRIDGE_SCHEMA
    assert response["capture_sha256"] == bridge_session.capture.content_sha256
    summary = bridge_session.to_dict()
    assert summary["wire_fixture"] == {
        "request": "T=105_UNSENT",
        "response": "T=1051_SYNTHETIC",
        "transport_invoked": False,
        "t104_representable": False,
    }
    assert summary["authority"] == {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "physical_release_effect": "NONE",
        "can_release_physical_gates": False,
        "live_capture_authority": False,
        "physical_calibration_authority": False,
        "robot_motion_authority": False,
        "contact_authority": False,
    }


def test_record_verify_and_replay_preserve_all_bridge_bytes(tmp_path: Path) -> None:
    result = record_and_replay_b0477_synthetic_sensor_session(
        WORKSPACE,
        tmp_path,
        sequence=212,
    )
    assert result.replay.status == "REPLAY_VERIFIED_SIMULATION_ONLY"
    assert result.status == B0477_SOURCE_BOUND_REPLAY_STATUS
    assert result.to_dict()["status"] == B0477_SOURCE_BOUND_REPLAY_STATUS
    assert result.to_dict()["generic_replay_status"] == result.replay.status
    assert result.to_dict()["verification_scope"] == (
        "EXACT_B0477_SOURCE_CONTRACT_DOCUMENTS_AND_BYTES"
    )
    assert result.replay.record.record_id == result.record.record_id
    assert result.replay.raw_frame_bytes == result.source.session.raw_frame_bytes
    assert (
        result.replay.decoded_frame_bytes
        == result.source.session.decoded_frame_bytes
    )
    assert (
        result.replay.undistorted_frame_bytes
        == result.source.session.undistorted_frame_bytes
    )
    detector = result.replay.record.document("perception.json")["detector_record"]
    restored = base64.b64decode("".join(detector["detector_input_jpeg"]["chunks"]), validate=True)
    assert restored == result.source.capture.jpeg_bytes
    assert set(path.name for path in result.record.directory.iterdir()) == {
        "contract.json",
        "camera.json",
        "timing.json",
        "raw-frame.bin",
        "decoded-frame.bin",
        "undistorted-frame.bin",
        "perception.json",
        "t105-request.line",
        "t1051-response.line",
        "manifest.json",
    }
    authority = cast(Mapping[str, object], result.to_dict()["authority"])
    assert authority["hardware_accessed"] is False


def test_base64_bounds_are_checked_before_aggregate_join(
    bridge_session: B0477SyntheticSensorSession,
) -> None:
    detector = _plain_json(bridge_session.session.detector_record)
    assert isinstance(detector, dict)
    encoded = detector["detector_input_jpeg"]
    assert isinstance(encoded, dict)
    maximum_encoded_chars = (
        (MAX_B0477_DETECTOR_INPUT_JPEG_BYTES + 2) // 3
    ) * 4
    maximum_chunks = (
        maximum_encoded_chars + MAX_B0477_JPEG_BASE64_CHUNK_CHARS - 1
    ) // MAX_B0477_JPEG_BASE64_CHUNK_CHARS

    # Every string is individually legal, but there are too many of them.
    encoded["chunks"] = ["AAAA"] * (maximum_chunks + 1)
    too_many_chunks = replace(
        bridge_session.session,
        detector_record=detector,
    )
    with pytest.raises(B0477SensorSessionBridgeError, match="chunks"):
        replace(bridge_session, session=too_many_chunks)

    # The legal maximum chunk count can still exceed the total encoded bound.
    encoded["chunks"] = [
        "A" * MAX_B0477_JPEG_BASE64_CHUNK_CHARS
    ] * maximum_chunks
    oversized_aggregate = replace(
        bridge_session.session,
        detector_record=detector,
    )
    with pytest.raises(B0477SensorSessionBridgeError, match="aggregate"):
        replace(bridge_session, session=oversized_aggregate)


def test_source_bound_replay_rejects_self_consistent_generic_perception_swap(
    bridge_session: B0477SyntheticSensorSession,
    tmp_path: Path,
) -> None:
    detector = _plain_json(bridge_session.session.detector_record)
    pose = _plain_json(bridge_session.session.pose_record)
    assert isinstance(detector, dict)
    assert isinstance(pose, dict)
    optical = detector["optical_contract"]
    rectifier = detector["full_frame_rectifier"]
    assert isinstance(optical, dict)
    assert isinstance(rectifier, dict)

    # This remains a perfectly self-consistent *generic* sensor package: its
    # manifest and perception hashes are freshly generated around the swapped
    # opaque records.  It is not evidence from the exact B0477 source.
    detector["scene_truth_supplied_to_detector"] = True
    optical["adversarial_substitution"] = "SELF_CONSISTENT_BUT_WRONG"
    rectifier["adversarial_substitution"] = "SELF_CONSISTENT_BUT_WRONG"
    pose["status"] = "ADVERSARIAL_SELF_CONSISTENT_STATUS"
    swapped_session = replace(
        bridge_session.session,
        detector_record=detector,
        pose_record=pose,
    )
    record = record_sensor_session(
        swapped_session,
        bridge_session.contract,
        tmp_path,
    )
    replay = replay_sensor_session(
        record.manifest_path,
        replay_contract=bridge_session.contract,
    )
    assert replay.status == "REPLAY_VERIFIED_SIMULATION_ONLY"
    with pytest.raises(
        B0477SensorSessionBridgeError,
        match="documents differ from the exact B0477 source",
    ):
        B0477RecordedSensorSession(
            source=bridge_session,
            record=record,
            replay=replay,
        )


def test_source_bound_replay_rejects_self_consistent_generic_contract_swap(
    bridge_session: B0477SyntheticSensorSession,
    tmp_path: Path,
) -> None:
    substituted_identity = replace(
        bridge_session.session.identity,
        serial_number="SIM-B0477-OTHER-GENERIC-PACKAGE",
    )
    substituted_contract = replace(
        bridge_session.contract,
        identity=substituted_identity,
    )
    substituted_session = replace(
        bridge_session.session,
        identity=substituted_identity,
    )
    record = record_sensor_session(
        substituted_session,
        substituted_contract,
        tmp_path,
    )
    replay = replay_sensor_session(
        record.manifest_path,
        replay_contract=substituted_contract,
    )
    assert replay.status == "REPLAY_VERIFIED_SIMULATION_ONLY"
    with pytest.raises(
        B0477SensorSessionBridgeError,
        match="contract differs from the B0477 source",
    ):
        B0477RecordedSensorSession(
            source=bridge_session,
            record=record,
            replay=replay,
        )


def test_tag_loss_rejection_is_recordable_without_inventing_a_pose(
    tmp_path: Path,
) -> None:
    result = record_and_replay_b0477_synthetic_sensor_session(
        WORKSPACE,
        tmp_path,
        sequence=213,
        mode=B0477StaticVisionMode.TAG_LOSS,
    )
    assert result.source.capture.report.status == "REJECTED"
    assert result.source.capture.pose_observation is None
    pose = result.replay.record.document("perception.json")["pose_record"]
    assert pose["schema"] == B0477_SENSOR_POSE_RECORD_SCHEMA
    assert pose["estimate_available"] is False
    assert pose["pose_observation"] is None
    assert pose["pose_observation_sha256"] is None


def test_capture_and_bridge_fail_closed_on_tamper_or_invalid_sequence(
    bridge_session: B0477SyntheticSensorSession,
) -> None:
    capture = bridge_session.capture
    changed = bytearray(capture.jpeg_bytes)
    changed[len(changed) // 2] ^= 1
    with pytest.raises(B0477StaticVisionError, match="JPEG differs"):
        replace(capture, jpeg_bytes=bytes(changed))

    over_authoritative = dict(bridge_session.full_frame_rectifier)
    authority_source = over_authoritative["authority"]
    assert isinstance(authority_source, Mapping)
    authority = dict(authority_source)
    authority["robot_motion_authority"] = True
    over_authoritative["authority"] = authority
    with pytest.raises(
        B0477SensorSessionBridgeError,
        match="rectifier provenance",
    ):
        replace(bridge_session, full_frame_rectifier=over_authoritative)

    detector = dict(bridge_session.session.detector_record)
    detector["scene_truth_supplied_to_detector"] = True
    forged_session = replace(
        bridge_session.session,
        detector_record=detector,
    )
    with pytest.raises(
        B0477SensorSessionBridgeError,
        match="complete B0477 perception evidence",
    ):
        replace(bridge_session, session=forged_session)

    for invalid in (0, -1, True, 1_000_000_001):
        with pytest.raises(B0477SensorSessionBridgeError, match="sequence"):
            build_b0477_synthetic_sensor_session(
                WORKSPACE,
                sequence=invalid,  # type: ignore[arg-type]
            )
    with pytest.raises(TypeError, match="mode"):
        build_b0477_synthetic_sensor_session(
            WORKSPACE,
            mode="NORMAL",  # type: ignore[arg-type]
        )
    with pytest.raises(FrozenInstanceError):
        bridge_session.schema = "forged"  # type: ignore[misc]
