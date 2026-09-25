"""Pure preparation plus incapable-runner execution; never run a native helper."""

from __future__ import annotations

import builtins
from dataclasses import FrozenInstanceError, asdict, replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.providers.windows import camera_worker_client as camera


ENDPOINT = "incapable-preparation-fixture-only"
SOURCE = "a" * 64
HELPER_BYTES = b"INCAPABLE fixture bytes, never executable"


def inputs():
    return (
        camera.CameraEndpointBinding(
            ENDPOINT, hashlib.sha256(ENDPOINT.encode()).hexdigest(), "b" * 64
        ),
        camera.NativeCameraMode(4, 2, 9, 1),
        camera.CameraCampaignBudget(500, 1, 16, 16),
    )


class IncapableRunner:
    """Produce a strict native-v1-shaped receipt and tiny private file fixture."""

    def __init__(self):
        self.calls = []

    def __call__(self, arguments, timeout_seconds, limit):
        self.calls.append((arguments, timeout_seconds, limit))
        operation = arguments[1]
        capture = operation == "capture"
        assert operation in {"probe", "capture"}
        binding, mode, _ = inputs()
        observed = {**asdict(mode), "stride_bytes": 8}
        frame = {
            "filename": "frame-000000.yuy2",
            "length_bytes": 16,
            "stride_bytes": 8,
            "row0_offset_bytes": 0,
            "host_sequence": 0,
            "media_timestamp_100ns": -17,
            "host_arrival_qpc": 1024,
            "qpc_frequency": 10_000_000,
            "discontinuity": None,
        }
        if capture:
            output = Path(arguments[arguments.index("--output") + 1])
            with (output / frame["filename"]).open("xb") as target:
                target.write(bytes(range(16)))
        controls = []
        if "--controls" in arguments:
            wire = arguments[arguments.index("--controls") + 1]
            for encoded in wire.split(";"):
                control_id, value, mode_name = encoded.split(",")
                controls.append(
                    {
                        "control_id": control_id,
                        "minimum": -100,
                        "maximum": 100,
                        "step": 1,
                        "default": 0,
                        "capability_flags": 3,
                        "value": int(value),
                        "flags": 2 if mode_name == "manual" else 1,
                        "unit": "INCAPABLE_DRIVER_UNITS",
                    }
                )
        body = {
            "schema": camera.PROTOCOL_SCHEMA,
            "operation": operation,
            "status": "OK",
            "reason_code": None,
            "selected_endpoint": binding.symbolic_link,
            "devices": [
                {"symbolic_link": ENDPOINT, "friendly_name": "INCAPABLE FIXTURE"}
            ],
            "modes": [observed],
            "requested_mode": asdict(mode) if capture else None,
            "observed_mode": observed if capture else None,
            "controls": controls,
            "frames": [frame] if capture else [],
            "counts": {
                "source_activation_attempts": 1,
                "source_opened": 1,
                "control_set_attempts": len(controls),
                "samples_received": int(capture),
                "frames_written": int(capture),
                "source_shutdown_attempts": 1,
            },
            "cleanup": {
                "source_shutdown_hr": 0,
                "source_released": True,
                "mf_shutdown_hr": 0,
                "com_uninitialized": True,
            },
            "limitations": ["INCAPABLE FIXTURE; NO HARDWARE OBSERVED"],
        }
        return camera.NativeProcessResult(0, json.dumps(body).encode())


def fixture_client(tmp_path, runner):
    helper = tmp_path / "incapable-helper.exe"
    helper.write_bytes(HELPER_BYTES)
    return camera.WindowsCameraWorkerClient(
        helper, hashlib.sha256(HELPER_BYTES).hexdigest(), runner=runner
    )


def prepare(client, operation, output, *, controls=()):
    binding, mode, budget = inputs()
    common = dict(source_sha256=SOURCE, campaign_id="prepared-001", budget=budget)
    if operation == "probe":
        return client.prepare_probe(binding, **common)
    return client.prepare_capture(binding, mode, output, controls=controls, **common)


def execute(client, operation, output, authorize, *, controls=()):
    binding, mode, budget = inputs()
    common = dict(
        source_sha256=SOURCE,
        campaign_id="prepared-001",
        budget=budget,
        authorize=authorize,
    )
    if operation == "probe":
        return client.probe(binding, **common)
    return client.capture(binding, mode, output, controls=controls, **common)


@pytest.mark.parametrize("operation", ["probe", "capture"])
def test_preparation_is_filesystem_and_provider_inert(tmp_path, monkeypatch, operation):
    def forbidden(*args, **kwargs):
        pytest.fail("preparation performed filesystem/provider/authorization effects")

    helper = tmp_path / "not-installed" / "helper.exe"
    output = tmp_path / "not-created" / "frames"
    client = camera.WindowsCameraWorkerClient(helper, "e" * 64, runner=forbidden)
    with monkeypatch.context() as patch:
        patch.setattr(builtins, "open", forbidden)
        for name in (
            "open",
            "stat",
            "lstat",
            "iterdir",
            "exists",
            "is_dir",
            "is_file",
            "mkdir",
            "resolve",
            "absolute",
            "cwd",
            "touch",
            "read_bytes",
        ):
            patch.setattr(Path, name, forbidden)
        patch.setattr(camera.shutil, "disk_usage", forbidden)
        patch.setattr(camera.subprocess, "Popen", forbidden)
        patch.setattr(camera, "_hash_file", forbidden)
        patch.setattr(camera, "_plain_path", forbidden)
        patch.setattr(client, "enumerate_metadata", forbidden)
        patch.setattr(client, "resolve_identity_metadata", forbidden)
        patch.setattr(client, "_registered_arguments", forbidden)
        plan = prepare(client, operation, output)
    assert type(plan) is camera.PreparedCameraCampaign
    assert plan.request.operation == operation
    assert plan.arguments[0] == str(helper)
    assert plan.request.helper_sha256 == "e" * 64
    assert not helper.parent.exists() and not output.parent.exists()


@pytest.mark.parametrize(
    "operation,with_controls", [("probe", False), ("capture", False), ("capture", True)]
)
def test_actual_execution_authorizes_exact_prepared_request(
    tmp_path, operation, with_controls
):
    runner = IncapableRunner()
    client = fixture_client(tmp_path, runner)
    output = tmp_path / "new-frames"
    controls = (camera.CameraControlSetting("gain", 3),) if with_controls else ()
    plan = prepare(client, operation, output, controls=controls)
    assert runner.calls == [] and not output.exists()
    if operation == "capture":
        output.mkdir()
    approved = []

    def authorize(request):
        assert request == plan.request
        assert request is not plan.request
        approved.append(request)

    result = execute(client, operation, output, authorize, controls=controls)
    assert result.cleanup_confirmed and not result.effect_uncertain
    assert approved == [plan.request]
    assert runner.calls == [(plan.arguments, 5.5, camera.MAX_IPC_BYTES)]
    canonical = json.dumps(
        plan.arguments, ensure_ascii=False, separators=(",", ":")
    ).encode()
    assert plan.request.arguments_sha256 == hashlib.sha256(canonical).hexdigest()
    if operation == "capture":
        assert result.frames[0].sha256 == hashlib.sha256(bytes(range(16))).hexdigest()
        assert result.frames[0].media_timestamp_100ns == -17


def test_preparation_defensively_snapshots_all_nested_inputs(tmp_path):
    client = camera.WindowsCameraWorkerClient(tmp_path / "absent.exe", "e" * 64)
    binding, mode, budget = inputs()
    control = camera.CameraControlSetting("gain", 3)
    plan = client.prepare_capture(
        binding,
        mode,
        tmp_path / "future",
        source_sha256=SOURCE,
        campaign_id="copy-001",
        budget=budget,
        controls=(control,),
    )
    original = asdict(plan.request)
    assert plan.request.binding is not binding
    assert plan.request.mode is not mode
    assert plan.request.budget is not budget
    assert plan.request.controls[0] is not control
    for value, key, changed in (
        (binding, "binding_sha256", "c" * 64),
        (mode, "fps_numerator", 8),
        (budget, "duration_ms", 700),
        (control, "value", 2),
    ):
        object.__setattr__(value, key, changed)
    assert asdict(plan.request) == original
    with pytest.raises(FrozenInstanceError):
        plan.arguments = ()
    with pytest.raises(FrozenInstanceError):
        plan.request.campaign_id = "changed"


@pytest.mark.parametrize(
    "drift",
    [
        "helper_changed",
        "helper_removed",
        "output_occupied",
        "output_removed",
        "insufficient_disk",
    ],
)
def test_execution_revalidates_filesystem_after_preparation(
    tmp_path, monkeypatch, drift
):
    runner = IncapableRunner()
    client = fixture_client(tmp_path, runner)
    output = tmp_path / "frames"
    output.mkdir()
    plan = prepare(client, "capture", output)
    if drift == "helper_changed":
        client.native_executable.write_bytes(b"different incapable fixture")
    elif drift == "helper_removed":
        client.native_executable.unlink()
    elif drift == "output_occupied":
        (output / "keep.txt").write_bytes(b"do not overwrite")
    elif drift == "output_removed":
        output.rmdir()
    else:
        monkeypatch.setattr(
            camera.shutil, "disk_usage", lambda _: SimpleNamespace(free=15)
        )
    approved = []
    with pytest.raises((camera.CameraWorkerError, OSError)):
        execute(client, "capture", output, approved.append)
    assert not approved and not runner.calls
    assert plan.request.output_directory == str(output)
    if drift == "output_occupied":
        assert (output / "keep.txt").read_bytes() == b"do not overwrite"


@pytest.mark.parametrize("operation", ["probe", "capture"])
def test_denied_or_absent_authorizer_never_dispatches_prepared_operation(
    tmp_path, operation
):
    runner = IncapableRunner()
    client = fixture_client(tmp_path, runner)
    output = tmp_path / "frames"
    output.mkdir()
    plan = prepare(client, operation, output)
    approvals = []

    def deny(request):
        assert request == plan.request
        approvals.append(request)
        raise RuntimeError("fixture authority deliberately denied")

    with pytest.raises(RuntimeError, match="deliberately denied"):
        execute(client, operation, output, deny)
    with pytest.raises(camera.CameraWorkerError, match="CAMERA_AUTHORIZATION_REQUIRED"):
        execute(client, operation, output, None)
    assert len(approvals) == 1 and not runner.calls


@pytest.mark.parametrize(
    "part,key,value",
    [
        ("binding", "endpoint_sha256", "f" * 64),
        ("binding", "extra_unregistered_field", True),
        ("mode", "width", True),
        ("mode", "fps_numerator", 0),
        ("mode", "subtype", "MJPG"),
        ("budget", "max_frames", 33),
        ("budget", "max_frame_bytes", 15),
        ("control", "value", True),
        ("control", "control_id", "focus"),
    ],
)
def test_forged_nested_frozen_inputs_are_revalidated(tmp_path, part, key, value):
    client = camera.WindowsCameraWorkerClient(tmp_path / "absent.exe", "e" * 64)
    binding, mode, budget = inputs()
    control = camera.CameraControlSetting("gain", 3)
    target = dict(binding=binding, mode=mode, budget=budget, control=control)[part]
    object.__setattr__(target, key, value)
    with pytest.raises(camera.CameraWorkerError):
        client.prepare_capture(
            binding,
            mode,
            tmp_path / "frames",
            source_sha256=SOURCE,
            campaign_id="forged-001",
            budget=budget,
            controls=(control,),
        )


@pytest.mark.parametrize("part", ["binding", "mode", "budget", "control", "controls"])
def test_untyped_or_subclass_inputs_are_rejected(tmp_path, part):
    client = camera.WindowsCameraWorkerClient(tmp_path / "absent.exe", "e" * 64)
    binding, mode, budget = inputs()
    controls = (camera.CameraControlSetting("gain", 3),)
    if part == "binding":
        binding = type("UnexpectedBinding", (camera.CameraEndpointBinding,), {})(
            **asdict(binding)
        )
    elif part == "mode":
        mode = asdict(mode)
    elif part == "budget":
        budget = asdict(budget)
    elif part == "control":
        controls = (asdict(controls[0]),)
    else:
        controls = list(controls)
    with pytest.raises(camera.CameraWorkerError):
        client.prepare_capture(
            binding,
            mode,
            tmp_path / "frames",
            source_sha256=SOURCE,
            campaign_id="untyped-001",
            budget=budget,
            controls=controls,
        )


@pytest.mark.parametrize("operation", ["probe", "capture"])
def test_authorization_cannot_mutate_prepared_request_and_then_dispatch(
    tmp_path, operation
):
    runner = IncapableRunner()
    client = fixture_client(tmp_path, runner)
    output = tmp_path / "frames"
    output.mkdir()

    def mutate(request):
        object.__setattr__(request.budget, "duration_ms", 501)

    with pytest.raises(
        camera.CameraWorkerError, match="authorization changed"
    ) as error:
        execute(client, operation, output, mutate)
    assert not error.value.effect_uncertain and not runner.calls


@pytest.mark.parametrize(
    "mutation", ["dictionary", "subclass", "extra_field", "helper_registration"]
)
def test_authorization_cannot_substitute_equal_looking_types_or_registration(
    tmp_path, mutation
):
    runner = IncapableRunner()
    client = fixture_client(tmp_path, runner)
    output = tmp_path / "frames"
    output.mkdir()

    def mutate(request):
        if mutation == "dictionary":
            object.__setattr__(request, "budget", asdict(request.budget))
        elif mutation == "subclass":
            forged = type("UnexpectedMode", (camera.NativeCameraMode,), {})(
                **asdict(request.mode)
            )
            object.__setattr__(request, "mode", forged)
        elif mutation == "extra_field":
            object.__setattr__(request, "unregistered_extra", True)
        else:
            client.expected_sha256 = "f" * 64

    with pytest.raises(camera.CameraWorkerError) as error:
        execute(client, "capture", output, mutate)
    assert not error.value.effect_uncertain and not runner.calls


def test_fresh_request_rejects_stale_review_after_valid_nested_input_change(tmp_path):
    runner = IncapableRunner()
    client = fixture_client(tmp_path, runner)
    binding, mode, budget = inputs()
    plan = client.prepare_probe(
        binding, source_sha256=SOURCE, campaign_id="stale-001", budget=budget
    )
    approvals = []

    def reject_stale(request):
        approvals.append(request)
        if request != plan.request:
            raise RuntimeError("fixture rejected stale reviewed request")

    with pytest.raises(RuntimeError, match="stale reviewed request"):
        client.probe(
            replace(binding, binding_sha256="d" * 64),
            source_sha256=SOURCE,
            campaign_id="stale-001",
            budget=budget,
            authorize=reject_stale,
        )
    # The argv hash alone deliberately does not represent the whole request:
    # reviewed identity provenance is separately bound in CameraActivationRequest.
    assert approvals[0].arguments_sha256 == plan.request.arguments_sha256
    assert approvals[0].binding != plan.request.binding and not runner.calls


@pytest.mark.parametrize(
    "path_kind",
    ["relative_helper", "relative_output", "parent_helper", "parent_output"],
)
def test_plan_rejects_lexically_ambiguous_paths_without_reading_them(
    tmp_path, path_kind
):
    helper, output = tmp_path / "helper.exe", tmp_path / "frames"
    if path_kind == "relative_helper":
        helper = Path("relative.exe")
    elif path_kind == "relative_output":
        output = Path("relative-frames")
    elif path_kind == "parent_helper":
        helper = tmp_path / "unknown" / ".." / "helper.exe"
    else:
        output = tmp_path / "unknown" / ".." / "frames"
    client = camera.WindowsCameraWorkerClient(helper, "e" * 64)
    with pytest.raises(
        camera.CameraWorkerError, match="absolute path without parent traversal"
    ):
        prepare(client, "capture", output)


def test_plan_request_remains_compatible_with_pure_ingest_preparation(tmp_path):
    from rocell.application.camera_capture_dataset import FramePlan, PreviewTransform
    from rocell.application.windows_camera_capture_ingest import (
        prepare_windows_camera_ingest,
    )

    client = camera.WindowsCameraWorkerClient(tmp_path / "absent.exe", "e" * 64)
    output = tmp_path / "absent-raw"
    plan = prepare(client, "capture", output)
    retained = prepare_windows_camera_ingest(
        plan.request,
        capture_directory=output,
        dataset_root=tmp_path / "absent-datasets",
        source_sha256=SOURCE,
        settings_epoch="c" * 64,
        domain="INCAPABLE_NATIVE_FIXTURE",
        frames=(FramePlan("frame-000000", preview=PreviewTransform(0, 0, 4, 2, 4, 2)),),
    )
    assert retained.source_sha256 == SOURCE
    assert retained.capture_directory == output
    assert not output.exists() and not retained.dataset_root.exists()
