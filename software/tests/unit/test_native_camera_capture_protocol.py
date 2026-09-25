"""Pure capture preparation/admission: no native process, port or pixel access."""

from dataclasses import asdict, replace
from pathlib import Path
import threading

import pytest

from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraControlSetting,
    NativeCameraReceiptMetadata,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.native_camera_capture_protocol import (
    NativeCameraCaptureAdmissionRequest,
    NativeCaptureConfiguration,
    local_capture_path,
    native_camera_capture_release,
    parse_owned_native_camera_capture_result,
)
from rocell.providers.windows.native_camera_capture_registration import (
    HELPER_RELATIVE_PATH,
    PreparedOwnedNativeCapture,
    create_native_camera_capture_runtime_registration,
    prepare_owned_native_capture,
)
from rocell.providers.windows.native_camera_parent_admission import (
    NativeCameraParentHandshake,
)
from rocell.providers.windows.native_camera_protocol import (
    NativeCameraAdmissionRequest,
    canonical,
    RESULT_SCHEMA,
    native_camera_release,
)
from rocell.providers.windows.owned_native_camera_runner import OwnedNativeCameraRunner
from test_native_camera_protocol import ready_for
from test_native_camera_parent_admission import Clock
from test_windows_camera_worker import BINDING, MODE, receipt


def capture_inputs(tmp_path, *, mode=MODE, controls=()):
    runtime = create_native_camera_capture_runtime_registration(
        tmp_path,
        source_sha256="a" * 64,
        catalog_sha256="b" * 64,
        helper_sha256="c" * 64,
        build_record_sha256="d" * 64,
    )
    directory = tmp_path / "working"
    plan = WindowsCameraWorkerClient(
        tmp_path / HELPER_RELATIVE_PATH, "c" * 64
    ).prepare_capture(
        BINDING,
        mode,
        directory / "capture-attempt-1",
        source_sha256="a" * 64,
        campaign_id="attempt-1",
        budget=CameraCampaignBudget(5000, 1, 32, 32),
        controls=controls,
    )
    return (
        runtime,
        plan,
        dict(
            session_id="session-1",
            operation_sha256="e" * 64,
            permit_sha256="f" * 64,
            working_directory=directory,
        ),
    )


def capture_prepared(tmp_path, **kwargs):
    runtime, plan, args = capture_inputs(tmp_path, **kwargs)
    return prepare_owned_native_capture(runtime, plan, **args)


def capture_result(request, ready, raw=None):
    return dict(
        schema=RESULT_SCHEMA,
        request_sha256=request.request_sha256,
        child_pid=ready.to_dict()["child_pid"],
        challenge_sha256=ready.challenge_sha256,
        permit_sha256=request.to_dict()["permit_sha256"],
        native_receipt=receipt("capture") if raw is None else raw,
    )


def test_full_preparation_reconstruction_has_no_filesystem_or_device_io(
    tmp_path, monkeypatch
):
    def forbidden(*a, **kw):
        pytest.fail("Pure capture preparation accessed a device or file")

    with monkeypatch.context() as patch:
        for method in ("open", "stat", "lstat", "resolve", "mkdir", "iterdir"):
            patch.setattr(Path, method, forbidden)
        for method in ("probe", "capture", "_registered_arguments"):
            patch.setattr(WindowsCameraWorkerClient, method, forbidden)
        runtime, plan, args = capture_inputs(tmp_path)
        prepared = prepare_owned_native_capture(runtime, plan, **args)
        assert asdict(prepared.camera_plan) == asdict(plan)
        assert prepared.required_lifetime_ns == 17_000_000_000
        assert prepared.registration.argv[0] == "--owned-capture"
        assert prepared.registration.composition == "PHYSICAL_UNQUALIFIED"
        assert prepared.runtime.to_dict()["dispatch_enabled"] is False
        assert PreparedOwnedNativeCapture(prepared.payload).payload == prepared.payload
        request = prepared.admission_request
        assert request.to_dict()["admission_timeout_ms"] == 5000
        assert (
            request.configuration.output_directory
            == args["working_directory"] / "capture-attempt-1"
        )


@pytest.mark.parametrize(
    "path",
    [
        "C:\\",
        r"C:\a\..\b",
        r"C:\a\.\b",
        r"C:\a\\b",
        "C:/a/b",
        r"\\server\share\folder",
        r"C:\a\b:stream",
        r"C:\a\NUL.txt",
        "C:\\a\\trailing.",
        "C:\\a\\trailing ",
        "relative\\leaf",
    ],
)
def test_output_aliases_and_nonlocal_paths_denied(path):
    with pytest.raises(ValueError):
        local_capture_path(path)


@pytest.mark.parametrize(
    "field,value",
    [
        ("width", 3),
        ("width", True),
        ("height", 0),
        ("fps_denominator", 0),
        ("subtype", "MJPG"),
        ("frame_count", 33),
        ("max_frame_bytes", 1),
        ("max_total_bytes", 1),
        ("requested_stride_bytes", "0"),
        ("requested_stride_bytes", "+8"),
        ("requested_stride_bytes", "08"),
        ("requested_stride_bytes", "7"),
        ("requested_stride_bytes", "32"),
        ("controls", "brightness,+1,manual"),
        ("controls", "gain,0,manual;brightness,0,manual"),
        ("controls", "brightness,0,manual;brightness,0,manual"),
        ("controls", "focus,1,auto"),
    ],
)
def test_closed_configuration_boundaries(tmp_path, field, value):
    data = capture_prepared(tmp_path).admission_request.configuration.to_dict()
    data[field] = value
    with pytest.raises((ValueError, RuntimeError)):
        NativeCaptureConfiguration(canonical(data))


def test_probe_and_capture_cannot_substitute_requests_or_release(tmp_path):
    request = capture_prepared(tmp_path).admission_request
    ready = ready_for(request)
    with pytest.raises(ValueError):
        NativeCameraAdmissionRequest(request.payload)
    with pytest.raises(ValueError):
        native_camera_release(request, ready)
    assert native_camera_capture_release(request, ready).endswith(b"\n")
    for field, value in (
        ("schema", "rocell.native_camera_admission_request.v1"),
        ("admission_timeout_ms", 2000),
        ("native_duration_ms", 6000),
    ):
        data = request.to_dict()
        data[field] = value
        with pytest.raises(ValueError):
            NativeCameraCaptureAdmissionRequest(canonical(data))


def test_exact_directory_runtime_and_original_plan_bindings(tmp_path):
    runtime, plan, args = capture_inputs(tmp_path)
    with pytest.raises(ValueError, match="PRIVATE_DIRECTORY"):
        prepare_owned_native_capture(
            runtime, plan, **{**args, "working_directory": tmp_path / "other"}
        )
    with pytest.raises(ValueError):
        prepare_owned_native_capture(
            runtime, replace(plan, arguments=(*plan.arguments, "--extra")), **args
        )
    prepared = prepare_owned_native_capture(runtime, plan, **args)
    changed_case = prepared.to_dict()
    changed_case["working_directory"] = changed_case["working_directory"].replace(
        "working", "WORKING"
    )
    with pytest.raises(ValueError, match="PRIVATE_DIRECTORY"):
        PreparedOwnedNativeCapture(canonical(changed_case))
    for field, value in (
        ("camera_request_sha256", "0" * 64),
        ("helper_sha256", "0" * 64),
        ("runtime_registration_sha256", "0" * 64),
    ):
        doc = prepared.to_dict()
        doc["admission_request"][field] = value
        with pytest.raises(ValueError):
            PreparedOwnedNativeCapture(canonical(doc))


def test_capture_metadata_parser_is_inert_and_has_no_invented_pixel_hash(
    tmp_path, monkeypatch
):
    request = capture_prepared(tmp_path).admission_request
    ready = ready_for(request)

    def forbidden(*a, **kw):
        pytest.fail("Native metadata parser accessed files")

    with monkeypatch.context() as patch:
        for name in ("open", "stat", "iterdir", "lstat"):
            patch.setattr(Path, name, forbidden)
        raw, metadata = parse_owned_native_camera_capture_result(
            canonical(capture_result(request, ready)),
            request=request,
            ready=ready,
            returncode=0,
        )
    assert type(metadata) is NativeCameraReceiptMetadata
    assert metadata.operation == "capture" and len(metadata.frames) == 1
    assert not hasattr(metadata.frames[0], "sha256")
    assert raw["native_receipt"] == receipt("capture")


def test_requested_stride_must_match_successful_native_observation(tmp_path):
    request = capture_prepared(
        tmp_path, mode=replace(MODE, stride_bytes=16)
    ).admission_request
    ready = ready_for(request)
    raw = receipt("capture")
    raw["requested_mode"] = asdict(request.configuration.mode)
    with pytest.raises(ValueError, match="OBSERVED_STRIDE"):
        parse_owned_native_camera_capture_result(
            canonical(capture_result(request, ready, raw)),
            request=request,
            ready=ready,
            returncode=0,
        )


@pytest.mark.parametrize("change", ["stride", "rational"])
def test_requested_mode_echo_cannot_change_admitted_values(tmp_path, change):
    request = capture_prepared(tmp_path).admission_request
    ready = ready_for(request)
    raw = receipt("capture")
    if change == "stride":
        raw["requested_mode"]["stride_bytes"] = 16
    else:
        raw["requested_mode"]["fps_numerator"] = 18
        raw["requested_mode"]["fps_denominator"] = 2
    with pytest.raises(ValueError, match="REQUESTED_MODE_MISMATCH"):
        parse_owned_native_camera_capture_result(
            canonical(capture_result(request, ready, raw)),
            request=request,
            ready=ready,
            returncode=0,
        )


def test_control_order_is_explicit_not_silently_reinterpreted(tmp_path):
    runtime, plan, args = capture_inputs(
        tmp_path,
        controls=(
            CameraControlSetting("gain", 0),
            CameraControlSetting("brightness", 0),
        ),
    )
    with pytest.raises(ValueError, match="CANONICAL_CAPTURE_CONTROL_ORDER"):
        prepare_owned_native_capture(runtime, plan, **args)


@pytest.mark.parametrize(
    "delay,accepted", [(3_000_000_000, True), (5_000_000_000, False)]
)
def test_parent_capture_timing_keeps_original_finite_window(tmp_path, delay, accepted):
    prepared = capture_prepared(tmp_path)
    clock, cancel, calls = Clock(), threading.Event(), []

    def current(exact):
        assert (
            type(exact) is PreparedOwnedNativeCapture
            and exact.payload == prepared.payload
        )
        calls.append(exact.preparation_sha256)
        if len(calls) == 2:
            clock.now += delay

    parent = NativeCameraParentHandshake(
        prepared, cancellation=cancel, revalidate_consumed_permit=current, _clock=clock
    )
    parent.begin(deadline_ns=21_000_000_000)
    ready = ready_for(prepared.admission_request)
    parent.accept_ready(ready.payload + b"\n", owned_child_pid=123)
    if accepted:
        parent.check_release()
        _, metadata = parent.accept_result(
            canonical(capture_result(prepared.admission_request, ready)), returncode=0
        )
        assert type(metadata) is NativeCameraReceiptMetadata
    else:
        with pytest.raises(ValueError, match="ADMISSION_DEADLINE"):
            parent.check_release()
    assert len(calls) == 2
    with pytest.raises(ValueError):
        parent.begin(deadline_ns=100_000_000_000)


def test_physical_capture_runner_stays_held_before_pin_callback_or_process(
    tmp_path, monkeypatch
):
    from rocell.providers.windows import owned_native_camera_runner as runner

    prepared = capture_prepared(tmp_path)

    def forbidden(*a, **kw):
        pytest.fail("Physical capture hold was bypassed")

    monkeypatch.setattr(runner, "_new_owner", forbidden)
    owner = OwnedNativeCameraRunner(prepared, revalidate_consumed_permit=forbidden)
    assert not owner.status()["consumed"]
    import time

    evidence = owner.run(
        cancellation=threading.Event(), deadline_ns=time.monotonic_ns() + 30_000_000_000
    )
    assert (
        evidence.safe_summary()["primary_error"]
        == "PHYSICAL_PROVIDER_QUALIFICATION_HELD"
    )
