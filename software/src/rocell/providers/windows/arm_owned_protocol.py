"""Closed, bounded IPC for one owned non-purging arm feedback campaign.

This module performs no I/O and issues no physical authority. The process owner
pins/owns the child and revalidates consumed authority at both release boundaries.
The child uses its actual PID and random challenge, then requires RELEASE + EOF
before the existing fixed-T105 worker can be called. Physical dispatch is held.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from threading import Lock
from typing import Any, TYPE_CHECKING

from rocell.application.physical_connection_contracts import EvidenceOrigin
from rocell.application.rehearsal_arm_feedback_evidence import (
    RehearsalArmFeedbackEvidence,
    verify_rehearsal_arm_feedback_evidence,
)
from rocell.providers.windows.arm_feedback_worker import (
    ArmFeedbackCampaignRequest,
    ArmFeedbackCampaignResult,
    parse_arm_feedback_request,
)
from rocell.providers.windows.arm_nonpurging_adapter import (
    ArmNativeLifecycleEvidence,
    verify_arm_native_lifecycle_evidence,
)


LEGACY_REQUEST_SCHEMA = "rocell.arm_owned_request.v1"
PREVIOUS_REQUEST_SCHEMA = "rocell.arm_owned_request.v2"
REQUEST_SCHEMA = "rocell.arm_owned_request.v3"
READY_SCHEMA = "rocell.arm_owned_ready.v1"
RELEASE_SCHEMA = "rocell.arm_owned_release.v1"
LEGACY_RESULT_SCHEMA = "rocell.arm_owned_result.v1"
RESULT_SCHEMA = "rocell.arm_owned_result.v2"
INCAPABLE_PROVENANCE = "INCAPABLE_NONPURGING_ARM_WORKER"
PHYSICAL_HELD_PROVENANCE = "PHYSICAL_NONPURGING_ARM_HELD"
PHYSICAL_HOLD = "ARM_NONPURGING_PHYSICAL_ACTIVATION_HELD"
ADMISSION_TIMEOUT_MS = 5000
# Historical v1 evidence keeps its original two-second bound. Only v3 is
# prepared/executed by the current closed child; decoding is not re-admission.
_REQUEST_ADMISSION_MS = {
    LEGACY_REQUEST_SCHEMA: 2000,
    PREVIOUS_REQUEST_SCHEMA: 5000,
    REQUEST_SCHEMA: ADMISSION_TIMEOUT_MS,
}
CLEANUP_TIMEOUT_MS = 2000
MAX_REQUEST_BYTES = 60 * 1024
MAX_HANDSHAKE_BYTES = 2048
MAX_RESULT_BYTES = 48 * 1024
MAX_FEEDBACK_LINE_BYTES = 2048
LEGACY_SCENARIOS = frozenset(
    {
        "nominal",
        "boot-bytes",
        "short-write",
        "timeout",
        "identity-change",
        "close-failure",
        "malformed-response",
        "extra-response",
        "child-timeout",
        "malformed-result",
    }
)
SCENARIOS = LEGACY_SCENARIOS | {"identity-change-preopen", "malformed-metadata"}

if TYPE_CHECKING:
    from rocell.application.arm_controller_resolution import ControllerResolutionTrace
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,63}\Z")


class ArmOwnedProtocolError(ValueError):
    """Fixed diagnostic codes only; raw wire stays in private process evidence."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(condition: bool, code: str = "INVALID_ARM_OWNED_PROTOCOL") -> None:
    if not condition:
        raise ArmOwnedProtocolError(code)


def _digest(value: Any) -> None:
    _require(
        type(value) is str and _HASH.fullmatch(value) is not None and value != "0" * 64
    )


def _integer(value: Any, low: int = 0, high: int = 2**63 - 1) -> None:
    _require(type(value) is int and low <= value <= high)


def _canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (ValueError, TypeError, UnicodeError, RecursionError) as exc:
        raise ArmOwnedProtocolError("INVALID_ARM_OWNED_JSON") from exc


def _sha(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "DUPLICATE_ARM_OWNED_FIELD")
        result[key] = value
    return result


def _decode(payload: bytes, maximum: int) -> dict[str, Any]:
    _require(
        type(payload) is bytes and 0 < len(payload) <= maximum, "ARM_OWNED_BYTES_LIMIT"
    )
    try:
        document = json.loads(
            payload,
            object_pairs_hook=_unique,
            parse_constant=lambda _: (_ for _ in ()).throw(
                ArmOwnedProtocolError("NONFINITE_ARM_OWNED_JSON")
            ),
        )
    except (ValueError, UnicodeError, RecursionError) as exc:
        if isinstance(exc, ArmOwnedProtocolError):
            raise
        raise ArmOwnedProtocolError("INVALID_ARM_OWNED_JSON") from exc
    _require(
        type(document) is dict and _canonical(document) == payload,
        "NONCANONICAL_ARM_OWNED_JSON",
    )
    return document


def _line(wire: bytes, maximum: int) -> bytes:
    _require(
        type(wire) is bytes and 1 < len(wire) <= maximum + 1, "ARM_OWNED_WIRE_LIMIT"
    )
    _require(
        wire.endswith(b"\n") and b"\n" not in wire[:-1] and b"\r" not in wire,
        "ARM_OWNED_ONE_LINE_REQUIRED",
    )
    return wire[:-1]


_REQUEST_FIELDS = {
    "schema",
    "session_id",
    "attempt_id",
    "source_sha256",
    "operation_sha256",
    "permit_sha256",
    "selected_identity_sha256",
    "worker_registration_sha256",
    "feedback_request",
    "provenance",
    "scenario",
    "parent_deadline_monotonic_ns",
    "admission_timeout_ms",
    "cleanup_timeout_ms",
    "physical_authority",
    "request_sha256",
}


@dataclass(frozen=True, slots=True)
class ArmOwnedRequest:
    payload: bytes

    def __post_init__(self) -> None:
        doc = _decode(self.payload, MAX_REQUEST_BYTES)
        _require(
            set(doc) == _REQUEST_FIELDS
            and type(doc["schema"]) is str
            and doc["schema"] in _REQUEST_ADMISSION_MS
        )
        for name in ("session_id", "attempt_id"):
            _require(type(doc[name]) is str and _ID.fullmatch(doc[name]) is not None)
        for name in (
            "source_sha256",
            "operation_sha256",
            "permit_sha256",
            "selected_identity_sha256",
            "worker_registration_sha256",
            "request_sha256",
        ):
            _digest(doc[name])
        _require(
            doc["admission_timeout_ms"] == _REQUEST_ADMISSION_MS[doc["schema"]]
            and type(doc["admission_timeout_ms"]) is int
        )
        _require(
            doc["cleanup_timeout_ms"] == CLEANUP_TIMEOUT_MS
            and type(doc["cleanup_timeout_ms"]) is int
        )
        _require(doc["physical_authority"] is False)
        try:
            inner = parse_arm_feedback_request(_canonical(doc["feedback_request"]))
        except (ValueError, RuntimeError) as exc:
            raise ArmOwnedProtocolError("INVALID_INNER_FEEDBACK_REQUEST") from exc
        _require(
            inner.campaign_id == doc["attempt_id"]
            and inner.feedback.run_id == doc["session_id"],
            "ARM_OWNED_SESSION_MISMATCH",
        )
        _require(
            inner.source_sha256 == doc["source_sha256"]
            and inner.operation_sha256 == doc["operation_sha256"],
            "ARM_OWNED_SOURCE_OPERATION_MISMATCH",
        )
        _require(
            inner.feedback.safety_permit_sha256 == doc["permit_sha256"],
            "ARM_OWNED_PERMIT_MISMATCH",
        )
        _require(
            inner.controller.identity.identity_sha256
            == doc["selected_identity_sha256"],
            "ARM_OWNED_IDENTITY_MISMATCH",
        )
        _require(
            inner.feedback.maximum_line_bytes <= MAX_FEEDBACK_LINE_BYTES,
            "ARM_OWNED_FEEDBACK_LINE_LIMIT",
        )
        _integer(
            doc["parent_deadline_monotonic_ns"],
            inner.feedback.requested_monotonic_ns + 1,
            inner.expires_monotonic_ns,
        )
        _require(
            inner.feedback.requested_monotonic_ns
            + (inner.budget.duration_ms + CLEANUP_TIMEOUT_MS) * 1_000_000
            <= doc["parent_deadline_monotonic_ns"],
            "ARM_OWNED_LIFETIME_TOO_SHORT",
        )
        if doc["provenance"] == INCAPABLE_PROVENANCE:
            _require(
                inner.controller.origin is EvidenceOrigin.SYNTHETIC_REHEARSAL
                and doc["scenario"]
                in (SCENARIOS if doc["schema"] == REQUEST_SCHEMA else LEGACY_SCENARIOS)
            )
        else:
            _require(
                doc["provenance"] == PHYSICAL_HELD_PROVENANCE
                and inner.controller.origin is EvidenceOrigin.PHYSICAL_OBSERVATION
                and doc["scenario"] == "physical-held"
            )
        core = {key: value for key, value in doc.items() if key != "request_sha256"}
        _require(
            _sha(_canonical(core)) == doc["request_sha256"],
            "ARM_OWNED_REQUEST_HASH_MISMATCH",
        )

    @property
    def request_sha256(self) -> str:
        return self.to_dict()["request_sha256"]  # type: ignore[no-any-return]

    @property
    def feedback_request(self) -> ArmFeedbackCampaignRequest:
        return parse_arm_feedback_request(
            _canonical(self.to_dict()["feedback_request"])
        )

    def to_dict(self) -> dict[str, Any]:
        return _decode(self.payload, MAX_REQUEST_BYTES)

    def wire(self) -> bytes:
        return self.payload + b"\n"


def build_arm_owned_request(
    *,
    session_id: str,
    attempt_id: str,
    source_sha256: str,
    operation_sha256: str,
    permit_sha256: str,
    selected_identity_sha256: str,
    worker_registration_sha256: str,
    feedback_request: ArmFeedbackCampaignRequest,
    provenance: str,
    scenario: str,
    parent_deadline_monotonic_ns: int,
) -> ArmOwnedRequest:
    _require(type(feedback_request) is ArmFeedbackCampaignRequest)
    core = {
        "schema": REQUEST_SCHEMA,
        "session_id": session_id,
        "attempt_id": attempt_id,
        "source_sha256": source_sha256,
        "operation_sha256": operation_sha256,
        "permit_sha256": permit_sha256,
        "selected_identity_sha256": selected_identity_sha256,
        "worker_registration_sha256": worker_registration_sha256,
        "feedback_request": feedback_request.to_dict(),
        "provenance": provenance,
        "scenario": scenario,
        "parent_deadline_monotonic_ns": parent_deadline_monotonic_ns,
        "admission_timeout_ms": ADMISSION_TIMEOUT_MS,
        "cleanup_timeout_ms": CLEANUP_TIMEOUT_MS,
        "physical_authority": False,
    }
    return ArmOwnedRequest(
        _canonical({**core, "request_sha256": _sha(_canonical(core))})
    )


@dataclass(frozen=True, slots=True)
class ArmOwnedReady:
    payload: bytes

    def __post_init__(self) -> None:
        doc = _decode(self.payload, MAX_HANDSHAKE_BYTES)
        _require(
            set(doc) == {"schema", "request_sha256", "child_pid", "challenge_sha256"}
            and doc["schema"] == READY_SCHEMA
        )
        _digest(doc["request_sha256"])
        _digest(doc["challenge_sha256"])
        _integer(doc["child_pid"], 1, 2**32 - 1)

    def to_dict(self) -> dict[str, Any]:
        return _decode(self.payload, MAX_HANDSHAKE_BYTES)

    def wire(self) -> bytes:
        return self.payload + b"\n"

    @property
    def ready_sha256(self) -> str:
        return _sha(self.payload)


def build_arm_owned_ready(
    request: ArmOwnedRequest, *, child_pid: int, challenge_sha256: str
) -> ArmOwnedReady:
    _require(type(request) is ArmOwnedRequest)
    return ArmOwnedReady(
        _canonical(
            {
                "schema": READY_SCHEMA,
                "request_sha256": request.request_sha256,
                "child_pid": child_pid,
                "challenge_sha256": challenge_sha256,
            }
        )
    )


def parse_arm_owned_ready(
    wire: bytes, *, expected_request_sha256: str, expected_child_pid: int
) -> ArmOwnedReady:
    _digest(expected_request_sha256)
    _integer(expected_child_pid, 1, 2**32 - 1)
    result = ArmOwnedReady(_line(wire, MAX_HANDSHAKE_BYTES))
    doc = result.to_dict()
    _require(
        doc["request_sha256"] == expected_request_sha256
        and doc["child_pid"] == expected_child_pid,
        "ARM_OWNED_READY_BINDING_MISMATCH",
    )
    return result


def arm_owned_release(request: ArmOwnedRequest, ready: ArmOwnedReady) -> bytes:
    _require(type(request) is ArmOwnedRequest and type(ready) is ArmOwnedReady)
    req, observed = request.to_dict(), ready.to_dict()
    _require(
        observed["request_sha256"] == request.request_sha256,
        "ARM_OWNED_READY_BINDING_MISMATCH",
    )
    return (
        _canonical(
            {
                "schema": RELEASE_SCHEMA,
                "request_sha256": request.request_sha256,
                "ready_sha256": ready.ready_sha256,
                "child_pid": observed["child_pid"],
                "challenge_sha256": observed["challenge_sha256"],
                "permit_sha256": req["permit_sha256"],
                "parent_deadline_monotonic_ns": req["parent_deadline_monotonic_ns"],
            }
        )
        + b"\n"
    )


class ArmOwnedChildGate:
    """Pure one-use child gate; caller owns PID, randomness, clock and stdin."""

    def __init__(
        self,
        request: ArmOwnedRequest,
        *,
        child_pid: int,
        challenge_sha256: str,
        started_monotonic_ns: int,
    ) -> None:
        _require(type(request) is ArmOwnedRequest)
        self._request = ArmOwnedRequest(request.payload)
        # Decoding historical bytes must not re-admit their executable gate.
        _require(
            self._request.to_dict()["schema"] == REQUEST_SCHEMA,
            "ARM_REQUEST_VERSION_HELD",
        )
        self._ready = build_arm_owned_ready(
            self._request, child_pid=child_pid, challenge_sha256=challenge_sha256
        )
        inner = request.feedback_request
        _integer(
            started_monotonic_ns,
            inner.feedback.requested_monotonic_ns,
            request.to_dict()["parent_deadline_monotonic_ns"] - 1,
        )
        self._started = started_monotonic_ns
        self._used = False
        self._lock = Lock()

    @property
    def ready(self) -> ArmOwnedReady:
        """The original child identity/challenge cannot be publicly replaced."""
        return self._ready

    def accept_release(self, wire: bytes, *, now_ns: int, stdin_eof: bool) -> None:
        _require(self._lock.acquire(blocking=False), "ARM_OWNED_CONCURRENT_RELEASE")
        try:
            _require(not self._used, "ARM_OWNED_RELEASE_ALREADY_ATTEMPTED")
            self._used = True
            _require(stdin_eof is True, "ARM_OWNED_RELEASE_REQUIRES_EOF")
            _line(wire, MAX_HANDSHAKE_BYTES)
            _require(
                wire == arm_owned_release(self._request, self.ready),
                "ARM_OWNED_RELEASE_BINDING_MISMATCH",
            )
            _integer(
                now_ns,
                self._started,
                self._started
                + self._request.to_dict()["admission_timeout_ms"] * 1_000_000
                - 1,
            )
            inner = self._request.feedback_request
            _require(
                now_ns + (inner.budget.duration_ms + CLEANUP_TIMEOUT_MS) * 1_000_000
                <= self._request.to_dict()["parent_deadline_monotonic_ns"],
                "ARM_OWNED_FULL_LIFETIME_EXPIRED",
            )
            _require(
                self._request.to_dict()["provenance"] == INCAPABLE_PROVENANCE,
                PHYSICAL_HOLD,
            )
        finally:
            self._lock.release()


@dataclass(frozen=True, slots=True)
class ArmOwnedResult:
    payload: bytes
    expected_request: ArmOwnedRequest

    def __post_init__(self) -> None:
        _require(type(self.expected_request) is ArmOwnedRequest)
        ArmOwnedRequest(self.expected_request.payload)
        doc = _decode(self.payload, MAX_RESULT_BYTES)
        current = self.expected_request.to_dict()["schema"] == REQUEST_SCHEMA
        _require(
            set(doc)
            == {
                "schema",
                "request_sha256",
                "status",
                "feedback_evidence",
                "feedback_evidence_sha256",
                "native_evidence",
                "native_evidence_sha256",
                "error_code",
                "physical_authority",
            }
            | ({"resolution_trace", "resolution_trace_sha256"} if current else set())
        )
        _require(
            doc["schema"] == (RESULT_SCHEMA if current else LEGACY_RESULT_SCHEMA)
            and doc["request_sha256"] == self.expected_request.request_sha256
            and doc["physical_authority"] is False
        )
        if doc["status"] == "PHYSICAL_HELD":
            if current:
                _require(
                    doc["resolution_trace"] is None
                    and doc["resolution_trace_sha256"] is None
                )
            _require(
                self.expected_request.to_dict()["provenance"]
                == PHYSICAL_HELD_PROVENANCE
                and doc["error_code"] == PHYSICAL_HOLD
            )
            _require(
                all(
                    doc[key] is None
                    for key in (
                        "feedback_evidence",
                        "feedback_evidence_sha256",
                        "native_evidence",
                        "native_evidence_sha256",
                    )
                )
            )
        else:
            _require(
                doc["status"] == "FEEDBACK_RETAINED"
                and doc["error_code"] is None
                and self.expected_request.to_dict()["provenance"]
                == INCAPABLE_PROVENANCE
            )
            feedback = self.feedback_evidence
            assert feedback is not None
            verify_arm_native_lifecycle_evidence(
                _canonical(doc["native_evidence"]),
                expected_request=self.expected_request.feedback_request,
                expected_result=feedback.result,
                expected_evidence_sha256=doc["native_evidence_sha256"],
            )
            if current:
                from rocell.application.arm_controller_resolution import (
                    verify_controller_resolution_trace,
                )

                verify_controller_resolution_trace(
                    _canonical(doc["resolution_trace"]),
                    reviewed=self.expected_request.feedback_request.controller,
                    expected_deadline_ns=self.expected_request.feedback_request.expires_monotonic_ns,
                    expected_trace_sha256=doc["resolution_trace_sha256"],
                    expected_result=feedback.result,
                )

    def to_dict(self) -> dict[str, Any]:
        return _decode(self.payload, MAX_RESULT_BYTES)

    def wire(self) -> bytes:
        return self.payload + b"\n"

    @property
    def feedback_evidence(self) -> RehearsalArmFeedbackEvidence | None:
        doc = self.to_dict()
        if doc["feedback_evidence"] is None:
            return None
        return verify_rehearsal_arm_feedback_evidence(
            _canonical(doc["feedback_evidence"]),
            expected_request=self.expected_request.feedback_request,
            expected_binding_sha256=self.expected_request.request_sha256,
            expected_evidence_sha256=doc["feedback_evidence_sha256"],
            expected_source_sha256=self.expected_request.to_dict()["source_sha256"],
        )

    @property
    def native_evidence(self) -> ArmNativeLifecycleEvidence | None:
        doc, feedback = self.to_dict(), self.feedback_evidence
        if feedback is None:
            return None
        return verify_arm_native_lifecycle_evidence(
            _canonical(doc["native_evidence"]),
            expected_request=self.expected_request.feedback_request,
            expected_result=feedback.result,
            expected_evidence_sha256=doc["native_evidence_sha256"],
        )

    @property
    def result(self) -> ArmFeedbackCampaignResult | None:
        feedback = self.feedback_evidence
        return None if feedback is None else feedback.result

    @property
    def resolution_trace(self) -> ControllerResolutionTrace | None:
        doc = self.to_dict()
        if doc["schema"] == LEGACY_RESULT_SCHEMA or doc["resolution_trace"] is None:
            return None
        from rocell.application.arm_controller_resolution import (
            ControllerResolutionTrace,
        )

        return ControllerResolutionTrace(_canonical(doc["resolution_trace"]))


def build_arm_owned_result(
    request: ArmOwnedRequest,
    *,
    feedback_evidence: RehearsalArmFeedbackEvidence | None = None,
    native_evidence: ArmNativeLifecycleEvidence | None = None,
    resolution_trace: ControllerResolutionTrace | None = None,
) -> ArmOwnedResult:
    _require(type(request) is ArmOwnedRequest)
    _require(request.to_dict()["schema"] == REQUEST_SCHEMA, "ARM_REQUEST_VERSION_HELD")
    from rocell.application.arm_controller_resolution import ControllerResolutionTrace

    held = request.to_dict()["provenance"] == PHYSICAL_HELD_PROVENANCE
    _require(
        (held and feedback_evidence is native_evidence is resolution_trace is None)
        or (
            not held
            and type(feedback_evidence) is RehearsalArmFeedbackEvidence
            and type(native_evidence) is ArmNativeLifecycleEvidence
            and type(resolution_trace) is ControllerResolutionTrace
        )
    )
    return ArmOwnedResult(
        _canonical(
            {
                "schema": RESULT_SCHEMA,
                "request_sha256": request.request_sha256,
                "status": "PHYSICAL_HELD" if held else "FEEDBACK_RETAINED",
                "resolution_trace": (
                    None if resolution_trace is None else resolution_trace.to_dict()
                ),
                "resolution_trace_sha256": (
                    None if resolution_trace is None else resolution_trace.sha256
                ),
                "feedback_evidence": (
                    None if feedback_evidence is None else feedback_evidence.to_dict()
                ),
                "feedback_evidence_sha256": (
                    None
                    if feedback_evidence is None
                    else feedback_evidence.evidence_sha256
                ),
                "native_evidence": (
                    None if native_evidence is None else native_evidence.to_dict()
                ),
                "native_evidence_sha256": (
                    None if native_evidence is None else native_evidence.evidence_sha256
                ),
                "error_code": PHYSICAL_HOLD if held else None,
                "physical_authority": False,
            }
        ),
        ArmOwnedRequest(request.payload),
    )


def parse_arm_owned_result(
    wire: bytes, *, expected_request: ArmOwnedRequest, returncode: int
) -> ArmOwnedResult:
    _integer(returncode, 0, 2**32 - 1)
    result = ArmOwnedResult(
        _line(wire, MAX_RESULT_BYTES), ArmOwnedRequest(expected_request.payload)
    )
    _require(
        returncode == (2 if result.to_dict()["status"] == "PHYSICAL_HELD" else 0),
        "ARM_OWNED_RESULT_EXIT_MISMATCH",
    )
    return result
