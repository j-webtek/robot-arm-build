"""Closed proposal/assessment compound record; parsing proves no provenance.

The original owner must independently authenticate the supplied subjects, retain
this package and read it back on the complete session history. The inner v4
diagnostic stays byte-for-byte historical: its retention hold is never edited
into an approval. This module performs no file/device I/O or stage transition.
"""

from dataclasses import dataclass
import re
from typing import Any

from .camera_capture_dataset import MAX_FRAME_BYTES
from .camera_operating_evidence_preflight import CameraOperatingEvidencePreflight
from .camera_operating_proposal import CameraOperatingProposal
from .camera_operating_stage_requirements import (
    RETENTION_HOLD,
    project_operating_requirements,
)
from .physical_camera_mode_entry import camera_mode_operator_valid
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.owned_worker_process import decode_owned_json

SCHEMA = "rocell.camera_operating_submission.v1"
SOURCE_WORKFLOW_OPERATING_SCHEMA = "rocell.physical_camera_source_workflow_readback.v17"
MAX_BYTES = 80 * 1024
MAX_ASSESSMENT_BYTES = 32 * 1024
STATE = "SUBMITTED_DIAGNOSTIC_NOT_REVIEWED"
SUBMISSION_ID = re.compile(r"cameraoperating-[0-9a-f]{32}\Z")
LABEL = re.compile(r"camera-operating-submission:(cameraoperating-[0-9a-f]{32})\Z")
EVENT = re.compile(r"CAMERA_OPERATING_SUBMITTED_([0-9A-F]{32})\Z")
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_KEY = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
FALSE_FIELDS = (
    "original_store_authenticated",
    "stage_passed",
    "approved_operating_policy",
    "physical_authority",
    "hardware_qualified",
    "connected",
    "device_io_performed",
)
BINDING_FIELDS = (
    "source_sha256",
    "cell_id",
    "session_id",
    "header_sha256",
    "entry_sha256",
    "probe_preparation_sha256",
    "probe_review_sha256",
    "journal_head_sha256",
    "original_records_sha256",
)
_FIELDS = {
    "schema",
    "state",
    "submission_id",
    "operator_id",
    "recorded_at_utc_ns",
    "binding",
    "proposal",
    "proposal_sha256",
    "assessment",
    "assessment_sha256",
    *FALSE_FIELDS,
}
_ASSESSMENT_FALSE = (
    "original_stage_record_retained",
    "approved_operating_policy",
    "physical_authority",
    "hardware_qualified",
    "connected",
)
_ASSESSMENT_FIELDS = {
    "schema",
    "status",
    "original_inputs_authenticated_at_read",
    "session_id",
    "header_sha256",
    "journal_head_sha256",
    "original_records_sha256",
    "proposal_sha256",
    "captures",
    "pixel_checks",
    "pixel_reference_scope",
    "preflight",
    "preflight_sha256",
    "unresolved_checks",
    "stage_requirements",
    "currentness_requires_revalidation",
    "meaning",
    *_ASSESSMENT_FALSE,
}
# An immutable v4 wire meaning, deliberately not imported through the live
# assessor/service ownership graph. A later schema must be reviewed separately.
_ASSESSMENT_MEANING = (
    "Saved original inputs were authenticated at read time. Each pixel check "
    "identifies its original receipt-bound checksum or older launch-only reference. "
    "Legacy references are not promoted to originals. This diagnostic assessment "
    "is not a retained stage assessment, review, connection or calibration."
)
_PIXEL_FALSE = (
    "frame_freshness_assessed",
    "original_stage_record_retained",
    "physical_authority",
)
_PIXEL_FIELDS = {
    "schema",
    "request_key",
    "attempt_id",
    "status",
    "reference_scope",
    "result_sha256",
    "native_frame_sha256",
    "verified_bytes",
    "content_verified_at_read",
    "capture_checksum_sha256",
    *_PIXEL_FALSE,
}


class CameraOperatingSubmissionError(ValueError):
    def __init__(self) -> None:
        super().__init__("CAMERA_OPERATING_SUBMISSION_INVALID")


def _need(ok: bool) -> None:
    if not ok:
        raise CameraOperatingSubmissionError()


def _sha(value: Any) -> None:
    _need(type(value) is str and bool(_HASH.fullmatch(value)) and value != "0" * 64)


def _key(value: Any) -> None:
    _need(type(value) is str and bool(_KEY.fullmatch(value)))


def _assessment(payload: bytes, proposal: CameraOperatingProposal) -> dict[str, Any]:
    """Closed v4 shape/cross-field checks, not original authentication.

    Require two explicit sealed references for this new submission version.
    Existing mixed/legacy diagnostics remain readable by their existing owners;
    they are not silently migrated into this new original-stage subject.
    """
    _need(type(payload) is bytes)
    report = decode_owned_json(payload, maximum=MAX_ASSESSMENT_BYTES)
    _need(set(report) == _ASSESSMENT_FIELDS and canonical(report) == payload)
    _need(
        report["schema"] == "rocell.camera_original_operating_assessment.v4"
        and report["status"] == "ORIGINAL_INPUTS_CHECKED_APPROVAL_HELD"
        and report["original_inputs_authenticated_at_read"] is True
        and report["currentness_requires_revalidation"] is True
        and all(report[k] is False for k in _ASSESSMENT_FALSE)
        and report["meaning"] == _ASSESSMENT_MEANING
        and report["pixel_reference_scope"]
        == "PER_CAPTURE_ORIGINAL_OR_LEGACY_REFERENCE"
        and report["proposal_sha256"] == proposal.sha256
    )
    for key in ("header_sha256", "journal_head_sha256", "original_records_sha256"):
        _sha(report[key])
    policy = proposal.to_dict()
    preflight = CameraOperatingEvidencePreflight(canonical(report["preflight"]))
    _need(report["preflight_sha256"] == preflight.sha256)
    data = preflight.to_dict()
    _need(
        data["proposal_sha256"] == proposal.sha256
        and all(
            data[k] == policy["subjects"][k]
            for k in ("capabilities_sha256", "settings_epoch")
        )
        and len(data["captures"]) == 2
    )
    for native in (data["probe"], *data["captures"]):
        # The configuration-v2 path is supervised; legacy unsupervised subjects
        # remain diagnostics, not implicit inputs to this new stage contract.
        _sha(native["supervision_sha256"])
    captures, pixels = report["captures"], report["pixel_checks"]
    _need(
        type(captures) is list
        and type(pixels) is list
        and len(captures) == len(pixels) == 2
    )
    for row, pixel in zip(captures, pixels):
        _need(
            type(row) is dict
            and set(row)
            == {"request_key", "attempt_id", "permit_sha256", "capture_checksum_sha256"}
        )
        for key in ("request_key", "attempt_id"):
            _key(row[key])
        for key in ("permit_sha256", "capture_checksum_sha256"):
            _sha(row[key])
        _need(type(pixel) is dict and set(pixel) == _PIXEL_FIELDS)
        _need(
            pixel["schema"] == "rocell.camera_operating_pixel_check.v2"
            and pixel["reference_scope"] == "M1_SEALED_CAPTURE_CHECKSUM"
            and all(
                pixel[k] == row[k]
                for k in ("request_key", "attempt_id", "capture_checksum_sha256")
            )
            and pixel["result_sha256"] is None
            and all(pixel[k] is False for k in _PIXEL_FALSE)
            and type(pixel["verified_bytes"]) is int
            and type(pixel["content_verified_at_read"]) is bool
        )
        status = pixel["status"]
        _need(
            type(status) is str
            and status
            in (
                "VERIFIED_AT_READ",
                "REFERENCE_MISMATCH",
                "PIXEL_FILE_UNAVAILABLE_OR_CHANGED",
            )
        )
        if status == "REFERENCE_MISMATCH":
            _need(pixel["native_frame_sha256"] is None)
        else:
            _sha(pixel["native_frame_sha256"])
        _need(pixel["content_verified_at_read"] is (status == "VERIFIED_AT_READ"))
        if status == "VERIFIED_AT_READ":
            # A successful bounded YUY2 read cannot be a tiny metadata fixture.
            # Actual signed stride and exact length are checked from originals.
            mode = policy["target_mode"]
            _need(
                mode["width"] * mode["height"] * 2
                <= pixel["verified_bytes"]
                <= MAX_FRAME_BYTES
            )
        else:
            _need(pixel["verified_bytes"] == 0)
    for key in (
        "request_key",
        "attempt_id",
        "permit_sha256",
        "capture_checksum_sha256",
    ):
        _need(len({row[key] for row in captures}) == 2)
    unresolved = [
        key
        for key in data["owner_obligations"]
        if key != "ORIGINAL_STORE_AND_CURRENTNESS_NOT_AUTHENTICATED"
        and not (
            key == "PIXEL_FILES_NOT_VERIFIED"
            and all(p["content_verified_at_read"] for p in pixels)
        )
    ] + [RETENTION_HOLD]
    _need(report["unresolved_checks"] == unresolved)
    _need(
        canonical(report["stage_requirements"])
        == canonical(project_operating_requirements(unresolved, data["failed_checks"]))
    )
    return report


def _document(payload: bytes) -> dict[str, Any]:
    try:
        _need(type(payload) is bytes)
        data = decode_owned_json(payload, maximum=MAX_BYTES)
        _need(set(data) == _FIELDS and canonical(data) == payload)
        _need(data["schema"] == SCHEMA and data["state"] == STATE)
        _need(
            type(data["submission_id"]) is str
            and bool(SUBMISSION_ID.fullmatch(data["submission_id"]))
        )
        _need(camera_mode_operator_valid(data["operator_id"]))
        _need(all(data[k] is False for k in FALSE_FIELDS))
        when = data["recorded_at_utc_ns"]
        _need(type(when) is int and 0 < when < 2**63)
        proposal = CameraOperatingProposal(canonical(data["proposal"]))
        _need(data["proposal_sha256"] == proposal.sha256)
        _need(when >= proposal.to_dict()["recorded_at_utc_ns"])
        raw = canonical(data["assessment"])
        report = _assessment(raw, proposal)
        _need(data["assessment_sha256"] == digest(raw))
        binding = data["binding"]
        _need(type(binding) is dict and set(binding) == set(BINDING_FIELDS))
        for key in BINDING_FIELDS:
            if key not in ("cell_id", "session_id"):
                _sha(binding[key])
        policy = proposal.to_dict()
        _need(
            all(
                binding[k] == policy["entry_binding"][k]
                for k in ("cell_id", "session_id", "source_sha256", "header_sha256")
            )
        )
        _need(binding["entry_sha256"] == policy["subjects"]["entry_sha256"])
        _need(
            all(
                binding[k] == report[k]
                for k in (
                    "session_id",
                    "header_sha256",
                    "journal_head_sha256",
                    "original_records_sha256",
                )
            )
        )
        return data
    except CameraOperatingSubmissionError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        UnicodeError,
    ) as error:
        raise CameraOperatingSubmissionError() from error


@dataclass(frozen=True, slots=True)
class CameraOperatingSubmission:
    """Structurally valid immutable data, never a currentness/admission token."""

    payload: bytes

    def __post_init__(self) -> None:
        _document(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _document(self.payload)


def build_camera_operating_submission(
    *,
    submission_id: str,
    operator_id: str,
    recorded_at_utc_ns: int,
    binding: dict[str, str],
    proposal_payload: bytes,
    assessment_payload: bytes,
) -> CameraOperatingSubmission:
    """Build from independently supplied original-owner inputs, with no I/O."""
    try:
        proposal = CameraOperatingProposal(proposal_payload)
        report = _assessment(assessment_payload, proposal)
        return CameraOperatingSubmission(
            canonical(
                dict(
                    schema=SCHEMA,
                    state=STATE,
                    submission_id=submission_id,
                    operator_id=operator_id,
                    recorded_at_utc_ns=recorded_at_utc_ns,
                    binding=binding,
                    proposal=proposal.to_dict(),
                    proposal_sha256=proposal.sha256,
                    assessment=report,
                    assessment_sha256=digest(assessment_payload),
                    **{key: False for key in FALSE_FIELDS},
                )
            )
        )
    except CameraOperatingSubmissionError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        UnicodeError,
    ) as error:
        raise CameraOperatingSubmissionError() from error


def verify_camera_operating_submission(
    payload: bytes,
    *,
    expected_sha256: str,
    expected_binding: dict[str, str],
    expected_proposal_payload: bytes,
    expected_assessment_payload: bytes,
) -> CameraOperatingSubmission:
    """Compare against independently authenticated subjects, not its own hashes.

    This pure comparison does not authenticate its arguments. The original owner
    must supply them from its scoped store and independently verified history.
    """
    _sha(expected_sha256)
    subject = CameraOperatingSubmission(payload)
    _need(subject.sha256 == expected_sha256)
    data = subject.to_dict()
    rebuilt = build_camera_operating_submission(
        **{k: data[k] for k in ("submission_id", "operator_id", "recorded_at_utc_ns")},
        binding=expected_binding,
        proposal_payload=expected_proposal_payload,
        assessment_payload=expected_assessment_payload,
    )
    _need(rebuilt.payload == payload)
    return subject


def camera_operating_submission_label(submission_id: str) -> str:
    _need(type(submission_id) is str and bool(SUBMISSION_ID.fullmatch(submission_id)))
    return "camera-operating-submission:" + submission_id


def camera_operating_submission_event(submission_id: str) -> str:
    camera_operating_submission_label(submission_id)
    # The journal's closed detail-code grammar requires uppercase hex, while
    # payload IDs and package labels retain their lowercase UUID convention.
    return (
        "CAMERA_OPERATING_SUBMITTED_"
        + submission_id.removeprefix("cameraoperating-").upper()
    )
