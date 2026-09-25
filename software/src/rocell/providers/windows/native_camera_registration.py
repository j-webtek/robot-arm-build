"""Dormant purpose-specific native probe preparation, never runtime approval.

The reviewed metadata registration cannot substitute for this candidate. Fixed
new-build pins are supplied by a server-owned build review, never learned from
whatever executable happens to exist. Physical dispatch remains independently
held by OwnedWindowsWorker and the qualified coordinator composition.
"""

from dataclasses import asdict, dataclass, fields
from pathlib import Path
from typing import Any

from .camera_worker_client import (
    CameraActivationRequest,
    PreparedCameraCampaign,
    WindowsCameraWorkerClient,
)
from .native_camera_protocol import (
    ADMISSION_TIMEOUT_MS,
    FRAME_BYTES,
    NATIVE_DURATION_MS,
    REQUEST_SCHEMA,
    RESULT_SCHEMA,
    NativeCameraAdmissionRequest,
    canonical,
    digest,
)
from .owned_worker_process import (
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
    decode_owned_json,
)

RUNTIME_SCHEMA = "rocell.native_camera_runtime_candidate.v1"
PREPARED_SCHEMA = "rocell.prepared_owned_native_probe.v1"
HELPER_RELATIVE_PATH = (
    "software/native/windows_camera/build-owned/Release/rocell_windows_camera.exe"
)
BUILD_RECORD_RELATIVE_PATH = "software/native/windows_camera/owned_build_manifest.json"


def _require(ok: bool, code: str) -> None:
    if not ok:
        raise ValueError(code)


def _path(value: Any) -> Path:
    _require(type(value) is str, "EXACT_PATH_STRING")
    path = Path(value)
    _require(
        path.is_absolute()
        and path != Path(path.anchor)
        and ".." not in path.parts
        and not value.startswith(("\\\\", "//"))
        and not any(ord(c) < 32 for c in value),
        "EXACT_LOCAL_PATH",
    )
    return path


def _load(payload: bytes) -> dict[str, Any]:
    data = decode_owned_json(payload, maximum=32 * 1024)
    _require(canonical(data) == payload, "EXACT_CANONICAL_PREPARATION")
    return data


def _pin(data: dict[str, Any]) -> PinnedWorkerFile:
    _require(
        type(data) is dict and set(data) == {"path", "sha256", "maximum_bytes"},
        "EXACT_PIN",
    )
    return PinnedWorkerFile(_path(data["path"]), data["sha256"], data["maximum_bytes"])


@dataclass(frozen=True, slots=True)
class NativeCameraRuntimeRegistration:
    payload: bytes

    def __post_init__(self) -> None:
        data = _load(self.payload)
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
            "RUNTIME_SCHEMA",
        )
        workspace = _path(data["workspace"])
        helper, record = _pin(data["helper"]), _pin(data["build_record"])
        # Reuse strict digest validation without reading a file.
        PinnedWorkerFile(helper.path, data["source_sha256"])
        PinnedWorkerFile(helper.path, data["catalog_sha256"])
        _require(
            data["schema"] == RUNTIME_SCHEMA
            and data["purpose"] == "FINITE_NATIVE_CAMERA_PROBE"
            and data["status"] == "DORMANT_REVIEW_REQUIRED"
            and data["allowed_operations"] == ["probe"]
            and data["request_schema"] == REQUEST_SCHEMA
            and data["result_schema"] == RESULT_SCHEMA,
            "RUNTIME_PURPOSE",
        )
        _require(
            helper.path == workspace / HELPER_RELATIVE_PATH
            and record.path == workspace / BUILD_RECORD_RELATIVE_PATH
            and helper.maximum_bytes == 8 * 1024 * 1024
            and record.maximum_bytes == 128 * 1024,
            "FIXED_NATIVE_BUILD_PINS",
        )
        _require(
            all(
                data[k] is False
                for k in ("dispatch_enabled", "physical_authority", "driver_qualified")
            ),
            "DORMANT_PHYSICAL_HOLD",
        )

    def to_dict(self) -> dict[str, Any]:
        return _load(self.payload)

    @property
    def registration_sha256(self) -> str:
        return digest(self.payload)


def create_native_camera_runtime_registration(
    workspace: Path,
    *,
    source_sha256: str,
    catalog_sha256: str,
    helper_sha256: str,
    build_record_sha256: str,
) -> NativeCameraRuntimeRegistration:
    """Pure candidate only; no file hashes, execution or metadata approval reuse."""

    def pin(path: Path, sha: str, maximum: int) -> dict[str, Any]:
        value = PinnedWorkerFile(path, sha, maximum)
        return {**asdict(value), "path": str(path)}

    workspace = _path(str(workspace))
    return NativeCameraRuntimeRegistration(
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
                "purpose": "FINITE_NATIVE_CAMERA_PROBE",
                "status": "DORMANT_REVIEW_REQUIRED",
                "allowed_operations": ["probe"],
                "request_schema": REQUEST_SCHEMA,
                "result_schema": RESULT_SCHEMA,
                "dispatch_enabled": False,
                "physical_authority": False,
                "driver_qualified": False,
            }
        )
    )


@dataclass(frozen=True, slots=True)
class PreparedOwnedNativeProbe:
    payload: bytes

    def __post_init__(self) -> None:
        data = _load(self.payload)
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
            "PREPARED_NATIVE_SCHEMA",
        )
        runtime = NativeCameraRuntimeRegistration(canonical(data["runtime"]))
        request = NativeCameraAdmissionRequest(canonical(data["admission_request"]))
        observed = request.to_dict()
        registered = runtime.to_dict()
        _require(
            observed["runtime_registration_sha256"] == runtime.registration_sha256
            and observed["source_sha256"] == registered["source_sha256"]
            and observed["helper_sha256"] == registered["helper"]["sha256"],
            "NATIVE_RUNTIME_REQUEST_MISMATCH",
        )
        _path(data["working_directory"])
        budget = WorkerProcessBudget(**data["process_budget"])
        _require(
            budget.run_timeout_ms == 10000
            and budget.cleanup_timeout_ms == 2000
            and budget.stdout_bytes == 32 * 1024
            and budget.stderr_bytes == 8 * 1024
            and budget.stdin_bytes >= 16 * 1024 + 1024,
            "NATIVE_PROBE_PROCESS_BUDGET",
        )
        _require(
            ADMISSION_TIMEOUT_MS + NATIVE_DURATION_MS < budget.run_timeout_ms,
            "ADMISSION_AND_NATIVE_MUST_FIT",
        )
        plan = self.camera_plan
        _require(
            digest(canonical(asdict(plan.request)))
            == observed["camera_request_sha256"],
            "NATIVE_CAMERA_PLAN_MISMATCH",
        )
        self.registration.__post_init__()

    def _value(self) -> dict[str, Any]:
        return _load(self.payload)

    @property
    def runtime(self) -> NativeCameraRuntimeRegistration:
        return NativeCameraRuntimeRegistration(canonical(self._value()["runtime"]))

    @property
    def admission_request(self) -> NativeCameraAdmissionRequest:
        return NativeCameraAdmissionRequest(
            canonical(self._value()["admission_request"])
        )

    @property
    def camera_plan(self) -> PreparedCameraCampaign:
        from .camera_worker_client import CameraCampaignBudget, CameraEndpointBinding

        request = self.admission_request.to_dict()
        pin = _pin(self.runtime.to_dict()["helper"])
        return WindowsCameraWorkerClient(pin.path, pin.sha256).prepare_probe(
            CameraEndpointBinding(
                request["endpoint"],
                request["endpoint_sha256"],
                request["selected_identity_sha256"],
            ),
            source_sha256=request["source_sha256"],
            campaign_id=request["attempt_id"],
            budget=CameraCampaignBudget(
                NATIVE_DURATION_MS, 1, FRAME_BYTES, FRAME_BYTES
            ),
        )

    @property
    def registration(self) -> WorkerProcessRegistration:
        data = self._value()
        runtime = self.runtime.to_dict()
        return WorkerProcessRegistration(
            "windows-native-camera-probe",
            _pin(runtime["helper"]),
            (
                "--owned-probe",
                "--request-sha256",
                self.admission_request.request_sha256,
            ),
            (_pin(runtime["build_record"]),),
            _path(data["working_directory"]),
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

    def to_dict(self) -> dict[str, Any]:
        return self._value()


def prepare_owned_native_probe(
    runtime: NativeCameraRuntimeRegistration,
    plan: PreparedCameraCampaign,
    *,
    session_id: str,
    operation_sha256: str,
    permit_sha256: str,
    working_directory: Path,
    process_budget: WorkerProcessBudget = WorkerProcessBudget(
        run_timeout_ms=10000,
        cleanup_timeout_ms=2000,
        stdout_bytes=32 * 1024,
        stderr_bytes=8 * 1024,
    ),
) -> PreparedOwnedNativeProbe:
    """Exact inert join; enough remaining parent lifetime is checked at dispatch."""
    _require(
        type(runtime) is NativeCameraRuntimeRegistration
        and type(plan) is PreparedCameraCampaign
        and type(plan.request) is CameraActivationRequest
        and type(process_budget) is WorkerProcessBudget,
        "EXACT_NATIVE_PREPARATION_TYPES",
    )
    _require(
        set(vars(plan)) == {f.name for f in fields(PreparedCameraCampaign)}
        and set(vars(plan.request)) == {f.name for f in fields(CameraActivationRequest)}
        and type(plan.request.controls) is tuple
        and type(plan.arguments) is tuple
        and all(type(arg) is str for arg in plan.arguments),
        "EXACT_NATIVE_PREPARATION_FIELDS",
    )
    runtime = NativeCameraRuntimeRegistration(runtime.payload)
    data = runtime.to_dict()
    helper = _pin(data["helper"])
    request = plan.request
    fresh = WindowsCameraWorkerClient(helper.path, helper.sha256).prepare_probe(
        request.binding,
        source_sha256=request.source_sha256,
        campaign_id=request.campaign_id,
        budget=request.budget,
    )
    _require(
        asdict(fresh) == asdict(plan)
        and type(plan.arguments) is tuple
        and request.mode is None
        and request.controls == ()
        and request.output_directory is None,
        "EXACT_LOGICAL_PROBE_PLAN",
    )
    _require(
        asdict(request.budget)
        == {
            "duration_ms": NATIVE_DURATION_MS,
            "max_frames": 1,
            "max_frame_bytes": FRAME_BYTES,
            "max_total_bytes": FRAME_BYTES,
        },
        "EXACT_LOGICAL_PROBE_BUDGET",
    )
    admission = NativeCameraAdmissionRequest(
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
            }
        )
    )
    return PreparedOwnedNativeProbe(
        canonical(
            {
                "schema": PREPARED_SCHEMA,
                "runtime": data,
                "admission_request": admission.to_dict(),
                "working_directory": str(_path(str(working_directory))),
                "process_budget": asdict(process_budget),
            }
        )
    )
