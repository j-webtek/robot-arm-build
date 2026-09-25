"""Check saved single-frame bytes against their explicitly identified reference.

Legacy native metadata has no pixel hash and requires a launch-log reference.
The separately versioned M1 collection includes a pre-seal checksum; only its
authenticated owner may supply that subject. Neither read grants stage acceptance.
"""

from contextlib import ExitStack
from dataclasses import asdict
from pathlib import Path
import re
from typing import Any

from .camera_capture_dataset import CameraDatasetCancelled, MAX_FRAME_BYTES
from .camera_capture_checksum import CameraCaptureChecksum, verify_capture_checksum
from .camera_configuration_wizard import _logged_digest
from .camera_configuration_wizard_contract import CAPTURE_ACTION_ID
from .physical_camera_configuration import _verified_observation
from .physical_onboarding_durability import safe_root
from .windows_camera_capture_ingest import (
    CameraCaptureIngestError,
    _blocks,
    _locked_file,
)
from .wizard_diagnostic_export import _directory_guard
from rocell.providers.windows.camera_worker_client import NativeFrameArtifact

SCHEMA = "rocell.camera_operating_pixel_check.v1"
REFERENCE_SCOPE = "RETAINED_LAUNCH_COMPLETION_JOINED_TO_M1_NATIVE_CAPTURE"
SEALED_SCHEMA = "rocell.camera_operating_pixel_check.v2"
SEALED_REFERENCE_SCOPE = "M1_SEALED_CAPTURE_CHECKSUM"
STATUSES = (
    "VERIFIED_AT_READ",
    "LOGGED_REFERENCE_UNAVAILABLE",
    "REFERENCE_MISMATCH",
    "PIXEL_FILE_UNAVAILABLE_OR_CHANGED",
)
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_OPERATION = re.compile(r"operation-[0-9a-f]{32}\Z")


def _sha(value: Any) -> bool:
    return type(value) is str and bool(_SHA.fullmatch(value)) and value != "0" * 64


def logged_pixel_reference(packet, *, request_key, source_sha256, session_id):
    """Extract only a successful retained completion, never paths from the UI.

    This is a launch-memory reference, not authentication of the on-disk log or
    a canonical stage record. The wizard pins the entire packet at preview and
    rechecks it during execution. Missing/redacted completion data stays missing.
    """
    try:
        if not (
            type(packet) is dict
            and packet["source_sha256"] == source_sha256
            and packet["physical_authority"] is False
            and packet["hardware_qualified"] is False
            and packet["queue"]["operation_id"] == request_key
            and packet["queue"]["claimed"] is True
        ):
            return None
        done = packet["completion"]
        result = done["result"]
        if not (
            done["operation_id"] == request_key
            and _OPERATION.fullmatch(request_key)
            and done["action_id"] == CAPTURE_ACTION_ID
            and done["status"] == "SUCCEEDED"
            and done["completion_log_persisted"] is True
            and _sha(done["result_sha256"])
            and _logged_digest(result) == done["result_sha256"]
            and result["schema"] == "rocell.wizard_retained_native_camera_data.v1"
            and result["action_id"] == CAPTURE_ACTION_ID
            and result["status"] == "SUCCEEDED"
            and result["physical_authority"] is False
            and len(result["steps"]) == 1
        ):
            return None
        step = result["steps"][0]
        report = step["report"]
        frame = report["last_frame"]
        if not (
            step["name"] == "retained_native_camera_data"
            and type(step["exit_code"]) is int
            and step["exit_code"] == 0
            and report["source_sha256"] == source_sha256
            and report["session_id"] == session_id
            and _sha(report["workflow_sha256"])
            and type(frame["frame_index"]) is int
            and frame["frame_index"] == 0
            and frame["live"] is False
            and frame["frame_content_verified"] is True
            and frame["provenance"] == "DERIVED_PREVIEW_OF_RETAINED_PHYSICAL_YUY2"
            and all(
                _sha(frame[key])
                for key in (
                    "native_frame_sha256",
                    "capture_evidence_sha256",
                    "settings_epoch",
                    "endpoint_sha256",
                    "manifest_sha256",
                    "preview_sha256",
                )
            )
        ):
            return None
        return dict(
            operation_id=request_key,
            result_sha256=done["result_sha256"],
            **{
                key: frame[key]
                for key in (
                    "attempt_id",
                    "native_frame_sha256",
                    "capture_evidence_sha256",
                    "settings_epoch",
                    "endpoint_sha256",
                )
            },
        )
    except (KeyError, TypeError, ValueError, AttributeError, RecursionError):
        return None


def verify_operating_capture_pixels(
    native, *, reference, request_key, assigned_parent, settings_epoch, cancelled
):
    """Historical launch-reference check; it does not create original provenance."""
    return _verify_pixels(
        native,
        reference=reference,
        request_key=request_key,
        assigned_parent=assigned_parent,
        settings_epoch=settings_epoch,
        cancelled=cancelled,
        checksum=None,
    )


def verify_sealed_operating_capture_pixels(
    native, *, checksum, request_key, assigned_parent, settings_epoch, cancelled
):
    """Check a separately authenticated M1 checksum, without a launch-log import.

    The caller must read/authenticate the original collection and receipt. This
    function independently validates its native join but issues no authority.
    The small mapping below is read context, not a fabricated historical log.
    """
    if type(checksum) is not CameraCaptureChecksum:
        raise ValueError("EXACT_ORIGINAL_CAPTURE_CHECKSUM_REQUIRED")
    checksum = verify_capture_checksum(
        checksum.payload,
        evidence=native.evidence,
        expected_request_key=request_key,
        expected_sha256=checksum.sha256,
    )
    data = checksum.to_dict()
    if data["status"] != "CAPTURE_BYTES_HASHED":
        raise ValueError("ORIGINAL_CAPTURE_CHECKSUM_NOT_SUCCESSFUL")
    request = native.preparation.camera_plan.request
    reference = dict(
        operation_id=request_key,
        attempt_id=request.campaign_id,
        capture_evidence_sha256=native.expected_evidence_sha256,
        settings_epoch=settings_epoch,
        endpoint_sha256=request.binding.endpoint_sha256,
        result_sha256=None,
        native_frame_sha256=data["frame"]["sha256"],
    )
    return _verify_pixels(
        native,
        reference=reference,
        request_key=request_key,
        assigned_parent=assigned_parent,
        settings_epoch=settings_epoch,
        cancelled=cancelled,
        checksum=checksum,
    )


def _verify_pixels(
    native,
    *,
    reference,
    request_key,
    assigned_parent,
    settings_epoch,
    cancelled,
    checksum
):
    """One bounded read in an exact native output directory; no new files.

    Called inside the existing original-owner scope. `cancelled` checks only
    Stop and its original deadline per chunk; expensive source/owner checks
    bracket this call in the original assessor. No timeout is renewed here.
    """
    request = native.preparation.camera_plan.request
    result = dict(
        schema=SEALED_SCHEMA if checksum is not None else SCHEMA,
        request_key=request_key,
        attempt_id=request.campaign_id,
        status="LOGGED_REFERENCE_UNAVAILABLE",
        reference_scope=(
            SEALED_REFERENCE_SCOPE if checksum is not None else REFERENCE_SCOPE
        ),
        result_sha256=None,
        native_frame_sha256=None,
        verified_bytes=0,
        content_verified_at_read=False,
        frame_freshness_assessed=False,
        original_stage_record_retained=False,
        physical_authority=False,
    )
    if checksum is not None:
        result["capture_checksum_sha256"] = checksum.sha256

    def check():
        stopped = cancelled()
        if type(stopped) is not bool:
            raise TypeError("PIXEL_CANCELLATION_MUST_RETURN_BOOL")
        if stopped:
            raise CameraDatasetCancelled("OPERATING_PIXEL_CHECK_INTERRUPTED")

    check()
    if reference is None:
        return result
    result["status"] = "REFERENCE_MISMATCH"
    if not (
        reference["operation_id"] == request_key
        and reference["attempt_id"] == request.campaign_id
        and reference["capture_evidence_sha256"] == native.expected_evidence_sha256
        and reference["settings_epoch"] == settings_epoch
        and reference["endpoint_sha256"] == request.binding.endpoint_sha256
    ):
        return result
    # Independent pair decoding is pure; it must not hash today's pixels and
    # then treat that newly invented digest as the old capture's reference.
    observed = _verified_observation(
        native.evidence,
        prepared=native.preparation,
        expected_evidence_sha256=native.expected_evidence_sha256,
        expected_supervision_sha256=native.expected_supervision_sha256,
    )
    receipt = observed.native_receipt
    if not (
        observed.process_cleanup_confirmed
        and receipt is not None
        and receipt.status == "OK"
        and receipt.cleanup_confirmed
        and request.operation == "capture"
        and request.budget.max_frames == 1
        and len(receipt.frames) == 1
        and receipt.observed_mode is not None
        and request.mode is not None
        and request.mode.same_format(receipt.observed_mode)
    ):
        return result
    metadata = receipt.frames[0]
    mode = receipt.observed_mode
    length = abs(metadata.stride_bytes) * mode.height
    if not (
        metadata.filename == "frame-000000.yuy2"
        and metadata.host_sequence == 0
        and 0
        < length
        == metadata.length_bytes
        <= min(
            MAX_FRAME_BYTES,
            request.budget.max_frame_bytes,
            request.budget.max_total_bytes,
        )
        and abs(metadata.stride_bytes) >= mode.width * 2
        and metadata.row0_offset_bytes
        == (
            0
            if metadata.stride_bytes > 0
            else abs(metadata.stride_bytes) * (mode.height - 1)
        )
    ):
        return result
    parent = Path(assigned_parent)
    capture_parent = parent / ("native-camera-" + request.campaign_id)
    capture = capture_parent / ("capture-" + request.campaign_id)
    if str(capture) != request.output_directory:
        return result
    result["result_sha256"] = reference["result_sha256"]
    result["native_frame_sha256"] = reference["native_frame_sha256"]
    artifact = NativeFrameArtifact(
        **asdict(metadata), sha256=reference["native_frame_sha256"]
    )
    try:
        # Pin every selected output ancestor; reject links, replacement, extra
        # files, truncation and changed bytes without repairing or recapturing.
        with ExitStack() as guards:
            for path in (parent, capture_parent, capture):
                guards.enter_context(
                    _directory_guard(
                        safe_root(path), confirm_handle_cleanup=checksum is not None
                    )
                )
            check()
            with _locked_file(capture / metadata.filename, length) as stream:
                from itertools import islice

                if [p.name for p in islice(capture.iterdir(), 2)] != [
                    metadata.filename
                ]:
                    raise CameraCaptureIngestError("OPERATING_PIXEL_INVENTORY_CHANGED")
                for _ in _blocks(stream, artifact, cancelled):
                    check()
                if [p.name for p in islice(capture.iterdir(), 2)] != [
                    metadata.filename
                ]:
                    raise CameraCaptureIngestError("OPERATING_PIXEL_INVENTORY_CHANGED")
                check()
        check()  # Include guard/handle cleanup before declaring a verified read.
    except CameraDatasetCancelled:
        raise
    except (OSError, ValueError):
        check()  # An expired operation cannot publish an ordinary file failure.
        result["status"] = "PIXEL_FILE_UNAVAILABLE_OR_CHANGED"
        return result
    result.update(
        status="VERIFIED_AT_READ", verified_bytes=length, content_verified_at_read=True
    )
    return result
