"""Complete bounded arm IPC evidence; process cleanup is not device/power proof.

The artifact retains exact stdout/stderr and independently verifies the existing
full feedback evidence and native lifecycle companion. It never opens a process,
file, DLL or device, and never reruns the worker while verifying retained bytes.
"""

from __future__ import annotations

import base64
from dataclasses import dataclass, fields
import re
from typing import Any, TYPE_CHECKING

if TYPE_CHECKING:
    from rocell.application.arm_controller_resolution import ControllerResolutionTrace

from rocell.application.rehearsal_arm_feedback_evidence import (
    RehearsalArmFeedbackEvidence,
)
from rocell.providers.windows.arm_feedback_worker import ArmFeedbackCampaignRequest
from rocell.providers.windows.arm_nonpurging_adapter import ArmNativeLifecycleEvidence
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from rocell.providers.windows.arm_owned_protocol import (
    ArmOwnedProtocolError,
    ArmOwnedReady,
    ArmOwnedRequest,
    ArmOwnedResult,
    INCAPABLE_PROVENANCE,
    PHYSICAL_HELD_PROVENANCE,
    REQUEST_SCHEMA,
    arm_owned_release,
    parse_arm_owned_result,
    _canonical,
    _decode,
    _digest,
    _integer,
    _require,
    _sha,
)


SCHEMA = "rocell.arm_owned_evidence.v1"
LEGACY_SUMMARY_SCHEMA = "rocell.arm_owned_evidence_summary.v1"
SUMMARY_SCHEMA = "rocell.arm_owned_evidence_summary.v2"
MAX_EVIDENCE_BYTES = 128 * 1024
MAX_STDOUT_BYTES = 64 * 1024
MAX_STDERR_BYTES = 8 * 1024
_POWER = "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
_SAFE_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,95}(?::[A-Za-z0-9_.-]{1,31})?\Z")
_PROCESS_CONST = {
    "schema": "rocell.owned_worker_process_result.v1",
    "physical_authority": False,
    "physical_provider_qualified": False,
    "device_cleanup_confirmed": False,
    "final_power_state": _POWER,
    "handle_limit_kind": "SAMPLED_NOT_KERNEL_ENFORCED",
    "retries": 0,
}
_PROCESS_FIELDS = {field.name for field in fields(OwnedWorkerResult)} - {
    "stdout",
    "stderr",
}


class ArmOwnedEvidenceError(ArmOwnedProtocolError):
    """Invalid retained evidence; public detail is a stable diagnostic code."""


def _wire(raw: bytes, maximum: int) -> dict[str, Any]:
    _require(
        type(raw) is bytes and len(raw) <= maximum, "ARM_OWNED_RETAINED_BYTES_LIMIT"
    )
    return {
        "bytes": len(raw),
        "sha256": _sha(raw),
        "base64": base64.b64encode(raw).decode("ascii"),
    }


def _bytes(value: Any, maximum: int) -> bytes:
    _require(type(value) is dict and set(value) == {"bytes", "sha256", "base64"})
    _integer(value["bytes"], 0, maximum)
    _require(
        type(value["base64"]) is str
        and len(value["base64"]) <= 4 * ((maximum + 2) // 3)
    )
    try:
        raw = base64.b64decode(value["base64"], validate=True)
    except (ValueError, TypeError) as exc:
        raise ArmOwnedEvidenceError("INVALID_ARM_OWNED_BASE64") from exc
    _require(_wire(raw, maximum) == value, "ARM_OWNED_RAW_HASH_MISMATCH")
    return raw


def _text(value: Any) -> None:
    _require(
        type(value) is str and 0 < len(value.encode("utf-8")) <= 512,
        "ARM_OWNED_ERROR_TEXT_LIMIT",
    )


def _safe_code(value: str | None) -> str | None:
    if value is None:
        return None
    return value if _SAFE_CODE.fullmatch(value) else "RETAINED_PROCESS_ERROR"


def _process(
    document: Any,
    request: ArmOwnedRequest,
    ready: ArmOwnedReady | None,
    release: bytes | None,
) -> OwnedWorkerResult:
    _require(type(document) is dict and set(document) == {"report", "stdout", "stderr"})
    report = document["report"]
    _require(
        type(report) is dict
        and set(report)
        == _PROCESS_FIELDS
        | set(_PROCESS_CONST)
        | {"stdout_bytes", "stdout_sha256", "stderr_bytes", "stderr_sha256"}
    )
    for key, expected in _PROCESS_CONST.items():
        _require(
            _canonical(report[key]) == _canonical(expected),
            "ARM_OWNED_PROCESS_AUTHORITY_MISMATCH",
        )
    _require(
        report["request_sha256"] == request.request_sha256
        and report["attempt_id"] == request.to_dict()["attempt_id"],
        "ARM_OWNED_PROCESS_BINDING_MISMATCH",
    )
    _require(report["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"})
    for key in ("process_created", "initial_thread_resumed", "tree_exit_confirmed"):
        _require(type(report[key]) is bool)
    _require(not report["initial_thread_resumed"] or report["process_created"])
    _require(not report["tree_exit_confirmed"] or report["process_created"])
    if report["primary_error"] is not None:
        _text(report["primary_error"])
    _require(
        type(report["cleanup_errors"]) is list and len(report["cleanup_errors"]) <= 64
    )
    for error in report["cleanup_errors"]:
        _text(error)
    for key in (
        "elapsed_ns",
        "stdin_bytes_written",
        "peak_observed_handles",
        "peak_active_processes",
    ):
        _integer(report[key])
    _integer(report["peak_observed_handles"], 0, 65536)
    _integer(report["peak_active_processes"], 0, 1024)
    if report["returncode"] is not None:
        _integer(report["returncode"], 0, 2**32 - 1)
        _require(report["process_created"])
    stdout = _bytes(document["stdout"], MAX_STDOUT_BYTES)
    stderr = _bytes(document["stderr"], MAX_STDERR_BYTES)
    for key, raw in (("stdout", stdout), ("stderr", stderr)):
        _require(
            report[key + "_bytes"] == len(raw)
            and type(report[key + "_bytes"]) is int
            and report[key + "_sha256"] == _sha(raw),
            "ARM_OWNED_PROCESS_RAW_MISMATCH",
        )
    _require(
        report["stdin_bytes_written"]
        <= len(request.wire()) + (0 if release is None else len(release)),
        "ARM_OWNED_STDIN_ACCOUNTING_MISMATCH",
    )
    if not report["process_created"]:
        _require(
            not stdout
            and not stderr
            and report["stdin_bytes_written"] == 0
            and report["returncode"] is None
        )
    if ready is not None:
        _require(
            report["process_created"]
            and report["initial_thread_resumed"]
            and report["stdin_bytes_written"] >= len(request.wire())
            and stdout.startswith(ready.wire()),
            "ARM_OWNED_READY_PROCESS_MISMATCH",
        )
    if report["status"] == "SUCCEEDED":
        _require(
            report["primary_error"] is None
            and not report["cleanup_errors"]
            and report["process_created"]
            and report["initial_thread_resumed"]
            and report["tree_exit_confirmed"]
            and report["returncode"] == 0
            and type(report["parsed_result"]) is dict,
            "ARM_OWNED_PROCESS_SUCCESS_MISMATCH",
        )
    else:
        _require(
            report["primary_error"] is not None or bool(report["cleanup_errors"]),
            "ARM_OWNED_PROCESS_FAILURE_UNEXPLAINED",
        )
    values = {key: report[key] for key in _PROCESS_FIELDS}
    values["cleanup_errors"] = tuple(values["cleanup_errors"])
    result = OwnedWorkerResult(**values, stdout=stdout, stderr=stderr)
    _require(
        _canonical(result.to_dict()) == _canonical(report),
        "ARM_OWNED_PROCESS_ROUNDTRIP_MISMATCH",
    )
    return result


def _validated(
    payload: bytes,
) -> tuple[
    dict[str, Any],
    ArmOwnedRequest,
    OwnedWorkerResult,
    ArmOwnedReady | None,
    bytes | None,
    ArmOwnedResult | None,
]:
    doc = _decode(payload, MAX_EVIDENCE_BYTES)
    _require(
        set(doc)
        == {
            "schema",
            "request",
            "request_sha256",
            "process",
            "ready",
            "release",
            "physical_authority",
        }
        and doc["schema"] == SCHEMA
        and doc["physical_authority"] is False
    )
    request = ArmOwnedRequest(_canonical(doc["request"]))
    _require(doc["request_sha256"] == request.request_sha256)
    ready = None if doc["ready"] is None else ArmOwnedReady(_canonical(doc["ready"]))
    if ready is not None:
        _require(
            ready.to_dict()["request_sha256"] == request.request_sha256,
            "ARM_OWNED_READY_BINDING_MISMATCH",
        )
    release = None if doc["release"] is None else _bytes(doc["release"], 2049)
    if release is not None:
        _require(
            ready is not None and release == arm_owned_release(request, ready),
            "ARM_OWNED_RELEASE_BINDING_MISMATCH",
        )
    process = _process(doc["process"], request, ready, release)
    result = None
    if process.parsed_result is not None:
        _require(type(process.parsed_result) is dict and process.returncode is not None)
        assert process.returncode is not None
        # Retain exact process bytes in addition to the independently validated
        # nested records. A malformed/partial stdout stays raw-only, not guessed.
        result_wire = _canonical(process.parsed_result) + b"\n"
        result = parse_arm_owned_result(
            result_wire, expected_request=request, returncode=process.returncode
        )
        _require(
            process.stdout == (b"" if ready is None else ready.wire()) + result_wire,
            "ARM_OWNED_STDOUT_SEQUENCE_MISMATCH",
        )
        if result.to_dict()["status"] == "FEEDBACK_RETAINED":
            _require(
                ready is not None
                and release is not None
                and process.stdin_bytes_written == len(request.wire()) + len(release),
                "ARM_OWNED_FEEDBACK_RELEASE_UNPROVEN",
            )
    return doc, request, process, ready, release, result


@dataclass(frozen=True, slots=True)
class ArmOwnedEvidence:
    payload: bytes

    def __post_init__(self) -> None:
        try:
            _validated(self.payload)
        except (
            ValueError,
            RuntimeError,
            KeyError,
            TypeError,
            AttributeError,
            RecursionError,
        ) as exc:
            if isinstance(exc, ArmOwnedEvidenceError):
                raise
            raise ArmOwnedEvidenceError("INVALID_ARM_OWNED_EVIDENCE") from exc

    @property
    def evidence_sha256(self) -> str:
        return _sha(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _decode(self.payload, MAX_EVIDENCE_BYTES)

    @property
    def outer_request(self) -> ArmOwnedRequest:
        return ArmOwnedRequest(_canonical(self.to_dict()["request"]))

    @property
    def request(self) -> ArmFeedbackCampaignRequest:
        return self.outer_request.feedback_request

    @property
    def feedback(self) -> RehearsalArmFeedbackEvidence | None:
        result = _validated(self.payload)[-1]
        return None if result is None else result.feedback_evidence

    @property
    def native(self) -> ArmNativeLifecycleEvidence | None:
        result = _validated(self.payload)[-1]
        return None if result is None else result.native_evidence

    @property
    def resolution(self) -> ControllerResolutionTrace | None:
        result = _validated(self.payload)[-1]
        return None if result is None else result.resolution_trace

    def safe_summary(self) -> dict[str, Any]:
        _, request, process, ready, release, result = _validated(self.payload)
        req = request.to_dict()
        current = req["schema"] == REQUEST_SCHEMA
        feedback = None if result is None else result.feedback_evidence
        native = None if result is None else result.native_evidence
        resolution = None if result is None else result.resolution_trace
        complete = (
            process.status == "SUCCEEDED"
            and feedback is not None
            and native is not None
            and (not current or resolution is not None)
        )
        held = result is not None and result.to_dict()["status"] == "PHYSICAL_HELD"
        blockers = []
        if not complete:
            blockers.append("COMPLETE_OWNED_FEEDBACK_NOT_ESTABLISHED")
        if process.status != "SUCCEEDED":
            blockers.append("PROCESS_LIFECYCLE_NOT_CLEAN")
        if feedback is None:
            blockers.append("FULL_FEEDBACK_EVIDENCE_UNAVAILABLE")
        if native is None:
            blockers.append("NATIVE_LIFECYCLE_EVIDENCE_UNAVAILABLE")
        if current and resolution is None:
            blockers.append("CONTROLLER_RESOLUTION_EVIDENCE_UNAVAILABLE")
        feedback_view = None
        if feedback is not None:
            serial, summary = feedback.result, feedback.safe_summary()
            feedback_view = {
                "status": serial.outcome.value,
                "technical_response_valid": summary["technical_response_valid"],
                "connection_closed": serial.connection_closed,
                "response_bytes": len(serial.response_bytes),
                "response_sha256": _sha(serial.response_bytes),
                "unexpected_bytes": len(serial.unexpected_bytes),
                "unexpected_sha256": _sha(serial.unexpected_bytes),
                "unexpected_bytes_unretained": serial.unexpected_bytes_unretained,
            }
        return {
            "schema": SUMMARY_SCHEMA if current else LEGACY_SUMMARY_SCHEMA,
            "status": (
                "PHYSICAL_HELD"
                if held
                else ("COMPLETE_INCAPABLE_EVIDENCE" if complete else "INCOMPLETE")
            ),
            "provenance": req["provenance"],
            **{
                key: req[key]
                for key in (
                    "session_id",
                    "attempt_id",
                    "source_sha256",
                    "permit_sha256",
                    "operation_sha256",
                    "selected_identity_sha256",
                    "worker_registration_sha256",
                    "request_sha256",
                )
            },
            "inner_request_sha256": request.feedback_request.request_sha256,
            "evidence_sha256": self.evidence_sha256,
            "process": {
                "status": process.status,
                "process_created": process.process_created,
                "initial_thread_resumed": process.initial_thread_resumed,
                "tree_exit_confirmed": process.tree_exit_confirmed,
                "returncode": process.returncode,
                "primary_error": _safe_code(process.primary_error),
                "cleanup_errors": [
                    _safe_code(error) for error in process.cleanup_errors[:16]
                ],
                "cleanup_error_count": len(process.cleanup_errors),
                "cleanup_errors_omitted": max(0, len(process.cleanup_errors) - 16),
                "stdin_bytes_written": process.stdin_bytes_written,
                "stdout_bytes": len(process.stdout),
                "stdout_sha256": _sha(process.stdout),
                "stderr_bytes": len(process.stderr),
                "stderr_sha256": _sha(process.stderr),
            },
            "handshake": {
                "ready_retained": ready is not None,
                "release_retained": release is not None,
                "child_pid": None if ready is None else ready.to_dict()["child_pid"],
            },
            "feedback": feedback_view,
            "native": None if native is None else native.view(),
            **(
                {
                    "resolution": (
                        None if resolution is None else resolution.safe_summary()
                    )
                }
                if current
                else {}
            ),
            "blockers": blockers,
            "physical_authority": False,
            "arm_connected": False,
            "device_cleanup_proven": False,
            "final_power_state": _POWER,
            "meaning": "Complete means retained incapable process, feedback and native-owner records, not successful serial operation or physical qualification. Process cleanup is separate from serial cleanup; final power requires an independent observation.",
        }


def retain_arm_owned_evidence(
    *,
    request: ArmOwnedRequest,
    process_result: OwnedWorkerResult,
    ready: ArmOwnedReady | None = None,
    release_wire: bytes | None = None,
) -> ArmOwnedEvidence:
    _require(
        type(request) is ArmOwnedRequest and type(process_result) is OwnedWorkerResult,
        "EXACT_ARM_OWNED_RETENTION_TYPES_REQUIRED",
    )
    _require(ready is None or type(ready) is ArmOwnedReady)
    return ArmOwnedEvidence(
        _canonical(
            {
                "schema": SCHEMA,
                "request": request.to_dict(),
                "request_sha256": request.request_sha256,
                "process": {
                    "report": process_result.to_dict(),
                    "stdout": _wire(process_result.stdout, MAX_STDOUT_BYTES),
                    "stderr": _wire(process_result.stderr, MAX_STDERR_BYTES),
                },
                "ready": None if ready is None else ready.to_dict(),
                "release": None if release_wire is None else _wire(release_wire, 2049),
                "physical_authority": False,
            }
        )
    )


def verify_arm_owned_evidence(
    payload: bytes, *, expected_request: ArmOwnedRequest, expected_evidence_sha256: str
) -> ArmOwnedEvidence:
    _require(
        type(expected_request) is ArmOwnedRequest, "EXACT_ARM_OWNED_REQUEST_REQUIRED"
    )
    _digest(expected_evidence_sha256)
    evidence = ArmOwnedEvidence(payload)
    _require(
        evidence.evidence_sha256 == expected_evidence_sha256
        and evidence.outer_request.payload == expected_request.payload,
        "ARM_OWNED_EVIDENCE_BINDING_MISMATCH",
    )
    return evidence
