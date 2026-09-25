"""Closed passive bench request codec, not an admission or dispatch capability.

Referenced originals must be independently authenticated by a future service.
Parsing a request does not verify isolation, qualify firmware, create a permit,
or make any of the currently held physical providers callable.
"""

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any


SCHEMA = "rocell.arm_passive_bench_request.v1"
PURPOSE = "USB_PASSIVE_OPEN_OBSERVE_CLOSE"
MAX_DOCUMENT_BYTES = 8192
OBSERVATION_MS = 5000
CLEANUP_MS = 2000
MAX_STARTUP_BYTES = 65536
_REFERENCE_NAMES = frozenset(
    {
        "source_sha256",
        "runtime_sha256",
        "serial_profile_sha256",
        "native_metadata_review_sha256",
        "received_unit_association_sha256",
        "electrical_isolation_review_sha256",
        "operator_attestation_sha256",
        "entry_policy_sha256",
    }
)
_FIELDS = frozenset(
    {
        "schema",
        "purpose",
        "attempt_id",
        "launch_id",
        "mode",
        "references",
        "parent_deadline_monotonic_ns",
        "limits",
    }
)
_LIMITS = {
    "maximum_open_attempts": 1,
    "maximum_observation_ms": OBSERVATION_MS,
    "maximum_cleanup_ms": CLEANUP_MS,
    "maximum_startup_bytes": MAX_STARTUP_BYTES,
    "maximum_outbound_bytes": 0,
    "maximum_retry_count": 0,
}


class BenchContractError(ValueError):
    """Invalid request syntax; never a device or qualification result."""


def _require(condition: bool, message: str) -> None:
    if not condition:
        raise BenchContractError(message)


def _object(pairs):
    result = {}
    for key, value in pairs:
        _require(key not in result, "Duplicate field")
        result[key] = value
    return result


def _reject_constant(value):
    raise BenchContractError("Non-finite JSON constant")


def _canonical(value) -> bytes:
    return json.dumps(
        value, sort_keys=True, ensure_ascii=True, separators=(",", ":"), allow_nan=False
    ).encode("ascii")


def _validate(payload: bytes) -> dict[str, Any]:
    _require(
        type(payload) is bytes and 0 < len(payload) <= MAX_DOCUMENT_BYTES,
        "Expected bounded request bytes",
    )
    try:
        value = json.loads(
            payload.decode("utf-8", errors="strict"),
            object_pairs_hook=_object,
            parse_constant=_reject_constant,
        )
    except (ValueError, RecursionError) as error:
        raise BenchContractError("Invalid request JSON") from error
    _require(
        type(value) is dict and set(value) == _FIELDS,
        "Unknown or missing request fields",
    )
    _require(
        value["schema"] == SCHEMA and value["purpose"] == PURPOSE,
        "Unregistered request purpose",
    )
    _require(value["mode"] in ("rehearsal", "physical"), "Unknown request mode")
    for field in ("attempt_id", "launch_id"):
        item = value[field]
        _require(
            type(item) is str
            and re.fullmatch(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,127}", item) is not None,
            "Invalid attempt or launch identity",
        )
    refs = value["references"]
    _require(
        type(refs) is dict and set(refs) == _REFERENCE_NAMES,
        "Missing independent evidence references",
    )
    for digest in refs.values():
        _require(
            type(digest) is str
            and re.fullmatch(r"[0-9a-f]{64}", digest) is not None
            and digest != "0" * 64,
            "Invalid evidence digest",
        )
    deadline = value["parent_deadline_monotonic_ns"]
    _require(
        type(deadline) is int and 0 < deadline < 2**63, "Invalid absolute deadline"
    )
    limits = value["limits"]
    _require(type(limits) is dict and set(limits) == set(_LIMITS), "Invalid limits")
    for name, expected in _LIMITS.items():
        _require(
            type(limits[name]) is int and limits[name] == expected,
            "Unreviewed limit or outbound effect",
        )
    return value


@dataclass(frozen=True, slots=True)
class PassiveBenchRequest:
    """Immutable validated bytes; possession confers no execution authority."""

    payload: bytes

    def __post_init__(self):
        object.__setattr__(self, "payload", _canonical(_validate(self.payload)))

    @property
    def request_sha256(self) -> str:
        return hashlib.sha256(self.payload).hexdigest()

    def to_dict(self) -> dict[str, Any]:
        return json.loads(self.payload)

    def require_time_available(self, now_monotonic_ns: int) -> None:
        """Pure deadline check; does not consult a clock or renew the deadline."""
        _require(
            type(now_monotonic_ns) is int and now_monotonic_ns > 0,
            "Invalid clock observation",
        )
        remaining = self.to_dict()["parent_deadline_monotonic_ns"] - now_monotonic_ns
        _require(
            remaining >= (OBSERVATION_MS + CLEANUP_MS) * 1_000_000,
            "Insufficient lifetime for observation and cleanup",
        )

    def summary(self) -> dict[str, Any]:
        value = self.to_dict()
        return {
            "schema": SCHEMA,
            "purpose": PURPOSE,
            "attempt_id": value["attempt_id"],
            "mode": value["mode"],
            "request_sha256": self.request_sha256,
            "status": "SYNTAX_VALIDATED_NOT_ADMITTED",
            "references_authenticated": False,
            "physical_authority": False,
            "connected": False,
            "physical_dispatch_available": False,
        }
