"""Modeled original-store publication joins; not storage/device qualification.

The separate public smoke checks actual M1 files. Here the retained prerequisite
artifact is real and strict, but the upstream M1 publication is explicitly modeled.
"""

import json
from pathlib import Path
import threading
import time

import pytest

from rocell.application.physical_camera_prerequisites import (
    collect_physical_camera_prerequisites,
)
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import make_service, _run, _ticket, _complete
from test_physical_camera_prerequisites import workspace, SOURCE


FIELDS = {
    "record_id": "INT-001",
    "observation_status": "UNKNOWN",
    "observed_value": "Hardware not received in this modeled service test",
    "method": "No measurement performed",
    "evidence_note": "No attachment supplied",
    "operator_id": "test-operator",
}


@pytest.fixture(autouse=True)
def no_devices_or_storage_runtime(monkeypatch):
    import subprocess

    def denied(*args, **kwargs):
        pytest.fail("Draft service tests must not dispatch any process or M1 runtime")

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(PhysicalOnboardingM1Runtime, "initialize", denied)
    monkeypatch.setattr(PhysicalOnboardingM1Runtime, "open", denied)


@pytest.fixture
def ready(make_service, workspace):
    service, runner, source = make_service(mode="physical")
    setup = service._physical_camera_setup
    binding = setup.session.descriptor()
    artifact = collect_physical_camera_prerequisites(
        workspace,
        source_sha256=SOURCE,
        session_id=binding["session_id"],
        launch_session_id=service.session_id,
        cancellation=threading.Event(),
        deadline_ns=time.monotonic_ns() + 30_000_000_000,
    )
    setup._prerequisites = artifact.safe_summary()
    setup._retained = {
        "document": artifact.to_dict(),
        "evidence_sha256": artifact.evidence_sha256,
        "retention": "M1_FULL_BYTES_READ_BACK",
        "reference": None,
    }
    setup._publication = {
        "status": "CURRENT",
        "operation_id": "modeled-upstream-publication",
    }
    return service, runner, source, artifact


def start(ready):
    service = ready[0]
    result = _run(service, "physical_intake_start")
    assert result["status"] == "SUCCEEDED", result
    return service.view()["physical_intake"]["notebook"]


def notebook_result(outcome):
    return outcome["result"]["steps"][0]["report"]["notebook"]


def test_start_blank_original_questions_and_unknown_entry_no_stage_mutation(ready):
    service, runner, source, artifact = ready
    before = service._physical_camera_setup.view()
    reads = source["calls"]
    assert service.view()["physical_intake"]["status"] == "NOT_STARTED"
    assert source["calls"] == reads
    blank = start(ready)
    assert blank["coverage"] == {
        "total": 16,
        "observed": 0,
        "unknown": 0,
        "unrecorded": 16,
    }
    assert all(row["observation"] is None for row in blank["rows"])
    assert {row["record_id"] for row in blank["rows"]} == {
        row["record_id"] for row in artifact.safe_summary()["stages"][2]["intake_rows"]
    }
    assert "INT-018" not in {row["record_id"] for row in blank["rows"]}
    outcome = _run(service, "physical_intake_record", FIELDS)
    assert outcome["status"] == "SUCCEEDED", outcome
    current = service.view()["physical_intake"]["notebook"]
    assert current == notebook_result(outcome)
    assert current["revision"] == 1
    assert current["previous_sha256"] == blank["snapshot_sha256"]
    assert current["coverage"]["unknown"] == 1 and current["coverage"]["observed"] == 0
    assert service._physical_camera_setup.view() == before
    assert (
        service.view()["camera"]["status"]
        == service.view()["arm"]["status"]
        == "NOT_CONNECTED"
    )
    assert not runner.calls
    with pytest.raises(WizardError, match="already has a draft"):
        _ticket(service, "physical_intake_start")


def test_explicit_revision_does_not_erase_retained_previous_result(ready):
    service = ready[0]
    start(ready)
    previous = _run(service, "physical_intake_record", FIELDS)
    after = _run(
        service,
        "physical_intake_record",
        {**FIELDS, "observed_value": "Still unknown after operator follow-up"},
    )
    assert after["status"] == "SUCCEEDED"
    assert notebook_result(after)["revision"] == 2
    assert (
        notebook_result(after)["previous_sha256"]
        == notebook_result(previous)["snapshot_sha256"]
    )
    assert notebook_result(
        service.operation(previous["operation_id"])
    ) == notebook_result(previous)


@pytest.mark.parametrize(
    "patch",
    [
        {"record_id": "INT-018"},
        {"record_id": "INT-025"},
        {"observation_status": "PASS"},
        {"evidence_path": "not-an-input"},
        {"intake_context_sha256": "a" * 64},
        {"physical_authority": True},
    ],
)
def test_closed_fields_and_question_selection(ready, patch):
    service = ready[0]
    start(ready)
    with pytest.raises(WizardError):
        _ticket(service, "physical_intake_record", {**FIELDS, **patch})


@pytest.mark.parametrize("value", ["NaN", "1e3", "-10", "0", "610 mm"])
def test_numeric_validation_fails_without_changing_old_draft(ready, value):
    service = ready[0]
    before = start(ready)
    outcome = _run(
        service,
        "physical_intake_record",
        {**FIELDS, "observation_status": "OBSERVED", "observed_value": value},
    )
    assert outcome["status"] == "FAILED"
    assert service.view()["physical_intake"]["notebook"] == before


@pytest.mark.parametrize(
    "retention", ["COLLECTED_NOT_M1_RETAINED", "M1_PUBLISHED_READBACK_PENDING"]
)
def test_accessor_refuses_nonreadback_artifact(ready, retention):
    setup = ready[0]._physical_camera_setup
    setup._retained["retention"] = retention
    with pytest.raises(WizardError):
        setup.current_prerequisite_artifact()


def test_prerequisite_tamper_refused_before_new_notebook(ready):
    service = ready[0]
    service._physical_camera_setup._retained["document"]["requirements"]["stages"][2][
        "intake_rows"
    ][0]["unit"] = "inch"
    outcome = _run(service, "physical_intake_start")
    assert outcome["status"] == "FAILED"
    assert service.view()["physical_intake"]["notebook"] is None


def test_stale_context_after_ticket_is_held(ready):
    service = ready[0]
    start(ready)
    ticket = _ticket(service, "physical_intake_record", FIELDS)
    service._physical_camera_setup._prerequisites["evidence_sha256"] = "f" * 64
    with pytest.raises(WizardError):
        service.execute_action(ticket["ticket_id"])
    assert service.view()["physical_intake"]["status"] == "HISTORICAL_HELD"


def test_redacted_draft_not_published(ready):
    service = ready[0]
    before = start(ready)
    outcome = _run(
        service,
        "physical_intake_record",
        {**FIELDS, "evidence_note": "Authorization: Bearer secret-test-token"},
    )
    assert outcome["status"] == "FAILED", outcome
    assert outcome["result"]["code"] == "BOUND_INTAKE_REDACTED"
    assert service.view()["physical_intake"]["notebook"] == before
    assert "secret-test-token" not in json.dumps(outcome)


def test_completion_log_failure_does_not_publish_candidate(ready, monkeypatch):
    service = ready[0]
    before = start(ready)
    append = service._log.append

    def fail_finish(kind, details):
        if kind == "ACTION_FINISHED":
            raise OSError("modeled completion failure")
        return append(kind, details)

    monkeypatch.setattr(service._log, "append", fail_finish)
    outcome = _run(service, "physical_intake_record", FIELDS)
    assert outcome["status"] == "FAILED"
    assert service._physical_intake.view() == before
    assert service.view()["physical_intake"]["notebook"] is None
    assert (
        notebook_result(outcome)["revision"] == 1
    )  # Candidate retained, not published.


def test_public_stop_after_staging_does_not_publish_candidate(ready, monkeypatch):
    service = ready[0]
    before = start(ready)
    reached, release = threading.Event(), threading.Event()
    validate = service._validated_result

    def barrier(action, result):
        if action == "physical_intake_record":
            reached.set()
            assert release.wait(3)
        return validate(action, result)

    monkeypatch.setattr(service, "_validated_result", barrier)
    ticket = _ticket(service, "physical_intake_record", FIELDS)
    receipt = service.execute_action(ticket["ticket_id"])
    try:
        assert reached.wait(3)
        _run(service, "stop_operation")
    finally:
        release.set()
    outcome = _complete(service, receipt["operation_id"])
    assert outcome["status"] == "CANCELLED"
    assert service._physical_intake.view() == before


def test_postresult_source_change_retains_candidate_not_current(ready, monkeypatch):
    service, _, source, _ = ready
    before = start(ready)
    validate = service._validated_result

    def drift(action, result):
        clean = validate(action, result)
        source["hash"] = "f" * 64
        return clean

    monkeypatch.setattr(service, "_validated_result", drift)
    outcome = _run(service, "physical_intake_record", FIELDS)
    assert outcome["status"] == "FAILED"
    assert notebook_result(outcome)["revision"] == 1
    assert service._physical_intake.view() == before
    assert service.view()["physical_intake"]["status"] == "HISTORICAL_HELD"


def test_export_reserves_draft_after_rotating_results_and_labels_historical(ready):
    service = ready[0]
    start(ready)
    outcome = _run(service, "physical_intake_record", FIELDS)
    expected = notebook_result(outcome)
    for index in range(9):
        _run(service, "record_note", {"note": f"Ordinary later diagnostic {index}"})
    assert service.operation(outcome["operation_id"])["result"] is None
    service._physical_camera_setup.invalidate()
    exported = _run(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    folder = Path(exported["result"]["receipt"]["path"])
    assert verify_export(folder)["valid"]
    payload = (folder / "attachment-physical-intake-notebook.json").read_bytes()
    dedicated = json.loads(payload)
    assert dedicated["status"] == "HISTORICAL_HELD"
    assert dedicated["notebook"] == expected
    report = json.loads((folder / "report.json").read_bytes())["snapshot"]
    assert report["result_export_policy"]["included_full_results"] == 7
    assert report["result_export_policy"]["dedicated_attachments"] == [
        "physical-intake-notebook.json"
    ]
    assert any(
        item["reason"] == "ATTACHMENT_COUNT_BUDGET"
        for item in report["result_export_policy"]["omitted"]
    )


def test_no_initial_notebook_and_no_physical_mode_fallback(make_service):
    for mode in ("rehearsal", "physical"):
        service, runner, _ = make_service(mode=mode)
        for action in ("physical_intake_start", "physical_intake_record"):
            with pytest.raises(WizardError):
                _ticket(service, action, FIELDS if action.endswith("record") else {})
        assert service.view()["physical_intake"]["notebook"] is None
        assert not runner.calls
