"""Arrival publication/export joins with an explicitly injected file service.

Actual intake codecs supply immutable documents; storage, file discovery and
retention are modeled. No M1, inbox, native metadata, process or device runs.
"""

from copy import deepcopy
import json
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.application.wizard_actions import ACTION_BY_ID, WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import make_service, _run, _ticket, _complete
from test_physical_intake_submission import intake_fixture
from test_wizard_physical_intake_evidence_ui import fixture_view
from test_wizard_workspace_source_ui import browser
from test_arrival_wizard_device_selection_ui import MetadataService, selection
import test_arrival_wizard_device_selection_ui as dom
from test_arrival_wizard_terminal import run as terminal_run


NAMES = (
    "physical_intake_files_discover",
    "physical_intake_submit",
    "physical_intake_review",
    "physical_intake_export_originals",
)


def worker(action_id, report):
    return {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": action_id,
        "status": "SUCCEEDED",
        "steps": [{"name": action_id, "exit_code": 0, "report": report}],
        "device_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
        "metadata_inventory_performed": False,
        "physical_authority": False,
    }


class EvidenceDouble:
    def __init__(self, arrival, data, produced):
        self.arrival, self.data, self.produced = arrival, data, produced
        self.context = "f" * 64
        self.calls = []
        self.after = lambda **kwargs: None
        self.history = {
            "schema": "rocell.wizard_physical_intake_evidence_diagnostics.v1",
            "original_context": deepcopy(data["original_context"]),
            "publication": deepcopy(data["publication"]),
            "collections": [],
            "attempt": None,
            "private_original_export": None,
            **{
                f"collection_1_{role}": getattr(produced, role).to_dict()
                for role in ("submission", "assessment", "review")
            },
            "physical_authority": False,
            "hardware_qualified": False,
            "meaning": "Modeled original retention; real pure documents, no raw media.",
        }

    def view(self):
        return deepcopy(self.data)

    def retained_diagnostics(self):
        return deepcopy(self.history)

    def blocked_reason(self, action_id, notebook):
        return None

    def context_sha256(self, notebook):
        return self.context

    def submission_fields(self, notebook):
        return tuple(
            {
                "name": "attachment_" + row["record_id"],
                "label": row["record_id"] + " original attachment",
                "type": "select",
                "required": False,
                "default": "",
                "options": [
                    {"value": "", "label": "No attachment (UNKNOWN only)"},
                    {"value": "intake-file-" + "1" * 32, "label": "modeled.txt"},
                ],
            }
            for row in self.produced.submission.safe_summary()["rows"]
        )

    def invalidate(self):
        self.calls.append("invalidate")
        self.data["status"] = "HISTORICAL_HELD"
        self.data["publication"] = {"status": "HISTORICAL_HELD", "operation_id": None}

    def observe_setup(self):
        self.calls.append("observe_setup")

    def publication_completed(self, operation_id):
        assert self.arrival.operation(operation_id)["completion_log_persisted"]
        self.calls.append("publish")
        self.data["publication"] = {"status": "CURRENT", "operation_id": operation_id}

    def perform(self, action_id, **kwargs):
        assert not self.arrival._lock._is_owned()
        assert (
            self.arrival._physical_camera_setup.view()["publication"]["status"]
            == "CURRENT"
        )
        self.calls.append(action_id)
        if kwargs["expected_context_sha256"] != self.context:
            raise WizardError("INTAKE_CONTEXT_CHANGED", "Modeled exact-context refusal")
        assert kwargs["export_parent"] == self.arrival.export_directory
        assert "_intake_evidence_context_sha256" not in kwargs["values"]
        report = {
            "submission": self.produced.submission.safe_summary(),
            "assessment": self.produced.assessment.safe_summary(),
            "review": self.produced.review.safe_summary(),
        }
        self.after(**kwargs)
        self.data["publication"]["status"] = "PENDING"
        if action_id != "physical_intake_files_discover":
            self.arrival._test_setup["publication"]["status"] = "PENDING"
        return worker(action_id, report)


@pytest.fixture
def joined(make_service, monkeypatch, tmp_path):
    service, runner, source = make_service(mode="physical")
    produced = intake_fixture()
    view = fixture_view(tmp_path, produced, "REVIEW_PENDING")
    setup = view["physical_camera_setup"]
    setup["launch_session_id"] = service.session_id
    setup["requirements_provenance"] = "REOPENED_ORIGINAL_CONTEXT"
    setup["reopening"]["current_launch_id"] = service.session_id
    service._test_setup = setup
    monkeypatch.setattr(service._physical_camera_setup, "view", lambda: deepcopy(setup))
    monkeypatch.setattr(
        service._physical_camera_setup,
        "invalidate",
        lambda: setup["publication"].update(status="HISTORICAL_HELD"),
    )
    monkeypatch.setattr(
        service._physical_camera_setup,
        "publication_completed",
        lambda operation_id: setup["publication"].update(
            status="CURRENT", operation_id=operation_id
        ),
    )
    data = view["physical_intake_evidence"]
    data["launch_session_id"] = service.session_id
    data["discovery"]["launch_session_id"] = service.session_id
    evidence = EvidenceDouble(service, data, produced)
    service._physical_intake_evidence = evidence
    return service, runner, source, evidence


def values(name):
    return (
        {
            "physical_intake_files_discover": {},
            "physical_intake_submit": {"operator_id": "Operator_A", "file_only": True},
            "physical_intake_review": {
                "reviewer_id": "Reviewer_B",
                "decision": "ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW",
                "file_only": True,
            },
            "physical_intake_export_originals": {
                "include_private_originals": True,
                "file_only": True,
            },
        }
    )[name]


def test_catalog_is_physical_only_no_paths_uploads_or_defaults(joined):
    service, runner, source, evidence = joined
    reads = source["calls"]
    view = service.view()
    assert source["calls"] == reads and not runner.calls and not evidence.calls
    for name in NAMES:
        assert ACTION_BY_ID[name].worker == "physical_intake_evidence"
        assert ACTION_BY_ID[name].mode == "physical"
        ticket = _ticket(service, name, values(name))
        assert not evidence.calls and not runner.calls
        assert "Original source assessment remains BLOCKED" in " ".join(
            ticket["effects"]
        )
        assert "_intake_evidence_context_sha256" not in ticket["input"]
    action = next(
        x for x in view["actions"] if x["action_id"] == "physical_intake_submit"
    )
    assert len(action["fields"]) == 18
    assert all(x["default"] == "" for x in action["fields"][:16])
    assert not {"path", "base64", "bytes", "directory"}.intersection(
        x["name"] for x in action["fields"]
    )


@pytest.mark.parametrize("name", NAMES)
def test_once_only_dispatch_publishes_after_logging_without_invalidate_before_entry(
    joined, name
):
    service, runner, _, evidence = joined
    ticket = _ticket(service, name, values(name))
    receipt = service.execute_action(ticket["ticket_id"])
    outcome = _complete(service, receipt["operation_id"])
    assert outcome["status"] == "SUCCEEDED", outcome
    assert evidence.calls == [name, "publish"]
    assert (
        service.execute_action(ticket["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    assert evidence.calls.count(name) == 1 and not runner.calls
    assert (
        service.view()["physical_intake_evidence"]["publication"]["status"] == "CURRENT"
    )
    assert (
        service.view()["camera"]["status"]
        == service.view()["arm"]["status"]
        == "NOT_CONNECTED"
    )


def test_cached_pending_view_hides_inner_complete_subject_before_worker_publication(
    joined,
):
    service, _, source, evidence = joined
    service._running = "modeled-running"
    service._operations[service._running] = {
        "operation_id": service._running,
        "action_id": "physical_intake_submit",
    }
    reads = source["calls"]
    value = service._physical_intake_evidence_view()
    assert value["publication"]["status"] == "PENDING"
    assert value["collection"] is None and value["discovery"]["files"] == []
    assert source["calls"] == reads and not evidence.calls
    service._running = None
    service._operations.clear()


@pytest.mark.parametrize("failure", ["stop", "source", "log", "redaction", "throw"])
def test_late_failure_holds_original_metadata_without_replay(
    joined, monkeypatch, failure
):
    service, runner, source, evidence = joined
    original = deepcopy(evidence.history)
    if failure == "stop":
        evidence.after = lambda **kwargs: kwargs["cancellation"].set()
    if failure == "source":
        evidence.after = lambda **kwargs: source.update(hash="b" * 64)
    if failure == "throw":

        def thrown(**kwargs):
            raise WizardError(
                "INJECTED_LATE_ERROR", "Modeled retention completed before failure"
            )

        evidence.after = thrown
    if failure == "log":
        append = service._append_event
        monkeypatch.setattr(
            service,
            "_append_event",
            lambda kind, details: (
                False if kind == "ACTION_FINISHED" else append(kind, details)
            ),
        )
    if failure == "redaction":
        validate = service._validated_result

        def redacted(action_id, result):
            clean = validate(action_id, result)
            clean["steps"][0]["report"]["redacted_test_marker"] = True
            return clean

        monkeypatch.setattr(service, "_validated_result", redacted)
    outcome = _run(service, "physical_intake_submit", values("physical_intake_submit"))
    assert outcome["status"] in (
        {"SUCCEEDED"} if failure == "stop" else {"FAILED"}
    ), outcome
    assert "publish" not in evidence.calls
    assert evidence.calls.count("physical_intake_submit") == 1 and not runner.calls
    assert (
        service.view()["physical_intake_evidence"]["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    assert evidence.history == original


def test_context_change_refuses_worker_without_automatic_new_preview(joined):
    service, _, _, evidence = joined
    ticket = _ticket(
        service, "physical_intake_submit", values("physical_intake_submit")
    )
    evidence.context = "e" * 64
    receipt = service.execute_action(ticket["ticket_id"])
    outcome = _complete(service, receipt["operation_id"])
    assert outcome["status"] == "FAILED"
    assert "publish" not in evidence.calls
    assert outcome["result"]["code"] == "INTAKE_CONTEXT_CHANGED"


@pytest.mark.parametrize("name", NAMES[1:])
def test_no_missing_or_coerced_consent_is_admitted(joined, name):
    service = joined[0]
    for consent in (None, False, 1, "true"):
        with pytest.raises(WizardError):
            _ticket(service, name, {**values(name), "file_only": consent})
    if name == "physical_intake_export_originals":
        with pytest.raises(WizardError):
            _ticket(
                service, name, {"file_only": True, "include_private_originals": False}
            )


def test_exact_review_distinct_labels_and_closed_decision(joined):
    service = joined[0]
    for changes in (
        {"reviewer_id": "operator_a"},
        {"decision": "PASS"},
        {"path": "C:/private.txt"},
    ):
        with pytest.raises(WizardError):
            _ticket(
                service,
                "physical_intake_review",
                {**values("physical_intake_review"), **changes},
            )


def test_actual_batch_fields_browser_and_terminal_prepare_only(joined):
    service, _, _, evidence = joined
    view = service.view()
    fields = {
        "attachment_" + row["record_id"]: ""
        for row in evidence.produced.submission.safe_summary()["rows"]
    }
    fields.update(operator_id="Operator_A", file_only=True)
    # The older harness locates forms by a humanized ID. Keep the actual
    # production action label and change only this test's locator seam.
    with pytest.MonkeyPatch.context() as patch:
        patch.setattr(
            dom,
            "_HARNESS",
            dom._HARNESS.replace(
                "child.textContent===input.action.replaceAll('_',' ')",
                "child.textContent===input.snapshot.actions.find(action=>action.action_id===input.action).label",
            ),
        )
        page = browser(
            selection(),
            "camera",
            snapshot=view,
            prepare=True,
            action="physical_intake_submit",
            values=fields,
        )
    assert [x["path"] for x in page["requests"]] == ["/api/view", "/api/prepare"]
    assert page["requests"][-1]["body"]["input"] == fields
    assert len(json.dumps(page["requests"][-1]["body"]).encode()) < 65536
    form = MetadataService(selection())
    form.view = lambda: deepcopy(view)
    code, output, _ = terminal_run(
        form, ["physical_intake_submit", *([""] * 16), "Operator_A", "yes", "", "quit"]
    )
    assert code == 0
    assert [x for x in form.calls if x[0] == "prepare"] == [
        ("prepare", "physical_intake_submit", fields, view["revision"])
    ]
    assert not any(x[0] == "execute" for x in form.calls)
    assert not evidence.calls


def test_successful_setup_completion_adopts_original_intake_once(joined, monkeypatch):
    service, _, _, evidence = joined
    setup = service._physical_camera_setup
    monkeypatch.setattr(setup, "blocked_reason", lambda _: None)
    monkeypatch.setattr(setup, "context_sha256", lambda *args: "f" * 64)
    monkeypatch.setattr(
        setup,
        "perform",
        lambda action_id, **kwargs: worker(action_id, {"modeled_audit": True}),
    )
    outcome = _run(service, "physical_camera_refresh", {"operator_id": "Operator_A"})
    assert outcome["status"] == "SUCCEEDED", outcome
    assert evidence.calls == ["observe_setup"]


def test_dedicated_full_metadata_survives_generic_eviction_and_export(joined):
    service, runner, _, evidence = joined
    outcome = _run(service, "physical_intake_submit", values("physical_intake_submit"))
    assert outcome["status"] == "SUCCEEDED"
    for i in range(9):
        assert (
            _run(service, "record_note", {"note": f"Modeled rotation note {i}"})[
                "status"
            ]
            == "SUCCEEDED"
        )
    assert service.operation(outcome["operation_id"])["result"] is None
    exported = _run(service, "export_logs")
    assert exported["status"] == "SUCCEEDED", exported
    path = Path(exported["result"]["receipt"]["path"])
    assert verify_export(path)["valid"]
    data = json.loads(
        (path / "attachment-intake-evidence.json").read_text(encoding="utf-8")
    )
    assert data["original_bytes_preserved"] is True
    for role in ("submission", "assessment", "review"):
        assert (
            data[f"collection_1_{role}"] == getattr(evidence.produced, role).to_dict()
        )
    assert "MODELED TEST ATTACHMENT; NOT HARDWARE EVIDENCE" not in json.dumps(data)
    assert not runner.calls
