"""Hardware-inert fixtures at the native worker boundary; no MF/USB calls."""

from __future__ import annotations

from dataclasses import asdict
import hashlib
import json
from pathlib import Path

import pytest

from rocell.providers.windows.camera_worker_client import (
    MAX_IPC_BYTES,
    CameraCampaignBudget,
    CameraControlSetting,
    CameraEndpointBinding,
    CameraWorkerError,
    NativeCameraMode,
    NativeProcessResult,
    WindowsCameraWorkerClient,
)


ENDPOINT = r"\\?\usb#fixture-camera#synthetic-unit#{fixture}"
BINDING = CameraEndpointBinding(
    ENDPOINT, hashlib.sha256(ENDPOINT.encode()).hexdigest(), "b" * 64
)
MODE = NativeCameraMode(4, 2, 9, 1)
BUDGET = CameraCampaignBudget(
    duration_ms=500, max_frames=1, max_frame_bytes=16, max_total_bytes=16
)


def receipt(operation: str = "inventory") -> dict:
    activation = operation != "inventory"
    capture = operation == "capture"
    mode = asdict(MODE)
    observed = {**mode, "stride_bytes": 8}
    return {
        "schema": "rocell.windows_camera.v1",
        "operation": operation,
        "status": "OK",
        "reason_code": None,
        "selected_endpoint": ENDPOINT if activation else None,
        "devices": [{"symbolic_link": ENDPOINT, "friendly_name": "SYNTHETIC camera"}],
        "modes": [observed] if activation else [],
        "requested_mode": mode if capture else None,
        "observed_mode": observed if capture else None,
        "controls": [],
        "frames": (
            [
                {
                    "filename": "frame-000000.yuy2",
                    "length_bytes": 16,
                    "stride_bytes": 8,
                    "row0_offset_bytes": 0,
                    "host_sequence": 0,
                    "media_timestamp_100ns": -200,
                    "host_arrival_qpc": 1234567,
                    "qpc_frequency": 10_000_000,
                    "discontinuity": None,
                }
            ]
            if capture
            else []
        ),
        "counts": {
            "source_activation_attempts": int(activation),
            "source_opened": int(activation),
            "control_set_attempts": 0,
            "samples_received": int(capture),
            "frames_written": int(capture),
            "source_shutdown_attempts": int(activation),
        },
        "cleanup": {
            "source_shutdown_hr": 0 if activation else None,
            "source_released": True,
            "mf_shutdown_hr": 0,
            "com_uninitialized": True,
        },
        "limitations": [
            "SENSOR_SEQUENCE_UNAVAILABLE",
            "MEDIA_TIMESTAMP_IS_NOT_EXPOSURE_TIME",
        ],
    }


class FixtureRunner:
    """Only temporary fixture files, never a subprocess or real device."""

    def __init__(self, document: dict, output: Path | None = None):
        self.document = document
        self.output = output
        self.calls: list[tuple] = []
        self.raw: bytes | None = None
        self.returncode: int | None = None
        self.timed_out = False
        self.output_limit_exceeded = False
        self.payload = bytes(range(16))

    def __call__(
        self, arguments: tuple[str, ...], timeout_seconds: float, limit: int
    ) -> NativeProcessResult:
        self.calls.append((arguments, timeout_seconds, limit))
        if self.output is not None:
            (self.output / "frame-000000.yuy2").write_bytes(self.payload)
        code = self.returncode
        if code is None:
            code = 0 if self.document["status"] == "OK" else 1
        return NativeProcessResult(
            code,
            self.raw if self.raw is not None else json.dumps(self.document).encode(),
            timed_out=self.timed_out,
            output_limit_exceeded=self.output_limit_exceeded,
        )


def client(tmp_path: Path, runner: FixtureRunner) -> WindowsCameraWorkerClient:
    executable = tmp_path / "fixture-helper.exe"
    executable.write_bytes(b"INCAPABLE TEST HELPER; NEVER EXECUTED")
    return WindowsCameraWorkerClient(
        executable, hashlib.sha256(executable.read_bytes()).hexdigest(), runner=runner
    )


def capture_with(
    client: WindowsCameraWorkerClient,
    output: Path,
    authorize=lambda request: None,
    **extra,
):
    return client.capture(
        BINDING,
        MODE,
        output,
        source_sha256="a" * 64,
        campaign_id="fixture-001",
        budget=BUDGET,
        authorize=authorize,
        **extra,
    )


def test_constructor_is_inert_even_when_helper_is_missing(tmp_path: Path):
    runner = FixtureRunner(receipt())
    value = WindowsCameraWorkerClient(tmp_path / "missing.exe", "a" * 64, runner=runner)
    assert runner.calls == []
    with pytest.raises(CameraWorkerError, match="CAMERA_HELPER_UNAVAILABLE"):
        value.enumerate_metadata()
    assert runner.calls == []


def test_metadata_inventory_is_explicit_bounded_and_never_activates(tmp_path: Path):
    runner = FixtureRunner(receipt())
    value = client(tmp_path, runner).enumerate_metadata(duration_ms=700)
    assert value.operation == "inventory" and value.cleanup_confirmed
    assert value.candidates[0].endpoint_sha256 == BINDING.endpoint_sha256
    assert not any(value.counts.values())
    assert runner.calls[0][0][1:] == ("inventory", "--max-ms", "700")
    assert runner.calls[0][1:] == (5.7, MAX_IPC_BYTES)
    assert not value.effect_uncertain


def test_inventory_reordering_does_not_select_first_camera(tmp_path: Path):
    root = receipt()
    root["devices"].insert(
        0,
        {
            "symbolic_link": "another-opaque-endpoint",
            "friendly_name": "SYNTHETIC camera",
        },
    )
    value = client(tmp_path, FixtureRunner(root)).enumerate_metadata()
    assert value.selected_endpoint is None
    assert value.candidates[1].symbolic_link == ENDPOINT


def test_hash_mismatch_blocks_before_authorization_or_dispatch(tmp_path: Path):
    runner = FixtureRunner(receipt("probe"))
    value = client(tmp_path, runner)
    value.native_executable.write_bytes(b"changed")
    approvals = []
    with pytest.raises(CameraWorkerError, match="CAMERA_HELPER_HASH_MISMATCH"):
        value.probe(
            BINDING,
            source_sha256="a" * 64,
            campaign_id="probe",
            budget=BUDGET,
            authorize=approvals.append,
        )
    assert not approvals and not runner.calls


def test_authorization_binds_request_and_denial_never_dispatches(tmp_path: Path):
    runner = FixtureRunner(receipt("probe"))
    value = client(tmp_path, runner)
    approvals = []

    def deny(request):
        approvals.append(request)
        raise RuntimeError("coordinator refused stale authority")

    with pytest.raises(RuntimeError, match="stale authority"):
        value.probe(
            BINDING,
            source_sha256="a" * 64,
            campaign_id="probe",
            budget=BUDGET,
            authorize=deny,
        )
    request = approvals[0]
    assert request.binding == BINDING
    assert request.source_sha256 == "a" * 64
    assert request.operation == "probe" and request.output_directory is None
    assert request.mode is None and request.controls == ()
    assert len(request.arguments_sha256) == 64
    assert not runner.calls


def test_absent_authorizer_cannot_activate(tmp_path: Path):
    runner = FixtureRunner(receipt("probe"))
    with pytest.raises(CameraWorkerError, match="CAMERA_AUTHORIZATION_REQUIRED"):
        client(tmp_path, runner).probe(
            BINDING,
            source_sha256="a" * 64,
            campaign_id="probe",
            budget=BUDGET,
            authorize=None,
        )
    assert not runner.calls


def test_probe_inspects_modes_but_does_not_write_or_capture(tmp_path: Path):
    runner = FixtureRunner(receipt("probe"))
    approvals = []
    result = client(tmp_path, runner).probe(
        BINDING,
        source_sha256="a" * 64,
        campaign_id="probe",
        budget=BUDGET,
        authorize=approvals.append,
    )
    assert len(approvals) == 1 and len(runner.calls) == 1
    assert result.modes[0].same_format(MODE)
    assert result.controls == () and result.frames == ()
    assert result.cleanup_confirmed


def test_capture_binary_hash_and_clock_domains_are_preserved(tmp_path: Path):
    output = tmp_path / "new-campaign"
    output.mkdir()
    runner = FixtureRunner(receipt("capture"), output)
    approvals = []
    result = capture_with(client(tmp_path, runner), output, approvals.append)
    frame = result.frames[0]
    assert frame.sha256 == hashlib.sha256(bytes(range(16))).hexdigest()
    assert frame.media_timestamp_100ns == -200
    assert frame.host_arrival_qpc == 1234567
    assert frame.qpc_frequency == 10_000_000
    assert frame.host_sequence == 0 and frame.discontinuity is None
    assert approvals[0].output_directory == str(output)
    assert approvals[0].mode == MODE
    assert result.requested_mode.stride_bytes is None
    assert result.observed_mode.stride_bytes == 8
    assert b"base64" not in json.dumps(runner.document).encode()
    with pytest.raises(TypeError):
        result.counts["source_opened"] = 3


@pytest.mark.parametrize(
    "mutation",
    [
        lambda r: r.update(schema="wrong"),
        lambda r: r.update(unexpected=True),
        lambda r: r.update(selected_endpoint="wrong-camera"),
        lambda r: r["observed_mode"].update(width=2),
        lambda r: r["modes"].clear(),
        lambda r: r["frames"][0].update(filename="../secret.yuy2"),
        lambda r: r["frames"][0].update(stride_bytes=2),
        lambda r: r["frames"][0].update(stride_bytes=-8, row0_offset_bytes=0),
        lambda r: r["frames"][0].update(length_bytes=15),
        lambda r: r["frames"][0].update(length_bytes=17),
        lambda r: r["frames"][0].update(host_sequence=1),
        lambda r: r["frames"][0].update(host_arrival_qpc=True),
        lambda r: r["frames"][0].update(qpc_frequency=0),
        lambda r: r["frames"][0].update(sensor_sequence=1),
        lambda r: r["counts"].update(source_activation_attempts=2),
        lambda r: r["counts"].update(control_set_attempts=1),
        lambda r: r["counts"].update(frames_written=0),
        lambda r: r["cleanup"].update(source_shutdown_hr=-1),
        lambda r: r["cleanup"].update(source_released=False),
        lambda r: r["devices"].append(r["devices"][0]),
    ],
)
def test_invalid_post_dispatch_receipts_are_uncertain_and_never_retried(
    tmp_path: Path, mutation
):
    root = receipt("capture")
    mutation(root)
    output = tmp_path / "new-campaign"
    output.mkdir()
    runner = FixtureRunner(root, output)
    with pytest.raises(CameraWorkerError) as error:
        capture_with(client(tmp_path, runner), output)
    assert error.value.effect_uncertain
    assert len(runner.calls) == 1


def test_negative_stride_is_allowed_only_with_valid_row_origin(tmp_path: Path):
    root = receipt("capture")
    root["frames"][0].update(stride_bytes=-8, row0_offset_bytes=8)
    output = tmp_path / "new-campaign"
    output.mkdir()
    result = capture_with(client(tmp_path, FixtureRunner(root, output)), output)
    assert result.frames[0].stride_bytes == -8


@pytest.mark.parametrize(
    "fault",
    [
        "timed_out",
        "output_limit_exceeded",
        "malformed",
        "duplicate",
        "nonfinite",
        "too_large",
        "exit_mismatch",
    ],
)
def test_worker_ipc_faults_never_retry(tmp_path: Path, fault: str):
    runner = FixtureRunner(receipt("probe"))
    if fault in {"timed_out", "output_limit_exceeded"}:
        setattr(runner, fault, True)
    elif fault == "malformed":
        runner.raw = b"not JSON"
    elif fault == "duplicate":
        runner.raw = b'{"schema":1,"schema":2}'
    elif fault == "nonfinite":
        runner.raw = b'{"schema":NaN}'
    elif fault == "too_large":
        runner.raw = b"x" * (MAX_IPC_BYTES + 1)
    else:
        runner.returncode = 1
    with pytest.raises(CameraWorkerError) as error:
        client(tmp_path, runner).probe(
            BINDING,
            source_sha256="a" * 64,
            campaign_id="probe",
            budget=BUDGET,
            authorize=lambda request: None,
        )
    assert error.value.effect_uncertain and len(runner.calls) == 1


def test_failed_shutdown_remains_explicitly_uncertain(tmp_path: Path):
    root = receipt("probe")
    root.update(status="FAILED", reason_code="SOURCE_SHUTDOWN_FAILED")
    root["cleanup"]["source_shutdown_hr"] = -1
    result = client(tmp_path, FixtureRunner(root)).probe(
        BINDING,
        source_sha256="a" * 64,
        campaign_id="probe",
        budget=BUDGET,
        authorize=lambda request: None,
    )
    assert not result.cleanup_confirmed and result.effect_uncertain
    assert result.reason_code == "SOURCE_SHUTDOWN_FAILED"


def test_removed_endpoint_is_known_preopen_failure(tmp_path: Path):
    root = receipt("inventory")
    root.update(
        operation="probe",
        status="FAILED",
        reason_code="CAMERA_IDENTITY_NOT_PRESENT",
        selected_endpoint=ENDPOINT,
    )
    root["devices"] = []
    result = client(tmp_path, FixtureRunner(root)).probe(
        BINDING,
        source_sha256="a" * 64,
        campaign_id="probe",
        budget=BUDGET,
        authorize=lambda request: None,
    )
    assert result.cleanup_confirmed and not result.effect_uncertain
    assert not any(result.counts.values())


def test_probe_cannot_hide_control_writes(tmp_path: Path):
    root = receipt("probe")
    root["counts"]["control_set_attempts"] = 1
    with pytest.raises(CameraWorkerError):
        client(tmp_path, FixtureRunner(root)).probe(
            BINDING,
            source_sha256="a" * 64,
            campaign_id="probe",
            budget=BUDGET,
            authorize=lambda request: None,
        )


def test_inventory_cannot_hide_activation(tmp_path: Path):
    root = receipt()
    root["counts"]["source_activation_attempts"] = 1
    with pytest.raises(CameraWorkerError) as error:
        client(tmp_path, FixtureRunner(root)).enumerate_metadata()
    # Contract violation remains visible, but inventory has no admitted capture
    # authority; the caller must investigate rather than assume a device test.
    assert "INVALID_CAMERA_CONTRACT" in str(error.value)
    assert error.value.effect_uncertain


@pytest.mark.parametrize(
    "fault",
    [
        "existing_output",
        "bad_binding",
        "frame_budget",
        "duplicate_control",
        "lens_focus",
    ],
)
def test_invalid_requests_stop_before_any_dispatch(tmp_path: Path, fault: str):
    runner = FixtureRunner(receipt("capture"))
    value = client(tmp_path, runner)
    output = tmp_path / "campaign"
    output.mkdir()
    with pytest.raises(CameraWorkerError):
        if fault == "existing_output":
            (output / "keep.txt").write_text("user evidence")
            capture_with(value, output)
        elif fault == "bad_binding":
            CameraEndpointBinding(ENDPOINT, "f" * 64, "b" * 64)
        elif fault == "frame_budget":
            value.capture(
                BINDING,
                NativeCameraMode(5472, 3648, 9, 1),
                output,
                source_sha256="a" * 64,
                campaign_id="x",
                budget=BUDGET,
                authorize=lambda request: None,
            )
        elif fault == "duplicate_control":
            capture_with(
                value,
                output,
                controls=(
                    CameraControlSetting("gain", 1),
                    CameraControlSetting("gain", 2),
                ),
            )
        else:
            CameraControlSetting("focus", 4)
    assert not runner.calls


@pytest.mark.parametrize(
    "field,value",
    [
        ("duration_ms", True),
        ("max_frames", 33),
        ("max_frames", 0),
        ("duration_ms", 300001),
        ("max_frame_bytes", 64 * 1024 * 1024 + 1),
    ],
)
def test_budgets_are_finite_and_closed(field: str, value):
    with pytest.raises(CameraWorkerError):
        CameraCampaignBudget(**{field: value})


def test_control_readback_is_required_and_manual_value_exact(tmp_path: Path):
    root = receipt("capture")
    root["counts"]["control_set_attempts"] = 1
    root["controls"] = [
        {
            "control_id": "exposure",
            "minimum": -12,
            "maximum": -1,
            "step": 1,
            "default": -5,
            "capability_flags": 3,
            "value": -4,
            "flags": 2,
            "unit": "log2_seconds",
        }
    ]
    output = tmp_path / "campaign"
    output.mkdir()
    with pytest.raises(CameraWorkerError, match="control did not read back exactly"):
        capture_with(
            client(tmp_path, FixtureRunner(root, output)),
            output,
            controls=(CameraControlSetting("exposure", -5),),
        )


def test_exact_control_request_and_readback_are_retained(tmp_path: Path):
    root = receipt("capture")
    root["counts"]["control_set_attempts"] = 1
    root["controls"] = [
        {
            "control_id": "exposure",
            "minimum": -12,
            "maximum": -1,
            "step": 1,
            "default": -5,
            "capability_flags": 3,
            "value": -5,
            "flags": 2,
            "unit": "log2_seconds",
        }
    ]
    output = tmp_path / "campaign"
    output.mkdir()
    runner = FixtureRunner(root, output)
    approved = []
    result = capture_with(
        client(tmp_path, runner),
        output,
        approved.append,
        controls=(CameraControlSetting("exposure", -5),),
    )
    assert result.controls[0].value == -5
    assert runner.calls[0][0][-2:] == ("--controls", "exposure,-5,manual")
    assert approved[0].controls == (CameraControlSetting("exposure", -5),)
