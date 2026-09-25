"""Lossless private arm-feedback evidence, not a worker or an admission API.

Both entry points are pure: no source reads, device operations, worker replay,
or publication. The caller owns durable retention and authenticated expected
hashes. ``to_dict`` contains wire bytes; only ``safe_summary`` belongs in the UI.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass
import hashlib
import json
import math
import re
from typing import Any

from rocell.application.physical_connection_contracts import (
    EvidenceOrigin,
    SingleT105FeedbackReceipt,
    T105TransactionTiming,
    canonical_sha256,
)
from rocell.arm.feedback import parse_feedback_1051
from rocell.arm.feedback_wire import validate_feedback_response_line
from rocell.arm.protocol import encode_line, feedback_request
from rocell.providers.windows.arm_feedback_worker import (
    ArmFeedbackCampaignRequest,
    ArmFeedbackCampaignResult,
    ArmFeedbackOutcome,
    ArmFeedbackWorkerError,
    SerialApiCounts,
    SerialLifecycleError,
    INCAPABLE_COMPOSITION,
    MAX_LINE_BYTES,
    PINNED_SDK_COMMIT,
    PINNED_FIRMWARE_ARCHIVE_SHA256,
    parse_arm_feedback_request,
)


SCHEMA = "rocell.rehearsal_arm_feedback_evidence.v1"
SUMMARY_SCHEMA = "rocell.rehearsal_arm_feedback_summary.v1"
MAX_EVIDENCE_BYTES = 256 * 1024
MAX_WIRE_BYTES = MAX_LINE_BYTES + 1
MAX_CLEANUP_ERRORS = 8
_MAX_INT = (1 << 63) - 1
_HASH = re.compile(r"[0-9a-f]{64}")
_ERROR_CODE = re.compile(r"[A-Z][A-Z0-9_]{0,95}")
_TYPE = re.compile(r"[A-Za-z_][A-Za-z0-9_]{0,95}")
_PHASES = {
    "ADMISSION",
    "IDENTITY_BEFORE_OPEN",
    "CONFIGURING_CLOSED",
    "OPENING",
    "QUIET_BUFFER_OBSERVATION",
    "IDENTITY_BEFORE_WRITE",
    "ONE_T105_WRITE",
    "ONE_T1051_RESPONSE",
    "RESPONSE_VALIDATED",
    "CLOSING",
    "COMPLETION",
}
_WIRE = encode_line(feedback_request())
_RESULT_FIELDS = set(ArmFeedbackCampaignResult.__dataclass_fields__)
_COUNT_FIELDS = set(SerialApiCounts.__dataclass_fields__)
_RECEIPT_FIELDS = set(SingleT105FeedbackReceipt.__dataclass_fields__)
_TIMING_FIELDS = set(T105TransactionTiming.__dataclass_fields__)
_AUTHORITY = {
    "composition": INCAPABLE_COMPOSITION,
    "physical_authority": False,
    "hardware_accessed_by_retention": False,
    "worker_replayed": False,
    "arm_connected": False,
    "stage_advance_authority": False,
    "physical_release_effect": "NONE",
}
_PROVENANCE = {
    "source_sha256_role": "WORKSPACE_SOURCE_NOT_EVALUATOR_FILE_HASH",
    "binding_sha256_role": "CALLER_RETAINED_EXACT_CAMPAIGN_CONTEXT",
    "wire_role": "PRIVATE_LOSSLESS_SYNTHETIC_WORKER_BYTES_NOT_UI_TEXT",
    "timing_basis": "HOST_READ_COMPLETION_NOT_DEVICE_TIMESTAMP",
    "failure_timing_scope": "ONLY_TIMES_RETURNED_BY_WORKER_NO_MISSING_TIMES_INVENTED",
    "firmware_identity": "NOT_PROVEN_BY_PACKET",
    "physical_activation": "HELD",
}


class RehearsalArmFeedbackEvidenceError(ValueError):
    """The bounded retained record is malformed, inconsistent or misbound."""


def _require(condition: bool, detail: str) -> None:
    if not condition:
        raise RehearsalArmFeedbackEvidenceError(detail)


def _object(value: object, fields: set[str] | None = None) -> dict[str, Any]:
    _require(type(value) is dict, "expected an exact JSON object")
    assert isinstance(value, dict)
    _require(fields is None or set(value) == fields, "missing or unknown fields")
    return value


def _digest(value: object) -> str:
    _require(
        type(value) is str and _HASH.fullmatch(value) is not None and value != "0" * 64,
        "expected a nonzero lowercase SHA-256",
    )
    assert isinstance(value, str)
    return value


def _integer(value: object, maximum: int = _MAX_INT) -> int:
    _require(
        type(value) is int and 0 <= value <= maximum, "integer outside its exact bound"
    )
    assert isinstance(value, int)
    return value


def _boolean(value: object) -> bool:
    _require(type(value) is bool, "expected an exact Boolean")
    assert isinstance(value, bool)
    return value


def _tree(value: object, depth: int = 0) -> None:
    _require(depth <= 18, "JSON nesting exceeds bound")
    if type(value) is dict:
        _require(
            len(value) <= 64
            and all(type(key) is str and len(key) <= 128 for key in value),
            "invalid JSON keys/count",
        )
        for item in value.values():
            _tree(item, depth + 1)
    elif type(value) is list:
        _require(len(value) <= 64, "JSON array exceeds bound")
        for item in value:
            _tree(item, depth + 1)
    elif type(value) is str:
        _require(len(value) <= MAX_EVIDENCE_BYTES, "JSON string exceeds bound")
    elif type(value) is int:
        _require(abs(value) <= _MAX_INT, "JSON integer exceeds bound")
    elif type(value) is float:
        _require(math.isfinite(value), "nonfinite number")
    else:
        _require(value is None or type(value) is bool, "non-JSON value")


def _canonical(value: object) -> bytes:
    _tree(value)
    try:
        payload = json.dumps(
            value,
            ensure_ascii=False,
            allow_nan=False,
            sort_keys=True,
            separators=(",", ":"),
        ).encode("utf-8")
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise RehearsalArmFeedbackEvidenceError("invalid JSON encoding") from exc
    _require(
        len(payload) <= MAX_EVIDENCE_BYTES, "evidence exceeds 256 KiB; never truncate"
    )
    return payload


def _same(left: object, right: object, label: str) -> None:
    _require(_canonical(left) == _canonical(right), f"{label} mismatch")


def _unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        _require(key not in result, "duplicate JSON key")
        result[key] = value
    return result


def _nonfinite(value: str) -> None:
    raise RehearsalArmFeedbackEvidenceError("nonfinite JSON constant")


def _decode(payload: bytes) -> dict[str, Any]:
    _require(
        type(payload) is bytes and 0 < len(payload) <= MAX_EVIDENCE_BYTES,
        "expected nonempty bounded evidence bytes",
    )
    try:
        value = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=_unique,
            parse_constant=_nonfinite,
        )
        _tree(value)
        return _object(value)
    except (ValueError, UnicodeError, RecursionError) as exc:
        raise RehearsalArmFeedbackEvidenceError("invalid bounded JSON") from exc


def _wire(value: bytes) -> dict[str, Any]:
    _require(
        type(value) is bytes and len(value) <= MAX_WIRE_BYTES, "wire bytes exceed bound"
    )
    return {
        "encoding": "hex",
        "bytes_hex": value.hex(),
        "retained_bytes": len(value),
        "sha256": hashlib.sha256(value).hexdigest(),
    }


def _parse_wire(value: object) -> bytes:
    obj = _object(value, {"encoding", "bytes_hex", "retained_bytes", "sha256"})
    count = _integer(obj["retained_bytes"], MAX_WIRE_BYTES)
    hex_value = obj["bytes_hex"]
    _require(
        type(hex_value) is str
        and len(hex_value) == count * 2
        and re.fullmatch(r"[0-9a-f]*", hex_value) is not None,
        "invalid bounded canonical wire hex",
    )
    decoded = bytes.fromhex(hex_value)
    _same(obj, _wire(decoded), "wire encoding/length/hash")
    return decoded


def _error(value: object) -> SerialLifecycleError | None:
    if value is None:
        return None
    obj = _object(value, {"code", "phase", "error_type"})
    _require(
        type(obj["code"]) is str and _ERROR_CODE.fullmatch(obj["code"]) is not None,
        "invalid bounded lifecycle code",
    )
    _require(
        type(obj["phase"]) is str and obj["phase"] in _PHASES, "unknown lifecycle phase"
    )
    _require(
        type(obj["error_type"]) is str
        and _TYPE.fullmatch(obj["error_type"]) is not None,
        "invalid bounded error type",
    )
    return SerialLifecycleError(**obj)


def _receipt_document(
    receipt: SingleT105FeedbackReceipt | None,
) -> dict[str, Any] | None:
    if receipt is None:
        return None
    _require(
        type(receipt) is SingleT105FeedbackReceipt,
        "expected exact feedback receipt type",
    )
    _require(
        type(receipt.request_bytes) is bytes and receipt.request_bytes == _WIRE,
        "receipt request must be the bounded fixed line",
    )
    _require(
        type(receipt.response_bytes) is bytes
        and len(receipt.response_bytes) <= MAX_LINE_BYTES,
        "receipt response exceeds byte bound",
    )
    _require(
        type(receipt.timing) is T105TransactionTiming,
        "expected exact transaction timing",
    )
    document = receipt.to_dict()
    # Deduplicate bytes without losing the complete receipt: the referenced
    # request line/response are reconstructed and validated against its hashes.
    del document["request_bytes_hex"], document["response_bytes_hex"]
    document["wire_references"] = {
        "request": "request.wire_request_hex",
        "response": "result.response_bytes",
    }
    document["receipt_sha256"] = receipt.receipt_sha256
    return document


def _request_document(request: ArmFeedbackCampaignRequest) -> dict[str, Any]:
    document = request.to_dict()
    # The existing typed request retains a str Enum in asdict(); convert that
    # one declared field explicitly, not arbitrary objects through a JSON hook.
    document["controller"]["origin"] = request.controller.origin.value
    return document


def _parse_receipt(
    value: object, request: ArmFeedbackCampaignRequest, response: bytes
) -> SingleT105FeedbackReceipt | None:
    if value is None:
        return None
    obj = _object(
        value,
        (_RECEIPT_FIELDS - {"request_bytes", "response_bytes"})
        | {"wire_references", "receipt_sha256"},
    )
    _same(
        obj["wire_references"],
        {"request": "request.wire_request_hex", "response": "result.response_bytes"},
        "receipt byte references",
    )
    timing = _object(obj["timing"], _TIMING_FIELDS)
    for field, moment in timing.items():
        _require(_integer(moment) > 0, f"invalid {field}")
    for field in (
        "pre_request_bytes_waiting",
        "post_response_bytes_waiting",
        "write_attempts",
        "feedback_query_count",
        "retry_count",
        "t104_motion_count",
    ):
        _integer(obj[field])
    _boolean(obj["connection_closed"])
    fields = {
        key: item
        for key, item in obj.items()
        if key not in {"schema", "wire_references", "receipt_sha256", "timing"}
    }
    restored = SingleT105FeedbackReceipt(
        **fields,
        timing=T105TransactionTiming(**timing),
        request_bytes=_WIRE,
        response_bytes=response,
    )
    _same(obj, _receipt_document(restored), "complete feedback receipt")
    _same(restored.run_id, request.feedback.run_id, "receipt run")
    _same(
        restored.request_context_sha256,
        request.feedback.request_context_sha256,
        "receipt request context",
    )
    _same(
        restored.arm_identity_sha256,
        request.controller.identity.identity_sha256,
        "receipt controller",
    )
    _same(
        restored.controller_session_id,
        request.feedback.controller_session_id,
        "controller session",
    )
    descriptor = canonical_sha256(
        {
            "composition": INCAPABLE_COMPOSITION,
            "sdk_commit": PINNED_SDK_COMMIT,
            "firmware_archive_sha256": PINNED_FIRMWARE_ARCHIVE_SHA256,
        }
    )
    _same(
        restored.provider_descriptor_sha256, descriptor, "incapable provider descriptor"
    )
    _require(
        request.feedback.requested_monotonic_ns
        <= timing["port_opened_monotonic_ns"]
        <= timing["port_closed_monotonic_ns"]
        < request.expires_monotonic_ns,
        "receipt times outside exact request lifetime",
    )
    _require(
        timing["pre_request_buffer_observed_monotonic_ns"]
        - timing["port_opened_monotonic_ns"]
        >= request.budget.quiet_interval_ms * 1_000_000,
        "quiet interval incomplete",
    )
    return restored


def _result_document(result: ArmFeedbackCampaignResult) -> dict[str, Any]:
    _require(
        type(result) is ArmFeedbackCampaignResult, "expected exact worker result type"
    )
    _require(type(result.api_counts) is SerialApiCounts, "expected exact counter type")
    _require(
        type(result.cleanup_errors) is tuple
        and len(result.cleanup_errors) <= MAX_CLEANUP_ERRORS,
        "cleanup errors must be immutable and bounded",
    )
    _require(
        result.primary_error is None
        or type(result.primary_error) is SerialLifecycleError,
        "expected exact primary error type",
    )
    _require(
        all(type(error) is SerialLifecycleError for error in result.cleanup_errors),
        "expected exact cleanup error types",
    )
    _require(
        type(result.origin) is EvidenceOrigin
        and type(result.outcome) is ArmFeedbackOutcome,
        "expected exact result enums",
    )
    for settings in (result.settings_before_open, result.settings_after_open):
        _require(
            type(settings) is tuple
            and len(settings) <= 14
            and all(type(pair) is tuple and len(pair) == 2 for pair in settings),
            "settings must retain immutable ordered pairs",
        )
    return {
        "request_sha256": result.request_sha256,
        "origin": result.origin.value,
        "composition": result.composition,
        "outcome": result.outcome.value,
        "api_counts": asdict(result.api_counts),
        "primary_error": asdict(result.primary_error) if result.primary_error else None,
        "cleanup_errors": [asdict(error) for error in result.cleanup_errors],
        "feedback_receipt": _receipt_document(result.feedback_receipt),
        "response_bytes": _wire(result.response_bytes),
        "unexpected_bytes": _wire(result.unexpected_bytes),
        "unexpected_bytes_unretained": result.unexpected_bytes_unretained,
        "opened_monotonic_ns": result.opened_monotonic_ns,
        "closed_monotonic_ns": result.closed_monotonic_ns,
        "elapsed_ns": result.elapsed_ns,
        "connection_closed": result.connection_closed,
        "settings_before_open": [list(pair) for pair in result.settings_before_open],
        "settings_after_open": [list(pair) for pair in result.settings_after_open],
        "write_api_returned_count": result.write_api_returned_count,
    }


def _parse_result(
    value: object, request: ArmFeedbackCampaignRequest
) -> ArmFeedbackCampaignResult:
    obj = _object(value, _RESULT_FIELDS)
    _same(obj["request_sha256"], request.request_sha256, "worker request digest")
    _same(
        obj["origin"],
        EvidenceOrigin.SYNTHETIC_REHEARSAL.value,
        "synthetic result origin",
    )
    _same(obj["composition"], INCAPABLE_COMPOSITION, "incapable result composition")
    outcome = ArmFeedbackOutcome(obj["outcome"])
    counts = _object(obj["api_counts"], _COUNT_FIELDS)
    limits = {name: 1 for name in _COUNT_FIELDS}
    limits.update(
        identity_checks=2,
        write_bytes_confirmed=len(_WIRE),
        read_attempts=request.budget.maximum_read_calls,
        read_bytes_retained=MAX_WIRE_BYTES,
    )
    for name, limit in limits.items():
        _integer(counts[name], limit)
    for lesser, greater in (
        ("opens_confirmed", "open_attempts"),
        ("open_attempts", "object_creations"),
        ("unexpected_open_objects", "object_creations"),
        ("write_attempts", "opens_confirmed"),
        ("writes_confirmed", "write_attempts"),
        ("close_attempts", "object_creations"),
        ("closes_confirmed", "close_attempts"),
    ):
        _require(counts[lesser] <= counts[greater], "inconsistent lifecycle counts")
    _require(
        counts["open_attempts"] + counts["unexpected_open_objects"] <= 1,
        "two open paths claimed",
    )
    if counts["open_attempts"]:
        _require(counts["identity_checks"] >= 1, "open lacks identity check")
    if counts["object_creations"]:
        _require(counts["identity_checks"] >= 1, "object creation lacks identity check")
    if counts["read_attempts"]:
        _require(counts["opens_confirmed"] == 1, "read lacks confirmed open")
    if counts["write_attempts"]:
        _require(counts["identity_checks"] == 2, "write lacks second identity check")
    response, unexpected = _parse_wire(obj["response_bytes"]), _parse_wire(
        obj["unexpected_bytes"]
    )
    retained = len(response) + len(unexpected)
    _require(
        retained <= request.feedback.maximum_line_bytes + 1,
        "wire prefix exceeds request bound",
    )
    _require(retained == counts["read_bytes_retained"], "wire read accounting mismatch")
    _require(not retained or counts["read_attempts"] > 0, "retained bytes without read")
    _require(
        not response or counts["writes_confirmed"] == 1,
        "response precedes confirmed request write",
    )
    omitted = _integer(obj["unexpected_bytes_unretained"])
    _require(
        len(unexpected) + omitted <= _MAX_INT, "unexpected observation count overflow"
    )
    returned = obj["write_api_returned_count"]
    if returned is not None:
        _integer(returned, MAX_LINE_BYTES)
        _require(counts["write_attempts"] == 1, "write API count without attempt")
    _require(
        counts["write_bytes_confirmed"]
        == (returned if returned is not None and returned <= len(_WIRE) else 0),
        "confirmed write-byte accounting mismatch",
    )
    _require(
        counts["writes_confirmed"] == int(returned == len(_WIRE)),
        "confirmed write count mismatch",
    )
    primary = _error(obj["primary_error"])
    cleanup_values = obj["cleanup_errors"]
    _require(
        type(cleanup_values) is list and len(cleanup_values) <= MAX_CLEANUP_ERRORS,
        "cleanup diagnostics exceed bound",
    )
    cleanup_list: list[SerialLifecycleError] = []
    for value in cleanup_values:
        issue = _error(value)
        if issue is None:
            raise RehearsalArmFeedbackEvidenceError("null cleanup issue")
        cleanup_list.append(issue)
    cleanup = tuple(cleanup_list)
    closed = _boolean(obj["connection_closed"])
    _require(closed == (counts["closes_confirmed"] == 1), "close confirmation mismatch")
    elapsed = _integer(obj["elapsed_ns"])
    opened, ended = obj["opened_monotonic_ns"], obj["closed_monotonic_ns"]
    for moment in (opened, ended):
        if moment is not None:
            _require(_integer(moment) > 0, "invalid lifecycle timestamp")
            _require(
                moment >= request.feedback.requested_monotonic_ns,
                "lifecycle time precedes request",
            )
    _require(
        opened is None or counts["opens_confirmed"] == 1,
        "open time without confirmed open",
    )
    _require(ended is None or closed, "close time without confirmed close")
    if opened is not None and ended is not None:
        _require(
            0 <= ended - opened <= elapsed, "lifecycle timing order/duration mismatch"
        )
    settings = []
    expected_pairs = [
        list(pair)
        for pair in {
            "port": request.controller.identity.port_name,
            **request.to_dict()["serial_settings"],
        }.items()
    ]
    for field in ("settings_before_open", "settings_after_open"):
        values = obj[field]
        _require(type(values) is list, "settings must be arrays of exact pairs")
        if values:
            _same(values, expected_pairs, "complete settings readback")
        settings.append(tuple(tuple(pair) for pair in values))
    _require(
        not settings[0] or counts["object_creations"] == 1,
        "pre-open readback lacks created object",
    )
    _require(
        not settings[1] or counts["opens_confirmed"] == 1 and opened is not None,
        "post-open readback lacks confirmed timed open",
    )
    _require(
        not counts["open_attempts"] or bool(settings[0]), "open lacks pre-open settings"
    )
    _require(
        not counts["write_attempts"] or bool(settings[1]),
        "write lacks post-open settings",
    )
    receipt = _parse_receipt(obj["feedback_receipt"], request, response)
    expected_outcome = (
        ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC
        if primary is None and not cleanup
        else (
            ArmFeedbackOutcome.FAILED_UNCERTAIN
            if counts["open_attempts"] or counts["unexpected_open_objects"]
            else (
                ArmFeedbackOutcome.CANCELLED_PRE_OPEN
                if primary is not None and primary.code == "CANCELLED"
                else ArmFeedbackOutcome.BLOCKED_PRE_OPEN
            )
        )
    )
    _require(
        outcome is expected_outcome, "worker outcome contradicts retained lifecycle"
    )
    if outcome is ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC:
        _require(
            receipt is not None and closed and opened is not None and ended is not None,
            "successful diagnostic lacks complete closed transaction",
        )
        assert receipt is not None
        _require(
            counts["open_attempts"]
            == counts["opens_confirmed"]
            == counts["write_attempts"]
            == counts["writes_confirmed"]
            == counts["close_attempts"]
            == counts["closes_confirmed"]
            == 1,
            "successful diagnostic lifecycle counts differ",
        )
        _require(
            not unexpected and omitted == 0,
            "successful diagnostic has unexpected bytes",
        )
        _require(
            len(response) <= request.feedback.maximum_line_bytes,
            "successful response exceeds exact request line limit",
        )
        _require(
            elapsed < request.budget.duration_ms * 1_000_000,
            "successful diagnostic exceeded duration",
        )
        _require(
            receipt.timing.port_opened_monotonic_ns == opened
            and receipt.timing.port_closed_monotonic_ns == ended,
            "receipt/result timing mismatch",
        )
    else:
        _require(
            receipt is None,
            "failed campaign must not retain a successful transaction receipt",
        )
    restored = ArmFeedbackCampaignResult(
        request.request_sha256,
        EvidenceOrigin.SYNTHETIC_REHEARSAL,
        INCAPABLE_COMPOSITION,
        outcome,
        SerialApiCounts(**counts),
        primary,
        cleanup,
        receipt,
        response,
        unexpected,
        omitted,
        opened,
        ended,
        elapsed,
        closed,
        settings[0],
        settings[1],
        returned,
    )
    _same(obj, _result_document(restored), "lossless result round trip")
    return restored


def _summary(
    request: ArmFeedbackCampaignRequest,
    result: ArmFeedbackCampaignResult,
    binding_sha256: str,
) -> dict[str, Any]:
    technical = False
    try:
        parsed = validate_feedback_response_line(
            result.response_bytes, max_line_bytes=request.feedback.maximum_line_bytes
        )
        parse_feedback_1051(parsed)
        technical = True
    except (ValueError, TypeError, OverflowError, RecursionError):
        pass
    return {
        "schema": SUMMARY_SCHEMA,
        "binding_sha256": binding_sha256,
        "source_sha256": request.source_sha256,
        "request_sha256": request.request_sha256,
        "controller_binding_sha256": request.controller.binding_sha256,
        "worker_outcome": result.outcome.value,
        "technical_response_valid": technical,
        "feedback_receipt_valid": result.feedback_receipt is not None,
        "serial_cleanup_confirmed": result.connection_closed
        and not any(error.phase == "CLOSING" for error in result.cleanup_errors),
        "effect_uncertain": result.effect_uncertain,
        "api_counts": asdict(result.api_counts),
        "primary_error": asdict(result.primary_error) if result.primary_error else None,
        "cleanup_errors": [asdict(error) for error in result.cleanup_errors],
        "wire": {
            "response": {
                "sha256": hashlib.sha256(result.response_bytes).hexdigest(),
                "retained_bytes": len(result.response_bytes),
            },
            "unexpected": {
                "sha256": hashlib.sha256(result.unexpected_bytes).hexdigest(),
                "retained_bytes": len(result.unexpected_bytes),
                "unretained_bytes": result.unexpected_bytes_unretained,
            },
        },
        "timing": {
            "opened_monotonic_ns": result.opened_monotonic_ns,
            "closed_monotonic_ns": result.closed_monotonic_ns,
            "elapsed_ns": result.elapsed_ns,
            "basis": "HOST_READ_COMPLETION_NOT_DEVICE_TIMESTAMP",
            "transaction_timing_available": result.feedback_receipt is not None,
        },
        "final_power_state": "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
        "physical_authority": False,
        "arm_connected": False,
        "installed_firmware_proven_by_packet": False,
    }


@dataclass(frozen=True, slots=True)
class RehearsalArmFeedbackEvidence:
    """Immutable verified bytes; direct construction alone is not admission."""

    _payload: bytes

    @property
    def evidence_sha256(self) -> str:
        return hashlib.sha256(self._payload).hexdigest()

    def canonical_bytes(self) -> bytes:
        return self._payload

    def to_dict(self) -> dict[str, Any]:
        """Private lossless record. Never put this dictionary in ordinary logs."""
        return _decode(self._payload)

    def safe_summary(self) -> dict[str, Any]:
        return self.to_dict()["safe_summary"]  # type: ignore[no-any-return]

    @property
    def result(self) -> ArmFeedbackCampaignResult:
        document = self.to_dict()
        return _parse_result(
            document["result"],
            parse_arm_feedback_request(_canonical(document["request"])),
        )


def verify_rehearsal_arm_feedback_evidence(
    payload: bytes,
    *,
    expected_request: ArmFeedbackCampaignRequest,
    expected_binding_sha256: str,
    expected_evidence_sha256: str,
    expected_source_sha256: str,
) -> RehearsalArmFeedbackEvidence:
    """Strict pure verification against independently trusted request/context/hash.

    Source means the workspace source, not this module's hash. Caller-owned M1
    references authenticate these inputs; computing them from untrusted supplied
    JSON does not authenticate evidence. No file or worker is opened/replayed.
    """
    try:
        _require(
            type(expected_request) is ArmFeedbackCampaignRequest,
            "expected exact typed request",
        )
        _digest(expected_binding_sha256)
        _digest(expected_evidence_sha256)
        _digest(expected_source_sha256)
        document = _decode(payload)
        _object(
            document,
            {
                "schema",
                "source_sha256",
                "binding_sha256",
                "request_sha256",
                "controller_binding_sha256",
                "request",
                "result",
                "result_sha256",
                "wire_accounting",
                "safe_summary",
                "provenance",
                "authority",
            },
        )
        _same(document["schema"], SCHEMA, "schema")
        _same(document["source_sha256"], expected_source_sha256, "workspace source")
        _same(
            expected_request.source_sha256,
            expected_source_sha256,
            "request workspace source",
        )
        _same(document["binding_sha256"], expected_binding_sha256, "campaign context")
        _same(document["provenance"], _PROVENANCE, "provenance")
        _same(document["authority"], _AUTHORITY, "zero authority")
        request = parse_arm_feedback_request(_canonical(document["request"]))
        _same(
            _request_document(request),
            _request_document(expected_request),
            "exact retained request",
        )
        _same(
            request.controller.origin.value,
            EvidenceOrigin.SYNTHETIC_REHEARSAL.value,
            "incapable request origin",
        )
        _same(document["request_sha256"], request.request_sha256, "request hash")
        _same(
            document["controller_binding_sha256"],
            request.controller.binding_sha256,
            "controller binding",
        )
        result = _parse_result(document["result"], request)
        _same(
            document["result_sha256"],
            canonical_sha256(document["result"]),
            "result hash",
        )
        _same(
            document["wire_accounting"],
            _accounting(result),
            "wire prefix/omission accounting",
        )
        _same(
            document["safe_summary"],
            _summary(request, result, expected_binding_sha256),
            "safe derived summary",
        )
        canonical = _canonical(document)
        _same(
            hashlib.sha256(canonical).hexdigest(),
            expected_evidence_sha256,
            "trusted retained evidence hash",
        )
        return RehearsalArmFeedbackEvidence(canonical)
    except (
        ArmFeedbackWorkerError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        RecursionError,
    ) as exc:
        if isinstance(exc, RehearsalArmFeedbackEvidenceError):
            raise
        raise RehearsalArmFeedbackEvidenceError(
            "invalid lossless feedback evidence"
        ) from exc


def _accounting(result: ArmFeedbackCampaignResult) -> dict[str, Any]:
    return {
        "response_retained_bytes": len(result.response_bytes),
        "unexpected_retained_prefix_bytes": len(result.unexpected_bytes),
        "unexpected_unretained_observed_bytes": result.unexpected_bytes_unretained,
        "unexpected_observed_bytes": len(result.unexpected_bytes)
        + result.unexpected_bytes_unretained,
        "unexpected_retention": (
            "BOUNDED_PREFIX_WITH_OMISSIONS"
            if result.unexpected_bytes_unretained
            else "ALL_OBSERVED_UNEXPECTED_BYTES_RETAINED"
        ),
        "scope": "HOST_BUFFER_OBSERVATION_ONLY_NOT_ALL_FUTURE_DEVICE_OUTPUT",
        "raw_wire_visible_in_safe_summary": False,
    }


def retain_rehearsal_arm_feedback_evidence(
    request: ArmFeedbackCampaignRequest,
    result: ArmFeedbackCampaignResult,
    *,
    binding_sha256: str,
    source_sha256: str,
) -> RehearsalArmFeedbackEvidence:
    """Build bounded private evidence from actual worker values, without I/O.

    The caller must persist these complete bytes under its owned transaction
    before a known seal. This function cannot declare retention durable, close
    an uncertain attempt, assert power-off, or advance stage 12.
    """
    try:
        _require(
            type(request) is ArmFeedbackCampaignRequest, "expected exact typed request"
        )
        _digest(binding_sha256)
        _digest(source_sha256)
        result_document = _result_document(result)
        restored = _parse_result(result_document, request)
        document = {
            "schema": SCHEMA,
            "source_sha256": source_sha256,
            "binding_sha256": binding_sha256,
            "request_sha256": request.request_sha256,
            "controller_binding_sha256": request.controller.binding_sha256,
            "request": _request_document(request),
            "result": result_document,
            "result_sha256": canonical_sha256(result_document),
            "wire_accounting": _accounting(restored),
            "safe_summary": _summary(request, restored, binding_sha256),
            "provenance": dict(_PROVENANCE),
            "authority": dict(_AUTHORITY),
        }
        payload = _canonical(document)
        return verify_rehearsal_arm_feedback_evidence(
            payload,
            expected_request=request,
            expected_binding_sha256=binding_sha256,
            expected_evidence_sha256=hashlib.sha256(payload).hexdigest(),
            expected_source_sha256=source_sha256,
        )
    except (
        ArmFeedbackWorkerError,
        ValueError,
        TypeError,
        KeyError,
        AttributeError,
        OverflowError,
        RecursionError,
    ) as exc:
        if isinstance(exc, RehearsalArmFeedbackEvidenceError):
            raise
        raise RehearsalArmFeedbackEvidenceError(
            "invalid worker evidence input"
        ) from exc


__all__ = [
    "SCHEMA",
    "SUMMARY_SCHEMA",
    "MAX_EVIDENCE_BYTES",
    "MAX_WIRE_BYTES",
    "RehearsalArmFeedbackEvidenceError",
    "RehearsalArmFeedbackEvidence",
    "retain_rehearsal_arm_feedback_evidence",
    "verify_rehearsal_arm_feedback_evidence",
]
