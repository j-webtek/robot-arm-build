"""Exact v2 probe/capture preparation; construction grants no runtime authority.

The build-review owner supplies expected pins. We neither hash arbitrary installed
files to learn trust nor reuse legacy/metadata runtime registrations. All path,
request, intent and budget checks below are filesystem/process/device inert.
"""

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .camera_worker_client import (
    CameraActivationRequest,
    CameraCampaignBudget,
    CameraEndpointBinding,
    PreparedCameraCampaign,
    WindowsCameraWorkerClient,
)
from .native_camera_activation_expectation import CameraActivationExpectation
from .native_camera_activation_protocol import (
    PROBE_SCHEMA,
    CAPTURE_SCHEMA,
    RESULT_SCHEMA,
    NativeCameraActivationRequest,
)
from .native_camera_capture_protocol import (
    NativeCaptureConfiguration,
    encode_controls,
    local_capture_path,
)
from .native_camera_protocol import (
    FRAME_BYTES,
    MAX_HANDSHAKE_BYTES,
    MAX_REQUEST_BYTES,
    MAX_RESULT_BYTES,
    NATIVE_DURATION_MS,
    _require,
    _sha,
    canonical,
    digest,
)
from .native_camera_registration import _pin
from .owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
    decode_owned_json,
)

RUNTIME_SCHEMA = "rocell.native_camera_activation_runtime_candidate.v2"
PREPARED_SCHEMA = "rocell.prepared_owned_native_activation.v2"
_BASE = "software/native/windows_camera"
_RUNTIME_FIELDS = {
    "schema",
    "workspace",
    "source_sha256",
    "catalog_sha256",
    "helper",
    "build_record",
    "purpose",
    "request_schema",
    "result_schema",
    "status",
    "dispatch_enabled",
}


def _purpose(value: Any) -> str:
    _require(
        type(value) is str and value in ("probe", "capture"),
        "ACTIVATION_RUNTIME_PURPOSE",
    )
    return value


def helper_relative_path(purpose: str) -> str:
    return f"{_BASE}/build-owned-activation-{_purpose(purpose)}/Release/rocell_windows_camera.exe"


def build_record_relative_path(purpose: str) -> str:
    return f"{_BASE}/owned_activation_{_purpose(purpose)}_build_manifest.json"


def process_budget(purpose: str) -> WorkerProcessBudget:
    """One child; complete stdout (READY plus result) shares the fixed 256 KiB cap.

    This does not expand the shared process owner cap. An oversized combined
    stream is a failed observation, never permission to drop or truncate fields.
    """
    return WorkerProcessBudget(
        run_timeout_ms=10000 if _purpose(purpose) == "probe" else 15000,
        cleanup_timeout_ms=2000,
        stdin_bytes=MAX_REQUEST_BYTES + MAX_HANDSHAKE_BYTES,
        stdout_bytes=MAX_RESULT_BYTES,
        stderr_bytes=8 * 1024,
        process_count=1,
    )


def _load(payload: bytes) -> dict[str, Any]:
    data = decode_owned_json(payload, maximum=48 * 1024)
    _require(canonical(data) == payload, "CANONICAL_V2_PREPARATION_REQUIRED")
    return data


@dataclass(frozen=True, slots=True)
class NativeCameraActivationRuntime:
    payload: bytes

    def __post_init__(self) -> None:
        data = self.to_dict()
        _require(
            set(data) == _RUNTIME_FIELDS and data["schema"] == RUNTIME_SCHEMA,
            "V2_RUNTIME_SCHEMA",
        )
        purpose = _purpose(data["purpose"])
        workspace = local_capture_path(data["workspace"])
        for key in ("source_sha256", "catalog_sha256"):
            _sha(data[key])
            _require(data[key] != "0" * 64, "V2_RUNTIME_ZERO_DIGEST")
        helper, record = _pin(data["helper"]), _pin(data["build_record"])
        _require(
            helper.path == workspace / helper_relative_path(purpose)
            and record.path == workspace / build_record_relative_path(purpose)
            and helper.maximum_bytes == 8 * 1024 * 1024
            and record.maximum_bytes == 128 * 1024,
            "V2_FIXED_RUNTIME_PATHS",
        )
        _require(
            helper.sha256 != "0" * 64 and record.sha256 != "0" * 64,
            "V2_RUNTIME_ZERO_DIGEST",
        )
        _require(
            data["request_schema"]
            == (PROBE_SCHEMA if purpose == "probe" else CAPTURE_SCHEMA)
            and data["result_schema"] == RESULT_SCHEMA
            and data["status"] == "BUILD_REVIEW_REQUIRED"
            and data["dispatch_enabled"] is False,
            "V2_RUNTIME_NOT_AUTHORITY",
        )

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)

    @property
    def registration_sha256(self) -> str:
        return digest(self.payload)


def create_activation_runtime(
    workspace: Path,
    *,
    purpose: str,
    source_sha256: str,
    catalog_sha256: str,
    helper_sha256: str,
    build_record_sha256: str,
) -> NativeCameraActivationRuntime:
    """Prepare a candidate for build review, not a reviewed/qualified runtime."""
    purpose = _purpose(purpose)
    workspace = local_capture_path(str(workspace))

    def pin(path: Path, sha: str, maximum: int) -> dict[str, Any]:
        return {**asdict(PinnedWorkerFile(path, sha, maximum)), "path": str(path)}

    return NativeCameraActivationRuntime(
        canonical(
            dict(
                schema=RUNTIME_SCHEMA,
                workspace=str(workspace),
                purpose=purpose,
                source_sha256=source_sha256,
                catalog_sha256=catalog_sha256,
                helper=pin(
                    workspace / helper_relative_path(purpose),
                    helper_sha256,
                    8 * 1024 * 1024,
                ),
                build_record=pin(
                    workspace / build_record_relative_path(purpose),
                    build_record_sha256,
                    128 * 1024,
                ),
                request_schema=PROBE_SCHEMA if purpose == "probe" else CAPTURE_SCHEMA,
                result_schema=RESULT_SCHEMA,
                status="BUILD_REVIEW_REQUIRED",
                dispatch_enabled=False,
            )
        )
    )


def _camera_plan(
    runtime: NativeCameraActivationRuntime, request: NativeCameraActivationRequest
) -> PreparedCameraCampaign:
    data = request.to_dict()
    pin = _pin(runtime.to_dict()["helper"])
    client = WindowsCameraWorkerClient(pin.path, pin.sha256)
    binding = CameraEndpointBinding(
        data["endpoint"], data["endpoint_sha256"], data["selected_identity_sha256"]
    )
    common = dict(source_sha256=data["source_sha256"], campaign_id=data["attempt_id"])
    config = request.configuration
    if config is None:
        return client.prepare_probe(
            binding,
            budget=CameraCampaignBudget(
                NATIVE_DURATION_MS, 1, FRAME_BYTES, FRAME_BYTES
            ),
            **common,
        )
    return client.prepare_capture(
        binding,
        config.mode,
        config.output_directory,
        budget=config.budget,
        controls=config.controls,
        **common,
    )


@dataclass(frozen=True, slots=True)
class PreparedOwnedNativeActivation:
    """Entire process/intent/identity binding, never an executable permission."""

    payload: bytes

    def __post_init__(self) -> None:
        data = self.to_dict()
        _require(
            set(data)
            == {
                "schema",
                "runtime",
                "admission_request",
                "working_directory",
                "process_budget",
            }
            and data["schema"] == PREPARED_SCHEMA,
            "V2_PREPARED_SCHEMA",
        )
        runtime, request = self.runtime, self.admission_request
        registered, observed = runtime.to_dict(), request.to_dict()
        _require(
            registered["purpose"] == request.purpose
            and observed["runtime_registration_sha256"] == runtime.registration_sha256
            and observed["source_sha256"] == registered["source_sha256"]
            and observed["helper_sha256"] == registered["helper"]["sha256"],
            "V2_PREPARATION_RUNTIME_MISMATCH",
        )
        directory = local_capture_path(data["working_directory"])
        config = request.configuration
        if config is not None:
            _require(
                config.output_directory
                == directory / ("capture-" + observed["attempt_id"]),
                "V2_PRIVATE_CAPTURE_DIRECTORY",
            )
        _require(type(data["process_budget"]) is dict, "V2_PROCESS_BUDGET_FIELDS")
        WorkerProcessBudget(**data["process_budget"]).__post_init__()
        _require(
            data["process_budget"] == asdict(process_budget(request.purpose)),
            "V2_EXACT_PROCESS_BUDGET",
        )
        _require(
            digest(canonical(asdict(self.camera_plan.request)))
            == observed["camera_request_sha256"],
            "V2_LOGICAL_PLAN_MISMATCH",
        )
        self.registration.__post_init__()

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)

    @property
    def runtime(self) -> NativeCameraActivationRuntime:
        return NativeCameraActivationRuntime(canonical(self.to_dict()["runtime"]))

    @property
    def admission_request(self) -> NativeCameraActivationRequest:
        return NativeCameraActivationRequest(
            canonical(self.to_dict()["admission_request"])
        )

    @property
    def camera_plan(self) -> PreparedCameraCampaign:
        return _camera_plan(self.runtime, self.admission_request)

    @property
    def registration(self) -> WorkerProcessRegistration:
        data, runtime, request = (
            self.to_dict(),
            self.runtime.to_dict(),
            self.admission_request,
        )
        return WorkerProcessRegistration(
            "windows-native-camera-activation-" + request.purpose,
            _pin(runtime["helper"]),
            (
                "--owned-" + request.purpose + "-v2",
                "--request-sha256",
                request.request_sha256,
            ),
            (_pin(runtime["build_record"]),),
            local_capture_path(data["working_directory"]),
            process_budget(request.purpose),
            "PHYSICAL_UNQUALIFIED",
            runtime["request_schema"],
            RESULT_SCHEMA,
        )

    @property
    def preparation_sha256(self) -> str:
        return digest(self.payload)

    @property
    def required_lifetime_ns(self) -> int:
        budget = process_budget(self.admission_request.purpose)
        return (budget.run_timeout_ms + budget.cleanup_timeout_ms) * 1_000_000


def prepare_owned_activation(
    runtime: NativeCameraActivationRuntime,
    plan: PreparedCameraCampaign,
    expectation: CameraActivationExpectation,
    *,
    session_id: str,
    operation_sha256: str,
    permit_sha256: str,
    working_directory: Path,
) -> PreparedOwnedNativeActivation:
    """Join the existing camera intent without inventing a shortened v1 request."""
    _require(
        type(runtime) is NativeCameraActivationRuntime
        and type(plan) is PreparedCameraCampaign
        and type(plan.request) is CameraActivationRequest
        and type(expectation) is CameraActivationExpectation,
        "V2_EXACT_PREPARATION_TYPES",
    )
    _require(
        set(vars(plan)) == {f.name for f in fields(PreparedCameraCampaign)}
        and set(vars(plan.request)) == {f.name for f in fields(CameraActivationRequest)}
        and type(plan.arguments) is tuple
        and all(type(arg) is str for arg in plan.arguments)
        and type(plan.request.controls) is tuple,
        "V2_EXACT_LOGICAL_TYPES",
    )
    runtime = NativeCameraActivationRuntime(runtime.payload)
    expectation = CameraActivationExpectation(expectation.payload)
    request = plan.request
    purpose = _purpose(request.operation)
    _require(request.budget.duration_ms == NATIVE_DURATION_MS, "V2_LOGICAL_DURATION")
    data = dict(
        schema=PROBE_SCHEMA if purpose == "probe" else CAPTURE_SCHEMA,
        attempt_id=request.campaign_id,
        session_id=session_id,
        source_sha256=request.source_sha256,
        operation_sha256=operation_sha256,
        selected_identity_sha256=request.binding.binding_sha256,
        endpoint=request.binding.symbolic_link,
        endpoint_sha256=request.binding.endpoint_sha256,
        helper_sha256=request.helper_sha256,
        runtime_registration_sha256=runtime.registration_sha256,
        camera_request_sha256=digest(canonical(asdict(request))),
        permit_sha256=permit_sha256,
        native_duration_ms=NATIVE_DURATION_MS,
        admission_timeout_ms=2000 if purpose == "probe" else 5000,
        activation_identity_json=expectation.payload.decode("ascii"),
    )
    if purpose == "capture":
        mode, budget = request.mode, request.budget
        _require(
            mode is not None and request.output_directory is not None,
            "V2_LOGICAL_CAPTURE_MODE",
        )
        assert mode is not None
        config = NativeCaptureConfiguration(
            canonical(
                dict(
                    width=mode.width,
                    height=mode.height,
                    fps_numerator=mode.fps_numerator,
                    fps_denominator=mode.fps_denominator,
                    subtype=mode.subtype,
                    frame_count=budget.max_frames,
                    max_frame_bytes=budget.max_frame_bytes,
                    max_total_bytes=budget.max_total_bytes,
                    output_directory=request.output_directory,
                    controls=encode_controls(request.controls),
                    requested_stride_bytes=(
                        "" if mode.stride_bytes is None else str(mode.stride_bytes)
                    ),
                )
            )
        )
        data["capture_json"] = config.payload.decode("ascii")
    admission = NativeCameraActivationRequest(canonical(data))
    _require(
        asdict(_camera_plan(runtime, admission)) == asdict(plan),
        "V2_EXACT_LOGICAL_PLAN",
    )
    return PreparedOwnedNativeActivation(
        canonical(
            dict(
                schema=PREPARED_SCHEMA,
                runtime=runtime.to_dict(),
                admission_request=admission.to_dict(),
                working_directory=str(working_directory),
                process_budget=asdict(process_budget(purpose)),
            )
        )
    )
