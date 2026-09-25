"""Pure staged registration of an inspected development helper for metadata.

Different operator labels provide diagnostic role separation, not authenticated
human identities. The helper remains unqualified for activation/probe/capture.
No state method inspects files, constructs a provider or runs a process.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from threading import RLock
from typing import Any

from .wizard_camera_helper_inspection import verify_camera_helper_inspection

SCHEMA = "rocell.wizard_camera_helper_registration.v1"
MAX_REPORT_BYTES = 256 * 1024
_SHA256 = re.compile(r"[0-9a-f]{64}\Z")
_IDENTIFIER = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}\Z")
_BASELINE_HOLDS = frozenset(
    {
        "DEVELOPMENT_METADATA_ONLY_NOT_TRUSTED_RELEASE",
        "DISTINCT_OPERATOR_LABELS_NOT_AUTHENTICATED_IDENTITIES",
        "CAMERA_ACTIVATION_NOT_AUTHORIZED",
        "DRIVER_AND_PROCESS_CONTAINMENT_NOT_QUALIFIED",
        "RECEIVED_CAMERA_AND_ARM_NOT_QUALIFIED",
    }
)


class CameraHelperRegistrationError(ValueError):
    def __init__(self, code: str, message: str) -> None:
        self.code = code
        super().__init__(message)


def _require(condition: bool, code: str, message: str) -> None:
    if not condition:
        raise CameraHelperRegistrationError(code, message)


def _text(value: object, maximum: int = 128) -> str:
    _require(
        type(value) is str and bool(value) and len(value) <= maximum,
        "INVALID_INPUT",
        "Expected bounded nonempty text.",
    )
    assert isinstance(value, str)
    try:
        valid = value == value.strip() and len(value.encode("utf-8")) <= maximum
    except UnicodeError:
        valid = False
    _require(
        valid and not any(ord(c) < 32 or ord(c) == 127 for c in value),
        "INVALID_INPUT",
        "Text must be bounded UTF-8 without controls.",
    )
    return value


def _identifier(value: object) -> str:
    checked = _text(value)
    _require(
        _IDENTIFIER.fullmatch(checked) is not None,
        "INVALID_INPUT",
        "Session and operation IDs must be bounded identifiers.",
    )
    return checked


def _canonical(value: object) -> bytes:
    return json.dumps(
        value,
        sort_keys=True,
        ensure_ascii=False,
        separators=(",", ":"),
        allow_nan=False,
    ).encode("utf-8")


def _owned(value: object) -> dict[str, Any]:
    nodes = 0
    text_bytes = 0

    def copy(item: object, depth: int) -> Any:
        nonlocal nodes, text_bytes
        nodes += 1
        _require(
            depth <= 16 and nodes <= 8192,
            "REPORT_LIMIT",
            "Helper report structure exceeds its bound.",
        )
        if item is None or type(item) is bool:
            return item
        if type(item) is int:
            _require(
                -(1 << 63) <= item < (1 << 63),
                "INVALID_REPORT",
                "Helper report integer is invalid.",
            )
            return item
        if type(item) is str:
            _require(
                len(item) <= 4096,
                "REPORT_LIMIT",
                "Helper report text exceeds its bound.",
            )
            try:
                length = len(item.encode("utf-8"))
            except UnicodeError as exc:
                raise CameraHelperRegistrationError(
                    "INVALID_REPORT", "Helper report text is not UTF-8."
                ) from exc
            text_bytes += length
            _require(
                length <= 4096 and text_bytes <= MAX_REPORT_BYTES,
                "REPORT_LIMIT",
                "Helper report text exceeds its byte bound.",
            )
            return item
        if type(item) is dict:
            _require(
                len(item) <= 64
                and all(type(key) is str and len(key) <= 128 for key in item),
                "INVALID_REPORT",
                "Helper report fields are invalid.",
            )
            return {
                copy(key, depth + 1): copy(child, depth + 1)
                for key, child in item.items()
            }
        if type(item) is list:
            _require(
                len(item) <= 128,
                "REPORT_LIMIT",
                "Helper report array exceeds its bound.",
            )
            return [copy(child, depth + 1) for child in item]
        raise CameraHelperRegistrationError(
            "INVALID_REPORT", "Helper report requires plain JSON values."
        )

    try:
        result = copy(value, 0)
        _require(
            type(result) is dict and len(_canonical(result)) <= MAX_REPORT_BYTES,
            "REPORT_LIMIT",
            "Complete helper report exceeds its byte bound.",
        )
        return result
    except RuntimeError as exc:
        raise CameraHelperRegistrationError(
            "INVALID_REPORT", "Helper report changed while copied."
        ) from exc


@dataclass(frozen=True, slots=True)
class ReviewedCameraHelperRegistration:
    """Immutable metadata artifact; its fields do not authenticate its creator.

    A provider factory must independently verify this artifact and its complete
    inspection against the caller's mode/source and fixed catalog before use.
    """

    _payload_json: bytes
    _inspection_json: bytes

    def __post_init__(self) -> None:
        # Public construction does not confer trust, but the value itself must
        # actually be immutable and bounded. The factory still verifies every
        # semantic/catalog/source field independently before metadata use.
        for payload in (self._payload_json, self._inspection_json):
            _require(
                type(payload) is bytes and len(payload) <= MAX_REPORT_BYTES,
                "INVALID_ARTIFACT",
                "Registration requires bounded immutable canonical bytes.",
            )
            try:
                parsed = _owned(json.loads(payload))
                _require(
                    _canonical(parsed) == payload,
                    "INVALID_ARTIFACT",
                    "Registration bytes must use the exact canonical JSON encoding.",
                )
            except (ValueError, TypeError, UnicodeError) as exc:
                raise CameraHelperRegistrationError(
                    "INVALID_ARTIFACT", "Registration artifact bytes are invalid."
                ) from exc

    @property
    def payload(self) -> dict[str, Any]:
        return json.loads(self._payload_json)

    @property
    def inspection(self) -> dict[str, Any]:
        return json.loads(self._inspection_json)

    @property
    def registration_sha256(self) -> str:
        return hashlib.sha256(self._payload_json).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return {
            "payload": self.payload,
            "registration_sha256": self.registration_sha256,
        }


class WizardCameraHelperRegistration:
    def __init__(self, mode: str, session_id: str, source_sha256: str) -> None:
        _require(
            type(mode) is str and mode in {"rehearsal", "physical"},
            "INVALID_MODE",
            "Mode must be rehearsal or physical.",
        )
        self._mode = mode
        self._session = _identifier(session_id)
        self._source = _text(source_sha256)
        _require(
            _SHA256.fullmatch(self._source) is not None,
            "INVALID_INPUT",
            "Workspace source must be a lowercase SHA-256.",
        )
        self._lock = RLock()
        self._inspection: bytes | None = None
        self._operation: str | None = None
        self._operator: str | None = None
        self._review: bytes | None = None
        self._artifact: bytes | None = None
        self._reason: str | None = None

    def staged_copy(self) -> WizardCameraHelperRegistration:
        with self._lock:
            copied = WizardCameraHelperRegistration(
                self._mode, self._session, self._source
            )
            for field in (
                "_inspection",
                "_operation",
                "_operator",
                "_review",
                "_artifact",
                "_reason",
            ):
                setattr(copied, field, getattr(self, field))
            return copied

    def invalidate(self, reason: str) -> None:
        reason = _text(reason, 512)
        with self._lock:
            self._inspection = self._review = self._artifact = None
            self._operation = self._operator = None
            self._reason = reason

    def invalidate_review(self, reason: str) -> None:
        reason = _text(reason, 512)
        with self._lock:
            self._review = self._artifact = None
            self._reason = reason

    def ingest(
        self, inspection_report: dict[str, Any], *, operation_id: str, operator_id: str
    ) -> dict[str, Any]:
        with self._lock:
            self.invalidate("HELPER_INSPECTION_REPLACEMENT_NOT_VERIFIED")
            operation = _identifier(operation_id)
            operator = _text(operator_id)
            owned = _owned(inspection_report)
            expected_provenance = (
                "INCAPABLE_FIXTURE"
                if self._mode == "rehearsal"
                else "WORKSPACE_FILE_INSPECTION"
            )
            try:
                verified = verify_camera_helper_inspection(
                    owned,
                    expected_source_sha256=self._source,
                    expected_inspection_sha256=_text(owned.get("inspection_sha256")),
                    expected_provenance=expected_provenance,
                )
            except Exception as exc:
                # Preserve KeyboardInterrupt/SystemExit semantics; no raw file
                # path, provider detail or exception text becomes public here.
                raise CameraHelperRegistrationError(
                    "INSPECTION_INVALID",
                    "Helper inspection differs from its exact catalog/source/provenance contract.",
                ) from exc
            _require(
                _canonical(owned) == _canonical(verified)
                and verified["mode"] == self._mode,
                "INSPECTION_INVALID",
                "Helper inspection changed during reconstruction.",
            )
            self._inspection = _canonical(verified)
            self._operation, self._operator = operation, operator
            self._reason = None
            return self._finish_mutation("inspection")

    def _inspection_summary(self) -> dict[str, Any] | None:
        if self._inspection is None:
            return None
        value = json.loads(self._inspection)
        return {
            "catalog_id": value["catalog_id"],
            "display_name": value["catalog_label"],
            "catalog_sha256": value["catalog_sha256"],
            "inspection_sha256": value["inspection_sha256"],
            "operation_id": self._operation,
            "operator_id": self._operator,
            "inspection_status": value["inspection_status"],
            "inspection_provenance": value["inspection_provenance"],
            # A missing/drifted helper is not displayed as an observed digest.
            "helper_sha256": (
                value["helper_sha256"] if value["metadata_eligible"] else None
            ),
            "eligible_for_metadata_registration": value["metadata_eligible"],
            "blockers": list(value["blockers"]),
        }

    def _blockers(self) -> list[str]:
        values = set(_BASELINE_HOLDS)
        if self._inspection is not None:
            inspection = json.loads(self._inspection)
            values.update(inspection["blockers"])
            values.update(inspection["warnings"])
        _require(
            len(values) <= 32,
            "REPORT_LIMIT",
            "Helper review blockers exceed the display bound.",
        )
        return sorted(values)

    def preview(self) -> dict[str, Any]:
        with self._lock:
            _require(
                self._inspection is not None,
                "INSPECTION_REQUIRED",
                "Inspect the fixed helper catalog before review.",
            )
            return {
                "schema": "rocell.wizard_camera_helper_review_preview.v1",
                "provenance": self._provenance(),
                "inspection": self._inspection_summary(),
                "blockers": self._blockers(),
                "allowed_operations": ["inventory", "identity"],
                "required_role_separation": "DISTINCT_OPERATOR_LABELS_NOT_AUTHENTICATED_IDENTITIES",
                "meaning": "Review only the exact retained inspection for metadata operations. No path selection, source approval, process execution, probe or capture occurs here.",
                "probe_allowed": False,
                "capture_allowed": False,
                "connected": False,
                "qualified": False,
                "physical_authority": False,
            }

    def review(self, reviewer_id: str, *, operation_id: str) -> dict[str, Any]:
        with self._lock:
            self.invalidate_review("HELPER_REVIEW_NOT_VERIFIED")
            _require(
                self._inspection is not None,
                "INSPECTION_REQUIRED",
                "Inspect the fixed helper catalog before review.",
            )
            reviewer, operation = _text(reviewer_id), _identifier(operation_id)
            assert self._operator is not None and self._inspection is not None
            _require(
                reviewer.casefold() != self._operator.casefold(),
                "REVIEWER_MUST_DIFFER",
                "Use a reviewer label distinct from the inspection operator; labels are not authenticated identities.",
            )
            _require(
                operation != self._operation,
                "OPERATION_CONFLICT",
                "Inspection and review require distinct operation IDs.",
            )
            inspection = json.loads(self._inspection)
            accepted = inspection["metadata_eligible"] is True
            registration_hash = None
            if accepted:
                payload = {
                    "schema": "rocell.wizard_camera_helper_registration_artifact.v1",
                    "status": "METADATA_ONLY_REGISTERED",
                    "mode": self._mode,
                    "session_id": self._session,
                    "source_sha256": self._source,
                    "catalog_id": inspection["catalog_id"],
                    "catalog_sha256": inspection["catalog_sha256"],
                    "helper_sha256": inspection["helper_sha256"],
                    "inspection_provenance": inspection["inspection_provenance"],
                    "inspection_sha256": inspection["inspection_sha256"],
                    "inspection_operation_id": self._operation,
                    "inspection_operator_id": self._operator,
                    "review_operation_id": operation,
                    "reviewer_id": reviewer,
                    "distinct_operator_labels": True,
                    "allowed_operations": ["inventory", "identity"],
                    "probe_allowed": False,
                    "capture_allowed": False,
                    "connected": False,
                    "qualified": False,
                    "physical_authority": False,
                    "trust_scope": "DEVELOPMENT_METADATA_ONLY_NOT_TRUSTED_RELEASE",
                }
                self._artifact = _canonical(payload)
                registration_hash = hashlib.sha256(self._artifact).hexdigest()
            self._review = _canonical(
                {
                    "reviewer_id": reviewer,
                    "review_operation_id": operation,
                    "status": (
                        "METADATA_ONLY_REGISTERED"
                        if accepted
                        else "ACKNOWLEDGED_BUT_HELD"
                    ),
                    "registration_sha256": registration_hash,
                    "distinct_operator_labels": True,
                    "physical_authority": False,
                }
            )
            self._reason = None
            return self._finish_mutation("review")

    def registration(self) -> ReviewedCameraHelperRegistration | None:
        with self._lock:
            if self._artifact is None:
                return None
            assert self._inspection is not None
            return ReviewedCameraHelperRegistration(self._artifact, self._inspection)

    def _provenance(self) -> dict[str, str]:
        return {
            "mode": self._mode,
            "session_id": self._session,
            "source_sha256": self._source,
            "scope": "CAMERA_HELPER_METADATA_ONLY",
        }

    def view(self) -> dict[str, Any]:
        with self._lock:
            review = None if self._review is None else json.loads(self._review)
            status = (
                "INVALIDATED"
                if self._inspection is None and self._reason is not None
                else (
                    "NO_INSPECTION"
                    if self._inspection is None
                    else (
                        "METADATA_HELPER_REGISTERED"
                        if self._artifact is not None
                        else (
                            "REVIEW_HELD"
                            if review is not None
                            else "INSPECTION_RETAINED"
                        )
                    )
                )
            )
            return {
                "schema": SCHEMA,
                "status": status,
                "provenance": self._provenance(),
                "inspection": self._inspection_summary(),
                "review": review,
                "blockers": self._blockers(),
                "allowed_operations": ["inventory", "identity"],
                "probe_allowed": False,
                "capture_allowed": False,
                "connected": False,
                "qualified": False,
                "physical_authority": False,
                "invalidation_reason": self._reason,
            }

    def export_snapshot(self) -> dict[str, Any]:
        with self._lock:
            artifact = self.registration()
            return _owned(
                {
                    "schema": "rocell.wizard_camera_helper_registration_report.v1",
                    "view": self.view(),
                    "inspection_report": (
                        None
                        if self._inspection is None
                        else json.loads(self._inspection)
                    ),
                    "registration_artifact": (
                        None if artifact is None else artifact.to_dict()
                    ),
                }
            )

    def _finish_mutation(self, scope: str) -> dict[str, Any]:
        try:
            return self.export_snapshot()
        except CameraHelperRegistrationError:
            if scope == "inspection":
                self.invalidate("HELPER_INSPECTION_RESULT_NOT_RETAINED")
            else:
                self.invalidate_review("HELPER_REVIEW_RESULT_NOT_RETAINED")
            raise
