"""Closed bridge from the feedback worker to the non-purging serial owner.

The same bridge exercises the sealed Win32 fixture and contains the prospective
native path. Native activation remains unconditionally held. This module is not
a process supervisor, identity resolver, power observer or commissioning gate.
"""

from __future__ import annotations

import base64
from copy import deepcopy
from dataclasses import asdict, dataclass
from enum import Enum
import hashlib
import json
import math
import re
from threading import RLock
from typing import Any, Callable

from rocell.application.physical_connection_contracts import EvidenceOrigin
from rocell.providers.windows.arm_feedback_worker import (
    ArmFeedbackCampaignRequest,
    ArmFeedbackCampaignResult,
    ArmFeedbackOutcome,
    ArmFeedbackWorkerError,
    INCAPABLE_COMPOSITION,
    ReviewedControllerBinding,
    SerialApiCounts,
    _settings,
    parse_arm_feedback_request,
)
from rocell.providers.windows.nonpurging_serial_api import (
    CommTimeouts,
    DcbSettings,
    IncapableWin32SerialApi,
    NATIVE_HOLD,
    NativeSerialError,
    WindowsNativeSerialApi,
    _native_release_hold,
)
from rocell.providers.windows.nonpurging_serial_backend import (
    NonPurgingSerialConnection,
)


SCHEMA = "rocell.arm_native_lifecycle_evidence.v1"
SUMMARY_SCHEMA = "rocell.arm_native_lifecycle_summary.v1"
NATIVE_COMPOSITION = "WINDOWS_NONPURGING_SERIAL_PHYSICAL_HELD"
MAX_EVIDENCE_BYTES = 32 * 1024
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,95}\Z")
_OPERATION = re.compile(r"[a-z][a-z0-9_:]{0,63}\Z")
_FINAL_POWER = "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
_ACTUAL_ZERO = {
    "device_opens": 0,
    "serial_transactions": 0,
    "robot_commands_sent": 0,
    "robot_power_operations": 0,
}


def _require(condition: bool, code: str = "INVALID_NATIVE_LIFECYCLE_EVIDENCE") -> None:
    if not condition:
        raise ArmFeedbackWorkerError(code, "non-purging adapter contract refused")


def _plain(value: Any, depth: int = 0) -> Any:
    _require(depth <= 16)
    if isinstance(value, Enum):
        return _plain(value.value, depth + 1)
    if type(value) is bytes:
        _require(len(value) <= 65537)
        return {"base64": base64.b64encode(value).decode("ascii")}
    if type(value) in (tuple, list):
        _require(len(value) <= 64)
        return [_plain(item, depth + 1) for item in value]
    if type(value) is dict:
        _require(
            len(value) <= 64 and all(type(k) is str and len(k) <= 128 for k in value)
        )
        return {key: _plain(item, depth + 1) for key, item in value.items()}
    if type(value) is str:
        _require(len(value.encode("utf-8")) <= 262144)
    elif type(value) is float:
        _require(math.isfinite(value))
    elif type(value) is int:
        _require(abs(value) <= 2**63 - 1)
    else:
        _require(value is None or type(value) is bool)
    return value


def _json(value: Any) -> bytes:
    try:
        payload = json.dumps(
            _plain(value),
            ensure_ascii=True,
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise ArmFeedbackWorkerError(
            "INVALID_NATIVE_LIFECYCLE_EVIDENCE", "invalid bounded JSON"
        ) from exc
    _require(len(payload) <= 512 * 1024)
    return payload


def _digest(value: Any) -> str:
    return hashlib.sha256(_json(value)).hexdigest()


def _int(value: Any, maximum: int = 2**63 - 1) -> None:
    _require(type(value) is int and 0 <= value <= maximum)


def _exact(value: Any, names: set[str]) -> None:
    _require(type(value) is dict and set(value) == names)


def _request_bytes(request: ArmFeedbackCampaignRequest) -> bytes:
    _require(
        type(request) is ArmFeedbackCampaignRequest, "EXACT_NATIVE_REQUEST_REQUIRED"
    )
    payload = _json(request.to_dict())
    restored = parse_arm_feedback_request(payload)
    _require(restored.to_dict() == request.to_dict(), "EXACT_NATIVE_REQUEST_REQUIRED")
    return payload


def _result_bytes(
    result: ArmFeedbackCampaignResult, request: ArmFeedbackCampaignRequest
) -> bytes:
    _require(type(result) is ArmFeedbackCampaignResult, "EXACT_NATIVE_RESULT_REQUIRED")
    _require(
        type(result.api_counts) is SerialApiCounts
        and type(result.outcome) is ArmFeedbackOutcome
    )
    _require(
        result.request_sha256 == request.request_sha256,
        "NATIVE_RESULT_REQUEST_MISMATCH",
    )
    _require(result.origin is request.controller.origin)
    _require(
        result.composition
        == (
            INCAPABLE_COMPOSITION
            if result.origin is EvidenceOrigin.SYNTHETIC_REHEARSAL
            else NATIVE_COMPOSITION
        )
    )
    for value in asdict(result.api_counts).values():
        _int(value, 65537)
    _require(
        type(result.response_bytes) is bytes and type(result.unexpected_bytes) is bytes
    )
    _require(
        len(result.response_bytes) + len(result.unexpected_bytes)
        <= request.feedback.maximum_line_bytes + 1
    )
    _int(result.unexpected_bytes_unretained, 0xFFFFFFFF)
    _require(type(result.connection_closed) is bool and len(result.cleanup_errors) <= 8)
    # Include every typed field and raw byte in the digest. The native artifact
    # is a companion to full feedback evidence, not a lossy replacement for it.
    return _json(asdict(result))


def _validate_native(
    native: Any, late: bytes, binding_sha256: str, identity_sha256: str
) -> None:
    expected = {
        "schema",
        "phase",
        "composition",
        "binding_sha256",
        "identity_sha256",
        "physical_authority",
        "physical_hold",
        "hardware_accessed_by_status",
        "arm_connected",
        "native_settings_requested",
        "native_timeouts_requested",
        "settings_readback_verified",
        "open_consumed",
        "write_consumed",
        "close_consumed",
        "api_calls",
        "resource_counts",
        "pending_io_unresolved",
        "cleanup_confirmed",
        "startup_input_observed",
        "largest_prewrite_input_bytes",
        "communication_error_mask",
        "confirmed_write_bytes",
        "retained_read_bytes",
        "read_bytes_sha256",
        "late_read_bytes",
        "late_read_sha256",
        "primary_error",
        "cleanup_errors",
        "actual_effect_counts",
        "final_power_state",
        "limitations",
    }
    _exact(native, expected)
    _require(native["schema"] == "rocell.nonpurging_serial_lifecycle.v1")
    _require(
        native["phase"]
        in {
            "CLOSED_UNOPENED",
            "OPENING",
            "OPEN",
            "FAILED",
            "CLEANUP_UNCONFIRMED",
            "CLOSED_FAILED",
            "CLOSED",
        }
    )
    _require(native["composition"] in {INCAPABLE_COMPOSITION, NATIVE_COMPOSITION})
    _require(
        native["binding_sha256"] == binding_sha256
        and native["identity_sha256"] == identity_sha256
    )
    for name in ("physical_authority", "hardware_accessed_by_status", "arm_connected"):
        _require(native[name] is False)
    for name in (
        "settings_readback_verified",
        "open_consumed",
        "write_consumed",
        "close_consumed",
        "pending_io_unresolved",
        "cleanup_confirmed",
        "startup_input_observed",
    ):
        _require(type(native[name]) is bool)
    _require(
        native["physical_hold"] == NATIVE_HOLD
        and native["final_power_state"] == _FINAL_POWER
    )
    _require(_json(native["actual_effect_counts"]) == _json(_ACTUAL_ZERO))
    _require(_json(native["native_settings_requested"]) == _json(asdict(DcbSettings())))
    _require(
        _json(native["native_timeouts_requested"]) == _json(asdict(CommTimeouts()))
    )
    calls = native["api_calls"]
    _require(
        type(calls) is dict
        and set(calls)
        <= {
            "create_file",
            "create_event",
            "get_state",
            "set_state",
            "get_timeouts",
            "set_timeouts",
            "queue_status",
            "submit_io",
            "complete_io",
            "cancel_io",
            "close_handle",
            "read_admissions",
        }
    )
    for count in calls.values():
        _int(count, 32768)
    resources = native["resource_counts"]
    _exact(resources, {"acquired", "close_attempted", "close_confirmed", "unresolved"})
    for count in resources.values():
        _int(count, 3)
    _require(
        resources["acquired"] == resources["close_confirmed"] + resources["unresolved"]
    )
    _require(
        resources["close_confirmed"]
        <= resources["close_attempted"]
        <= resources["acquired"]
    )
    _require(
        native["cleanup_confirmed"]
        is (resources["unresolved"] == 0 and not native["pending_io_unresolved"])
    )
    for name in ("largest_prewrite_input_bytes", "communication_error_mask"):
        _int(native[name], 0xFFFFFFFF)
    _int(native["confirmed_write_bytes"], 10)
    _int(native["retained_read_bytes"], 65537)
    _int(native["late_read_bytes"], 1024)
    for name in ("read_bytes_sha256", "late_read_sha256"):
        _require(
            type(native[name]) is str and _HASH.fullmatch(native[name]) is not None
        )
    _require(
        native["late_read_bytes"] == len(late)
        and native["late_read_sha256"] == hashlib.sha256(late).hexdigest()
    )
    issues = native["cleanup_errors"]
    _require(type(issues) is list and len(issues) <= 8)
    for issue in issues + (
        [] if native["primary_error"] is None else [native["primary_error"]]
    ):
        _exact(issue, {"code", "operation", "winerror"})
        _require(
            type(issue["code"]) is str and _CODE.fullmatch(issue["code"]) is not None
        )
        _require(
            type(issue["operation"]) is str
            and _OPERATION.fullmatch(issue["operation"]) is not None
        )
        _int(issue["winerror"], 0xFFFFFFFF)
    _require(type(native["limitations"]) is list and len(native["limitations"]) <= 16)
    for text in native["limitations"]:
        _require(
            type(text) is str
            and len(text.encode("utf-8")) <= 512
            and all(ord(c) >= 32 and ord(c) != 127 for c in text)
        )


@dataclass(frozen=True, slots=True)
class ArmNativeLifecycleEvidence:
    """Bounded immutable companion; full worker wire evidence is still required."""

    payload: bytes

    def __post_init__(self) -> None:
        _require(
            type(self.payload) is bytes and 0 < len(self.payload) <= MAX_EVIDENCE_BYTES
        )
        try:
            doc = json.loads(self.payload)
            _require(_json(doc) == self.payload)
        except (ValueError, UnicodeError, RecursionError) as exc:
            raise ArmFeedbackWorkerError(
                "INVALID_NATIVE_LIFECYCLE_EVIDENCE", "invalid retained JSON"
            ) from exc
        _exact(
            doc,
            {
                "schema",
                "request_sha256",
                "controller_binding_sha256",
                "identity_sha256",
                "worker_result_sha256",
                "worker_status",
                "source_sha256",
                "operation_sha256",
                "energization_envelope_sha256",
                "native",
                "late_read",
                "worker_wire",
                "physical_authority",
                "arm_connected",
                "final_power_state",
                "device_cleanup_proven",
                "retention_role",
            },
        )
        _require(doc["schema"] == SCHEMA)
        for name in (
            "request_sha256",
            "controller_binding_sha256",
            "identity_sha256",
            "worker_result_sha256",
            "source_sha256",
            "operation_sha256",
            "energization_envelope_sha256",
        ):
            _require(type(doc[name]) is str and _HASH.fullmatch(doc[name]) is not None)
        _require(
            doc["worker_status"]
            in {
                "SUCCEEDED_DIAGNOSTIC",
                "BLOCKED_PRE_OPEN",
                "CANCELLED_PRE_OPEN",
                "FAILED_UNCERTAIN",
            }
        )
        for name in ("physical_authority", "arm_connected", "device_cleanup_proven"):
            _require(doc[name] is False)
        _require(doc["final_power_state"] == _FINAL_POWER)
        _require(
            doc["retention_role"] == "NATIVE_COMPANION_REQUIRES_FULL_FEEDBACK_EVIDENCE"
        )
        _exact(doc["late_read"], {"bytes", "sha256", "base64"})
        _int(doc["late_read"]["bytes"], 1024)
        try:
            late = base64.b64decode(doc["late_read"]["base64"], validate=True)
        except (ValueError, TypeError) as exc:
            raise ArmFeedbackWorkerError(
                "INVALID_NATIVE_LIFECYCLE_EVIDENCE", "invalid late-byte encoding"
            ) from exc
        _require(
            len(late) == doc["late_read"]["bytes"]
            and base64.b64encode(late).decode("ascii") == doc["late_read"]["base64"]
            and hashlib.sha256(late).hexdigest() == doc["late_read"]["sha256"]
        )
        _exact(
            doc["worker_wire"],
            {
                "response_bytes",
                "response_sha256",
                "unexpected_bytes",
                "unexpected_sha256",
                "unexpected_bytes_unretained",
            },
        )
        for key, value in doc["worker_wire"].items():
            if key.endswith("sha256"):
                _require(type(value) is str and _HASH.fullmatch(value) is not None)
            else:
                _int(value, 0xFFFFFFFF if key.endswith("unretained") else 65537)
        if doc["native"] is None:
            _require(not late and doc["worker_status"] != "SUCCEEDED_DIAGNOSTIC")
        else:
            _validate_native(
                doc["native"],
                late,
                doc["controller_binding_sha256"],
                doc["identity_sha256"],
            )
        if doc["worker_status"] == "SUCCEEDED_DIAGNOSTIC":
            native = doc["native"]
            _require(native is not None)
            _require(
                native["phase"] == "CLOSED"
                and native["settings_readback_verified"] is True
                and native["cleanup_confirmed"] is True
                and native["pending_io_unresolved"] is False
                and native["startup_input_observed"] is False
                and native["primary_error"] is None
                and not native["cleanup_errors"]
                and native["communication_error_mask"] == 0
                and native["confirmed_write_bytes"] == 10
                and native["open_consumed"] is True
                and native["write_consumed"] is True
                and native["close_consumed"] is True
                and native["resource_counts"]
                == {
                    "acquired": 3,
                    "close_attempted": 3,
                    "close_confirmed": 3,
                    "unresolved": 0,
                }
                and native["api_calls"].get("create_file") == 1
                and native["api_calls"].get("create_event") == 2
                and native["api_calls"].get("close_handle") == 3
                and not late,
                "NATIVE_SUCCESS_PREDICATES_MISMATCH",
            )

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload)  # type: ignore[no-any-return]

    def view(self) -> dict[str, Any]:
        doc = self.to_dict()
        native = doc["native"]
        return {
            "schema": SUMMARY_SCHEMA,
            "evidence_sha256": self.evidence_sha256,
            "request_sha256": doc["request_sha256"],
            "controller_binding_sha256": doc["controller_binding_sha256"],
            "worker_result_sha256": doc["worker_result_sha256"],
            "worker_status": doc["worker_status"],
            "native_cleanup_confirmed": (
                None if native is None else native["cleanup_confirmed"]
            ),
            "resource_counts": None if native is None else native["resource_counts"],
            "pending_io_unresolved": (
                None if native is None else native["pending_io_unresolved"]
            ),
            "startup_input_observed": (
                None if native is None else native["startup_input_observed"]
            ),
            "native_primary_error": None if native is None else native["primary_error"],
            "native_cleanup_errors": [] if native is None else native["cleanup_errors"],
            "late_read_bytes": doc["late_read"]["bytes"],
            "late_read_sha256": doc["late_read"]["sha256"],
            "physical_authority": False,
            "arm_connected": False,
            "device_cleanup_proven": False,
            "final_power_state": _FINAL_POWER,
            "physical_hold": NATIVE_HOLD,
            "meaning": "Native API cleanup is separate from process cleanup and final power. Full feedback evidence remains required; this companion grants no authority.",
        }


def verify_arm_native_lifecycle_evidence(
    payload: bytes,
    *,
    expected_request: ArmFeedbackCampaignRequest,
    expected_result: ArmFeedbackCampaignResult,
    expected_evidence_sha256: str,
) -> ArmNativeLifecycleEvidence:
    """Pure expected-input verification, never replay, device I/O or publication."""
    _request_bytes(expected_request)
    result_bytes = _result_bytes(expected_result, expected_request)
    artifact = ArmNativeLifecycleEvidence(payload)
    _require(
        artifact.evidence_sha256 == expected_evidence_sha256,
        "NATIVE_EVIDENCE_HASH_MISMATCH",
    )
    doc = artifact.to_dict()
    _require(
        doc["request_sha256"] == expected_request.request_sha256
        and doc["worker_result_sha256"] == hashlib.sha256(result_bytes).hexdigest(),
        "NATIVE_EVIDENCE_BINDING_MISMATCH",
    )
    for name, expected in _binding_fields(expected_request, expected_result).items():
        _require(
            _json(doc[name]) == _json(expected), "NATIVE_EVIDENCE_BINDING_MISMATCH"
        )
    native = doc["native"]
    if native is None:
        _require(
            expected_result.api_counts.object_creations == 0
            and expected_result.api_counts.open_attempts == 0
            and expected_result.api_counts.write_attempts == 0
            and expected_result.api_counts.read_attempts == 0
            and expected_result.connection_closed is False
            and not expected_result.response_bytes
            and not expected_result.unexpected_bytes,
            "NATIVE_RESOURCE_EVIDENCE_MISSING",
        )
    else:
        late = base64.b64decode(doc["late_read"]["base64"], validate=True)
        all_read_bytes = (
            expected_result.response_bytes + expected_result.unexpected_bytes + late
        )
        _require(
            native["composition"] == expected_result.composition
            and native["retained_read_bytes"] == len(all_read_bytes)
            and native["read_bytes_sha256"]
            == hashlib.sha256(all_read_bytes).hexdigest(),
            "NATIVE_READ_EVIDENCE_MISMATCH",
        )
        _require(
            expected_result.connection_closed is native["cleanup_confirmed"],
            "NATIVE_CLEANUP_EVIDENCE_MISMATCH",
        )
        if doc["worker_status"] == "SUCCEEDED_DIAGNOSTIC":
            counts = expected_result.api_counts
            _require(
                expected_result.feedback_receipt is not None
                and expected_result.primary_error is None
                and not expected_result.cleanup_errors
                and counts.object_creations
                == counts.open_attempts
                == counts.opens_confirmed
                == 1
                and counts.write_attempts == counts.writes_confirmed == 1
                and counts.write_bytes_confirmed == 10
                and counts.close_attempts == counts.closes_confirmed == 1
                and counts.read_attempts == native["api_calls"].get("read_admissions"),
                "NATIVE_SUCCESS_PREDICATES_MISMATCH",
            )
    return artifact


def _binding_fields(
    request: ArmFeedbackCampaignRequest, result: ArmFeedbackCampaignResult
) -> dict[str, Any]:
    return {
        "request_sha256": request.request_sha256,
        "controller_binding_sha256": request.controller.binding_sha256,
        "identity_sha256": request.controller.identity.identity_sha256,
        "worker_result_sha256": hashlib.sha256(
            _result_bytes(result, request)
        ).hexdigest(),
        "worker_status": result.outcome.value,
        "source_sha256": request.source_sha256,
        "operation_sha256": request.operation_sha256,
        "energization_envelope_sha256": request.energization_envelope_sha256,
        "worker_wire": {
            "response_bytes": len(result.response_bytes),
            "response_sha256": hashlib.sha256(result.response_bytes).hexdigest(),
            "unexpected_bytes": len(result.unexpected_bytes),
            "unexpected_sha256": hashlib.sha256(result.unexpected_bytes).hexdigest(),
            "unexpected_bytes_unretained": result.unexpected_bytes_unretained,
        },
    }


class _ClosedFeedbackConnection:
    """Worker-compatible fixed settings; no serial-for-URL or raw options."""

    __slots__ = (
        "_owner",
        "_expected",
        "_assigned",
        "_timeout",
        "_open_requested",
        "_check",
    )

    def __init__(
        self, binding: ReviewedControllerBinding, api: Any, check: Callable[[], None]
    ) -> None:
        object.__setattr__(self, "_check", check)
        object.__setattr__(self, "_owner", NonPurgingSerialConnection(binding, api=api))
        object.__setattr__(
            self, "_expected", {"port": binding.identity.port_name, **_settings()}
        )
        object.__setattr__(self, "_assigned", set())
        object.__setattr__(self, "_timeout", 1.0)
        object.__setattr__(self, "_open_requested", False)

    def __getattr__(self, name: str) -> Any:
        if name in self._expected:
            return self._timeout if name == "timeout" else self._expected[name]
        raise AttributeError(name)

    def __setattr__(self, name: str, value: Any) -> None:
        _require(name in self._expected, "UNREGISTERED_SERIAL_SETTING")
        if name == "timeout":
            _require(
                type(value) is float and math.isfinite(value) and 0.001 <= value <= 1.0,
                "READ_DEADLINE_TOO_SHORT_OR_INVALID",
            )
            _require(
                self._open_requested or value == 1.0, "FIXED_SERIAL_SETTINGS_REQUIRED"
            )
            object.__setattr__(self, "_timeout", value)
        else:
            _require(
                not self._open_requested
                and type(value) is type(self._expected[name])
                and value == self._expected[name],
                "FIXED_SERIAL_SETTINGS_REQUIRED",
            )
        self._assigned.add(name)

    @property
    def is_open(self) -> bool:
        return self._owner.is_open

    @property
    def in_waiting(self) -> int:
        self._check()
        return self._owner.in_waiting

    def open(self) -> None:
        self._check()
        _require(
            self._assigned == set(self._expected) and not self._open_requested,
            "CLOSED_SETTINGS_NOT_COMPLETE",
        )
        object.__setattr__(self, "_open_requested", True)
        self._owner.open()

    def read(self, size: int) -> bytes:
        self._check()
        # Floor, never round up: if less than one native millisecond remains,
        # refuse without submitting I/O. Cancellation completion is separately
        # bounded by the owner and cannot retroactively make a deadline pass.
        milliseconds = int(self._timeout * 1000)
        _require(1 <= milliseconds <= 1000, "READ_DEADLINE_TOO_SHORT_OR_INVALID")
        return self._owner.read(size, timeout_ms=milliseconds)

    def write(self, payload: bytes) -> int:
        self._check()
        try:
            return self._owner.write(payload)
        except NativeSerialError as exc:
            if exc.code == "SHORT_WRITE_NO_RETRY":
                # Preserve the native API's partial count in the existing
                # worker receipt; the worker rejects it and never resubmits.
                return int(self._owner.status()["confirmed_write_bytes"])
            raise

    def close(self) -> None:
        self._owner.close()  # Raises even if only an event/pending I/O remains.


class NonPurgingArmFeedbackBackend:
    """One bound worker/connection; exact native facade stays release-held."""

    def __init__(
        self,
        binding: ReviewedControllerBinding,
        *,
        api: IncapableWin32SerialApi | WindowsNativeSerialApi | None = None,
    ) -> None:
        _require(
            type(binding) is ReviewedControllerBinding, "REVIEWED_BINDING_REQUIRED"
        )
        _require(
            api is None
            or type(api) in (IncapableWin32SerialApi, WindowsNativeSerialApi),
            "UNREGISTERED_NATIVE_API",
        )
        incapable = type(api) is IncapableWin32SerialApi
        self.origin = (
            EvidenceOrigin.SYNTHETIC_REHEARSAL
            if incapable
            else EvidenceOrigin.PHYSICAL_OBSERVATION
        )
        _require(binding.origin is self.origin, "PROVENANCE_MISMATCH")
        self.composition = INCAPABLE_COMPOSITION if incapable else NATIVE_COMPOSITION
        self._binding = deepcopy(binding)
        self._binding_bytes = _json(binding.to_dict())
        self._api = WindowsNativeSerialApi() if api is None else api
        self._lock = RLock()
        self._request: bytes | None = None
        self._request_object: ArmFeedbackCampaignRequest | None = None
        self._admission_consumed = False
        self._connection: _ClosedFeedbackConnection | None = None
        self._creation_consumed = False
        self._result: ArmFeedbackCampaignResult | None = None
        self._result_bytes: bytes | None = None
        self._artifact: ArmNativeLifecycleEvidence | None = None

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "composition": self.composition,
                "origin": self.origin.value,
                "binding_sha256": self._binding.binding_sha256,
                "request_bound": self._request is not None,
                "admission_consumed": self._admission_consumed,
                "connection_creation_consumed": self._creation_consumed,
                "result_retained_in_memory": self._artifact is not None,
                "physical_hold": NATIVE_HOLD,
                "physical_authority": False,
                "hardware_accessed_by_status": False,
                "arm_connected": False,
            }

    def require_available(self) -> None:
        if type(self._api) is WindowsNativeSerialApi:
            try:
                _native_release_hold()
            except NativeSerialError as exc:
                raise ArmFeedbackWorkerError(
                    exc.code, "native qualification is held"
                ) from exc

    def _bind_request(self, request: ArmFeedbackCampaignRequest) -> None:
        """Called only by the exact registered worker before backend admission."""
        with self._lock:
            _require(not self._admission_consumed, "NATIVE_BACKEND_ALREADY_USED")
            self._admission_consumed = True
            payload = _request_bytes(request)
            _require(
                self._request is None and not self._creation_consumed,
                "NATIVE_BACKEND_ALREADY_USED",
            )
            _require(
                _json(request.controller.to_dict()) == self._binding_bytes
                and _json(self._binding.to_dict()) == self._binding_bytes,
                "NATIVE_CONTROLLER_BINDING_MISMATCH",
            )
            self._request = payload
            self._request_object = request

    def _check_request(self) -> None:
        with self._lock:
            _require(
                self._request_object is not None
                # Full typed reconstruction is done once at admission. Exact
                # canonical comparison is enough on this high-frequency path
                # to detect any later field mutation before native access.
                and self._request == _json(self._request_object.to_dict())
                and _json(self._binding.to_dict()) == self._binding_bytes,
                "NATIVE_REQUEST_CHANGED_AFTER_ADMISSION",
            )

    def create_closed(self) -> _ClosedFeedbackConnection:
        with self._lock:
            _require(
                self._request is not None
                and not self._creation_consumed
                and self._result is None,
                "NATIVE_BACKEND_NOT_ADMITTED_OR_USED",
            )
            self._creation_consumed = True
            self._check_request()
            self.require_available()
            self._connection = _ClosedFeedbackConnection(
                self._binding, self._api, self._check_request
            )
            return self._connection

    def _complete_result(
        self, request: ArmFeedbackCampaignRequest, result: ArmFeedbackCampaignResult
    ) -> None:
        """Seal a copy after the actual worker's finally/close path, with no I/O."""
        with self._lock:
            _require(
                self._request == _request_bytes(request) and self._result is None,
                "NATIVE_RESULT_NOT_FROM_BOUND_EXECUTION",
            )
            result_bytes = _result_bytes(result, request)
            native = (
                None if self._connection is None else self._connection._owner.status()
            )
            late = (
                b""
                if self._connection is None
                else self._connection._owner.late_read_bytes
            )
            payload = _json(
                {
                    "schema": SCHEMA,
                    **_binding_fields(request, result),
                    "native": native,
                    "late_read": {
                        "bytes": len(late),
                        "sha256": hashlib.sha256(late).hexdigest(),
                        "base64": base64.b64encode(late).decode("ascii"),
                    },
                    "physical_authority": False,
                    "arm_connected": False,
                    "device_cleanup_proven": False,
                    "final_power_state": _FINAL_POWER,
                    "retention_role": "NATIVE_COMPANION_REQUIRES_FULL_FEEDBACK_EVIDENCE",
                }
            )
            self._artifact = ArmNativeLifecycleEvidence(payload)
            self._result, self._result_bytes = result, result_bytes

    def retain_evidence(
        self, request: ArmFeedbackCampaignRequest, result: ArmFeedbackCampaignResult
    ) -> ArmNativeLifecycleEvidence:
        with self._lock:
            _require(
                self._artifact is not None
                and self._result is result
                and self._request == _request_bytes(request)
                and self._result_bytes == _result_bytes(result, request),
                "NATIVE_RESULT_NOT_FROM_BOUND_EXECUTION",
            )
            assert self._artifact is not None
            if self._connection is not None:
                _require(
                    _json(self._connection._owner.status())
                    == _json(self._artifact.to_dict()["native"]),
                    "NATIVE_LIFECYCLE_CHANGED_AFTER_RESULT",
                )
                _require(
                    hashlib.sha256(self._connection._owner.late_read_bytes).hexdigest()
                    == self._artifact.to_dict()["late_read"]["sha256"],
                    "NATIVE_LIFECYCLE_CHANGED_AFTER_RESULT",
                )
            return verify_arm_native_lifecycle_evidence(
                self._artifact.payload,
                expected_request=request,
                expected_result=result,
                expected_evidence_sha256=self._artifact.evidence_sha256,
            )
