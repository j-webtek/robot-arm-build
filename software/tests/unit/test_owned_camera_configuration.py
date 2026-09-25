"""Probe/configuration tests: pure contracts and fixed incapable children only."""

from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import threading

import pytest

import rocell.providers.windows.owned_camera_runner as runner_module
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraControlSetting,
    CameraWorkerError,
)
from rocell.providers.windows.owned_camera_codec import (
    CONFIG_REQUEST_SCHEMA,
    CONFIG_RESULT_SCHEMA,
    CONFIG_PAYLOAD_SCHEMA,
    REQUEST_SCHEMA,
    RESULT_SCHEMA,
    PAYLOAD_SCHEMA,
    FIXTURE_CONTROL_UNITS,
    fixture_control_observations,
    validate_camera_registration,
    validate_camera_result,
    validate_control_observations,
)
from rocell.providers.windows.owned_camera_runner import (
    FRAME_BYTES,
    OwnedPreparedCameraRunner,
    prepare_owned_camera_fixture,
)
from rocell.providers.windows.owned_worker_process import (
    WorkerProcessBudget,
)
from test_owned_camera_runner import fixture, ExactAuthority


def probe_fixture(tmp_path, *, create=True, scenario="nominal"):
    client, capture, inputs = fixture(tmp_path, create=False)
    working = tmp_path / "probe-working"
    if create:
        working.mkdir()
    inputs.update(
        templates=(),
        working_directory=working,
        scenario=scenario,
        budget=WorkerProcessBudget(
            run_timeout_ms=10000, stdout_bytes=32 * 1024, stderr_bytes=8 * 1024
        ),
    )
    request = capture.request
    probe = client.prepare_probe(
        request.binding,
        source_sha256=request.source_sha256,
        campaign_id=request.campaign_id,
        budget=CameraCampaignBudget(5000, 1, FRAME_BYTES, FRAME_BYTES),
    )
    return client, probe, inputs


def configured_fixture(tmp_path, controls, *, scenario="nominal"):
    client, plan, inputs = fixture(tmp_path)
    request = plan.request
    plan = client.prepare_capture(
        request.binding,
        request.mode,
        Path(request.output_directory),
        source_sha256=request.source_sha256,
        campaign_id=request.campaign_id,
        budget=request.budget,
        controls=controls,
    )
    inputs["scenario"] = scenario
    return client, plan, inputs


def run_client(client, prepared):
    authority = ExactAuthority(prepared, prepared.request.expires_at_ns)
    runner = OwnedPreparedCameraRunner(
        prepared,
        cancellation=threading.Event(),
        deadline_ns=prepared.request.expires_at_ns,
        authorize_owned=authority,
    )
    client.runner = runner
    camera_calls = []

    def authorize(request):
        assert asdict(request) == asdict(prepared.plan.request)
        assert not camera_calls
        camera_calls.append(request)

    request = prepared.plan.request
    try:
        if request.operation == "probe":
            receipt = client.probe(
                request.binding,
                source_sha256=request.source_sha256,
                campaign_id=request.campaign_id,
                budget=request.budget,
                authorize=authorize,
            )
        else:
            receipt = client.capture(
                request.binding,
                request.mode,
                Path(request.output_directory),
                source_sha256=request.source_sha256,
                campaign_id=request.campaign_id,
                budget=request.budget,
                controls=request.controls,
                authorize=authorize,
            )
    except Exception as error:
        return runner, authority, error
    return runner, authority, receipt


def test_probe_preparation_has_no_filesystem_or_worker_effects(tmp_path, monkeypatch):
    _, plan, inputs = probe_fixture(tmp_path, create=False)

    def forbidden(*args, **kwargs):
        pytest.fail("Pure probe preparation must not touch files or workers")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(Path, "lstat", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(runner_module, "OwnedWindowsWorker", forbidden)
    prepared = prepare_owned_camera_fixture(plan, **inputs)
    runner = OwnedPreparedCameraRunner(
        prepared,
        cancellation=threading.Event(),
        deadline_ns=inputs["expires_at_ns"],
        authorize_owned=forbidden,
    )
    assert runner.owned_result is None
    assert prepared.registration.request_schema == CONFIG_REQUEST_SCHEMA
    assert prepared.registration.result_schema == CONFIG_RESULT_SCHEMA
    assert prepared.registration.working_directory == inputs["working_directory"]
    assert prepared.plan == plan
    assert prepared.plan.request.output_directory is None
    assert prepared.plan.request.mode is None and prepared.plan.request.controls == ()
    assert len(prepared.plan.arguments) == 6
    payload = json.loads(prepared.request.payload_json)
    assert payload["schema"] == CONFIG_PAYLOAD_SCHEMA and payload["templates"] == []
    assert payload["working_directory"] == str(inputs["working_directory"])


def test_legacy_capture_protocol_and_fields_remain_unchanged(tmp_path):
    _, plan, inputs = fixture(tmp_path)
    prepared = prepare_owned_camera_fixture(plan, **inputs)
    assert prepared.registration.request_schema == REQUEST_SCHEMA
    assert prepared.registration.result_schema == RESULT_SCHEMA
    payload = json.loads(prepared.request.payload_json)
    assert payload["schema"] == PAYLOAD_SCHEMA
    assert "working_directory" not in payload
    assert prepared.plan.request.controls == ()


@pytest.mark.parametrize(
    "fault",
    [
        "missing-cwd",
        "relative-cwd",
        "templates",
        "drift-scenario",
        "requested-mode",
        "requested-output",
        "requested-controls",
        "mixed-protocol",
    ],
)
def test_probe_rejects_capture_fields_or_unbound_working_directory(tmp_path, fault):
    _, plan, inputs = probe_fixture(tmp_path, create=False)
    if fault == "missing-cwd":
        inputs.pop("working_directory")
    elif fault == "relative-cwd":
        inputs["working_directory"] = Path("relative")
    elif fault == "templates":
        inputs["templates"] = (inputs["fixture_script"],)
    elif fault == "drift-scenario":
        inputs["scenario"] = "control-readback-drift"
    elif fault == "requested-mode":
        _, capture, _ = fixture(tmp_path, create=False)
        plan = replace(plan, request=replace(plan.request, mode=capture.request.mode))
    elif fault == "requested-output":
        plan = replace(
            plan, request=replace(plan.request, output_directory=str(tmp_path / "out"))
        )
    elif fault == "requested-controls":
        plan = replace(
            plan,
            request=replace(plan.request, controls=(CameraControlSetting("gain", 16),)),
        )
    else:
        prepared = prepare_owned_camera_fixture(plan, **inputs)
        registration = replace(
            prepared.registration,
            request_schema=REQUEST_SCHEMA,
            result_schema=RESULT_SCHEMA,
        )
        with pytest.raises(ValueError):
            validate_camera_registration(registration, prepared.request)
        return
    with pytest.raises((ValueError, CameraWorkerError)):
        prepare_owned_camera_fixture(plan, **inputs)


@pytest.mark.parametrize(
    "control",
    [
        {"control_id": "gain", "value": -1, "mode": "manual"},
        {"control_id": "gain", "value": 256, "mode": "manual"},
        {"control_id": "white_balance", "value": 4550, "mode": "manual"},
        {"control_id": "gain", "value": 16, "mode": "auto"},
    ],
)
def test_requested_range_step_and_mode_rejected_before_dispatch(
    tmp_path, control, monkeypatch
):
    _, plan, inputs = configured_fixture(tmp_path, (CameraControlSetting(**control),))
    monkeypatch.setattr(
        runner_module, "OwnedWindowsWorker", lambda *a, **k: pytest.fail("No dispatch")
    )
    with pytest.raises(ValueError):
        prepare_owned_camera_fixture(plan, **inputs)


def test_control_descriptors_are_owned_and_flags_are_closed():
    descriptors = fixture_control_observations()
    assert len(descriptors) == 6 and all(
        row["unit"] == FIXTURE_CONTROL_UNITS for row in descriptors
    )
    descriptors[0]["default"] = 999
    assert fixture_control_observations()[0]["default"] == -6
    for flag in (0, 3, 4, True):
        malformed = list(fixture_control_observations())
        malformed[0]["flags"] = flag
        with pytest.raises(ValueError):
            validate_control_observations(malformed)


def test_probe_working_directory_changes_full_owned_hash_not_native_request(tmp_path):
    _, plan, inputs = probe_fixture(tmp_path, create=False)
    first = prepare_owned_camera_fixture(plan, **inputs)
    second = prepare_owned_camera_fixture(
        plan, **{**inputs, "working_directory": tmp_path / "different"}
    )
    assert first.plan == second.plan
    assert first.request_sha256(inputs["expires_at_ns"]) != second.request_sha256(
        inputs["expires_at_ns"]
    )
    # A forged registration cannot borrow the already bound payload's cwd.
    with pytest.raises(ValueError):
        validate_camera_registration(second.registration, first.request)


native = pytest.mark.skipif(
    os.name != "nt", reason="Actual owned Windows incapable process only"
)


@native
def test_actual_probe_reports_mode_and_six_modeled_controls_without_frame_files(
    tmp_path,
):
    client, plan, inputs = probe_fixture(tmp_path)
    prepared = prepare_owned_camera_fixture(plan, **inputs)
    runner, authority, receipt = run_client(client, prepared)
    assert not isinstance(receipt, Exception), (receipt, runner.owned_result)
    assert (
        receipt.operation == "probe"
        and receipt.status == "OK"
        and receipt.cleanup_confirmed
    )
    assert (
        receipt.requested_mode is None
        and receipt.observed_mode is None
        and not receipt.frames
    )
    assert len(receipt.modes) == 1 and receipt.modes[0].width == 5472
    assert (
        tuple(asdict(control) for control in receipt.controls)
        == fixture_control_observations()
    )
    assert all(
        receipt.counts[key] == 0
        for key in ("control_set_attempts", "samples_received", "frames_written")
    )
    assert (
        receipt.counts["source_opened"]
        == receipt.counts["source_shutdown_attempts"]
        == 1
    )
    assert not list(inputs["working_directory"].iterdir())
    assert authority.calls == 1 and runner.owned_result.status == "SUCCEEDED"
    assert (
        runner.owned_result.tree_exit_confirmed
        and not runner.owned_result.cleanup_errors
    )
    assert runner.owned_result.to_dict()["physical_authority"] is False
    raw = json.loads(runner.owned_result.stdout)
    assert raw["schema"] == CONFIG_RESULT_SCHEMA
    assert raw["fixture_result"]["template_sha256s"] == []
    assert raw["request_sha256"] == prepared.request_sha256(
        prepared.request.expires_at_ns
    )
    changed = json.loads(runner.owned_result.stdout)
    changed["fixture_result"]["native_receipt"]["controls"][0]["flags"] = 3
    with pytest.raises(ValueError):
        validate_camera_result(
            changed,
            payload=json.loads(prepared.request.payload_json),
            request_sha256=runner.expected_request_sha256,
            attempt_id=prepared.request.attempt_id,
            returncode=0,
        )


@native
@pytest.mark.parametrize(
    "scenario", ["identity-mismatch", "cleanup-uncertain", "malformed-result"]
)
def test_actual_probe_faults_retain_owned_diagnostics_without_frame_files(
    tmp_path, scenario
):
    client, plan, inputs = probe_fixture(tmp_path, scenario=scenario)
    prepared = prepare_owned_camera_fixture(plan, **inputs)
    runner, authority, result = run_client(client, prepared)
    assert authority.calls == 1 and runner.owned_result.tree_exit_confirmed
    assert runner.owned_result.stdout and not list(
        inputs["working_directory"].iterdir()
    )
    if scenario == "cleanup-uncertain":
        assert not isinstance(result, Exception)
        assert result.status == "FAILED" and not result.cleanup_confirmed
        assert runner.owned_result.primary_error == "WORKER_EXIT_FAILED"
    else:
        assert isinstance(result, CameraWorkerError)


@native
def test_actual_probe_timeout_terminates_owned_tree_without_frame_files(tmp_path):
    client, plan, inputs = probe_fixture(tmp_path, scenario="child-timeout")
    plan = client.prepare_probe(
        plan.request.binding,
        source_sha256=plan.request.source_sha256,
        campaign_id=plan.request.campaign_id,
        budget=CameraCampaignBudget(100, 1, FRAME_BYTES, FRAME_BYTES),
    )
    inputs["budget"] = WorkerProcessBudget(
        run_timeout_ms=200, stdout_bytes=32 * 1024, stderr_bytes=8 * 1024
    )
    prepared = prepare_owned_camera_fixture(plan, **inputs)
    runner, authority, result = run_client(client, prepared)
    assert isinstance(result, CameraWorkerError)
    assert result.code == "OWNED_CAMERA_TIMED_OUT"
    owned = runner.owned_result
    assert authority.calls == 1 and owned.status == "TIMED_OUT"
    assert owned.tree_exit_confirmed and not owned.cleanup_errors
    assert owned.parsed_result is None and not owned.stdout
    assert not list(inputs["working_directory"].iterdir())


@native
def test_actual_configured_capture_manual_and_auto_observations(tmp_path):
    controls = (
        CameraControlSetting("exposure", -7, "auto"),
        CameraControlSetting("gain", 21),
        CameraControlSetting("white_balance", 5000, "auto"),
        CameraControlSetting("brightness", -2),
        CameraControlSetting("contrast", 70),
        CameraControlSetting("saturation", 40),
    )
    client, plan, inputs = configured_fixture(tmp_path, controls)
    prepared = prepare_owned_camera_fixture(plan, **inputs)
    assert prepared.registration.request_schema == CONFIG_REQUEST_SCHEMA
    assert (
        len(prepared.plan.arguments) == 24
        and prepared.plan.request.controls == controls
    )
    runner, _, receipt = run_client(client, prepared)
    assert not isinstance(receipt, Exception), (receipt, runner.owned_result)
    assert receipt.status == "OK" and receipt.counts["control_set_attempts"] == 6
    observed = {row.control_id: row for row in receipt.controls}
    for setting in controls:
        actual = observed[setting.control_id]
        if setting.mode == "manual":
            assert actual.flags == 2 and actual.value == setting.value
        else:
            assert actual.flags == 1 and actual.value != setting.value
    assert receipt.frames[0].length_bytes == FRAME_BYTES and receipt.cleanup_confirmed
    assert runner.owned_result.tree_exit_confirmed


@native
@pytest.mark.parametrize("mode", ["manual", "auto"])
def test_actual_control_readback_drift_is_rejected_and_raw_packet_retained(
    tmp_path, mode
):
    client, plan, inputs = configured_fixture(
        tmp_path,
        (CameraControlSetting("exposure", -7, mode),),
        scenario="control-readback-drift",
    )
    prepared = prepare_owned_camera_fixture(plan, **inputs)
    runner, _, result = run_client(client, prepared)
    assert isinstance(result, CameraWorkerError)
    assert result.code == "INVALID_CAMERA_CONTRACT"
    assert (
        runner.owned_result.status == "SUCCEEDED"
        and runner.owned_result.tree_exit_confirmed
    )
    raw = runner.owned_result.parsed_result["fixture_result"]["native_receipt"]
    assert raw["counts"]["control_set_attempts"] == 1
    observed = next(row for row in raw["controls"] if row["control_id"] == "exposure")
    assert observed["value"] != -7 if mode == "manual" else observed["flags"] != 1


@native
def test_probe_cwd_pin_and_denied_admission_never_create_frames(tmp_path):
    client, plan, inputs = probe_fixture(tmp_path)
    prepared = prepare_owned_camera_fixture(plan, **inputs)
    called = []

    def deny(registration, request, digest):
        called.append(digest)
        with pytest.raises(OSError):
            inputs["working_directory"].rename(tmp_path / "retargeted")
        raise PermissionError("No fixture admission")

    runner = OwnedPreparedCameraRunner(
        prepared,
        cancellation=threading.Event(),
        deadline_ns=prepared.request.expires_at_ns,
        authorize_owned=deny,
    )
    with pytest.raises(CameraWorkerError):
        runner(plan.arguments, 10.0, 256 * 1024)
    assert len(called) == 1 and not runner.owned_result.process_created
    assert not list(inputs["working_directory"].iterdir())
