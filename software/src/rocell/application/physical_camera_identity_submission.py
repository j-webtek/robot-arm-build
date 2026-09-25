"""Pure original stage-4 metadata subjects; never opens a device or qualifies it.

The original store authenticates role labels and committed history. These
codecs separately authenticate complete producer reports and exact cross-role
bindings. A review acknowledges metadata, not USB identity, camera activation,
installation or motion. Missing physical observations always remain BLOCKED.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any

from .physical_camera_prerequisites import PhysicalCameraPrerequisites
from .physical_camera_selection import selection_from_enrollment_snapshot
from .physical_onboarding import STAGE_ORDER, _parse_evidence_reference
from .physical_received_camera_submission import ReceivedCameraSubmission
from .wizard_camera_helper_registration import WizardCameraHelperRegistration
from .wizard_native_camera_enrollment import verify_native_camera_enrollment_snapshot
from .wizard_native_camera_metadata import validate_native_packet
from rocell.providers.windows.camera_worker_client import NativeCameraIdentityReceipt

MAX_COLLECTIONS = 4
ROLE_BYTES = dict(
    metadata=896 * 1024,
    helper=240 * 1024,
    receipt=32 * 1024,
    assessment=16 * 1024,
    review=16 * 1024,
)
FLAGS = dict(
    physical_authority=False,
    hardware_qualified=False,
    native_release_allowed=False,
    device_io_performed=False,
    measurement_truth_verified=False,
    authenticated_operator_identity=False,
)
MEANING = (
    "Original metadata evidence and procedural review only. No USB serial "
    "provenance, operating-speed qualification, reconnect/reboot qualification, "
    "camera activation, installed acceptance or physical authority is conferred."
)
_BINDING = {
    "identity_id",
    "source_sha256",
    "cell_id",
    "session_id",
    "header_sha256",
    "origin_launch_id",
    "collection_launch_id",
    "operator_id",
    "prerequisites_sha256",
    "received_camera",
    "identity_request_event_sha256",
}


class CameraIdentitySubmissionError(ValueError):
    def __init__(self, code="CAMERA_IDENTITY_SUBJECT_INVALID"):
        self.code = code
        super().__init__(code)


def _require(condition, code="CAMERA_IDENTITY_SUBJECT_INVALID"):
    if not condition:
        raise CameraIdentitySubmissionError(code)


def canonical(value):
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _same(left, right):
    _require(canonical(left) == canonical(right), "CAMERA_IDENTITY_SUBJECT_MISMATCH")


def _exact(value, keys):
    _require(type(value) is dict and set(value) == set(keys))
    return value


def _sha(value):
    _require(
        type(value) is str
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
        and value != "0" * 64
    )


def _text(value, maximum=128):
    _require(
        type(value) is str
        and 0 < len(value) <= maximum
        and value == value.strip()
        and not any(ord(c) < 32 or ord(c) == 127 for c in value)
    )
    _require(len(value.encode("utf-8")) <= maximum)


def _time(value):
    _require(type(value) is int and 0 < value < 2**63)
    return value


def _binding(value):
    _exact(value, _BINDING)
    _require(
        type(value["identity_id"]) is str
        and re.fullmatch(r"cameraidentity-[0-9a-f]{32}", value["identity_id"])
        is not None
    )
    for key in (
        "source_sha256",
        "header_sha256",
        "prerequisites_sha256",
        "identity_request_event_sha256",
    ):
        _sha(value[key])
    for key in ("cell_id", "session_id", "origin_launch_id", "collection_launch_id"):
        _text(value[key])
    _text(value["operator_id"], 64)
    for val in _exact(
        value["received_camera"], {"submission", "assessment", "review"}
    ).values():
        _sha(val)


def _load(payload, role):
    _require(
        type(payload) is bytes and 0 < len(payload) <= ROLE_BYTES[role],
        "CAMERA_IDENTITY_BYTE_LIMIT",
    )

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result)
            result[key] = value
        return result

    try:
        data = json.loads(payload.decode("ascii"), object_pairs_hook=pairs)
        _require(type(data) is dict and canonical(data) == payload)
        stack, nodes = [(data, 0)], 0
        # The complete native producer permits depth24/nodes32000 including
        # keys. Only this stage-owned wrapper gets two more structural levels.
        while stack:
            value, depth = stack.pop()
            nodes += 1
            _require(depth <= 26 and nodes <= 40000, "CAMERA_IDENTITY_STRUCTURE_LIMIT")
            if type(value) is dict:
                stack.extend((v, depth + 1) for pair in value.items() for v in pair)
            elif type(value) is list:
                stack.extend((v, depth + 1) for v in value)
        return data
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        if isinstance(error, CameraIdentitySubmissionError):
            raise
        raise CameraIdentitySubmissionError() from error


def _base(data, role, extra):
    _exact(data, {"schema", "binding", "sequence", "meaning", *FLAGS, *extra})
    _require(
        data["schema"] == f"rocell.camera_identity_{role}.v1"
        and data["meaning"] == MEANING
    )
    _require(all(data[k] is False for k in FLAGS))
    _binding(data["binding"])
    _require(type(data["sequence"]) is int and 1 <= data["sequence"] <= MAX_COLLECTIONS)


def _document(role, binding, sequence, **extra):
    return dict(
        schema=f"rocell.camera_identity_{role}.v1",
        binding=binding,
        sequence=sequence,
        meaning=MEANING,
        **FLAGS,
        **extra,
    )


def _metadata(payload):
    data = _load(payload, "metadata")
    _base(data, "metadata", {"collected_at_ns", "enrollment", "selection"})
    _time(data["collected_at_ns"])
    binding = data["binding"]
    expected = dict(
        source_sha256=binding["source_sha256"],
        launch_session_id=binding["collection_launch_id"],
    )
    # The full report is re-derived by the existing pure registry, including a
    # reviewed-but-held endpoint. That held state must never create a selection.
    report = verify_native_camera_enrollment_snapshot(data["enrollment"], **expected)
    selected = selection_from_enrollment_snapshot(report, **expected)
    _same(
        data["selection"],
        (
            None
            if selected is None
            else {"document": selected.identity_document, "sha256": selected.sha256}
        ),
    )
    return data


def _helper(payload):
    data = _load(payload, "helper")
    _base(data, "helper", {"collected_at_ns", "helper_report"})
    _time(data["collected_at_ns"])
    report = _exact(
        data["helper_report"],
        {"schema", "view", "inspection_report", "registration_artifact"},
    )
    artifact = _exact(
        report["registration_artifact"], {"payload", "registration_sha256"}
    )
    saved = artifact["payload"]
    # Replaying pure constructors verifies historical bytes, not current files
    # or a live provider; no registration is installed into application state.
    owner = WizardCameraHelperRegistration(
        "physical",
        data["binding"]["collection_launch_id"],
        data["binding"]["source_sha256"],
    )
    owner.ingest(
        report["inspection_report"],
        operation_id=saved["inspection_operation_id"],
        operator_id=saved["inspection_operator_id"],
    )
    owner.review(saved["reviewer_id"], operation_id=saved["review_operation_id"])
    _same(owner.export_snapshot(), report)
    return data


def identity_question(prerequisites):
    _require(type(prerequisites) is PhysicalCameraPrerequisites)
    stage = prerequisites.to_dict()["requirements"]["stages"][3]
    _require(stage["stage"] == STAGE_ORDER[3].value)
    rows = stage["intake_rows"]
    _require(len(rows) == 1 and rows[0]["record_id"] == "INT-018")
    return rows[0]


def _observation(value):
    _exact(value, {"record_id", "state", "value", "method", "evidence_note"})
    _require(
        value["record_id"] == "INT-018"
        and type(value["state"]) is str
        and value["state"] in {"UNKNOWN", "OBSERVED"}
    )
    for key, size in (("value", 1024), ("method", 512), ("evidence_note", 1024)):
        _text(value[key], size)


def _receipt(payload, prerequisites):
    data = _load(payload, "receipt")
    _base(
        data,
        "receipt",
        {
            "predecessor",
            "submitted_at_ns",
            "metadata_reference",
            "helper_reference",
            "metadata_sha256",
            "helper_sha256",
            "question",
            "observation",
        },
    )
    _time(data["submitted_at_ns"])
    _same(data["question"], identity_question(prerequisites))
    _require(data["binding"]["prerequisites_sha256"] == prerequisites.evidence_sha256)
    _observation(data["observation"])
    if data["sequence"] == 1:
        _require(data["predecessor"] is None)
    else:
        for val in _exact(
            data["predecessor"], {"receipt", "assessment", "review"}
        ).values():
            _sha(val)
    for role in ("metadata", "helper"):
        ref = _parse_evidence_reference(data[role + "_reference"])
        _require(
            ref.stage is STAGE_ORDER[3]
            and ref.payload_sha256 == data[role + "_sha256"]
            and 0 < ref.payload_bytes <= ROLE_BYTES[role]
        )
        _sha(data[role + "_sha256"])
    return data


def _assessment(payload):
    data = _load(payload, "assessment")
    _base(
        data,
        "assessment",
        {"receipt_sha256", "checks", "missing_requirements", "verdict"},
    )
    _sha(data["receipt_sha256"])
    _require(data["verdict"] == "BLOCKED")
    _exact(
        data["checks"],
        {
            "received_serial_reported_match",
            "endpoint_selection_available",
            "native_review_blockers",
            "driver_protocol_schema",
            "exact_devnode_driver_observed",
            "driver_field_availability",
            "generic_driver_service_matches",
            "operator_observation_state",
        },
    )
    missing = data["missing_requirements"]
    _require(
        type(missing) is list
        and 1 <= len(missing) <= 16
        and all(type(v) is str for v in missing)
        and sorted(set(missing)) == missing
    )
    return data


def _review(payload):
    data = _load(payload, "review")
    _base(
        data,
        "review",
        {
            "receipt_sha256",
            "assessment_sha256",
            "decision",
            "reviewer_id",
            "review_launch_id",
            "reviewed_at_ns",
            "verdict",
        },
    )
    for key in ("receipt_sha256", "assessment_sha256"):
        _sha(data[key])
    _text(data["reviewer_id"], 64)
    _text(data["review_launch_id"])
    _time(data["reviewed_at_ns"])
    _require(
        type(data["decision"]) is str
        and data["decision"] in {"ACKNOWLEDGE_EXACT", "REJECT"}
        and data["verdict"] == "BLOCKED"
        and data["reviewer_id"].casefold() != data["binding"]["operator_id"].casefold()
    )
    return data


class _Subject:
    payload: bytes

    def to_dict(self):
        return json.loads(self.payload)

    @property
    def sha256(self):
        return hashlib.sha256(self.payload).hexdigest()

    def safe_summary(self):
        data = self.to_dict()
        summary = dict(
            schema=data["schema"],
            sha256=self.sha256,
            identity_id=data["binding"]["identity_id"],
            sequence=data["sequence"],
            verdict=data.get("verdict"),
            meaning=MEANING,
            **FLAGS,
        )
        if "checks" in data:
            summary.update(
                checks=data["checks"], missing_requirements=data["missing_requirements"]
            )
        return summary


@dataclass(frozen=True, slots=True)
class CameraIdentityMetadata(_Subject):
    payload: bytes

    def __post_init__(self):
        _metadata(self.payload)


@dataclass(frozen=True, slots=True)
class CameraIdentityHelper(_Subject):
    payload: bytes

    def __post_init__(self):
        _helper(self.payload)


@dataclass(frozen=True, slots=True)
class CameraIdentityReceipt(_Subject):
    payload: bytes
    prerequisites: PhysicalCameraPrerequisites = field(repr=False, compare=False)

    def __post_init__(self):
        _receipt(self.payload, self.prerequisites)


@dataclass(frozen=True, slots=True)
class CameraIdentityAssessment(_Subject):
    payload: bytes

    def __post_init__(self):
        _assessment(self.payload)


@dataclass(frozen=True, slots=True)
class CameraIdentityReview(_Subject):
    payload: bytes

    def __post_init__(self):
        _review(self.payload)


def _expected(artifact, expected_binding=None, expected_sha256=None):
    if expected_binding is not None:
        _same(artifact.to_dict()["binding"], expected_binding)
    if expected_sha256 is not None:
        _require(artifact.sha256 == expected_sha256, "CAMERA_IDENTITY_HASH_MISMATCH")
    return artifact


def verify_camera_identity_metadata(
    payload, *, expected_binding=None, expected_sha256=None
):
    return _expected(CameraIdentityMetadata(payload), expected_binding, expected_sha256)


def verify_camera_identity_helper(
    payload, *, expected_binding=None, expected_sha256=None
):
    return _expected(CameraIdentityHelper(payload), expected_binding, expected_sha256)


def _join(receipt, metadata, helper, received_submission):
    _require(
        type(receipt) is CameraIdentityReceipt
        and type(metadata) is CameraIdentityMetadata
        and type(helper) is CameraIdentityHelper
        and type(received_submission) is ReceivedCameraSubmission
    )
    data, native, registered = receipt.to_dict(), metadata.to_dict(), helper.to_dict()
    for role, artifact in (("metadata", metadata), ("helper", helper)):
        other = artifact.to_dict()
        _same(data["binding"], other["binding"])
        _require(
            data["sequence"] == other["sequence"]
            and data["submitted_at_ns"] >= other["collected_at_ns"]
        )
        ref = _parse_evidence_reference(data[role + "_reference"])
        _require(
            ref.payload_bytes == len(artifact.payload)
            and data[role + "_sha256"] == artifact.sha256
        )
    binding = data["binding"]
    previous = received_submission.to_dict()["binding"]
    for key in (
        "source_sha256",
        "cell_id",
        "session_id",
        "header_sha256",
        "origin_launch_id",
        "prerequisites_sha256",
    ):
        _same(binding[key], previous[key])
    _require(binding["received_camera"]["submission"] == received_submission.sha256)
    _same(
        native["enrollment"]["view"]["provenance"]["helper_sha256"],
        registered["helper_report"]["registration_artifact"]["payload"][
            "helper_sha256"
        ],
    )


def verify_camera_identity_receipt(
    payload,
    *,
    prerequisites,
    metadata,
    helper,
    received_submission,
    predecessor=None,
    expected_sha256=None,
):
    receipt = CameraIdentityReceipt(payload, prerequisites)
    _join(receipt, metadata, helper, received_submission)
    data = receipt.to_dict()
    if predecessor is None:
        _require(data["sequence"] == 1 and data["predecessor"] is None)
    else:
        _require(type(predecessor) is tuple and len(predecessor) == 3)
        old, assessment, review = predecessor
        verify_camera_identity_review(
            review.payload, receipt=old, assessment=assessment
        )
        expected = {
            role: artifact.sha256
            for role, artifact in zip(("receipt", "assessment", "review"), predecessor)
        }
        _same(data["predecessor"], expected)
        _require(
            data["sequence"] == old.to_dict()["sequence"] + 1
            and data["submitted_at_ns"] >= review.to_dict()["reviewed_at_ns"]
        )
        # A new collection may have a different launch/operator, not a different
        # original session, received camera or entry event.
        for key in _BINDING - {"identity_id", "collection_launch_id", "operator_id"}:
            _same(data["binding"][key], old.to_dict()["binding"][key])
        _require(
            data["binding"]["identity_id"] != old.to_dict()["binding"]["identity_id"]
        )
    return _expected(receipt, expected_sha256=expected_sha256)


def build_camera_identity_metadata(
    binding, sequence, enrollment, selection, collected_at_ns
):
    return CameraIdentityMetadata(
        canonical(
            _document(
                "metadata",
                binding,
                sequence,
                enrollment=enrollment,
                selection=selection,
                collected_at_ns=collected_at_ns,
            )
        )
    )


def build_camera_identity_helper(binding, sequence, helper_report, collected_at_ns):
    return CameraIdentityHelper(
        canonical(
            _document(
                "helper",
                binding,
                sequence,
                helper_report=helper_report,
                collected_at_ns=collected_at_ns,
            )
        )
    )


def build_camera_identity_receipt(
    prerequisites,
    *,
    metadata,
    helper,
    received_submission,
    metadata_reference,
    helper_reference,
    observation,
    submitted_at_ns,
    predecessor=None,
):
    subject = metadata.to_dict()
    data = _document(
        "receipt",
        subject["binding"],
        subject["sequence"],
        predecessor=(
            None
            if predecessor is None
            else {
                role: obj.sha256
                for role, obj in zip(("receipt", "assessment", "review"), predecessor)
            }
        ),
        submitted_at_ns=submitted_at_ns,
        metadata_reference=metadata_reference.to_dict(),
        helper_reference=helper_reference.to_dict(),
        metadata_sha256=metadata.sha256,
        helper_sha256=helper.sha256,
        observation=observation,
        question=identity_question(prerequisites),
    )
    return verify_camera_identity_receipt(
        canonical(data),
        prerequisites=prerequisites,
        metadata=metadata,
        helper=helper,
        received_submission=received_submission,
        predecessor=predecessor,
    )


def assess_camera_identity(receipt, *, metadata, helper, received_submission):
    _join(receipt, metadata, helper, received_submission)
    data, report = receipt.to_dict(), metadata.to_dict()["enrollment"]
    packet = report["identity_packet"]
    _, observed = validate_native_packet(
        packet,
        kind="identity",
        provenance=packet["provenance"],
        helper_sha256=packet["helper_sha256"],
        expected_endpoint=packet["receipt"]["requested_endpoint"],
    )
    _require(type(observed) is NativeCameraIdentityReceipt)
    driver = observed.driver
    names = ("provider", "service", "version", "inf_path")
    availability = {
        name: "NOT_RETAINED" if driver is None else getattr(driver, name).availability
        for name in names
    }
    complete = driver is not None and all(
        getattr(driver, name).observed for name in names
    )
    candidate = report["generic_review"]["candidate_record"]
    generic_service = candidate.get("driver_service")
    service_match = bool(
        complete and generic_service and driver.service.value == generic_service
    )
    inspection = received_submission.to_dict()["inspection"]
    serial = candidate["usb_identity"].get("unit_serial")
    serial_match = bool(
        inspection and serial and serial == inspection["observed_camera_serial"]
    )
    checks = dict(
        received_serial_reported_match=serial_match,
        endpoint_selection_available=metadata.to_dict()["selection"] is not None,
        native_review_blockers=report["view"]["blockers"],
        driver_protocol_schema=observed.protocol_schema,
        exact_devnode_driver_observed=complete,
        driver_field_availability=availability,
        generic_driver_service_matches=service_match,
        operator_observation_state=data["observation"]["state"],
    )
    missing = {
        "USB_DESCRIPTOR_SERIAL_PROVENANCE_REQUIRED",
        "USB_OPERATING_TOPOLOGY_AND_SPEED_REQUIRED",
        "RECONNECT_AND_REBOOT_IDENTITY_EVIDENCE_REQUIRED",
        "RECEIVED_LABEL_USB_CORRELATION_REQUIRED",
    }
    if not checks["endpoint_selection_available"]:
        missing.add("ENDPOINT_METADATA_REVIEW_HELD")
    if not complete:
        missing.add("EXACT_DEVNODE_DRIVER_PROPERTIES_REQUIRED")
    if not service_match:
        missing.add("GENERIC_NATIVE_DRIVER_SERVICE_CORRELATION_REQUIRED")
    if data["observation"]["state"] == "UNKNOWN":
        missing.add("INT018_OBSERVATION_NOT_RECORDED")
    return CameraIdentityAssessment(
        canonical(
            _document(
                "assessment",
                data["binding"],
                data["sequence"],
                receipt_sha256=receipt.sha256,
                checks=checks,
                missing_requirements=sorted(missing),
                verdict="BLOCKED",
            )
        )
    )


def verify_camera_identity_assessment(
    payload, *, receipt, metadata, helper, received_submission, expected_sha256=None
):
    result = assess_camera_identity(
        receipt,
        metadata=metadata,
        helper=helper,
        received_submission=received_submission,
    )
    _require(
        type(payload) is bytes and payload == result.payload,
        "CAMERA_IDENTITY_ASSESSMENT_MISMATCH",
    )
    return _expected(result, expected_sha256=expected_sha256)


def review_camera_identity(
    receipt, assessment, *, decision, reviewer_id, review_launch_id, reviewed_at_ns
):
    _require(
        type(receipt) is CameraIdentityReceipt
        and type(assessment) is CameraIdentityAssessment
    )
    data, evaluated = receipt.to_dict(), assessment.to_dict()
    _same(data["binding"], evaluated["binding"])
    _require(
        evaluated["receipt_sha256"] == receipt.sha256
        and evaluated["sequence"] == data["sequence"]
        and _time(reviewed_at_ns) >= data["submitted_at_ns"]
    )
    return CameraIdentityReview(
        canonical(
            _document(
                "review",
                data["binding"],
                data["sequence"],
                receipt_sha256=receipt.sha256,
                assessment_sha256=assessment.sha256,
                decision=decision,
                reviewer_id=reviewer_id,
                review_launch_id=review_launch_id,
                reviewed_at_ns=reviewed_at_ns,
                verdict="BLOCKED",
            )
        )
    )


def verify_camera_identity_review(
    payload, *, receipt, assessment, expected_sha256=None
):
    data = CameraIdentityReview(payload).to_dict()
    result = review_camera_identity(
        receipt,
        assessment,
        **{
            key: data[key]
            for key in ("decision", "reviewer_id", "review_launch_id", "reviewed_at_ns")
        },
    )
    _require(result.payload == payload, "CAMERA_IDENTITY_REVIEW_MISMATCH")
    return _expected(result, expected_sha256=expected_sha256)
