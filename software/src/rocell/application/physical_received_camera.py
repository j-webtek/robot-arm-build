"""Pure received-camera record completeness, not physical stage acceptance.

The notebook is an original question/observation record, not structured camera
identity. Existing CameraReceiptInspection supplies that separate contract. No
narrative parsing invents a model, serial, lens mount or numeric acceptance limit.
Only the supplied notebook bytes are verified here; the original stage owner
must read every referenced package under its existing leases before review.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from decimal import Decimal
import hashlib
import json
import re
from typing import Any

from .commissioning_camera_persistence import physical_camera_source_binding
from .physical_camera_prerequisites import PhysicalCameraPrerequisites
from .physical_intake_notebook import PhysicalIntakeNotebook
from .physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
    _parse_evidence_reference,
)
from .physical_onboarding_receipts import (
    BoundEvidence,
    CameraReceiptInspection,
    assess_camera_receipt,
)

SCHEMA = "rocell.received_camera_record_assessment.v1"
SUMMARY_SCHEMA = "rocell.received_camera_record_assessment_summary.v1"
MAX_ASSESSMENT_BYTES = 128 * 1024
MAX_SUMMARY_BYTES = 24 * 1024
FLAGS = {
    "physical_authority": False,
    "hardware_qualified": False,
    "canonical_stage_pass": False,
    "device_io_performed": False,
    "attachment_bytes_verified": False,
}
RECORD_IDS = (
    "INT-001",
    "INT-002",
    "INT-003",
    "INT-004",
    "INT-005",
    "INT-006",
    "INT-007",
    "INT-008",
    "INT-009",
    "INT-017",
    "INT-019",
    "INT-020",
    "INT-021",
    "INT-022",
    "INT-023",
    "INT-024",
)
RESIDUALS = [
    "ORIGINAL_REFERENCED_PACKAGES_REQUIRE_LEASED_READBACK",
    "NARRATIVE_AND_STRUCTURED_INSPECTION_REQUIRE_EXACT_SUBJECT_REVIEW",
    "INT_005_FLATNESS_LIMIT_DEFERRED_TO_TARGET_ACCURACY_BUDGET",
    "MOUNT_THREAD_LENS_MOUNT_AND_BENCH_ACCEPTANCE_NOT_INFERRED",
    "RECEIVED_DIMENSIONS_AND_MASS_HAVE_NO_INVENTED_NOMINAL_TOLERANCE",
    "USB_IDENTITY_OPTICAL_LOAD_COLLISION_AND_NATIVE_RELEASE_REMAIN_SEPARATE",
]
MEANING = (
    "RECEIPT_COMPLETE describes record completeness and the explicit receipt "
    "checks only, never physical stage PASS. Operator narratives are retained "
    "without identity parsing. No attachment authentication, installed geometry, "
    "flatness acceptance, lens-mount resolution or native release is inferred."
)
_BINDING = {
    "receipt_id",
    "source_sha256",
    "cell_id",
    "session_id",
    "header_sha256",
    "origin_launch_id",
    "collection_launch_id",
    "operator_id",
    "prerequisites_sha256",
    "static_contract",
    "camera_request_event_sha256",
}


class ReceivedCameraError(ValueError):
    def __init__(self, code: str = "RECEIVED_CAMERA_RECORD_INVALID"):
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str = "RECEIVED_CAMERA_RECORD_INVALID") -> None:
    if not condition:
        raise ReceivedCameraError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _digest(value: Any) -> None:
    _require(
        type(value) is str
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
        and value != "0" * 64
    )


def _exact(value: Any, fields: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == fields)
    return value


def _same(left: Any, right: Any) -> None:
    _require(_canonical(left) == _canonical(right))


def _binding(value: Any) -> dict[str, Any]:
    data = _exact(value, _BINDING)
    for key in (
        "source_sha256",
        "header_sha256",
        "prerequisites_sha256",
        "camera_request_event_sha256",
    ):
        _digest(data[key])
    for key, pattern in (
        ("receipt_id", r"receivedcamera-[0-9a-f]{32}"),
        ("cell_id", r"wizard-physical-camera-[0-9a-f]{16}"),
        ("session_id", r"physical-camera-[0-9a-f]{32}"),
        ("origin_launch_id", r"wizard-[0-9a-f]{32}"),
        ("collection_launch_id", r"wizard-[0-9a-f]{32}"),
        ("operator_id", r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}"),
    ):
        _require(
            type(data[key]) is str and re.fullmatch(pattern, data[key]) is not None
        )
    for digest in _exact(
        data["static_contract"], {"receipt", "assessment", "review"}
    ).values():
        _digest(digest)
    return data


def _load(payload: bytes) -> dict[str, Any]:
    _require(type(payload) is bytes and 0 < len(payload) <= MAX_ASSESSMENT_BYTES)

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result)
            result[key] = value
        return result

    def bad(value):
        raise ReceivedCameraError()

    try:
        data = json.loads(
            payload.decode("ascii"),
            object_pairs_hook=pairs,
            parse_float=bad,
            parse_constant=bad,
        )
        _require(type(data) is dict and _canonical(data) == payload)
        stack, nodes = [(data, 0)], 0
        while stack:
            value, depth = stack.pop()
            nodes += 1
            _require(nodes <= 8192 and depth <= 16)
            if type(value) is dict:
                stack.extend((item, depth + 1) for item in value.values())
            elif type(value) is list:
                stack.extend((item, depth + 1) for item in value)
            elif type(value) is int:
                _require(-(2**63) < value < 2**63)
        return data
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as error:
        raise ReceivedCameraError() from error


def _reference(value: Any, notebook: PhysicalIntakeNotebook) -> BoundEvidence | None:
    if value is None:
        return None
    reference = BoundEvidence.from_reference(_parse_evidence_reference(value))
    _require(
        reference.stage is PhysicalOnboardingStage.CAMERA_RECEIPT,
        "NOTEBOOK_ORIGINAL_STAGE_MISMATCH",
    )
    _require(
        reference.payload_sha256 == notebook.sha256
        and reference.payload_bytes == len(notebook.payload),
        "NOTEBOOK_ORIGINAL_BYTES_MISMATCH",
    )
    return reference


def _derive(
    binding: dict[str, Any],
    notebook: PhysicalIntakeNotebook,
    inspection: CameraReceiptInspection | None,
    reference: BoundEvidence | None,
) -> dict[str, Any]:
    rows = notebook.to_dict()["rows"]
    _require(tuple(row["record_id"] for row in rows) == RECORD_IDS)
    missing = []
    if reference is None:
        missing.append("NOTEBOOK_CAMERA_STAGE_ORIGINAL_NOT_BOUND")
    observations = {}
    row_checks = []
    for row in rows:
        observation = row["observation"]
        observed = observation is not None and observation["status"] == "OBSERVED"
        status = (
            "OBSERVED"
            if observed
            else ("UNKNOWN" if observation is not None else "UNRECORDED")
        )
        if not observed:
            missing.append(row["record_id"] + "_OBSERVATION_REQUIRED")
        else:
            observations[row["record_id"]] = observation["observed_value"]
        # Decimal representation/positivity already belongs to the exact
        # notebook validator, not a new float coercion or nominal tolerance.
        row_checks.append(
            {
                "record_id": row["record_id"],
                "observation_status": status,
                "acceptance": (
                    "DEFERRED_LIMIT"
                    if row["record_id"] == "INT-005"
                    else (
                        "THICKNESS_ACCOMMODATION"
                        if row["record_id"] in {"INT-003", "INT-004"}
                        else "RECORDED_NOT_QUALIFIED"
                    )
                ),
            }
        )
    low, high = observations.get("INT-003"), observations.get("INT-004")
    thickness = "UNOBSERVED"
    if low is not None and high is not None:
        thickness = (
            "WITHIN_ACCOMMODATION"
            if Decimal("17.5") <= Decimal(low) <= Decimal(high) <= Decimal("18.5")
            else "OUTSIDE_ACCOMMODATION"
        )
        if thickness == "OUTSIDE_ACCOMMODATION":
            missing.append("BOARD_THICKNESS_OUTSIDE_ACCOMMODATION")
    camera_assessment = None
    if inspection is None:
        missing.append("STRUCTURED_CAMERA_INSPECTION_REQUIRED")
    else:
        for item in inspection.binding.evidence:
            _parse_evidence_reference(item.to_dict())
        _require(
            inspection.binding.source_binding_sha256
            == physical_camera_source_binding(binding["source_sha256"])
            and inspection.binding.session_header_sha256 == binding["header_sha256"]
            and inspection.binding.session_id == binding["session_id"]
            and inspection.binding.cell_id == binding["cell_id"]
            and inspection.operator_id == binding["operator_id"],
            "CAMERA_INSPECTION_ORIGINAL_CONTEXT_MISMATCH",
        )
        if reference is None or reference not in inspection.binding.evidence:
            missing.append("INSPECTION_NOTEBOOK_REFERENCE_NOT_BOUND")
        assessed = assess_camera_receipt(inspection)
        camera_assessment = assessed.to_dict()
        if not assessed.diagnostic_ready:
            missing.extend(assessed.reason_codes)
    return {
        "status": "RECEIPT_INCOMPLETE" if missing else "RECEIPT_COMPLETE",
        "coverage": notebook.to_dict()["coverage"],
        "row_checks": row_checks,
        "thickness": {
            "minimum_mm": low,
            "maximum_mm": high,
            "status": thickness,
            "allowed_minimum_mm": "17.5",
            "allowed_maximum_mm": "18.5",
        },
        "flatness_acceptance": "DEFERRED_LIMIT",
        "inspection_assessment": camera_assessment,
        "missing_requirements": missing,
    }


def _validate(
    payload: bytes, prerequisites: PhysicalCameraPrerequisites
) -> dict[str, Any]:
    _require(type(prerequisites) is PhysicalCameraPrerequisites)
    data = _load(payload)
    _exact(
        data,
        {
            "schema",
            "binding",
            "notebook",
            "notebook_sha256",
            "notebook_reference",
            "inspection",
            "inspection_sha256",
            "status",
            "coverage",
            "row_checks",
            "thickness",
            "flatness_acceptance",
            "inspection_assessment",
            "missing_requirements",
            "residuals",
            "meaning",
            *FLAGS,
        },
    )
    _require(
        data["schema"] == SCHEMA
        and data["residuals"] == RESIDUALS
        and data["meaning"] == MEANING
    )
    _require(all(data[key] is False for key in FLAGS))
    binding = _binding(data["binding"])
    notebook = PhysicalIntakeNotebook.from_payload(
        _canonical(data["notebook"]),
        prerequisites=prerequisites,
        expected_sha256=data["notebook_sha256"],
    )
    nb = notebook.to_dict()["binding"]
    for key in (
        "source_sha256",
        "session_id",
        "origin_launch_id",
        "prerequisites_sha256",
    ):
        _same(binding[key], nb[key])
    _same(binding["collection_launch_id"], nb["launch_session_id"])
    reference = _reference(data["notebook_reference"], notebook)
    inspection = None
    if data["inspection"] is not None:
        inspection = CameraReceiptInspection.from_dict(data["inspection"])
        _same(inspection.receipt_sha256, data["inspection_sha256"])
    else:
        _require(data["inspection_sha256"] is None)
    for key, value in _derive(binding, notebook, inspection, reference).items():
        _same(data[key], value)
    return data


@dataclass(frozen=True, slots=True)
class ReceivedCameraAssessment:
    payload: bytes
    _prerequisites: PhysicalCameraPrerequisites = field(repr=False, compare=False)

    def __post_init__(self):
        _validate(self.payload, self._prerequisites)

    @property
    def sha256(self) -> str:
        return _sha(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _validate(self.payload, self._prerequisites)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        value = {
            "schema": SUMMARY_SCHEMA,
            "assessment_sha256": self.sha256,
            **{
                key: data[key]
                for key in (
                    "binding",
                    "notebook_sha256",
                    "inspection_sha256",
                    "status",
                    "coverage",
                    "row_checks",
                    "thickness",
                    "flatness_acceptance",
                    "missing_requirements",
                    "residuals",
                )
            },
            "notebook_original_bound": data["notebook_reference"] is not None,
            **FLAGS,
        }
        _require(len(_canonical(value)) <= MAX_SUMMARY_BYTES)
        return value


def assess_received_camera_receipt(
    prerequisites: PhysicalCameraPrerequisites,
    notebook: PhysicalIntakeNotebook,
    *,
    binding: dict[str, Any],
    inspection: CameraReceiptInspection | None = None,
    notebook_reference: EvidenceReference | None = None,
) -> ReceivedCameraAssessment:
    """Assess supplied original records, without reading any referenced file."""
    _require(
        type(prerequisites) is PhysicalCameraPrerequisites
        and type(notebook) is PhysicalIntakeNotebook
    )
    _require(inspection is None or type(inspection) is CameraReceiptInspection)
    _require(
        notebook_reference is None or type(notebook_reference) is EvidenceReference
    )
    binding = json.loads(_canonical(binding))
    _binding(binding)
    verified = PhysicalIntakeNotebook.from_payload(
        notebook.payload, prerequisites=prerequisites, expected_sha256=notebook.sha256
    )
    ref_document = None if notebook_reference is None else notebook_reference.to_dict()
    reference = _reference(ref_document, verified)
    data = {
        "schema": SCHEMA,
        "binding": binding,
        "notebook": verified.to_dict(),
        "notebook_sha256": verified.sha256,
        "notebook_reference": ref_document,
        "inspection": None if inspection is None else inspection.to_dict(),
        "inspection_sha256": None if inspection is None else inspection.receipt_sha256,
        **_derive(binding, verified, inspection, reference),
        "residuals": RESIDUALS,
        "meaning": MEANING,
        **FLAGS,
    }
    return ReceivedCameraAssessment(_canonical(data), prerequisites)


def verify_received_camera_assessment(
    value: Any,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    expected_binding: dict[str, Any],
    expected_notebook_sha256: str,
    expected_inspection_sha256: str | None,
    expected_notebook_reference: EvidenceReference | None,
    expected_assessment_sha256: str,
) -> ReceivedCameraAssessment:
    _require(type(value) in {bytes, ReceivedCameraAssessment})
    result = ReceivedCameraAssessment(
        value if type(value) is bytes else value.payload, prerequisites
    )
    data = result.to_dict()
    _require(
        result.sha256 == expected_assessment_sha256, "RECEIVED_ASSESSMENT_HASH_MISMATCH"
    )
    _same(data["binding"], expected_binding)
    _same(data["notebook_sha256"], expected_notebook_sha256)
    _same(data["inspection_sha256"], expected_inspection_sha256)
    _require(
        expected_notebook_reference is None
        or type(expected_notebook_reference) is EvidenceReference
    )
    _same(
        data["notebook_reference"],
        (
            None
            if expected_notebook_reference is None
            else expected_notebook_reference.to_dict()
        ),
    )
    return result
