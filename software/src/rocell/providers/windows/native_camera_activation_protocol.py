"""Pure v2 request/owned-result codec; does not launch or authorize a worker.

Keep the old v1 parsers strict. Only their unchanged capture-settings data
validator and handshake format are shared. The process owner must independently
own the child, enforce deadlines/Stop, and consume current original-derived
authority before sending RELEASE. This codec cannot prove any of those facts.
"""

from dataclasses import dataclass
from typing import Any

from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraEndpointBinding,
    NativeCameraReceiptMetadata,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_capture_protocol import (
    NativeCaptureConfiguration,
)
from rocell.providers.windows.native_camera_protocol import (
    FRAME_BYTES,
    MAX_REQUEST_BYTES,
    MAX_RESULT_BYTES,
    NATIVE_DURATION_MS,
    RELEASE_SCHEMA,
    NativeCameraReady,
    _ID,
    _REQUEST_FIELDS,
    _load,
    _pid,
    _require,
    _sha,
    canonical,
    digest,
)
from rocell.providers.windows.owned_worker_process import decode_owned_json

from .native_camera_activation_expectation import CameraActivationExpectation
from .native_camera_activation_observation import (
    ActivationObservation,
    validate_activation_observation,
)

PROBE_SCHEMA = "rocell.native_camera_admission_request.v2"
CAPTURE_SCHEMA = "rocell.native_camera_capture_admission_request.v2"
RESULT_SCHEMA = "rocell.owned_native_camera_result.v2"
_RESULT_FIELDS = {
    "schema",
    "request_sha256",
    "child_pid",
    "challenge_sha256",
    "permit_sha256",
    "activation_identity",
    "native_receipt",
}


def _ascii(value: Any, code: str) -> bytes:
    _require(type(value) is str and value.isascii(), code)
    return value.encode("ascii")


@dataclass(frozen=True, slots=True)
class NativeCameraActivationRequest:
    """One canonical request, including the exact pre-open expectation."""

    payload: bytes

    def __post_init__(self) -> None:
        data = self.to_dict()
        _require(
            data.get("schema") in (PROBE_SCHEMA, CAPTURE_SCHEMA), "V2_REQUEST_SCHEMA"
        )
        capture = data["schema"] == CAPTURE_SCHEMA
        _require(
            set(data)
            == _REQUEST_FIELDS
            | {"activation_identity_json"}
            | ({"capture_json"} if capture else set()),
            "V2_REQUEST_FIELDS",
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
            _require(data[key] != "0" * 64, "V2_ZERO_DIGEST")
        for key in ("attempt_id", "session_id"):
            _require(
                type(data[key]) is str and bool(_ID.fullmatch(data[key])),
                "V2_REQUEST_ID",
            )
        expectation = self.expectation
        _require(
            data["endpoint"] == expectation.to_dict()["endpoint"],
            "V2_EXPECTED_ENDPOINT",
        )
        _require(
            digest(data["endpoint"].encode("utf-8")) == data["endpoint_sha256"],
            "V2_ENDPOINT_HASH",
        )
        _require(
            type(data["native_duration_ms"]) is int
            and data["native_duration_ms"] == NATIVE_DURATION_MS
            and type(data["admission_timeout_ms"]) is int
            and data["admission_timeout_ms"] == (5000 if capture else 2000),
            "V2_REQUEST_BUDGET",
        )
        if capture:
            config = self.configuration
            assert config is not None
            _require(
                config.output_directory.name == "capture-" + data["attempt_id"],
                "V2_CAPTURE_LEAF",
            )

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_REQUEST_BYTES - 1, line=False)

    @property
    def purpose(self) -> str:
        return "capture" if self.to_dict()["schema"] == CAPTURE_SCHEMA else "probe"

    @property
    def expectation(self) -> CameraActivationExpectation:
        return CameraActivationExpectation(
            _ascii(self.to_dict()["activation_identity_json"], "V2_EXPECTATION_STRING")
        )

    @property
    def configuration(self) -> NativeCaptureConfiguration | None:
        if self.purpose == "probe":
            return None
        return NativeCaptureConfiguration(
            _ascii(self.to_dict()["capture_json"], "V2_CAPTURE_STRING")
        )

    @property
    def request_sha256(self) -> str:
        return digest(self.payload)

    def wire(self) -> bytes:
        return self.payload + b"\n"


def _bound_inputs(
    request: NativeCameraActivationRequest, ready: NativeCameraReady, child_pid: int
) -> tuple[NativeCameraActivationRequest, NativeCameraReady]:
    _require(
        type(request) is NativeCameraActivationRequest
        and type(ready) is NativeCameraReady,
        "V2_EXACT_TYPES",
    )
    _pid(child_pid)
    # Revalidate payloads even when handed a frozen Python object.
    request, ready = NativeCameraActivationRequest(request.payload), NativeCameraReady(
        ready.payload
    )
    observed = ready.to_dict()
    _require(
        observed["request_sha256"] == request.request_sha256
        and observed["child_pid"] == child_pid,
        "V2_READY_OWNED_CHILD_BINDING",
    )
    return request, ready


def activation_release(
    request: NativeCameraActivationRequest,
    ready: NativeCameraReady,
    *,
    expected_child_pid: int,
) -> bytes:
    """Encode only. No permit is checked, consumed or granted by serialization."""
    request, ready = _bound_inputs(request, ready, expected_child_pid)
    return (
        canonical(
            dict(
                schema=RELEASE_SCHEMA,
                request_sha256=request.request_sha256,
                child_pid=expected_child_pid,
                challenge_sha256=ready.challenge_sha256,
                permit_sha256=request.to_dict()["permit_sha256"],
            )
        )
        + b"\n"
    )


@dataclass(frozen=True, slots=True)
class ValidatedActivationResult:
    """Verified wire consistency, not a permit, completed process or pixel set."""

    wire: bytes
    receipt: NativeCameraReceiptMetadata
    activation: ActivationObservation

    def to_dict(self) -> dict[str, Any]:
        return decode_owned_json(self.wire, maximum=MAX_RESULT_BYTES)


def parse_owned_activation_result(
    wire: bytes,
    *,
    request: NativeCameraActivationRequest,
    ready: NativeCameraReady,
    expected_child_pid: int,
    returncode: int,
) -> ValidatedActivationResult:
    """Bind the full v2 exchange, acquisition metadata and fresh identity together.

    Uses metadata-only parsing for BOTH probe and capture. It never reads a frame
    or output path. Missing/malformed results fail; callers retain the raw process
    outcome rather than fabricating a successful or zero-effect observation.
    """
    request, ready = _bound_inputs(request, ready, expected_child_pid)
    _require(
        type(wire) is bytes and 0 < len(wire) <= MAX_RESULT_BYTES,
        "V2_RESULT_BYTE_LIMIT",
    )
    raw = decode_owned_json(wire, maximum=MAX_RESULT_BYTES)
    _require(
        set(raw) == _RESULT_FIELDS and raw["schema"] == RESULT_SCHEMA,
        "V2_RESULT_SCHEMA",
    )
    data = request.to_dict()
    _require(
        raw["request_sha256"] == request.request_sha256
        and type(raw["child_pid"]) is int
        and raw["child_pid"] == expected_child_pid
        and raw["challenge_sha256"] == ready.challenge_sha256
        and raw["permit_sha256"] == data["permit_sha256"],
        "V2_RESULT_ADMISSION_BINDING",
    )
    binding = CameraEndpointBinding(
        data["endpoint"], data["endpoint_sha256"], data["selected_identity_sha256"]
    )
    config = request.configuration
    metadata = WindowsCameraWorkerClient._parse_receipt_metadata(
        raw["native_receipt"],
        request.purpose,
        binding,
        None if config is None else config.mode,
        (
            (
                CameraCampaignBudget(NATIVE_DURATION_MS, 1, FRAME_BYTES, FRAME_BYTES),
                None,
            )
            if config is None
            else (config.budget, config.output_directory)
        ),
        () if config is None else config.controls,
    )
    if config is not None:
        _require(metadata.requested_mode == config.mode, "V2_CAPTURE_REQUESTED_MODE")
        stride = config.mode.stride_bytes
        if stride is not None and metadata.status == "OK":
            _require(
                metadata.observed_mode is not None
                and metadata.observed_mode.stride_bytes == stride
                and all(frame.stride_bytes == stride for frame in metadata.frames),
                "V2_CAPTURE_OBSERVED_STRIDE",
            )
    _require(
        type(returncode) is int and returncode == (0 if metadata.status == "OK" else 1),
        "V2_RESULT_EXIT_MISMATCH",
    )
    activation = validate_activation_observation(
        raw["activation_identity"],
        request.expectation,
        source_activation_attempts=metadata.counts["source_activation_attempts"],
        source_opened=metadata.counts["source_opened"],
        native_status=metadata.status,
    )
    return ValidatedActivationResult(wire, metadata, activation)
