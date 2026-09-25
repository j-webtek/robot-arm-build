"""Bounded capture-time checksum subject for future original-stage retention.

This codec performs no I/O. The owned ingestion path must supply the frame hash
it has just verified, then an original owner must retain/read back the subject.
A parsed reference or matching caller-provided hash alone proves neither step.
Legacy launch-only checksums cannot be promoted by this module.
"""

from dataclasses import asdict, dataclass, fields
from typing import Any
import re

from .camera_capture_dataset import MAX_FRAME_BYTES
from .camera_operating_evidence_preflight import CameraNativeEvidenceSubject
from .physical_camera_configuration import (
    PhysicalCameraReadback,
    StagedPhysicalCameraConfiguration,
    _verified_observation,
    compare_physical_camera_readback,
)
from rocell.providers.windows.camera_worker_client import (
    NativeCameraMode,
    NativeFrameArtifact,
    CameraWorkerError,
)
from rocell.providers.windows.native_camera_activation_registration import (
    PreparedOwnedNativeActivation,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.owned_worker_process import decode_owned_json

SCHEMA = "rocell.camera_capture_reference.v1"
MAX_BYTES = 24 * 1024
ORIGIN = "OWNED_CAPTURE_COMPLETION_CANDIDATE"
FALSE_FIELDS = (
    "original_store_authenticated",
    "stage_passed",
    "physical_authority",
    "hardware_qualified",
    "frame_freshness_assessed",
    "device_io_performed",
)
_HASH = re.compile(r"[0-9a-f]{64}\Z")
# Match RegisteredActionRequest's portable 64-character key contract.
_REQUEST = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_FIELDS = {
    "schema",
    "stage",
    "origin",
    "request_key",
    "native_evidence",
    "readback",
    "readback_sha256",
    "frame",
    "manifest_sha256",
    "ingest_envelope_sha256",
    "timestamp_semantics",
    *FALSE_FIELDS,
}
_NATIVE_KEYS = {"preparation_sha256", "evidence_sha256", "supervision_sha256"}
_FRAME_KEYS = {field.name for field in fields(NativeFrameArtifact)}


class CameraCaptureReferenceError(ValueError):
    def __init__(self) -> None:
        super().__init__("CAMERA_CAPTURE_REFERENCE_INVALID")


def _need(condition: bool) -> None:
    if not condition:
        raise CameraCaptureReferenceError()


def _sha(value: Any) -> None:
    _need(
        type(value) is str and _HASH.fullmatch(value) is not None and value != "0" * 64
    )


def _frame(value: Any, mode: NativeCameraMode) -> None:
    _need(type(value) is dict and set(value) == _FRAME_KEYS)
    _sha(value["sha256"])
    _need(value["filename"] == "frame-000000.yuy2")
    for key, low, high in (
        ("length_bytes", 1, MAX_FRAME_BYTES),
        ("stride_bytes", -1_048_576, 1_048_576),
        ("row0_offset_bytes", 0, MAX_FRAME_BYTES - 1),
        ("host_sequence", 0, 0),
        ("media_timestamp_100ns", -(2**63), 2**63 - 1),
        ("host_arrival_qpc", 0, 2**63 - 1),
        ("qpc_frequency", 1, 2**63 - 1),
    ):
        _need(type(value[key]) is int and low <= value[key] <= high)
    _need(value["discontinuity"] is None or type(value["discontinuity"]) is bool)
    stride = value["stride_bytes"]
    _need(
        mode.subtype == "YUY2"
        and mode.width % 2 == 0
        and abs(stride) >= mode.width * 2
        and abs(stride) % 2 == 0
        and mode.stride_bytes == stride
        and value["length_bytes"] == abs(stride) * mode.height
        and value["row0_offset_bytes"]
        == (0 if stride > 0 else abs(stride) * (mode.height - 1))
    )


def _document(payload: bytes) -> dict[str, Any]:
    try:
        _need(type(payload) is bytes)
        data = decode_owned_json(payload, maximum=MAX_BYTES)
        _need(set(data) == _FIELDS and canonical(data) == payload)
        _need(
            data["schema"] == SCHEMA
            and data["stage"] == "camera_mode_controls"
            and data["origin"] == ORIGIN
            and type(data["request_key"]) is str
            and _REQUEST.fullmatch(data["request_key"]) is not None
            and data["timestamp_semantics"]
            == "NATIVE_SAMPLE_AND_HOST_ARRIVAL_NOT_EXPOSURE_TIME"
            and all(data[key] is False for key in FALSE_FIELDS)
        )
        native = data["native_evidence"]
        _need(type(native) is dict and set(native) == _NATIVE_KEYS)
        for value in native.values():
            _sha(value)
        for key in ("readback_sha256", "manifest_sha256", "ingest_envelope_sha256"):
            _sha(data[key])
        readback = PhysicalCameraReadback(canonical(data["readback"]))
        rb = readback.to_dict()
        _need(readback.readback_sha256 == data["readback_sha256"])
        _need(
            rb["status"] == "REQUESTED_SETTINGS_OBSERVED_UNQUALIFIED"
            and rb["native_status"] == "OK"
            and rb["mode_matched"] is rb["native_receipt_valid"] is True
            and rb["process_cleanup_confirmed"]
            is rb["native_cleanup_confirmed"]
            is True
            and rb["capture_preparation_sha256"] == native["preparation_sha256"]
            and rb["capture_evidence_sha256"] == native["evidence_sha256"]
        )
        for binding in (rb["probe_binding"], rb["capture_binding"]):
            for key, value in binding.items():
                if key not in ("session_id", "attempt_id"):
                    _sha(value)
        for key in ("settings_epoch", "capabilities_sha256", "capture_request_sha256"):
            _sha(rb[key])
        _frame(data["frame"], NativeCameraMode(**rb["observed_mode"]))
        return data
    except CameraCaptureReferenceError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        UnicodeError,
        CameraWorkerError,
    ) as error:
        raise CameraCaptureReferenceError() from error


@dataclass(frozen=True, slots=True)
class CameraCaptureReference:
    """Structurally valid immutable data; not a verified original or a permit."""

    payload: bytes

    def __post_init__(self) -> None:
        _document(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _document(self.payload)


def build_capture_reference(
    native: CameraNativeEvidenceSubject,
    *,
    configuration_payload: bytes,
    expected_settings_epoch: str,
    request_key: str,
    frame: NativeFrameArtifact,
    manifest_sha256: str,
    ingest_envelope_sha256: str,
) -> CameraCaptureReference:
    """Join freshly supplied ingestion artifacts to independent native metadata.

    No file is opened or hash calculated over pixels here. The call site's
    original owner must authenticate the request key, native/config inputs and
    capture-time artifact provenance before durable retention/publication.
    Initial scope is exactly one settings-verified frame from the v2 native path.
    """
    try:
        _need(type(native) is CameraNativeEvidenceSubject)
        _need(type(native.preparation) is PreparedOwnedNativeActivation)
        assert isinstance(native.preparation, PreparedOwnedNativeActivation)
        _need(type(frame) is NativeFrameArtifact)
        config = StagedPhysicalCameraConfiguration(configuration_payload)
        _sha(expected_settings_epoch)
        _need(config.settings_epoch == expected_settings_epoch)
        checked = _verified_observation(
            native.evidence,
            prepared=native.preparation,
            expected_evidence_sha256=native.expected_evidence_sha256,
            expected_supervision_sha256=native.expected_supervision_sha256,
        )
        request = native.preparation.camera_plan.request
        receipt = checked.native_receipt
        _need(
            request.operation == "capture"
            and request.budget.max_frames == 1
            and checked.process_cleanup_confirmed
            and receipt is not None
            and receipt.status == "OK"
            and receipt.cleanup_confirmed
            and len(receipt.frames) == 1
        )
        assert receipt is not None
        metadata = {
            key: value for key, value in asdict(frame).items() if key != "sha256"
        }
        # Never normalize driver timestamps, signed stride or frame rate in a
        # retained reference. Preserve exactly what the original evidence says.
        _need(canonical(metadata) == canonical(asdict(receipt.frames[0])))
        _need(
            frame.length_bytes
            <= min(request.budget.max_frame_bytes, request.budget.max_total_bytes)
        )
        readback = compare_physical_camera_readback(
            config,
            native.evidence,
            expected_preparation=native.preparation,
            expected_capture_evidence_sha256=native.expected_evidence_sha256,
            expected_supervision_sha256=native.expected_supervision_sha256,
            expected_settings_epoch=expected_settings_epoch,
        )
        return CameraCaptureReference(
            canonical(
                dict(
                    schema=SCHEMA,
                    stage="camera_mode_controls",
                    origin=ORIGIN,
                    request_key=request_key,
                    native_evidence=dict(
                        preparation_sha256=native.preparation.preparation_sha256,
                        evidence_sha256=native.expected_evidence_sha256,
                        supervision_sha256=native.expected_supervision_sha256,
                    ),
                    readback=readback.to_dict(),
                    readback_sha256=readback.readback_sha256,
                    frame=asdict(frame),
                    manifest_sha256=manifest_sha256,
                    ingest_envelope_sha256=ingest_envelope_sha256,
                    timestamp_semantics="NATIVE_SAMPLE_AND_HOST_ARRIVAL_NOT_EXPOSURE_TIME",
                    **{key: False for key in FALSE_FIELDS},
                )
            )
        )
    except CameraCaptureReferenceError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        UnicodeError,
        CameraWorkerError,
    ) as error:
        raise CameraCaptureReferenceError() from error


def verify_capture_reference(
    payload: bytes,
    *,
    expected_reference_sha256: str,
    expected_request_key: str,
    native: CameraNativeEvidenceSubject,
    configuration_payload: bytes,
    expected_settings_epoch: str,
) -> CameraCaptureReference:
    """Rebuild metadata/settings joins from independent owner-supplied subjects.

    The original owner's expected reference digest binds the earlier frame and
    manifest checksums; this does not recheck their files. A later byte reader
    must use those original hashes, not replace them with freshly observed ones.
    """
    _sha(expected_reference_sha256)
    reference = CameraCaptureReference(payload)
    _need(reference.sha256 == expected_reference_sha256)
    data = reference.to_dict()
    rebuilt = build_capture_reference(
        native,
        configuration_payload=configuration_payload,
        expected_settings_epoch=expected_settings_epoch,
        request_key=expected_request_key,
        frame=NativeFrameArtifact(**data["frame"]),
        manifest_sha256=data["manifest_sha256"],
        ingest_envelope_sha256=data["ingest_envelope_sha256"],
    )
    _need(rebuilt.payload == reference.payload)
    return reference
