"""Actual Arrival/tickets/log/export with an injected qualification service.

All qualification/isolation/storage subjects are explicitly modeled. No ownership
child, device, M1 initialization or inbox discovery is executed by these tests.
"""

from copy import deepcopy
import json
from pathlib import Path

import pytest

from rocell.application.wizard_actions import ACTION_BY_ID, WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import (
    make_service,
    _complete,
    _run,
    _ticket,
)  # noqa: F401
from test_arrival_wizard_intake_evidence import worker
from test_wizard_physical_camera_setup_ui import (
    complete_setup,
    prerequisite_summary,
)  # noqa: F401
from test_wizard_source_reassessment_ui import fixture_view
from test_wizard_workspace_source_ui import render_snapshot


NAMES = (
    "physical_source_isolation_files_discover",
    "physical_source_qualify",
    "physical_source_qualification_review",
    "physical_static_contract_begin",
)


class QualificationDouble:
    def __init__(self, arrival, view):
        self.arrival, self.data = arrival, view
        self.calls = []
        self.context = "c" * 64
        self.after = lambda **kwargs: None
        self.bad_validation = False
        self.history = {
            "qualification_1_receipt": {
                "schema": "MODELED_RECEIPT",
                "receipt_sha256": "4" * 64,
            },
            "qualification_1_assessment": {
                "schema": "MODELED_ASSESSMENT",
                "assessment_sha256": "5" * 64,
            },
            "physical_authority": False,
        }

    def view(self):
        return deepcopy(self.data)

    def retained_diagnostics(self):
        return deepcopy(self.history)

    def context_sha256(self):
        return self.context

    def blocked_reason(self, action_id):
        return None

    def fields(self, action_id):
        consent = {
            "name": "file_only",
            "type": "checkbox",
            "required": True,
            "default": False,
            "label": "Original evidence work only; no device release",
        }
        actor = lambda name: {
            "name": name,
            "type": "text",
            "required": True,
            "default": "",
            "max_length": 64,
            "label": name,
        }
        if action_id == NAMES[0]:
            return []
        if action_id == NAMES[1]:
            return [
                actor("operator_id"),
                {
                    "name": "isolation_state",
                    "type": "select",
                    "required": True,
                    "default": "UNKNOWN",
                    "label": "Recorded isolation",
                    "options": [
                        {"value": value, "label": value}
                        for value in ("UNKNOWN", "OBSERVED_DISCONNECTED")
                    ],
                },
                {
                    "name": "isolation_statement",
                    "type": "text",
                    "required": False,
                    "default": "",
                    "max_length": 512,
                    "label": "Exact isolation statement",
                },
                {
                    "name": "isolation_choice",
                    "type": "select",
                    "required": False,
                    "default": "",
                    "label": "Original attachment",
                    "options": [
                        {"value": "", "label": "No original selected"},
                        {"value": "intake-file-" + "1" * 32, "label": "modeled.txt"},
                    ],
                },
                consent,
            ]
        return [actor("reviewer_id"), consent] if action_id == NAMES[2] else [consent]

    def observe_setup(self):
        self.calls.append("observe_setup")

    def invalidate(self):
        self.calls.append("invalidate")
        self.data.update(status="HISTORICAL_HELD", next_action=None)
        self.data["publication"] = {"status": "HISTORICAL_HELD", "operation_id": None}

    def perform(self, action_id, values, **kwargs):
        assert not self.arrival._lock._is_owned()
        assert self.arrival._test_setup["publication"]["status"] == "CURRENT"
        assert not any(key.startswith("_") for key in values)
        self.calls.append(action_id)
        if kwargs["expected_context_sha256"] != self.context:
            raise WizardError(
                "SOURCE_QUALIFICATION_CONTEXT_CHANGED", "Modeled stale subject refusal"
            )
        self.expected_result = worker(
            action_id, {"qualification": deepcopy(self.data["qualification"])}
        )
        self.data["publication"]["status"] = "PENDING"
        self.arrival._test_setup["publication"]["status"] = "PENDING"
        self.after(values=values, **kwargs)
        return deepcopy(self.expected_result)

    def validate_publication(self, result):
        self.calls.append("validate")
        if self.bad_validation or result != self.expected_result:
            raise WizardError(
                "SOURCE_QUALIFICATION_RESULT_CHANGED",
                "Modeled exact retained result refusal",
            )

    def publication_completed(self, operation_id):
        assert self.arrival.operation(operation_id)["completion_log_persisted"]
        assert self.arrival._test_setup["publication"]["status"] == "CURRENT"
        self.calls.append("publish")
        self.data["publication"] = {"status": "CURRENT", "operation_id": operation_id}


@pytest.fixture
def joined(make_service, monkeypatch, complete_setup):
    arrival, runner, source = make_service(mode="physical")
    full = fixture_view(complete_setup)
    setup = full["physical_camera_setup"]
    setup["schema"] = "rocell.wizard_physical_camera_setup.v3"
    setup["configuration_records"] = deepcopy(
        arrival._physical_camera_setup.view()["configuration_records"]
    )
    setup["launch_session_id"] = arrival.session_id
    setup["requirements_provenance"] = "REOPENED_ORIGINAL_CONTEXT"
    setup["reopening"]["current_launch_id"] = arrival.session_id
    arrival._test_setup = setup
    monkeypatch.setattr(arrival._physical_camera_setup, "view", lambda: deepcopy(setup))
    monkeypatch.setattr(
        arrival._physical_camera_setup,
        "invalidate",
        lambda: setup["publication"].update(status="HISTORICAL_HELD"),
    )
    monkeypatch.setattr(
        arrival._physical_camera_setup,
        "publication_completed",
        lambda operation_id: setup["publication"].update(
            status="CURRENT", operation_id=operation_id
        ),
    )
    data = full["source_reassessment"]
    data["launch_session_id"] = arrival.session_id
    qualification = QualificationDouble(arrival, data)
    arrival._source_qualification = qualification
    observations = []
    monkeypatch.setattr(
        arrival._physical_intake_evidence,
        "observe_setup",
        lambda: observations.append("observe_setup"),
    )
    return arrival, runner, source, qualification, observations


def values(name):
    return {
        NAMES[0]: {},
        NAMES[1]: {"operator_id": "source_operator", "file_only": True},
        NAMES[2]: {"reviewer_id": "another_reviewer", "file_only": True},
        NAMES[3]: {"file_only": True},
    }[name]


def test_catalog_cached_fields_and_preview_do_not_execute_qualification(joined):
    arrival, runner, source, owner, _ = joined
    reads = source["calls"]
    view = arrival.view()
    assert source["calls"] == reads and not owner.calls and not runner.calls
    for name, timeout in zip(NAMES, (60, 300, 120, 120)):
        definition = ACTION_BY_ID[name]
        assert (
            definition.worker == "physical_source_qualification"
            and definition.mode == "physical"
            and definition.timeout_s == timeout
        )
        assert not definition.view(mode="rehearsal", busy=False)["enabled"]
        ticket = _ticket(arrival, name, values(name))
        assert "_source_qualification_context_sha256" not in ticket["input"]
        assert "No device is opened" in " ".join(ticket["effects"])
    fields = next(
        action["fields"]
        for action in view["actions"]
        if action["action_id"] == NAMES[1]
    )
    assert (
        next(field for field in fields if field["name"] == "isolation_state")["default"]
        == "UNKNOWN"
    )
    assert (
        next(field for field in fields if field["name"] == "isolation_choice")[
            "default"
        ]
        == ""
    )
    assert not runner.calls and not owner.calls


@pytest.mark.parametrize("name", NAMES)
def test_one_dispatch_exact_validation_then_log_publication_and_no_replay(joined, name):
    arrival, runner, _, owner, observations = joined
    ticket = _ticket(arrival, name, values(name))
    first = arrival.execute_action(ticket["ticket_id"])
    result = _complete(arrival, first["operation_id"])
    assert result["status"] == "SUCCEEDED", result
    assert owner.calls == [name, "validate", "publish"]
    assert observations == ["observe_setup"]
    assert (
        arrival.execute_action(ticket["ticket_id"])["operation_id"]
        == first["operation_id"]
    )
    assert owner.calls.count(name) == 1 and not runner.calls
    view = arrival.view()
    assert view["source_reassessment"]["publication"]["status"] == "CURRENT"
    assert view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED"


@pytest.mark.parametrize(
    "change",
    [
        {"isolation_statement": "é" * 257},
        {"isolation_statement": "two\nlines"},
        {"isolation_statement": " leading"},
        {"isolation_state": "OBSERVED_DISCONNECTED"},
        {"isolation_choice": "arbitrary-path"},
        {"operator_id": "operator name"},
        {"qualification_sha256": "a" * 64},
        {"physical_authority": True},
    ],
)
def test_source_intake_rejects_unbounded_or_unbound_semantic_fields(joined, change):
    arrival, runner, _, owner, _ = joined
    with pytest.raises(WizardError):
        _ticket(arrival, NAMES[1], {**values(NAMES[1]), **change})
    assert not owner.calls and not runner.calls


def test_same_reviewer_label_is_rejected_before_worker(joined):
    arrival, _, _, owner, _ = joined
    with pytest.raises(WizardError, match="distinct"):
        _ticket(
            arrival, NAMES[2], {**values(NAMES[2]), "reviewer_id": "SOURCE_OPERATOR"}
        )
    assert not owner.calls


def test_pending_view_withholds_inner_completed_subject_without_context_mutation(
    joined,
):
    arrival, runner, source, owner, _ = joined
    original = owner.view()
    arrival._running = "in-flight"
    arrival._operations["in-flight"] = {
        "operation_id": "in-flight",
        "action_id": NAMES[1],
        "status": "RUNNING",
    }
    try:
        reads = source["calls"]
        current = arrival.view()["source_reassessment"]
        assert (
            current["publication"]["status"] == "PENDING"
            and current["qualification"] is None
            and current["next_action"] is None
        )
        assert (
            owner.view() == original
            and not owner.calls
            and not runner.calls
            and source["calls"] == reads
        )
    finally:
        arrival._running = None


@pytest.mark.parametrize("fault", ["stop", "source", "log", "validation", "exception"])
def test_late_failure_keeps_original_diagnostics_but_no_current_subject(
    joined, monkeypatch, fault
):
    arrival, runner, source, owner, _ = joined
    if fault == "log":
        append = arrival._log.append

        def fail(name, details):
            if name == "ACTION_FINISHED":
                raise OSError("Modeled completion log failure")
            return append(name, details)

        monkeypatch.setattr(arrival._log, "append", fail)
    if fault == "validation":
        owner.bad_validation = True

    def after(**kwargs):
        if fault == "stop":
            kwargs["cancellation"].set()
        elif fault == "source":
            source["hash"] = "f" * 64
        elif fault == "exception":
            raise RuntimeError("Modeled late retained-service failure")

    owner.after = after
    saved = owner.retained_diagnostics()
    result = _run(arrival, NAMES[1], values(NAMES[1]))
    assert result["status"] == ("SUCCEEDED" if fault == "stop" else "FAILED"), result
    assert "publish" not in owner.calls
    assert (
        arrival.view()["source_reassessment"]["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    assert (
        arrival._physical_camera_setup.view()["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    assert (
        owner.retained_diagnostics() == saved
        and owner.calls.count(NAMES[1]) == 1
        and not runner.calls
    )


def test_stale_context_does_not_fallback_or_replay(joined):
    arrival, runner, _, owner, _ = joined
    ticket = _ticket(arrival, NAMES[1], values(NAMES[1]))
    owner.context = "d" * 64
    receipt = arrival.execute_action(ticket["ticket_id"])
    result = _complete(arrival, receipt["operation_id"])
    assert result["status"] == "FAILED" and "publish" not in owner.calls
    assert owner.calls.count(NAMES[1]) == 1 and not runner.calls


def test_execute_log_failure_never_enters_qualification_or_replays(joined, monkeypatch):
    arrival, runner, _, owner, _ = joined
    ticket = _ticket(arrival, NAMES[1], values(NAMES[1]))
    append = arrival._log.append

    def fail(name, details):
        if name == "ACTION_EXECUTED":
            raise OSError("Modeled intent log failure")
        return append(name, details)

    monkeypatch.setattr(arrival._log, "append", fail)
    receipt = arrival.execute_action(ticket["ticket_id"])
    completed = _complete(arrival, receipt["operation_id"])
    assert completed["status"] == "FAILED"
    assert NAMES[1] not in owner.calls and "publish" not in owner.calls
    assert not runner.calls
    assert (
        arrival.view()["source_reassessment"]["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    with pytest.raises(WizardError):
        _ticket(arrival, NAMES[1], values(NAMES[1]))


def test_redacted_worker_subject_never_publishes_or_fakes_exact_retention(joined):
    arrival, runner, _, owner, _ = joined
    original = owner.retained_diagnostics()

    def after(**kwargs):
        owner.expected_result["steps"][0]["report"][
            "credential"
        ] = "password=modeled-secret"

    owner.after = after
    result = _run(arrival, NAMES[1], values(NAMES[1]))
    assert result["status"] == "FAILED", result
    assert "publish" not in owner.calls and not runner.calls
    assert owner.retained_diagnostics() == original
    assert (
        arrival.view()["source_reassessment"]["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    assert "modeled-secret" not in json.dumps(result)


def test_reserved_metadata_export_survives_result_eviction_without_original_bytes(
    joined,
):
    arrival, runner, _, owner, _ = joined
    assert _run(arrival, NAMES[1], values(NAMES[1]))["status"] == "SUCCEEDED"
    for index in range(9):
        assert (
            _run(
                arrival,
                "record_note",
                {"note": f"Source qualification rotation {index}"},
            )["status"]
            == "SUCCEEDED"
        )
    exported = _run(arrival, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    directory = Path(exported["result"]["receipt"]["path"])
    verify_export(directory)
    attachment = json.loads(
        (directory / "attachment-source-qualification-data.json").read_text(
            encoding="utf-8"
        )
    )
    assert attachment["schema"] == "rocell.wizard_source_qualification_export.v1"
    assert attachment["original_bytes_preserved"] is True
    for key, value in owner.retained_diagnostics().items():
        assert attachment[key] == value
    assert (
        attachment["physical_authority"] is False
        and attachment["hardware_qualified"] is False
    )
    assert (
        "raw_bytes" not in attachment
        and "base64" not in attachment
        and not runner.calls
    )
