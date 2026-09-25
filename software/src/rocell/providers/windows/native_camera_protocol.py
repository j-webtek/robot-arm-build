"""Pure closed native-probe admission codec; serialization never grants authority.

The parent owns the Job, current M1 lease and consumed permit. Only that parent
may send RELEASE after verifying READY. No constructor, parser or Boolean here
authorizes a process or a camera. The physical runner remains held separately.
"""

from dataclasses import dataclass
import hashlib
import json
import re
from typing import Any

from .camera_worker_client import (
    CameraCampaignBudget,
    CameraEndpointBinding,
    NativeCameraReceipt,
    WindowsCameraWorkerClient,
)

REQUEST_SCHEMA = "rocell.native_camera_admission_request.v1"
READY_SCHEMA = "rocell.native_camera_admission_ready.v1"
RELEASE_SCHEMA = "rocell.native_camera_admission_release.v1"
RESULT_SCHEMA = "rocell.owned_native_camera_result.v1"
MAX_REQUEST_BYTES = 16 * 1024
MAX_HANDSHAKE_BYTES = 1024
MAX_RESULT_BYTES = 256 * 1024
NATIVE_DURATION_MS = 5000
ADMISSION_TIMEOUT_MS = 2000
FRAME_BYTES = 39_923_712  # Unused probe budget fields, never permission for frames.
_SHA = re.compile(r"[0-9a-f]{64}\Z")
_ID = re.compile(r"[A-Za-z0-9][A-Za-z0-9_.-]{0,95}\Z")
_REQUEST_FIELDS = {
    "schema",
    "attempt_id",
    "session_id",
    "source_sha256",
    "operation_sha256",
    "selected_identity_sha256",
    "endpoint",
    "endpoint_sha256",
    "helper_sha256",
    "runtime_registration_sha256",
    "camera_request_sha256",
    "permit_sha256",
    "native_duration_ms",
    "admission_timeout_ms",
}


class NativeCameraProtocolError(ValueError):
    pass


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise NativeCameraProtocolError(code)


def canonical(value: Any) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("ascii")


def digest(value: bytes) -> str:
    _require(type(value) is bytes, "EXACT_BYTES_REQUIRED")
    return hashlib.sha256(value).hexdigest()


def _sha(value: Any) -> None:
    _require(type(value) is str and bool(_SHA.fullmatch(value)), "INVALID_SHA256")


def _pid(value: Any) -> None:
    _require(type(value) is int and 1 <= value <= 2**32 - 1, "INVALID_CHILD_PID")


def _load(payload: bytes, maximum: int, *, line: bool) -> dict[str, Any]:
    _require(
        type(payload) is bytes and 0 < len(payload) <= maximum, "MESSAGE_BYTE_LIMIT"
    )
    if line:
        _require(
            payload.endswith(b"\n") and payload.count(b"\n") == 1,
            "ONE_MESSAGE_LINE_REQUIRED",
        )
        payload = payload[:-1]

    def pairs(items: list[tuple[str, Any]]) -> dict[str, Any]:
        result = {}
        for key, value in items:
            _require(key not in result, "DUPLICATE_JSON_KEY")
            result[key] = value
        return result

    def bad(_: str) -> Any:
        raise NativeCameraProtocolError("NONFINITE_JSON")

    try:
        value = json.loads(
            payload.decode("ascii"), object_pairs_hook=pairs, parse_constant=bad
        )
        _require(
            type(value) is dict and canonical(value) == payload,
            "CANONICAL_OBJECT_REQUIRED",
        )
    except (UnicodeError, json.JSONDecodeError, RecursionError, TypeError) as exc:
        raise NativeCameraProtocolError("INVALID_BOUNDED_JSON") from exc
    return value


@dataclass(frozen=True, slots=True)
class NativeCameraAdmissionRequest:
    payload: bytes

    def __post_init__(self) -> None:
        data = _load(self.payload, MAX_REQUEST_BYTES - 1, line=False)
        _require(
            set(data) == _REQUEST_FIELDS and data["schema"] == REQUEST_SCHEMA,
            "REQUEST_SCHEMA",
        )
        for key in _REQUEST_FIELDS - {
            "schema",
            "attempt_id",
            "session_id",
            "endpoint",
            "native_duration_ms",
            "admission_timeout_ms",
        }:
            _sha(data[key])
        for key in ("attempt_id", "session_id"):
            _require(
                type(data[key]) is str and bool(_ID.fullmatch(data[key])), "REQUEST_ID"
            )
        endpoint = data["endpoint"]
        _require(
            type(endpoint) is str
            and 0 < len(endpoint.encode("utf-8")) <= 4096
            and not any(ord(c) < 32 or ord(c) == 127 for c in endpoint),
            "REQUEST_ENDPOINT",
        )
        _require(
            digest(endpoint.encode("utf-8")) == data["endpoint_sha256"], "ENDPOINT_HASH"
        )
        _require(
            type(data["native_duration_ms"]) is int
            and data["native_duration_ms"] == NATIVE_DURATION_MS,
            "NATIVE_PROBE_BUDGET",
        )
        _require(
            type(data["admission_timeout_ms"]) is int
            and data["admission_timeout_ms"] == ADMISSION_TIMEOUT_MS,
            "ADMISSION_BUDGET",
        )

    @property
    def request_sha256(self) -> str:
        return digest(self.payload)

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_REQUEST_BYTES - 1, line=False)

    def wire(self) -> bytes:
        return self.payload + b"\n"


@dataclass(frozen=True, slots=True)
class NativeCameraReady:
    payload: bytes

    def __post_init__(self) -> None:
        data = _load(self.payload, MAX_HANDSHAKE_BYTES - 1, line=False)
        _require(
            set(data) == {"schema", "request_sha256", "child_pid", "challenge"}
            and data["schema"] == READY_SCHEMA,
            "READY_SCHEMA",
        )
        _sha(data["request_sha256"])
        _sha(data["challenge"])
        _pid(data["child_pid"])

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_HANDSHAKE_BYTES - 1, line=False)

    @property
    def challenge_sha256(self) -> str:
        return digest(self.to_dict()["challenge"].encode("ascii"))


def parse_native_camera_ready(
    wire: bytes, *, expected_request_sha256: str, expected_child_pid: int
) -> NativeCameraReady:
    _sha(expected_request_sha256)
    _pid(expected_child_pid)
    data = _load(wire, MAX_HANDSHAKE_BYTES, line=True)
    ready = NativeCameraReady(canonical(data))
    _require(
        data["request_sha256"] == expected_request_sha256
        and data["child_pid"] == expected_child_pid,
        "READY_OWNED_CHILD_BINDING",
    )
    return ready


def native_camera_release(
    request: NativeCameraAdmissionRequest, ready: NativeCameraReady
) -> bytes:
    """Encode only; caller must check current consumed authority before using it."""
    _require(
        type(request) is NativeCameraAdmissionRequest
        and type(ready) is NativeCameraReady,
        "EXACT_ADMISSION_TYPES",
    )
    request = NativeCameraAdmissionRequest(request.payload)
    ready = NativeCameraReady(ready.payload)
    data = request.to_dict()
    observed = ready.to_dict()
    _require(
        observed["request_sha256"] == request.request_sha256, "RELEASE_REQUEST_MISMATCH"
    )
    return (
        canonical(
            {
                "schema": RELEASE_SCHEMA,
                "request_sha256": request.request_sha256,
                "child_pid": observed["child_pid"],
                "challenge_sha256": ready.challenge_sha256,
                "permit_sha256": data["permit_sha256"],
            }
        )
        + b"\n"
    )


def parse_owned_native_camera_result(
    wire: bytes,
    *,
    request: NativeCameraAdmissionRequest,
    ready: NativeCameraReady,
    returncode: int,
) -> tuple[dict[str, Any], NativeCameraReceipt]:
    """Pure probe parse; all native effects must remain actual reported values."""
    _require(
        type(request) is NativeCameraAdmissionRequest
        and type(ready) is NativeCameraReady,
        "EXACT_ADMISSION_TYPES",
    )
    request = NativeCameraAdmissionRequest(request.payload)
    ready = NativeCameraReady(ready.payload)
    # Native receipt serialization is not required to use Python key ordering.
    # Decode through the existing bounded duplicate/nonfinite parser, then own it.
    _require(
        type(wire) is bytes and 0 < len(wire) <= MAX_RESULT_BYTES, "RESULT_BYTE_LIMIT"
    )
    from .owned_worker_process import decode_owned_json

    raw = decode_owned_json(wire, maximum=MAX_RESULT_BYTES)
    _require(
        set(raw)
        == {
            "schema",
            "request_sha256",
            "child_pid",
            "challenge_sha256",
            "permit_sha256",
            "native_receipt",
        },
        "RESULT_SCHEMA",
    )
    data, observed = request.to_dict(), ready.to_dict()
    _require(
        raw["schema"] == RESULT_SCHEMA
        and raw["request_sha256"]
        == request.request_sha256
        == observed["request_sha256"]
        and type(raw["child_pid"]) is int
        and raw["child_pid"] == observed["child_pid"]
        and raw["challenge_sha256"] == ready.challenge_sha256
        and raw["permit_sha256"] == data["permit_sha256"],
        "RESULT_ADMISSION_BINDING",
    )
    budget = CameraCampaignBudget(NATIVE_DURATION_MS, 1, FRAME_BYTES, FRAME_BYTES)
    binding = CameraEndpointBinding(
        data["endpoint"], data["endpoint_sha256"], data["selected_identity_sha256"]
    )
    receipt = WindowsCameraWorkerClient._parse_receipt(
        raw["native_receipt"], "probe", binding, None, (budget, None), ()
    )
    _require(
        type(returncode) is int and returncode == (0 if receipt.status == "OK" else 1),
        "RESULT_EXIT_MISMATCH",
    )
    return raw, receipt
