"""Fixed powered-feedback intent; parsing is never native dispatch permission.

Separate from USB-only passive requests: query and powered zero-write telemetry
purposes have distinct immutable write budgets; neither permits movement.
Original startup, identity, firmware/protocol review and runtime references must
be resolved by the service/child before a future physical dispatch. Nonzero
hashes alone prove none of those reviews. No motion command is representable.
"""

from dataclasses import dataclass
import hashlib
import re

from rocell.arm.protocol import encode_line, feedback_request
from .arm_bench_qualification_contract import _canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json

SCHEMA = "rocell.powered_arm_feedback_intent.v1"
PURPOSE = "SINGLE_T105_POWERED_FEEDBACK"
TELEMETRY_PURPOSE = "POWERED_UNSOLICITED_TELEMETRY_ZERO_WRITE"
REFERENCE_NAMES = frozenset(
    {
        "source_sha256",
        "runtime_sha256",
        "serial_profile_sha256",
        "powered_startup_original_sha256",
        "native_identity_original_sha256",
        "protocol_review_sha256",
        "firmware_compatibility_review_sha256",
    }
)
LIMITS = {
    "maximum_open_attempts": 1,
    "maximum_write_attempts": 1,
    "maximum_outbound_bytes": len(encode_line(feedback_request())),
    "maximum_startup_bytes": 65536,
    "maximum_response_bytes": 65536,
    "observation_timeout_ms": 5000,
    "cleanup_timeout_ms": 2000,
    "quiet_interval_ms": 250,
    "maximum_read_calls": 512,
    "retries": 0,
}
TELEMETRY_LIMITS = {**LIMITS, "maximum_write_attempts": 0, "maximum_outbound_bytes": 0}


@dataclass(frozen=True, slots=True)
class PoweredFeedbackIntent:
    payload: bytes

    def __post_init__(self):
        if type(self.payload) is not bytes:
            raise ValueError("Immutable powered feedback request bytes required")
        body = decode_diagnostic_json(self.payload, maximum=8192)
        fields = {
            "schema",
            "purpose",
            "mode",
            "session_id",
            "attempt_id",
            "references",
            "startup_recorded_monotonic_ns",
            "parent_deadline_monotonic_ns",
            "limits",
        }
        if type(body) is not dict or set(body) != fields:
            raise ValueError("Exact powered feedback intent fields required")
        if (
            body["schema"] != SCHEMA
            or body["purpose"] not in (PURPOSE, TELEMETRY_PURPOSE)
            or type(body["mode"]) is not str
            or body["mode"] not in {"physical", "rehearsal"}
        ):
            raise ValueError("Powered feedback intent domain mismatch")
        for name, pattern in (
            ("session_id", r"wizard-[a-f0-9]{32}"),
            ("attempt_id", r"operation-[a-f0-9]{32}"),
        ):
            if type(body[name]) is not str or re.fullmatch(pattern, body[name]) is None:
                raise ValueError("Exact service identifiers required")
        refs = body["references"]
        if type(refs) is not dict or set(refs) != REFERENCE_NAMES:
            raise ValueError("Exact powered feedback references required")
        for value in refs.values():
            if (
                type(value) is not str
                or re.fullmatch(r"[a-f0-9]{64}", value) is None
                or value == "0" * 64
            ):
                raise ValueError("Nonzero original SHA-256 references required")
        if type(body["limits"]) is not dict or _canonical(body["limits"]) != _canonical(
            TELEMETRY_LIMITS if body["purpose"] == TELEMETRY_PURPOSE else LIMITS
        ):
            raise ValueError("Powered feedback limits are not caller-adjustable")
        for name in ("startup_recorded_monotonic_ns", "parent_deadline_monotonic_ns"):
            if type(body[name]) is not int or not 0 < body[name] < 2**63:
                raise ValueError("Exact positive monotonic timestamps required")
        if (
            body["parent_deadline_monotonic_ns"]
            <= body["startup_recorded_monotonic_ns"]
        ):
            raise ValueError("Feedback deadline must follow recorded startup")
        object.__setattr__(self, "payload", _canonical(body))

    def to_dict(self):
        return decode_diagnostic_json(self.payload, maximum=8192)

    @property
    def request_sha256(self):
        return hashlib.sha256(self.payload).hexdigest()

    @property
    def outbound_line(self):
        if self.to_dict()["purpose"] == TELEMETRY_PURPOSE:
            raise ValueError("Zero-write telemetry intent has no outbound command")
        return encode_line(feedback_request())

    def require_time_available(self, now_monotonic_ns):
        body = self.to_dict()
        if type(now_monotonic_ns) is not int:
            raise ValueError("Exact monotonic clock value required")
        age = now_monotonic_ns - body["startup_recorded_monotonic_ns"]
        remaining = body["parent_deadline_monotonic_ns"] - now_monotonic_ns
        if not 0 <= age <= 300_000_000_000:
            raise ValueError("Powered startup is stale or from a future clock")
        if not 7_000_000_000 <= remaining <= 30_000_000_000:
            raise ValueError("Feedback observation and cleanup lifetime unavailable")

    def summary(self):
        return {
            "schema": SCHEMA + ".summary",
            "request_sha256": self.request_sha256,
            "command_type": None if self.to_dict()["purpose"] == TELEMETRY_PURPOSE else 105,
            "expected_response_type": 1051,
            "maximum_outbound_bytes": self.to_dict()["limits"]["maximum_outbound_bytes"],
            "usb_only_passive": False,
            "references_verified": False,
            "physical_dispatch_available": False,
            "motion_authorized": False,
            "physical_authority": False,
        }
