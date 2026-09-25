"""Pure guarded-capture wire codec; neither parsing nor encoding opens a camera.

Capture has a distinct request schema. Its nested flat configuration preserves
the old native decoder's field bound and exactly reconstructs the existing
camera client request. Returned metadata is not a verified pixel dataset.
"""

from __future__ import annotations

from dataclasses import dataclass
from pathlib import Path, PureWindowsPath
import re
from typing import Any, TYPE_CHECKING

from .camera_worker_client import (
    CameraCampaignBudget,
    CameraControlSetting,
    CameraEndpointBinding,
    NativeCameraMode,
    WindowsCameraWorkerClient,
)
from .native_camera_protocol import (
    MAX_REQUEST_BYTES,
    MAX_RESULT_BYTES,
    NATIVE_DURATION_MS,
    RELEASE_SCHEMA,
    RESULT_SCHEMA,
    NativeCameraReady,
    _ID,
    _REQUEST_FIELDS,
    _load,
    _require,
    _sha,
    canonical,
    digest,
)
from .owned_worker_process import decode_owned_json

if TYPE_CHECKING:
    from .camera_worker_client import NativeCameraReceiptMetadata

REQUEST_SCHEMA = "rocell.native_camera_capture_admission_request.v1"
ADMISSION_TIMEOUT_MS = 5000
_CAPTURE_FIELDS = {
    "width",
    "height",
    "fps_numerator",
    "fps_denominator",
    "subtype",
    "frame_count",
    "max_frame_bytes",
    "max_total_bytes",
    "output_directory",
    "controls",
    "requested_stride_bytes",
}
_SIGNED = re.compile(r"(?:0|-[1-9][0-9]*|[1-9][0-9]*)\Z")


def local_capture_path(value: Any) -> Path:
    """Windows-local structural check only; no path is resolved or created."""
    _require(
        type(value) is str and 0 < len(value.encode("utf-8")) <= 4096,
        "CAPTURE_LOCAL_PATH_REQUIRED",
    )
    path = PureWindowsPath(value)
    _require(
        path.is_absolute()
        and str(path) == value
        and bool(re.fullmatch(r"[A-Za-z]:", path.drive))
        and len(path.parts) > 1
        and ".." not in path.parts
        and not any(ord(c) < 32 or ord(c) == 127 for c in value)
        and all(
            not any(c in part for c in ':<>"|?*')
            and not part.endswith((" ", "."))
            and not PureWindowsPath(part).is_reserved()
            for part in path.parts[1:]
        ),
        "CAPTURE_LOCAL_PATH_REQUIRED",
    )
    return Path(value)


def encode_controls(controls: tuple[CameraControlSetting, ...]) -> str:
    _require(type(controls) is tuple and len(controls) <= 6, "EXACT_CAPTURE_CONTROLS")
    seen = set()
    for item in controls:
        _require(type(item) is CameraControlSetting, "EXACT_CAPTURE_CONTROL")
        item.__post_init__()
        _require(item.control_id not in seen, "DUPLICATE_CAPTURE_CONTROL")
        seen.add(item.control_id)
    return ";".join(
        f"{item.control_id},{item.value},{item.mode}"
        for item in sorted(controls, key=lambda item: item.control_id)
    )


def decode_controls(value: Any) -> tuple[CameraControlSetting, ...]:
    _require(type(value) is str and len(value) <= 512, "CAPTURE_CONTROLS_LIMIT")
    items = []
    if value:
        for part in value.split(";"):
            fields = part.split(",")
            _require(
                len(fields) == 3 and bool(_SIGNED.fullmatch(fields[1])),
                "CANONICAL_CAPTURE_CONTROL",
            )
            items.append(CameraControlSetting(fields[0], int(fields[1]), fields[2]))
    result = tuple(items)
    _require(encode_controls(result) == value, "CANONICAL_CAPTURE_CONTROLS")
    return result


@dataclass(frozen=True, slots=True)
class NativeCaptureConfiguration:
    payload: bytes

    def __post_init__(self) -> None:
        data = self.to_dict()
        _require(set(data) == _CAPTURE_FIELDS, "CAPTURE_CONFIGURATION_FIELDS")
        stride = data["requested_stride_bytes"]
        _require(
            type(stride) is str
            and len(stride) <= 8
            and (stride == "" or bool(_SIGNED.fullmatch(stride)) and stride != "0"),
            "CAPTURE_STRIDE",
        )
        mode, budget = self.mode, self.budget
        _require(
            mode.subtype == "YUY2" and mode.width >= 2 and mode.width % 2 == 0,
            "CAPTURE_YUY2_REQUIRED",
        )
        _require(
            mode.width * mode.height * 2 <= budget.max_frame_bytes,
            "CAPTURE_FRAME_BUDGET",
        )
        if mode.stride_bytes is not None:
            _require(
                abs(mode.stride_bytes) >= mode.width * 2
                and (mode.height - 1) * abs(mode.stride_bytes) + mode.width * 2
                <= budget.max_frame_bytes,
                "CAPTURE_STRIDE_BUDGET",
            )
        decode_controls(data["controls"])
        local_capture_path(data["output_directory"])

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_REQUEST_BYTES - 1, line=False)

    @property
    def mode(self) -> NativeCameraMode:
        data = self.to_dict()
        stride = data["requested_stride_bytes"]
        return NativeCameraMode(
            data["width"],
            data["height"],
            data["fps_numerator"],
            data["fps_denominator"],
            data["subtype"],
            None if stride == "" else int(stride),
        )

    @property
    def budget(self) -> CameraCampaignBudget:
        data = self.to_dict()
        return CameraCampaignBudget(
            NATIVE_DURATION_MS,
            data["frame_count"],
            data["max_frame_bytes"],
            data["max_total_bytes"],
        )

    @property
    def controls(self) -> tuple[CameraControlSetting, ...]:
        return decode_controls(self.to_dict()["controls"])

    @property
    def output_directory(self) -> Path:
        return local_capture_path(self.to_dict()["output_directory"])


@dataclass(frozen=True, slots=True)
class NativeCameraCaptureAdmissionRequest:
    payload: bytes

    def __post_init__(self) -> None:
        data = self.to_dict()
        _require(
            set(data) == _REQUEST_FIELDS | {"capture_json"}
            and data["schema"] == REQUEST_SCHEMA,
            "CAPTURE_REQUEST_SCHEMA",
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
        CameraEndpointBinding(
            data["endpoint"], data["endpoint_sha256"], data["selected_identity_sha256"]
        )
        _require(
            type(data["native_duration_ms"]) is int
            and data["native_duration_ms"] == NATIVE_DURATION_MS,
            "NATIVE_CAPTURE_BUDGET",
        )
        _require(
            type(data["admission_timeout_ms"]) is int
            and data["admission_timeout_ms"] == ADMISSION_TIMEOUT_MS,
            "CAPTURE_ADMISSION_BUDGET",
        )
        _require(type(data["capture_json"]) is str, "CAPTURE_CONFIGURATION_STRING")
        config = self.configuration
        _require(
            config.output_directory.name == "capture-" + data["attempt_id"],
            "CAPTURE_ASSIGNED_LEAF",
        )

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload, MAX_REQUEST_BYTES - 1, line=False)

    @property
    def configuration(self) -> NativeCaptureConfiguration:
        return NativeCaptureConfiguration(
            self.to_dict()["capture_json"].encode("ascii")
        )

    @property
    def request_sha256(self) -> str:
        return digest(self.payload)

    def wire(self) -> bytes:
        return self.payload + b"\n"


def native_camera_capture_release(
    request: NativeCameraCaptureAdmissionRequest,
    ready: NativeCameraReady,
) -> bytes:
    """Encoding only. A current consumed-permit check still precedes WriteFile."""
    _require(
        type(request) is NativeCameraCaptureAdmissionRequest
        and type(ready) is NativeCameraReady,
        "EXACT_CAPTURE_ADMISSION_TYPES",
    )
    request = NativeCameraCaptureAdmissionRequest(request.payload)
    ready = NativeCameraReady(ready.payload)
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
                "permit_sha256": request.to_dict()["permit_sha256"],
            }
        )
        + b"\n"
    )


def parse_owned_native_camera_capture_result(
    wire: bytes,
    *,
    request: NativeCameraCaptureAdmissionRequest,
    ready: NativeCameraReady,
    returncode: int,
) -> tuple[dict[str, Any], NativeCameraReceiptMetadata]:
    """Pure native metadata; frame existence/length/hash verification is separate."""
    _require(
        type(request) is NativeCameraCaptureAdmissionRequest
        and type(ready) is NativeCameraReady,
        "EXACT_CAPTURE_ADMISSION_TYPES",
    )
    request = NativeCameraCaptureAdmissionRequest(request.payload)
    ready = NativeCameraReady(ready.payload)
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
    config = request.configuration
    metadata = WindowsCameraWorkerClient._parse_receipt_metadata(
        raw["native_receipt"],
        "capture",
        CameraEndpointBinding(
            data["endpoint"], data["endpoint_sha256"], data["selected_identity_sha256"]
        ),
        config.mode,
        (config.budget, config.output_directory),
        config.controls,
    )
    # The sent-mode echo is copied from the admitted options, not negotiated by
    # a driver. Require exact rationals and stride; only observed modes may use
    # equivalent rational representations.
    _require(metadata.requested_mode == config.mode, "CAPTURE_REQUESTED_MODE_MISMATCH")
    # A failed native negotiation may legitimately report the mismatching
    # stride. Retain that failure; only successful metadata must satisfy the
    # requested stride, independently of the legacy format-equivalence check.
    stride = config.mode.stride_bytes
    if stride is not None and metadata.status == "OK":
        _require(
            metadata.observed_mode is not None
            and metadata.observed_mode.stride_bytes == stride
            and all(frame.stride_bytes == stride for frame in metadata.frames),
            "CAPTURE_OBSERVED_STRIDE_MISMATCH",
        )
    _require(
        type(returncode) is int and returncode == (0 if metadata.status == "OK" else 1),
        "RESULT_EXIT_MISMATCH",
    )
    return raw, metadata
