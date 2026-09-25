"""Exact, filesystem-inert capture preparation for a separately held native build.

The candidate is never metadata registration or physical approval. Its full
preparation, not just a request hash, must be bound by the future coordinator.
"""

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .camera_worker_client import (
    CameraActivationRequest,
    CameraEndpointBinding,
    PreparedCameraCampaign,
    WindowsCameraWorkerClient,
)
from .native_camera_protocol import canonical, digest, NATIVE_DURATION_MS, RESULT_SCHEMA
from .native_camera_capture_protocol import (
    ADMISSION_TIMEOUT_MS,
    REQUEST_SCHEMA,
    NativeCameraCaptureAdmissionRequest,
    NativeCaptureConfiguration,
    encode_controls,
    local_capture_path,
)
from .native_camera_registration import _load, _pin, _require
from .owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
)

RUNTIME_SCHEMA = "rocell.native_camera_capture_runtime_candidate.v1"
PREPARED_SCHEMA = "rocell.prepared_owned_native_capture.v1"
HELPER_RELATIVE_PATH = "software/native/windows_camera/build-owned-capture/Release/rocell_windows_camera.exe"
BUILD_RECORD_RELATIVE_PATH = (
    "software/native/windows_camera/owned_capture_build_manifest.json"
)
CAPTURE_PROCESS_BUDGET = WorkerProcessBudget(
    run_timeout_ms=15000,
    cleanup_timeout_ms=2000,
    stdout_bytes=32 * 1024,
    stderr_bytes=8 * 1024,
    process_count=1,
)


@dataclass(frozen=True, slots=True)
class NativeCameraCaptureRuntimeRegistration:
    payload: bytes

    def __post_init__(self) -> None:
        data = self.to_dict()
        _require(
            set(data)
            == {
                "schema",
                "workspace",
                "source_sha256",
                "catalog_sha256",
                "helper",
                "build_record",
                "purpose",
                "status",
                "allowed_operations",
                "request_schema",
                "result_schema",
                "dispatch_enabled",
                "physical_authority",
                "driver_qualified",
            },
            "CAPTURE_RUNTIME_SCHEMA",
        )
        workspace = local_capture_path(data["workspace"])
        helper, record = _pin(data["helper"]), _pin(data["build_record"])
        PinnedWorkerFile(helper.path, data["source_sha256"])
        PinnedWorkerFile(helper.path, data["catalog_sha256"])
        _require(
            data["schema"] == RUNTIME_SCHEMA
            and data["purpose"] == "FINITE_NATIVE_CAMERA_CAPTURE"
            and data["status"] == "DORMANT_REVIEW_REQUIRED"
            and data["allowed_operations"] == ["capture"]
            and data["request_schema"] == REQUEST_SCHEMA
            and data["result_schema"] == RESULT_SCHEMA,
            "CAPTURE_RUNTIME_PURPOSE",
        )
        _require(
            helper.path == workspace / HELPER_RELATIVE_PATH
            and record.path == workspace / BUILD_RECORD_RELATIVE_PATH
            and helper.maximum_bytes == 8 * 1024 * 1024
            and record.maximum_bytes == 128 * 1024,
            "FIXED_CAPTURE_BUILD_PINS",
        )
        _require(
            all(
                data[k] is False
                for k in (
                    "dispatch_enabled",
                    "physical_authority",
                    "driver_qualified",
                )
            ),
            "DORMANT_PHYSICAL_HOLD",
        )

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)

    @property
    def registration_sha256(self) -> str:
        return digest(self.payload)


def create_native_camera_capture_runtime_registration(
    workspace: Path,
    *,
    source_sha256: str,
    catalog_sha256: str,
    helper_sha256: str,
    build_record_sha256: str,
) -> NativeCameraCaptureRuntimeRegistration:
    """Supplied reviewed pins, never hash whatever happens to be installed."""
    workspace = local_capture_path(str(workspace))

    def pin(path: Path, sha: str, maximum: int) -> dict[str, Any]:
        return {**asdict(PinnedWorkerFile(path, sha, maximum)), "path": str(path)}

    return NativeCameraCaptureRuntimeRegistration(
        canonical(
            {
                "schema": RUNTIME_SCHEMA,
                "workspace": str(workspace),
                "source_sha256": source_sha256,
                "catalog_sha256": catalog_sha256,
                "helper": pin(
                    workspace / HELPER_RELATIVE_PATH, helper_sha256, 8 * 1024 * 1024
                ),
                "build_record": pin(
                    workspace / BUILD_RECORD_RELATIVE_PATH,
                    build_record_sha256,
                    128 * 1024,
                ),
                "purpose": "FINITE_NATIVE_CAMERA_CAPTURE",
                "status": "DORMANT_REVIEW_REQUIRED",
                "allowed_operations": ["capture"],
                "request_schema": REQUEST_SCHEMA,
                "result_schema": RESULT_SCHEMA,
                "dispatch_enabled": False,
                "physical_authority": False,
                "driver_qualified": False,
            }
        )
    )


@dataclass(frozen=True, slots=True)
class PreparedOwnedNativeCapture:
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
            "PREPARED_CAPTURE_SCHEMA",
        )
        runtime, request = self.runtime, self.admission_request
        registered, observed = runtime.to_dict(), request.to_dict()
        _require(
            observed["runtime_registration_sha256"] == runtime.registration_sha256
            and observed["source_sha256"] == registered["source_sha256"]
            and observed["helper_sha256"] == registered["helper"]["sha256"],
            "CAPTURE_RUNTIME_REQUEST_MISMATCH",
        )
        directory = local_capture_path(data["working_directory"])
        _require(
            str(request.configuration.output_directory)
            == str(directory / ("capture-" + observed["attempt_id"])),
            "CAPTURE_PRIVATE_DIRECTORY",
        )
        _require(
            type(data["process_budget"]) is dict
            and data["process_budget"] == asdict(CAPTURE_PROCESS_BUDGET),
            "EXACT_CAPTURE_PROCESS_BUDGET",
        )
        WorkerProcessBudget(**data["process_budget"]).__post_init__()
        _require(
            digest(canonical(asdict(self.camera_plan.request)))
            == observed["camera_request_sha256"],
            "CAPTURE_CAMERA_PLAN_MISMATCH",
        )
        self.registration.__post_init__()

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)

    @property
    def runtime(self) -> NativeCameraCaptureRuntimeRegistration:
        return NativeCameraCaptureRuntimeRegistration(
            canonical(self.to_dict()["runtime"])
        )

    @property
    def admission_request(self) -> NativeCameraCaptureAdmissionRequest:
        return NativeCameraCaptureAdmissionRequest(
            canonical(self.to_dict()["admission_request"])
        )

    @property
    def camera_plan(self) -> PreparedCameraCampaign:
        data = self.admission_request.to_dict()
        config = self.admission_request.configuration
        helper = _pin(self.runtime.to_dict()["helper"])
        return WindowsCameraWorkerClient(helper.path, helper.sha256).prepare_capture(
            CameraEndpointBinding(
                data["endpoint"],
                data["endpoint_sha256"],
                data["selected_identity_sha256"],
            ),
            config.mode,
            config.output_directory,
            source_sha256=data["source_sha256"],
            campaign_id=data["attempt_id"],
            budget=config.budget,
            controls=config.controls,
        )

    @property
    def registration(self) -> WorkerProcessRegistration:
        data, runtime = self.to_dict(), self.runtime.to_dict()
        return WorkerProcessRegistration(
            "windows-native-camera-capture",
            _pin(runtime["helper"]),
            (
                "--owned-capture",
                "--request-sha256",
                self.admission_request.request_sha256,
            ),
            (_pin(runtime["build_record"]),),
            local_capture_path(data["working_directory"]),
            WorkerProcessBudget(**data["process_budget"]),
            "PHYSICAL_UNQUALIFIED",
            REQUEST_SCHEMA,
            RESULT_SCHEMA,
        )

    @property
    def preparation_sha256(self) -> str:
        return digest(self.payload)

    @property
    def required_lifetime_ns(self) -> int:
        budget = self.registration.budget
        return (budget.run_timeout_ms + budget.cleanup_timeout_ms) * 1_000_000


def prepare_owned_native_capture(
    runtime: NativeCameraCaptureRuntimeRegistration,
    plan: PreparedCameraCampaign,
    *,
    session_id: str,
    operation_sha256: str,
    permit_sha256: str,
    working_directory: Path,
) -> PreparedOwnedNativeCapture:
    """Pure join of an existing logical capture and its exact original admission."""
    _require(
        type(runtime) is NativeCameraCaptureRuntimeRegistration
        and type(plan) is PreparedCameraCampaign
        and type(plan.request) is CameraActivationRequest,
        "EXACT_CAPTURE_PREPARATION_TYPES",
    )
    _require(
        set(vars(plan)) == {f.name for f in fields(PreparedCameraCampaign)}
        and set(vars(plan.request)) == {f.name for f in fields(CameraActivationRequest)}
        and type(plan.arguments) is tuple
        and type(plan.request.controls) is tuple,
        "EXACT_CAPTURE_PREPARATION_FIELDS",
    )
    runtime = NativeCameraCaptureRuntimeRegistration(runtime.payload)
    request = plan.request
    helper = _pin(runtime.to_dict()["helper"])
    _require(
        request.operation == "capture"
        and request.mode is not None
        and request.output_directory is not None,
        "EXACT_LOGICAL_CAPTURE_PLAN",
    )
    assert request.mode is not None and request.output_directory is not None
    fresh = WindowsCameraWorkerClient(helper.path, helper.sha256).prepare_capture(
        request.binding,
        request.mode,
        local_capture_path(request.output_directory),
        source_sha256=request.source_sha256,
        campaign_id=request.campaign_id,
        budget=request.budget,
        controls=request.controls,
    )
    _require(asdict(plan) == asdict(fresh), "EXACT_LOGICAL_CAPTURE_PLAN")
    _require(
        request.controls
        == tuple(sorted(request.controls, key=lambda item: item.control_id)),
        "CANONICAL_CAPTURE_CONTROL_ORDER_REQUIRED",
    )
    mode, budget = request.mode, request.budget
    _require(budget.duration_ms == NATIVE_DURATION_MS, "EXACT_LOGICAL_CAPTURE_BUDGET")
    config = NativeCaptureConfiguration(
        canonical(
            {
                "width": mode.width,
                "height": mode.height,
                "fps_numerator": mode.fps_numerator,
                "fps_denominator": mode.fps_denominator,
                "subtype": mode.subtype,
                "frame_count": budget.max_frames,
                "max_frame_bytes": budget.max_frame_bytes,
                "max_total_bytes": budget.max_total_bytes,
                "output_directory": request.output_directory,
                "controls": encode_controls(request.controls),
                "requested_stride_bytes": (
                    "" if mode.stride_bytes is None else str(mode.stride_bytes)
                ),
            }
        )
    )
    admission = NativeCameraCaptureAdmissionRequest(
        canonical(
            {
                "schema": REQUEST_SCHEMA,
                "attempt_id": request.campaign_id,
                "session_id": session_id,
                "source_sha256": request.source_sha256,
                "operation_sha256": operation_sha256,
                "selected_identity_sha256": request.binding.binding_sha256,
                "endpoint": request.binding.symbolic_link,
                "endpoint_sha256": request.binding.endpoint_sha256,
                "helper_sha256": request.helper_sha256,
                "runtime_registration_sha256": runtime.registration_sha256,
                "camera_request_sha256": digest(canonical(asdict(request))),
                "permit_sha256": permit_sha256,
                "native_duration_ms": NATIVE_DURATION_MS,
                "admission_timeout_ms": ADMISSION_TIMEOUT_MS,
                "capture_json": config.payload.decode("ascii"),
            }
        )
    )
    return PreparedOwnedNativeCapture(
        canonical(
            {
                "schema": PREPARED_SCHEMA,
                "runtime": runtime.to_dict(),
                "admission_request": admission.to_dict(),
                "working_directory": str(working_directory),
                "process_budget": asdict(CAPTURE_PROCESS_BUDGET),
            }
        )
    )
