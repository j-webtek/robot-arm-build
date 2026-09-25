"""Finite Arrival publication models; no static file collection or hardware.

Actual stage codecs are exercised separately. This fixture tests the public
ticket/log/Stop/export seam without claiming modeled subjects are real evidence.
"""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from rocell.application.wizard_actions import ACTION_BY_ID, WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_source_qualification import (
    QualificationDouble,
    joined,
    make_service,
    complete_setup,
    prerequisite_summary,
)  # noqa: F401
from test_arrival_wizard_service import _run, _ticket, _complete
from test_arrival_wizard_intake_evidence import worker


NAMES = (
    "physical_static_contract_collect",
    "physical_static_contract_review",
    "physical_camera_receipt_begin",
)


class StaticDouble(QualificationDouble):
    def fields(self, action):
        consent = {
            "name": "file_only",
            "type": "checkbox",
            "required": True,
            "default": False,
            "label": "File-only design record, no installation release",
        }
        if action == NAMES[2]:
            return [consent]
        return [
            {
                "name": "operator_id" if action == NAMES[0] else "reviewer_id",
                "type": "text",
                "required": True,
                "default": "",
                "max_length": 64,
                "label": "Procedural label",
            },
            consent,
        ]

    def perform(self, action, values, **kwargs):
        assert not self.arrival._lock._is_owned()
        assert self.arrival._test_setup["publication"]["status"] == "CURRENT"
        assert not any(key.startswith("_") for key in values)
        self.calls.append(action)
        if kwargs["expected_context_sha256"] != self.context:
            raise WizardError("STATIC_CONTEXT_CHANGED", "Modeled changed subject")
        self.expected_result = worker(
            action, {"contract": deepcopy(self.data["contract"])}
        )
        self.data["publication"]["status"] = "PENDING"
        self.arrival._test_setup["publication"]["status"] = "PENDING"
        self.after(values=values, **kwargs)
        return deepcopy(self.expected_result)


@pytest.fixture
def static_join(joined):
    arrival, runner, source, previous, observations = joined
    data = previous.view()
    data.update(
        schema="rocell.wizard_static_camera_onboarding.v1",
        contract={
            "contract_id": "staticcontract-" + "a" * 32,
            "state": "REVIEW_PENDING",
            "receipt": {
                "binding": {"operator_id": "static-operator"},
                "receipt_sha256": "1" * 64,
            },
            "assessment": {"assessment_sha256": "2" * 64},
            "review": None,
        },
        camera_receipt_entry=None,
        next_action=NAMES[1],
    )
    data.pop("qualification")
    data["stage_states"]["camera_receipt"] = "PENDING"
    owner = StaticDouble(arrival, data)
    owner.history = {
        "schema": "MODELED_STATIC_DIAGNOSTICS",
        "static_receipt_document": {"identity": "MODELED_NOT_HARDWARE"},
        "physical_authority": False,
    }
    arrival._static_camera_onboarding = owner
    return arrival, runner, source, owner, previous, observations


def values(action):
    return {
        "file_only": True,
        **(
            {"operator_id": "static-operator"}
            if action == NAMES[0]
            else {"reviewer_id": "static-reviewer"} if action == NAMES[1] else {}
        ),
    }


@pytest.mark.parametrize("action,timeout", zip(NAMES, (180, 120, 120)))
def test_catalog_inert_prepare_one_execution_and_postlog_publication(
    static_join, action, timeout
):
    arrival, runner, source, owner, previous, observations = static_join
    reads = source["calls"]
    assert arrival.view()["static_camera_onboarding"] == owner.view()
    assert source["calls"] == reads and not owner.calls
    assert ACTION_BY_ID[action].timeout_s == timeout
    assert not ACTION_BY_ID[action].view(mode="rehearsal", busy=False)["enabled"]
    ticket = _ticket(arrival, action, values(action))
    assert not owner.calls and "No device is opened" in " ".join(ticket["effects"])
    dispatched = arrival.execute_action(ticket["ticket_id"])
    result = _complete(arrival, dispatched["operation_id"])
    assert result["status"] == "SUCCEEDED", result
    assert owner.calls == [action, "validate", "publish"]
    assert previous.calls == ["observe_setup"] and observations == ["observe_setup"]
    assert (
        arrival.execute_action(ticket["ticket_id"])["operation_id"]
        == result["operation_id"]
    )
    assert owner.calls.count(action) == 1 and not runner.calls
    assert arrival.view()["camera"]["status"] == "NOT_CONNECTED"


@pytest.mark.parametrize(
    "fault", ("stop", "source", "log", "validation", "redaction", "exception")
)
def test_late_fault_holds_original_context_and_retains_history(
    static_join, monkeypatch, fault
):
    arrival, runner, source, owner, previous, _ = static_join
    before = owner.retained_diagnostics()
    if fault == "log":
        append = arrival._log.append

        def fail(name, details):
            if name == "ACTION_FINISHED":
                raise OSError("Modeled completion log failure")
            return append(name, details)

        monkeypatch.setattr(arrival._log, "append", fail)
    owner.bad_validation = fault == "validation"

    def after(**kwargs):
        if fault == "stop":
            kwargs["cancellation"].set()
        elif fault == "source":
            source["hash"] = "f" * 64
        elif fault == "redaction":
            owner.expected_result["steps"][0]["report"][
                "text"
            ] = "password=modeled-secret"
        elif fault == "exception":
            raise RuntimeError("Modeled retained failure")

    owner.after = after
    result = _run(arrival, NAMES[0], values(NAMES[0]))
    assert result["status"] == ("SUCCEEDED" if fault == "stop" else "FAILED"), result
    assert "publish" not in owner.calls and not runner.calls
    assert owner.retained_diagnostics() == before
    assert (
        arrival.view()["static_camera_onboarding"]["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    assert (
        arrival._physical_camera_setup.view()["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    assert "modeled-secret" not in json.dumps(result)


def test_pending_hides_contract_and_entry_without_action_or_mutation(static_join):
    arrival, runner, source, owner, _, _ = static_join
    before = owner.view()
    arrival._running = "modeled-operation"
    arrival._operations[arrival._running] = {
        "operation_id": arrival._running,
        "action_id": NAMES[0],
        "status": "RUNNING",
    }
    try:
        value = arrival.view()["static_camera_onboarding"]
        assert value["publication"]["status"] == "PENDING"
        assert (
            value["contract"]
            is value["camera_receipt_entry"]
            is value["next_action"]
            is None
        )
        assert owner.view() == before and not owner.calls and not runner.calls
    finally:
        arrival._running = None


def test_exact_reviewer_and_stale_context_have_no_fallback(static_join):
    arrival, runner, _, owner, _, _ = static_join
    with pytest.raises(WizardError, match="distinct"):
        _ticket(
            arrival, NAMES[1], {"reviewer_id": "STATIC-OPERATOR", "file_only": True}
        )
    assert not owner.calls
    ticket = _ticket(arrival, NAMES[0], values(NAMES[0]))
    owner.context = "f" * 64
    result = _complete(
        arrival, arrival.execute_action(ticket["ticket_id"])["operation_id"]
    )
    assert (
        result["status"] == "FAILED"
        and "publish" not in owner.calls
        and not runner.calls
    )


def test_combined_reserved_v2_export_keeps_both_families_after_rotation(static_join):
    arrival, _, _, owner, previous, _ = static_join
    assert _run(arrival, NAMES[0], values(NAMES[0]))["status"] == "SUCCEEDED"
    for index in range(9):
        assert (
            _run(arrival, "record_note", {"note": f"Rotation {index}"})["status"]
            == "SUCCEEDED"
        )
    exported = _run(arrival, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    directory = Path(exported["result"]["receipt"]["path"])
    verify_export(directory)
    value = json.loads(
        (directory / "attachment-source-qualification-data.json").read_text()
    )
    assert value["schema"] == "rocell.wizard_source_qualification_export.v2"
    assert (
        value["original_bytes_preserved"]
        is value["source_qualification_original_bytes_preserved"]
        is True
    )
    assert value["static_camera_onboarding"]["original_bytes_preserved"] is True
    for key, original in previous.retained_diagnostics().items():
        if key not in {"schema", "meaning"}:
            assert value[key] == original
    for key, original in owner.retained_diagnostics().items():
        assert value["static_camera_onboarding"][key] == original
    assert len(list(directory.glob("attachment-*"))) <= 8


@pytest.mark.parametrize("family", ["source", "static"])
def test_reserved_export_tracks_each_family_redaction_independently(
    static_join, family
):
    arrival, _, _, owner, previous, _ = static_join
    changed = previous if family == "source" else owner
    changed.history["private_note"] = "password=modeled-private-original"
    before = changed.retained_diagnostics()
    exported = _run(arrival, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    directory = Path(exported["result"]["receipt"]["path"])
    verify_export(directory)
    packet = json.loads(
        (directory / "attachment-source-qualification-data.json").read_text()
    )
    assert packet["original_bytes_preserved"] is False
    assert packet["publication"]["status"] == "HISTORICAL_HELD"
    assert packet["source_qualification_original_bytes_preserved"] == (
        family != "source"
    )
    assert packet["static_camera_onboarding"]["original_bytes_preserved"] == (
        family != "static"
    )
    assert "modeled-private-original" not in json.dumps(packet)
    assert changed.retained_diagnostics() == before


def test_execute_intent_log_failure_never_calls_static_service(
    static_join, monkeypatch
):
    arrival, runner, _, owner, _, _ = static_join
    ticket = _ticket(arrival, NAMES[0], values(NAMES[0]))
    append = arrival._log.append

    def fail(name, detail):
        if name == "ACTION_EXECUTED":
            raise OSError("Modeled intent-log failure")
        return append(name, detail)

    monkeypatch.setattr(arrival._log, "append", fail)
    dispatched = arrival.execute_action(ticket["ticket_id"])
    result = _complete(arrival, dispatched["operation_id"])
    assert result["status"] == "FAILED"
    assert (
        NAMES[0] not in owner.calls
        and "publish" not in owner.calls
        and not runner.calls
    )
    assert (
        arrival.view()["static_camera_onboarding"]["publication"]["status"]
        == "HISTORICAL_HELD"
    )


def test_after_log_publication_exception_withdraws_both_owners(
    static_join, monkeypatch
):
    arrival, runner, _, owner, _, _ = static_join
    original = owner.retained_diagnostics()
    monkeypatch.setattr(
        owner,
        "publication_completed",
        lambda *_: (_ for _ in ()).throw(
            RuntimeError("Modeled late cache adoption failure")
        ),
    )
    result = _run(arrival, NAMES[0], values(NAMES[0]))
    assert result["status"] == "FAILED"
    assert owner.retained_diagnostics() == original
    assert (
        arrival.view()["static_camera_onboarding"]["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    assert (
        arrival._physical_camera_setup.view()["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    assert not runner.calls
