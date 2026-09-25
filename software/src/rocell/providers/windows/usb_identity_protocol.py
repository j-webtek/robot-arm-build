"""Pure USB-observation admission and receipt contracts; no OS or device calls.

USB descriptor queries are a distinct owned operation, never a metadata-only
camera grant. Encoding RELEASE does not consume a permit or authorize dispatch:
the owning application must revalidate its consumed scope before sending it.
An OBSERVED receipt describes identity evidence, not camera qualification.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

REQUEST_SCHEMA = "rocell.native_usb_identity_admission_request.v1"
READY_SCHEMA = "rocell.native_usb_identity_admission_ready.v1"
RELEASE_SCHEMA = "rocell.native_usb_identity_admission_release.v1"
RESULT_SCHEMA = "rocell.owned_usb_identity_result.v1"
OBSERVATION_SCHEMA = "rocell.windows_usb_identity.v1"
MAX_REQUEST_BYTES = 16 * 1024
MAX_HANDSHAKE_BYTES = 1024
MAX_OBSERVATION_BYTES = 64 * 1024
MAX_RESULT_BYTES = MAX_OBSERVATION_BYTES + 1024
NATIVE_DURATION_MS = 10000
ADMISSION_TIMEOUT_MS = 5000
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_REQUEST_FIELDS = {
    "schema",
    "attempt_id",
    "session_id",
    "source_sha256",
    "operation_sha256",
    "selected_identity_sha256",
    "native_identity_sha256",
    "endpoint",
    "endpoint_sha256",
    "expected_device_instance_id",
    "expected_device_instance_id_sha256",
    "helper_sha256",
    "runtime_registration_sha256",
    "permit_sha256",
    "native_duration_ms",
    "admission_timeout_ms",
}


class UsbIdentityProtocolError(ValueError):
    """Fixed error codes avoid reflecting raw USB paths into UI errors."""

    def __init__(self, code: str) -> None:
        self.code = code
        super().__init__(code)


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise UsbIdentityProtocolError(code)


def canonical(value: Any) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("ascii")
    except (ValueError, TypeError, UnicodeError, RecursionError) as error:
        raise UsbIdentityProtocolError("INVALID_JSON_VALUE") from error


def digest(value: bytes) -> str:
    _require(type(value) is bytes, "EXACT_BYTES_REQUIRED")
    return hashlib.sha256(value).hexdigest()


def _sha(value: Any) -> None:
    _require(type(value) is str and bool(_SHA.fullmatch(value)), "INVALID_SHA256")


def _integer(value: Any, low: int, high: int) -> None:
    _require(type(value) is int and low <= value <= high, "INTEGER_BOUND")


def _text(value: Any, maximum: int = 4096) -> None:
    _require(type(value) is str and bool(value), "TEXT_REQUIRED")
    try:
        encoded = value.encode("utf-8", errors="strict")
    except UnicodeError as error:
        raise UsbIdentityProtocolError("INVALID_TEXT_ENCODING") from error
    _require(
        len(encoded) <= maximum
        and not any(ord(char) < 32 or ord(char) == 127 for char in value),
        "TEXT_BOUND",
    )


def _closed(value: Any, names: set[str]) -> None:
    _require(type(value) is dict and set(value) == names, "EXACT_FIELDS_REQUIRED")


def _load(payload: bytes, maximum: int, *, canonical_required: bool = True) -> dict:
    _require(type(payload) is bytes and 0 < len(payload) <= maximum, "BYTE_LIMIT")

    def pairs(items: list[tuple[str, Any]]) -> dict:
        result: dict[str, Any] = {}
        for key, value in items:
            _require(key not in result, "DUPLICATE_KEY")
            result[key] = value
        return result

    def number(_: str) -> Any:
        raise UsbIdentityProtocolError("INTEGER_JSON_REQUIRED")

    try:
        value = json.loads(
            payload.decode("ascii" if canonical_required else "utf-8"),
            object_pairs_hook=pairs,
            parse_float=number,
            parse_constant=number,
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError, ValueError) as error:
        if isinstance(error, UsbIdentityProtocolError):
            raise
        raise UsbIdentityProtocolError("INVALID_JSON") from error
    _require(type(value) is dict, "OBJECT_REQUIRED")
    pending = [(value, 0)]
    nodes = 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        _require(depth <= 12 and nodes <= 8192, "STRUCTURE_LIMIT")
        if type(item) is dict:
            pending.extend((child, depth + 1) for child in item.values())
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
    if canonical_required:
        _require(canonical(value) == payload, "CANONICAL_JSON_REQUIRED")
    return value


@dataclass(frozen=True, slots=True)
class UsbIdentityAdmissionRequest:
    payload: bytes

    def __post_init__(self) -> None:
        value = _load(self.payload, MAX_REQUEST_BYTES - 1)
        _closed(value, _REQUEST_FIELDS)
        _require(value["schema"] == REQUEST_SCHEMA, "REQUEST_SCHEMA")
        for key in _REQUEST_FIELDS - {
            "schema",
            "attempt_id",
            "session_id",
            "endpoint",
            "expected_device_instance_id",
            "native_duration_ms",
            "admission_timeout_ms",
        }:
            _sha(value[key])
        for key in ("attempt_id", "session_id"):
            _require(
                type(value[key]) is str and bool(_ID.fullmatch(value[key])),
                "REQUEST_ID",
            )
        for key in ("endpoint", "expected_device_instance_id"):
            _text(value[key])
            _require(
                digest(value[key].encode("utf-8")) == value[key + "_sha256"],
                "REQUEST_TARGET_HASH",
            )
        _integer(value["native_duration_ms"], NATIVE_DURATION_MS, NATIVE_DURATION_MS)
        _integer(
            value["admission_timeout_ms"], ADMISSION_TIMEOUT_MS, ADMISSION_TIMEOUT_MS
        )

    @property
    def request_sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_REQUEST_BYTES - 1)

    def wire(self) -> bytes:
        return self.payload + b"\n"


@dataclass(frozen=True, slots=True)
class UsbIdentityReady:
    payload: bytes

    def __post_init__(self) -> None:
        value = _load(self.payload, MAX_HANDSHAKE_BYTES - 1)
        _closed(value, {"schema", "request_sha256", "child_pid", "challenge"})
        _require(value["schema"] == READY_SCHEMA, "READY_SCHEMA")
        _sha(value["request_sha256"])
        _sha(value["challenge"])
        _integer(value["child_pid"], 1, 2**32 - 1)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_HANDSHAKE_BYTES - 1)

    @property
    def challenge_sha256(self) -> str:
        return digest(self.to_dict()["challenge"].encode("ascii"))


def parse_usb_identity_ready(
    wire: bytes,
    *,
    expected_request_sha256: str,
    expected_child_pid: int,
) -> UsbIdentityReady:
    _sha(expected_request_sha256)
    _integer(expected_child_pid, 1, 2**32 - 1)
    _require(
        type(wire) is bytes
        and len(wire) <= MAX_HANDSHAKE_BYTES
        and wire.endswith(b"\n")
        and wire.count(b"\n") == 1,
        "ONE_READY_LINE_REQUIRED",
    )
    ready = UsbIdentityReady(wire[:-1])
    value = ready.to_dict()
    _require(
        value["request_sha256"] == expected_request_sha256
        and value["child_pid"] == expected_child_pid,
        "READY_OWNED_CHILD_BINDING",
    )
    return ready


def usb_identity_release(
    request: UsbIdentityAdmissionRequest, ready: UsbIdentityReady
) -> bytes:
    """Encode only; no dispatcher, permit consumption or device access here."""
    _require(
        type(request) is UsbIdentityAdmissionRequest
        and type(ready) is UsbIdentityReady,
        "EXACT_ADMISSION_TYPES",
    )
    request, ready = UsbIdentityAdmissionRequest(request.payload), UsbIdentityReady(
        ready.payload
    )
    _require(
        ready.to_dict()["request_sha256"] == request.request_sha256,
        "RELEASE_REQUEST_BINDING",
    )
    return (
        canonical(
            {
                "schema": RELEASE_SCHEMA,
                "request_sha256": request.request_sha256,
                "child_pid": ready.to_dict()["child_pid"],
                "challenge_sha256": ready.challenge_sha256,
                "permit_sha256": request.to_dict()["permit_sha256"],
            }
        )
        + b"\n"
    )


_ERROR_CODES = {
    "NOT_REQUESTED",
    "REQUEST_INVALID",
    "ENDPOINT_MISMATCH",
    "DEVICE_CHANGED",
    "USB_ANCESTOR_MISSING",
    "ANCESTRY_AMBIGUOUS",
    "HUB_MAPPING_MISSING",
    "HUB_MAPPING_AMBIGUOUS",
    "PORT_MISMATCH",
    "NOT_CONNECTED",
    "SERIAL_NOT_PRESENT",
    "SERIAL_AMBIGUOUS",
    "DESCRIPTOR_MALFORMED",
    "UTF16_INVALID",
    "PROPERTY_TYPE",
    "BYTE_LIMIT",
    "CALL_LIMIT",
    "HOP_LIMIT",
    "TIMEOUT",
    "CANCELLED",
    "API_FAILED",
    "CLOSE_FAILED",
    "POST_MAPPING_FAILED",
}
_OPERATIONS = {
    "MAP_ENDPOINT",
    "DEVICE_ID",
    "PARENT",
    "DRIVER_KEY_PROPERTY",
    "HUB_INTERFACE",
    "HOST_CONTROLLER_PROPERTY",
    "OPEN_HUB",
    "HUB_INFORMATION",
    "CONNECTION_DRIVER_KEY",
    "CONNECTION_EX",
    "CONNECTION_EX_V2",
    "DEVICE_DESCRIPTOR",
    "LANGUAGE_DESCRIPTOR",
    "SERIAL_DESCRIPTOR",
    "CLOSE_HUB",
}
_IOCTLS = {
    "HUB_INFORMATION",
    "CONNECTION_DRIVER_KEY",
    "CONNECTION_EX",
    "CONNECTION_EX_V2",
    "DEVICE_DESCRIPTOR",
    "LANGUAGE_DESCRIPTOR",
    "SERIAL_DESCRIPTOR",
}
_DESCRIPTORS = {"DEVICE_DESCRIPTOR", "LANGUAGE_DESCRIPTOR", "SERIAL_DESCRIPTOR"}
_RAW_OPERATIONS = _DESCRIPTORS | {"CONNECTION_EX", "CONNECTION_EX_V2"}
_ACCOUNTING = {
    "api_calls",
    "hub_open_attempts",
    "hub_open_successes",
    "ioctl_attempts",
    "ioctl_successes",
    "descriptor_requests",
    "close_attempts",
    "close_successes",
    "peak_open_handles",
    "remaining_open_handles",
    "returned_bytes",
}
_MAPPING_FIELDS = {
    "returned_endpoint",
    "endpoint_instance_id",
    "physical_usb_instance_id",
    "physical_driver_key",
    "host_controller_instance_id",
    "hops",
}
_LINK_FLAGS = (
    "operating_superspeed_or_higher",
    "capable_superspeed_or_higher",
    "operating_superspeed_plus_or_higher",
    "capable_superspeed_plus_or_higher",
)


def _raw(value: Any, maximum: int) -> bytes:
    _require(
        type(value) is str
        and len(value) <= maximum * 2
        and len(value) % 2 == 0
        and bool(re.fullmatch(r"[0-9a-f]*", value)),
        "RAW_HEX_BOUND",
    )
    return bytes.fromhex(value)


def _u16(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset : offset + 2], "little")


def _u32(raw: bytes, offset: int) -> int:
    return int.from_bytes(raw[offset : offset + 4], "little")


def _valid_ex(raw: bytes) -> bool:
    return (
        len(raw) >= 35
        and 1 <= _u32(raw, 0) <= 255
        and raw[23] <= 3
        and raw[24] <= 1
        and _u32(raw, 31) <= 10
        and 35 + 11 * _u32(raw, 27) <= len(raw)
    )


def _mapping(value: Any) -> bool:
    if value is None:
        return False
    _closed(value, _MAPPING_FIELDS)
    complete = True
    for key in _MAPPING_FIELDS - {"hops"}:
        if value[key] is None:
            complete = False
        else:
            _text(value[key])
    _require(type(value["hops"]) is list and len(value["hops"]) <= 8, "HOP_LIMIT")
    hubs: set[str] = set()
    interfaces: set[str] = set()
    for hop in value["hops"]:
        _closed(
            hop,
            {
                "hub_instance_id",
                "hub_interface_path",
                "connection_index",
                "downstream_driver_key",
            },
        )
        for key in ("hub_instance_id", "hub_interface_path", "downstream_driver_key"):
            _text(hop[key])
        _integer(hop["connection_index"], 1, 255)
        _require(
            hop["hub_instance_id"].casefold() not in hubs
            and hop["hub_interface_path"].casefold() not in interfaces,
            "MAPPING_CYCLE",
        )
        hubs.add(hop["hub_instance_id"].casefold())
        interfaces.add(hop["hub_interface_path"].casefold())
    if value["hops"] and value["physical_driver_key"] is not None:
        _require(
            value["hops"][0]["downstream_driver_key"].casefold()
            == value["physical_driver_key"].casefold(),
            "PHYSICAL_PORT_DRIVER_KEY",
        )
    return complete and bool(value["hops"])


def _device_descriptor(value: Any) -> bool:
    if value is None:
        return False
    fields = {"vid", "pid", "bcd_usb", "i_serial_number"}
    _closed(value, {"raw_hex", *fields})
    raw = _raw(value["raw_hex"], 18)
    valid = len(raw) == 18 and raw[:2] == b"\x12\x01"
    if not valid:
        _require(all(value[key] is None for key in fields), "MALFORMED_DEVICE_FIELDS")
        return False
    expected = {
        "vid": f"{_u16(raw, 8):04x}",
        "pid": f"{_u16(raw, 10):04x}",
        "bcd_usb": _u16(raw, 2),
        "i_serial_number": raw[16],
    }
    _integer(value["bcd_usb"], 0, 65535)
    _integer(value["i_serial_number"], 0, 255)
    _require(
        all(value[key] == field for key, field in expected.items()),
        "DEVICE_DESCRIPTOR_DECODE",
    )
    return True


def _string_bytes(raw: bytes) -> bool:
    return (
        2 <= len(raw) <= 255
        and len(raw) % 2 == 0
        and raw[0] == len(raw)
        and raw[1] == 3
    )


def _languages(value: Any) -> list[int] | None:
    if value is None:
        return None
    _closed(value, {"raw_hex", "language_ids"})
    raw = _raw(value["raw_hex"], 255)
    ids = value["language_ids"]
    _require(type(ids) is list and len(ids) <= 4, "LANGUAGE_LIMIT")
    for language in ids:
        _integer(language, 1, 65535)
    # Over-budget or duplicate language lists remain malformed evidence. No
    # prefix of a device's list is promoted as if every language were checked.
    decoded = (
        [_u16(raw, i) for i in range(2, len(raw), 2)] if _string_bytes(raw) else []
    )
    valid = (
        1 <= len(decoded) <= 4
        and len(set(decoded)) == len(decoded)
        and 0 not in decoded
    )
    _require(ids == (decoded if valid else []), "LANGUAGE_DESCRIPTOR_DECODE")
    return decoded if valid else None


def _serial_descriptors(value: Any, languages: list[int] | None) -> list[str | None]:
    _require(type(value) is list and len(value) <= 4, "SERIAL_DESCRIPTOR_LIMIT")
    observed: list[str | None] = []
    for index, item in enumerate(value):
        _closed(item, {"language_id", "raw_hex", "value"})
        _integer(item["language_id"], 1, 65535)
        _require(
            languages is not None
            and index < len(languages)
            and item["language_id"] == languages[index],
            "SERIAL_LANGUAGE_BINDING",
        )
        raw = _raw(item["raw_hex"], 255)
        decoded = None
        if _string_bytes(raw):
            try:
                candidate = raw[2:].decode("utf-16-le", errors="strict")
                _text(candidate, 512)
                decoded = candidate
            except (UnicodeError, UsbIdentityProtocolError):
                pass
        _require(item["value"] == decoded, "SERIAL_DESCRIPTOR_DECODE")
        observed.append(decoded)
    return observed


def _link(value: Any) -> tuple[bool, int | None]:
    if value is None:
        return False, None
    _closed(
        value,
        {
            "connection_status",
            "ex_speed",
            "ex_v2_available",
            "supported_usb_protocols",
            *_LINK_FLAGS,
            "ex_raw_hex",
            "ex_v2_raw_hex",
        },
    )
    raw = _raw(value["ex_raw_hex"], 4096)
    ex_valid = _valid_ex(raw)
    if ex_valid:
        _integer(value["connection_status"], 0, 10)
        _integer(value["ex_speed"], 0, 3)
        _require(
            value["connection_status"] == _u32(raw, 31)
            and value["ex_speed"] == raw[23],
            "LINK_EX_DECODE",
        )
    else:
        _require(
            value["connection_status"] is value["ex_speed"] is None,
            "MALFORMED_EX_FIELDS",
        )
    _require(type(value["ex_v2_available"]) is bool, "V2_AVAILABILITY_TYPE")
    if not value["ex_v2_available"]:
        _require(
            value["ex_v2_raw_hex"] is None
            and all(
                value[key] is None for key in ("supported_usb_protocols", *_LINK_FLAGS)
            ),
            "V2_UNAVAILABLE_FIELDS",
        )
    else:
        v2 = _raw(value["ex_v2_raw_hex"], 16)
        valid = (
            len(v2) == 16
            and 1 <= _u32(v2, 0) <= 255
            and _u32(v2, 4) == 16
            and _u32(v2, 8) <= 7
            and _u32(v2, 12) <= 15
            and not (_u32(v2, 12) & 4 and not _u32(v2, 12) & 1)
            and ex_valid
            and _u32(v2, 0) == _u32(raw, 0)
        )
        if valid:
            _integer(value["supported_usb_protocols"], 0, 7)
            _require(
                value["supported_usb_protocols"] == _u32(v2, 8), "LINK_PROTOCOL_DECODE"
            )
            for bit, key in enumerate(_LINK_FLAGS):
                _require(
                    type(value[key]) is bool
                    and value[key] == bool(_u32(v2, 12) & (1 << bit)),
                    "LINK_FLAG_DECODE",
                )
        else:
            _require(
                all(
                    value[key] is None
                    for key in ("supported_usb_protocols", *_LINK_FLAGS)
                ),
                "MALFORMED_V2_FIELDS",
            )
            return False, _u32(raw, 0) if ex_valid else None
    return ex_valid, _u32(raw, 0) if ex_valid else None


def _accounting(calls: Any, claimed: Any) -> None:
    _require(type(calls) is list and len(calls) <= 128, "CALL_LIMIT")
    _closed(claimed, _ACCOUNTING)
    for value in claimed.values():
        _integer(value, 0, 128 * 4096)
    derived = dict.fromkeys(_ACCOUNTING, 0)
    live: set[int] = set()
    closed: set[int] = set()
    last_phase = 0
    for sequence, call in enumerate(calls, 1):
        _closed(
            call,
            {
                "sequence",
                "phase",
                "operation",
                "handle_id",
                "target_id",
                "connection_index",
                "requested_bytes",
                "returned_bytes",
                "status",
                "error_domain",
                "error_code",
                "observed_text",
                "observed_number",
                "descriptor_index",
                "language_id",
                "returned_raw_hex",
            },
        )
        _integer(call["sequence"], sequence, sequence)
        _require(call["phase"] in ("PRE", "OBSERVE", "POST", "CLEANUP"), "CALL_PHASE")
        op = call["operation"]
        _require(type(op) is str and op in _OPERATIONS, "CALL_OPERATION")
        _require(
            (op == "CLOSE_HUB") == (call["phase"] == "CLEANUP"), "CLEANUP_PHASE_BINDING"
        )
        if call["phase"] != "CLEANUP":
            phase_index = ("PRE", "OBSERVE", "POST").index(call["phase"])
            _require(phase_index >= last_phase, "CALL_PHASE_ORDER")
            last_phase = phase_index
        if op in _DESCRIPTORS:
            _integer(call["descriptor_index"], 0, 255)
            _integer(call["language_id"], 0, 65535)
            if op == "SERIAL_DESCRIPTOR":
                _require(
                    call["descriptor_index"] > 0 and call["language_id"] > 0,
                    "SERIAL_QUERY_PARAMETERS",
                )
            else:
                _require(
                    call["descriptor_index"] == call["language_id"] == 0,
                    "DESCRIPTOR_QUERY_PARAMETERS",
                )
        else:
            _require(
                call["descriptor_index"] is call["language_id"] is None,
                "NONDESCRIPTOR_QUERY_PARAMETERS",
            )
        _require(call["status"] in ("OK", "ERROR"), "CALL_STATUS")
        _require(
            call["error_domain"] in ("NONE", "WIN32", "CM", "CONTRACT"),
            "CALL_ERROR_DOMAIN",
        )
        _integer(call["error_code"], 0, 2**32 - 1)
        ok = call["status"] == "OK"
        _require(
            (
                (call["error_domain"] == "NONE" and call["error_code"] == 0)
                if ok
                else call["error_domain"] != "NONE"
            ),
            "CALL_ERROR_BINDING",
        )
        for key, low, high in (
            ("handle_id", 1, 32),
            ("target_id", 0, 2**32 - 1),
            ("connection_index", 1, 255),
        ):
            if call[key] is not None:
                _integer(call[key], low, high)
        _integer(call["requested_bytes"], 0, 4096)
        _integer(call["returned_bytes"], 0, call["requested_bytes"])
        if ok and op in _RAW_OPERATIONS:
            maximum = {
                "DEVICE_DESCRIPTOR": 18,
                "LANGUAGE_DESCRIPTOR": 255,
                "SERIAL_DESCRIPTOR": 255,
                "CONNECTION_EX": 4096,
                "CONNECTION_EX_V2": 16,
            }[op]
            observed_raw = _raw(call["returned_raw_hex"], maximum)
            _require(
                call["returned_bytes"]
                == len(observed_raw) + (12 if op in _DESCRIPTORS else 0),
                "CALL_RAW_BYTE_BINDING",
            )
        else:
            _require(call["returned_raw_hex"] is None, "CALL_RAW_AVAILABILITY")
        # A composite metadata read can succeed before its information-set
        # cleanup fails; retain those actual bytes while withholding its join.
        # Failed device IOCTLs never claim that their output was observed.
        if not ok and op in _IOCTLS | {"OPEN_HUB", "CLOSE_HUB"}:
            _require(call["returned_bytes"] == 0, "FAILED_CALL_BYTES")
        if call["observed_text"] is not None:
            _text(call["observed_text"])
        if ok and op in {"MAP_ENDPOINT", "PARENT", "HUB_INFORMATION"}:
            _integer(
                call["observed_number"],
                1,
                255 if op == "HUB_INFORMATION" else 2**32 - 1,
            )
        else:
            _require(call["observed_number"] is None, "CALL_NUMBER_BINDING")
        derived["api_calls"] += 1
        derived["returned_bytes"] += call["returned_bytes"]
        token = call["handle_id"]
        if op == "OPEN_HUB":
            derived["hub_open_attempts"] += 1
            _require(
                token == derived["hub_open_attempts"] and token <= 32,
                "OPEN_TOKEN_SEQUENCE",
            )
            _require(not live, "ONE_LIVE_HUB_HANDLE")
            if ok:
                live.add(token)
                derived["hub_open_successes"] += 1
                derived["peak_open_handles"] = 1
        elif op == "CLOSE_HUB":
            _require(token in live and token not in closed, "CLOSE_OWNERSHIP")
            closed.add(token)
            derived["close_attempts"] += 1
            if ok:
                live.remove(token)
                derived["close_successes"] += 1
        elif op in _IOCTLS:
            _require(token in live and token not in closed, "IOCTL_HANDLE_OWNERSHIP")
            derived["ioctl_attempts"] += 1
            derived["ioctl_successes"] += int(ok)
            derived["descriptor_requests"] += int(op in _DESCRIPTORS)
        else:
            _require(token is None, "METADATA_HANDLE_TOKEN")
    derived["remaining_open_handles"] = len(live)
    _require(derived == claimed, "TRACE_ACCOUNTING_MISMATCH")


def _observed_trace_coverage(value: dict[str, Any]) -> None:
    """Join retained claims to the closed call trace, including all hub ports.

    This verifies internal provenance, not attestation of a hostile provider.
    The producer still needs the separately pinned/owned execution boundary.
    CM node tokens are meaningful only within this one observation.
    """
    calls = value["calls"]
    for phase, mapping in (
        ("PRE", value["pre_mapping"]),
        ("POST", value["post_mapping"]),
    ):
        rows = [row for row in calls if row["phase"] == phase]
        used: set[int] = set()

        def one(op: str, **match: Any) -> dict[str, Any]:
            found = [
                row
                for row in rows
                if row["operation"] == op
                and row["status"] == "OK"
                and all(row[key] == item for key, item in match.items())
            ]
            _require(len(found) == 1, "MAPPING_TRACE_COVERAGE")
            used.add(found[0]["sequence"])
            return found[0]

        mapped = one("MAP_ENDPOINT", observed_text=mapping["returned_endpoint"])
        current = mapped["observed_number"]
        one(
            "DEVICE_ID",
            target_id=current,
            observed_text=mapping["endpoint_instance_id"],
        )
        seen = {current}
        hop_index = 0
        parent_rows = [row for row in rows if row["operation"] == "PARENT"]
        _require(bool(parent_rows) and len(parent_rows) <= 24, "PARENT_TRACE_COVERAGE")
        for parent in parent_rows:
            used.add(parent["sequence"])
            _require(
                parent["status"] == "OK" and parent["target_id"] == current,
                "PARENT_TRACE_CHAIN",
            )
            node = parent["observed_number"]
            _require(node not in seen, "PARENT_TRACE_CYCLE")
            seen.add(node)
            interface = one("HUB_INTERFACE", target_id=node)
            if interface["observed_text"] is not None:
                _require(hop_index < len(mapping["hops"]), "HOP_TRACE_COUNT")
                hop = mapping["hops"][hop_index]
                _require(
                    interface["observed_text"] == hop["hub_interface_path"],
                    "HUB_INTERFACE_TRACE",
                )
                one("DEVICE_ID", target_id=node, observed_text=hop["hub_instance_id"])
                one(
                    "DRIVER_KEY_PROPERTY",
                    target_id=current,
                    observed_text=hop["downstream_driver_key"],
                )
                if hop_index == 0:
                    one(
                        "DEVICE_ID",
                        target_id=current,
                        observed_text=mapping["physical_usb_instance_id"],
                    )
                opened = one("OPEN_HUB", target_id=node)
                token = opened["handle_id"]
                ports = one("HUB_INFORMATION", handle_id=token)["observed_number"]
                scans = [
                    row
                    for row in rows
                    if row["operation"] == "CONNECTION_EX" and row["handle_id"] == token
                ]
                _require(
                    len(scans) == ports
                    and [row["connection_index"] for row in scans]
                    == list(range(1, ports + 1))
                    and all(row["status"] == "OK" for row in scans),
                    "COMPLETE_PORT_SCAN_REQUIRED",
                )
                connected = []
                for scan in scans:
                    used.add(scan["sequence"])
                    raw = _raw(scan["returned_raw_hex"], 4096)
                    _require(
                        _valid_ex(raw)
                        and _u32(raw, 0) == scan["connection_index"]
                        and _u32(raw, 31) in (0, 1),
                        "PORT_SCAN_RAW_BINDING",
                    )
                    if _u32(raw, 31) == 1:
                        connected.append(scan["connection_index"])
                port_keys = [
                    row
                    for row in rows
                    if row["operation"] == "CONNECTION_DRIVER_KEY"
                    and row["handle_id"] == token
                ]
                _require(
                    [row["connection_index"] for row in port_keys] == connected
                    and all(row["status"] == "OK" for row in port_keys),
                    "CONNECTED_PORT_DRIVER_COVERAGE",
                )
                used.update(row["sequence"] for row in port_keys)
                matches = [
                    row
                    for row in rows
                    if row["operation"] == "CONNECTION_DRIVER_KEY"
                    and row["handle_id"] == token
                    and row["status"] == "OK"
                    and row["observed_text"] == hop["downstream_driver_key"]
                ]
                _require(
                    len(matches) == 1
                    and matches[0]["connection_index"] == hop["connection_index"],
                    "UNAMBIGUOUS_PORT_TRACE",
                )
                hop_index += 1
            elif hop_index:
                host = one("HOST_CONTROLLER_PROPERTY", target_id=node)
                _require(
                    host["observed_text"] is not None and parent is parent_rows[-1],
                    "HOST_CONTROLLER_TRACE",
                )
                one(
                    "DEVICE_ID",
                    target_id=node,
                    observed_text=mapping["host_controller_instance_id"],
                )
            current = node
        _require(hop_index == len(mapping["hops"]), "HOP_TRACE_COUNT")
        one("HOST_CONTROLLER_PROPERTY", target_id=current)
        _require(used == {row["sequence"] for row in rows}, "UNACCOUNTED_MAPPING_CALL")

    observations = [row for row in calls if row["phase"] == "OBSERVE"]
    observation_opens = [
        row
        for row in observations
        if row["operation"] == "OPEN_HUB" and row["status"] == "OK"
    ]
    _require(len(observation_opens) == 1, "OBSERVATION_OPEN_TRACE")
    token = observation_opens[0]["handle_id"]
    port = value["pre_mapping"]["hops"][0]["connection_index"]
    expected = [
        ("CONNECTION_EX", value["link"]["ex_raw_hex"], 0),
        ("DEVICE_DESCRIPTOR", value["device_descriptor"]["raw_hex"], 12),
        ("LANGUAGE_DESCRIPTOR", value["languages"]["raw_hex"], 12),
        *(
            ("SERIAL_DESCRIPTOR", item["raw_hex"], 12)
            for item in value["serial_descriptors"]
        ),
    ]
    _require(
        [row["operation"] for row in observations]
        == [
            "OPEN_HUB",
            "CONNECTION_EX",
            "CONNECTION_EX_V2",
            "DEVICE_DESCRIPTOR",
            "LANGUAGE_DESCRIPTOR",
            *("SERIAL_DESCRIPTOR" for _ in value["serial_descriptors"]),
        ],
        "EXACT_OBSERVATION_CALL_SEQUENCE",
    )
    observed_rows = [
        row
        for row in observations
        if row["operation"] in _DESCRIPTORS | {"CONNECTION_EX"}
    ]
    _require(len(observed_rows) == len(expected), "DESCRIPTOR_TRACE_COUNT")
    for row, (op, raw, header) in zip(observed_rows, expected):
        _require(
            row["operation"] == op
            and row["status"] == "OK"
            and row["handle_id"] == token
            and row["connection_index"] == port
            and row["returned_bytes"] == len(raw) // 2 + header,
            "DESCRIPTOR_TRACE_BINDING",
        )
    serial_rows = [
        row for row in observed_rows if row["operation"] == "SERIAL_DESCRIPTOR"
    ]
    for row, serial in zip(serial_rows, value["serial_descriptors"]):
        _require(
            row["descriptor_index"] == value["device_descriptor"]["i_serial_number"]
            and row["language_id"] == serial["language_id"],
            "SERIAL_QUERY_PROVENANCE",
        )
    v2 = [row for row in observations if row["operation"] == "CONNECTION_EX_V2"]
    _require(
        len(v2) == 1
        and v2[0]["handle_id"] == token
        and v2[0]["connection_index"] == port,
        "V2_TRACE_BINDING",
    )
    _require(
        (
            (v2[0]["status"] == "OK" and v2[0]["returned_bytes"] == 16)
            if value["link"]["ex_v2_available"]
            else v2[0]["status"] == "ERROR"
        ),
        "V2_TRACE_AVAILABILITY",
    )


def _retained_raw_bindings(value: dict[str, Any]) -> None:
    """Even HELD projections must preserve the actual returned payload bytes."""
    observed = [
        row
        for row in value["calls"]
        if row["phase"] == "OBSERVE" and row["status"] == "OK"
    ]
    subjects = []
    for op, key in (
        ("DEVICE_DESCRIPTOR", "device_descriptor"),
        ("LANGUAGE_DESCRIPTOR", "languages"),
    ):
        if value[key] is not None:
            subjects.append((op, value[key]["raw_hex"]))
    if value["link"] is not None:
        subjects.append(("CONNECTION_EX", value["link"]["ex_raw_hex"]))
        if value["link"]["ex_v2_raw_hex"] is not None:
            subjects.append(("CONNECTION_EX_V2", value["link"]["ex_v2_raw_hex"]))
    for op, raw in subjects:
        matching = [row for row in observed if row["operation"] == op]
        _require(
            len(matching) == 1 and matching[0]["returned_raw_hex"] == raw,
            "RETAINED_RAW_SUBJECT_BINDING",
        )
    serial_rows = [row for row in observed if row["operation"] == "SERIAL_DESCRIPTOR"]
    serials = value["serial_descriptors"]
    _require(
        len(serial_rows) == len(serials)
        and all(
            row["returned_raw_hex"] == item["raw_hex"]
            and row["language_id"] == item["language_id"]
            for row, item in zip(serial_rows, serials)
        ),
        "RETAINED_SERIAL_RAW_BINDING",
    )


@dataclass(frozen=True, slots=True)
class UsbIdentityObservation:
    """Owned immutable evidence bytes, including correctly accounted HELD runs."""

    payload: bytes

    def __post_init__(self) -> None:
        value = _load(self.payload, MAX_OBSERVATION_BYTES)
        _closed(
            value,
            {
                "schema",
                "request_sha256",
                "requested_endpoint",
                "expected_device_instance_id",
                "outcome",
                "pre_mapping",
                "post_mapping",
                "device_descriptor",
                "languages",
                "serial_descriptors",
                "link",
                "accounting",
                "calls",
                "error",
                "elapsed_ms",
            },
        )
        _require(value["schema"] == OBSERVATION_SCHEMA, "OBSERVATION_SCHEMA")
        _sha(value["request_sha256"])
        _text(value["requested_endpoint"])
        _text(value["expected_device_instance_id"])
        _require(value["outcome"] in ("OBSERVED", "HELD"), "OBSERVATION_OUTCOME")
        _integer(value["elapsed_ms"], 0, 2**32 - 1)
        error = value["error"]
        if error is not None:
            _closed(error, {"code", "domain", "native_code"})
            _require(
                type(error["code"]) is str and error["code"] in _ERROR_CODES,
                "ERROR_REASON",
            )
            _require(
                error["domain"] in ("NONE", "WIN32", "CM", "CONTRACT"), "ERROR_DOMAIN"
            )
            _integer(error["native_code"], 0, 2**32 - 1)
        pre_complete = _mapping(value["pre_mapping"])
        post_complete = _mapping(value["post_mapping"])
        device_valid = _device_descriptor(value["device_descriptor"])
        languages = _languages(value["languages"])
        serials = _serial_descriptors(value["serial_descriptors"], languages)
        link_valid, port = _link(value["link"])
        _accounting(value["calls"], value["accounting"])
        _retained_raw_bindings(value)
        if value["outcome"] == "HELD":
            _require(error is not None, "HELD_REASON_REQUIRED")
            return
        _require(
            error is None and value["elapsed_ms"] < NATIVE_DURATION_MS,
            "OBSERVED_ERROR_OR_DEADLINE",
        )
        _require(
            pre_complete
            and post_complete
            and value["pre_mapping"] == value["post_mapping"],
            "OBSERVED_STABLE_MAPPING",
        )
        mapping = value["pre_mapping"]
        _require(
            mapping["returned_endpoint"] == value["requested_endpoint"]
            and mapping["endpoint_instance_id"] == value["expected_device_instance_id"],
            "OBSERVED_SELECTED_TARGET",
        )
        _require(
            device_valid
            and value["device_descriptor"]["i_serial_number"] != 0
            and languages is not None
            and len(serials) == len(languages)
            and bool(serials)
            and all(serial is not None for serial in serials)
            and len(set(serials)) == 1,
            "OBSERVED_DESCRIPTOR_IDENTITY",
        )
        physical_usb = re.match(
            r"USB\\VID_([0-9a-f]{4})&PID_([0-9a-f]{4})(?:&[^\\]+)?\\",
            mapping["physical_usb_instance_id"],
            re.IGNORECASE,
        )
        _require(
            physical_usb is not None
            and physical_usb.group(1).lower() == value["device_descriptor"]["vid"]
            and physical_usb.group(2).lower() == value["device_descriptor"]["pid"],
            "PHYSICAL_USB_DESCRIPTOR_BINDING",
        )
        _require(
            link_valid
            and value["link"]["connection_status"] == 1
            and port == mapping["hops"][0]["connection_index"],
            "OBSERVED_CONNECTED_PORT",
        )
        ex_raw = _raw(value["link"]["ex_raw_hex"], 4096)
        _require(
            ex_raw[4:22].hex() == value["device_descriptor"]["raw_hex"],
            "EX_DEVICE_DESCRIPTOR_BINDING",
        )
        counts = value["accounting"]
        _require(
            all(
                call["status"] == "OK"
                or (
                    call["phase"] == "OBSERVE"
                    and call["operation"] == "CONNECTION_EX_V2"
                    and not value["link"]["ex_v2_available"]
                )
                for call in value["calls"]
            ),
            "OBSERVED_REQUIRED_CALL_FAILED",
        )
        _require(
            counts["hub_open_successes"] > 0
            and counts["hub_open_successes"] == counts["close_successes"]
            and counts["remaining_open_handles"] == 0
            and counts["descriptor_requests"] >= len(serials) + 2,
            "OBSERVED_QUERY_CLEANUP",
        )
        _observed_trace_coverage(value)

    @property
    def sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_OBSERVATION_BYTES)


def parse_usb_identity_observation(
    wire: bytes, *, request: UsbIdentityAdmissionRequest
) -> UsbIdentityObservation:
    """Decode native JSON without requiring its serializer's object key order."""
    _require(type(request) is UsbIdentityAdmissionRequest, "EXACT_REQUEST_TYPE")
    request = UsbIdentityAdmissionRequest(request.payload)
    result = UsbIdentityObservation(
        canonical(_load(wire, MAX_OBSERVATION_BYTES, canonical_required=False))
    )
    value, bound = result.to_dict(), request.to_dict()
    _require(
        value["request_sha256"] == request.request_sha256
        and value["requested_endpoint"] == bound["endpoint"]
        and value["expected_device_instance_id"]
        == bound["expected_device_instance_id"],
        "OBSERVATION_REQUEST_BINDING",
    )
    return result


def parse_owned_usb_identity_result(
    wire: bytes,
    *,
    request: UsbIdentityAdmissionRequest,
    ready: UsbIdentityReady,
    returncode: int,
) -> tuple[dict[str, Any], UsbIdentityObservation]:
    _require(
        type(request) is UsbIdentityAdmissionRequest
        and type(ready) is UsbIdentityReady,
        "EXACT_ADMISSION_TYPES",
    )
    request, ready = UsbIdentityAdmissionRequest(request.payload), UsbIdentityReady(
        ready.payload
    )
    value = _load(wire, MAX_RESULT_BYTES, canonical_required=False)
    _closed(
        value,
        {
            "schema",
            "request_sha256",
            "child_pid",
            "challenge_sha256",
            "permit_sha256",
            "native_receipt",
        },
    )
    _require(
        value["schema"] == RESULT_SCHEMA
        and value["request_sha256"]
        == request.request_sha256
        == ready.to_dict()["request_sha256"]
        and type(value["child_pid"]) is int
        and value["child_pid"] == ready.to_dict()["child_pid"]
        and value["challenge_sha256"] == ready.challenge_sha256
        and value["permit_sha256"] == request.to_dict()["permit_sha256"],
        "RESULT_ADMISSION_BINDING",
    )
    observation = parse_usb_identity_observation(
        canonical(value["native_receipt"]), request=request
    )
    _require(
        type(returncode) is int
        and returncode == (0 if observation.to_dict()["outcome"] == "OBSERVED" else 1),
        "RESULT_EXIT_MISMATCH",
    )
    return value, observation
