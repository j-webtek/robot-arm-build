"""Pre-terminal capture checksum contract; parsing never proves original storage.

Unlike the later ingestion reference, this subject has no dataset/preview hashes.
Its owner must bind these bytes into the original attempt before sealing. Failed
reads are retained data, not permission to retry the already performed capture.
"""

from dataclasses import asdict, dataclass
from typing import Any

from .camera_activation_campaign_evidence import validate_camera_activation_evidence
from .camera_capture_reference import _frame, _REQUEST, _sha
from rocell.providers.windows.camera_worker_client import (
    NativeCameraMode,
    NativeFrameArtifact,
    CameraWorkerError,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.owned_worker_process import decode_owned_json

SCHEMA = "rocell.camera_capture_checksum.v1"
MAX_BYTES = 24 * 1024
ORIGIN = "OWNED_CAPTURE_POST_CLEANUP_PRE_SEAL"
STATUSES = (
    "CAPTURE_BYTES_HASHED",
    "NATIVE_CAPTURE_NOT_COMPLETE",
    "PIXEL_READ_NOT_ATTESTED",
    "PIXEL_READ_FAILED",
    "PIXEL_READ_INTERRUPTED",
)
FALSE_FIELDS = (
    "original_store_authenticated",
    "stage_passed",
    "physical_authority",
    "hardware_qualified",
    "frame_freshness_assessed",
    "device_io_performed",
)
FIELDS = {
    "schema",
    "origin",
    "request_key",
    "preparation_sha256",
    "native_run_sha256",
    "native_supervision_sha256",
    "request_sha256",
    "status",
    "frame",
    "observed_mode",
    "native_finished_ns",
    "read_started_ns",
    "read_finished_ns",
    "deadline_ns",
    "verified_pixel_bytes",
    "timestamp_semantics",
    *FALSE_FIELDS,
}


class CameraCaptureChecksumError(ValueError):
    def __init__(self):
        super().__init__("CAMERA_CAPTURE_CHECKSUM_INVALID")


def _need(ok):
    if not ok:
        raise CameraCaptureChecksumError()


def _ns(value):
    _need(type(value) is int and 0 < value < 2**63)


def _document(payload):
    try:
        _need(type(payload) is bytes)
        data = decode_owned_json(payload, maximum=MAX_BYTES)
        _need(set(data) == FIELDS and canonical(data) == payload)
        _need(
            data["schema"] == SCHEMA
            and data["origin"] == ORIGIN
            and type(data["request_key"]) is str
            and _REQUEST.fullmatch(data["request_key"]) is not None
            and type(data["status"]) is str
            and data["status"] in STATUSES
            and all(data[key] is False for key in FALSE_FIELDS)
            and data["timestamp_semantics"] == "HOST_READ_INTERVAL_NOT_EXPOSURE_TIME"
        )
        for key in (
            "preparation_sha256",
            "native_run_sha256",
            "native_supervision_sha256",
            "request_sha256",
        ):
            _sha(data[key])
        _ns(data["deadline_ns"])
        if data["native_finished_ns"] is not None:
            _ns(data["native_finished_ns"])
        _need(type(data["verified_pixel_bytes"]) is int)
        if data["status"] == "NATIVE_CAPTURE_NOT_COMPLETE":
            _need(
                all(
                    data[key] is None
                    for key in (
                        "frame",
                        "observed_mode",
                        "read_started_ns",
                        "read_finished_ns",
                    )
                )
            )
            _need(data["verified_pixel_bytes"] == 0)
            return data
        _ns(data["native_finished_ns"])
        mode = NativeCameraMode(**data["observed_mode"])
        _need(asdict(mode) == data["observed_mode"])
        if data["status"] == "PIXEL_READ_NOT_ATTESTED":
            # Native completion remains available even when a denied scope,
            # interruption or invalid clock prevents a trustworthy read report.
            # Missing host times are unknown, not synthesized from native times.
            _need(
                data["frame"] is None
                and data["read_started_ns"] is None
                and data["read_finished_ns"] is None
                and data["verified_pixel_bytes"] == 0
            )
            return data
        _ns(data["read_finished_ns"])
        _need(data["read_finished_ns"] >= data["native_finished_ns"])
        start = data["read_started_ns"]
        if start is not None:
            _ns(start)
            _need(data["native_finished_ns"] <= start <= data["read_finished_ns"])
        if data["status"] == "CAPTURE_BYTES_HASHED":
            _need(start is not None and data["read_finished_ns"] < data["deadline_ns"])
            _frame(data["frame"], mode)
            _need(data["verified_pixel_bytes"] == data["frame"]["length_bytes"])
        else:
            _need(data["frame"] is None and data["verified_pixel_bytes"] == 0)
            if data["status"] == "PIXEL_READ_FAILED":
                _need(
                    start is not None and data["read_finished_ns"] < data["deadline_ns"]
                )
        return data
    except CameraCaptureChecksumError:
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
        raise CameraCaptureChecksumError() from error


@dataclass(frozen=True, slots=True)
class CameraCaptureChecksum:
    """Immutable structurally checked data; never a restored capture permission."""

    payload: bytes

    def __post_init__(self):
        _document(self.payload)

    @property
    def sha256(self):
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _document(self.payload)


def capture_metadata(evidence):
    """Validate the original native pair and derive hashable-frame eligibility.

    This is not device qualification or settings acceptance. Preserve failed
    native evidence; only a successful, cleaned-up, exact single-frame capture
    can enter the bounded pixel read. No native counters are synthesized.
    """
    checked = validate_camera_activation_evidence(evidence)
    prepared = checked.prepared
    request = prepared.camera_plan.request
    _need(request.operation == "capture" and request.budget.max_frames == 1)
    # This exact pair has just been independently decoded above. Derive the
    # native assessment once within this call; constructing a display projection
    # would decode the same immutable bytes again, compare their own hashes to
    # themselves, and build a large unused dictionary. No result is cached across
    # calls, original-store reads, context checks or consumed-scope boundaries.
    assessed = checked.run.assessment()
    receipt = None if assessed.native is None else assessed.native.receipt
    complete = (
        assessed.status == "SUCCEEDED_NATIVE_DIAGNOSTIC"
        and assessed.process_cleanup_confirmed
        and receipt is not None
        and receipt.status == "OK"
        and receipt.cleanup_confirmed
        and len(receipt.frames) == 1
        and request.mode is not None
        and receipt.observed_mode is not None
        and request.mode.same_format(receipt.observed_mode)
    )
    if complete:
        assert receipt is not None and receipt.observed_mode is not None
        # Reuse the exact signed-stride/layout contract. This dummy digest is
        # solely a structural check and is never returned or retained as a hash.
        metadata = asdict(receipt.frames[0])
        _frame(dict(metadata, sha256="1" * 64), receipt.observed_mode)
        _need(
            metadata["length_bytes"]
            <= min(request.budget.max_frame_bytes, request.budget.max_total_bytes)
        )
        return checked, receipt.observed_mode, metadata
    return checked, None, None


def build_capture_checksum(
    evidence,
    *,
    request_key,
    status,
    frame: NativeFrameArtifact | None,
    read_started_ns: int | None,
    read_finished_ns: int | None,
) -> CameraCaptureChecksum:
    """Pure builder: the capture owner supplies an earlier guarded-read hash.

    The native evidence supplies the deadline, identity and metadata independently.
    A caller-supplied self-consistent hash is not proof that bytes were read.
    """
    try:
        checked, mode, metadata = capture_metadata(evidence)
        prepared = checked.prepared
        _need((metadata is None) == (status == "NATIVE_CAPTURE_NOT_COMPLETE"))
        data = checked.run.to_dict()
        _need((frame is not None) == (status == "CAPTURE_BYTES_HASHED"))
        if frame is not None:
            _need(type(frame) is NativeFrameArtifact)
            _need(
                canonical({k: v for k, v in asdict(frame).items() if k != "sha256"})
                == canonical(metadata)
            )
        return CameraCaptureChecksum(
            canonical(
                dict(
                    schema=SCHEMA,
                    origin=ORIGIN,
                    request_key=request_key,
                    preparation_sha256=prepared.preparation_sha256,
                    native_run_sha256=evidence[0].payload_sha256,
                    native_supervision_sha256=evidence[1].payload_sha256,
                    request_sha256=prepared.admission_request.request_sha256,
                    status=status,
                    frame=None if frame is None else asdict(frame),
                    observed_mode=None if mode is None else asdict(mode),
                    native_finished_ns=data["finished_ns"],
                    deadline_ns=data["parent_deadline_ns"],
                    read_started_ns=read_started_ns,
                    read_finished_ns=read_finished_ns,
                    verified_pixel_bytes=0 if frame is None else frame.length_bytes,
                    timestamp_semantics="HOST_READ_INTERVAL_NOT_EXPOSURE_TIME",
                    **{key: False for key in FALSE_FIELDS},
                )
            )
        )
    except CameraCaptureChecksumError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        CameraWorkerError,
    ) as error:
        raise CameraCaptureChecksumError() from error


def verify_capture_checksum(
    payload, *, evidence, expected_request_key, expected_sha256
):
    """Independent native join; original retention/receipt authentication is external."""
    subject = CameraCaptureChecksum(payload)
    _need(subject.sha256 == expected_sha256)
    data = subject.to_dict()
    rebuilt = build_capture_checksum(
        evidence,
        request_key=expected_request_key,
        status=data["status"],
        frame=None if data["frame"] is None else NativeFrameArtifact(**data["frame"]),
        read_started_ns=data["read_started_ns"],
        read_finished_ns=data["read_finished_ns"],
    )
    _need(subject == rebuilt)
    return subject
