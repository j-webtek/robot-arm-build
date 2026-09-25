"""Real Win32 directory/file handles only. Fake helper bytes are never executed."""

from dataclasses import replace
import hashlib
import os
from pathlib import Path
import threading
import time

import pytest

from rocell.providers.windows._owned_worker_win32 import (
    WindowsOwnedProcess,
    WindowsOwnedCameraActivationPipeProcess,
)
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.providers.windows.native_camera_activation_registration import (
    create_activation_runtime,
    helper_relative_path,
    build_record_relative_path,
    prepare_owned_activation,
)
from rocell.providers.windows import native_camera_activation_supervisor as supervisor
from rocell.providers.windows import owned_worker_process as shared
from test_native_camera_activation_registration import inputs

pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="real Win32 file/directory pinning"
)
ATTEMPT = "attempt-" + "2" * 32


@pytest.fixture(autouse=True)
def no_process_or_camera(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("Directory-only test attempted process/device access")

    monkeypatch.setattr(WindowsOwnedProcess, "start", denied)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, denied)
    assert shared._UNRESOLVED_BACKEND is None
    yield
    assert shared._UNRESOLVED_BACKEND is None


def prepared_at(tmp_path, purpose="probe"):
    workspace = tmp_path / "w"
    assigned = tmp_path / "o"
    assigned.mkdir()
    helper = workspace / helper_relative_path(purpose)
    helper.parent.mkdir(parents=True)
    raw = b"INCAPABLE FILE PIN TEST, NOT AN EXECUTABLE\n"
    helper.write_bytes(raw)
    record = workspace / build_record_relative_path(purpose)
    record.write_bytes(b'{"provenance":"DIRECTORY_TEST_ONLY"}')
    runtime = create_activation_runtime(
        workspace,
        purpose=purpose,
        source_sha256="a" * 64,
        catalog_sha256="b" * 64,
        helper_sha256=hashlib.sha256(raw).hexdigest(),
        build_record_sha256=hashlib.sha256(record.read_bytes()).hexdigest(),
    )
    _, old, expectation, args = inputs(workspace, purpose)
    client = WindowsCameraWorkerClient(helper, runtime.to_dict()["helper"]["sha256"])
    working = assigned / ("native-camera-" + ATTEMPT)
    common = dict(
        source_sha256="a" * 64, campaign_id=ATTEMPT, budget=old.request.budget
    )
    plan = (
        client.prepare_probe(old.request.binding, **common)
        if purpose == "probe"
        else client.prepare_capture(
            old.request.binding,
            old.request.mode,
            working / ("capture-" + ATTEMPT),
            **common,
        )
    )
    args.update(session_id="physical-camera-" + "3" * 32, working_directory=working)
    return prepare_owned_activation(runtime, plan, expectation, **args)


def cleanup(owner):
    result = owner.cleanup(time.monotonic_ns() + 1_000_000_000)
    assert not owner.created and not owner.resumed
    assert not owner.handles and not owner.unclosed_handles and not owner.pins
    return result


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_pin_create(tmp_path, purpose):
    prepared = prepared_at(tmp_path, purpose)
    working = prepared.registration.working_directory
    owner = WindowsOwnedCameraActivationPipeProcess()
    assert not working.exists()
    try:
        owner.pin(prepared.registration)
        assert working.is_dir() and len(owner.pins) == 2
        with pytest.raises(OSError):
            working.rename(working.parent / "denied")
        if purpose == "capture":
            output = prepared.admission_request.configuration.output_directory
            assert output.is_dir()
            with pytest.raises(OSError):
                output.rename(working / "denied")
            # Directory pinning must still permit the child's exclusive creation.
            with (output / "modeled.bin").open("xb") as stream:
                stream.write(b"MODELED, NOT CAMERA PIXELS")
        assert not owner.created and not owner.resumed
    finally:
        assert cleanup(owner) == ()
    assert working.is_dir()  # No success/failure cleanup deletes original files.
    if purpose == "capture":
        assert (output / "modeled.bin").read_bytes() == b"MODELED, NOT CAMERA PIXELS"


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_occupied(tmp_path, purpose):
    prepared = prepared_at(tmp_path, purpose)
    working = prepared.registration.working_directory
    working.mkdir()
    (working / "original.txt").write_bytes(b"KEEP")
    owner = WindowsOwnedCameraActivationPipeProcess()
    try:
        with pytest.raises(FileExistsError):
            owner.pin(prepared.registration)
    finally:
        assert cleanup(owner) == ()
    assert (working / "original.txt").read_bytes() == b"KEEP"


def test_one_use(tmp_path):
    prepared = prepared_at(tmp_path)
    owner = WindowsOwnedCameraActivationPipeProcess()
    try:
        owner.pin(prepared.registration)
        with pytest.raises(ValueError, match="ALREADY_ATTEMPTED"):
            owner.pin(prepared.registration)
    finally:
        assert cleanup(owner) == ()


def test_legacy_no_create(tmp_path):
    prepared = prepared_at(tmp_path)
    owner = WindowsOwnedProcess()
    try:
        with pytest.raises(FileNotFoundError):
            owner.pin(prepared.registration)
    finally:
        assert cleanup(owner) == ()
    assert not prepared.registration.working_directory.exists()


@pytest.mark.parametrize(
    "field,value",
    [
        ("worker_id", "unreviewed-other-worker"),
        ("composition", "INCAPABLE_PROCESS_FIXTURE"),
        ("request_schema", "other-schema"),
        ("result_schema", "other-schema"),
        ("argv", ("--owned-probe-v2", "--request-sha256", "not-a-hash")),
    ],
)
def test_exact_policy(tmp_path, field, value):
    prepared = prepared_at(tmp_path)
    registration = replace(prepared.registration, **{field: value})
    owner = WindowsOwnedCameraActivationPipeProcess()
    try:
        with pytest.raises(ValueError, match="DIRECTORY_POLICY"):
            owner.pin(registration)
        assert not owner.handles and not registration.working_directory.exists()
    finally:
        assert cleanup(owner) == ()


def test_partial_create(tmp_path, monkeypatch):
    prepared = prepared_at(tmp_path, "capture")
    output = prepared.admission_request.configuration.output_directory
    original = Path.mkdir

    def fail(path, *args, **kwargs):
        if path == output:
            raise OSError("MODELED_CAPTURE_DIRECTORY_CREATE_FAILURE")
        return original(path, *args, **kwargs)

    monkeypatch.setattr(Path, "mkdir", fail)
    owner = WindowsOwnedCameraActivationPipeProcess()
    try:
        with pytest.raises(OSError, match="MODELED_CAPTURE"):
            owner.pin(prepared.registration)
    finally:
        assert cleanup(owner) == ()
    assert prepared.registration.working_directory.is_dir() and not output.exists()


def test_directory_budget(tmp_path):
    prepared = prepared_at(tmp_path)
    deep = tmp_path.joinpath(*(["x"] * 129), "native-camera-" + ATTEMPT)
    registration = replace(prepared.registration, working_directory=deep)
    owner = WindowsOwnedCameraActivationPipeProcess()
    try:
        with pytest.raises(ValueError, match="HANDLE_BUDGET"):
            owner.pin(registration)
        assert not owner.handles
    finally:
        assert cleanup(owner) == ()


def test_close_failure_tracked(tmp_path, monkeypatch):
    prepared = prepared_at(tmp_path, "capture")
    owner = WindowsOwnedCameraActivationPipeProcess()
    owner.pin(prepared.registration)
    directory_handle = next(reversed(owner.handles))
    actual_close = owner.k.CloseHandle

    def modeled_failure(handle):
        # Do NOT call the kernel for this one handle. The explicit teardown below
        # performs its first real close, not a retry of an ambiguous kernel close.
        return False if handle == directory_handle else actual_close(handle)

    monkeypatch.setattr(owner.k, "CloseHandle", modeled_failure)
    try:
        errors = owner.cleanup(time.monotonic_ns() + 1_000_000_000)
        assert "CLOSE_FAILED:pinned-directory" in errors
        assert directory_handle in owner.unclosed_handles
        assert not owner.handles and not owner.pins and not owner.created
    finally:
        assert actual_close(directory_handle)


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_supervised_refusal(tmp_path, monkeypatch, purpose):
    prepared = prepared_at(tmp_path, purpose)
    owner = WindowsOwnedCameraActivationPipeProcess()
    monkeypatch.setattr(supervisor, "_new_owner", lambda: owner)

    def revoked(exact):
        assert exact.payload == prepared.payload and owner.handles
        raise PermissionError("MODELED_ORIGINAL_SCOPE_REVOKED_AFTER_PINS")

    observed = supervisor._supervise(
        prepared,
        prepared.registration,
        revalidate_consumed_permit=revoked,
        cancellation=threading.Event(),
        deadline_ns=time.monotonic_ns() + 25_000_000_000,
    )
    record = observed.run_evidence(prepared)
    assert record.assessment().native is None
    assert observed.before_cleanup.values()["handles_remaining"] > 0
    assert observed.after_cleanup.values()["handles_remaining"] == 0
    assert (
        not owner.created
        and not owner.resumed
        and not observed.unresolved_owner_retained
    )
    assert not owner.handles and not owner.pins
    assert prepared.registration.working_directory.is_dir()


@pytest.mark.parametrize("purpose", ["probe", "capture"])
def test_m1_scoped_refusal(tmp_path, monkeypatch, purpose):
    """Actual M1 + campaign + pinning + supervision; modeled guard always denies.

    Fake helper bytes are pinned only. The class-wide start guard above would
    fail this test before any process creation if the after-pin refusal regressed.
    """
    from rocell.application import (
        physical_camera_activation_campaign as campaign_module,
    )
    from rocell.application.physical_camera_activation_campaign import (
        PhysicalCameraActivationCampaign,
    )
    from rocell.application.cell_commissioning_coordinator import (
        PhysicalCameraAcquisitionCoordinator,
        RegisteredActionRequest,
    )
    from rocell.application.commissioning_camera_persistence import (
        M1PhysicalCameraPersistence,
        PhysicalCameraAdmissionFacts,
    )
    from rocell.application.physical_onboarding_attempts import AttemptState
    from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
    from rocell.application.commissioning_camera_persistence import (
        physical_camera_source_binding,
    )
    from test_commissioning_camera_persistence import runtime_and_adapter
    import test_commissioning_camera_persistence as fixture_module
    from test_physical_camera_coordinator import CELL, SESSION, SOURCE, LEASES
    from test_native_camera_activation_expectation import enrollment
    from test_wizard_native_camera_enrollment import SESSION as LAUNCH

    seed = prepared_at(tmp_path, purpose)
    worker = PhysicalCameraActivationCampaign.from_enrollment(
        Path(seed.runtime.to_dict()["workspace"]),
        seed.registration.working_directory.parent,
        enrollment=enrollment(),
        launch_session_id=LAUNCH,
        source_sha256=SOURCE,
        cell_id=CELL,
        session_id=SESSION,
        runtime=seed.runtime,
        mode=seed.camera_plan.request.mode,
        budget=seed.camera_plan.request.budget,
    )
    monkeypatch.setattr(fixture_module, "STAGE", worker.registration().stage)
    runtime, _ = runtime_and_adapter(tmp_path)

    def modeled_facts(request, snapshot):
        return PhysicalCameraAdmissionFacts(
            {"provenance": "MODELED_DIRECTORY_ONLY_CONTEXT_NOT_RUNTIME_APPROVAL"},
            tuple({"modeled_epoch": i} for i in range(8)),
            worker.plan()["selection"],
        )

    adapter = M1PhysicalCameraPersistence(
        runtime, workspace_source_sha256=SOURCE, admission_facts=modeled_facts
    )
    item = worker.registration()
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=adapter,
        registrations=(item,),
        workers={item.worker_id: worker},
        retained_campaign_actions=(item.action_id,),
        scoped_campaign_actions=(item.action_id,),
    )
    request = RegisteredActionRequest(
        CELL, SESSION, item.action_id, "directory-only-refusal", "1" * 64
    )
    with adapter.transaction(LEASES) as tx:
        request = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )
    permit = core.prepare(request)
    prepared = worker.preparation_for_permit(permit)

    def guard():
        if prepared.registration.working_directory.exists():
            raise PermissionError("MODELED_REFUSAL_AFTER_REAL_DIRECTORY_PINS")

    worker._bind_application_guard(guard)
    monkeypatch.setattr(campaign_module, "source_fingerprint", lambda workspace: SOURCE)
    # This directory/refusal test models software review; its helper bytes are
    # deliberately not executable and must not enter the installed catalog.
    monkeypatch.setattr(
        campaign_module, "verify_reviewed_activation_runtime", lambda *a, **k: {}
    )
    owner = WindowsOwnedCameraActivationPipeProcess()
    monkeypatch.setattr(supervisor, "_new_owner", lambda: owner)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.receipt is None
    assert prepared.registration.working_directory.is_dir()
    assert (
        not owner.created and not owner.resumed and not owner.handles and not owner.pins
    )
    assert worker.evidence is not None and worker.status()["post_context_failed"]
    with adapter.transaction(LEASES) as tx:
        assert tx.read_camera_activation_evidence(permit.attempt_id) == worker.evidence
        assert tx.read_campaign_result(permit.attempt_id) == result
    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        cell_id=CELL,
    )
    fresh = M1PhysicalCameraPersistence(
        reopened, workspace_source_sha256=SOURCE, admission_facts=modeled_facts
    )
    with fresh.transaction(LEASES) as tx:
        assert tx.read_camera_activation_evidence(permit.attempt_id) == worker.evidence
        assert tx.read_campaign_result(permit.attempt_id) == result
    assert reopened.verify(SESSION).quarantined
