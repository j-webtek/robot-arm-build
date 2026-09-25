"""Application publication/fault tests with explicitly modeled storage callbacks.

These fast tests do not qualify NTFS or devices. The separate public setup
smoke executes actual M1 storage and original-byte readback without hardware.
"""

from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from rocell.application.physical_camera_setup_service import SETUP_ACTIONS
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import make_service, _run, _ticket


def model_storage(service, monkeypatch):
    owner = service._physical_camera_setup.session
    calls = []

    def initialized(**kwargs):
        calls.append("initialize")
        owner._cached.update(
            status="STORAGE_READY_PENDING",
            initialize_attempted=True,
            verification={
                "effects_allowed_by_m1_storage": True,
                "challenge_sha256": "c" * 64,
            },
            stages=[
                {
                    "stage": x.value,
                    "state": "PENDING",
                    "last_event_sequence": None,
                    "evidence_ids": [],
                }
                for x in STAGE_ORDER
            ],
        )
        return owner.view()

    monkeypatch.setattr(owner, "initialize", initialized)
    return calls


def test_cached_constructor_and_preview_are_inert(make_service):
    service, runner, source = make_service(mode="physical")
    setup = service._physical_camera_setup
    before = setup.view()
    reads = source["calls"]
    for _ in range(3):
        assert service.view()["physical_camera_setup"] == before
    assert source["calls"] == reads
    assert before["session"]["status"] == "NOT_INITIALIZED"
    assert not Path(before["session"]["binding"]["directory"]).exists()
    ticket = _ticket(service, "physical_camera_initialize")
    assert "Exact setup context" in " ".join(ticket["effects"])
    assert setup.view() == before and not runner.calls


@pytest.mark.parametrize("name", sorted(SETUP_ACTIONS))
def test_rehearsal_and_browser_supplied_internal_fields_are_refused(make_service, name):
    rehearsal, _, _ = make_service()
    with pytest.raises(WizardError):
        _ticket(rehearsal, name)
    physical, runner, _ = make_service(mode="physical")
    for values in (
        {"setup_context_sha256": "a" * 64},
        {"directory": "C:\\elsewhere"},
        {"source_report": {}},
        {"selection": {}},
    ):
        with pytest.raises(WizardError, match="unsupported field"):
            _ticket(physical, name, values)
    assert not runner.calls


def test_explicit_initialization_publishes_storage_only_and_is_one_use(
    make_service, monkeypatch
):
    service, runner, _ = make_service(mode="physical")
    calls = model_storage(service, monkeypatch)
    outcome = _run(service, "physical_camera_initialize")
    assert outcome["status"] == "SUCCEEDED", outcome
    view = service.view()
    assert view["physical_camera_setup"]["publication"]["status"] == "CURRENT"
    assert view["physical_camera_setup"]["prerequisites"] is None
    assert all(
        x["state"] == "PENDING"
        for x in view["physical_camera_setup"]["session"]["stages"]
    )
    assert all(x["state"] == "PHYSICAL_PENDING" for x in view["stages"])
    assert view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED"
    with pytest.raises(WizardError):
        _ticket(service, "physical_camera_initialize")
    for name in (
        "physical_camera_probe",
        "physical_camera_capture",
        "camera_connect",
        "arm_connect",
        "execute_task",
    ):
        with pytest.raises(WizardError):
            _ticket(service, name)
    assert calls == ["initialize"] and not runner.calls


def test_ticket_bound_original_state_cannot_change_between_preview_and_execution(
    make_service, monkeypatch
):
    service, runner, _ = make_service(mode="physical")
    calls = model_storage(service, monkeypatch)
    ticket = _ticket(service, "physical_camera_initialize")
    service._physical_camera_setup.session._cached["partial_store_possible"] = True
    from test_arrival_wizard_service import _complete

    outcome = _complete(
        service, service.execute_action(ticket["ticket_id"])["operation_id"]
    )
    assert outcome["status"] == "FAILED"
    assert outcome["result"]["code"] == "CAMERA_SETUP_CONTEXT_CHANGED"
    assert not calls and not runner.calls


@pytest.mark.parametrize("cause", ["stop", "source", "redaction"])
def test_late_failures_preserve_result_without_current_publication(
    make_service, monkeypatch, cause
):
    service, runner, source = make_service(mode="physical")
    calls = model_storage(service, monkeypatch)
    original = service._physical_camera_setup.perform

    def late(*args, **kwargs):
        result = original(*args, **kwargs)
        if cause == "stop":
            kwargs["cancellation"].set()
        elif cause == "source":
            source["hash"] = "f" * 64
        else:
            result["steps"][0]["report"]["note"] = "token=example-fixture"
        return result

    monkeypatch.setattr(service._physical_camera_setup, "perform", late)
    outcome = _run(service, "physical_camera_initialize")
    assert outcome["status"] == ("SUCCEEDED" if cause == "stop" else "FAILED"), outcome
    view = service.view()["physical_camera_setup"]
    assert view["publication"]["status"] == "HISTORICAL_HELD"
    assert view["prerequisites"] is None
    if cause == "stop":
        assert "cannot undo evidence" in outcome["result"]["message"]
    elif cause == "redaction":
        assert outcome["result"]["code"] == "BOUND_CAMERA_SETUP_REDACTED"
        assert "example-fixture" not in json.dumps(outcome)
    else:
        assert "retained_camera_setup" in outcome["result"]
    assert calls == ["initialize"] and not runner.calls


@pytest.mark.parametrize("event", ["ACTION_EXECUTED", "ACTION_FINISHED"])
def test_log_failure_cannot_publish_current_setup(make_service, monkeypatch, event):
    service, runner, _ = make_service(mode="physical")
    calls = model_storage(service, monkeypatch)
    original = service._append_event
    monkeypatch.setattr(
        service,
        "_append_event",
        lambda name, data: False if name == event else original(name, data),
    )
    outcome = _run(service, "physical_camera_initialize")
    assert outcome["status"] == "FAILED"
    assert (
        service.view()["physical_camera_setup"]["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    assert len(calls) == int(event == "ACTION_FINISHED") and not runner.calls


def test_retained_setup_full_result_is_exported(make_service, monkeypatch):
    service, _, _ = make_service(mode="physical")
    model_storage(service, monkeypatch)
    outcome = _run(service, "physical_camera_initialize")
    exported = _run(service, "export_logs")
    folder = Path(exported["result"]["receipt"]["path"])
    assert verify_export(folder)["valid"] is True
    assert (
        json.loads(next(folder.glob("attachment-result-*.json")).read_bytes())
        == outcome["result"]
    )


def test_precancelled_collection_is_one_use_without_a_file_read(
    make_service, monkeypatch
):
    service, _, _ = make_service(mode="physical")
    model_storage(service, monkeypatch)
    assert _run(service, "physical_camera_initialize")["status"] == "SUCCEEDED"
    setup = service._physical_camera_setup
    context = setup.context_sha256(
        "physical_camera_prerequisites", service._native_camera, None
    )
    stop = threading.Event()
    stop.set()
    with pytest.raises(WizardError, match="stopped or expired"):
        setup.perform(
            "physical_camera_prerequisites",
            expected_context_sha256=context,
            operator_id="operator",
            enrollment=service._native_camera,
            source_report=None,
            cancellation=stop,
            progress=lambda _: None,
        )
    assert setup.retained_diagnostics()["collection_attempted"] is True
    assert "already attempted" in setup.blocked_reason("physical_camera_prerequisites")
    assert setup.view()["prerequisites"] is None
