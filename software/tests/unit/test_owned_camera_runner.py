"""Real subprocesses here are only the closed stdlib incapable camera child."""

from dataclasses import asdict, replace
import hashlib
import json
import os
from pathlib import Path
import sys
import threading
import time

import pytest

import rocell.providers.windows.owned_camera_runner as module
import rocell.providers.windows.owned_worker_process as owned
from rocell.providers.windows._owned_camera_fixture import (
    MODE,
    PROVENANCE,
    canonical,
    digest,
    validate_envelope,
)
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    CameraEndpointBinding,
    CameraWorkerError,
    NativeCameraMode,
    WindowsCameraWorkerClient,
)
from rocell.providers.windows.owned_camera_runner import (
    CAMERA_FIXTURE_PATH,
    FRAME_BYTES,
    TEMPLATE_BYTES,
    OwnedPreparedCameraRunner,
    PreparedOwnedCameraFixture,
    prepare_owned_camera_fixture,
)
from rocell.providers.windows.owned_worker_process import (
    OwnedWindowsWorker,
    PinnedWorkerFile,
    WorkerProcessBudget,
    owned_request_wire,
)


def pin(path, maximum=64 * 1024 * 1024):
    return PinnedWorkerFile(
        path, hashlib.sha256(path.read_bytes()).hexdigest(), maximum
    )


def fixture(
    tmp_path,
    *,
    scenario="nominal",
    frames=1,
    duration=20_000,
    run_ms=25_000,
    create=True,
    luma=70,
):
    script = pin(CAMERA_FIXTURE_PATH)
    executable = pin(Path(sys._base_executable))
    output = tmp_path / "output"
    templates = []
    for index in range(frames):
        path = tmp_path / f"template-{index}.gray8"
        data = bytes([luma + index]) * TEMPLATE_BYTES
        if create:
            path.write_bytes(data)
        templates.append(
            PinnedWorkerFile(path, hashlib.sha256(data).hexdigest(), TEMPLATE_BYTES)
        )
    if create:
        output.mkdir()
    endpoint = "incapable-fixture-only"
    binding = CameraEndpointBinding(
        endpoint, hashlib.sha256(endpoint.encode()).hexdigest(), "c" * 64
    )
    client = WindowsCameraWorkerClient(CAMERA_FIXTURE_PATH, script.sha256)
    plan = client.prepare_capture(
        binding,
        NativeCameraMode(**MODE),
        output,
        source_sha256="a" * 64,
        campaign_id="attempt-fixture",
        budget=CameraCampaignBudget(
            duration, frames, FRAME_BYTES, FRAME_BYTES * frames
        ),
    )
    inputs = dict(
        session_id="session-fixture",
        operation_sha256="b" * 64,
        selected_identity_sha256="c" * 64,
        expires_at_ns=time.monotonic_ns() + 60_000_000_000,
        templates=tuple(templates),
        executable=executable,
        fixture_script=script,
        scenario=scenario,
        budget=WorkerProcessBudget(
            run_timeout_ms=run_ms, stdout_bytes=32 * 1024, stderr_bytes=8 * 1024
        ),
    )
    return client, plan, inputs


def prepared_fixture(tmp_path, **kwargs):
    client, plan, inputs = fixture(tmp_path, **kwargs)
    return client, prepare_owned_camera_fixture(plan, **inputs)


class ExactAuthority:
    def __init__(self, prepared, deadline, *, deny=False, cancellation=None):
        self.prepared, self.deadline, self.deny, self.cancellation = (
            prepared,
            deadline,
            deny,
            cancellation,
        )
        self.calls = 0

    def __call__(self, registration, request, digest):
        assert self.calls == 0
        assert asdict(registration) == asdict(self.prepared.registration)
        assert request == self.prepared.request
        assert digest == self.prepared.request_sha256(self.deadline)
        self.calls += 1
        if self.cancellation is not None:
            self.cancellation.set()
        if self.deny:
            raise PermissionError("explicit incapable fixture refusal")


def run_client(client, prepared, *, cancellation=None, deny=False):
    cancel = cancellation or threading.Event()
    deadline = prepared.request.expires_at_ns
    authority = ExactAuthority(prepared, deadline, deny=deny)
    runner = OwnedPreparedCameraRunner(
        prepared, cancellation=cancel, deadline_ns=deadline, authorize_owned=authority
    )
    client.runner = runner
    requested = []

    def authorize_camera(request):
        assert asdict(request) == asdict(prepared.plan.request)
        assert not requested
        requested.append(request)

    request = prepared.plan.request
    try:
        receipt = client.capture(
            request.binding,
            request.mode,
            Path(request.output_directory),
            source_sha256=request.source_sha256,
            campaign_id=request.campaign_id,
            budget=request.budget,
            authorize=authorize_camera,
        )
    except Exception as error:
        return runner, authority, error
    return runner, authority, receipt


def test_preparation_constructor_and_views_are_filesystem_inert(tmp_path, monkeypatch):
    client, plan, inputs = fixture(tmp_path, create=False)

    def forbidden(*args, **kwargs):
        pytest.fail("No filesystem/process action while preparing")

    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(Path, "lstat", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    monkeypatch.setattr(module, "OwnedWindowsWorker", forbidden)
    prepared = prepare_owned_camera_fixture(plan, **inputs)
    assert prepared.plan == plan
    assert prepared.registration.working_directory == Path(
        plan.request.output_directory
    )
    runner = OwnedPreparedCameraRunner(
        prepared,
        cancellation=threading.Event(),
        deadline_ns=inputs["expires_at_ns"],
        authorize_owned=forbidden,
    )
    assert runner.owned_result is None
    assert runner.expected_request_sha256 == prepared.request_sha256(
        inputs["expires_at_ns"]
    )


def test_prepared_snapshots_and_shared_admission_digest(tmp_path):
    _, prepared = prepared_fixture(tmp_path)
    deadline = prepared.request.expires_at_ns
    wire, digest = owned_request_wire(
        prepared.registration, prepared.request, deadline_ns=deadline
    )
    assert prepared.request_sha256(deadline) == digest
    assert prepared.request_sha256(deadline - 1) != digest
    payload = validate_envelope(json.loads(wire), "nominal")
    assert payload["camera_request"] == json.loads(
        canonical(asdict(prepared.plan.request))
    )
    external = prepared.plan
    object.__setattr__(external.request.binding, "binding_sha256", "e" * 64)
    object.__setattr__(prepared.registration.budget, "run_timeout_ms", 101)
    assert prepared.plan.request.binding.binding_sha256 == "c" * 64
    assert prepared.registration.budget.run_timeout_ms == 25_000


@pytest.mark.parametrize(
    "fault",
    [
        "scenario",
        "selected",
        "template-size",
        "duplicate",
        "mode",
        "argv",
        "script",
        "executable",
        "process-budget",
        "pipe-budget",
        "frames",
    ],
)
def test_preparation_rejects_changed_closed_contract(tmp_path, fault):
    _, plan, inputs = fixture(tmp_path)
    if fault == "scenario":
        inputs["scenario"] = "arbitrary"
    elif fault == "selected":
        inputs["selected_identity_sha256"] = "e" * 64
    elif fault == "template-size":
        inputs["templates"] = (replace(inputs["templates"][0], maximum_bytes=1),)
    elif fault == "duplicate":
        inputs["templates"] = inputs["templates"] * 2
    elif fault == "mode":
        plan = replace(
            plan, request=replace(plan.request, mode=NativeCameraMode(2, 2, 9, 1))
        )
    elif fault == "argv":
        plan = replace(plan, arguments=(*plan.arguments[:-1], str(tmp_path / "other")))
    elif fault == "script":
        inputs["fixture_script"] = replace(
            inputs["fixture_script"], path=tmp_path / "other.py"
        )
    elif fault == "executable":
        inputs["executable"] = replace(
            inputs["executable"], path=tmp_path / "other.exe"
        )
    elif fault == "process-budget":
        inputs["budget"] = replace(inputs["budget"], run_timeout_ms=19_999)
    elif fault == "pipe-budget":
        inputs["budget"] = replace(
            inputs["budget"], stdout_bytes=256 * 1024, stderr_bytes=64 * 1024
        )
    elif fault == "frames":
        inputs["templates"] = ()
    with pytest.raises((ValueError, CameraWorkerError)):
        prepare_owned_camera_fixture(plan, **inputs)


@pytest.mark.parametrize("fault", ["argv", "timeout", "output-limit"])
def test_adapter_drift_is_one_use_and_never_constructs_worker(
    tmp_path, monkeypatch, fault
):
    _, prepared = prepared_fixture(tmp_path)
    monkeypatch.setattr(
        module, "OwnedWindowsWorker", lambda *a, **kw: pytest.fail("No worker on drift")
    )
    runner = OwnedPreparedCameraRunner(
        prepared,
        cancellation=threading.Event(),
        deadline_ns=prepared.request.expires_at_ns,
        authorize_owned=lambda *a: pytest.fail("No authority on drift"),
    )
    args, timeout, limit = prepared.plan.arguments, 25.0, 256 * 1024
    if fault == "argv":
        args = (*args[:-1], str(tmp_path / "other"))
    elif fault == "timeout":
        timeout = 26.0
    else:
        limit -= 1
    with pytest.raises(ValueError):
        runner(args, timeout, limit)
    assert runner.owned_result is None
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        runner(prepared.plan.arguments, 25.0, 256 * 1024)


def test_physical_and_protocol_substitution_held_before_backend(tmp_path):
    _, prepared = prepared_fixture(tmp_path)
    for registration in (
        replace(prepared.registration, composition="PHYSICAL_UNQUALIFIED"),
        replace(
            prepared.registration,
            request_schema=owned.REQUEST_SCHEMA,
            result_schema=owned.RESULT_SCHEMA,
        ),
    ):
        worker = OwnedWindowsWorker(
            registration,
            authorizer=lambda *a: pytest.fail("No authority"),
            _backend_factory=lambda: pytest.fail("No backend"),
        )
        result = worker.run(
            prepared.request,
            cancellation=threading.Event(),
            deadline_ns=prepared.request.expires_at_ns,
        )
        assert result.status == "FAILED" and not result.process_created


def test_unknown_nested_fields_and_undersized_stdin_rejected(tmp_path):
    _, plan, inputs = fixture(tmp_path)
    object.__setattr__(plan.request, "extra", "not admitted")
    with pytest.raises(ValueError, match="EXACT_PREPARED"):
        prepare_owned_camera_fixture(plan, **inputs)
    _, fresh, _ = fixture(tmp_path / "unused", create=False)
    inputs["budget"] = replace(inputs["budget"], stdin_bytes=512)
    with pytest.raises(ValueError, match="STDIN_LIMIT"):
        prepare_owned_camera_fixture(fresh, **inputs)


@pytest.mark.parametrize("fault", ["hash", "source", "scenario", "unknown"])
def test_child_pure_envelope_rejects_tampering(tmp_path, fault):
    _, prepared = prepared_fixture(tmp_path)
    wire, _ = owned_request_wire(
        prepared.registration,
        prepared.request,
        deadline_ns=prepared.request.expires_at_ns,
    )
    request = json.loads(wire)
    if fault == "hash":
        request["request_sha256"] = "f" * 64
    elif fault == "source":
        request["source_sha256"] = "f" * 64
        request["request_sha256"] = digest(
            {k: v for k, v in request.items() if k != "request_sha256"}
        )
    elif fault == "scenario":
        request["payload"]["scenario"] = "other"
    else:
        request["extra"] = True
    with pytest.raises(ValueError):
        validate_envelope(request, "nominal")


def test_prepared_serialized_unknown_registration_field_rejected(tmp_path):
    _, prepared = prepared_fixture(tmp_path)
    value = json.loads(prepared._canonical_json)
    value["registration"]["execute_anything"] = True
    with pytest.raises(ValueError, match="REGISTRATION_FIELDS"):
        PreparedOwnedCameraFixture(canonical(value))


native = pytest.mark.skipif(
    os.name != "nt", reason="Owned Windows fixture processes only"
)


@native
@pytest.mark.parametrize("frames", [1, 4])
def test_real_full_size_capture_unchanged_client_and_lossless_process_result(
    tmp_path, frames
):
    client, prepared = prepared_fixture(tmp_path, frames=frames)
    runner, authority, receipt = run_client(client, prepared)
    assert not isinstance(receipt, Exception), (receipt, runner.owned_result)
    result = runner.owned_result
    assert (
        result.status == "SUCCEEDED"
        and result.tree_exit_confirmed
        and not result.cleanup_errors
    )
    assert result.initial_thread_resumed and authority.calls == 1
    assert result.request_sha256 == runner.expected_request_sha256
    assert receipt.status == "OK" and receipt.cleanup_confirmed
    assert receipt.frames[0].length_bytes == FRAME_BYTES
    assert len(receipt.frames) == frames
    assert PROVENANCE in receipt.limitations
    file = Path(prepared.plan.request.output_directory) / receipt.frames[0].filename
    with file.open("rb") as stream:
        assert stream.read(16) == bytes([70, 128, 70, 128]) * 4
    assert file.stat().st_size == FRAME_BYTES
    assert receipt.frames[0].sha256 == hashlib.sha256(file.read_bytes()).hexdigest()
    assert json.loads(result.stdout) == result.parsed_result
    result.parsed_result["fixture_result"]["scenario"] = "changed"
    assert runner.owned_result.parsed_result["fixture_result"]["scenario"] == "nominal"
    assert runner.owned_result.to_dict()["physical_authority"] is False
    assert runner.owned_result.to_dict()["device_cleanup_confirmed"] is False


@native
@pytest.mark.parametrize("fault", ["cleanup", "tree-exit"])
def test_valid_native_packet_never_hides_owned_cleanup_failure(
    tmp_path, monkeypatch, fault
):
    client, prepared = prepared_fixture(tmp_path)
    original_runner, _, receipt = run_client(client, prepared)
    assert not isinstance(receipt, Exception)
    original = original_runner.owned_result
    changed = replace(
        original, status="FAILED", cleanup_errors=("FIXTURE_CLEANUP_UNCONFIRMED",)
    )
    if fault == "tree-exit":
        changed = replace(original, status="FAILED", tree_exit_confirmed=False)

    class ReturnedOwnedFixture:
        def __init__(self, registration, **kwargs):
            assert registration == prepared.registration

        def run(self, request, **kwargs):
            assert request == prepared.request
            return changed

    monkeypatch.setattr(module, "OwnedWindowsWorker", ReturnedOwnedFixture)
    runner = OwnedPreparedCameraRunner(
        prepared,
        cancellation=threading.Event(),
        deadline_ns=prepared.request.expires_at_ns,
        authorize_owned=ExactAuthority(prepared, prepared.request.expires_at_ns),
    )
    with pytest.raises(CameraWorkerError) as error:
        runner(prepared.plan.arguments, 25.0, 256 * 1024)
    assert error.value.code == "OWNED_CAMERA_PROCESS_CLEANUP_UNCONFIRMED"
    assert runner.owned_result.stdout == original.stdout
    assert (
        runner.owned_result.parsed_result["fixture_result"]["native_receipt"]["status"]
        == "OK"
    )


@native
@pytest.mark.parametrize(
    "scenario", ["identity-mismatch", "cleanup-uncertain", "malformed-result"]
)
def test_real_faults_keep_full_owned_result(tmp_path, scenario):
    client, prepared = prepared_fixture(tmp_path, scenario=scenario)
    runner, authority, receipt = run_client(client, prepared)
    result = runner.owned_result
    assert (
        authority.calls == 1
        and result.tree_exit_confirmed
        and not result.cleanup_errors
    )
    assert result.stdout
    if scenario == "cleanup-uncertain":
        assert not isinstance(receipt, Exception), receipt
        assert receipt.status == "FAILED" and not receipt.cleanup_confirmed
        assert (
            result.primary_error == "WORKER_EXIT_FAILED"
            and result.parsed_result is not None
        )
    else:
        assert isinstance(receipt, CameraWorkerError)
        if scenario == "identity-mismatch":
            assert result.parsed_result is not None
        else:
            assert result.parsed_result is None
            assert result.stdout == b'{"duplicate":1,"duplicate":2}'


@native
def test_real_child_timeout_kills_only_owned_tree_and_retains_diagnostic(tmp_path):
    client, prepared = prepared_fixture(
        tmp_path, scenario="child-timeout", duration=1000, run_ms=1500
    )
    runner, authority, receipt = run_client(client, prepared)
    assert isinstance(receipt, CameraWorkerError)
    result = runner.owned_result
    assert result.status == "TIMED_OUT" and result.tree_exit_confirmed
    assert not result.cleanup_errors and authority.calls == 1
    assert not list(Path(prepared.plan.request.output_directory).iterdir())


@native
def test_real_cancellation_from_after_pins_authority_prevents_creation(tmp_path):
    _, prepared = prepared_fixture(tmp_path)
    cancel = threading.Event()
    authority = ExactAuthority(
        prepared, prepared.request.expires_at_ns, cancellation=cancel
    )
    runner = OwnedPreparedCameraRunner(
        prepared,
        cancellation=cancel,
        deadline_ns=prepared.request.expires_at_ns,
        authorize_owned=authority,
    )
    with pytest.raises(CameraWorkerError) as error:
        runner(prepared.plan.arguments, 25.0, 256 * 1024)
    assert error.value.code == "OWNED_CAMERA_CANCELLED"
    assert runner.owned_result.status == "CANCELLED" and authority.calls == 1
    assert (
        not runner.owned_result.process_created
        and not runner.owned_result.cleanup_errors
    )


@native
def test_real_output_ancestry_is_pinned_during_admission(tmp_path):
    _, prepared = prepared_fixture(tmp_path)
    authority = ExactAuthority(prepared, prepared.request.expires_at_ns)

    def check_pin(registration, request, digest):
        authority(registration, request, digest)
        with pytest.raises(OSError):
            registration.working_directory.rename(tmp_path / "retargeted")

    runner = OwnedPreparedCameraRunner(
        prepared,
        cancellation=threading.Event(),
        deadline_ns=prepared.request.expires_at_ns,
        authorize_owned=check_pin,
    )
    result = runner(prepared.plan.arguments, 25.0, 256 * 1024)
    assert result.returncode == 0 and runner.owned_result.status == "SUCCEEDED"


@native
def test_real_pipe_quota_retains_bounded_prefix_not_silent_success(tmp_path):
    _, plan, inputs = fixture(tmp_path)
    inputs["budget"] = replace(inputs["budget"], stdout_bytes=128)
    prepared = prepare_owned_camera_fixture(plan, **inputs)
    authority = ExactAuthority(prepared, prepared.request.expires_at_ns)
    runner = OwnedPreparedCameraRunner(
        prepared,
        cancellation=threading.Event(),
        deadline_ns=prepared.request.expires_at_ns,
        authorize_owned=authority,
    )
    with pytest.raises(CameraWorkerError):
        runner(prepared.plan.arguments, 25.0, 256 * 1024)
    result = runner.owned_result
    assert result.status == "FAILED" and len(result.stdout) <= 128
    assert result.parsed_result is None and result.primary_error
    assert result.tree_exit_confirmed and not result.cleanup_errors


@native
@pytest.mark.parametrize(
    "fault", ["deny", "precancel", "template-drift", "nonempty-output", "invalid-luma"]
)
def test_real_boundary_refusals(tmp_path, fault):
    client, prepared = prepared_fixture(
        tmp_path, luma=0 if fault == "invalid-luma" else 70
    )
    cancel = threading.Event()
    if fault == "precancel":
        cancel.set()
    elif fault == "template-drift":
        prepared.registration.package_files[1].path.write_bytes(b"bad")
    elif fault == "nonempty-output":
        (prepared.registration.working_directory / "keep.txt").write_text("keep")
    runner, authority, receipt = run_client(
        client, prepared, cancellation=cancel, deny=fault == "deny"
    )
    assert isinstance(receipt, Exception)
    if fault == "nonempty-output":
        assert runner.owned_result is None and authority.calls == 0
        assert (
            prepared.registration.working_directory / "keep.txt"
        ).read_text() == "keep"
    else:
        result = runner.owned_result
        assert result.status != "SUCCEEDED"
        if fault == "invalid-luma":
            assert authority.calls == 1 and result.initial_thread_resumed
            assert result.stderr == b"INCAPABLE_CAMERA_CHILD_FAILED\r\n"
        else:
            assert not result.initial_thread_resumed
            assert authority.calls == (1 if fault == "deny" else 0)
        assert not list(prepared.registration.working_directory.iterdir())
