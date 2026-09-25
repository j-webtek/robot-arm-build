"""Arrival's cached publication boundary, without a camera, child or M1 store.

Real pure report producers feed the real service cache. Operation records and
private store/evidence sentinels are injected: these tests prove publication and
nonmutation, not acquisition, durable stage acceptance or storage qualification.
"""

from copy import deepcopy
from pathlib import Path
import threading

import pytest

from rocell.application import arrival_wizard_service as arrival
from rocell.application.camera_configuration import compare_camera_readback
from rocell.application.wizard_actions import ACTION_BY_ID, WizardError
from test_arrival_wizard_service import make_service  # noqa: F401
from test_camera_configuration import configuration_inputs


INVALIDATING_ACTIONS = (
    "rehearsal_camera_probe",
    "rehearsal_camera_configuration",
    "rehearsal_camera_campaign",
    "rehearsal_owned_camera_campaign",
    "rehearsal_collect",
    "rehearsal_arm_feedback_campaign",
    "rehearsal_reopen",
)


def seed(service):
    """Install substantive pure reports and opaque, never-operated store evidence."""
    _, probe, _, candidate, native = configuration_inputs()
    readback = compare_camera_readback(
        candidate, native, expected_settings_epoch=candidate.settings_epoch
    )
    state = service._commissioning
    state._camera_probe = probe
    state._electronic_configuration = candidate
    state._camera_readback = readback
    state._cached["camera_configuration"] = state._configuration_projection()
    # Sentinels cannot perform a transaction, replay, repair or write.
    state._store = object()
    state._receipt = {"fixture_only_private_bytes": b"unchanged original receipt"}
    return {
        "store": state._store,
        "receipt": state._receipt,
        "receipt_value": deepcopy(state._receipt),
        "probe": probe,
        "probe_value": probe.view(),
        "candidate": candidate,
        "candidate_value": candidate.view(),
        "readback": readback,
        "readback_value": deepcopy(readback),
        "projection": deepcopy(state._cached["camera_configuration"]),
    }


def assert_private_evidence_unchanged(service, original):
    state = service._commissioning
    assert state._store is original["store"]
    assert state._receipt is original["receipt"]
    assert state._receipt == original["receipt_value"]
    assert state._camera_probe is original["probe"]
    assert state._camera_probe.view() == original["probe_value"]
    assert state._electronic_configuration is original["candidate"]
    assert state._electronic_configuration.view() == original["candidate_value"]
    # Current readback may be retired, but not mutate a retained original object.
    assert original["readback"] == original["readback_value"]


def pending(service, action_id, status="RUNNING"):
    operation_id = "injected-publication-operation"
    service._operations[operation_id] = {
        "operation_id": operation_id,
        "action_id": action_id,
        "label": ACTION_BY_ID[action_id].label,
        "status": status,
        "created_at": "INJECTED_TEST_RECORD_NOT_DURABLE_EVIDENCE",
        "message": "Publication-boundary fixture only",
        "progress_count": 0,
        "physical_authority": False,
        "mode": "rehearsal",
        "result": None,
        "result_retention": "NOT_FINISHED",
        "error": None,
    }
    service._running = operation_id
    service._cancel = threading.Event()
    return operation_id


def configuration(service):
    return service.view()["commissioning_rehearsal"]["camera_configuration"]


@pytest.mark.parametrize("action_id", INVALIDATING_ACTIONS)
@pytest.mark.parametrize("status", ["QUEUED", "RUNNING"])
def test_in_flight_actions_withhold_even_complete_inner_readback_without_mutation(
    make_service, action_id, status
):
    service, runner, _ = make_service()
    original = seed(service)
    assert configuration(service)["status"] == "READBACK_COMPLETE"
    pending(service, action_id, status)
    assert configuration(service) is None
    assert configuration(service) is None
    assert (
        service._commissioning.view()["camera_configuration"] == original["projection"]
    )
    assert not service._commissioning._configuration_hidden
    assert_private_evidence_unchanged(service, original)
    assert not runner.calls and service._events == []


@pytest.mark.parametrize("action_id", INVALIDATING_ACTIONS)
def test_successful_completion_publishes_only_after_real_diagnostic_log_commit(
    make_service, monkeypatch, action_id
):
    service, runner, _ = make_service()
    original = seed(service)
    operation_id = pending(service, action_id)
    appended = []
    append = service._log.append

    def persist(kind, details):
        record = append(kind, details)
        appended.append((kind, details["status"]))
        return record

    monkeypatch.setattr(service._log, "append", persist)
    assert configuration(service) is None
    with service._lock:
        service._finish(
            operation_id,
            "SUCCEEDED",
            {"message": "Injected completed outcome", "physical_authority": False},
        )
    assert appended == [("ACTION_FINISHED", "SUCCEEDED")]
    assert service.operation(operation_id)["completion_log_persisted"] is True
    assert configuration(service) == original["projection"]
    assert_private_evidence_unchanged(service, original)
    assert not runner.calls


def test_concurrent_status_cannot_cross_the_uncommitted_completion_log_boundary(
    make_service, monkeypatch
):
    service, _, _ = make_service()
    original = seed(service)
    operation_id = pending(service, "rehearsal_camera_configuration")
    entered, release, read_started, read_done = [threading.Event() for _ in range(4)]
    observations, errors = [], []
    append = service._log.append

    def delayed_log(kind, details):
        entered.set()
        if not release.wait(3):
            raise TimeoutError("Test completion-log barrier did not release")
        return append(kind, details)

    def complete():
        try:
            with service._lock:
                service._finish(
                    operation_id, "SUCCEEDED", {"physical_authority": False}
                )
        except BaseException as error:
            errors.append(error)

    def read():
        read_started.set()
        try:
            observations.append(configuration(service))
        except BaseException as error:
            errors.append(error)
        finally:
            read_done.set()

    monkeypatch.setattr(service._log, "append", delayed_log)
    finishing = threading.Thread(target=complete, daemon=True)
    reading = threading.Thread(target=read, daemon=True)
    finishing.start()
    try:
        assert entered.wait(2)
        reading.start()
        assert read_started.wait(2)
        assert not read_done.wait(0.05)
    finally:
        release.set()
        finishing.join(3)
        if reading.ident is not None:
            reading.join(3)
    assert not finishing.is_alive() and not reading.is_alive() and not errors
    assert observations == [original["projection"]]
    assert service.operation(operation_id)["completion_log_persisted"] is True


@pytest.mark.parametrize("action_id", INVALIDATING_ACTIONS)
@pytest.mark.parametrize("status", ["FAILED", "CANCELLED", "TIMED_OUT"])
def test_failed_commissioning_retires_current_config_but_not_original_evidence(
    make_service, action_id, status
):
    service, runner, _ = make_service()
    original = seed(service)
    operation_id = pending(service, action_id)
    with service._lock:
        service._finish(operation_id, status, {"physical_authority": False})
    assert configuration(service) is None
    assert service._commissioning._configuration_hidden is True
    assert service._commissioning._camera_readback is None
    assert service.operation(operation_id)["status"] == status
    assert_private_evidence_unchanged(service, original)
    assert not runner.calls


@pytest.mark.parametrize("action_id", INVALIDATING_ACTIONS)
def test_completion_log_loss_does_not_publish_an_inner_success(
    make_service, monkeypatch, action_id
):
    service, runner, _ = make_service()
    original = seed(service)
    operation_id = pending(service, action_id)

    def fail(*args, **kwargs):
        raise OSError("Injected log loss; no automatic repair")

    monkeypatch.setattr(service._log, "append", fail)
    with service._lock:
        service._finish(operation_id, "SUCCEEDED", {"physical_authority": False})
    operation = service.operation(operation_id)
    assert operation["status"] == "FAILED"
    assert operation["action_outcome_before_log_failure"] == "SUCCEEDED"
    assert operation["completion_log_persisted"] is False
    assert operation["result_retention"] == "FULL_JSON_RETAINED_COMPLETION_LOG_FAILED"
    assert configuration(service) is None
    assert_private_evidence_unchanged(service, original)
    assert not runner.calls


@pytest.mark.parametrize("failure", ["changed", "unreadable"])
def test_source_verification_hold_retires_current_not_retained_configuration(
    make_service, monkeypatch, failure
):
    service, runner, source = make_service()
    original = seed(service)
    if failure == "changed":
        source["hash"] = "f" * 64
    else:

        def unreadable(*args, **kwargs):
            raise OSError("Injected source verification failure")

        monkeypatch.setattr(arrival, "source_fingerprint", unreadable)
    with service._lock, pytest.raises(WizardError) as error:
        service._recheck_source("rehearsal_camera_configuration")
    assert error.value.code == "SOURCE_CHANGED"
    assert configuration(service) is None
    assert service.view()["diagnostics"]["source_changed"] is True
    assert_private_evidence_unchanged(service, original)
    assert not runner.calls


def test_unrelated_diagnostic_log_loss_also_retires_current_configuration(
    make_service, monkeypatch
):
    service, _, _ = make_service()
    original = seed(service)

    def fail(*args, **kwargs):
        raise OSError("Injected unrelated note-log loss")

    monkeypatch.setattr(service._log, "append", fail)
    with service._lock:
        assert service._append_event("OPERATOR_NOTE", {"note": "fixture"}) is False
    assert configuration(service) is None
    assert service.view()["diagnostics"]["log_state"] == "HELD"
    assert_private_evidence_unchanged(service, original)


@pytest.mark.parametrize("in_flight", [False, True])
def test_status_reads_only_cached_configuration_and_never_dispatches_or_reads_files(
    make_service, monkeypatch, in_flight
):
    service, runner, source = make_service()
    original = seed(service)
    if in_flight:
        operation_id = pending(service, "rehearsal_camera_probe")
    # Warm imports before denying every host-file access during status.
    before = service.view()
    source_calls = source["calls"]

    def forbidden(*args, **kwargs):
        raise AssertionError("Status must use cached data only")

    with monkeypatch.context() as guard:
        for name in ("open", "read_text", "read_bytes", "stat", "exists"):
            guard.setattr(Path, name, forbidden)
        guard.setattr("builtins.open", forbidden)
        guard.setattr(arrival, "source_fingerprint", forbidden)
        guard.setattr(service._commissioning, "perform", forbidden)
        guard.setattr(service._commissioning, "latest_preview", forbidden)
        guard.setattr(service._runner, "run", forbidden)
        guard.setattr(service._log, "append", forbidden)
        assert service.view() == before
        assert service.view() == before
        if in_flight:
            assert service.operation(operation_id)["status"] == "RUNNING"
    assert source["calls"] == source_calls
    assert_private_evidence_unchanged(service, original)
    assert not runner.calls and service._events == []
