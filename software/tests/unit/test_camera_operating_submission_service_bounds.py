"""Fast orchestration bounds with explicit modeled read/store seams, no I/O."""

from contextlib import contextmanager
from copy import deepcopy
from threading import Event

import pytest

from rocell.application import camera_operating_submission_service as service
from rocell.application.physical_camera_acquisition_service import (
    PhysicalCameraAcquisitionService,
)
from rocell.application.physical_camera_session import PhysicalCameraSession
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_native_camera_enrollment import (
    WizardNativeCameraEnrollment,
)
from test_physical_camera_session import (
    session_fixture,
    SOURCE,
    LAUNCH,
    no_device_or_process,
)


@pytest.fixture
def composition(tmp_path, monkeypatch):
    session = session_fixture(tmp_path)
    camera = PhysicalCameraAcquisitionService(
        tmp_path, launch_id=LAUNCH, source_sha256=SOURCE, mode="physical"
    )
    enrollment = WizardNativeCameraEnrollment("physical", LAUNCH, SOURCE)
    now, calls = [100], []
    monkeypatch.setattr(service, "monotonic_ns", lambda: now[0])
    monkeypatch.setattr(service, "source_fingerprint", lambda _: SOURCE)
    session._cached["verification"] = dict(
        effects_allowed_by_m1_storage=True, challenge_sha256="b" * 64
    )
    workflow = dict(
        schema="MODELED closing original workflow",
        physical_authority=False,
        connected=False,
    )
    event = Event()
    arguments = dict(
        context={},
        expected_workflow_payload=b"MODELED original workflow",
        proposal_payload=b"MODELED proposal",
        expected_proposal_sha256="d" * 64,
        capture_request_keys=("one", "two"),
        request_key="bounded-submission",
        operator_id="MODELED operator",
        cancellation=event,
        deadline_ns=1000,
        validate_current_context=lambda: None,
        progress=lambda _: None,
        attempt={},
    )
    hooks = {}

    def visit(phase):
        calls.append(phase)
        if phase in hooks:
            hooks[phase]()

    def assess(*owners, **kwargs):
        assert owners == (camera, session, enrollment)
        assert kwargs["deadline_ns"] == arguments["deadline_ns"]
        assert kwargs["capture_request_keys"] == ("one", "two")
        kwargs["validate_current_context"]()
        visit("assessment")
        return dict(header_sha256="e" * 64)

    @contextmanager
    def stage(owner, **kwargs):
        assert owner is session
        visit("scope_open")
        yield "MODELED transaction"
        visit("scope_close")

    def retain(tx, **kwargs):
        assert tx == "MODELED transaction"
        kwargs["check"]()
        kwargs["attempt"]["commit"] = "COMMITTED_ORIGINAL_READ_BACK"
        visit("stage")
        kwargs["check"]()
        return deepcopy(workflow)

    def refresh(owner, **kwargs):
        assert owner is session
        assert kwargs["deadline_ns"] == arguments["deadline_ns"]
        visit("refresh")

    def reopen(owner, **kwargs):
        assert owner is session
        assert kwargs["deadline_ns"] == arguments["deadline_ns"]
        visit("reopen")
        return deepcopy(workflow)

    monkeypatch.setattr(service, "run_original_operating_assessment", assess)
    monkeypatch.setattr(service, "_retain_in_stage_transaction", retain)
    monkeypatch.setattr(PhysicalCameraSession, "stage_transaction", stage)
    monkeypatch.setattr(PhysicalCameraSession, "refresh", refresh)
    monkeypatch.setattr(PhysicalCameraSession, "read_original_source_workflow", reopen)
    return camera, session, enrollment, arguments, now, calls, hooks, workflow


def invoke(c):
    return service.run_original_operating_submission(*c[:3], **c[3])


def test_same_deadline_and_exact_reopened_workflow_with_no_approval(composition):
    c = composition
    value = invoke(c)
    assert value == c[-1] and value is not c[-1]
    assert c[5] == [
        "assessment",
        "scope_open",
        "stage",
        "scope_close",
        "refresh",
        "reopen",
    ]
    assert c[3]["attempt"]["commit"] == "COMMITTED_AND_REOPENED_ORIGINAL"
    assert not value["connected"] and not value["physical_authority"]
    assert c[0]._dispatch_lock.acquire(False)
    c[0]._dispatch_lock.release()


@pytest.mark.parametrize(
    "phase", ["assessment", "stage", "scope_close", "refresh", "reopen"]
)
@pytest.mark.parametrize("fault", ["stop", "deadline", "context"])
def test_changed_context_after_any_phase_cannot_publish(composition, phase, fault):
    c = composition

    def changed():
        if fault == "stop":
            c[3]["cancellation"].set()
        elif fault == "deadline":
            c[4][0] = c[3]["deadline_ns"]
        else:
            c[3]["validate_current_context"] = lambda: False
            # The service has already pinned the callback, so mutate that
            # callback's observed state rather than pretending to replace it.
            context_current[0] = False

    context_current = [True]
    c[3]["validate_current_context"] = lambda: None if context_current[0] else False
    c[6][phase] = changed
    with pytest.raises(WizardError) as error:
        invoke(c)
    assert error.value.code == "OPERATING_SUBMISSION_" + (
        "CONTEXT_CHANGED" if fault == "context" else "INTERRUPTED"
    )
    assert c[5][-1] == phase
    assert c[3]["attempt"].get("commit") != "COMMITTED_AND_REOPENED_ORIGINAL"
    assert c[0]._dispatch_lock.acquire(False)
    c[0]._dispatch_lock.release()


@pytest.mark.parametrize(
    "key,value",
    [
        ("deadline_ns", True),
        ("deadline_ns", 100),
        ("deadline_ns", 301_000_000_100),
        ("capture_request_keys", ()),
        ("capture_request_keys", ("one", "one")),
        ("capture_request_keys", ({}, "two")),
        ("capture_request_keys", ["one", "two"]),
        ("operator_id", ""),
        ("expected_workflow_payload", {}),
        ("attempt", {"already": True}),
    ],
)
def test_invalid_input_does_not_start_original_read(composition, key, value):
    composition[3][key] = value
    with pytest.raises(WizardError) as error:
        invoke(composition)
    assert error.value.code == "OPERATING_SUBMISSION_INPUT"
    assert not composition[5]


def test_busy_dispatcher_is_not_released_or_retried(composition):
    c = composition
    assert c[0]._dispatch_lock.acquire(False)
    try:
        with pytest.raises(WizardError) as error:
            invoke(c)
        assert error.value.code == "OPERATING_SUBMISSION_CAMERA_OPERATION_ACTIVE"
        assert c[0]._dispatch_lock.locked()
        assert c[5] == ["assessment"]
        assert not c[3]["attempt"]
    finally:
        c[0]._dispatch_lock.release()


def test_reopen_substitution_is_not_published(composition, monkeypatch):
    c = composition

    def changed(owner, **kwargs):
        c[5].append("changed_reopen")
        return {**c[-1], "unrelated": True}

    monkeypatch.setattr(PhysicalCameraSession, "read_original_source_workflow", changed)
    with pytest.raises(WizardError) as error:
        invoke(c)
    assert error.value.code == "OPERATING_SUBMISSION_REOPEN_CHANGED"
    assert c[3]["attempt"]["commit"] == "COMMITTED_ORIGINAL_READ_BACK"
    assert c[0]._dispatch_lock.acquire(False)
    c[0]._dispatch_lock.release()
