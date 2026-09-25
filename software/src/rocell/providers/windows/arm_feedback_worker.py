"""One reviewed RoArm-M3 Pro onboarding feedback campaign, never a motion API.

The shared wire validator and existing SingleT105FeedbackReceipt remain the
protocol authority. This separate provider does not manufacture the legacy
commissioned FeedbackPermit or bypass arm_connection.json/current-build gates.

Physical composition is independently held in this revision. Its unopened
pySerial construction is implemented, but no public flag, callback or fixture
can remove that release hold. The sealed rehearsal backend is memory-only.
The caller must supervise this worker in a bounded process before any future
physical release: Python deadlines cannot interrupt a stalled OS open/close.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, field
from enum import Enum
import hashlib
import importlib
import json
import os
import re
from threading import Event, RLock
import time
from typing import TYPE_CHECKING, Any, Callable, Protocol, cast

if TYPE_CHECKING:
    from .arm_nonpurging_adapter import NonPurgingArmFeedbackBackend

from rocell.application.physical_connection_contracts import (
    EvidenceOrigin,
    RoArmUsbSerialIdentity,
    SingleT105FeedbackReceipt,
    SingleT105FeedbackRequest,
    T105TransactionTiming,
    UsbDriverIdentity,
    canonical_sha256,
)
from rocell.arm.feedback import parse_feedback_1051
from rocell.arm.feedback_wire import (
    FeedbackWireError,
    receive_buffered_byte_count,
    validate_feedback_response_line,
)
from rocell.arm.protocol import encode_line, feedback_request


REQUEST_SCHEMA = "rocell.arm_feedback_campaign.v1"
RESULT_SCHEMA = "rocell.arm_feedback_campaign_result.v1"
PHYSICAL_HOLD = "ARM_FEEDBACK_INDEPENDENT_PHYSICAL_QUALIFICATION_REQUIRED"
PYSERIAL_PURGE_HOLD = (
    "PYSERIAL_WINDOWS_OPEN_PURGES_INPUT_REQUIRES_REVIEWED_NONPURGING_BACKEND"
)
MAX_REQUEST_BYTES = 64 * 1024
INCAPABLE_COMPOSITION = "HARDWARE_INCAPABLE_REHEARSAL"
PHYSICAL_COMPOSITION = "WINDOWS_PYSERIAL_PHYSICAL_HELD"
PINNED_SDK_COMMIT = "d9893632aa7f5a9cb283136ab024faf3143ea7db"
PINNED_FIRMWARE_ARCHIVE_SHA256 = (
    "a28247fee0bbb65cc034ff206031b8700d2b1ec8e3a1fa4b1a5a7365c55f1a57"
)
MAX_LINE_BYTES = 65536
MAX_READ_CALLS = 4096
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.:-]{0,95}\Z")
_COM = re.compile(r"COM[1-9][0-9]{0,3}\Z")
_T105_LINE = encode_line(feedback_request())


class ArmFeedbackWorkerError(RuntimeError):
    def __init__(self, code: str, detail: str) -> None:
        super().__init__(f"{code}: {detail}")
        self.code = code


def _integer(value: object, name: str, minimum: int, maximum: int) -> int:
    if type(value) is not int or not minimum <= value <= maximum:
        raise ArmFeedbackWorkerError(
            "INVALID_REQUEST", f"{name} exceeds its integer bounds"
        )
    return value


def _digest(value: object, name: str) -> None:
    if type(value) is not str or _HASH.fullmatch(value) is None or value == "0" * 64:
        raise ArmFeedbackWorkerError(
            "INVALID_REQUEST", f"{name} must be a nonzero SHA-256"
        )


@dataclass(frozen=True, slots=True)
class ReviewedControllerBinding:
    """Server-retained review references, not a browser-selected COM number.

    A USB interface is not proof of arm model or firmware. Those observations
    stay separate and must be checked by the mandatory external authorizer.
    """

    identity: RoArmUsbSerialIdentity
    identity_receipt_sha256: str
    arm_model_receipt_sha256: str
    installed_firmware_evidence_sha256: str
    boot_policy_evidence_sha256: str
    serial_profile_sha256: str
    origin: EvidenceOrigin

    def __post_init__(self) -> None:
        if type(self.identity) is not RoArmUsbSerialIdentity or not isinstance(
            self.origin, EvidenceOrigin
        ):
            raise ArmFeedbackWorkerError(
                "INVALID_REQUEST", "reviewed controller identity/origin is required"
            )
        if (
            _COM.fullmatch(self.identity.port_name) is None
            or int(self.identity.port_name[3:]) > 4096
        ):
            raise ArmFeedbackWorkerError(
                "INVALID_REQUEST",
                "reviewed Windows endpoint must be exact COM1..COM4096",
            )
        for name in (
            "identity_receipt_sha256",
            "arm_model_receipt_sha256",
            "installed_firmware_evidence_sha256",
            "boot_policy_evidence_sha256",
            "serial_profile_sha256",
        ):
            _digest(getattr(self, name), name)

    def to_dict(self) -> dict[str, Any]:
        return {**asdict(self), "identity": self.identity.to_dict()}

    @property
    def binding_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


@dataclass(frozen=True, slots=True)
class ArmFeedbackBudget:
    duration_ms: int = 5000
    quiet_interval_ms: int = 250
    maximum_read_calls: int = 512
    read_chunk_bytes: int = 256

    def __post_init__(self) -> None:
        _integer(self.duration_ms, "duration_ms", 4000, 10000)
        _integer(self.quiet_interval_ms, "quiet_interval_ms", 250, 1000)
        _integer(self.maximum_read_calls, "maximum_read_calls", 1, MAX_READ_CALLS)
        _integer(self.read_chunk_bytes, "read_chunk_bytes", 1, 1024)


@dataclass(frozen=True, slots=True)
class ArmFeedbackCampaignRequest:
    campaign_id: str
    source_sha256: str
    operation_sha256: str
    energization_envelope_sha256: str
    controller: ReviewedControllerBinding
    feedback: SingleT105FeedbackRequest
    expires_monotonic_ns: int
    budget: ArmFeedbackBudget = field(default_factory=ArmFeedbackBudget)

    def __post_init__(self) -> None:
        if type(self.campaign_id) is not str or _ID.fullmatch(self.campaign_id) is None:
            raise ArmFeedbackWorkerError(
                "INVALID_REQUEST", "campaign_id must be a bounded identifier"
            )
        for name in (
            "source_sha256",
            "operation_sha256",
            "energization_envelope_sha256",
        ):
            _digest(getattr(self, name), name)
        if (
            type(self.controller) is not ReviewedControllerBinding
            or type(self.feedback) is not SingleT105FeedbackRequest
            or type(self.budget) is not ArmFeedbackBudget
        ):
            raise ArmFeedbackWorkerError(
                "INVALID_REQUEST", "closed reviewed campaign types are required"
            )
        for name in (
            "arm_identity_receipt_sha256",
            "arm_identity_sha256",
            "power_event_observation_sha256",
            "safety_permit_sha256",
        ):
            _digest(getattr(self.feedback, name), name)
        if (
            self.feedback.arm_identity_receipt_sha256
            != self.controller.identity_receipt_sha256
            or self.feedback.arm_identity_sha256
            != self.controller.identity.identity_sha256
        ):
            raise ArmFeedbackWorkerError(
                "INVALID_REQUEST",
                "feedback must bind this exact reviewed controller receipt",
            )
        _integer(
            self.expires_monotonic_ns,
            "expires_monotonic_ns",
            self.feedback.requested_monotonic_ns + 1,
            self.feedback.requested_monotonic_ns + 30_000_000_000,
        )
        if (
            self.expires_monotonic_ns - self.feedback.requested_monotonic_ns
            < self.budget.duration_ms * 1_000_000
        ):
            raise ArmFeedbackWorkerError(
                "INVALID_REQUEST",
                "request lifetime does not contain its campaign budget",
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": REQUEST_SCHEMA,
            **asdict(self),
            "controller": self.controller.to_dict(),
            "wire_request_hex": _T105_LINE.hex(),
            "wire_request_type": 105,
            "serial_settings": _settings(),
            "physical_authority": False,
        }

    @property
    def request_sha256(self) -> str:
        return canonical_sha256(self.to_dict())


def parse_arm_feedback_request(payload: bytes) -> ArmFeedbackCampaignRequest:
    """Strict bounded process-input decoder, not a browser authorization API."""
    if type(payload) is not bytes or not 1 <= len(payload) <= MAX_REQUEST_BYTES:
        raise ArmFeedbackWorkerError(
            "INVALID_REQUEST", "campaign IPC must be bounded UTF-8 JSON bytes"
        )

    def object_pairs(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
        document: dict[str, Any] = {}
        for key, value in pairs:
            if key in document:
                raise ArmFeedbackWorkerError(
                    "INVALID_REQUEST", "duplicate campaign JSON field"
                )
            document[key] = value
        return document

    def nonfinite(value: str) -> None:
        raise ArmFeedbackWorkerError("INVALID_REQUEST", "nonfinite campaign JSON value")

    try:
        document = json.loads(
            payload.decode("utf-8"),
            object_pairs_hook=object_pairs,
            parse_constant=nonfinite,
        )
        if type(document) is not dict or document.get("schema") != REQUEST_SCHEMA:
            raise ArmFeedbackWorkerError(
                "INVALID_REQUEST", "unsupported campaign schema"
            )
        controller = dict(document["controller"])
        identity = dict(controller["identity"])
        for constant in (
            "manufacturer",
            "product",
            "controller",
            "baudrate",
            "rts",
            "dtr",
            "flow_control",
        ):
            del identity[constant]
        identity["driver"] = UsbDriverIdentity(**identity["driver"])
        controller["identity"] = RoArmUsbSerialIdentity(**identity)
        controller["origin"] = EvidenceOrigin(controller["origin"])
        restored = ArmFeedbackCampaignRequest(
            document["campaign_id"],
            document["source_sha256"],
            document["operation_sha256"],
            document["energization_envelope_sha256"],
            ReviewedControllerBinding(**controller),
            SingleT105FeedbackRequest(**document["feedback"]),
            document["expires_monotonic_ns"],
            ArmFeedbackBudget(**document["budget"]),
        )
        # Exact canonical comparison rejects all extra/fixed-field substitutions
        # and bool/float-vs-int coercions, while allowing pretty JSON whitespace.
        if canonical_sha256(document) != restored.request_sha256:
            raise ArmFeedbackWorkerError(
                "INVALID_REQUEST",
                "campaign fields/settings do not match the closed schema",
            )
        return restored
    except (ValueError, TypeError, KeyError, UnicodeError, RecursionError) as exc:
        raise ArmFeedbackWorkerError(
            "INVALID_REQUEST", "malformed closed campaign document"
        ) from exc


class ArmFeedbackAuthorizer(Protocol):
    def __call__(self, request: ArmFeedbackCampaignRequest, /) -> None:
        """Consume exact durable one-use authority or raise before backend access.

        Must verify CELL→SESSION→ARM_CONTROLLER leases, source/stage/revision,
        installed firmware/boot policy, binding, fresh power-event/envelope,
        output bounds and the independently qualified composition. Returning
        None is a protocol acknowledgement, not an authorization Boolean.
        """


class ControllerIdentityResolver(Protocol):
    def __call__(self, expected: RoArmUsbSerialIdentity, /) -> RoArmUsbSerialIdentity:
        """Return freshly observed exact OS identity, or raise; never open serial."""


def _settings() -> dict[str, Any]:
    return {
        "baudrate": 115200,
        "bytesize": 8,
        "parity": "N",
        "stopbits": 1,
        "timeout": 1.0,
        "write_timeout": 1.0,
        "xonxoff": False,
        "rtscts": False,
        "dsrdtr": False,
        "rts": False,
        "dtr": False,
        "inter_byte_timeout": None,
    }


def _settings_readback(
    connection: Any, expected_port: str
) -> tuple[tuple[str, Any], ...]:
    expected = {"port": expected_port, **_settings()}
    observed = {name: getattr(connection, name, object()) for name in expected}
    if any(
        type(observed[name]) is not type(value) or observed[name] != value
        for name, value in expected.items()
    ):
        raise ArmFeedbackWorkerError(
            "SERIAL_SETTINGS_READBACK_MISMATCH",
            "115200/8N1/control-line settings did not match exactly",
        )
    return tuple(observed.items())


def _require_independent_physical_qualification() -> None:
    # This is a source-controlled release hold, not a runtime option. An
    # external callback cannot waive OS identity/RTS-DTR/process qualification.
    raise ArmFeedbackWorkerError(
        PHYSICAL_HOLD, "physical onboarding provider release is unavailable"
    )


class WindowsPySerialBackend:
    """Concrete native closed-object construction, currently release-held.

    No serial-for-URL, auto-open constructor, SDK, demo, reset or motion path.
    pySerial 3.5's Win32 open unconditionally purges receive/transmit buffers.
    Therefore even removing a release flag would not qualify preservation of
    startup bytes: a reviewed non-purging native opener is still required.
    """

    __slots__ = ()
    composition = PHYSICAL_COMPOSITION
    origin = EvidenceOrigin.PHYSICAL_OBSERVATION

    def require_available(self) -> None:
        _require_independent_physical_qualification()

    def create_closed(self) -> Any:
        self.require_available()
        if os.name != "nt":
            raise ArmFeedbackWorkerError(
                "WINDOWS_REQUIRED", "this backend requires Windows"
            )
        serial = importlib.import_module("serial")
        if getattr(serial, "VERSION", None) != "3.5":
            raise ArmFeedbackWorkerError(
                "PYSERIAL_VERSION_MISMATCH",
                "the reviewed backend requires pySerial 3.5",
            )
        return serial.Serial(port=None)


@dataclass(frozen=True, slots=True)
class IncapableSerialScenario:
    """Finite in-memory bytes/faults; cannot delegate to a serial factory."""

    response_bytes: bytes = (
        b'{"T":1051,"x":120,"y":0,"z":180,"b":0,"s":0,"e":1,"t":0,"r":0,"g":1}\n'
    )
    preexisting_bytes: bytes = b""
    delayed_preexisting_bytes: bytes = b""
    dirty_after_buffer_checks: int = 2
    fail_at: tuple[str, ...] = ()
    short_write_count: int | None = None
    read_fragment_bytes: int = 256
    close_remains_open: bool = False
    already_open: bool = False
    read_returns_nonbytes: bool = False

    def __post_init__(self) -> None:
        for name in (
            "response_bytes",
            "preexisting_bytes",
            "delayed_preexisting_bytes",
        ):
            value = getattr(self, name)
            if type(value) is not bytes or len(value) > MAX_LINE_BYTES + 2:
                raise ArmFeedbackWorkerError(
                    "INVALID_FIXTURE", "fixture bytes exceed their immutable bound"
                )
        if type(self.fail_at) is not tuple or any(
            item not in {"configure", "open", "buffer", "write", "read", "close"}
            for item in self.fail_at
        ):
            raise ArmFeedbackWorkerError(
                "INVALID_FIXTURE", "unknown in-memory failure point"
            )
        _integer(self.dirty_after_buffer_checks, "dirty_after_buffer_checks", 1, 1000)
        _integer(self.read_fragment_bytes, "read_fragment_bytes", 1, 1024)
        if self.short_write_count is not None:
            _integer(
                self.short_write_count, "short_write_count", 0, len(_T105_LINE) + 1
            )
        for name in ("close_remains_open", "already_open", "read_returns_nonbytes"):
            if type(getattr(self, name)) is not bool:
                raise ArmFeedbackWorkerError(
                    "INVALID_FIXTURE", f"{name} must be Boolean"
                )


class _IncapableSerialApi:
    def __init__(self, scenario: IncapableSerialScenario) -> None:
        self._scenario, self._buffer = scenario, bytearray(scenario.preexisting_bytes)
        self.is_open, self._buffer_checks, self._written = (
            scenario.already_open,
            0,
            False,
        )
        self.trace: list[tuple[str, Any]] = []

    def __setattr__(self, name: str, value: Any) -> None:
        if name in _settings() or name == "port":
            if "configure" in self._scenario.fail_at:
                raise OSError("injected serial configuration failure")
            self.trace.append((f"set:{name}", value))
        object.__setattr__(self, name, value)

    def open(self) -> None:
        self.trace.append(("open", None))
        self.is_open = True
        if "open" in self._scenario.fail_at:
            raise OSError("injected open with ambiguous handle state")

    @property
    def in_waiting(self) -> int:
        self.trace.append(("in_waiting", None))
        if "buffer" in self._scenario.fail_at:
            raise OSError("injected buffer observation failure")
        self._buffer_checks += 1
        if (
            self._buffer_checks == self._scenario.dirty_after_buffer_checks
            and not self._written
        ):
            self._buffer.extend(self._scenario.delayed_preexisting_bytes)
        return len(self._buffer)

    def write(self, payload: bytes) -> int:
        if payload != _T105_LINE or self._written:
            raise AssertionError(
                "incapable backend accepts exactly one fixed T105 line"
            )
        self.trace.append(("write", payload))
        self._written = True
        if "write" in self._scenario.fail_at:
            raise OSError("injected ambiguous write failure")
        self._buffer.extend(self._scenario.response_bytes)
        return (
            len(payload)
            if self._scenario.short_write_count is None
            else self._scenario.short_write_count
        )

    def read(self, size: int) -> bytes:
        self.trace.append(("read", size))
        if "read" in self._scenario.fail_at:
            raise OSError("injected read failure")
        if self._scenario.read_returns_nonbytes:
            return None  # type: ignore[return-value]
        count = min(size, self._scenario.read_fragment_bytes, len(self._buffer))
        value = bytes(self._buffer[:count])
        del self._buffer[:count]
        return value

    def close(self) -> None:
        self.trace.append(("close", None))
        if "close" in self._scenario.fail_at:
            raise OSError("injected close failure")
        self.is_open = self._scenario.close_remains_open


class IncapableSerialBackend:
    """Sealed memory-only fixture backend, not an injectable native factory."""

    __slots__ = ("_scenario", "_connection")
    composition = INCAPABLE_COMPOSITION
    origin = EvidenceOrigin.SYNTHETIC_REHEARSAL

    def __init__(
        self, scenario: IncapableSerialScenario = IncapableSerialScenario()
    ) -> None:
        if type(scenario) is not IncapableSerialScenario:
            raise ArmFeedbackWorkerError(
                "INVALID_FIXTURE", "typed incapable serial scenario is required"
            )
        self._scenario = scenario
        self._connection: _IncapableSerialApi | None = None

    def require_available(self) -> None:
        return None

    def create_closed(self) -> _IncapableSerialApi:
        if self._connection is not None:
            raise ArmFeedbackWorkerError(
                "FIXTURE_ALREADY_USED", "one serial API instance per campaign"
            )
        self._connection = _IncapableSerialApi(self._scenario)
        return self._connection

    @property
    def trace(self) -> tuple[tuple[str, Any], ...]:
        return () if self._connection is None else tuple(self._connection.trace)


class ArmFeedbackOutcome(str, Enum):
    SUCCEEDED_DIAGNOSTIC = "SUCCEEDED_DIAGNOSTIC"
    BLOCKED_PRE_OPEN = "BLOCKED_PRE_OPEN"
    CANCELLED_PRE_OPEN = "CANCELLED_PRE_OPEN"
    FAILED_UNCERTAIN = "FAILED_UNCERTAIN"


@dataclass(frozen=True, slots=True)
class SerialLifecycleError:
    code: str
    phase: str
    error_type: str


@dataclass(frozen=True, slots=True)
class SerialApiCounts:
    object_creations: int = 0
    identity_checks: int = 0
    open_attempts: int = 0
    opens_confirmed: int = 0
    unexpected_open_objects: int = 0
    write_attempts: int = 0
    writes_confirmed: int = 0
    write_bytes_confirmed: int = 0
    read_attempts: int = 0
    read_bytes_retained: int = 0
    close_attempts: int = 0
    closes_confirmed: int = 0


@dataclass(frozen=True, slots=True)
class ArmFeedbackCampaignResult:
    request_sha256: str
    origin: EvidenceOrigin
    composition: str
    outcome: ArmFeedbackOutcome
    api_counts: SerialApiCounts
    primary_error: SerialLifecycleError | None
    cleanup_errors: tuple[SerialLifecycleError, ...]
    feedback_receipt: SingleT105FeedbackReceipt | None
    response_bytes: bytes
    unexpected_bytes: bytes
    unexpected_bytes_unretained: int
    opened_monotonic_ns: int | None
    closed_monotonic_ns: int | None
    elapsed_ns: int
    connection_closed: bool
    settings_before_open: tuple[tuple[str, Any], ...] = ()
    settings_after_open: tuple[tuple[str, Any], ...] = ()
    write_api_returned_count: int | None = None

    @property
    def effect_uncertain(self) -> bool:
        return (
            self.api_counts.open_attempts > 0
            or self.api_counts.unexpected_open_objects > 0
        ) and self.outcome is not ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC

    def to_dict(self) -> dict[str, Any]:
        """Safe status projection: raw boot/response bytes are not UI log text.

        The lossless typed receipt/bytes remain available for a separately
        authorized evidence writer; default diagnostics retain hashes/counts.
        """
        summary = None
        if self.feedback_receipt is not None:
            parsed = validate_feedback_response_line(
                self.feedback_receipt.response_bytes, max_line_bytes=MAX_LINE_BYTES
            )
            typed = parse_feedback_1051(parsed)
            summary = {
                key: value
                for key, value in asdict(typed).items()
                if key not in {"raw_fields", "unknown_fields"}
            }
        return {
            "schema": RESULT_SCHEMA,
            "request_sha256": self.request_sha256,
            "origin": self.origin.value,
            "composition": self.composition,
            "status": self.outcome.value,
            "serial_api_counts": asdict(self.api_counts),
            "physical_operation_counts": (
                {
                    "serial_opens": 0,
                    "serial_writes": 0,
                    "serial_reads": 0,
                    "serial_closes": 0,
                }
                if self.origin is EvidenceOrigin.SYNTHETIC_REHEARSAL
                else {
                    "serial_opens": self.api_counts.open_attempts,
                    "serial_writes": self.api_counts.write_attempts,
                    "serial_reads": self.api_counts.read_attempts,
                    "serial_closes": self.api_counts.close_attempts,
                }
            ),
            "primary_error": (
                None if self.primary_error is None else asdict(self.primary_error)
            ),
            "cleanup_errors": [asdict(error) for error in self.cleanup_errors],
            "effect_uncertain": self.effect_uncertain,
            "connection_closed": self.connection_closed,
            "settings_before_open": dict(self.settings_before_open),
            "settings_after_open": dict(self.settings_after_open),
            "write_api_returned_count": self.write_api_returned_count,
            "request_bytes_attempted": (
                len(_T105_LINE) if self.api_counts.write_attempts else 0
            ),
            "request_bytes_sha256": hashlib.sha256(_T105_LINE).hexdigest(),
            "feedback_receipt_sha256": (
                None
                if self.feedback_receipt is None
                else self.feedback_receipt.receipt_sha256
            ),
            "feedback": summary,
            "response_sha256": hashlib.sha256(self.response_bytes).hexdigest(),
            "response_bytes_retained": len(self.response_bytes),
            "unexpected_sha256": hashlib.sha256(self.unexpected_bytes).hexdigest(),
            "unexpected_bytes_retained": len(self.unexpected_bytes),
            "unexpected_bytes_unretained": self.unexpected_bytes_unretained,
            "opened_monotonic_ns": self.opened_monotonic_ns,
            "closed_monotonic_ns": self.closed_monotonic_ns,
            "elapsed_ns": self.elapsed_ns,
            "timing_basis": "HOST_READ_COMPLETION_NOT_DEVICE_TIMESTAMP",
            "final_power_state": "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION",
            "installed_firmware_proven_by_packet": False,
            "retry_count": 0,
            "motion_commands_sent": 0,
            "physical_authority": False,
            "limits": [
                PHYSICAL_HOLD,
                PYSERIAL_PURGE_HOLD,
                "PROCESS_CONTAINMENT_NOT_QUALIFIED",
                "RTS_DTR_OPEN_GLITCH_UNQUALIFIED",
                "FINAL_POWER_OBSERVATION_REQUIRED",
            ],
        }


class ArmFeedbackWorker:
    """One-use exact campaign; external coordinator owns durable admission.

    `run` must be the only operation dispatched into a future bounded worker
    process. Request IDs/nonces are log correlation, not a firmware ACK token.
    """

    def __init__(
        self,
        *,
        authorizer: ArmFeedbackAuthorizer,
        identity_resolver: ControllerIdentityResolver,
        backend: (
            WindowsPySerialBackend
            | IncapableSerialBackend
            | NonPurgingArmFeedbackBackend
            | None
        ) = None,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        wait: Callable[[Event, float], bool] = lambda event, seconds: event.wait(
            seconds
        ),
    ) -> None:
        if (
            not callable(authorizer)
            or not callable(identity_resolver)
            or not callable(monotonic_ns)
            or not callable(wait)
        ):
            raise ArmFeedbackWorkerError(
                "INVALID_PROVIDER",
                "explicit authorization, identity, clock and wait callbacks are required",
            )
        # Local import avoids the typed binding/native-owner dependency cycle.
        # This remains a closed registry, never an arbitrary serial factory.
        from .arm_nonpurging_adapter import NonPurgingArmFeedbackBackend

        selected = WindowsPySerialBackend() if backend is None else backend
        if type(selected) not in (
            WindowsPySerialBackend,
            IncapableSerialBackend,
            NonPurgingArmFeedbackBackend,
        ):
            raise ArmFeedbackWorkerError(
                "INVALID_PROVIDER", "unregistered serial backend composition"
            )
        self._backend, self._authorizer, self._identity_resolver = (
            selected,
            authorizer,
            identity_resolver,
        )
        self._clock, self._wait, self._lock = monotonic_ns, wait, RLock()
        self._used, self._phase = False, "IDLE"
        self._nonpurging_adapter = (
            selected if isinstance(selected, NonPurgingArmFeedbackBackend) else None
        )

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "phase": self._phase,
                "consumed": self._used,
                "composition": self._backend.composition,
                "origin": self._backend.origin.value,
                "hardware_accessed_by_status": False,
                "physical_authority": False,
                "physical_hold": PHYSICAL_HOLD,
                "native_buffer_preservation_hold": (
                    self._nonpurging_adapter.status()["physical_hold"]
                    if self._nonpurging_adapter is not None
                    else PYSERIAL_PURGE_HOLD
                ),
            }

    def run(
        self, request: ArmFeedbackCampaignRequest, *, cancellation: Event | None = None
    ) -> ArmFeedbackCampaignResult:
        if type(request) is not ArmFeedbackCampaignRequest:
            raise ArmFeedbackWorkerError(
                "INVALID_REQUEST", "a closed typed campaign request is required"
            )
        cancel = Event() if cancellation is None else cancellation
        if type(cancel) is not Event:
            raise ArmFeedbackWorkerError(
                "INVALID_REQUEST", "cancellation must be a threading Event"
            )
        with self._lock:
            if self._used:
                raise ArmFeedbackWorkerError(
                    "CAMPAIGN_ALREADY_USED",
                    "worker cannot retry or accept another request",
                )
            self._used, self._phase = True, "ADMISSION"
        if self._nonpurging_adapter is not None:
            self._nonpurging_adapter._bind_request(request)
        result = self._run_once(request, cancel)
        if self._nonpurging_adapter is not None:
            # Capture native resource/late-byte evidence only after the actual
            # worker completed its cleanup path. This does not publish a seal.
            self._nonpurging_adapter._complete_result(request, result)
        return result

    def _run_once(
        self, request: ArmFeedbackCampaignRequest, cancel: Event
    ) -> ArmFeedbackCampaignResult:
        counts = {name: 0 for name in SerialApiCounts.__dataclass_fields__}
        response, unexpected = bytearray(), bytearray()
        extra_unretained = 0
        connection: Any = None
        primary: SerialLifecycleError | None = None
        cleanup: list[SerialLifecycleError] = []
        timing: dict[str, int] = {}
        receipt = None
        closed = False
        before_settings: tuple[tuple[str, Any], ...] = ()
        after_settings: tuple[tuple[str, Any], ...] = ()
        write_api_returned_count: int | None = None
        start = _integer(self._clock(), "clock", 1, 2**63 - 1)
        last_now = start
        deadline = min(
            request.expires_monotonic_ns, start + request.budget.duration_ms * 1_000_000
        )

        def phase(value: str) -> None:
            with self._lock:
                self._phase = value

        def now() -> int:
            nonlocal last_now
            observed = _integer(self._clock(), "clock", 1, 2**63 - 1)
            if observed < last_now:
                raise ArmFeedbackWorkerError(
                    "MONOTONIC_CLOCK_REGRESSED", "campaign clock moved backwards"
                )
            last_now = observed
            return observed

        def checkpoint() -> int:
            current = now()
            if cancel.is_set():
                raise ArmFeedbackWorkerError(
                    "CANCELLED", "cancellation requests cessation, not power removal"
                )
            if current >= deadline:
                raise ArmFeedbackWorkerError(
                    "CAMPAIGN_DEADLINE_EXCEEDED", "campaign deadline elapsed"
                )
            return current

        def resolve_exact() -> None:
            checkpoint()
            counts["identity_checks"] += 1
            observed = self._identity_resolver(request.controller.identity)
            if (
                type(observed) is not RoArmUsbSerialIdentity
                or observed != request.controller.identity
            ):
                raise ArmFeedbackWorkerError(
                    "CONTROLLER_IDENTITY_CHANGED",
                    "reviewed identity/driver/COM mapping changed",
                )
            checkpoint()

        def read_bytes(size: int) -> bytes:
            checkpoint()
            if counts["read_attempts"] >= request.budget.maximum_read_calls:
                raise ArmFeedbackWorkerError(
                    "READ_CALL_BUDGET_EXCEEDED", "bounded read-call count exhausted"
                )
            connection.timeout = min(1.0, (deadline - now()) / 1_000_000_000)
            counts["read_attempts"] += 1
            raw = connection.read(size)
            if type(raw) is not bytes or len(raw) > size:
                raise ArmFeedbackWorkerError(
                    "INVALID_SERIAL_READ", "serial read violated its exact byte bound"
                )
            counts["read_bytes_retained"] += len(raw)
            return raw

        def quiet_or_retain() -> None:
            nonlocal extra_unretained
            pending = receive_buffered_byte_count(connection)
            if pending:
                remaining = (
                    request.feedback.maximum_line_bytes
                    + 1
                    - len(response)
                    - len(unexpected)
                )
                # Preserve a bounded prefix as evidence, never flush it and
                # continue. The count records unread excess before closing.
                extra_unretained += pending
                if remaining > 0:
                    retained = read_bytes(
                        min(pending, remaining, request.budget.read_chunk_bytes)
                    )
                    unexpected.extend(retained)
                    extra_unretained -= len(retained)
                raise ArmFeedbackWorkerError(
                    "STALE_OR_EXTRA_BUFFERED_BYTES",
                    "unexpected bytes prohibit a feedback write or successful receipt",
                )

        try:
            checkpoint()
            if (
                request.feedback.requested_monotonic_ns > start
                or request.expires_monotonic_ns - start
                < request.budget.duration_ms * 1_000_000
            ):
                raise ArmFeedbackWorkerError(
                    "STALE_CAMPAIGN_REQUEST",
                    "fresh lifetime must contain the complete campaign",
                )
            if request.controller.origin is not self._backend.origin:
                raise ArmFeedbackWorkerError(
                    "PROVENANCE_MISMATCH",
                    "rehearsal/physical controller origins cannot be mixed",
                )
            self._backend.require_available()
            acknowledgement = cast(
                Callable[[ArmFeedbackCampaignRequest], object], self._authorizer
            )(request)
            if acknowledgement is not None:
                raise ArmFeedbackWorkerError(
                    "INVALID_AUTHORIZER_ACK",
                    "authorizer must consume authority and return None or raise",
                )
            checkpoint()
            phase("IDENTITY_BEFORE_OPEN")
            resolve_exact()
            phase("CONFIGURING_CLOSED")
            counts["object_creations"] += 1
            connection = self._backend.create_closed()
            if getattr(connection, "is_open", None) is not False:
                counts["unexpected_open_objects"] += 1
                raise ArmFeedbackWorkerError(
                    "FACTORY_ALREADY_OPEN",
                    "serial factory must produce a closed connection",
                )
            connection.port = request.controller.identity.port_name
            for name, value in _settings().items():
                setattr(connection, name, value)
            before_settings = _settings_readback(
                connection, request.controller.identity.port_name
            )
            checkpoint()
            phase("OPENING")
            counts["open_attempts"] += 1
            connection.open()
            if getattr(connection, "is_open", None) is not True:
                raise ArmFeedbackWorkerError(
                    "OPEN_UNCONFIRMED", "serial open did not report an open handle"
                )
            counts["opens_confirmed"] += 1
            timing["port_opened_monotonic_ns"] = checkpoint()
            after_settings = _settings_readback(
                connection, request.controller.identity.port_name
            )
            phase("QUIET_BUFFER_OBSERVATION")
            quiet_until = (
                timing["port_opened_monotonic_ns"]
                + request.budget.quiet_interval_ms * 1_000_000
            )
            for _ in range(128):
                current = checkpoint()
                quiet_or_retain()
                if current >= quiet_until:
                    break
                self._wait(cancel, min(0.01, (quiet_until - current) / 1_000_000_000))
            else:
                raise ArmFeedbackWorkerError(
                    "QUIET_WINDOW_INCOMPLETE",
                    "bounded quiet observations did not span the required interval",
                )
            phase("IDENTITY_BEFORE_WRITE")
            resolve_exact()
            quiet_or_retain()
            timing["pre_request_buffer_observed_monotonic_ns"] = checkpoint()
            phase("ONE_T105_WRITE")
            timing["request_write_started_monotonic_ns"] = checkpoint()
            if deadline - timing["request_write_started_monotonic_ns"] < 1_000_000_000:
                raise ArmFeedbackWorkerError(
                    "INSUFFICIENT_WRITE_DEADLINE",
                    "the fixed one-second write timeout no longer fits",
                )
            counts["write_attempts"] += 1
            written = connection.write(_T105_LINE)
            if type(written) is int and 0 <= written <= MAX_LINE_BYTES:
                write_api_returned_count = written
                if written <= len(_T105_LINE):
                    counts["write_bytes_confirmed"] = written
            if type(written) is not int or written != len(_T105_LINE):
                raise ArmFeedbackWorkerError(
                    "SHORT_OR_AMBIGUOUS_WRITE",
                    "one write did not report the exact request byte count",
                )
            counts["writes_confirmed"], counts["write_bytes_confirmed"] = 1, written
            timing["request_write_completed_monotonic_ns"] = checkpoint()
            phase("ONE_T1051_RESPONSE")
            while not response.endswith(b"\n"):
                checkpoint()
                room = request.feedback.maximum_line_bytes + 1 - len(response)
                if room <= 0:
                    raise ArmFeedbackWorkerError(
                        "RESPONSE_LINE_TOO_LONG",
                        "feedback line exceeded its retained bound",
                    )
                pending = receive_buffered_byte_count(connection)
                raw = read_bytes(
                    min(max(1, pending), request.budget.read_chunk_bytes, room)
                )
                if raw:
                    if not response:
                        timing["first_response_byte_monotonic_ns"] = now()
                    response.extend(raw)
                else:
                    raise ArmFeedbackWorkerError(
                        "RESPONSE_TIMEOUT_OR_TRUNCATED",
                        "one bounded response read timed out before a complete line",
                    )
                checkpoint()
            timing["response_completed_monotonic_ns"] = now()
            parsed = validate_feedback_response_line(
                bytes(response), max_line_bytes=request.feedback.maximum_line_bytes
            )
            quiet_or_retain()
            phase("RESPONSE_VALIDATED")
        except Exception as exc:
            code = (
                exc.code
                if isinstance(exc, ArmFeedbackWorkerError)
                else (
                    exc.failure.value
                    if isinstance(exc, FeedbackWireError)
                    else "SERIAL_API_FAILURE"
                )
            )
            primary = SerialLifecycleError(code, self._phase, type(exc).__name__[:96])
        finally:
            if connection is not None:
                phase("CLOSING")
                counts["close_attempts"] += 1
                try:
                    connection.close()
                    if getattr(connection, "is_open", None) is not False:
                        raise ArmFeedbackWorkerError(
                            "CLOSE_UNCONFIRMED",
                            "serial close did not report a closed handle",
                        )
                    counts["closes_confirmed"] += 1
                    closed = True
                    timing["port_closed_monotonic_ns"] = now()
                except Exception as exc:
                    cleanup.append(
                        SerialLifecycleError(
                            (
                                exc.code
                                if isinstance(exc, ArmFeedbackWorkerError)
                                else "SERIAL_CLOSE_FAILED"
                            ),
                            "CLOSING",
                            type(exc).__name__[:96],
                        )
                    )
            try:
                ended = now()
                if cancel.is_set() and counts["open_attempts"]:
                    cleanup.append(
                        SerialLifecycleError(
                            "CANCELLATION_AFTER_OPEN",
                            "COMPLETION",
                            "ArmFeedbackWorkerError",
                        )
                    )
                if ended >= deadline:
                    cleanup.append(
                        SerialLifecycleError(
                            "CAMPAIGN_DEADLINE_EXCEEDED",
                            "COMPLETION",
                            "ArmFeedbackWorkerError",
                        )
                    )
            except Exception as exc:
                ended = last_now
                cleanup.append(
                    SerialLifecycleError(
                        "INVALID_COMPLETION_CLOCK",
                        "COMPLETION",
                        type(exc).__name__[:96],
                    )
                )
        if primary is None and not cleanup:
            try:
                receipt = SingleT105FeedbackReceipt(
                    request.feedback.run_id,
                    canonical_sha256(
                        {
                            "composition": self._backend.composition,
                            "sdk_commit": PINNED_SDK_COMMIT,
                            "firmware_archive_sha256": PINNED_FIRMWARE_ARCHIVE_SHA256,
                        }
                    ),
                    request.feedback.request_context_sha256,
                    request.controller.identity.identity_sha256,
                    request.feedback.controller_session_id,
                    T105TransactionTiming(**timing),
                    0,
                    0,
                    _T105_LINE,
                    bytes(response),
                    hashlib.sha256(_T105_LINE).hexdigest(),
                    hashlib.sha256(response).hexdigest(),
                    canonical_sha256(parsed),
                    1,
                    1,
                    0,
                    0,
                    True,
                )
            except Exception as exc:
                primary = SerialLifecycleError(
                    "INVALID_COMPLETION_RECEIPT", "COMPLETION", type(exc).__name__[:96]
                )
        outcome = (
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
        phase(outcome.value)
        return ArmFeedbackCampaignResult(
            request.request_sha256,
            self._backend.origin,
            self._backend.composition,
            outcome,
            SerialApiCounts(**counts),
            primary,
            tuple(cleanup),
            receipt,
            bytes(response),
            bytes(unexpected),
            max(0, extra_unretained),
            timing.get("port_opened_monotonic_ns"),
            timing.get("port_closed_monotonic_ns"),
            max(0, ended - start),
            closed,
            before_settings,
            after_settings,
            write_api_returned_count,
        )


def rehearse_arm_feedback_campaign(scenario: str = "nominal") -> dict[str, Any]:
    """Run one closed, deterministic, hardware-incapable lifecycle fixture.

    This entry has no endpoint, provider, factory, path or authorization input.
    Its exact in-memory acknowledgement is NOT production authorization and
    cannot be installed in the hard-held native composition by this function.
    """
    scenarios = {
        "nominal": IncapableSerialScenario(),
        "boot-bytes": IncapableSerialScenario(
            preexisting_bytes=b"ets SYNTHETIC ESP32 boot text\n"
        ),
        "short-write": IncapableSerialScenario(short_write_count=1),
        "timeout": IncapableSerialScenario(response_bytes=b""),
        "identity-change": IncapableSerialScenario(),
        "close-failure": IncapableSerialScenario(fail_at=("close",)),
    }
    if type(scenario) is not str or scenario not in scenarios:
        raise ArmFeedbackWorkerError(
            "UNKNOWN_REHEARSAL_SCENARIO", "select one registered arm feedback fixture"
        )
    identity = RoArmUsbSerialIdentity(
        "ffff",
        "0002",
        "SYNTHETIC-NOT-A-RECEIVED-CONTROLLER",
        "USB\\VID_FFFF&PID_0002\\SYNTHETIC-CONTROLLER",
        "usb-unit:ffff:0002:SYNTHETIC-CONTROLLER",
        "COM404",
        UsbDriverIdentity(
            "SYNTHETIC", "memory-only", "1.0", "synthetic-not-installed.inf"
        ),
    )

    def fact(label: str) -> str:
        return canonical_sha256({"synthetic_fact": label, "scenario": scenario})

    binding = ReviewedControllerBinding(
        identity=identity,
        identity_receipt_sha256=fact("unpowered-controller"),
        arm_model_receipt_sha256=fact("arm-model"),
        installed_firmware_evidence_sha256=fact("installed-firmware"),
        boot_policy_evidence_sha256=fact("boot-policy"),
        serial_profile_sha256=fact("serial-profile"),
        origin=EvidenceOrigin.SYNTHETIC_REHEARSAL,
    )
    moment = 1_000_000_000

    def clock() -> int:
        nonlocal moment
        moment += 1
        return moment

    def wait(event: Event, seconds: float) -> bool:
        nonlocal moment
        moment += int(seconds * 1_000_000_000)
        return event.is_set()

    feedback = SingleT105FeedbackRequest(
        "synthetic-arm-feedback-rehearsal",
        binding.identity_receipt_sha256,
        identity.identity_sha256,
        canonical_sha256({"synthetic": "manual-power-observation"}),
        canonical_sha256({"synthetic": "not-a-production-permit"}),
        "synthetic-controller-session",
        moment,
        2048,
    )
    request = ArmFeedbackCampaignRequest(
        "synthetic-" + scenario,
        canonical_sha256({"synthetic": "fixture-source"}),
        canonical_sha256({"synthetic": "one-t105"}),
        canonical_sha256({"synthetic": "not-a-physical-energy-envelope"}),
        binding,
        feedback,
        moment + 30_000_000_000,
    )
    acknowledged = False

    def exact_fixture_acknowledgement(observed: ArmFeedbackCampaignRequest) -> None:
        nonlocal acknowledged
        if (
            acknowledged
            or observed is not request
            or observed.request_sha256 != request.request_sha256
        ):
            raise ArmFeedbackWorkerError(
                "INVALID_FIXTURE_ACK", "fixture request was reused/substituted"
            )
        acknowledged = True

    identity_checks = 0

    def identity_resolver(expected: RoArmUsbSerialIdentity) -> RoArmUsbSerialIdentity:
        nonlocal identity_checks
        identity_checks += 1
        if scenario == "identity-change" and identity_checks == 2:
            return RoArmUsbSerialIdentity(
                expected.vid,
                expected.pid,
                expected.unit_serial,
                expected.persistent_instance_id,
                expected.persistent_port_path,
                "COM405",
                expected.driver,
            )
        return expected

    worker = ArmFeedbackWorker(
        authorizer=exact_fixture_acknowledgement,
        identity_resolver=identity_resolver,
        backend=IncapableSerialBackend(scenarios[scenario]),
        monotonic_ns=clock,
        wait=wait,
    )
    result = worker.run(request)
    expected_code = {
        "nominal": None,
        "boot-bytes": "STALE_OR_EXTRA_BUFFERED_BYTES",
        "short-write": "SHORT_OR_AMBIGUOUS_WRITE",
        "timeout": "RESPONSE_TIMEOUT_OR_TRUNCATED",
        "identity-change": "CONTROLLER_IDENTITY_CHANGED",
        "close-failure": "SERIAL_CLOSE_FAILED",
    }[scenario]
    observed_codes = [
        error.code
        for error in ((result.primary_error,) if result.primary_error else ())
        + result.cleanup_errors
    ]
    matched = (
        result.outcome is ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC
        if expected_code is None
        else result.outcome is ArmFeedbackOutcome.FAILED_UNCERTAIN
        and expected_code in observed_codes
    )
    projection = result.to_dict()
    return {
        "schema": "rocell.arm_feedback_rehearsal.v1",
        "scenario": scenario,
        "composition": INCAPABLE_COMPOSITION,
        "status": (
            "CONTRACT_VERIFIED_INCAPABLE" if matched else "REHEARSAL_CONTRACT_FAILED"
        ),
        "expected_outcome_matched": matched,
        "expected_fault_code": expected_code,
        "observed": projection,
        "physical_authority": False,
        "actual_effect_counts": {
            "metadata_enumerations": 0,
            "device_opens": 0,
            "serial_transactions": 0,
            "robot_commands_sent": 0,
            "robot_power_operations": 0,
        },
        "durable_coordinator_authority": False,
        "arm_connected": False,
        "clock_basis": "DETERMINISTIC_VIRTUAL_CLOCK",
        "authorizer_kind": "IN_MEMORY_EXACT_FIXTURE_CHECK_NOT_PRODUCTION_AUTHORIZATION",
    }
