"""Public action and export boundaries with a delegated service double.

No test in this file proves process execution, M1 durability or physical I/O.
Full process/native bytes remain outside Arrival's bounded diagnostics.
"""

from copy import deepcopy
import json
from pathlib import Path
import threading

import pytest

from rocell.application.wizard_actions import (
    ACTION_BY_ID,
    WizardError,
    validate_action_input,
)
from test_arrival_wizard_service import make_service, _complete, _run, _ticket
from test_wizard_owned_camera_arrival import worker_result, prior_preview
from test_wizard_owned_arm_feedback_ui import summary


ACTION = "rehearsal_owned_arm_feedback_campaign"
SCENARIOS = (
    "nominal",
    "boot-bytes",
    "short-write",
    "timeout",
    "identity-change",
    "identity-change-preopen",
    "malformed-metadata",
    "close-failure",
    "malformed-response",
    "extra-response",
    "child-timeout",
    "malformed-result",
)


def install(service, monkeypatch, *, status="SUCCEEDED", hook=None):
    calls = []
    monkeypatch.setattr(service._commissioning, "blocked_reason", lambda _: None)
    monkeypatch.setattr(service._commissioning, "bind", lambda action, values: values)
    original_view = service._commissioning.view
    projection = summary()
    monkeypatch.setattr(
        service._commissioning,
        "view",
        lambda: {**original_view(), "arm_feedback_process": deepcopy(projection)},
    )

    def forbidden(*args, **kwargs):
        pytest.fail("No camera preview/file/provider access belongs to arm feedback")

    monkeypatch.setattr(service._commissioning, "latest_preview", forbidden)

    def perform(action_id, values, *, cancellation, progress):
        calls.append((action_id, deepcopy(values)))
        assert service.view()["commissioning_rehearsal"]["arm_feedback_process"] is None
        if hook:
            hook(cancellation)
        result = worker_result(action_id, status)
        if result["schema"] == "rocell.wizard_worker_result.v1":
            result["steps"].append(
                {
                    "name": "retained-owned-feedback-diagnostics",
                    "exit_code": 0,
                    "report": {
                        "arm_feedback_process": deepcopy(projection),
                        "physical_authority": False,
                    },
                }
            )
        return result

    monkeypatch.setattr(service._commissioning, "perform", perform)
    return calls, projection


@pytest.mark.parametrize("scenario", SCENARIOS)
def test_only_closed_scenarios_are_offered_and_old_memory_action_is_unchanged(scenario):
    action = ACTION_BY_ID[ACTION]
    assert action.worker == "commissioning" and action.mode == "rehearsal"
    assert validate_action_input(action, {"scenario": scenario}) == {
        "scenario": scenario
    }
    assert [row["value"] for row in action.fields[0]["options"]] == list(SCENARIOS)
    assert ACTION_BY_ID["rehearsal_arm_feedback_campaign"].fields == ()
    assert not action.view(mode="physical", busy=False)["enabled"]


@pytest.mark.parametrize(
    "value",
    [
        {"scenario": "arbitrary"},
        {"scenario": None},
        {"scenario": 1},
        {"port": "COM3"},
        {"command": "T105"},
        {"directory": "C:/arbitrary"},
        {"worker": "native"},
        {"allow_hardware": True},
        {"timeout_s": 120},
    ],
)
def test_no_command_path_hardware_switch_or_budget_override(value):
    with pytest.raises(WizardError):
        validate_action_input(ACTION_BY_ID[ACTION], value)


def test_start_view_and_due_stage_hold_are_inert(make_service):
    service, runner, _ = make_service()
    view = service.view()
    assert view["commissioning_rehearsal"]["arm_feedback_process"] is None
    assert not next(row for row in view["actions"] if row["action_id"] == ACTION)[
        "enabled"
    ]
    with pytest.raises(WizardError):
        _ticket(service, ACTION)
    assert not runner.calls and not service._commissioning.directory.exists()


def test_preview_has_exact_count_budget_stop_limits_and_no_dispatch(
    make_service, monkeypatch
):
    service, runner, _ = make_service()
    calls, _ = install(service, monkeypatch)
    prior_preview(service)
    prepared = _ticket(service, ACTION, {"scenario": "child-timeout"})
    text = " ".join(prepared["effects"])
    for expected in (
        "at most one owned child",
        "20-second",
        "2048-byte",
        "one close attempt",
        "Stop",
        "without replay or fallback",
        "never prove physical de-energization",
    ):
        assert expected in text
    assert prepared["input"] == {"scenario": "child-timeout"}
    assert prepared["physical_authority"] is False
    assert service.view()["camera"]["image_id"] == "old-image"
    assert not calls and not runner.calls


def test_process_projection_waits_for_persisted_outer_completion(
    make_service, monkeypatch
):
    service, _, _ = make_service()
    calls, expected = install(service, monkeypatch)
    prior_preview(service)
    append = service._log.append

    def inspect_log(kind, value):
        if kind in {"ACTION_EXECUTED", "ACTION_FINISHED"}:
            assert (
                service.view()["commissioning_rehearsal"]["arm_feedback_process"]
                is None
            )
        return append(kind, value)

    monkeypatch.setattr(service._log, "append", inspect_log)
    result = _run(service, ACTION)
    assert (
        result["status"] == "SUCCEEDED" and result["completion_log_persisted"]
    ), result
    assert calls == [(ACTION, {"scenario": "nominal"})]
    assert service.view()["commissioning_rehearsal"]["arm_feedback_process"] == expected
    assert service.view()["camera"]["image_id"] is None
    assert service.view()["arm"]["status"] == "NOT_CONNECTED"
    assert service.view()["arm"]["physical_connection_available"] is False


@pytest.mark.parametrize("kind", ["source", "log", "closed"])
def test_external_hold_hides_current_card_but_keeps_original_delegated_report(
    make_service, monkeypatch, kind
):
    service, _, _ = make_service()
    _, original = install(service, monkeypatch)
    before = deepcopy(original)
    if kind == "source":
        service._source_changed = True
    elif kind == "log":
        service._log_error = {"code": "LOG_FAILED", "message": "injected"}
    else:
        service._closed = True
    assert service.view()["commissioning_rehearsal"]["arm_feedback_process"] is None
    assert service._commissioning.view()["arm_feedback_process"] == before == original


def test_stop_is_one_cancellation_not_process_restart_or_memory_fallback(
    make_service, monkeypatch
):
    service, _, _ = make_service()
    entered, release = threading.Event(), threading.Event()

    def hook(cancellation):
        entered.set()
        assert release.wait(3)
        assert cancellation.is_set()

    calls, _ = install(service, monkeypatch, status="CANCELLED", hook=hook)
    operation = service.execute_action(_ticket(service, ACTION)["ticket_id"])
    try:
        assert entered.wait(3)
        stop = _ticket(service, "stop_operation")
        service.execute_action(stop["ticket_id"])
    finally:
        release.set()
    done = _complete(service, operation["operation_id"])
    assert done["status"] == "CANCELLED"
    assert len(calls) == 1 and calls[0][0] == ACTION


def test_assigned_export_retains_small_process_summary_and_no_raw_streams(
    make_service, monkeypatch
):
    from rocell.application.wizard_diagnostic_export import verify_export

    service, _, _ = make_service()
    _, expected = install(service, monkeypatch)
    completed = _run(service, ACTION)
    assert completed["status"] == "SUCCEEDED"
    exported = _run(service, "export_logs")
    assert exported["status"] == "SUCCEEDED"
    receipt = exported["result"]["receipt"]
    verified = verify_export(Path(receipt["path"]))
    assert verified["valid"], verified
    retained = json.dumps(completed, sort_keys=True)
    assert (
        expected["evidence_sha256"] in retained and "arm_feedback_process" in retained
    )
    assert len(retained) < 64 * 1024
    assert not any(
        '"' + key + '"' in retained
        for key in (
            "stdout",
            "stderr",
            "raw_serial",
            "response_base64",
            "unexpected_base64",
        )
    )


def test_late_failure_exports_retained_safe_feedback_without_current_claim(
    make_service, monkeypatch
):
    service, _, _ = make_service()
    _, process = install(service, monkeypatch)
    retained = {
        "arm_feedback_process": deepcopy(process),
        "retained_campaign_sha256": "b" * 64,
        "physical_authority": False,
    }
    service._commissioning._feedback_diagnostic = deepcopy(retained)

    def late_failure(*args, **kwargs):
        raise WizardError(
            "FEEDBACK_CANCELLED_BEFORE_PUBLICATION",
            "Stop after known private retention; no replay",
        )

    monkeypatch.setattr(service._commissioning, "perform", late_failure)
    completed = _run(service, ACTION)
    assert completed["status"] == "FAILED"
    assert service.view()["commissioning_rehearsal"]["arm_feedback_process"] is None
    assert completed["result"]["retained_feedback_diagnostics"] == retained
    assert service._commissioning.retained_feedback_diagnostics() == retained
    completed["result"]["retained_feedback_diagnostics"]["physical_authority"] = True
    assert (
        service._commissioning.retained_feedback_diagnostics()["physical_authority"]
        is False
    )
    exported = _run(service, "export_logs")
    folder = Path(exported["result"]["receipt"]["path"])
    assert verify_export_for_test(folder)
    dedicated = json.loads(
        (folder / "attachment-owned-arm-connection.json").read_bytes()
    )
    assert dedicated["publication"] == "HISTORICAL_HELD"
    content = "".join(
        path.read_text(encoding="utf-8")
        for path in folder.glob("attachment-result-*.json")
    )
    assert (
        process["evidence_sha256"] in content
        and "retained_feedback_diagnostics" in content
    )


def verify_export_for_test(folder):
    from rocell.application.wizard_diagnostic_export import verify_export

    return verify_export(folder)["valid"]


@pytest.mark.parametrize("historical", [False, True])
def test_connection_diagnostics_survive_rotating_results_in_assigned_export(
    make_service, monkeypatch, historical
):
    service, _, _ = make_service()
    _, process = install(service, monkeypatch)
    # This is an export boundary fixture, not evidence of controller resolution.
    retained = {
        "arm_feedback_process": deepcopy(process),
        "controller_resolution": {
            "status": "NOT_RETAINED",
            "trace": None,
            "trace_sha256": None,
            "physical_authority": False,
        },
        "retained_campaign_sha256": "b" * 64,
        "physical_authority": False,
    }
    service._commissioning._feedback_diagnostic = deepcopy(retained)
    for index in range(9):
        assert (
            _run(service, "record_note", {"note": f"connection-note-{index}"})["status"]
            == "SUCCEEDED"
        )
    if historical:
        service._source_changed = True
    completed = _run(service, "export_logs")
    assert completed["status"] == "SUCCEEDED", completed
    folder = Path(completed["result"]["receipt"]["path"])
    assert verify_export_for_test(folder)
    payload = json.loads((folder / "attachment-owned-arm-connection.json").read_bytes())
    assert payload["original_bytes_preserved"] is True
    assert payload["diagnostics"] == retained
    assert payload["publication"] == (
        "HISTORICAL_HELD" if historical else "CURRENT_REHEARSAL_DIAGNOSTIC"
    )
    assert payload["physical_authority"] is False
    assert "owned-arm-connection.json" in json.dumps(completed)


def test_real_resolution_trace_uses_dedicated_export_not_deep_worker_result(
    make_service, monkeypatch
):
    from test_arm_controller_resolution_trace import execution
    from rocell.application.wizard_diagnostic_export import sanitize_diagnostic_record

    service, _, _ = make_service()
    _, process = install(service, monkeypatch)
    executed = execution()
    trace = executed[2]
    full = {
        "arm_feedback_process": process,
        "controller_resolution": {
            "status": "RETAINED",
            "trace": trace.to_dict(),
            "trace_sha256": trace.sha256,
            "physical_authority": False,
        },
        "physical_authority": False,
    }
    service._commissioning._feedback_diagnostic = deepcopy(full)
    compact = service._commissioning.retained_feedback_diagnostics(
        include_resolution_trace=False
    )
    assert (
        compact["controller_resolution"]["status"] == "FULL_TRACE_IN_DEDICATED_EXPORT"
    )
    assert compact["controller_resolution"]["trace"] is None
    assert compact["controller_resolution"]["trace_sha256"] == trace.sha256
    wrapped = {
        "steps": [
            {"name": "retained-incapable-feedback-diagnostics", "report": compact}
        ]
    }
    assert sanitize_diagnostic_record(wrapped) == wrapped
    assert service._commissioning.retained_feedback_diagnostics() == full
    exported = _run(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    folder = Path(exported["result"]["receipt"]["path"])
    document = json.loads(
        (folder / "attachment-owned-arm-connection.json").read_bytes()
    )
    assert document["original_bytes_preserved"] is True
    assert (
        document["diagnostics"]["controller_resolution"]
        == full["controller_resolution"]
    )
