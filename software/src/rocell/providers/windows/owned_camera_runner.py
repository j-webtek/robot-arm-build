"""Prepared camera -> closed incapable owned process -> native-wire adapter.

Construction/preparation are filesystem-inert. The actual camera client still
performs its existing preflight and mandatory exact-request authorization. This
adapter separately validates the same attempt at owned-process admission; it
does not issue permits, redeem a second permit, or launch a native helper.
"""

from __future__ import annotations

from dataclasses import asdict, dataclass, fields
import math
from pathlib import Path
import threading
from typing import Any, Callable

from .camera_worker_client import (
    CameraActivationRequest,
    CameraCampaignBudget,
    CameraControlSetting,
    CameraEndpointBinding,
    CameraWorkerError,
    MAX_IPC_BYTES,
    NativeCameraMode,
    NativeProcessResult,
    PreparedCameraCampaign,
    WindowsCameraWorkerClient,
)
from .owned_camera_codec import (
    CAMERA_FIXTURE_PATH,
    CONFIG_PAYLOAD_SCHEMA,
    FRAME_BYTES,
    MODE,
    PAYLOAD_SCHEMA,
    PROVENANCE,
    REQUEST_SCHEMA,
    RESULT_SCHEMA,
    TEMPLATE_BYTES,
    canonical,
    payload_protocols,
    payload_working_directory,
    validate_camera_registration,
    validate_camera_result,
)
from .owned_worker_process import (
    OwnedWindowsWorker,
    OwnedWorkerRequest,
    OwnedWorkerResult,
    PinnedWorkerFile,
    WorkerProcessBudget,
    WorkerProcessRegistration,
    decode_owned_json,
    owned_registration_document,
    owned_request_wire,
)


def _require(value: bool, code: str) -> None:
    if not value:
        raise ValueError(code)


def _snapshot_plan(plan: PreparedCameraCampaign) -> PreparedCameraCampaign:
    _require(
        type(plan) is PreparedCameraCampaign
        and set(vars(plan)) == {"request", "arguments"},
        "EXACT_PREPARED_CAMERA_PLAN_REQUIRED",
    )
    request = plan.request
    _require(
        type(request) is CameraActivationRequest
        and set(vars(request))
        == {field.name for field in fields(CameraActivationRequest)}
        and type(plan.arguments) is tuple
        and len(plan.arguments) in {6, 22, 24}
        and all(type(arg) is str for arg in plan.arguments),
        "EXACT_PREPARED_CAMERA_REQUEST_REQUIRED",
    )
    # The existing public pure builder enforces the exact nested camera types.
    client = WindowsCameraWorkerClient(Path(plan.arguments[0]), request.helper_sha256)
    if request.operation == "probe":
        _require(
            request.mode is None
            and request.controls == ()
            and type(request.controls) is tuple
            and request.output_directory is None,
            "FIXTURE_PROBE_HAS_CAPTURE_FIELDS",
        )
        fresh = client.prepare_probe(
            request.binding,
            source_sha256=request.source_sha256,
            campaign_id=request.campaign_id,
            budget=request.budget,
        )
    else:
        _require(
            request.operation == "capture" and request.output_directory is not None,
            "FIXTURE_CAPTURE_OR_PROBE_ONLY",
        )
        _require(type(request.mode) is NativeCameraMode, "FIXTURE_MODE_REQUIRED")
        assert request.mode is not None and request.output_directory is not None
        fresh = client.prepare_capture(
            request.binding,
            request.mode,
            Path(request.output_directory),
            source_sha256=request.source_sha256,
            campaign_id=request.campaign_id,
            budget=request.budget,
            controls=request.controls,
        )
    _require(asdict(fresh) == asdict(plan), "PREPARED_CAMERA_PLAN_DRIFT")
    return fresh


def _registration(document: dict[str, Any]) -> WorkerProcessRegistration:
    def pin(value: dict[str, Any]) -> PinnedWorkerFile:
        return PinnedWorkerFile(
            Path(value["path"]), value["sha256"], value["maximum_bytes"]
        )

    return WorkerProcessRegistration(
        document["worker_id"],
        pin(document["executable"]),
        tuple(document["argv"]),
        tuple(pin(item) for item in document["package_files"]),
        Path(document["working_directory"]),
        WorkerProcessBudget(**document["budget"]),
        document["composition"],
        document["request_schema"],
        document["result_schema"],
    )


def _request(document: dict[str, Any]) -> OwnedWorkerRequest:
    return OwnedWorkerRequest(
        **{key: value for key, value in document.items() if key != "payload"},
        payload_json=canonical(document["payload"]),
    )


def _native_plan(payload: dict[str, Any]) -> PreparedCameraCampaign:
    camera = payload["camera_request"]
    request = CameraActivationRequest(
        camera["campaign_id"],
        camera["source_sha256"],
        camera["operation"],
        CameraEndpointBinding(**camera["binding"]),
        NativeCameraMode(**camera["mode"]) if camera["mode"] is not None else None,
        tuple(CameraControlSetting(**setting) for setting in camera["controls"]),
        CameraCampaignBudget(**camera["budget"]),
        camera["helper_sha256"],
        camera["arguments_sha256"],
        camera["output_directory"],
    )
    return _snapshot_plan(
        PreparedCameraCampaign(request, tuple(payload["native_arguments"]))
    )


@dataclass(frozen=True)
class PreparedOwnedCameraFixture:
    """Immutable bytes-backed plan. Every public projection is a fresh snapshot."""

    _canonical_json: bytes

    def __post_init__(self) -> None:
        value = decode_owned_json(self._canonical_json, maximum=60 * 1024)
        _require(
            set(value) == {"schema", "registration", "request"}
            and value["schema"] == "rocell.prepared_owned_camera_fixture.v1"
            and canonical(value) == self._canonical_json,
            "INVALID_OWNED_CAMERA_PREPARATION",
        )
        registration = _registration(value["registration"])
        request = _request(value["request"])
        _require(
            owned_registration_document(registration) == value["registration"],
            "OWNED_CAMERA_REGISTRATION_FIELDS",
        )
        payload = validate_camera_registration(registration, request)
        _native_plan(payload)
        # The largest legal decimal deadline fits before any worker is created.
        owned_request_wire(registration, request, deadline_ns=request.expires_at_ns)

    def _value(self) -> dict[str, Any]:
        return decode_owned_json(self._canonical_json, maximum=60 * 1024)

    @property
    def registration(self) -> WorkerProcessRegistration:
        return _registration(self._value()["registration"])

    @property
    def request(self) -> OwnedWorkerRequest:
        return _request(self._value()["request"])

    @property
    def plan(self) -> PreparedCameraCampaign:
        return _native_plan(self._value()["request"]["payload"])

    def request_sha256(self, deadline_ns: int) -> str:
        """Same pure canonical body builder used at actual after-pins admission."""
        return owned_request_wire(
            self.registration, self.request, deadline_ns=deadline_ns
        )[1]


def prepare_owned_camera_fixture(
    plan: PreparedCameraCampaign,
    *,
    session_id: str,
    operation_sha256: str,
    selected_identity_sha256: str,
    expires_at_ns: int,
    templates: tuple[PinnedWorkerFile, ...],
    executable: PinnedWorkerFile,
    fixture_script: PinnedWorkerFile,
    working_directory: Path | None = None,
    scenario: str = "nominal",
    budget: WorkerProcessBudget = WorkerProcessBudget(
        run_timeout_ms=25_000, stdout_bytes=32 * 1024, stderr_bytes=8 * 1024
    ),
) -> PreparedOwnedCameraFixture:
    """Pure request join; no hashing, directories, template reads or dispatch.

    Probe requires an explicit assigned working directory and no templates;
    capture retains its existing output directory default. Pins/hashes must be
    assigned by the server. One distinct limited-range
    2736x1824 GRAY8 template is required per requested full-size YUY2 frame.
    Output cwd is pinned by the owned backend before external admission.
    """
    fresh = _snapshot_plan(plan)
    _require(
        type(templates) is tuple
        and 0 <= len(templates) <= 4
        and all(type(item) is PinnedWorkerFile for item in templates)
        and type(fixture_script) is PinnedWorkerFile
        and type(executable) is PinnedWorkerFile,
        "EXACT_CAMERA_PINS_REQUIRED",
    )
    configured = fresh.request.operation == "probe" or bool(fresh.request.controls)
    if fresh.request.operation == "probe":
        _require(
            isinstance(working_directory, Path), "PROBE_WORKING_DIRECTORY_REQUIRED"
        )
        _require(not templates, "PROBE_TEMPLATES_FORBIDDEN")
    else:
        assert fresh.request.output_directory is not None
        if working_directory is None:
            working_directory = Path(fresh.request.output_directory)
        _require(
            working_directory == Path(fresh.request.output_directory),
            "CAPTURE_WORKING_DIRECTORY_DRIFT",
        )
    payload = {
        "schema": CONFIG_PAYLOAD_SCHEMA if configured else PAYLOAD_SCHEMA,
        "provenance": PROVENANCE,
        "scenario": scenario,
        "camera_request": asdict(fresh.request),
        "native_arguments": list(fresh.arguments),
        "templates": [{**asdict(item), "path": str(item.path)} for item in templates],
    }
    if configured:
        payload["working_directory"] = str(working_directory)
    # JSON conversion owns nested lists and intentionally turns empty controls
    # into the existing JSON array representation used by the child protocol.
    payload = decode_owned_json(canonical(payload), maximum=60 * 1024)
    request = OwnedWorkerRequest(
        fresh.request.campaign_id,
        session_id,
        fresh.request.source_sha256,
        operation_sha256,
        selected_identity_sha256,
        expires_at_ns,
        canonical(payload),
    )
    request_schema, result_schema = payload_protocols(payload)
    registration = WorkerProcessRegistration(
        "incapable-owned-camera",
        executable,
        ("-I", "-S", str(CAMERA_FIXTURE_PATH), scenario),
        (fixture_script, *templates),
        payload_working_directory(payload),
        budget,
        "INCAPABLE_PROCESS_FIXTURE",
        request_schema,
        result_schema,
    )
    validate_camera_registration(registration, request)
    value = {
        "schema": "rocell.prepared_owned_camera_fixture.v1",
        "registration": owned_registration_document(registration),
        "request": {
            **{
                key: item
                for key, item in asdict(request).items()
                if key != "payload_json"
            },
            "payload": payload,
        },
    }
    return PreparedOwnedCameraFixture(canonical(value))


class OwnedPreparedCameraRunner:
    """One-use existing NativeProcessRunner adapter, never a generic dispatcher.

    The returned native result alone cannot prove process cleanup. Callers must
    retain/check ``owned_result`` on both success and exception paths before M1
    acceptance. Raw pipes remain available for bounded lossless evidence.
    """

    def __init__(
        self,
        prepared: PreparedOwnedCameraFixture,
        *,
        cancellation: threading.Event,
        deadline_ns: int,
        authorize_owned: Callable[
            [WorkerProcessRegistration, OwnedWorkerRequest, str], None
        ],
    ) -> None:
        _require(
            type(prepared) is PreparedOwnedCameraFixture,
            "EXACT_OWNED_CAMERA_PREPARATION_REQUIRED",
        )
        self._prepared = PreparedOwnedCameraFixture(prepared._canonical_json)
        _require(
            isinstance(cancellation, threading.Event) and callable(authorize_owned),
            "CAMERA_CANCELLATION_AND_AUTHORIZER_REQUIRED",
        )
        self._cancellation, self._deadline_ns, self._authorize = (
            cancellation,
            deadline_ns,
            authorize_owned,
        )
        self.expected_request_sha256 = self._prepared.request_sha256(deadline_ns)
        self._owned_result: OwnedWorkerResult | None = None
        self._consumed = False
        self._lock = threading.Lock()

    @property
    def owned_result(self) -> OwnedWorkerResult | None:
        # Result raw pipes are immutable. Copy its mutable parsed projection so
        # a UI/evidence consumer cannot alter the retained worker result.
        if self._owned_result is None:
            return None
        result = self._owned_result
        parsed = (
            decode_owned_json(canonical(result.parsed_result), maximum=256 * 1024)
            if result.parsed_result is not None
            else None
        )
        return OwnedWorkerResult(**{**vars(result), "parsed_result": parsed})

    def __call__(
        self,
        arguments: tuple[str, ...],
        timeout_seconds: float,
        output_limit_bytes: int,
    ) -> NativeProcessResult:
        with self._lock:
            _require(not self._consumed, "OWNED_CAMERA_RUNNER_ALREADY_CONSUMED")
            self._consumed = True
        plan = self._prepared.plan
        _require(
            type(arguments) is tuple
            and arguments == plan.arguments
            and all(type(item) is str for item in arguments),
            "OWNED_CAMERA_ARGUMENT_DRIFT",
        )
        _require(
            type(timeout_seconds) in {int, float}
            and math.isfinite(timeout_seconds)
            and timeout_seconds == plan.request.budget.duration_ms / 1000 + 5,
            "OWNED_CAMERA_TIMEOUT_DRIFT",
        )
        _require(
            type(output_limit_bytes) is int and output_limit_bytes == MAX_IPC_BYTES,
            "OWNED_CAMERA_PIPE_BUDGET_DRIFT",
        )
        registration, request = self._prepared.registration, self._prepared.request
        worker = OwnedWindowsWorker(registration, authorizer=self._authorize)
        result = worker.run(
            request, cancellation=self._cancellation, deadline_ns=self._deadline_ns
        )
        self._owned_result = result
        payload = decode_owned_json(request.payload_json, maximum=60 * 1024)
        if result.parsed_result is not None:
            validate_camera_result(
                result.parsed_result,
                payload=payload,
                request_sha256=self.expected_request_sha256,
                attempt_id=request.attempt_id,
                returncode=result.returncode,
            )
        # Never translate uncertain process cleanup into a valid camera result.
        # The original bound packet remains in owned_result for failure export.
        if result.status in {"CANCELLED", "TIMED_OUT"}:
            raise CameraWorkerError(
                "OWNED_CAMERA_" + result.status,
                "Finite incapable campaign did not complete; retain owned_result",
                effect_uncertain=result.initial_thread_resumed
                or bool(result.cleanup_errors),
            )
        if result.cleanup_errors or (
            result.process_created and not result.tree_exit_confirmed
        ):
            raise CameraWorkerError(
                "OWNED_CAMERA_PROCESS_CLEANUP_UNCONFIRMED",
                "Owned process did not confirm bounded cleanup; retain owned_result",
                effect_uncertain=True,
            )
        if result.parsed_result is None or result.primary_error not in {
            None,
            "WORKER_EXIT_FAILED",
        }:
            raise CameraWorkerError(
                "OWNED_CAMERA_RESULT_INVALID",
                "No valid exact owned camera envelope; retain owned_result",
                effect_uncertain=result.initial_thread_resumed,
            )
        native = canonical(result.parsed_result["fixture_result"]["native_receipt"])
        _require(
            len(native) + len(result.stderr) <= MAX_IPC_BYTES,
            "OWNED_CAMERA_COMBINED_PIPE_LIMIT",
        )
        assert result.returncode is not None
        return NativeProcessResult(result.returncode, native, result.stderr)
