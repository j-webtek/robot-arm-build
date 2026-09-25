"""Record and replay the B0477 pixel rehearsal as raw sensor evidence.

This is a deliberately narrow bridge between two existing simulation-only
boundaries:

* :mod:`rocell.application.b0477_static_vision` creates exact synthetic JPEG,
  detector, rectifier, and pose evidence for the selected B0477 architecture;
* :mod:`rocell.evidence.sensor_session` writes and verifies an immutable raw
  session package.

The bridge uses only public APIs from those modules.  It has no live camera or
serial adapter.  Its one ``T=105`` request line is generated as an *unsent*
fixture and paired with a synthetic ``T=1051`` response.  It cannot represent
``T=104``, open hardware, or release calibration, motion, or contact gates.
"""

from __future__ import annotations

import base64
import binascii
from dataclasses import dataclass
import hashlib
from io import BytesIO
import json
from pathlib import Path
from types import MappingProxyType
from typing import Any, Mapping

from rocell.arm.protocol import ProtocolError, decode_line, encode_line, feedback_request
from rocell.evidence.sensor_session import (
    CAMERA_SCHEMA,
    PERCEPTION_SCHEMA,
    CameraControlSnapshot,
    CameraModeSnapshot,
    RawSensorSessionInput,
    ReplayedSensorSession,
    SensorSessionContract,
    SensorSessionEvidenceError,
    SensorSessionRecord,
    SensorTimingBracket,
    SyntheticCameraIdentity,
    record_sensor_session,
    replay_sensor_session,
)

from .b0477_static_vision import (
    MAX_B0477_REHEARSAL_SEQUENCE,
    B0477StaticVisionCapture,
    B0477StaticVisionMode,
    run_b0477_static_vision_capture_rehearsal,
)


B0477_SENSOR_SESSION_BRIDGE_SCHEMA = "rocell.b0477_sensor_session_bridge.v1"
B0477_SENSOR_DETECTOR_RECORD_SCHEMA = (
    "rocell.b0477_sensor_session_detector_record.v1"
)
B0477_SENSOR_POSE_RECORD_SCHEMA = "rocell.b0477_sensor_session_pose_record.v1"
B0477_FULL_FRAME_RECTIFIER_SCHEMA = "rocell.b0477_pillow_mesh_rectifier.v1"

# A 64-pixel grid gives 1,247 cells at the 2736 x 1824 rehearsal resolution.
# It is fine enough for an evidence-only visualization of the deliberately
# modest stress distortion while remaining comfortably bounded.  Pose fitting
# continues to use the optical contract's analytic corner rectifier, not this
# approximate full-frame raster.
B0477_RECTIFICATION_MESH_STEP_PX = 64
MAX_B0477_RECTIFICATION_MESH_CELLS = 4_096
MAX_B0477_JPEG_BASE64_CHUNK_CHARS = 16_000
MAX_B0477_DETECTOR_INPUT_JPEG_BYTES = 600 * 1024

# Base64 expands three input bytes into four ASCII characters.  These derived
# limits let validation reject an attacker-controlled chunk tuple before
# ``"".join`` allocates a second, potentially oversized string.
_MAX_B0477_DETECTOR_INPUT_JPEG_BASE64_CHARS = (
    (MAX_B0477_DETECTOR_INPUT_JPEG_BYTES + 2) // 3
) * 4
_MAX_B0477_DETECTOR_INPUT_JPEG_BASE64_CHUNKS = (
    _MAX_B0477_DETECTOR_INPUT_JPEG_BASE64_CHARS
    + MAX_B0477_JPEG_BASE64_CHUNK_CHARS
    - 1
) // MAX_B0477_JPEG_BASE64_CHUNK_CHARS

B0477_SOURCE_BOUND_REPLAY_STATUS = (
    "B0477_SOURCE_BOUND_REPLAY_VERIFIED_SIMULATION_ONLY"
)

_ZERO_AUTHORITY = {
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


class B0477SensorSessionBridgeError(ValueError):
    """The synthetic capture cannot be represented as coherent evidence."""


def _json_value(value: Any) -> Any:
    """Detach immutable mapping/tuple records into plain JSON containers."""

    if isinstance(value, Mapping):
        return {str(key): _json_value(child) for key, child in value.items()}
    if isinstance(value, (list, tuple)):
        return [_json_value(child) for child in value]
    return value


def _freeze_json(value: Any) -> Any:
    if isinstance(value, Mapping):
        return MappingProxyType(
            {str(key): _freeze_json(child) for key, child in value.items()}
        )
    if isinstance(value, (list, tuple)):
        return tuple(_freeze_json(child) for child in value)
    return value


def _canonical_hash(value: object) -> str:
    try:
        payload = json.dumps(
            _json_value(value),
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise B0477SensorSessionBridgeError(
            f"B0477 sensor bridge value is not canonical JSON: {exc}"
        ) from exc
    return hashlib.sha256(payload).hexdigest()


def _bounded_bridge_sequence(value: object) -> int:
    # SensorTimingBracket reserves zero as "no frame"; the underlying static
    # renderer also accepts zero for legacy use, but evidence sessions do not.
    if (
        isinstance(value, bool)
        or not isinstance(value, int)
        or value < 1
        or value > MAX_B0477_REHEARSAL_SEQUENCE
    ):
        raise B0477SensorSessionBridgeError(
            "B0477 sensor-session sequence must be an integer within "
            f"[1, {MAX_B0477_REHEARSAL_SEQUENCE}]"
        )
    return value


def _jpeg_base64_chunks(payload: bytes) -> tuple[str, ...]:
    """Encode a bounded binary detector input without one oversized JSON string."""

    if (
        not isinstance(payload, bytes)
        or not payload
        or len(payload) > MAX_B0477_DETECTOR_INPUT_JPEG_BYTES
    ):
        raise B0477SensorSessionBridgeError(
            "B0477 detector-input JPEG exceeds its bridge evidence bound"
        )
    encoded = base64.b64encode(payload).decode("ascii")
    chunks = tuple(
        encoded[offset : offset + MAX_B0477_JPEG_BASE64_CHUNK_CHARS]
        for offset in range(0, len(encoded), MAX_B0477_JPEG_BASE64_CHUNK_CHARS)
    )
    if not chunks or any(
        len(chunk) > MAX_B0477_JPEG_BASE64_CHUNK_CHARS for chunk in chunks
    ):
        raise B0477SensorSessionBridgeError(
            "B0477 detector-input JPEG chunking exceeded its bound"
        )
    return chunks


def _decode_and_rectify_rasters(
    capture: B0477StaticVisionCapture,
) -> tuple[bytes, bytes, bytes, Mapping[str, object]]:
    """Create exact YUY2 raw and RGB8 decoded/rectified evidence buffers.

    Pillow's mesh transform maps each destination (undistorted) tile to a
    source (distorted) quadrilateral.  The exact analytic Brown-Conrady map is
    evaluated at every tile corner.  This raster is retained for record/replay
    evidence only; the pose estimate is the independently hash-bound analytic
    corner-rectification path in ``capture.rectified_detection_batch``.
    """

    try:
        from PIL import Image, __version__ as pillow_version
    except (ImportError, ModuleNotFoundError) as exc:  # pragma: no cover
        raise B0477SensorSessionBridgeError(
            "B0477 sensor-session raster evidence requires Pillow"
        ) from exc
    try:
        decoded = Image.open(BytesIO(capture.jpeg_bytes)).convert("L")
        decoded.load()
    except Exception as exc:
        raise B0477SensorSessionBridgeError(
            "B0477 capture JPEG could not be decoded for evidence"
        ) from exc

    contract = capture.optical_contract
    expected_size = (contract.width_px, contract.height_px)
    if decoded.size != expected_size:
        raise B0477SensorSessionBridgeError(
            "decoded B0477 raster differs from the optical contract resolution"
        )
    mesh: list[
        tuple[tuple[int, int, int, int], tuple[float, ...]]
    ] = []
    step = B0477_RECTIFICATION_MESH_STEP_PX
    for top in range(0, contract.height_px, step):
        bottom = min(top + step, contract.height_px)
        for left in range(0, contract.width_px, step):
            right = min(left + step, contract.width_px)
            upper_left = contract.distort_rectified_pixel(float(left), float(top))
            lower_left = contract.distort_rectified_pixel(
                float(left), float(bottom)
            )
            lower_right = contract.distort_rectified_pixel(
                float(right), float(bottom)
            )
            upper_right = contract.distort_rectified_pixel(
                float(right), float(top)
            )
            quad = tuple(
                coordinate
                for point in (upper_left, lower_left, lower_right, upper_right)
                for coordinate in point
            )
            mesh.append(((left, top, right, bottom), quad))
    if not mesh or len(mesh) > MAX_B0477_RECTIFICATION_MESH_CELLS:
        raise B0477SensorSessionBridgeError(
            "B0477 rectification mesh exceeds its fixed cell limit"
        )

    try:
        rectified = decoded.transform(
            expected_size,
            Image.Transform.MESH,
            mesh,
            resample=Image.Resampling.BILINEAR,
            fillcolor=0,
        )
    except Exception as exc:
        raise B0477SensorSessionBridgeError(
            "B0477 full-frame synthetic rectification failed"
        ) from exc
    decoded_l8 = decoded.tobytes()
    rectified_l8 = rectified.tobytes()
    pixel_count = contract.width_px * contract.height_px
    if len(decoded_l8) != pixel_count or len(rectified_l8) != pixel_count:
        raise B0477SensorSessionBridgeError(
            "B0477 L8 raster byte counts differ from their resolution"
        )

    # Future physical B0477 acquisition is locked to the camera's published
    # YUY2 wire layout.  The renderer emits a full-range grayscale JPEG, so this
    # fixture deterministically packs each adjacent luminance pair as
    # Y0/U0/Y1/V0 with neutral chroma.  This is explicitly full-range synthetic
    # JPEG-derived YCbCr; a future physical adapter must record the real UVC
    # driver's negotiated colorimetry instead of inheriting this fixture.
    # The decoded and rectified evidence uses explicit full-range sRGB RGB8.
    if contract.width_px % 2:
        raise B0477SensorSessionBridgeError(
            "YUY2 evidence requires an even B0477 frame width"
        )
    pair_count = pixel_count // 2
    raw_yuy2 = bytearray(pixel_count * 2)
    raw_yuy2[0::4] = decoded_l8[0::2]
    raw_yuy2[1::4] = b"\x80" * pair_count
    raw_yuy2[2::4] = decoded_l8[1::2]
    raw_yuy2[3::4] = b"\x80" * pair_count
    decoded_rgb8 = decoded.convert("RGB").tobytes()
    rectified_rgb8 = rectified.convert("RGB").tobytes()
    if (
        len(raw_yuy2) != pixel_count * 2
        or len(decoded_rgb8) != pixel_count * 3
        or len(rectified_rgb8) != pixel_count * 3
    ):
        raise B0477SensorSessionBridgeError(
            "B0477 evidence buffers differ from their declared pixel layouts"
        )
    provenance: Mapping[str, object] = {
        "schema": B0477_FULL_FRAME_RECTIFIER_SCHEMA,
        "backend": {"id": "Pillow", "version": str(pillow_version)},
        "algorithm": "DESTINATION_TILE_TO_DISTORTED_SOURCE_QUAD",
        "resampling": "BILINEAR",
        "mesh_step_px": step,
        "mesh_cell_count": len(mesh),
        "resolution_px": [contract.width_px, contract.height_px],
        "raw_encoding": "YUY2_Y0_U0_Y1_V0_NEUTRAL_CHROMA",
        "raw_stride_bytes": contract.width_px * 2,
        "raw_colorimetry": {
            "color_primaries": "SRGB_BT709",
            "transfer_characteristics": "SRGB",
            "matrix_coefficients": "BT601_YCBCR",
            "quantization_range": "FULL_Y0_255_C0_255",
            "chroma_siting": "COSITED_LEFT_422",
            "row_origin": "TOP_LEFT",
        },
        "decoded_encoding": "RGB8_INTERLEAVED_ROW_MAJOR",
        "decoded_stride_bytes": contract.width_px * 3,
        "derived_rgb_colorimetry": {
            "color_primaries": "SRGB_BT709",
            "transfer_characteristics": "SRGB",
            "matrix_coefficients": "IDENTITY_RGB",
            "quantization_range": "FULL_0_255",
            "chroma_siting": "NOT_APPLICABLE_RGB",
            "row_origin": "TOP_LEFT",
        },
        "rectified_encoding": "RGB8_INTERLEAVED_ROW_MAJOR",
        "rectified_stride_bytes": contract.width_px * 3,
        "jpeg_to_yuy2_derivation": (
            "DECODE_JPEG_TO_L8_THEN_PACK_Y0_128_Y1_128"
        ),
        "jpeg_to_rgb8_derivation": "DECODE_JPEG_TO_L8_THEN_REPLICATE_Y_TO_RGB",
        "capture_pixel_space": contract.capture_pixel_space,
        "rectified_pixel_space": contract.estimator_pixel_space,
        "optical_contract_sha256": contract.content_sha256,
        "undistortion_map_sha256": contract.undistortion_map_sha256,
        "used_for_pose_estimation": False,
        "pose_rectification_path": "ANALYTIC_PER_DETECTION_CORNER",
        "physical_calibration_claim": False,
        "authority": dict(_ZERO_AUTHORITY),
    }
    return bytes(raw_yuy2), decoded_rgb8, rectified_rgb8, provenance


def _detector_record(
    capture: B0477StaticVisionCapture,
    *,
    raw_bytes: bytes,
    decoded_bytes: bytes,
    rectified_bytes: bytes,
    full_frame_rectifier: Mapping[str, object],
) -> Mapping[str, Any]:
    raw = capture.raw_detection_batch.to_dict()
    rectified = capture.rectified_detection_batch.to_dict()
    return {
        "schema": B0477_SENSOR_DETECTOR_RECORD_SCHEMA,
        "capture_sha256": capture.content_sha256,
        "report_sha256": capture.report.content_sha256,
        "detector_input_jpeg": {
            "encoding": "BASE64_CHUNKS",
            "chunks": list(_jpeg_base64_chunks(capture.jpeg_bytes)),
            "decoded_byte_count": len(capture.jpeg_bytes),
            "decoded_sha256": capture.jpeg_sha256,
        },
        "raw_detection_batch": raw,
        "raw_detection_batch_sha256": capture.raw_detection_batch.content_hash,
        "rectified_detection_batch": rectified,
        "rectified_detection_batch_sha256": (
            capture.rectified_detection_batch.content_hash
        ),
        "optical_contract": capture.optical_contract.to_dict(),
        "optical_contract_sha256": capture.optical_contract.content_sha256,
        "full_frame_rectifier": dict(full_frame_rectifier),
        "raster_sha256": {
            "jpeg": capture.jpeg_sha256,
            "raw_yuy2": hashlib.sha256(raw_bytes).hexdigest(),
            "decoded_rgb8": hashlib.sha256(decoded_bytes).hexdigest(),
            "rectified_rgb8": hashlib.sha256(rectified_bytes).hexdigest(),
        },
        "detector_input": "JPEG_BYTES_ONLY",
        "scene_truth_supplied_to_detector": False,
        "hardware_camera_accessed": False,
        "authority": dict(_ZERO_AUTHORITY),
    }


def _pose_record(capture: B0477StaticVisionCapture) -> Mapping[str, Any]:
    observation = capture.pose_observation
    return {
        "schema": B0477_SENSOR_POSE_RECORD_SCHEMA,
        "capture_sha256": capture.content_sha256,
        "report_sha256": capture.report.content_sha256,
        "estimate_available": observation is not None,
        "pose_observation": observation.to_dict() if observation is not None else None,
        "pose_observation_sha256": (
            observation.content_hash if observation is not None else None
        ),
        "pose_comparison": capture.report.pose_comparison.to_dict(),
        "held_out_station_residuals": [
            residual.to_dict()
            for residual in capture.report.held_out_station_residuals
        ],
        "status": capture.report.status,
        "detail_code": capture.report.detail_code,
        "physical_pose_authority": False,
        "authority": dict(_ZERO_AUTHORITY),
    }


def _sensor_timing(sequence: int) -> SensorTimingBracket:
    # These are synthetic logical ticks, not wall time.  Their sole purpose is
    # to exercise strict ordering, freshness, and feedback-latency checks.
    base = sequence * 10 + 100
    return SensorTimingBracket(
        frame_sequence=sequence,
        event_monotonic_ns=tuple(base + offset for offset in range(9)),
        feedback_receive_buffer_bytes_before_request=0,
    )


def _synthetic_feedback_line(
    capture: B0477StaticVisionCapture,
) -> bytes:
    """Return one deterministic fake T=1051 line; no transport is involved."""

    return encode_line(
        {
            "T": 1051,
            "b": 0.0,
            "s": 0.0,
            "e": 0.0,
            "t": 0.0,
            "r": 0.0,
            "g": 0.0,
            "x": 0.0,
            "y": 0.0,
            "z": 0.0,
            "v": 1200.0,
            "simulation_fixture": B0477_SENSOR_SESSION_BRIDGE_SCHEMA,
            "capture_sha256": capture.content_sha256,
        }
    )


@dataclass(frozen=True, slots=True)
class B0477SyntheticSensorSession:
    """In-memory B0477 capture plus the exact generic evidence inputs."""

    capture: B0477StaticVisionCapture
    contract: SensorSessionContract
    session: RawSensorSessionInput
    full_frame_rectifier: Mapping[str, object]
    schema: str = B0477_SENSOR_SESSION_BRIDGE_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != B0477_SENSOR_SESSION_BRIDGE_SCHEMA:
            raise B0477SensorSessionBridgeError(
                "unsupported B0477 sensor-session bridge schema"
            )
        if not isinstance(self.capture, B0477StaticVisionCapture):
            raise TypeError("capture must be B0477StaticVisionCapture")
        if not isinstance(self.contract, SensorSessionContract):
            raise TypeError("contract must be SensorSessionContract")
        if not isinstance(self.session, RawSensorSessionInput):
            raise TypeError("session must be RawSensorSessionInput")
        if not isinstance(self.full_frame_rectifier, Mapping):
            raise TypeError("full_frame_rectifier must be a mapping")
        object.__setattr__(
            self,
            "full_frame_rectifier",
            _freeze_json(_json_value(self.full_frame_rectifier)),
        )
        if self.session.identity != self.contract.identity:
            raise B0477SensorSessionBridgeError(
                "session identity differs from the bridge contract"
            )
        if self.session.mode != self.contract.mode:
            raise B0477SensorSessionBridgeError(
                "session mode differs from the bridge contract"
            )
        if self.session.controls != self.contract.controls:
            raise B0477SensorSessionBridgeError(
                "session controls differ from the bridge contract"
            )
        if self.session.timing.frame_sequence != self.capture.report.sequence:
            raise B0477SensorSessionBridgeError(
                "session sequence differs from the B0477 capture"
            )
        if self.contract.calibration_sha256 != self.capture.optical_contract.content_sha256:
            raise B0477SensorSessionBridgeError(
                "session calibration binding differs from the optical contract"
            )
        rectifier = dict(self.full_frame_rectifier)
        if (
            rectifier.get("schema") != B0477_FULL_FRAME_RECTIFIER_SCHEMA
            or rectifier.get("optical_contract_sha256")
            != self.capture.optical_contract.content_sha256
            or rectifier.get("authority") != _ZERO_AUTHORITY
        ):
            raise B0477SensorSessionBridgeError(
                "full-frame rectifier provenance is incomplete or over-authoritative"
            )
        detector = self.session.detector_record
        pose = self.session.pose_record
        if (
            detector.get("schema") != B0477_SENSOR_DETECTOR_RECORD_SCHEMA
            or detector.get("capture_sha256") != self.capture.content_sha256
            or pose.get("schema") != B0477_SENSOR_POSE_RECORD_SCHEMA
            or pose.get("capture_sha256") != self.capture.content_sha256
        ):
            raise B0477SensorSessionBridgeError(
                "perception records are not bound to the B0477 capture"
            )
        encoded_jpeg = detector.get("detector_input_jpeg")
        if not isinstance(encoded_jpeg, Mapping):
            raise B0477SensorSessionBridgeError(
                "detector record omits the encoded JPEG input"
            )
        chunks = encoded_jpeg.get("chunks")
        if (
            not isinstance(chunks, tuple)
            or not chunks
            or len(chunks) > _MAX_B0477_DETECTOR_INPUT_JPEG_BASE64_CHUNKS
            or any(
                not isinstance(chunk, str)
                or not chunk
                or len(chunk) > MAX_B0477_JPEG_BASE64_CHUNK_CHARS
                for chunk in chunks
            )
        ):
            raise B0477SensorSessionBridgeError(
                "detector-input JPEG chunks are malformed or unbounded"
            )
        encoded_length = sum(len(chunk) for chunk in chunks)
        if encoded_length > _MAX_B0477_DETECTOR_INPUT_JPEG_BASE64_CHARS:
            raise B0477SensorSessionBridgeError(
                "detector-input JPEG aggregate base64 is unbounded"
            )
        try:
            restored_jpeg = base64.b64decode("".join(chunks), validate=True)
        except (ValueError, binascii.Error) as exc:
            raise B0477SensorSessionBridgeError(
                "detector-input JPEG base64 is invalid"
            ) from exc
        if (
            restored_jpeg != self.capture.jpeg_bytes
            or encoded_jpeg.get("decoded_byte_count") != len(restored_jpeg)
            or encoded_jpeg.get("decoded_sha256")
            != hashlib.sha256(restored_jpeg).hexdigest()
        ):
            raise B0477SensorSessionBridgeError(
                "detector-input JPEG does not match the B0477 capture"
            )
        raster_hashes = detector.get("raster_sha256")
        expected_raster_hashes = {
            "jpeg": self.capture.jpeg_sha256,
            "raw_yuy2": hashlib.sha256(
                self.session.raw_frame_bytes
            ).hexdigest(),
            "decoded_rgb8": hashlib.sha256(
                self.session.decoded_frame_bytes
            ).hexdigest(),
            "rectified_rgb8": hashlib.sha256(
                self.session.undistorted_frame_bytes
            ).hexdigest(),
        }
        if not isinstance(raster_hashes, Mapping) or dict(raster_hashes) != expected_raster_hashes:
            raise B0477SensorSessionBridgeError(
                "detector raster hashes differ from the session bytes"
            )
        expected_detector = _detector_record(
            self.capture,
            raw_bytes=self.session.raw_frame_bytes,
            decoded_bytes=self.session.decoded_frame_bytes,
            rectified_bytes=self.session.undistorted_frame_bytes,
            full_frame_rectifier=self.full_frame_rectifier,
        )
        expected_pose = _pose_record(self.capture)
        if _json_value(detector) != _json_value(expected_detector):
            raise B0477SensorSessionBridgeError(
                "detector record differs from the complete B0477 perception evidence"
            )
        if _json_value(pose) != _json_value(expected_pose):
            raise B0477SensorSessionBridgeError(
                "pose record differs from the complete B0477 perception evidence"
            )
        try:
            request = decode_line(self.session.t105_request_line)
            response = decode_line(self.session.t1051_response_line)
        except ProtocolError as exc:
            raise B0477SensorSessionBridgeError(
                "bridge wire fixture is not valid newline JSON"
            ) from exc
        if request != {"T": 105}:
            raise B0477SensorSessionBridgeError(
                "bridge wire fixture must contain exactly one unsent T=105"
            )
        if (
            response.get("T") != 1051
            or response.get("simulation_fixture")
            != B0477_SENSOR_SESSION_BRIDGE_SCHEMA
            or response.get("capture_sha256") != self.capture.content_sha256
        ):
            raise B0477SensorSessionBridgeError(
                "synthetic T=1051 is not bound to this B0477 capture"
            )

    @property
    def content_sha256(self) -> str:
        return _canonical_hash(self.to_dict())

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": self.schema,
            "capture_sha256": self.capture.content_sha256,
            "report_sha256": self.capture.report.content_sha256,
            "contract": self.contract.to_dict(),
            "frame_sequence": self.session.timing.frame_sequence,
            "artifact_sha256": {
                "raw_yuy2": hashlib.sha256(
                    self.session.raw_frame_bytes
                ).hexdigest(),
                "decoded_rgb8": hashlib.sha256(
                    self.session.decoded_frame_bytes
                ).hexdigest(),
                "rectified_rgb8": hashlib.sha256(
                    self.session.undistorted_frame_bytes
                ).hexdigest(),
                "detector_record": _canonical_hash(
                    self.session.detector_record
                ),
                "pose_record": _canonical_hash(self.session.pose_record),
                "t105_request_line": hashlib.sha256(
                    self.session.t105_request_line
                ).hexdigest(),
                "t1051_response_line": hashlib.sha256(
                    self.session.t1051_response_line
                ).hexdigest(),
            },
            "full_frame_rectifier": _json_value(self.full_frame_rectifier),
            "wire_fixture": {
                "request": "T=105_UNSENT",
                "response": "T=1051_SYNTHETIC",
                "transport_invoked": False,
                "t104_representable": False,
            },
            "authority": dict(_ZERO_AUTHORITY),
        }


def _expected_generic_documents(
    source: B0477SyntheticSensorSession,
) -> Mapping[str, Mapping[str, object]]:
    """Reconstruct the exact generic evidence documents for ``source``.

    Generic sensor replay proves that a package is internally coherent.  This
    separate reconstruction proves the stronger, domain-specific statement:
    every verified document came from this exact B0477 source object.  In
    particular, self-consistent generic packages with substituted detector,
    pose, optical-contract, rectifier, camera, timing, or contract records are
    rejected here.
    """

    session = source.session
    contract = source.contract
    contract_document = contract.to_dict()
    authority = contract_document.get("authority")
    if not isinstance(authority, Mapping):  # pragma: no cover - constructor invariant
        raise B0477SensorSessionBridgeError(
            "source session contract omits zero-authority evidence"
        )

    identity = session.identity.to_dict()
    selected_mode = contract.mode.to_dict()
    observed_mode = session.mode.to_dict()
    requested_controls = contract.controls.to_dict()
    observed_controls = session.controls.to_dict()
    timing = session.timing.to_dict()
    detector = _json_value(session.detector_record)
    pose = _json_value(session.pose_record)

    camera_document: Mapping[str, object] = {
        "schema": CAMERA_SCHEMA,
        "source_kind": "FAKE_UVC",
        "identity": identity,
        "selected_mode": selected_mode,
        "observed_mode": observed_mode,
        "requested_controls": requested_controls,
        "observed_controls": observed_controls,
        "frame_sequence": session.timing.frame_sequence,
        "snapshot_sha256": {
            "identity": _canonical_hash(identity),
            "selected_mode": _canonical_hash(selected_mode),
            "observed_mode": _canonical_hash(observed_mode),
            "requested_controls": _canonical_hash(requested_controls),
            "observed_controls": _canonical_hash(observed_controls),
        },
        "authority": dict(authority),
    }
    perception_document: Mapping[str, object] = {
        "schema": PERCEPTION_SCHEMA,
        "source_kind": "SYNTHETIC_PERCEPTION_FIXTURE",
        "frame_sequence": session.timing.frame_sequence,
        "calibration_sha256": contract.calibration_sha256,
        "source_sha256": {
            "raw_frame": hashlib.sha256(session.raw_frame_bytes).hexdigest(),
            "decoded_frame": hashlib.sha256(
                session.decoded_frame_bytes
            ).hexdigest(),
            "undistorted_frame": hashlib.sha256(
                session.undistorted_frame_bytes
            ).hexdigest(),
            "timing": _canonical_hash(timing),
        },
        "detector_record": detector,
        "detector_record_sha256": _canonical_hash(detector),
        "pose_record": pose,
        "pose_record_sha256": _canonical_hash(pose),
        "authority": dict(authority),
    }
    return {
        "contract.json": contract_document,
        "camera.json": camera_document,
        "timing.json": timing,
        "perception.json": perception_document,
    }


@dataclass(frozen=True, slots=True)
class B0477RecordedSensorSession:
    """A verified generic replay bound to one exact B0477 source session."""

    source: B0477SyntheticSensorSession
    record: SensorSessionRecord
    replay: ReplayedSensorSession

    def __post_init__(self) -> None:
        if not isinstance(self.source, B0477SyntheticSensorSession):
            raise TypeError("source must be B0477SyntheticSensorSession")
        if not isinstance(self.record, SensorSessionRecord):
            raise TypeError("record must be SensorSessionRecord")
        if not isinstance(self.replay, ReplayedSensorSession):
            raise TypeError("replay must be ReplayedSensorSession")
        if (
            self.record.record_id != self.replay.record.record_id
            or self.record.content_sha256 != self.replay.record.content_sha256
            or self.record.manifest_sha256 != self.replay.record.manifest_sha256
            or self.record.directory != self.replay.record.directory
            or self.record.manifest_path
            != self.replay.record.directory / "manifest.json"
        ):
            raise B0477SensorSessionBridgeError(
                "record handle differs from the strictly verified replay"
            )

        source = self.source
        verified = self.replay.record
        if (
            verified.contract != source.contract
            or verified.applied_contract != source.contract
            or verified.identity != source.session.identity
            or verified.mode != source.session.mode
            or verified.controls != source.session.controls
            or verified.timing != source.session.timing
            or verified.calibration_sha256
            != source.capture.optical_contract.content_sha256
        ):
            raise B0477SensorSessionBridgeError(
                "verified generic session contract differs from the B0477 source"
            )

        expected_documents = _expected_generic_documents(source)
        if set(verified.documents) != set(expected_documents) or any(
            _json_value(verified.document(name))
            != _json_value(expected_document)
            for name, expected_document in expected_documents.items()
        ):
            raise B0477SensorSessionBridgeError(
                "verified replay documents differ from the exact B0477 source"
            )

        expected_blobs = {
            "raw-frame.bin": source.session.raw_frame_bytes,
            "decoded-frame.bin": source.session.decoded_frame_bytes,
            "undistorted-frame.bin": source.session.undistorted_frame_bytes,
            "t105-request.line": source.session.t105_request_line,
            "t1051-response.line": source.session.t1051_response_line,
        }
        if set(verified.blobs) != set(expected_blobs) or any(
            verified.blob(name) != expected_payload
            for name, expected_payload in expected_blobs.items()
        ):
            raise B0477SensorSessionBridgeError(
                "verified replay byte artifacts differ from the exact B0477 source"
            )

    @property
    def status(self) -> str:
        """Name the stronger B0477 binding, not only generic replay validity."""

        return B0477_SOURCE_BOUND_REPLAY_STATUS

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": B0477_SENSOR_SESSION_BRIDGE_SCHEMA,
            "status": self.status,
            "generic_replay_status": self.replay.status,
            "verification_scope": (
                "EXACT_B0477_SOURCE_CONTRACT_DOCUMENTS_AND_BYTES"
            ),
            "source_sha256": self.source.content_sha256,
            "record_id": self.record.record_id,
            "content_sha256": self.record.content_sha256,
            "manifest_sha256": self.record.manifest_sha256,
            "replay_sha256": self.replay.replay_sha256,
            "manifest_path": str(self.record.manifest_path),
            "authority": dict(_ZERO_AUTHORITY),
        }


def build_b0477_synthetic_sensor_session(
    workspace_root: Path,
    *,
    sequence: int = 1,
    mode: B0477StaticVisionMode = B0477StaticVisionMode.NORMAL,
    camera_profile_path: Path | None = None,
    support_design_path: Path | None = None,
) -> B0477SyntheticSensorSession:
    """Build one bounded session entirely from deterministic fake providers."""

    selected_sequence = _bounded_bridge_sequence(sequence)
    if not isinstance(mode, B0477StaticVisionMode):
        raise TypeError("mode must be B0477StaticVisionMode")
    capture = run_b0477_static_vision_capture_rehearsal(
        workspace_root,
        sequence=selected_sequence,
        mode=mode,
        camera_profile_path=camera_profile_path,
        support_design_path=support_design_path,
    )
    raw_bytes, decoded_bytes, rectified_bytes, rectifier = (
        _decode_and_rectify_rasters(capture)
    )
    identity = SyntheticCameraIdentity(
        manufacturer="Arducam",
        model="B0477",
        sensor="IMX283",
        vid="ffff",
        pid="ffff",
        serial_number="SIM-B0477-NOT-PHYSICAL",
        device_key="fake-uvc:b0477-static-overhead",
    )
    mode_snapshot = CameraModeSnapshot(
        width_px=capture.optical_contract.width_px,
        height_px=capture.optical_contract.height_px,
        fps_numerator=9,
        fps_denominator=1,
        pixel_format="YUY2",
    )
    controls = CameraControlSnapshot(
        # Match the established B0477 UVC/onboarding fixture: 8 ms exposure,
        # unity gain, 5000 K manual white balance.  These remain synthetic
        # values and are not proposed physical acceptance settings.
        exposure_us=8_000,
        gain_milli_db=0,
        white_balance_kelvin=5_000,
        focus_position=0,
        auto_exposure=False,
        auto_white_balance=False,
        autofocus=False,
    )
    timing = _sensor_timing(selected_sequence)
    contract = SensorSessionContract(
        identity=identity,
        mode=mode_snapshot,
        controls=controls,
        calibration_sha256=capture.optical_contract.content_sha256,
        minimum_frame_sequence_exclusive=selected_sequence - 1,
        not_before_monotonic_ns=timing.timestamp("FRAME_CAPTURED"),
        maximum_frame_age_ns=2,
        maximum_feedback_latency_ns=1,
        maximum_stage_duration_ns=1,
        maximum_session_duration_ns=8,
    )
    session = RawSensorSessionInput(
        identity=identity,
        mode=mode_snapshot,
        controls=controls,
        timing=timing,
        raw_frame_bytes=raw_bytes,
        decoded_frame_bytes=decoded_bytes,
        undistorted_frame_bytes=rectified_bytes,
        detector_record=_detector_record(
            capture,
            raw_bytes=raw_bytes,
            decoded_bytes=decoded_bytes,
            rectified_bytes=rectified_bytes,
            full_frame_rectifier=rectifier,
        ),
        pose_record=_pose_record(capture),
        t105_request_line=encode_line(feedback_request()),
        t1051_response_line=_synthetic_feedback_line(capture),
    )
    return B0477SyntheticSensorSession(
        capture=capture,
        contract=contract,
        session=session,
        full_frame_rectifier=rectifier,
    )


def record_and_replay_b0477_synthetic_sensor_session(
    workspace_root: Path,
    evidence_root: Path,
    *,
    sequence: int = 1,
    mode: B0477StaticVisionMode = B0477StaticVisionMode.NORMAL,
    camera_profile_path: Path | None = None,
    support_design_path: Path | None = None,
) -> B0477RecordedSensorSession:
    """Record, verify, and replay one B0477 synthetic session.

    ``evidence_root`` must already exist, matching the generic recorder's
    no-surprise filesystem contract.  Any package or replay inconsistency
    fails closed and no hardware fallback exists.
    """

    source = build_b0477_synthetic_sensor_session(
        workspace_root,
        sequence=sequence,
        mode=mode,
        camera_profile_path=camera_profile_path,
        support_design_path=support_design_path,
    )
    try:
        record = record_sensor_session(source.session, source.contract, evidence_root)
        replay = replay_sensor_session(
            record.manifest_path,
            replay_contract=source.contract,
        )
    except SensorSessionEvidenceError as exc:
        raise B0477SensorSessionBridgeError(
            f"B0477 sensor-session record/replay failed: {exc}"
        ) from exc
    return B0477RecordedSensorSession(source=source, record=record, replay=replay)


__all__ = [
    "B0477_FULL_FRAME_RECTIFIER_SCHEMA",
    "B0477_RECTIFICATION_MESH_STEP_PX",
    "B0477_SENSOR_DETECTOR_RECORD_SCHEMA",
    "B0477_SENSOR_POSE_RECORD_SCHEMA",
    "B0477_SENSOR_SESSION_BRIDGE_SCHEMA",
    "B0477_SOURCE_BOUND_REPLAY_STATUS",
    "MAX_B0477_RECTIFICATION_MESH_CELLS",
    "MAX_B0477_JPEG_BASE64_CHUNK_CHARS",
    "MAX_B0477_DETECTOR_INPUT_JPEG_BYTES",
    "B0477RecordedSensorSession",
    "B0477SensorSessionBridgeError",
    "B0477SyntheticSensorSession",
    "build_b0477_synthetic_sensor_session",
    "record_and_replay_b0477_synthetic_sensor_session",
]
