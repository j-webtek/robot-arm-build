"""Strict, zero-authority validation for the physical hardware intake sheet.

The checked-in 55-row CSV is an immutable question set.  An operator works on
a copy and may change only the observation, method, evidence path, status, and
notes columns.  This module verifies that no required question was removed or
rewritten and hashes every referenced evidence file.  A complete assessment is
review-ready evidence; it is never a power, motion, calibration, or contact
permit.
"""

from __future__ import annotations

from collections import Counter
import csv
from dataclasses import dataclass
import hashlib
import io
import json
import os
from pathlib import Path
import re
from typing import Mapping


HARDWARE_INTAKE_SCHEMA = "rocell.physical_hardware_intake_assessment.v1"
DEFAULT_INTAKE_TEMPLATE = Path(
    "hardware/static_overhead_camera/hardware_intake_template.csv"
)
INTAKE_HEADER = (
    "record_id",
    "stage",
    "assembly",
    "measurement",
    "unit",
    "candidate_or_requirement",
    "observed_value",
    "instrument_or_method",
    "evidence_path",
    "status",
    "notes",
)
_LOCKED_COLUMNS = INTAKE_HEADER[:6]
_ALLOWED_STATUSES = frozenset(
    {
        "NOT_CAPTURED",
        "NOT_CREATED",
        "NOT_MEASURED",
        "NOT_RECORDED",
        "NOT_TESTED",
        "OPEN_LIMIT",
        "PASS",
        "HOLD",
        "NA",
    }
)
_RECORD_ID_RE = re.compile(r"^INT-(\d{3})$")
_SHA256_RE = re.compile(r"^[0-9a-f]{64}$")
_MAX_CSV_BYTES = 512 * 1024
_MAX_FIELD_CHARS = 4096
_EXPECTED_RECORD_COUNT = 55


class HardwareIntakeError(ValueError):
    """The intake sheet or referenced evidence failed strict validation."""


def _reject_symlink_chain(path: Path, label: str) -> None:
    cursor = Path(os.path.abspath(path))
    while True:
        if os.path.lexists(cursor) and cursor.is_symlink():
            raise HardwareIntakeError(f"{label} contains a symlink")
        if cursor.parent == cursor:
            return
        cursor = cursor.parent


def _safe_text(value: object, label: str, *, allow_empty: bool = True) -> str:
    if not isinstance(value, str):
        raise HardwareIntakeError(f"{label} must be text")
    if len(value) > _MAX_FIELD_CHARS:
        raise HardwareIntakeError(f"{label} exceeds {_MAX_FIELD_CHARS} characters")
    if any(ord(character) < 32 and character not in "\t" for character in value):
        raise HardwareIntakeError(f"{label} contains a control character")
    stripped = value.strip()
    if not allow_empty and not stripped:
        raise HardwareIntakeError(f"{label} must not be empty")
    return stripped


def _read_csv(path: Path) -> tuple[bytes, tuple[Mapping[str, str], ...]]:
    _reject_symlink_chain(path, "intake CSV")
    try:
        resolved = path.resolve(strict=True)
    except OSError as exc:
        raise HardwareIntakeError(f"intake CSV is unavailable: {path}") from exc
    if resolved.is_symlink() or not resolved.is_file():
        raise HardwareIntakeError(f"intake CSV must be a regular non-symlink: {resolved}")
    try:
        raw = resolved.read_bytes()
    except OSError as exc:
        raise HardwareIntakeError(f"could not read intake CSV: {resolved}") from exc
    if not raw or len(raw) > _MAX_CSV_BYTES:
        raise HardwareIntakeError(
            f"intake CSV size must be within 1..{_MAX_CSV_BYTES} bytes"
        )
    try:
        text = raw.decode("utf-8")
    except UnicodeError as exc:
        raise HardwareIntakeError("intake CSV must be strict UTF-8") from exc
    reader = csv.DictReader(io.StringIO(text, newline=""), strict=True)
    if tuple(reader.fieldnames or ()) != INTAKE_HEADER:
        raise HardwareIntakeError("intake CSV header or column order changed")
    rows: list[Mapping[str, str]] = []
    try:
        for index, row in enumerate(reader, start=2):
            if None in row:
                raise HardwareIntakeError(f"intake CSV row {index} has extra columns")
            parsed = {
                field: _safe_text(row.get(field), f"row {index} {field}")
                for field in INTAKE_HEADER
            }
            rows.append(parsed)
    except csv.Error as exc:
        raise HardwareIntakeError(f"intake CSV syntax is invalid: {exc}") from exc
    return raw, tuple(rows)


def _contained_evidence(workspace: Path, relative_text: str) -> Path:
    candidate = Path(relative_text)
    if candidate.is_absolute():
        raise HardwareIntakeError("evidence_path must be relative to the workspace")
    _reject_symlink_chain(workspace / candidate, "evidence_path")
    try:
        resolved = (workspace / candidate).resolve(strict=True)
        resolved.relative_to(workspace)
    except (OSError, ValueError) as exc:
        raise HardwareIntakeError(
            f"evidence_path is missing or outside the workspace: {relative_text}"
        ) from exc
    if resolved.is_symlink() or not resolved.is_file():
        raise HardwareIntakeError(
            f"evidence_path must name a regular non-symlink: {relative_text}"
        )
    return resolved


def _contained_input_file(workspace: Path, path: Path, label: str) -> Path:
    selected = path if path.is_absolute() else workspace / path
    _reject_symlink_chain(selected, label)
    try:
        resolved = selected.resolve(strict=True)
        resolved.relative_to(workspace)
    except (OSError, ValueError) as exc:
        raise HardwareIntakeError(
            f"{label} is missing or outside the workspace"
        ) from exc
    if not resolved.is_file():
        raise HardwareIntakeError(f"{label} must be a regular file")
    return resolved


@dataclass(frozen=True, slots=True)
class IntakeEvidenceBinding:
    record_id: str
    relative_path: str
    size_bytes: int
    sha256: str

    def __post_init__(self) -> None:
        if _RECORD_ID_RE.fullmatch(self.record_id) is None:
            raise HardwareIntakeError("evidence record_id is invalid")
        if not self.relative_path or Path(self.relative_path).is_absolute():
            raise HardwareIntakeError("evidence relative_path is invalid")
        if isinstance(self.size_bytes, bool) or self.size_bytes <= 0:
            raise HardwareIntakeError("evidence size_bytes must be positive")
        if _SHA256_RE.fullmatch(self.sha256) is None:
            raise HardwareIntakeError("evidence sha256 is invalid")

    def to_dict(self) -> dict[str, object]:
        return {
            "record_id": self.record_id,
            "relative_path": self.relative_path,
            "size_bytes": self.size_bytes,
            "sha256": self.sha256,
        }


@dataclass(frozen=True, slots=True)
class IntakeStageAssessment:
    """Review progress for one named section of the controlled intake sheet."""

    stage: str
    record_ids: tuple[str, ...]
    review_ready_record_ids: tuple[str, ...]
    incomplete_record_ids: tuple[str, ...]
    hold_record_ids: tuple[str, ...]
    ready_for_human_review: bool

    def to_dict(self) -> dict[str, object]:
        return {
            "stage": self.stage,
            "record_ids": list(self.record_ids),
            "review_ready_record_ids": list(self.review_ready_record_ids),
            "incomplete_record_ids": list(self.incomplete_record_ids),
            "hold_record_ids": list(self.hold_record_ids),
            "ready_for_human_review": self.ready_for_human_review,
        }


@dataclass(frozen=True, slots=True)
class HardwareIntakeAssessment:
    intake_path: str
    intake_sha256: str
    template_sha256: str
    record_count: int
    status_counts: tuple[tuple[str, int], ...]
    review_ready_record_ids: tuple[str, ...]
    incomplete_record_ids: tuple[str, ...]
    hold_record_ids: tuple[str, ...]
    evidence_bindings: tuple[IntakeEvidenceBinding, ...]
    stage_assessments: tuple[IntakeStageAssessment, ...]
    ready_for_human_review: bool

    def stage(self, name: str) -> IntakeStageAssessment:
        for assessment in self.stage_assessments:
            if assessment.stage == name:
                return assessment
        raise HardwareIntakeError(f"intake stage does not exist: {name}")

    @property
    def assessment_sha256(self) -> str:
        return hashlib.sha256(
            json.dumps(
                self.to_dict(include_hash=False),
                sort_keys=True,
                separators=(",", ":"),
                ensure_ascii=True,
                allow_nan=False,
            ).encode("utf-8")
        ).hexdigest()

    def to_dict(self, *, include_hash: bool = True) -> dict[str, object]:
        value: dict[str, object] = {
            "schema": HARDWARE_INTAKE_SCHEMA,
            "intake_path": self.intake_path,
            "intake_sha256": self.intake_sha256,
            "template_sha256": self.template_sha256,
            "record_count": self.record_count,
            "status_counts": dict(self.status_counts),
            "review_ready_record_ids": list(self.review_ready_record_ids),
            "incomplete_record_ids": list(self.incomplete_record_ids),
            "hold_record_ids": list(self.hold_record_ids),
            "evidence_bindings": [item.to_dict() for item in self.evidence_bindings],
            "stage_assessments": [
                item.to_dict() for item in self.stage_assessments
            ],
            "ready_for_human_review": self.ready_for_human_review,
            "authority": {
                "evidence_class": "OBSERVED_DIAGNOSTIC_PENDING_REVIEW",
                "hardware_accessed": False,
                "safe_to_power_robot_conferred": False,
                "motion_authorized": False,
                "contact_authorized": False,
                "physical_release_effect": "NONE",
            },
        }
        if include_hash:
            value["assessment_sha256"] = self.assessment_sha256
        return value


def assess_hardware_intake(
    workspace: Path,
    intake_path: Path,
    *,
    template_path: Path | None = None,
) -> HardwareIntakeAssessment:
    """Validate one completed copy against the immutable 55-row question set."""

    try:
        _reject_symlink_chain(workspace, "workspace")
        root = Path(workspace).resolve(strict=True)
    except OSError as exc:
        raise HardwareIntakeError("workspace is unavailable") from exc
    if root.is_symlink() or not root.is_dir():
        raise HardwareIntakeError("workspace must be a non-symlink directory")

    selected_template = (
        DEFAULT_INTAKE_TEMPLATE if template_path is None else Path(template_path)
    )
    resolved_template = _contained_input_file(root, selected_template, "intake template")
    resolved_intake = _contained_input_file(root, Path(intake_path), "intake copy")
    template_raw, template_rows = _read_csv(resolved_template)
    intake_raw, intake_rows = _read_csv(resolved_intake)
    if len(template_rows) != _EXPECTED_RECORD_COUNT:
        raise HardwareIntakeError(
            f"template must contain exactly {_EXPECTED_RECORD_COUNT} records"
        )
    if len(intake_rows) != len(template_rows):
        raise HardwareIntakeError("intake row count differs from the controlled template")

    expected_ids = tuple(f"INT-{index:03d}" for index in range(1, 56))
    observed_ids = tuple(row["record_id"] for row in intake_rows)
    if observed_ids != expected_ids:
        raise HardwareIntakeError("intake record IDs must be ordered INT-001 through INT-055")

    evidence: list[IntakeEvidenceBinding] = []
    ready: list[str] = []
    incomplete: list[str] = []
    holds: list[str] = []
    statuses: Counter[str] = Counter()
    stage_records: dict[str, list[tuple[str, str]]] = {}

    for template, observed in zip(template_rows, intake_rows, strict=True):
        record_id = observed["record_id"]
        for field in _LOCKED_COLUMNS:
            if observed[field] != template[field]:
                raise HardwareIntakeError(
                    f"{record_id} changed controlled question field {field!r}"
                )
        status = observed["status"].upper()
        if status not in _ALLOWED_STATUSES:
            raise HardwareIntakeError(f"{record_id} has unsupported status {status!r}")
        statuses[status] += 1
        stage_records.setdefault(observed["stage"], []).append((record_id, status))
        if status == "HOLD":
            holds.append(record_id)

        is_review_ready = status in {"PASS", "NA"}
        if is_review_ready:
            if not observed["observed_value"]:
                raise HardwareIntakeError(
                    f"{record_id} {status} requires observed_value"
                )
            if not observed["instrument_or_method"]:
                raise HardwareIntakeError(
                    f"{record_id} {status} requires instrument_or_method"
                )
            if not observed["evidence_path"]:
                raise HardwareIntakeError(
                    f"{record_id} {status} requires evidence_path"
                )
            evidence_path = _contained_evidence(root, observed["evidence_path"])
            try:
                payload = evidence_path.read_bytes()
            except OSError as exc:
                raise HardwareIntakeError(
                    f"could not read evidence for {record_id}"
                ) from exc
            if not payload:
                raise HardwareIntakeError(f"evidence for {record_id} is empty")
            evidence.append(
                IntakeEvidenceBinding(
                    record_id=record_id,
                    relative_path=evidence_path.relative_to(root).as_posix(),
                    size_bytes=len(payload),
                    sha256=hashlib.sha256(payload).hexdigest(),
                )
            )
            ready.append(record_id)
        else:
            incomplete.append(record_id)

    ready_for_review = (
        len(ready) == _EXPECTED_RECORD_COUNT and not incomplete and not holds
    )
    stage_assessments = tuple(
        IntakeStageAssessment(
            stage=stage,
            record_ids=tuple(record_id for record_id, _ in records),
            review_ready_record_ids=tuple(
                record_id
                for record_id, status in records
                if status in {"PASS", "NA"}
            ),
            incomplete_record_ids=tuple(
                record_id
                for record_id, status in records
                if status not in {"PASS", "NA"}
            ),
            hold_record_ids=tuple(
                record_id for record_id, status in records if status == "HOLD"
            ),
            ready_for_human_review=all(
                status in {"PASS", "NA"} for _, status in records
            ),
        )
        for stage, records in stage_records.items()
    )
    return HardwareIntakeAssessment(
        intake_path=resolved_intake.relative_to(root).as_posix(),
        intake_sha256=hashlib.sha256(intake_raw).hexdigest(),
        template_sha256=hashlib.sha256(template_raw).hexdigest(),
        record_count=len(intake_rows),
        status_counts=tuple(sorted(statuses.items())),
        review_ready_record_ids=tuple(ready),
        incomplete_record_ids=tuple(incomplete),
        hold_record_ids=tuple(holds),
        evidence_bindings=tuple(evidence),
        stage_assessments=stage_assessments,
        ready_for_human_review=ready_for_review,
    )


__all__ = [
    "DEFAULT_INTAKE_TEMPLATE",
    "HARDWARE_INTAKE_SCHEMA",
    "HardwareIntakeAssessment",
    "HardwareIntakeError",
    "IntakeEvidenceBinding",
    "IntakeStageAssessment",
    "assess_hardware_intake",
]
