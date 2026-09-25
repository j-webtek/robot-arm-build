"""Exact source-stage successor subjects, not native or actuator authority.

The service collects the originals; these codecs validate their relationships
and derive the stage-relative verdict. Operator statements and attachment byte
integrity do not prove their contents. Review is procedural, not authentication.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from pathlib import Path
import re
from typing import Any

from .physical_onboarding import _parse_evidence_reference
from .physical_source_stage_evidence import WorkspaceSourceReceipt
from rocell.providers.windows.native_camera_protocol import canonical, digest

RECEIPT_SCHEMA = "rocell.workspace_source_qualification_receipt.v1"
ASSESSMENT_SCHEMA = "rocell.workspace_source_qualification_assessment.v1"
REVIEW_SCHEMA = "rocell.workspace_source_qualification_review.v1"
MAX_RECEIPT_BYTES = 512 * 1024
MAX_ASSESSMENT_BYTES = MAX_REVIEW_BYTES = 64 * 1024
MAX_QUALIFICATIONS = 8
LABELS = {
    "isolation_original": "workspace-source-isolation-original-v1",
    "receipt": "workspace-source-qualification-receipt-v1",
    "assessment": "workspace-source-qualification-assessment-v1",
    "review": "workspace-source-qualification-review-v1",
}
FLAGS = {
    "physical_authority": False,
    "hardware_qualified": False,
    "native_release_allowed": False,
    "device_io_performed": False,
    "canonical_stage_pass": False,
}
RESIDUALS = [
    "CURRENT_ACTUATOR_ISOLATION_REQUIRED_FOR_EFFECTFUL_ADMISSION",
    "RECEIVED_DEVICE_IDENTITY_RECHECK_REQUIRED_UNDER_LEASE",
    "NATIVE_RUNTIME_AND_DIRECTORY_OWNERSHIP_RELEASE_REQUIRED",
    "STATIC_INSTALLATION_AND_CALIBRATION_NOT_QUALIFIED",
    "ARM_POWER_MOTION_AND_CONTACT_AUTHORITY_NOT_GRANTED",
]
CHECK_IDS = (
    "SOFTWARE_SOURCE_CHECKS",
    "ACTUATOR_ISOLATION_RECORDED",
    "SOFTWARE_OWNERSHIP_COVERAGE",
)
MISSING_IDS = (
    "SOFTWARE_PREREQUISITES_NOT_READY",
    "DISCONNECTED_ACTUATOR_OBSERVATION_REQUIRED",
    "SOFTWARE_OWNERSHIP_QUALIFICATION_REQUIRED",
)
_BINDING = {
    "qualification_id",
    "source_sha256",
    "cell_id",
    "session_id",
    "header_sha256",
    "origin_launch_id",
    "collection_launch_id",
    "operator_id",
    "prerequisites_sha256",
    "predecessor_source",
    "predecessor_qualification",
    "store_directory",
}
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ACTOR = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


class SourceQualificationError(ValueError):
    def __init__(self, code: str = "SOURCE_QUALIFICATION_INVALID") -> None:
        self.code = code
        super().__init__(code)


def _require(value: bool, code: str = "SOURCE_QUALIFICATION_INVALID") -> None:
    if not value:
        raise SourceQualificationError(code)


def _exact(value: Any, keys: set[str]) -> dict[str, Any]:
    _require(type(value) is dict and set(value) == keys)
    return value


def _sha(value: Any) -> None:
    _require(
        type(value) is str and _SHA.fullmatch(value) is not None and value != "0" * 64
    )


def _actor(value: Any) -> None:
    _require(type(value) is str and _ACTOR.fullmatch(value) is not None)


def _load(payload: bytes, maximum: int) -> dict[str, Any]:
    _require(type(payload) is bytes and 0 < len(payload) <= maximum)

    def pairs(items):
        result = {}
        for key, value in items:
            _require(key not in result)
            result[key] = value
        return result

    def bad(value):
        raise SourceQualificationError()

    try:
        data = json.loads(payload, object_pairs_hook=pairs, parse_constant=bad)
        _require(type(data) is dict and canonical(data) == payload)
        stack, nodes = [(data, 0)], 0
        while stack:
            value, depth = stack.pop()
            nodes += 1
            _require(nodes <= 32768 and depth <= 16)
            if type(value) is dict:
                stack.extend((item, depth + 1) for item in value.values())
            elif type(value) is list:
                stack.extend((item, depth + 1) for item in value)
            elif type(value) is float:
                _require(math.isfinite(value))
        return data
    except (TypeError, ValueError, UnicodeError, RecursionError) as error:
        raise SourceQualificationError() from error


def _binding(value: Any) -> dict[str, Any]:
    data = _exact(value, _BINDING)
    for key in ("source_sha256", "header_sha256", "prerequisites_sha256"):
        _sha(data[key])
    for key, pattern in (
        ("qualification_id", r"sourcequal-[0-9a-f]{32}"),
        ("cell_id", r"wizard-physical-camera-[0-9a-f]{16}"),
        ("session_id", r"physical-camera-[0-9a-f]{32}"),
        ("origin_launch_id", r"wizard-[0-9a-f]{32}"),
        ("collection_launch_id", r"wizard-[0-9a-f]{32}"),
    ):
        _require(
            type(data[key]) is str and re.fullmatch(pattern, data[key]) is not None
        )
    _actor(data["operator_id"])
    for key in ("predecessor_source", "predecessor_qualification"):
        if key == "predecessor_qualification" and data[key] is None:
            continue
        for sha in _exact(data[key], {"receipt", "assessment", "review"}).values():
            _sha(sha)
    directory = data["store_directory"]
    _require(type(directory) is str and len(directory) <= 4096)
    path = Path(directory)
    _require(
        path.is_absolute()
        and ".." not in path.parts
        and not directory.startswith(("\\\\", "//"))
    )
    return data


def ownership_directory(binding: dict[str, Any]) -> Path:
    _binding(binding)
    return Path(binding["store_directory"]) / (
        "source-ownership-" + binding["qualification_id"][11:]
    )


def _common(data: dict[str, Any], schema: str, keys: set[str]) -> dict[str, Any]:
    _exact(data, {"schema", "binding", "residuals", *FLAGS, *keys})
    _require(data["schema"] == schema and data["residuals"] == RESIDUALS)
    _require(all(data[key] is False for key in FLAGS))
    return _binding(data["binding"])


def _receipt(payload: bytes) -> dict[str, Any]:
    from .physical_ownership_qualification import (
        verify_physical_ownership_qualification,
    )

    data = _load(payload, MAX_RECEIPT_BYTES)
    binding = _common(
        data, RECEIPT_SCHEMA, {"software_receipt", "ownership_report", "isolation"}
    )
    software = WorkspaceSourceReceipt(canonical(data["software_receipt"])).to_dict()
    expected = {
        "source_sha256": binding["source_sha256"],
        "session_id": binding["session_id"],
        "origin_launch_id": binding["origin_launch_id"],
        "collection_launch_id": binding["collection_launch_id"],
        "header_sha256": binding["header_sha256"],
        "prerequisites_sha256": binding["prerequisites_sha256"],
        "operator_id": binding["operator_id"],
    }
    _require(software["binding"] == expected, "SOURCE_QUALIFICATION_SOFTWARE_BINDING")
    report = canonical(data["ownership_report"])
    verify_physical_ownership_qualification(
        report,
        expected_source_sha256=binding["source_sha256"],
        expected_directory=ownership_directory(binding),
        expected_report_sha256=digest(report),
    )
    isolation = _exact(
        data["isolation"],
        {"status", "statement", "original_reference", "basename", "recorded_at_ns"},
    )
    _require(isolation["status"] in {"UNKNOWN", "OBSERVED_DISCONNECTED"})
    statement = isolation["statement"]
    _require(
        type(statement) is str
        and len(statement.encode("utf-8")) <= 512
        and statement == statement.strip()
        and all(ord(char) >= 32 and not 127 <= ord(char) <= 159 for char in statement)
    )
    _require(
        type(isolation["recorded_at_ns"]) is int
        and 0 < isolation["recorded_at_ns"] < 2**63
    )
    reference = isolation["original_reference"]
    if reference is None:
        _require(isolation["status"] == "UNKNOWN" and isolation["basename"] is None)
    else:
        ref = _parse_evidence_reference(reference)
        _require(
            ref.stage.value == "workspace_sources"
            and 0 < ref.payload_bytes <= 2 * 1024 * 1024
        )
        name = isolation["basename"]
        _require(
            type(name) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,94}", name) is not None
        )
    if isolation["status"] == "OBSERVED_DISCONNECTED":
        _require(reference is not None and len(statement.strip()) >= 12)
    return data


@dataclass(frozen=True)
class SourceQualificationReceipt:
    payload: bytes

    def __post_init__(self) -> None:
        _receipt(self.payload)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _receipt(self.payload)


def build_source_qualification_receipt(
    *,
    binding: dict[str, Any],
    software_receipt: WorkspaceSourceReceipt,
    ownership_report: Any,
    isolation: dict[str, Any],
) -> SourceQualificationReceipt:
    return SourceQualificationReceipt(
        canonical(
            {
                "schema": RECEIPT_SCHEMA,
                "binding": binding,
                "software_receipt": software_receipt.to_dict(),
                "ownership_report": ownership_report.to_dict(),
                "isolation": isolation,
                "residuals": RESIDUALS,
                **FLAGS,
            }
        )
    )


def _assessment_document(receipt: SourceQualificationReceipt) -> dict[str, Any]:
    from .physical_ownership_qualification import PhysicalOwnershipQualification

    data = receipt.to_dict()
    summary = PhysicalOwnershipQualification(
        canonical(data["ownership_report"])
    ).safe_summary()
    checks = [
        {"check_id": name, "passed": passed}
        for name, passed in zip(
            CHECK_IDS,
            (
                all(
                    row["passed"] for row in data["software_receipt"]["software_checks"]
                ),
                data["isolation"]["status"] == "OBSERVED_DISCONNECTED",
                summary["status"] == "SOFTWARE_OWNERSHIP_COVERED",
            ),
        )
    ]
    missing = [name for name, row in zip(MISSING_IDS, checks) if not row["passed"]]
    return {
        "schema": ASSESSMENT_SCHEMA,
        "binding": data["binding"],
        "receipt_sha256": receipt.sha256,
        "checks": checks,
        "verdict": "BLOCKED" if missing else "PASS",
        "missing_requirements": missing,
        "residuals": RESIDUALS,
        **FLAGS,
    }


@dataclass(frozen=True)
class SourceQualificationAssessment:
    payload: bytes

    def __post_init__(self) -> None:
        data = _load(self.payload, MAX_ASSESSMENT_BYTES)
        _common(
            data,
            ASSESSMENT_SCHEMA,
            {"receipt_sha256", "checks", "verdict", "missing_requirements"},
        )
        _sha(data["receipt_sha256"])
        _require(type(data["checks"]) is list and len(data["checks"]) == len(CHECK_IDS))
        for row, name in zip(data["checks"], CHECK_IDS):
            _exact(row, {"check_id", "passed"})
            _require(row["check_id"] == name and type(row["passed"]) is bool)
        missing = [
            name for name, row in zip(MISSING_IDS, data["checks"]) if not row["passed"]
        ]
        _require(
            data["missing_requirements"] == missing
            and data["verdict"] == ("BLOCKED" if missing else "PASS")
        )

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_ASSESSMENT_BYTES)


def assess_source_qualification(
    receipt: SourceQualificationReceipt,
) -> SourceQualificationAssessment:
    _require(type(receipt) is SourceQualificationReceipt)
    return SourceQualificationAssessment(canonical(_assessment_document(receipt)))


def verify_source_qualification_assessment(
    payload: bytes, *, receipt: SourceQualificationReceipt, expected_sha256: str
) -> SourceQualificationAssessment:
    result = SourceQualificationAssessment(payload)
    _require(
        result.sha256 == expected_sha256
        and result.payload == assess_source_qualification(receipt).payload,
        "SOURCE_QUALIFICATION_ASSESSMENT_MISMATCH",
    )
    return result


@dataclass(frozen=True)
class SourceQualificationReview:
    payload: bytes

    def __post_init__(self) -> None:
        data = _load(self.payload, MAX_REVIEW_BYTES)
        binding = _common(
            data,
            REVIEW_SCHEMA,
            {
                "receipt_sha256",
                "assessment_sha256",
                "verdict",
                "reviewer_id",
                "review_launch_id",
                "reviewed_at_ns",
            },
        )
        _sha(data["receipt_sha256"])
        _sha(data["assessment_sha256"])
        _actor(data["reviewer_id"])
        _require(data["reviewer_id"].casefold() != binding["operator_id"].casefold())
        _require(data["verdict"] in {"PASS", "BLOCKED"})
        _require(
            type(data["review_launch_id"]) is str
            and re.fullmatch(r"wizard-[0-9a-f]{32}", data["review_launch_id"])
            is not None
        )
        _require(
            type(data["reviewed_at_ns"]) is int and 0 < data["reviewed_at_ns"] < 2**63
        )

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_REVIEW_BYTES)


def review_source_qualification(
    receipt: SourceQualificationReceipt,
    assessment: SourceQualificationAssessment,
    *,
    reviewer_id: str,
    review_launch_id: str,
    reviewed_at_ns: int,
) -> SourceQualificationReview:
    verified = verify_source_qualification_assessment(
        assessment.payload, receipt=receipt, expected_sha256=assessment.sha256
    )
    return SourceQualificationReview(
        canonical(
            {
                "schema": REVIEW_SCHEMA,
                "binding": receipt.to_dict()["binding"],
                "receipt_sha256": receipt.sha256,
                "assessment_sha256": verified.sha256,
                "verdict": verified.to_dict()["verdict"],
                "reviewer_id": reviewer_id,
                "review_launch_id": review_launch_id,
                "reviewed_at_ns": reviewed_at_ns,
                "residuals": RESIDUALS,
                **FLAGS,
            }
        )
    )


def verify_source_qualification_review(
    payload: bytes,
    *,
    receipt: SourceQualificationReceipt,
    assessment: SourceQualificationAssessment,
    expected_sha256: str,
) -> SourceQualificationReview:
    result = SourceQualificationReview(payload)
    data = result.to_dict()
    expected = review_source_qualification(
        receipt,
        assessment,
        reviewer_id=data["reviewer_id"],
        review_launch_id=data["review_launch_id"],
        reviewed_at_ns=data["reviewed_at_ns"],
    )
    _require(
        result.sha256 == expected_sha256 and result.payload == expected.payload,
        "SOURCE_QUALIFICATION_REVIEW_MISMATCH",
    )
    return result
