"""Pure original-byte intake subjects, not measurement truth or stage acceptance.

The service owns guarded reads and M1 retention. Contextual verification must
use the original audited inventory and prerequisites; parsing bytes alone does
not authenticate either. The reader separately verifies original source review,
collection-start journal citations and the predecessor's completed review.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from .commissioning_camera_persistence import physical_camera_source_binding
from .physical_camera_prerequisites import (
    PhysicalCameraPrerequisites,
    _OBSERVATION_FIELDS,
)
from . import physical_intake_notebook as notebook_codec
from .physical_intake_notebook import PhysicalIntakeNotebook
from .physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
    _parse_evidence_reference,
)
from .physical_onboarding_stage_catalog import _EXPECTED_INTAKE_BY_STAGE

SUBMISSION_SCHEMA = "rocell.physical_passive_intake_submission.v1"
ASSESSMENT_SCHEMA = "rocell.physical_passive_intake_assessment.v1"
REVIEW_SCHEMA = "rocell.physical_passive_intake_review.v1"
ORIGINAL_LABEL = "physical-intake-original-v1"
SUBMISSION_LABEL = "physical-intake-submission-v1"
ASSESSMENT_LABEL = "physical-intake-assessment-v1"
REVIEW_LABEL = "physical-intake-review-v1"
MAX_RECORD_BYTES = 128 * 1024
MAX_INVENTORY_BYTES = 4 * 1024 * 1024
MAX_ATTACHMENTS = 16
MAX_COLLECTIONS = 8
RECORD_IDS = _EXPECTED_INTAKE_BY_STAGE[PhysicalOnboardingStage.CAMERA_RECEIPT]
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")
_COLLECTION = re.compile(r"intake-[0-9a-f]{32}\Z")
_MEDIA = {
    "txt": "text/plain",
    "json": "application/json",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "pdf": "application/pdf",
}
_FLAGS = {
    key: False
    for key in (
        "physical_authority",
        "hardware_qualified",
        "canonical_stage_pass",
        "device_io_performed",
        "measurement_truth_verified",
        "authenticated_operator_identity",
    )
}
_STAGES = {"stage": "workspace_sources", "observation_owner_stage": "camera_receipt"}
_BINDING_KEYS = {
    "source_sha256",
    "source_binding_sha256",
    "session_id",
    "cell_id",
    "header_sha256",
    "origin_launch_id",
    "submission_launch_id",
    "prerequisites_sha256",
    "notebook_sha256",
}
SUBMISSION_MEANING = "Original attachment references and explicit operator observations, not authenticated measurements. Source-stage supplementary material is intended for later camera-receipt review; no stage, hazard, epoch, device or physical qualification is accepted. INT-005 acceptance remains deferred."
ASSESSMENT_MEANING = "Completeness and reference structure only. UNKNOWN observations remain unknown; byte integrity does not prove measurement truth or physical readiness."
REVIEW_MEANING = "Exact-subject procedural review only. Different labels do not authenticate independent people. Acknowledgement or rejection neither rewrites the original source verdict nor accepts a physical stage."


class PhysicalIntakeSubmissionError(ValueError):
    def __init__(self, code: str = "INVALID_INTAKE_SUBMISSION") -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str = "INVALID_INTAKE_SUBMISSION") -> None:
    if not condition:
        raise PhysicalIntakeSubmissionError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _hash(value: Any) -> str:
    return hashlib.sha256(_canonical(value)).hexdigest()


def _exact(value: Any, keys: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == keys)
    return value


def _same(left: Any, right: Any) -> None:
    _require(_canonical(left) == _canonical(right), "INTAKE_SUBJECT_MISMATCH")


def _sha(value: Any) -> str:
    _require(type(value) is str and _SHA.fullmatch(value) is not None)
    return value


def _identifier(value: Any, *, actor: bool = False) -> str:
    _require(
        type(value) is str and (_ACTOR if actor else _ID).fullmatch(value) is not None
    )
    return value


def _time(value: Any) -> int:
    _require(type(value) is int and 0 < value < 2**63)
    return value


def _reference(value: EvidenceReference) -> EvidenceReference:
    _require(type(value) is EvidenceReference, "EXACT_ORIGINAL_REFERENCE_REQUIRED")
    restored = _parse_evidence_reference(value.to_dict())
    _same(restored.to_dict(), value.to_dict())
    _require(
        restored.stage is PhysicalOnboardingStage.WORKSPACE_SOURCES,
        "SOURCE_STAGE_REFERENCE_REQUIRED",
    )
    _require(restored.payload_bytes <= MAX_INVENTORY_BYTES, "INTAKE_BYTE_LIMIT")
    return restored


def _inventory(value: tuple[EvidenceReference, ...]) -> dict[str, EvidenceReference]:
    _require(type(value) is tuple and len(value) <= 32, "INTAKE_INVENTORY_LIMIT")
    rows = tuple(_reference(row) for row in value)
    _require(len({row.evidence_id for row in rows}) == len(rows))
    _require(tuple(sorted(rows, key=lambda row: row.evidence_id)) == rows)
    _require(
        sum(row.payload_bytes for row in rows) <= MAX_INVENTORY_BYTES,
        "INTAKE_INVENTORY_LIMIT",
    )
    return {row.evidence_id: row for row in rows}


@dataclass(frozen=True, slots=True)
class IntakeAttachment:
    reference: EvidenceReference
    basename: str
    media_type: str

    def __post_init__(self) -> None:
        _reference(self.reference)
        name = self.basename
        _require(
            type(name) is str
            and len(name) <= 128
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.()-]*\.[A-Za-z]+", name)
            is not None,
            "UNSAFE_ATTACHMENT_NAME",
        )
        _require(
            not name.endswith((" ", ".")) and ".." not in name, "UNSAFE_ATTACHMENT_NAME"
        )
        stem, extension = name.rsplit(".", 1)
        _require(
            stem.upper().split(".")[0]
            not in {
                "CON",
                "PRN",
                "AUX",
                "NUL",
                *(f"COM{i}" for i in range(1, 10)),
                *(f"LPT{i}" for i in range(1, 10)),
            },
            "UNSAFE_ATTACHMENT_NAME",
        )
        _require(
            type(self.media_type) is str
            and _MEDIA.get(extension.lower()) == self.media_type,
            "ATTACHMENT_MEDIA_REFUSED",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference.to_dict(),
            "basename": self.basename,
            "media_type": self.media_type,
        }


@dataclass(frozen=True, slots=True)
class IntakeRowAttachment:
    record_id: str
    evidence_id: str

    def __post_init__(self) -> None:
        _require(
            type(self.record_id) is str and self.record_id in RECORD_IDS,
            "UNKNOWN_INTAKE_ROW",
        )
        _require(
            type(self.evidence_id) is str
            and re.fullmatch(r"evidence-[0-9a-f]{64}", self.evidence_id) is not None
        )

    def to_dict(self) -> dict[str, str]:
        return {"record_id": self.record_id, "evidence_id": self.evidence_id}


def _binding(value: Any) -> dict[str, Any]:
    bound = _exact(value, _BINDING_KEYS)
    for key, item in bound.items():
        _sha(item) if key.endswith("sha256") else _identifier(item)
    _require(
        re.fullmatch(r"physical-camera-[0-9a-f]{32}", bound["session_id"]) is not None
        and re.fullmatch(r"wizard-physical-camera-[0-9a-f]{16}", bound["cell_id"])
        is not None
    )
    _same(
        bound["source_binding_sha256"],
        physical_camera_source_binding(bound["source_sha256"]),
    )
    return bound


def _notebook_structure(value: Any) -> dict[str, Any]:
    """Reuse observation validation; exact questions require contextual verify."""
    book = _exact(
        value,
        {
            "schema",
            "binding",
            "revision",
            "previous_sha256",
            "rows",
            "coverage",
            "meaning",
            *notebook_codec._FALSE,
        },
    )
    _require(len(_canonical(book)) <= notebook_codec.MAX_NOTEBOOK_BYTES)
    _same(book["schema"], notebook_codec.SCHEMA)
    _same(book["meaning"], notebook_codec._MEANING)
    _require(all(book[key] is False for key in notebook_codec._FALSE))
    bound = _exact(
        book["binding"],
        {
            "source_sha256",
            "session_id",
            "origin_launch_id",
            "launch_session_id",
            "prerequisites_sha256",
        },
    )
    for key, item in bound.items():
        _sha(item) if key.endswith("sha256") else _identifier(item)
    _require(
        type(book["revision"]) is int
        and 16 <= book["revision"] <= notebook_codec.MAX_REVISIONS
    )
    _require(_sha(book["previous_sha256"]) != "0" * 64)
    rows = book["rows"]
    _require(type(rows) is list and len(rows) == 16)
    for row, record_id in zip(rows, RECORD_IDS, strict=True):
        _exact(
            row,
            {
                "record_id",
                "assembly",
                "measurement",
                "unit",
                "candidate_or_requirement",
                "template_phase",
                "template_status",
                "template_notes",
                "required_observation_fields",
                "observation",
                "acceptance",
            },
        )
        _same(row["record_id"], record_id)
        for key in (
            "assembly",
            "measurement",
            "unit",
            "candidate_or_requirement",
            "template_phase",
            "template_status",
            "template_notes",
        ):
            _require(
                type(row[key]) is str
                and len(row[key]) <= 4096
                and all(ord(char) >= 32 for char in row[key])
            )
        _same(row["required_observation_fields"], list(_OBSERVATION_FIELDS))
        _same(
            row["acceptance"],
            {
                "status": (
                    "DEFERRED_LIMIT" if record_id == "INT-005" else "NOT_ASSESSED"
                ),
                "owner_stage": (
                    "noncontact_acceptance"
                    if record_id == "INT-005"
                    else "camera_receipt"
                ),
                "prerequisites": (
                    ["TARGET_ACCURACY_BUDGET_CLOSED"] if record_id == "INT-005" else []
                ),
                "measurement_required": True,
            },
        )
        _require(row["observation"] is not None, "ALL_INTAKE_ROWS_REQUIRED")
        notebook_codec._observation(row["observation"], row)
    _same(book["coverage"], notebook_codec._coverage(rows))
    return book


def _coverage(
    book: dict[str, Any], attachments: list[dict[str, Any]], links: list[dict[str, Any]]
) -> dict[str, int]:
    return {
        "total": 16,
        "observed": book["coverage"]["observed"],
        "unknown": book["coverage"]["unknown"],
        "attached_rows": len(links),
        "attachment_count": len(attachments),
        "attachment_bytes": sum(
            row["reference"]["payload_bytes"] for row in attachments
        ),
    }


def _common(data: dict[str, Any], schema: str, meaning: str) -> None:
    _same(data["schema"], schema)
    _same(data["meaning"], meaning)
    _require(all(data[key] is False for key in _FLAGS))
    _binding(data["binding"])
    _require(
        type(data["collection_id"]) is str
        and _COLLECTION.fullmatch(data["collection_id"]) is not None
    )


def _submission(data: Any) -> dict[str, Any]:
    _exact(
        data,
        {
            "schema",
            "binding",
            "collection_id",
            "sequence",
            "predecessor_submission_sha256",
            "operator_id",
            "submitted_at_ns",
            "notebook",
            "attachments",
            "row_attachments",
            "coverage",
            "meaning",
            *_STAGES,
            *_FLAGS,
        },
    )
    _common(data, SUBMISSION_SCHEMA, SUBMISSION_MEANING)
    _same({key: data[key] for key in _STAGES}, _STAGES)
    _identifier(data["operator_id"], actor=True)
    timestamp = _time(data["submitted_at_ns"])
    _require(type(data["sequence"]) is int and 1 <= data["sequence"] <= MAX_COLLECTIONS)
    if data["sequence"] == 1:
        _require(data["predecessor_submission_sha256"] is None)
    else:
        _sha(data["predecessor_submission_sha256"])
    book = _notebook_structure(data["notebook"])
    bound = data["binding"]
    _same(
        book["binding"],
        {
            "source_sha256": bound["source_sha256"],
            "session_id": bound["session_id"],
            "origin_launch_id": bound["origin_launch_id"],
            "launch_session_id": bound["submission_launch_id"],
            "prerequisites_sha256": bound["prerequisites_sha256"],
        },
    )
    _same(_hash(book), bound["notebook_sha256"])
    _require(
        all(row["observation"]["recorded_at_ns"] <= timestamp for row in book["rows"])
    )
    attachments = data["attachments"]
    _require(type(attachments) is list and len(attachments) <= MAX_ATTACHMENTS)
    parsed = []
    for row in attachments:
        _exact(row, {"reference", "basename", "media_type"})
        parsed.append(
            IntakeAttachment(
                _parse_evidence_reference(row["reference"]),
                row["basename"],
                row["media_type"],
            )
        )
    _same(attachments, [row.to_dict() for row in parsed])
    ids = [row.reference.evidence_id for row in parsed]
    _require(ids == sorted(set(ids)))
    _require(
        sum(row.reference.payload_bytes for row in parsed) <= MAX_INVENTORY_BYTES,
        "INTAKE_BYTE_LIMIT",
    )
    links = data["row_attachments"]
    _require(type(links) is list and len(links) <= 16)
    for row in links:
        _exact(row, {"record_id", "evidence_id"})
        IntakeRowAttachment(row["record_id"], row["evidence_id"])
        _require(row["evidence_id"] in ids, "ATTACHMENT_REFERENCE_MISSING")
    row_ids = [row["record_id"] for row in links]
    _require(row_ids == sorted(set(row_ids), key=RECORD_IDS.index))
    _require(
        set(row["evidence_id"] for row in links) == set(ids),
        "UNUSED_ATTACHMENT_REFUSED",
    )
    _require(
        all(
            row["record_id"] in row_ids
            for row in book["rows"]
            if row["observation"]["status"] == "OBSERVED"
        ),
        "OBSERVED_ATTACHMENT_REQUIRED",
    )
    _same(data["coverage"], _coverage(book, attachments, links))
    return data


def _assessment_document(submission: PhysicalIntakeSubmission) -> dict[str, Any]:
    data = submission.to_dict()
    unknown = [
        row["record_id"]
        for row in data["notebook"]["rows"]
        if row["observation"]["status"] == "UNKNOWN"
    ]
    return {
        "schema": ASSESSMENT_SCHEMA,
        "binding": data["binding"],
        "collection_id": data["collection_id"],
        "submission_sha256": submission.sha256,
        "status": "STRUCTURE_AND_REFERENCES_VALID",
        "observation_completeness": (
            "UNKNOWN_ROWS_REMAIN" if unknown else "ALL_ROWS_OBSERVED"
        ),
        "unknown_record_ids": unknown,
        "coverage": data["coverage"],
        "physical_readiness": False,
        **_FLAGS,
        "meaning": ASSESSMENT_MEANING,
    }


def _assessment(data: Any) -> dict[str, Any]:
    _exact(
        data,
        {
            "schema",
            "binding",
            "collection_id",
            "submission_sha256",
            "status",
            "observation_completeness",
            "unknown_record_ids",
            "coverage",
            "physical_readiness",
            "meaning",
            *_FLAGS,
        },
    )
    _common(data, ASSESSMENT_SCHEMA, ASSESSMENT_MEANING)
    _sha(data["submission_sha256"])
    _same(data["status"], "STRUCTURE_AND_REFERENCES_VALID")
    _require(data["physical_readiness"] is False)
    unknown = data["unknown_record_ids"]
    _require(
        type(unknown) is list
        and len(unknown) <= 16
        and all(type(v) is str and v in RECORD_IDS for v in unknown)
    )
    _require(unknown == sorted(set(unknown), key=RECORD_IDS.index))
    _same(
        data["observation_completeness"],
        "UNKNOWN_ROWS_REMAIN" if unknown else "ALL_ROWS_OBSERVED",
    )
    counts = _exact(
        data["coverage"],
        {
            "total",
            "observed",
            "unknown",
            "attached_rows",
            "attachment_count",
            "attachment_bytes",
        },
    )
    _require(all(type(v) is int and v >= 0 for v in counts.values()))
    _require(
        counts["total"] == 16
        and counts["unknown"] == len(unknown)
        and counts["observed"] == 16 - len(unknown)
        and counts["observed"] <= counts["attached_rows"] <= 16
        and counts["attachment_count"] <= counts["attached_rows"]
    )
    _require(
        counts["attachment_count"] <= counts["attachment_bytes"] <= MAX_INVENTORY_BYTES
        and (counts["attachment_bytes"] == 0) == (counts["attachment_count"] == 0)
        and (counts["attached_rows"] == 0) == (counts["attachment_count"] == 0)
    )
    return data


def _review(data: Any) -> dict[str, Any]:
    _exact(
        data,
        {
            "schema",
            "binding",
            "collection_id",
            "submission_sha256",
            "assessment_sha256",
            "reviewer_id",
            "review_launch_id",
            "reviewed_at_ns",
            "decision",
            "status",
            "distinct_operator_labels",
            "authenticated_independent_people",
            "meaning",
            *_FLAGS,
        },
    )
    _common(data, REVIEW_SCHEMA, REVIEW_MEANING)
    _sha(data["submission_sha256"])
    _sha(data["assessment_sha256"])
    _identifier(data["reviewer_id"], actor=True)
    _identifier(data["review_launch_id"])
    _time(data["reviewed_at_ns"])
    _require(
        type(data["decision"]) is str
        and data["decision"] in {"ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW", "REJECT"}
    )
    _same(
        data["status"],
        (
            "REJECTED"
            if data["decision"] == "REJECT"
            else "ACKNOWLEDGED_FOR_LATER_STAGE_REVIEW"
        ),
    )
    _require(
        data["distinct_operator_labels"] is True
        and data["authenticated_independent_people"] is False
    )
    return data


def _decode(payload: bytes, validator: Any) -> dict[str, Any]:
    _require(
        type(payload) is bytes and 0 < len(payload) <= MAX_RECORD_BYTES,
        "INTAKE_BYTE_LIMIT",
    )

    def pairs(rows: list[tuple[str, Any]]) -> dict[str, Any]:
        result: dict[str, Any] = {}
        for key, value in rows:
            _require(key not in result, "DUPLICATE_INTAKE_FIELD")
            result[key] = value
        return result

    try:
        value = json.loads(payload.decode("ascii"), object_pairs_hook=pairs)
        _require(_canonical(value) == payload, "NONCANONICAL_INTAKE_RECORD")
        return validator(value)
    except PhysicalIntakeSubmissionError:
        raise
    except (
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        RecursionError,
        OverflowError,
    ) as error:
        raise PhysicalIntakeSubmissionError() from error


@dataclass(frozen=True, slots=True)
class PhysicalIntakeSubmission:
    payload: bytes

    def __post_init__(self) -> None:
        _decode(self.payload, _submission)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return _decode(self.payload, _submission)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        links = {
            row["record_id"]: row["evidence_id"] for row in data["row_attachments"]
        }
        return {
            "schema": "rocell.physical_passive_intake_submission_summary.v1",
            "submission_sha256": self.sha256,
            **{
                key: data[key]
                for key in (
                    "binding",
                    "collection_id",
                    "sequence",
                    "predecessor_submission_sha256",
                    "operator_id",
                    "coverage",
                    "meaning",
                    *_FLAGS,
                    *_STAGES,
                )
            },
            "notebook_revision": data["notebook"]["revision"],
            "rows": [
                {
                    "record_id": row["record_id"],
                    "measurement": row["measurement"],
                    "unit": row["unit"],
                    "status": row["observation"]["status"],
                    "observed_value": row["observation"]["observed_value"],
                    "method": row["observation"]["method"],
                    "attachment_evidence_id": links.get(row["record_id"]),
                    "acceptance_status": row["acceptance"]["status"],
                    "acceptance_owner_stage": row["acceptance"]["owner_stage"],
                }
                for row in data["notebook"]["rows"]
            ],
            "attachments": [
                {
                    "evidence_id": row["reference"]["evidence_id"],
                    "basename": row["basename"],
                    "media_type": row["media_type"],
                    "payload_sha256": row["reference"]["payload_sha256"],
                    "payload_bytes": row["reference"]["payload_bytes"],
                }
                for row in data["attachments"]
            ],
        }


@dataclass(frozen=True, slots=True)
class PhysicalIntakeAssessment:
    payload: bytes

    def __post_init__(self) -> None:
        _decode(self.payload, _assessment)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return _decode(self.payload, _assessment)

    def safe_summary(self) -> dict[str, Any]:
        return {
            **self.to_dict(),
            "schema": "rocell.physical_passive_intake_assessment_summary.v1",
            "assessment_sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class PhysicalIntakeReview:
    payload: bytes

    def __post_init__(self) -> None:
        _decode(self.payload, _review)

    @property
    def sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return _decode(self.payload, _review)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        del data["reviewed_at_ns"]
        return {
            **data,
            "schema": "rocell.physical_passive_intake_review_summary.v1",
            "review_sha256": self.sha256,
        }


def _predecessor(
    subject: PhysicalIntakeSubmission, predecessor: PhysicalIntakeSubmission | None
) -> None:
    data = subject.to_dict()
    if predecessor is None:
        _require(
            data["sequence"] == 1 and data["predecessor_submission_sha256"] is None,
            "INTAKE_PREDECESSOR_REQUIRED",
        )
        return
    _require(
        type(predecessor) is PhysicalIntakeSubmission,
        "EXACT_INTAKE_PREDECESSOR_REQUIRED",
    )
    previous = predecessor.to_dict()
    _require(
        data["sequence"] == previous["sequence"] + 1
        and data["predecessor_submission_sha256"] == predecessor.sha256
        and data["collection_id"] != previous["collection_id"]
        and data["submitted_at_ns"] > previous["submitted_at_ns"],
        "INTAKE_PREDECESSOR_MISMATCH",
    )
    keys = _BINDING_KEYS - {"notebook_sha256", "submission_launch_id"}
    _same(
        {k: data["binding"][k] for k in keys}, {k: previous["binding"][k] for k in keys}
    )


def build_physical_intake_submission(
    prerequisites: PhysicalCameraPrerequisites,
    notebook: PhysicalIntakeNotebook,
    *,
    cell_id: str,
    header_sha256: str,
    collection_id: str,
    operator_id: str,
    submitted_at_ns: int,
    attachments: tuple[IntakeAttachment, ...],
    row_attachments: tuple[IntakeRowAttachment, ...],
    evidence_inventory: tuple[EvidenceReference, ...],
    predecessor: PhysicalIntakeSubmission | None = None,
) -> PhysicalIntakeSubmission:
    _require(
        type(prerequisites) is PhysicalCameraPrerequisites
        and type(notebook) is PhysicalIntakeNotebook,
        "EXACT_INTAKE_INPUTS_REQUIRED",
    )
    book = PhysicalIntakeNotebook.from_payload(
        notebook.payload, prerequisites=prerequisites, expected_sha256=notebook.sha256
    )
    _require(
        type(attachments) is tuple
        and len(attachments) <= 16
        and all(type(v) is IntakeAttachment for v in attachments)
    )
    _require(
        type(row_attachments) is tuple
        and len(row_attachments) <= 16
        and all(type(v) is IntakeRowAttachment for v in row_attachments)
    )
    _require(predecessor is None or type(predecessor) is PhysicalIntakeSubmission)
    bound = book.to_dict()["binding"]
    result = PhysicalIntakeSubmission(
        _canonical(
            {
                "schema": SUBMISSION_SCHEMA,
                "binding": {
                    "source_sha256": bound["source_sha256"],
                    "source_binding_sha256": physical_camera_source_binding(
                        bound["source_sha256"]
                    ),
                    "session_id": bound["session_id"],
                    "cell_id": cell_id,
                    "header_sha256": header_sha256,
                    "origin_launch_id": bound["origin_launch_id"],
                    "submission_launch_id": bound["launch_session_id"],
                    "prerequisites_sha256": prerequisites.evidence_sha256,
                    "notebook_sha256": book.sha256,
                },
                "collection_id": collection_id,
                "sequence": (
                    1 if predecessor is None else predecessor.to_dict()["sequence"] + 1
                ),
                "predecessor_submission_sha256": (
                    None if predecessor is None else predecessor.sha256
                ),
                "operator_id": operator_id,
                "submitted_at_ns": submitted_at_ns,
                "notebook": book.to_dict(),
                "attachments": [v.to_dict() for v in attachments],
                "row_attachments": [v.to_dict() for v in row_attachments],
                "coverage": _coverage(
                    book.to_dict(),
                    [v.to_dict() for v in attachments],
                    [v.to_dict() for v in row_attachments],
                ),
                **_STAGES,
                **_FLAGS,
                "meaning": SUBMISSION_MEANING,
            }
        )
    )
    return verify_physical_intake_submission(
        result.payload,
        prerequisites=prerequisites,
        evidence_inventory=evidence_inventory,
        expected_source_sha256=bound["source_sha256"],
        expected_session_id=bound["session_id"],
        expected_cell_id=cell_id,
        expected_origin_launch_id=bound["origin_launch_id"],
        expected_header_sha256=header_sha256,
        expected_submission_sha256=result.sha256,
        predecessor=predecessor,
    )


def verify_physical_intake_submission(
    payload: bytes,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    evidence_inventory: tuple[EvidenceReference, ...],
    expected_source_sha256: str,
    expected_session_id: str,
    expected_cell_id: str,
    expected_origin_launch_id: str,
    expected_header_sha256: str,
    expected_submission_sha256: str,
    predecessor: PhysicalIntakeSubmission | None = None,
) -> PhysicalIntakeSubmission:
    result = PhysicalIntakeSubmission(payload)
    _require(
        type(prerequisites) is PhysicalCameraPrerequisites,
        "EXACT_PREREQUISITES_REQUIRED",
    )
    original = PhysicalCameraPrerequisites(prerequisites.payload).to_dict()
    _same(result.sha256, _sha(expected_submission_sha256))
    data = result.to_dict()
    bound = data["binding"]
    _same(
        {
            k: bound[k]
            for k in (
                "source_sha256",
                "session_id",
                "cell_id",
                "origin_launch_id",
                "header_sha256",
                "prerequisites_sha256",
            )
        },
        {
            "source_sha256": _sha(expected_source_sha256),
            "session_id": _identifier(expected_session_id),
            "cell_id": _identifier(expected_cell_id),
            "origin_launch_id": _identifier(expected_origin_launch_id),
            "header_sha256": _sha(expected_header_sha256),
            "prerequisites_sha256": prerequisites.evidence_sha256,
        },
    )
    _same(
        original["binding"],
        {
            "source_sha256": expected_source_sha256,
            "session_id": expected_session_id,
            "launch_session_id": expected_origin_launch_id,
        },
    )
    PhysicalIntakeNotebook.from_payload(
        _canonical(data["notebook"]),
        prerequisites=prerequisites,
        expected_sha256=bound["notebook_sha256"],
    )
    inventory = _inventory(evidence_inventory)
    for row in data["attachments"]:
        reference = row["reference"]
        _require(
            reference["evidence_id"] in inventory,
            "ATTACHMENT_NOT_IN_ORIGINAL_INVENTORY",
        )
        _same(reference, inventory[reference["evidence_id"]].to_dict())
    _predecessor(result, predecessor)
    return result


def assess_physical_intake_submission(
    submission: PhysicalIntakeSubmission,
) -> PhysicalIntakeAssessment:
    _require(
        type(submission) is PhysicalIntakeSubmission, "EXACT_INTAKE_SUBMISSION_REQUIRED"
    )
    return PhysicalIntakeAssessment(_canonical(_assessment_document(submission)))


def verify_physical_intake_assessment(
    payload: bytes,
    *,
    submission: PhysicalIntakeSubmission,
    expected_assessment_sha256: str,
) -> PhysicalIntakeAssessment:
    result = PhysicalIntakeAssessment(payload)
    _same(result.sha256, _sha(expected_assessment_sha256))
    _same(result.to_dict(), assess_physical_intake_submission(submission).to_dict())
    return result


def review_physical_intake_submission(
    submission: PhysicalIntakeSubmission,
    assessment: PhysicalIntakeAssessment,
    *,
    reviewer_id: str,
    review_launch_id: str,
    reviewed_at_ns: int,
    decision: str,
) -> PhysicalIntakeReview:
    _require(
        type(submission) is PhysicalIntakeSubmission
        and type(assessment) is PhysicalIntakeAssessment
    )
    verify_physical_intake_assessment(
        assessment.payload,
        submission=submission,
        expected_assessment_sha256=assessment.sha256,
    )
    data = submission.to_dict()
    _require(
        _identifier(reviewer_id, actor=True).casefold()
        != data["operator_id"].casefold(),
        "DISTINCT_INTAKE_REVIEWER_REQUIRED",
    )
    _require(
        _time(reviewed_at_ns) >= data["submitted_at_ns"], "INTAKE_REVIEW_TIME_MISMATCH"
    )
    return PhysicalIntakeReview(
        _canonical(
            {
                "schema": REVIEW_SCHEMA,
                "binding": data["binding"],
                "collection_id": data["collection_id"],
                "submission_sha256": submission.sha256,
                "assessment_sha256": assessment.sha256,
                "reviewer_id": reviewer_id,
                "review_launch_id": review_launch_id,
                "reviewed_at_ns": reviewed_at_ns,
                "decision": decision,
                "status": (
                    "REJECTED"
                    if decision == "REJECT"
                    else "ACKNOWLEDGED_FOR_LATER_STAGE_REVIEW"
                ),
                "distinct_operator_labels": True,
                "authenticated_independent_people": False,
                **_FLAGS,
                "meaning": REVIEW_MEANING,
            }
        )
    )


def verify_physical_intake_review(
    payload: bytes,
    *,
    submission: PhysicalIntakeSubmission,
    assessment: PhysicalIntakeAssessment,
    expected_review_sha256: str,
) -> PhysicalIntakeReview:
    result = PhysicalIntakeReview(payload)
    _same(result.sha256, _sha(expected_review_sha256))
    data = result.to_dict()
    expected = review_physical_intake_submission(
        submission,
        assessment,
        reviewer_id=data["reviewer_id"],
        review_launch_id=data["review_launch_id"],
        reviewed_at_ns=data["reviewed_at_ns"],
        decision=data["decision"],
    )
    _same(data, expected.to_dict())
    return result
