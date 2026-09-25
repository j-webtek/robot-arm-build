"""Strict physical-node presence wire codecs; no OS, process or device calls.

An ABSENT receipt describes two complete present-node lists for an exact physical
instance. It is not evidence of mechanical unplug cause or continuous absence.
The application still has to bind the original baseline, phase, boot report,
owned execution and fresh one-use permission. These codecs issue no authority.
"""

from dataclasses import dataclass
import re
from typing import Any

from .usb_identity_protocol import canonical, digest, _load

REQUEST_SCHEMA = "rocell.native_usb_presence_request.v1"
OBSERVATION_SCHEMA = "rocell.windows_usb_presence.v1"
READY_SCHEMA = "rocell.usb_presence_ready.v1"
RELEASE_SCHEMA = "rocell.usb_presence_release.v1"
RESULT_SCHEMA = "rocell.owned_usb_presence_result.v1"
MAX_REQUEST_BYTES = 8192
MAX_OBSERVATION_BYTES = 65536
MAX_RESULT_BYTES = MAX_OBSERVATION_BYTES + 1024
MAX_CHARS = 8192
MAX_IDS = 64
DURATION_MS = 2000
ADMISSION_TIMEOUT_MS = 5000
SAMPLE_COUNT = 2
_HASH = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_INSTANCE = re.compile(
    r"USB\\VID_[0-9A-F]{4}&PID_[0-9A-F]{4}(?:&REV_[0-9A-F]{4})?\\[^\\\x00-\x20\x7f-\uffff]+\Z",
    re.IGNORECASE | re.ASCII,
)
_REQUEST_KEYS = {
    "schema",
    "attempt_id",
    "session_id",
    "source_sha256",
    "phase_binding_sha256",
    "target_instance_id",
    "target_instance_id_sha256",
    "selected_identity_sha256",
    "operation_sha256",
    "permit_sha256",
    "helper_sha256",
    "runtime_registration_sha256",
    "request_nonce",
    "native_duration_ms",
    "admission_timeout_ms",
    "sample_count",
}
_ERRORS = {
    "CLOCK_REGRESSION",
    "CANCELLED",
    "ACQUISITION_DEADLINE",
    "SIZE_API_FAILED",
    "LIST_SIZE_LIMIT",
    "LIST_API_FAILED",
    "LIST_CAPACITY_MISMATCH",
    "MULTI_SZ_TERMINATOR_REQUIRED",
    "INSTANCE_ASCII_REQUIRED",
    "INSTANCE_LENGTH_LIMIT",
    "FILTER_RESULT_MISMATCH",
    "DUPLICATE_INSTANCE",
    "INSTANCE_COUNT_LIMIT",
    "PHYSICAL_INSTANCE_REQUIRED",
    "PHYSICAL_DEVICE_ID_REQUIRED",
    "API_EXCEPTION",
    "PRESENCE_CHANGED_DURING_ACQUISITION",
}


class UsbPresenceProtocolError(ValueError):
    pass


def _need(ok: bool, code: str = "USB_PRESENCE_INVALID") -> None:
    if not ok:
        raise UsbPresenceProtocolError(code)


def _integer(value: Any, low: int, high: int = 2**63 - 1) -> None:
    _need(type(value) is int and low <= value <= high, "INTEGER_BOUND")


def _sha(value: Any) -> None:
    _need(type(value) is str and bool(_HASH.fullmatch(value)), "HASH_REQUIRED")


def _closed(value: Any, keys: set[str]) -> None:
    _need(type(value) is dict and set(value) == keys, "EXACT_FIELDS_REQUIRED")


def physical_device_filter(instance_id: str) -> str:
    """Require the baseline's physical parent, never an endpoint or MI child."""
    _need(
        type(instance_id) is str
        and 0 < len(instance_id) < 200
        and bool(_INSTANCE.fullmatch(instance_id))
        and all(33 <= ord(c) < 127 for c in instance_id),
        "PHYSICAL_USB_INSTANCE_REQUIRED",
    )
    return instance_id.rsplit("\\", 1)[0]


@dataclass(frozen=True, slots=True)
class UsbPresenceRequest:
    payload: bytes

    def __post_init__(self) -> None:
        value = _load(self.payload, MAX_REQUEST_BYTES - 1)
        _closed(value, _REQUEST_KEYS)
        _need(value["schema"] == REQUEST_SCHEMA, "REQUEST_SCHEMA")
        for key in ("attempt_id", "session_id"):
            _need(
                type(value[key]) is str and bool(_ID.fullmatch(value[key])),
                "REQUEST_ID",
            )
        for key in _REQUEST_KEYS:
            if "sha256" in key or key == "request_nonce":
                _sha(value[key])
        for key, expected in {
            "native_duration_ms": DURATION_MS,
            "admission_timeout_ms": ADMISSION_TIMEOUT_MS,
            "sample_count": SAMPLE_COUNT,
        }.items():
            _need(
                type(value[key]) is int and value[key] == expected,
                "FIXED_BUDGET_REQUIRED",
            )
        target = value["target_instance_id"]
        physical_device_filter(target)
        _need(
            digest(target.encode("ascii")) == value["target_instance_id_sha256"],
            "TARGET_HASH",
        )

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return _load(self.payload, MAX_REQUEST_BYTES - 1)


def build_usb_presence_request(**binding: Any) -> UsbPresenceRequest:
    """Encode an existing admitted binding; this function never issues a permit."""
    _closed(
        binding,
        _REQUEST_KEYS
        - {
            "schema",
            "native_duration_ms",
            "admission_timeout_ms",
            "sample_count",
            "target_instance_id_sha256",
        },
    )
    target = binding["target_instance_id"]
    physical_device_filter(target)
    return UsbPresenceRequest(
        canonical(
            dict(
                binding,
                schema=REQUEST_SCHEMA,
                native_duration_ms=DURATION_MS,
                admission_timeout_ms=ADMISSION_TIMEOUT_MS,
                sample_count=SAMPLE_COUNT,
                target_instance_id_sha256=digest(target.encode("ascii")),
            )
        )
    )


def _moment(value: Any) -> tuple[int, int]:
    _closed(value, {"monotonic_ms", "utc_ns"})
    _integer(value["monotonic_ms"], 0)
    _integer(value["utc_ns"], 1)
    return value["monotonic_ms"], value["utc_ns"]


def _error(value: Any) -> None:
    _need(
        value is None or (type(value) is str and value in _ERRORS),
        "UNKNOWN_NATIVE_ERROR",
    )


@dataclass(frozen=True, slots=True)
class UsbPresenceObservation:
    payload: bytes

    def __post_init__(self) -> None:
        value = _load(self.payload, MAX_OBSERVATION_BYTES, canonical_required=False)
        _closed(
            value,
            {
                "schema",
                "request",
                "request_sha256",
                "provider",
                "filter",
                "scope",
                "outcome",
                "error",
                "started",
                "finished",
                "samples",
                "api_calls",
                "device_handle_opens",
                "configuration_writes",
                "frames",
                "physical_authority",
            },
        )
        _need(value["schema"] == OBSERVATION_SCHEMA)
        request = UsbPresenceRequest(canonical(value["request"]))
        _need(value["request_sha256"] == request.sha256, "REQUEST_HASH")
        target = value["request"]["target_instance_id"]
        _need(value["filter"] == physical_device_filter(target), "FILTER_BINDING")
        _need(value["scope"] == "PRESENT_PHYSICAL_USB_DEVICE_INSTANCES")
        _need(
            value["provider"] in ("WINDOWS_CONFIGURATION_MANAGER", "INCAPABLE_FIXTURE")
        )
        _need(value["outcome"] in ("PRESENT", "ABSENT", "HELD"))
        _need(value["physical_authority"] is False)
        for key in ("device_handle_opens", "configuration_writes", "frames"):
            _integer(value[key], 0, 0)
        _error(value["error"])
        start, end = _moment(value["started"]), _moment(value["finished"])
        samples = value["samples"]
        _need(type(samples) is list and len(samples) <= SAMPLE_COUNT)
        total_calls = 0
        previous = start
        timely = (
            end[0] >= start[0]
            and end[1] >= start[1]
            and end[0] - start[0] < DURATION_MS
        )
        for sample in samples:
            _closed(
                sample,
                {
                    "started",
                    "finished",
                    "required_chars",
                    "used_chars",
                    "api_calls",
                    "native_code",
                    "complete",
                    "target_present",
                    "error",
                    "instance_ids",
                },
            )
            first, last = _moment(sample["started"]), _moment(sample["finished"])
            timely = timely and all(
                previous[i] <= first[i] <= last[i] <= end[i] for i in (0, 1)
            )
            previous = last
            _integer(sample["required_chars"], 0, 2**32 - 1)
            _integer(sample["used_chars"], 0, MAX_CHARS)
            _integer(sample["api_calls"], 1, 2)
            if sample["native_code"] is not None:
                _integer(sample["native_code"], 0, 2**32 - 1)
            total_calls += sample["api_calls"]
            _need(type(sample["complete"]) is bool)
            _error(sample["error"])
            ids = sample["instance_ids"]
            _need(type(ids) is list and len(ids) <= MAX_IDS)
            # Incomplete parser traces may contain already parsed IDs. Only
            # complete lists are permitted to claim target presence or absence.
            for instance in ids:
                _need(
                    physical_device_filter(instance).upper() == value["filter"].upper(),
                    "FILTER_RESULT_MISMATCH",
                )
            _need(len({s.upper() for s in ids}) == len(ids), "DUPLICATE_INSTANCE")
            if sample["complete"]:
                _need(
                    sample["error"] is None
                    and sample["native_code"] == 0
                    and sample["api_calls"] == 2
                )
                _need(0 < sample["required_chars"] <= MAX_CHARS)
                _need(
                    sample["used_chars"]
                    == sum(len(s) + 1 for s in ids) + 1
                    <= sample["required_chars"]
                )
                _need(
                    type(sample["target_present"]) is bool
                    and sample["target_present"]
                    == (target.upper() in {s.upper() for s in ids})
                )
            else:
                _need(sample["target_present"] is None)
        _integer(value["api_calls"], 0, 4)
        _need(value["api_calls"] == total_calls, "API_COUNT_MISMATCH")
        if value["outcome"] != "HELD":
            _need(
                value["error"] is None and timely and len(samples) == SAMPLE_COUNT,
                "INCOMPLETE_OBSERVATION",
            )
            _need(
                all(
                    s["complete"]
                    and s["target_present"] == (value["outcome"] == "PRESENT")
                    for s in samples
                ),
                "PRESENCE_CONTRADICTION",
            )
        else:
            _need(value["error"] is not None, "HELD_REASON_REQUIRED")

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        self.__post_init__()
        return _load(self.payload, MAX_OBSERVATION_BYTES, canonical_required=False)

    def safe_summary(self) -> dict[str, Any]:
        value = self.to_dict()
        return dict(
            schema="rocell.usb_presence_summary.v1",
            observation_sha256=self.sha256,
            request_sha256=value["request_sha256"],
            provider=value["provider"],
            target_instance_id=value["request"]["target_instance_id"],
            outcome=value["outcome"],
            error=value["error"],
            api_calls=value["api_calls"],
            physical_authority=False,
            meaning="Two exact physical-node observations only; not unplug cause, continuous absence or qualification.",
        )


def decode_usb_presence_ready(
    payload: bytes, request: UsbPresenceRequest, *, child_pid: int
) -> dict[str, Any]:
    value = _load(payload, 1023, canonical_required=False)
    _closed(
        value, {"schema", "request_sha256", "child_pid", "challenge", "permit_sha256"}
    )
    _integer(child_pid, 1, 2**32 - 1)
    _integer(value["child_pid"], 1, 2**32 - 1)
    _sha(value["challenge"])
    _need(value["schema"] == READY_SCHEMA and value["child_pid"] == child_pid)
    _need(
        value["request_sha256"] == request.sha256
        and value["permit_sha256"] == request.to_dict()["permit_sha256"],
        "READY_BINDING",
    )
    return value


def encode_usb_presence_release(
    ready: dict[str, Any], request: UsbPresenceRequest, *, child_pid: int
) -> bytes:
    checked = decode_usb_presence_ready(canonical(ready), request, child_pid=child_pid)
    return canonical(dict(checked, schema=RELEASE_SCHEMA))


def decode_usb_presence_result(
    payload: bytes,
    request: UsbPresenceRequest,
    *,
    child_pid: int,
    challenge: str,
    expected_provider: str
) -> UsbPresenceObservation:
    value = _load(payload, MAX_RESULT_BYTES, canonical_required=False)
    _closed(
        value,
        {
            "schema",
            "request_sha256",
            "child_pid",
            "challenge_sha256",
            "permit_sha256",
            "observation",
        },
    )
    _integer(child_pid, 1, 2**32 - 1)
    _integer(value["child_pid"], 1, 2**32 - 1)
    _sha(challenge)
    _need(expected_provider in ("WINDOWS_CONFIGURATION_MANAGER", "INCAPABLE_FIXTURE"))
    _need(value["schema"] == RESULT_SCHEMA and value["child_pid"] == child_pid)
    _need(
        value["request_sha256"] == request.sha256
        and value["challenge_sha256"] == digest(challenge.encode("ascii"))
        and value["permit_sha256"] == request.to_dict()["permit_sha256"],
        "RESULT_BINDING",
    )
    observation = UsbPresenceObservation(canonical(value["observation"]))
    observed = observation.to_dict()
    _need(
        observed["request"] == request.to_dict()
        and observed["provider"] == expected_provider,
        "RESULT_PROVIDER_BINDING",
    )
    return observation
