"""Pure stage-3 original subjects and exact procedural review.

Original-store owners authenticate current-cycle package labels, raw bytes,
committed predecessor reviews and entry events. This module never invents that
authority from reference hashes. It reuses the received-camera foundation and
does not grant installed, native, device or motion authority.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import hashlib
import json
import re
from typing import Any

from . import physical_received_camera as foundation
from .physical_camera_prerequisites import PhysicalCameraPrerequisites
from .physical_intake_notebook import PhysicalIntakeNotebook, MAX_NOTEBOOK_BYTES
from .physical_onboarding import (
    EvidenceReference,
    PhysicalOnboardingStage,
    _parse_evidence_reference,
)
from .physical_onboarding_receipts import CameraReceiptInspection

SUBMISSION_SCHEMA = "rocell.received_camera_submission.v1"
ASSESSMENT_SCHEMA = "rocell.received_camera_submission_assessment.v1"
REVIEW_SCHEMA = "rocell.received_camera_submission_review.v1"
NOTEBOOK_LABEL = "received-camera-notebook-v1"
ORIGINAL_LABEL = "received-camera-original-v1"
SUBMISSION_LABEL = "received-camera-submission-v1"
ASSESSMENT_LABEL = "received-camera-assessment-v1"
REVIEW_LABEL = "received-camera-review-v1"
MAX_SUBMISSION_BYTES = 128 * 1024
MAX_ASSESSMENT_BYTES = 160 * 1024
MAX_REVIEW_BYTES = 32 * 1024
MAX_SUMMARY_BYTES = 24 * 1024
MAX_COLLECTIONS = 4
MAX_ATTACHMENTS = 16
MAX_ORIGINAL_BYTES = 2 * 1024 * 1024
MAX_SELECTED_BYTES = 4 * 1024 * 1024
MAX_STAGE_REFERENCES = MAX_COLLECTIONS * (MAX_ATTACHMENTS + 4)
MAX_STAGE_BYTES = MAX_COLLECTIONS * (
    MAX_SELECTED_BYTES
    + MAX_NOTEBOOK_BYTES
    + MAX_SUBMISSION_BYTES
    + MAX_ASSESSMENT_BYTES
    + MAX_REVIEW_BYTES
)
RECORD_IDS = foundation.RECORD_IDS
FLAGS = {
    **foundation.FLAGS,
    "installation_qualified": False,
    "native_runtime_released": False,
    "measurement_truth_verified": False,
    "authenticated_operator_identity": False,
}
_MEDIA = {
    "txt": "text/plain",
    "json": "application/json",
    "png": "image/png",
    "jpg": "image/jpeg",
    "jpeg": "image/jpeg",
    "pdf": "application/pdf",
}
MEANING = (
    "Exact camera-receipt originals and procedural review only. A PASS verdict "
    "is eligible for the separate original stage owner to commit, not a stage "
    "mutation or installed qualification. Raw bytes and current-cycle package "
    "labels require leased original readback. Flatness acceptance, mounting, "
    "optics, USB identity and native release remain separate."
)
_BASE_FIELDS = {"schema", "binding", "sequence", "meaning", *FLAGS}


class ReceivedCameraSubmissionError(ValueError):
    def __init__(self, code: str = "RECEIVED_CAMERA_SUBMISSION_INVALID"):
        self.code = code
        super().__init__(code)


def _require(value: bool, code: str = "RECEIVED_CAMERA_SUBMISSION_INVALID") -> None:
    if not value:
        raise ReceivedCameraSubmissionError(code)


def _canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def _hash(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _same(left: Any, right: Any) -> None:
    _require(_canonical(left) == _canonical(right), "RECEIVED_CAMERA_SUBJECT_MISMATCH")


def _exact(value: Any, keys: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == keys)
    return value


def _digest(value: Any) -> None:
    _require(
        type(value) is str
        and re.fullmatch(r"[0-9a-f]{64}", value) is not None
        and value != "0" * 64
    )


def _time(value: Any) -> int:
    _require(type(value) is int and 0 < value < 2**63)
    return value


def _load(payload: bytes, maximum: int) -> dict[str, Any]:
    _require(
        type(payload) is bytes and 0 < len(payload) <= maximum,
        "RECEIVED_CAMERA_BYTE_LIMIT",
    )

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result)
            result[key] = value
        return result

    def bad(value):
        raise ReceivedCameraSubmissionError()

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
            _require(nodes <= 16384 and depth <= 16)
            if type(value) is dict:
                stack.extend((item, depth + 1) for item in value.values())
            elif type(value) is list:
                stack.extend((item, depth + 1) for item in value)
            elif type(value) is int:
                _require(-(2**63) < value < 2**63)
        return data
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as error:
        raise ReceivedCameraSubmissionError() from error


def _base(data: dict[str, Any], schema: str, extra: set[str]) -> None:
    _exact(data, _BASE_FIELDS | extra)
    _require(data["schema"] == schema and data["meaning"] == MEANING)
    _require(all(data[key] is False for key in FLAGS))
    foundation._binding(data["binding"])
    _require(type(data["sequence"]) is int and 1 <= data["sequence"] <= MAX_COLLECTIONS)


def _reference(value: Any) -> EvidenceReference:
    ref = _parse_evidence_reference(value)
    _require(
        ref.stage is PhysicalOnboardingStage.CAMERA_RECEIPT,
        "CAMERA_STAGE_ORIGINAL_REQUIRED",
    )
    return ref


@dataclass(frozen=True, slots=True)
class ReceivedCameraAttachment:
    reference: EvidenceReference
    basename: str
    media_type: str

    def __post_init__(self):
        _require(type(self.reference) is EvidenceReference)
        ref = _reference(self.reference.to_dict())
        _require(
            ref.payload_bytes <= MAX_ORIGINAL_BYTES,
            "RECEIVED_CAMERA_ORIGINAL_BYTE_LIMIT",
        )
        name = self.basename
        _require(
            type(name) is str
            and len(name) <= 128
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9 _.()-]*\.[A-Za-z]+", name)
            is not None
            and not name.endswith((" ", "."))
            and ".." not in name,
            "RECEIVED_CAMERA_ATTACHMENT_NAME",
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
            }
        )
        _require(
            type(self.media_type) is str
            and _MEDIA.get(extension.lower()) == self.media_type,
            "RECEIVED_CAMERA_ATTACHMENT_MEDIA",
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "reference": self.reference.to_dict(),
            "basename": self.basename,
            "media_type": self.media_type,
        }


@dataclass(frozen=True, slots=True)
class ReceivedCameraRowLink:
    record_id: str
    evidence_id: str | None

    def __post_init__(self):
        _require(type(self.record_id) is str and self.record_id in RECORD_IDS)
        _require(
            self.evidence_id is None
            or (
                type(self.evidence_id) is str
                and re.fullmatch(r"evidence-[0-9a-f]{64}", self.evidence_id) is not None
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {"record_id": self.record_id, "evidence_id": self.evidence_id}


def _objects(data: dict[str, Any], prerequisites: PhysicalCameraPrerequisites):
    _require(type(prerequisites) is PhysicalCameraPrerequisites)
    book = PhysicalIntakeNotebook.from_payload(
        _canonical(data["notebook"]),
        prerequisites=prerequisites,
        expected_sha256=data["notebook_sha256"],
    )
    ref = _reference(data["notebook_reference"])
    inspection = (
        None
        if data["inspection"] is None
        else CameraReceiptInspection.from_dict(data["inspection"])
    )
    _same(
        data["inspection_sha256"],
        None if inspection is None else inspection.receipt_sha256,
    )
    assessed = foundation.assess_received_camera_receipt(
        prerequisites,
        book,
        binding=data["binding"],
        notebook_reference=ref,
        inspection=inspection,
    )
    return book, ref, inspection, assessed


def _submission(
    payload: bytes, prerequisites: PhysicalCameraPrerequisites
) -> dict[str, Any]:
    data = _load(payload, MAX_SUBMISSION_BYTES)
    _base(
        data,
        SUBMISSION_SCHEMA,
        {
            "predecessor",
            "submitted_at_ns",
            "notebook",
            "notebook_sha256",
            "notebook_reference",
            "inspection",
            "inspection_sha256",
            "attachments",
            "row_links",
            "coverage",
            "draft_origin_notebook_sha256",
            "carried_forward_record_ids",
        },
    )
    predecessor = data["predecessor"]
    if data["sequence"] == 1:
        _require(predecessor is None and data["draft_origin_notebook_sha256"] is None)
    else:
        for value in _exact(
            predecessor, {"submission", "assessment", "review"}
        ).values():
            _digest(value)
    if data["draft_origin_notebook_sha256"] is not None:
        _digest(data["draft_origin_notebook_sha256"])
    carried = data["carried_forward_record_ids"]
    _require(
        type(carried) is list
        and carried == [key for key in RECORD_IDS if key in carried]
    )
    if data["draft_origin_notebook_sha256"] is None:
        _require(carried == [])
    submitted = _time(data["submitted_at_ns"])
    book, ref, inspection, _ = _objects(data, prerequisites)
    _same(data["coverage"], book.to_dict()["coverage"])
    _require(
        type(data["attachments"]) is list
        and len(data["attachments"]) <= MAX_ATTACHMENTS
    )
    attachments = []
    for row in data["attachments"]:
        _exact(row, {"reference", "basename", "media_type"})
        attachments.append(
            ReceivedCameraAttachment(
                _reference(row["reference"]), row["basename"], row["media_type"]
            )
        )
    selected = {item.reference.evidence_id: item for item in attachments}
    _require(
        len(selected) == len(attachments)
        and list(selected) == sorted(selected)
        and sum(item.reference.payload_bytes for item in attachments)
        <= MAX_SELECTED_BYTES
        and ref.evidence_id not in selected,
        "RECEIVED_CAMERA_SELECTED_INVENTORY",
    )
    _require(type(data["row_links"]) is list and len(data["row_links"]) == 16)
    for row, original in zip(data["row_links"], book.to_dict()["rows"]):
        _exact(row, {"record_id", "evidence_id"})
        link = ReceivedCameraRowLink(**row)
        _require(link.record_id == original["record_id"])
        _require(link.evidence_id is None or link.evidence_id in selected)
        observation = original["observation"]
        if observation is not None:
            _require(
                observation["recorded_at_ns"] <= submitted,
                "RECEIVED_CAMERA_OBSERVATION_TIME",
            )
            if observation["status"] == "OBSERVED":
                _require(link.evidence_id is not None, "OBSERVED_ROW_ORIGINAL_REQUIRED")
        if link.record_id in carried:
            _require(observation is not None)
    if inspection is not None:
        _require(inspection.observed_at_ns <= submitted)
        available = {
            **{key: item.reference.to_dict() for key, item in selected.items()},
            ref.evidence_id: ref.to_dict(),
        }
        for item in inspection.binding.evidence:
            _require(item.evidence_id in available)
            _same(item.to_dict(), available[item.evidence_id])
        _require(ref.evidence_id in inspection.binding.evidence_ids)
        _require(
            inspection.purchase_record_evidence_id in selected,
            "PURCHASE_ORIGINAL_REQUIRED",
        )
        _require(
            all(
                key in selected
                and selected[key].media_type in {"image/png", "image/jpeg"}
                for key in inspection.inspection_image_evidence_ids
            ),
            "INSPECTION_IMAGE_ORIGINAL_REQUIRED",
        )
    return data


def _summary(value: dict[str, Any]) -> dict[str, Any]:
    _require(
        len(_canonical(value)) <= MAX_SUMMARY_BYTES, "RECEIVED_CAMERA_SUMMARY_LIMIT"
    )
    return value


@dataclass(frozen=True, slots=True)
class ReceivedCameraSubmission:
    payload: bytes
    prerequisites: PhysicalCameraPrerequisites = field(repr=False, compare=False)

    def __post_init__(self):
        _submission(self.payload, self.prerequisites)

    @property
    def sha256(self) -> str:
        return _hash(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _submission(self.payload, self.prerequisites)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        return _summary(
            {
                "schema": "rocell.received_camera_submission_summary.v1",
                "submission_sha256": self.sha256,
                "status": "SUBMISSION_COLLECTED",
                **{
                    key: data[key]
                    for key in (
                        "binding",
                        "sequence",
                        "predecessor",
                        "coverage",
                        "notebook_sha256",
                        "inspection_sha256",
                        "draft_origin_notebook_sha256",
                        "carried_forward_record_ids",
                    )
                },
                "attachment_count": len(data["attachments"]),
                "attachment_bytes": sum(
                    row["reference"]["payload_bytes"] for row in data["attachments"]
                ),
                "linked_row_count": sum(
                    row["evidence_id"] is not None for row in data["row_links"]
                ),
                **FLAGS,
            }
        )


def _assessment_document(submission: ReceivedCameraSubmission) -> dict[str, Any]:
    data = submission.to_dict()
    _, _, _, assessed = _objects(data, submission.prerequisites)
    return {
        "schema": ASSESSMENT_SCHEMA,
        "binding": data["binding"],
        "sequence": data["sequence"],
        "submission_sha256": submission.sha256,
        "foundation": assessed.to_dict(),
        "foundation_sha256": assessed.sha256,
        "verdict": (
            "PASS" if assessed.to_dict()["status"] == "RECEIPT_COMPLETE" else "BLOCKED"
        ),
        "missing_requirements": assessed.to_dict()["missing_requirements"],
        "meaning": MEANING,
        **FLAGS,
    }


@dataclass(frozen=True, slots=True)
class ReceivedCameraSubmissionAssessment:
    payload: bytes
    prerequisites: PhysicalCameraPrerequisites = field(repr=False, compare=False)

    def __post_init__(self):
        data = _load(self.payload, MAX_ASSESSMENT_BYTES)
        _base(
            data,
            ASSESSMENT_SCHEMA,
            {
                "submission_sha256",
                "foundation",
                "foundation_sha256",
                "verdict",
                "missing_requirements",
            },
        )
        _digest(data["submission_sha256"])
        assessed = foundation.ReceivedCameraAssessment(
            _canonical(data["foundation"]), self.prerequisites
        )
        _same(assessed.sha256, data["foundation_sha256"])
        result = assessed.to_dict()
        _same(data["binding"], result["binding"])
        _same(data["missing_requirements"], result["missing_requirements"])
        _require(
            data["verdict"]
            == ("PASS" if result["status"] == "RECEIPT_COMPLETE" else "BLOCKED")
        )

    @property
    def sha256(self) -> str:
        return _hash(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_ASSESSMENT_BYTES)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        return _summary(
            {
                "schema": "rocell.received_camera_submission_assessment_summary.v1",
                "assessment_sha256": self.sha256,
                "status": "ASSESSED",
                **{
                    key: data[key]
                    for key in (
                        "binding",
                        "sequence",
                        "submission_sha256",
                        "foundation_sha256",
                        "verdict",
                        "missing_requirements",
                    )
                },
                "foundation": foundation.ReceivedCameraAssessment(
                    _canonical(data["foundation"]), self.prerequisites
                ).safe_summary(),
                **FLAGS,
            }
        )


@dataclass(frozen=True, slots=True)
class ReceivedCameraSubmissionReview:
    payload: bytes
    prerequisites: PhysicalCameraPrerequisites = field(repr=False, compare=False)

    def __post_init__(self):
        _require(type(self.prerequisites) is PhysicalCameraPrerequisites)
        data = _load(self.payload, MAX_REVIEW_BYTES)
        _base(
            data,
            REVIEW_SCHEMA,
            {
                "submission_sha256",
                "assessment_sha256",
                "decision",
                "verdict",
                "reviewer_id",
                "review_launch_id",
                "reviewed_at_ns",
                "distinct_operator_labels",
            },
        )
        _digest(data["submission_sha256"])
        _digest(data["assessment_sha256"])
        _require(data["decision"] in {"ACKNOWLEDGE_EXACT", "REJECT"})
        _require(data["verdict"] in {"PASS", "BLOCKED"})
        if data["decision"] == "REJECT":
            _require(data["verdict"] == "BLOCKED")
        _require(
            type(data["reviewer_id"]) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}", data["reviewer_id"])
            is not None
        )
        _require(
            data["reviewer_id"].casefold() != data["binding"]["operator_id"].casefold()
            and data["distinct_operator_labels"] is True
        )
        _require(
            type(data["review_launch_id"]) is str
            and re.fullmatch(r"wizard-[0-9a-f]{32}", data["review_launch_id"])
            is not None
        )
        _time(data["reviewed_at_ns"])

    @property
    def sha256(self) -> str:
        return _hash(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_REVIEW_BYTES)

    def safe_summary(self) -> dict[str, Any]:
        data = self.to_dict()
        return _summary(
            {
                **data,
                "schema": "rocell.received_camera_submission_review_summary.v1",
                "review_sha256": self.sha256,
                "status": "REVIEW_RECORDED",
            }
        )


def _payload(value: Any, kind: type) -> bytes:
    _require(type(value) in {bytes, kind})
    return value if type(value) is bytes else value.payload


def assess_received_camera_submission(
    submission: ReceivedCameraSubmission,
) -> ReceivedCameraSubmissionAssessment:
    _require(type(submission) is ReceivedCameraSubmission)
    return ReceivedCameraSubmissionAssessment(
        _canonical(_assessment_document(submission)), submission.prerequisites
    )


def verify_received_camera_submission_assessment(
    value: Any, *, submission: ReceivedCameraSubmission, expected_assessment_sha256: str
) -> ReceivedCameraSubmissionAssessment:
    result = ReceivedCameraSubmissionAssessment(
        _payload(value, ReceivedCameraSubmissionAssessment), submission.prerequisites
    )
    _require(
        result.sha256 == expected_assessment_sha256
        and result.payload == assess_received_camera_submission(submission).payload,
        "RECEIVED_CAMERA_ASSESSMENT_MISMATCH",
    )
    return result


def review_received_camera_submission(
    submission: ReceivedCameraSubmission,
    assessment: ReceivedCameraSubmissionAssessment,
    *,
    decision: str,
    reviewer_id: str,
    review_launch_id: str,
    reviewed_at_ns: int,
) -> ReceivedCameraSubmissionReview:
    checked = verify_received_camera_submission_assessment(
        assessment, submission=submission, expected_assessment_sha256=assessment.sha256
    )
    data = submission.to_dict()
    _require(_time(reviewed_at_ns) >= data["submitted_at_ns"])
    return ReceivedCameraSubmissionReview(
        _canonical(
            {
                "schema": REVIEW_SCHEMA,
                "binding": data["binding"],
                "sequence": data["sequence"],
                "submission_sha256": submission.sha256,
                "assessment_sha256": checked.sha256,
                "decision": decision,
                "verdict": (
                    "BLOCKED" if decision == "REJECT" else checked.to_dict()["verdict"]
                ),
                "reviewer_id": reviewer_id,
                "review_launch_id": review_launch_id,
                "reviewed_at_ns": reviewed_at_ns,
                "distinct_operator_labels": True,
                "meaning": MEANING,
                **FLAGS,
            }
        ),
        submission.prerequisites,
    )


def verify_received_camera_submission_review(
    value: Any,
    *,
    submission: ReceivedCameraSubmission,
    assessment: ReceivedCameraSubmissionAssessment,
    expected_review_sha256: str,
) -> ReceivedCameraSubmissionReview:
    result = ReceivedCameraSubmissionReview(
        _payload(value, ReceivedCameraSubmissionReview), submission.prerequisites
    )
    data = result.to_dict()
    expected = review_received_camera_submission(
        submission,
        assessment,
        **{
            key: data[key]
            for key in ("decision", "reviewer_id", "review_launch_id", "reviewed_at_ns")
        },
    )
    _require(
        result.sha256 == expected_review_sha256 and result.payload == expected.payload,
        "RECEIVED_CAMERA_REVIEW_MISMATCH",
    )
    return result


def _previous(predecessor: Any):
    if predecessor is None:
        return None
    _require(type(predecessor) is tuple and len(predecessor) == 3)
    submission, assessment, review = predecessor
    _require(
        type(submission) is ReceivedCameraSubmission
        and type(assessment) is ReceivedCameraSubmissionAssessment
        and type(review) is ReceivedCameraSubmissionReview
    )
    verify_received_camera_submission_review(
        review,
        submission=submission,
        assessment=assessment,
        expected_review_sha256=review.sha256,
    )
    _require(
        review.to_dict()["verdict"] == "BLOCKED",
        "RECEIVED_CAMERA_PREDECESSOR_NOT_BLOCKED",
    )
    return submission, assessment, review


def _carried(book: dict[str, Any], origin: str | None, previous: Any) -> list[str]:
    if origin is None:
        return []
    _require(previous is not None)
    old = previous[0].to_dict()
    _require(origin == old["notebook_sha256"], "RECEIVED_CAMERA_DRAFT_ORIGIN_MISMATCH")
    return [
        row["record_id"]
        for row, prior in zip(book["rows"], old["notebook"]["rows"])
        if row["observation"] is not None
        and _canonical(row["observation"]) == _canonical(prior["observation"])
    ]


def _check_predecessor(data: dict[str, Any], predecessor: Any) -> None:
    previous = _previous(predecessor)
    if previous is None:
        _require(
            data["sequence"] == 1
            and data["predecessor"] is None
            and data["draft_origin_notebook_sha256"] is None,
            "RECEIVED_CAMERA_PREDECESSOR_REQUIRED",
        )
    else:
        old = previous[0].to_dict()
        _same(
            data["predecessor"],
            dict(
                zip(
                    ("submission", "assessment", "review"), (v.sha256 for v in previous)
                )
            ),
        )
        _require(
            data["sequence"] == old["sequence"] + 1
            and data["binding"]["receipt_id"] != old["binding"]["receipt_id"]
            and data["submitted_at_ns"] > previous[2].to_dict()["reviewed_at_ns"]
        )
        original_keys = set(data["binding"]) - {
            "receipt_id",
            "collection_launch_id",
            "operator_id",
        }
        _same(
            {key: data["binding"][key] for key in original_keys},
            {key: old["binding"][key] for key in original_keys},
        )
        old_ids = {row["reference"]["evidence_id"] for row in old["attachments"]} | {
            old["notebook_reference"]["evidence_id"]
        }
        new_ids = {row["reference"]["evidence_id"] for row in data["attachments"]} | {
            data["notebook_reference"]["evidence_id"]
        }
        _require(not old_ids.intersection(new_ids), "RECEIVED_CAMERA_ORIGINAL_REUSE")
    _same(
        data["carried_forward_record_ids"],
        _carried(data["notebook"], data["draft_origin_notebook_sha256"], previous),
    )


def _inventory(value: tuple[EvidenceReference, ...]) -> dict[str, EvidenceReference]:
    # Full original audited inventory may include unchanged source/static roles.
    # Only the new camera-stage slice gets these explicit additional budgets.
    _require(type(value) is tuple and len(value) <= 256)
    rows = []
    for item in value:
        _require(type(item) is EvidenceReference)
        rows.append(_parse_evidence_reference(item.to_dict()))
    ids = [row.evidence_id for row in rows]
    _require(len(set(ids)) == len(ids) and ids == sorted(ids))
    camera = [
        row for row in rows if row.stage is PhysicalOnboardingStage.CAMERA_RECEIPT
    ]
    _require(
        len(camera) <= MAX_STAGE_REFERENCES
        and sum(row.payload_bytes for row in camera) <= MAX_STAGE_BYTES,
        "RECEIVED_CAMERA_STAGE_INVENTORY_LIMIT",
    )
    return {row.evidence_id: row for row in rows}


def verify_received_camera_submission(
    value: Any,
    *,
    prerequisites: PhysicalCameraPrerequisites,
    expected_binding: dict[str, Any],
    evidence_inventory: tuple[EvidenceReference, ...],
    expected_submission_sha256: str,
    predecessor=None,
) -> ReceivedCameraSubmission:
    result = ReceivedCameraSubmission(
        _payload(value, ReceivedCameraSubmission), prerequisites
    )
    _require(
        result.sha256 == expected_submission_sha256,
        "RECEIVED_CAMERA_SUBMISSION_HASH_MISMATCH",
    )
    data = result.to_dict()
    _same(data["binding"], expected_binding)
    inventory = _inventory(evidence_inventory)
    for value in [
        data["notebook_reference"],
        *(row["reference"] for row in data["attachments"]),
    ]:
        ref = _reference(value)
        _require(
            ref.evidence_id in inventory, "RECEIVED_CAMERA_ORIGINAL_NOT_IN_INVENTORY"
        )
        _same(ref.to_dict(), inventory[ref.evidence_id].to_dict())
    _check_predecessor(data, predecessor)
    return result


def build_received_camera_submission(
    prerequisites: PhysicalCameraPrerequisites,
    notebook: PhysicalIntakeNotebook,
    *,
    binding: dict[str, Any],
    notebook_reference: EvidenceReference,
    inspection: CameraReceiptInspection | None = None,
    attachments: tuple[ReceivedCameraAttachment, ...] = (),
    row_links: tuple[ReceivedCameraRowLink, ...],
    submitted_at_ns: int,
    evidence_inventory: tuple[EvidenceReference, ...],
    predecessor=None,
    draft_origin_notebook_sha256: str | None = None,
) -> ReceivedCameraSubmission:
    _require(
        type(prerequisites) is PhysicalCameraPrerequisites
        and type(notebook) is PhysicalIntakeNotebook
    )
    _require(type(notebook_reference) is EvidenceReference)
    _require(inspection is None or type(inspection) is CameraReceiptInspection)
    _require(
        type(attachments) is tuple
        and all(type(item) is ReceivedCameraAttachment for item in attachments)
    )
    _require(
        type(row_links) is tuple
        and all(type(item) is ReceivedCameraRowLink for item in row_links)
    )
    book = PhysicalIntakeNotebook.from_payload(
        notebook.payload, prerequisites=prerequisites, expected_sha256=notebook.sha256
    )
    previous = _previous(predecessor)
    data = {
        "schema": SUBMISSION_SCHEMA,
        "binding": binding,
        "sequence": 1 if previous is None else previous[0].to_dict()["sequence"] + 1,
        "predecessor": (
            None
            if previous is None
            else dict(
                zip(
                    ("submission", "assessment", "review"), (v.sha256 for v in previous)
                )
            )
        ),
        "submitted_at_ns": submitted_at_ns,
        "notebook": book.to_dict(),
        "notebook_sha256": book.sha256,
        "notebook_reference": notebook_reference.to_dict(),
        "inspection": None if inspection is None else inspection.to_dict(),
        "inspection_sha256": None if inspection is None else inspection.receipt_sha256,
        "attachments": [item.to_dict() for item in attachments],
        "row_links": [item.to_dict() for item in row_links],
        "coverage": book.to_dict()["coverage"],
        "draft_origin_notebook_sha256": draft_origin_notebook_sha256,
        "carried_forward_record_ids": _carried(
            book.to_dict(), draft_origin_notebook_sha256, previous
        ),
        "meaning": MEANING,
        **FLAGS,
    }
    result = ReceivedCameraSubmission(_canonical(data), prerequisites)
    return verify_received_camera_submission(
        result,
        prerequisites=prerequisites,
        expected_binding=binding,
        evidence_inventory=evidence_inventory,
        expected_submission_sha256=result.sha256,
        predecessor=predecessor,
    )
