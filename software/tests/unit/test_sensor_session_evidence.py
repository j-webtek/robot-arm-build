from __future__ import annotations

import hashlib
import json
import operator
import os
from dataclasses import replace
from pathlib import Path
from typing import Any

import pytest

from rocell.evidence.sensor_session import (
    CONTENT_SCHEMA,
    CameraControlSnapshot,
    CameraModeSnapshot,
    FramePixelLayouts,
    PixelBufferLayout,
    RawSensorSessionInput,
    ReplayedSensorSession,
    SensorSessionContract,
    SensorSessionEvidenceError,
    SensorTimingBracket,
    SyntheticCameraIdentity,
    VerifiedSensorSessionRecord,
    record_sensor_session,
    replay_sensor_session,
    verify_sensor_session_record,
)


def _canonical_bytes(value: object) -> bytes:
    return (
        json.dumps(
            value,
            indent=2,
            sort_keys=True,
            ensure_ascii=True,
            allow_nan=False,
        )
        + "\n"
    ).encode("utf-8")


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def test_sensor_session_contract_is_intentionally_exported() -> None:
    import rocell.evidence as evidence

    assert evidence.RawSensorSessionInput is RawSensorSessionInput
    assert evidence.SensorSessionContract is SensorSessionContract
    assert evidence.record_sensor_session is record_sensor_session
    assert evidence.replay_sensor_session is replay_sensor_session
    assert evidence.FramePixelLayouts is FramePixelLayouts
    assert evidence.PixelBufferLayout is PixelBufferLayout
    assert evidence.RAW_SENSOR_SESSION_CONTENT_SCHEMA == CONTENT_SCHEMA
    assert (
        evidence.RAW_SENSOR_SESSION_PIXEL_LAYOUT_SCHEMA
        == "rocell.raw_sensor_session_pixel_layout.v2"
    )


@pytest.fixture
def identity() -> SyntheticCameraIdentity:
    return SyntheticCameraIdentity(
        manufacturer="Arducam",
        model="B0477",
        sensor="IMX283",
        vid="2bc5",
        pid="b047",
        serial_number="SIM-B0477-0001",
        device_key="fake-uvc:0",
    )


@pytest.fixture
def mode() -> CameraModeSnapshot:
    # Small buffers keep the strict byte-layout tests fast while exercising the
    # same packed/interleaved rules as the full B0477 raster.
    return CameraModeSnapshot(8, 6, 60, 1, "YUY2")


@pytest.fixture
def controls() -> CameraControlSnapshot:
    return CameraControlSnapshot(
        exposure_us=8_000,
        gain_milli_db=3_000,
        white_balance_kelvin=4_500,
        focus_position=16_000,
    )


@pytest.fixture
def timing() -> SensorTimingBracket:
    return SensorTimingBracket(
        frame_sequence=41,
        event_monotonic_ns=(100, 110, 120, 130, 140, 150, 160, 170, 180),
    )


@pytest.fixture
def contract(
    identity: SyntheticCameraIdentity,
    mode: CameraModeSnapshot,
    controls: CameraControlSnapshot,
) -> SensorSessionContract:
    return SensorSessionContract(
        identity=identity,
        mode=mode,
        controls=controls,
        calibration_sha256="a" * 64,
        minimum_frame_sequence_exclusive=40,
        not_before_monotonic_ns=125,
        maximum_frame_age_ns=20,
        maximum_feedback_latency_ns=20,
    )


@pytest.fixture
def session(
    identity: SyntheticCameraIdentity,
    mode: CameraModeSnapshot,
    controls: CameraControlSnapshot,
    timing: SensorTimingBracket,
) -> RawSensorSessionInput:
    return RawSensorSessionInput(
        identity=identity,
        mode=mode,
        controls=controls,
        timing=timing,
        raw_frame_bytes=bytes([41]) * mode.pixel_layouts.raw.expected_byte_length,
        decoded_frame_bytes=bytes([42])
        * mode.pixel_layouts.decoded.expected_byte_length,
        undistorted_frame_bytes=bytes([43])
        * mode.pixel_layouts.undistorted.expected_byte_length,
        detector_record={
            "schema": "rocell.fake_detector_record.v1",
            "detected_tag_ids": [0, 1, 2, 3],
            "accepted": True,
        },
        pose_record={
            "schema": "rocell.fake_pose_record.v1",
            "camera_frame": "camera_b0477_static_overhead_optical",
            "board_frame": "board",
            "accepted": True,
        },
        t105_request_line=b'{"T":105}\n',
        t1051_response_line=(
            b'{"T":1051,"x":1.0,"y":2.0,"z":3.0,"v":1200}\n'
        ),
    )


def _read_manifest(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    assert isinstance(value, dict)
    return value


def _rewrite_manifest(path: Path, manifest: dict[str, Any]) -> None:
    core = dict(manifest)
    core.pop("package_sha256", None)
    manifest["package_sha256"] = _stable_hash(core)
    path.write_bytes(_canonical_bytes(manifest))


def _rehash_one_artifact(manifest_path: Path, name: str) -> None:
    manifest = _read_manifest(manifest_path)
    rows = manifest["artifacts"]
    assert isinstance(rows, list)
    payload = (manifest_path.parent / name).read_bytes()
    row = next(item for item in rows if item["path"] == name)
    row["bytes"] = len(payload)
    row["sha256"] = hashlib.sha256(payload).hexdigest()
    manifest["total_artifact_bytes"] = sum(item["bytes"] for item in rows)
    _rewrite_manifest(manifest_path, manifest)


def _fully_readdress(manifest_path: Path) -> Path:
    """Rebuild all outer hashes so semantic checks, not envelopes, are tested."""

    manifest = _read_manifest(manifest_path)
    rows = manifest["artifacts"]
    assert isinstance(rows, list)
    manifest["content_sha256"] = _stable_hash(
        {"schema": CONTENT_SCHEMA, "artifacts": rows}
    )
    record_id = f"sensor-session-{manifest['content_sha256']}"
    manifest["record_id"] = record_id
    _rewrite_manifest(manifest_path, manifest)
    rebound = manifest_path.parent.parent / record_id
    manifest_path.parent.rename(rebound)
    return rebound / "manifest.json"


def test_record_verify_and_replay_are_byte_exact_and_zero_authority(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    assert record.record_id == f"sensor-session-{record.content_sha256}"
    assert record.manifest_path.exists()
    manifest_mtime = record.manifest_path.stat().st_mtime_ns
    assert all(
        manifest_mtime >= child.stat().st_mtime_ns
        for child in record.directory.iterdir()
        if child.name != "manifest.json"
    )

    verified = verify_sensor_session_record(record.manifest_path)
    assert verified.blob("raw-frame.bin") == session.raw_frame_bytes
    assert verified.blob("t105-request.line") == b'{"T":105}\n'
    assert verified.feedback_message["T"] == 1051
    assert verified.timing.frame_sequence == 41
    with pytest.raises(TypeError):
        operator.setitem(  # type: ignore[call-overload]
            verified.document("perception.json"), "schema", "forged"
        )

    replay = replay_sensor_session(record.manifest_path)
    assert replay.status == "REPLAY_VERIFIED_SIMULATION_ONLY"
    assert replay.raw_frame_bytes == session.raw_frame_bytes
    assert replay.to_dict()["authority"] == {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "synthetic_t105_request_lines_recorded": 1,
        "physical_t105_requests_sent": 0,
        "physical_t104_motion_requests_sent": 0,
        "physical_release_effect": "NONE",
        "can_release_physical_gates": False,
    }


def test_content_address_is_deterministic_but_same_root_cannot_overwrite(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    left = tmp_path / "left"
    right = tmp_path / "right"
    left.mkdir()
    right.mkdir()
    first = record_sensor_session(session, contract, left)
    second = record_sensor_session(session, contract, right)
    assert first.record_id == second.record_id
    assert first.manifest_sha256 == second.manifest_sha256
    with pytest.raises(SensorSessionEvidenceError, match="immutable sensor record"):
        record_sensor_session(session, contract, left)


def test_caller_owned_perception_payload_is_detached(
    tmp_path: Path,
    identity: SyntheticCameraIdentity,
    mode: CameraModeSnapshot,
    controls: CameraControlSnapshot,
    timing: SensorTimingBracket,
    contract: SensorSessionContract,
) -> None:
    detector: dict[str, Any] = {
        "schema": "rocell.fake_detector_record.v1",
        "ids": [0, 1],
    }
    value = RawSensorSessionInput(
        identity,
        mode,
        controls,
        timing,
        bytes([1]) * mode.pixel_layouts.raw.expected_byte_length,
        bytes([2]) * mode.pixel_layouts.decoded.expected_byte_length,
        bytes([3]) * mode.pixel_layouts.undistorted.expected_byte_length,
        detector,
        {"schema": "rocell.fake_pose_record.v1", "accepted": True},
        b'{"T":105}\n',
        b'{"T":1051,"x":0}\n',
    )
    detector["ids"].append(99)
    record = record_sensor_session(value, contract, tmp_path)
    verified = verify_sensor_session_record(record.manifest_path)
    assert verified.document("perception.json")["detector_record"]["ids"] == (0, 1)


@pytest.mark.parametrize("kind", ["missing", "extra"])
def test_missing_or_extra_files_are_rejected(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
    kind: str,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    if kind == "missing":
        (record.directory / "decoded-frame.bin").unlink()
    else:
        (record.directory / "unexpected.bin").write_bytes(b"extra")
    with pytest.raises(SensorSessionEvidenceError, match="directory is not exact"):
        verify_sensor_session_record(record.manifest_path)


def test_binary_tamper_is_rejected(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    (record.directory / "raw-frame.bin").write_bytes(b"tampered")
    with pytest.raises(SensorSessionEvidenceError, match="byte/hash mismatch"):
        verify_sensor_session_record(record.manifest_path)


@pytest.mark.parametrize("mutation", ["reorder", "duplicate", "escape"])
def test_manifest_reorder_duplicate_and_path_escape_are_rejected(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
    mutation: str,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    manifest = _read_manifest(record.manifest_path)
    rows = manifest["artifacts"]
    if mutation == "reorder":
        rows[0], rows[1] = rows[1], rows[0]
    elif mutation == "duplicate":
        rows[1] = dict(rows[0])
    else:
        rows[0]["path"] = "../contract.json"
    _rewrite_manifest(record.manifest_path, manifest)
    with pytest.raises(
        SensorSessionEvidenceError,
        match="reordered, missing, or duplicated|unsafe",
    ):
        verify_sensor_session_record(record.manifest_path)


def test_external_artifact_symlink_is_rejected(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    artifact = record.directory / "raw-frame.bin"
    outside = tmp_path / "outside.bin"
    outside.write_bytes(artifact.read_bytes())
    artifact.unlink()
    try:
        artifact.symlink_to(outside)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"artifact symlinks are unavailable: {exc}")
    with pytest.raises(SensorSessionEvidenceError, match="directory is not exact|escapes"):
        verify_sensor_session_record(record.manifest_path)


def test_duplicate_json_keys_are_rejected_even_when_outer_row_is_rehashed(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    contract_path = record.directory / "contract.json"
    payload = contract_path.read_bytes().replace(
        b'{\n  "authority"',
        b'{\n  "schema": "duplicate",\n  "authority"',
        1,
    )
    contract_path.write_bytes(payload)
    _rehash_one_artifact(record.manifest_path, "contract.json")
    with pytest.raises(SensorSessionEvidenceError, match="duplicate JSON key"):
        verify_sensor_session_record(record.manifest_path)


def test_reauthored_wrong_mode_is_rejected_semantically(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    camera_path = record.directory / "camera.json"
    camera = json.loads(camera_path.read_text(encoding="utf-8"))
    camera["observed_mode"]["width_px"] = 1280
    camera["snapshot_sha256"]["observed_mode"] = _stable_hash(camera["observed_mode"])
    camera_path.write_bytes(_canonical_bytes(camera))
    _rehash_one_artifact(record.manifest_path, "camera.json")
    rebound = _fully_readdress(record.manifest_path)
    with pytest.raises(
        SensorSessionEvidenceError,
        match="observed camera mode is wrong|pixel layouts do not match",
    ):
        verify_sensor_session_record(rebound)


def test_reauthored_reordered_timing_is_rejected_semantically(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    timing_path = record.directory / "timing.json"
    timing_doc = json.loads(timing_path.read_text(encoding="utf-8"))
    timing_doc["events"][2], timing_doc["events"][3] = (
        timing_doc["events"][3],
        timing_doc["events"][2],
    )
    timing_path.write_bytes(_canonical_bytes(timing_doc))
    _rehash_one_artifact(record.manifest_path, "timing.json")
    rebound = _fully_readdress(record.manifest_path)
    with pytest.raises(SensorSessionEvidenceError, match="reordered or duplicated"):
        verify_sensor_session_record(rebound)


def test_wrong_mode_cannot_be_recorded(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    wrong_mode = CameraModeSnapshot(10, 6, 120, 1, "YUY2")
    wrong = RawSensorSessionInput(
        session.identity,
        wrong_mode,
        session.controls,
        session.timing,
        bytes([1]) * wrong_mode.pixel_layouts.raw.expected_byte_length,
        bytes([2]) * wrong_mode.pixel_layouts.decoded.expected_byte_length,
        bytes([3]) * wrong_mode.pixel_layouts.undistorted.expected_byte_length,
        session.detector_record,
        session.pose_record,
        session.t105_request_line,
        session.t1051_response_line,
    )
    with pytest.raises(SensorSessionEvidenceError, match="observed camera mode"):
        record_sensor_session(wrong, contract, tmp_path)


@pytest.mark.parametrize(
    ("minimum_sequence", "not_before", "message"),
    [(41, 125, "sequence is stale"), (40, 131, "predates the freshness")],
)
def test_stale_inputs_cannot_be_recorded(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
    minimum_sequence: int,
    not_before: int,
    message: str,
) -> None:
    stale = SensorSessionContract(
        contract.identity,
        contract.mode,
        contract.controls,
        contract.calibration_sha256,
        minimum_sequence,
        not_before,
        contract.maximum_frame_age_ns,
        contract.maximum_feedback_latency_ns,
    )
    with pytest.raises(SensorSessionEvidenceError, match=message):
        record_sensor_session(session, stale, tmp_path)


def test_replay_applies_a_newer_freshness_boundary(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    newer = SensorSessionContract(
        contract.identity,
        contract.mode,
        contract.controls,
        contract.calibration_sha256,
        minimum_frame_sequence_exclusive=41,
        not_before_monotonic_ns=125,
        maximum_frame_age_ns=20,
        maximum_feedback_latency_ns=20,
    )
    with pytest.raises(SensorSessionEvidenceError, match="sequence is stale"):
        replay_sensor_session(record.manifest_path, replay_contract=newer)


@pytest.mark.parametrize(
    ("request_line", "response_line", "message"),
    [
        (b'{"T":105,"extra":1}\n', b'{"T":1051}\n', "exactly one T=105"),
        (b'{"T":105}\n', b'{"T":104}\n', "invalid recorded T=1051"),
        (b'{"T":105}\n', b'{"T":1051', "invalid recorded T=1051"),
    ],
)
def test_invalid_wire_inputs_cannot_be_recorded(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
    request_line: bytes,
    response_line: bytes,
    message: str,
) -> None:
    invalid = RawSensorSessionInput(
        session.identity,
        session.mode,
        session.controls,
        session.timing,
        session.raw_frame_bytes,
        session.decoded_frame_bytes,
        session.undistorted_frame_bytes,
        session.detector_record,
        session.pose_record,
        request_line,
        response_line,
    )
    with pytest.raises(SensorSessionEvidenceError, match=message):
        record_sensor_session(invalid, contract, tmp_path)


def test_prebuffered_feedback_and_duplicate_timestamps_are_rejected() -> None:
    with pytest.raises(SensorSessionEvidenceError, match="strictly increasing"):
        SensorTimingBracket(41, (100, 110, 120, 130, 140, 150, 160, 160, 180))
    with pytest.raises(SensorSessionEvidenceError, match="already buffered"):
        SensorTimingBracket(
            41,
            (100, 110, 120, 130, 140, 150, 160, 170, 180),
            feedback_receive_buffer_bytes_before_request=1,
        )


def test_symlinked_evidence_root_is_rejected(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    real = tmp_path / "real"
    linked = tmp_path / "linked"
    real.mkdir()
    try:
        linked.symlink_to(real, target_is_directory=True)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"directory symlinks are unavailable: {exc}")
    assert os.path.lexists(linked)
    with pytest.raises(SensorSessionEvidenceError, match="root must not be a symlink"):
        record_sensor_session(session, contract, linked)


def test_freshness_bounds_capture_through_completed_perception_not_just_receive(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    # Capture-to-receive remains only 10 ns, while perception finishes 21 ns
    # after capture and therefore exceeds the 20 ns freshness policy.
    late_perception = replace(
        session.timing,
        event_monotonic_ns=(100, 110, 120, 130, 140, 151, 160, 170, 180),
    )
    value = replace(session, timing=late_perception)

    with pytest.raises(SensorSessionEvidenceError, match="capture-to-perception"):
        record_sensor_session(value, contract, tmp_path)


@pytest.mark.parametrize(
    ("stage_limit", "session_limit", "message"),
    [
        (9, 80, "timing stage"),
        (10, 79, "session exceeded"),
    ],
)
def test_stage_and_complete_session_durations_are_independently_bounded(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
    stage_limit: int,
    session_limit: int,
    message: str,
) -> None:
    bounded = replace(
        contract,
        maximum_stage_duration_ns=stage_limit,
        maximum_session_duration_ns=session_limit,
    )
    with pytest.raises(SensorSessionEvidenceError, match=message):
        record_sensor_session(session, bounded, tmp_path)


def test_pixel_layout_metadata_is_explicit_and_byte_lengths_are_exact(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    raw = session.mode.pixel_layouts.raw
    decoded = session.mode.pixel_layouts.decoded
    undistorted = session.mode.pixel_layouts.undistorted
    assert raw.pixel_format == "YUY2"
    assert raw.pixel_layout == "PACKED_Y0_U0_Y1_V0_422"
    assert raw.row_stride_bytes == session.mode.width_px * 2
    assert raw.channels == ("Y", "U", "V")
    assert raw.channel_count == 3
    assert raw.bits_per_channel == 8
    assert raw.endianness == "NOT_APPLICABLE_8_BIT"
    assert decoded.pixel_format == undistorted.pixel_format == "RGB8"
    assert decoded.row_stride_bytes == undistorted.row_stride_bytes == 24
    assert decoded.channels == undistorted.channels == ("R", "G", "B")

    record = record_sensor_session(session, contract, tmp_path)
    verified = verify_sensor_session_record(record.manifest_path)
    selected_mode = verified.document("camera.json")["selected_mode"]
    assert selected_mode["pixel_layouts"]["raw"]["expected_byte_length"] == 96
    assert selected_mode["pixel_layouts"]["decoded"]["expected_byte_length"] == 144


@pytest.mark.parametrize(
    "field_name",
    ("raw_frame_bytes", "decoded_frame_bytes", "undistorted_frame_bytes"),
)
def test_each_image_boundary_rejects_even_one_missing_byte(
    session: RawSensorSessionInput,
    field_name: str,
) -> None:
    shortened = getattr(session, field_name)[:-1]
    with pytest.raises(SensorSessionEvidenceError, match="pixel layout"):
        replace(session, **{field_name: shortened})


def test_unsupported_or_internally_inconsistent_pixel_layouts_are_rejected() -> None:
    with pytest.raises(SensorSessionEvidenceError, match="YUY2 width must be even"):
        CameraModeSnapshot(7, 6, 60, 1, "YUY2")
    with pytest.raises(SensorSessionEvidenceError, match="currently supports YUY2"):
        CameraModeSnapshot(8, 6, 60, 1, "RGB8")
    with pytest.raises(SensorSessionEvidenceError, match="layout metadata is not exact"):
        PixelBufferLayout(
            pixel_format="YUY2",
            pixel_layout="PACKED_Y0_U0_Y1_V0_422",
            width_px=8,
            height_px=6,
            row_stride_bytes=17,
            channels=("Y", "U", "V"),
            bits_per_channel=8,
            endianness="NOT_APPLICABLE_8_BIT",
            color_primaries="SRGB_BT709",
            transfer_characteristics="SRGB",
            matrix_coefficients="BT601_YCBCR",
            quantization_range="FULL_Y0_255_C0_255",
            chroma_siting="COSITED_LEFT_422",
            row_origin="TOP_LEFT",
        )


@pytest.mark.parametrize(
    ("field_name", "wrong_value"),
    (
        ("color_primaries", "BT601"),
        ("transfer_characteristics", "LINEAR"),
        ("matrix_coefficients", "BT709_YCBCR"),
        ("quantization_range", "LIMITED_Y16_235_C16_240"),
        ("chroma_siting", "CENTERED_422"),
        ("row_origin", "BOTTOM_LEFT"),
    ),
)
def test_yuy2_color_and_orientation_interpretation_is_exact(
    field_name: str, wrong_value: str
) -> None:
    layout = PixelBufferLayout.packed_yuy2(8, 6)

    with pytest.raises(SensorSessionEvidenceError, match="layout metadata is not exact"):
        replace(layout, **{field_name: wrong_value})


def test_rgb8_color_and_orientation_interpretation_is_explicit() -> None:
    layout = PixelBufferLayout.interleaved_rgb8(8, 6)

    assert layout.color_primaries == "SRGB_BT709"
    assert layout.transfer_characteristics == "SRGB"
    assert layout.matrix_coefficients == "IDENTITY_RGB"
    assert layout.quantization_range == "FULL_0_255"
    assert layout.chroma_siting == "NOT_APPLICABLE_RGB"
    assert layout.row_origin == "TOP_LEFT"


def test_reauthored_wrong_binary_length_fails_after_all_outer_hashes_are_rebuilt(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    raw_path = record.directory / "raw-frame.bin"
    raw_path.write_bytes(raw_path.read_bytes() + b"x")
    _rehash_one_artifact(record.manifest_path, "raw-frame.bin")
    rebound = _fully_readdress(record.manifest_path)

    with pytest.raises(SensorSessionEvidenceError, match="pixel layout"):
        verify_sensor_session_record(rebound)


def test_replay_discloses_and_hash_binds_stored_and_stricter_applied_contracts(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    baseline = replay_sensor_session(record.manifest_path)
    stricter = replace(
        contract,
        not_before_monotonic_ns=126,
        maximum_stage_duration_ns=10,
        maximum_session_duration_ns=80,
    )
    replayed = replay_sensor_session(record.manifest_path, replay_contract=stricter)
    document = replayed.to_dict()

    assert baseline.replay_sha256 != replayed.replay_sha256
    assert document["contract_override_applied"] is True
    assert document["stored_contract"] == contract.to_dict()
    assert document["applied_contract"] == stricter.to_dict()
    assert document["stored_contract_sha256"] != document["applied_contract_sha256"]
    assert replayed.record.contract == contract
    assert replayed.record.applied_contract == stricter


@pytest.mark.parametrize(
    "weaker_contract",
    (
        lambda value: replace(value, minimum_frame_sequence_exclusive=39),
        lambda value: replace(value, not_before_monotonic_ns=124),
        lambda value: replace(value, maximum_frame_age_ns=21),
        lambda value: replace(value, maximum_feedback_latency_ns=21),
        lambda value: replace(
            value,
            maximum_stage_duration_ns=value.maximum_stage_duration_ns + 1,
        ),
        lambda value: replace(
            value,
            maximum_session_duration_ns=value.maximum_session_duration_ns + 1,
        ),
    ),
)
def test_replay_contract_cannot_relax_any_independent_policy_bound(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
    weaker_contract: Any,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    selected = weaker_contract(contract)
    with pytest.raises(SensorSessionEvidenceError, match="replay contract weakens"):
        replay_sensor_session(record.manifest_path, replay_contract=selected)


def test_replay_contract_cannot_change_identity_mode_controls_or_calibration(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    changed = replace(contract, calibration_sha256="b" * 64)
    with pytest.raises(SensorSessionEvidenceError, match="stored calibration binding"):
        replay_sensor_session(record.manifest_path, replay_contract=changed)


def test_verified_and_replayed_records_cannot_be_directly_forged_or_replaced(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    verified = verify_sensor_session_record(record.manifest_path)
    replayed = replay_sensor_session(record.manifest_path)

    with pytest.raises(SensorSessionEvidenceError, match="strict verification"):
        VerifiedSensorSessionRecord(
            record_id=verified.record_id,
            directory=verified.directory,
            manifest_sha256=verified.manifest_sha256,
            content_sha256=verified.content_sha256,
            contract=verified.contract,
            applied_contract=verified.applied_contract,
            stored_contract_sha256=verified.stored_contract_sha256,
            applied_contract_sha256=verified.applied_contract_sha256,
            identity=verified.identity,
            mode=verified.mode,
            controls=verified.controls,
            timing=verified.timing,
            calibration_sha256=verified.calibration_sha256,
            documents=verified.documents,
            blobs=verified.blobs,
            feedback_message=verified.feedback_message,
            _factory_token=object(),
        )
    with pytest.raises(SensorSessionEvidenceError, match="strict verification"):
        replace(
            verified,
            content_sha256="0" * 64,
            _factory_token=object(),
        )
    with pytest.raises(SensorSessionEvidenceError, match="strict replay"):
        ReplayedSensorSession(
            record=verified,
            replay_sha256=replayed.replay_sha256,
            _factory_token=object(),
        )
    with pytest.raises(SensorSessionEvidenceError, match="strict replay"):
        replace(
            replayed,
            replay_sha256="0" * 64,
            _factory_token=object(),
        )


def test_v1_contract_without_layout_and_duration_evidence_is_rejected(
    tmp_path: Path,
    session: RawSensorSessionInput,
    contract: SensorSessionContract,
) -> None:
    record = record_sensor_session(session, contract, tmp_path)
    contract_path = record.directory / "contract.json"
    document = json.loads(contract_path.read_text(encoding="utf-8"))
    document["schema"] = "rocell.raw_sensor_session_contract.v1"
    contract_path.write_bytes(_canonical_bytes(document))
    _rehash_one_artifact(record.manifest_path, "contract.json")
    rebound = _fully_readdress(record.manifest_path)

    with pytest.raises(SensorSessionEvidenceError, match="simulation-only v2"):
        verify_sensor_session_record(rebound)
