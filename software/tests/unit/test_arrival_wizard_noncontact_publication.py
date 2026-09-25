"""Public publication/export joins with a modeled commissioning service boundary.

The real Arrival tickets, worker-result validator, diagnostic log and exporter
are exercised. Original M1 receipt bytes and stage state are explicitly modeled;
these tests neither qualify storage nor run collision/accuracy or hardware work.
"""

from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from rocell.application import arrival_wizard_service as arrival
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_noncontact_ui import projection
from test_arrival_wizard_service import (
    make_service,
    _run,
    _ticket,
    _complete,
)  # noqa: F401


def seeded(service, monkeypatch, *, published=False):
    state = service._commissioning
    value = projection()
    receipt = {
        "schema": "MODELED_RECEIPT_NOT_DURABLE_EVIDENCE",
        "stage": "noncontact_acceptance",
        "evaluation_sha256": value["evaluation_sha256"],
        "evaluation": deepcopy(value),
        "physical_authority": False,
    }
    state._retained_noncontact = receipt
    state._latest_noncontact = deepcopy(value)
    state._cached.update(
        status="READY",
        stage="noncontact_acceptance",
        stage_state="WAITING_OPERATOR",
        noncontact_evaluation=deepcopy(value),
        challenge_sha256="c" * 64,
        quarantined=False,
        unresolved_attempt_ids=[],
    )
    monkeypatch.setattr(state, "blocked_reason", lambda action_id: None)
    monkeypatch.setattr(state, "bind", lambda action_id, values: dict(values))
    if published:
        service._published_noncontact_sha256 = service._noncontact_publication_context(
            state.view()
        )
    return receipt


def completion(action_id, receipt):
    return {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": action_id,
        "status": "SUCCEEDED",
        "steps": [
            {
                "name": "modeled-retained-gap",
                "exit_code": 0,
                "report": deepcopy(receipt),
            }
        ],
        "device_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
        "physical_authority": False,
        "metadata_inventory_performed": False,
    }


def install_perform(service, monkeypatch, receipt, effect=None):
    calls = []

    def perform(action_id, values, *, cancellation, progress):
        calls.append((action_id, deepcopy(values)))
        if effect is not None:
            effect(action_id, cancellation)
        return completion(action_id, receipt)

    monkeypatch.setattr(service._commissioning, "perform", perform)
    return calls


def current(service):
    return service.view()["commissioning_rehearsal"]["noncontact_evaluation"]


def export(service):
    result = _run(service, "export_logs")
    assert result["status"] == "SUCCEEDED", result
    directory = Path(result["result"]["receipt"]["path"])
    assert verify_export(directory)["valid"] is True
    dedicated = json.loads(
        (directory / "attachment-noncontact-readiness.json").read_text()
    )
    report = json.loads((directory / "report.json").read_text())
    return dedicated, report, directory


def test_start_and_prepare_are_inert_and_preview_explains_nominal_blockage(
    make_service, monkeypatch, tmp_path
):
    service, runner, source = make_service()
    assert current(service) is None
    original = seeded(service, monkeypatch, published=True)
    before = deepcopy(original)
    calls = install_perform(service, monkeypatch, original)
    ticket = _ticket(service, "rehearsal_collect", {"operator_id": "operator"})
    effects = " ".join(ticket["effects"])
    assert "BLOCKED/UNBOUNDED" in effects
    assert (
        "No IK search, route campaign, virtual contact, camera, serial or physical motion"
        in effects
    )
    assert "cannot advance to physical handoff" in effects
    assert current(service) == projection()
    assert original == before and not calls and not runner.calls
    assert not (tmp_path / "diagnostics").exists()
    assert not (tmp_path / "exports").exists()
    assert source["calls"] == 2  # constructor and explicit source-checking prepare
    physical, _, _ = make_service(mode="physical")
    with pytest.raises(WizardError) as error:
        _ticket(physical, "rehearsal_collect", {"operator_id": "operator"})
    assert error.value.code == "ACTION_BLOCKED"


@pytest.mark.parametrize(
    "action_id", ["rehearsal_collect", "rehearsal_assess", "rehearsal_refresh"]
)
def test_pending_and_completion_log_boundary_do_not_publish_inner_report(
    make_service, monkeypatch, action_id
):
    service, runner, _ = make_service()
    receipt = seeded(service, monkeypatch, published=True)
    before = deepcopy(receipt)
    entered, release = threading.Event(), threading.Event()

    def block(action, cancel):
        assert current(service) is None
        entered.set()
        assert release.wait(3), "Test worker barrier did not release"

    calls = install_perform(service, monkeypatch, receipt, block)
    append = service._log.append
    log_observations = []

    def log(kind, details):
        if kind == "ACTION_FINISHED":
            log_observations.append(current(service))
        return append(kind, details)

    monkeypatch.setattr(service._log, "append", log)
    values = {"operator_id": "operator"} if action_id == "rehearsal_collect" else {}
    ticket = _ticket(service, action_id, values)
    dispatched = service.execute_action(ticket["ticket_id"])
    try:
        assert entered.wait(2)
        assert current(service) is None
        assert service._commissioning.view()["noncontact_evaluation"] == projection()
    finally:
        release.set()
    finished = _complete(service, dispatched["operation_id"])
    assert finished["status"] == "SUCCEEDED", finished
    assert finished["completion_log_persisted"] is True
    assert log_observations == [None]
    assert current(service) == projection()
    assert (
        service.execute_action(ticket["ticket_id"])["operation_id"]
        == dispatched["operation_id"]
    )
    assert len(calls) == 1 and not runner.calls
    assert receipt == before
    assert all(row["state"] == "PHYSICAL_PENDING" for row in service.view()["stages"])


@pytest.mark.parametrize("failed_kind", ["ACTION_EXECUTED", "ACTION_FINISHED"])
def test_log_failure_withholds_without_mutating_or_replaying_retained_evidence(
    make_service, monkeypatch, failed_kind
):
    service, runner, _ = make_service()
    receipt = seeded(service, monkeypatch, published=True)
    before = deepcopy(receipt)
    calls = install_perform(service, monkeypatch, receipt)
    append = service._log.append

    def failed(kind, details):
        if kind == failed_kind:
            raise OSError("Modeled diagnostic log failure")
        return append(kind, details)

    monkeypatch.setattr(service._log, "append", failed)
    result = _run(service, "rehearsal_collect", {"operator_id": "operator"})
    assert result["status"] == "FAILED"
    assert result["error"]["code"] == "DIAGNOSTIC_LOG_FAILED"
    assert current(service) is None
    assert len(calls) == (failed_kind == "ACTION_FINISHED")
    assert receipt == before
    assert service._commissioning.retained_noncontact_diagnostics() == before
    assert not runner.calls


@pytest.mark.parametrize("when", ["before", "after"])
def test_source_drift_holds_publication_but_dedicated_export_keeps_history(
    make_service, monkeypatch, when
):
    service, runner, source = make_service()
    receipt = seeded(service, monkeypatch, published=True)
    before = deepcopy(receipt)
    if when == "after":

        def drift(action, cancel):
            source["hash"] = "f" * 64

        calls = install_perform(service, monkeypatch, receipt, drift)
        result = _run(service, "rehearsal_collect", {"operator_id": "operator"})
        assert result["status"] == "FAILED"
        assert result["error"]["code"] == "SOURCE_CHANGED"
        assert result["result"]["retained_noncontact_receipt"] == before
        assert len(calls) == 1
    else:
        source["hash"] = "f" * 64
        with pytest.raises(WizardError) as error:
            _ticket(service, "rehearsal_collect", {"operator_id": "operator"})
        assert error.value.code == "SOURCE_CHANGED"
    assert current(service) is None
    dedicated, report, _ = export(service)
    assert dedicated["publication"] == "HISTORICAL_HELD"
    assert dedicated["original_bytes_preserved"] is True
    assert dedicated["receipt"] == before
    assert (
        report["snapshot"]["commissioning_rehearsal"]["noncontact_evaluation"] is None
    )
    assert receipt == before and not runner.calls


@pytest.mark.parametrize("committed", [False, True])
def test_explicit_stop_never_publishes_or_replays_even_if_retention_completed(
    make_service, monkeypatch, committed
):
    service, runner, _ = make_service()
    receipt = seeded(service, monkeypatch, published=True)
    original = deepcopy(receipt)
    entered, release = threading.Event(), threading.Event()

    def stopped(action, cancel):
        entered.set()
        assert release.wait(3)
        assert cancel.is_set()
        if not committed:
            raise WizardError(
                "MODELED_CANCELLED_BEFORE_PUBLICATION", "No modeled stage publication"
            )

    calls = install_perform(service, monkeypatch, receipt, stopped)
    ticket = _ticket(service, "rehearsal_collect", {"operator_id": "operator"})
    dispatched = service.execute_action(ticket["ticket_id"])
    try:
        assert entered.wait(2)
        stop = _run(service, "stop_operation")
        assert stop["status"] == "SUCCEEDED"
        assert "Not a robot emergency stop" in stop["result"]["message"]
        assert current(service) is None
    finally:
        release.set()
    result = _complete(service, dispatched["operation_id"])
    assert result["status"] == ("SUCCEEDED" if committed else "FAILED")
    assert current(service) is None
    if committed:
        assert "cannot undo evidence or authorize replay" in result["message"]
    else:
        assert result["result"]["retained_noncontact_receipt"] == original
    assert (
        service.execute_action(ticket["ticket_id"])["operation_id"]
        == dispatched["operation_id"]
    )
    assert len(calls) == 1 and not runner.calls
    dedicated, _, _ = export(service)
    assert dedicated["publication"] == "HISTORICAL_HELD"
    assert dedicated["receipt"] == original
    assert receipt == original


@pytest.mark.parametrize(
    "change",
    [
        {"challenge_sha256": "e" * 64},
        {"session_id": "another-original-session"},
        {"stage": "physical_handoff"},
        {"stage_state": "REVIEW_PENDING"},
        {"status": "HELD"},
        {"status": "REOPEN_HELD"},
        {"quarantined": True},
        {"unresolved_attempt_ids": ["unresolved-attempt"]},
    ],
)
def test_changed_challenge_or_held_original_session_cannot_inherit_publication(
    make_service, monkeypatch, change
):
    service, runner, _ = make_service()
    receipt = seeded(service, monkeypatch, published=True)
    original = deepcopy(receipt)
    assert current(service) is not None
    service._commissioning._cached.update(change)
    assert current(service) is None
    assert service._commissioning.retained_noncontact_diagnostics() == original
    assert not runner.calls


def test_redacted_receipt_is_not_current_or_exported_as_original_hashed_evidence(
    make_service, monkeypatch
):
    service, runner, _ = make_service()
    receipt = seeded(service, monkeypatch)
    receipt["fixture_note"] = "api_key=fixture-sensitive-value"
    original = deepcopy(receipt)
    calls = install_perform(service, monkeypatch, receipt)
    result = _run(service, "rehearsal_collect", {"operator_id": "operator"})
    assert result["status"] == "FAILED"
    assert result["error"]["code"] == "BOUND_NONCONTACT_REDACTED"
    assert current(service) is None
    assert "fixture-sensitive-value" not in json.dumps(result)
    assert receipt == original and len(calls) == 1 and not runner.calls
    dedicated, report, directory = export(service)
    assert dedicated["publication"] == "HISTORICAL_HELD"
    assert dedicated["original_bytes_preserved"] is False
    assert "not the original evidence" in dedicated["meaning"]
    assert dedicated["receipt"]["fixture_note"] == "api_key=[REDACTED]"
    assert (
        "fixture-sensitive-value"
        not in (directory / "attachment-noncontact-readiness.json").read_text()
    )
    assert (
        report["snapshot"]["commissioning_rehearsal"]["noncontact_evaluation"] is None
    )


@pytest.mark.parametrize("failure", ["FAILED", "TIMED_OUT", "oversized", "exception"])
def test_failed_outer_result_cannot_publish_but_does_not_drop_original_receipt(
    make_service, monkeypatch, failure
):
    service, runner, _ = make_service()
    receipt = seeded(service, monkeypatch, published=True)
    original = deepcopy(receipt)
    calls = []

    def perform(action_id, values, *, cancellation, progress):
        calls.append(action_id)
        if failure == "exception":
            raise WizardError(
                "MODELED_LATE_FAILURE", "Retained receipt remains historical"
            )
        if failure == "TIMED_OUT":
            return {
                "schema": "rocell.wizard_diagnostic_completion.v1",
                "action_id": action_id,
                "status": "TIMED_OUT",
                "message": "Modeled bounded worker deadline expired",
                "elapsed_s": 0.0,
                "output_limit_exceeded": False,
                "physical_authority": False,
            }
        result = completion(action_id, receipt)
        if failure == "FAILED":
            result["status"] = "FAILED"
            result["steps"][0]["exit_code"] = 1
        else:
            result["steps"][0]["report"]["over_limit"] = "x" * (64 * 1024 + 1)
        return result

    monkeypatch.setattr(service._commissioning, "perform", perform)
    result = _run(service, "rehearsal_collect", {"operator_id": "operator"})
    assert result["status"] == ("TIMED_OUT" if failure == "TIMED_OUT" else "FAILED")
    assert current(service) is None
    assert calls == ["rehearsal_collect"] and not runner.calls
    assert service._commissioning.retained_noncontact_diagnostics() == original
    if failure in {"oversized", "exception"}:
        assert result["result"]["retained_noncontact_receipt"] == original
    dedicated, _, _ = export(service)
    assert dedicated["publication"] == "HISTORICAL_HELD"
    assert dedicated["original_bytes_preserved"] is True
    assert dedicated["receipt"] == original
    assert receipt == original


def test_dedicated_export_survives_actual_generic_result_eviction(
    make_service, monkeypatch
):
    service, runner, _ = make_service()
    receipt = seeded(service, monkeypatch)
    original = deepcopy(receipt)
    calls = install_perform(service, monkeypatch, receipt)
    first = _run(service, "rehearsal_collect", {"operator_id": "operator"})
    assert first["status"] == "SUCCEEDED"
    for index in range(8):
        assert (
            _run(
                service,
                "record_note",
                {"note": f"Modeled note {index}; no acceptance."},
            )["status"]
            == "SUCCEEDED"
        )
    older = service.operation(first["operation_id"])
    assert older["result"] is None
    assert older["result_retention"] == "OMITTED_OLDER_THAN_LAST_EIGHT_RESULTS"
    assert first["operation_id"] not in service._full_results
    dedicated, report, _ = export(service)
    assert dedicated["schema"] == "rocell.noncontact_diagnostic_export.v1"
    assert dedicated["publication"] == "CURRENT_GAP_REPORT"
    assert dedicated["original_bytes_preserved"] is True
    assert dedicated["receipt"] == original
    assert dedicated["physical_authority"] is False
    policy = report["snapshot"]["result_export_policy"]
    assert policy["dedicated_attachments"] == ["noncontact-readiness.json"]
    assert any(
        row["operation_id"] == first["operation_id"] for row in policy["omitted"]
    )
    assert (
        policy["included_full_results"] == 7
    )  # Dedicated evidence owns one of eight attachment slots.
    assert all("result" not in row for row in report["snapshot"]["operations"])
    assert len(calls) == 1 and not runner.calls and receipt == original


def test_status_and_historical_receipt_getter_are_cached_only(
    make_service, monkeypatch
):
    service, runner, source = make_service()
    receipt = seeded(service, monkeypatch, published=True)
    before = service.view()
    source_calls = source["calls"]

    def forbidden(*args, **kwargs):
        raise AssertionError(
            "Cached read must not access source, M1, evaluator or device"
        )

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
        returned = service._commissioning.retained_noncontact_diagnostics()
        assert returned == receipt
        returned["evaluation_sha256"] = "f" * 64
        assert service._commissioning.retained_noncontact_diagnostics() == receipt
    assert source["calls"] == source_calls and not runner.calls


def test_physical_reopen_retires_acquisition_intent_before_intent_log_failure(
    make_service, monkeypatch
):
    """Regression for unrelated physical-setup invalidation nesting, no M1 open."""
    service, runner, _ = make_service(mode="physical")
    setup = service._physical_camera_setup
    choice = "reopen-" + "1" * 32
    monkeypatch.setattr(setup, "blocked_reason", lambda action_id: None)
    monkeypatch.setattr(
        setup,
        "reopen_choices",
        lambda: [{"value": choice, "label": "Modeled original store"}],
    )
    monkeypatch.setattr(
        setup, "reopen_preview", lambda choice_id: {"choice_id": choice_id}
    )
    monkeypatch.setattr(setup, "context_sha256", lambda *args: "b" * 64)
    invalidations = []
    invalidate = service._physical_camera.invalidate

    def invalidated():
        invalidations.append("retired")
        return invalidate()

    monkeypatch.setattr(service._physical_camera, "invalidate", invalidated)
    ticket = _ticket(
        service,
        "physical_camera_reopen",
        {"choice_id": choice, "operator_id": "operator"},
    )
    assert invalidations == []

    def fail(kind, details):
        if kind == "ACTION_EXECUTED":
            assert invalidations == ["retired"]
        raise OSError("Modeled log failure before any store dispatch")

    monkeypatch.setattr(service._log, "append", fail)
    result = service.execute_action(ticket["ticket_id"])
    assert result["status"] == "FAILED"
    assert service._executor is None
    assert not runner.calls
