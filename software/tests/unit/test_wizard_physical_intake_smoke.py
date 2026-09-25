"""Script checks with real pure intake records and ordinary diagnostic exports.

No M1 qualification, process, inventory, serial, camera or device access. The
full public file-only M1 flow is an explicit separately source-bound smoke.
"""

from copy import deepcopy
import importlib.util
from pathlib import Path
import sys

import pytest

from rocell.application.physical_intake_notebook import PhysicalIntakeNotebook
from rocell.application.wizard_diagnostic_export import WizardDiagnosticExporter
from test_physical_camera_prerequisites import collect, workspace  # noqa: F401


SCRIPTS = Path(__file__).resolve().parents[2] / "scripts"
LAUNCH = "intake-script-fixture-launch"


@pytest.fixture
def smoke():
    spec = importlib.util.spec_from_file_location(
        "physical_intake_smoke_under_test",
        SCRIPTS / "wizard_physical_intake_smoke.py",
    )
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


@pytest.fixture
def notebook(smoke, workspace):
    prerequisites = collect(workspace)
    initial = PhysicalIntakeNotebook.start(prerequisites, launch_session_id=LAUNCH)
    current = initial.record(**smoke.UNKNOWN_NOTE, recorded_at_ns=123456789)
    return prerequisites, initial, current


class ActionService:
    """One terminal operation; deliberately no real application/store methods."""

    def __init__(self, smoke, **changes):
        result = {
            "physical_authority": False,
            "metadata_inventory_performed": False,
            **{name: 0 for name in smoke.ZERO_COUNTERS},
        }
        self.outcome = {
            "operation_id": "fixture-operation",
            "status": "SUCCEEDED",
            "result_sha256": "b" * 64,
            "completion_log_persisted": True,
            "result": result,
            **changes,
        }
        self.calls = []

    def view(self):
        return {"revision": 7}

    def prepare_action(self, name, values, revision):
        self.calls.append(("prepare", name, deepcopy(values), revision))
        return {"effects": ["NO_DEVICE_IO"], "ticket_id": "fixture-ticket"}

    def execute_action(self, ticket):
        self.calls.append(("execute", ticket))
        return {"operation_id": "fixture-operation"}

    def operation(self, operation_id):
        self.calls.append(("operation", operation_id))
        return deepcopy(self.outcome)


@pytest.mark.parametrize(
    "action_id",
    ["physical_camera_probe", "native_camera_inventory", "arm_connect", "execute_task"],
)
def test_closed_no_device_action_set_refuses_before_preparation(smoke, action_id):
    service = ActionService(smoke)
    with pytest.raises(RuntimeError, match="closed no-device"):
        smoke.action(service, action_id)
    assert service.calls == []


def test_unknown_note_uses_exact_fields_once(smoke):
    service = ActionService(smoke)
    outcome = smoke.action(service, "physical_intake_record", smoke.UNKNOWN_NOTE)
    assert outcome == service.outcome
    assert service.calls == [
        ("prepare", "physical_intake_record", smoke.UNKNOWN_NOTE, 7),
        ("execute", "fixture-ticket"),
        ("operation", "fixture-operation"),
    ]


@pytest.mark.parametrize("count", [1, False, None])
def test_nonzero_missing_or_boolean_effect_counter_cannot_pass(smoke, count):
    service = ActionService(smoke)
    service.outcome["result"]["device_open_count"] = count
    with pytest.raises(RuntimeError, match="effect count"):
        smoke.action(service, "physical_intake_start")
    assert len([call for call in service.calls if call[0] == "execute"]) == 1


@pytest.mark.parametrize("failure", ["FAILED", "CANCELLED", "TIMED_OUT", "LOG"])
def test_terminal_failure_or_unretained_completion_has_no_retry(smoke, failure):
    service = ActionService(smoke)
    if failure == "LOG":
        service.outcome["completion_log_persisted"] = False
    else:
        service.outcome["status"] = failure
    with pytest.raises(RuntimeError):
        smoke.action(service, "physical_intake_record", smoke.UNKNOWN_NOTE)
    assert len([call for call in service.calls if call[0] == "prepare"]) == 1
    assert len([call for call in service.calls if call[0] == "execute"]) == 1


def test_main_source_mismatch_does_not_construct_application(smoke, monkeypatch):
    monkeypatch.setattr(
        sys, "argv", ["intake-smoke", "--expected-source-sha256", "a" * 64]
    )
    monkeypatch.setattr(smoke, "source_fingerprint", lambda _: "b" * 64)
    monkeypatch.setattr(
        smoke,
        "ArrivalWizardService",
        lambda *_args, **_kwargs: pytest.fail("Source mismatch must precede launch"),
    )
    with pytest.raises(RuntimeError, match="Freeze mismatch before launch"):
        smoke.main()


def test_actual_notebook_verifies_unknown_without_changing_original(smoke, notebook):
    prerequisites, initial, current = notebook
    original = prerequisites.payload
    for record in (initial, current):
        verified = smoke.verify_snapshot(
            record.view(), prerequisites=prerequisites, launch_id=LAUNCH
        )
        assert verified.payload == record.payload
    assert current.to_dict()["coverage"] == {
        "total": 16,
        "observed": 0,
        "unknown": 1,
        "unrecorded": 15,
    }
    assert current.to_dict()["previous_sha256"] == initial.sha256
    assert prerequisites.payload == original


@pytest.mark.parametrize(
    "fault", ["hash", "launch", "requirements", "row", "authority"]
)
def test_changed_notebook_binding_or_content_is_rejected(smoke, notebook, fault):
    prerequisites, _, current = notebook
    snapshot = current.view()
    launch = LAUNCH
    if fault == "hash":
        snapshot["snapshot_sha256"] = "b" * 64
    elif fault == "launch":
        launch = "other-launch"
    elif fault == "requirements":
        snapshot["binding"]["prerequisites_sha256"] = "c" * 64
    elif fault == "row":
        snapshot["rows"][0]["observation"]["observed_value"] = "changed after hash"
    else:
        snapshot["physical_authority"] = True
    with pytest.raises((ValueError, RuntimeError)):
        smoke.verify_snapshot(snapshot, prerequisites=prerequisites, launch_id=launch)


def exported(smoke, workspace, notebook, *, include=True):
    prerequisites, _, current = notebook
    assigned = workspace / "software/runs/wizard-exports"
    assigned.parent.mkdir(parents=True, exist_ok=True)
    exporter = WizardDiagnosticExporter(assigned)
    exporter.prepare(create=True)
    wrapper = {
        "schema": "rocell.physical_intake_export.v1",
        "status": "CURRENT_DRAFT",
        "notebook": current.view(),
        "physical_authority": False,
        "hardware_qualified": False,
        "meaning": "Original last published draft snapshot; not an accepted receipt, verified attachment or restored physical readiness.",
    }
    receipt = exporter.export(
        {
            "session_id": LAUNCH,
            "mode": "PHYSICAL",
            "source_binding_sha256": "a" * 64,
            "source_identity": {"build": "ordinary-export-unit-fixture"},
            "physical_authority": "NONE",
        },
        [],
        attachments=(
            {"physical-intake-notebook.json": smoke.canonical(wrapper)}
            if include
            else {}
        ),
    )
    return receipt, prerequisites, current


def test_actual_export_verifies_full_snapshot_and_manifest(smoke, workspace, notebook):
    receipt, prerequisites, current = exported(smoke, workspace, notebook)
    checked = smoke.verify_notebook_export(
        receipt,
        workspace=workspace,
        expected_snapshot=current.view(),
        prerequisites=prerequisites,
        launch_id=LAUNCH,
    )
    assert checked["manifest_sha256"] == receipt["manifest_sha256"]
    assert checked["attachment"] == smoke.NOTEBOOK_ATTACHMENT
    assert 0 < checked["attachment_bytes"] < 128 * 1024


@pytest.mark.parametrize("fault", ["missing", "snapshot", "receipt", "assigned"])
def test_export_refuses_missing_changed_or_unassigned_snapshot(
    smoke, workspace, notebook, fault
):
    receipt, prerequisites, current = exported(
        smoke, workspace, notebook, include=fault != "missing"
    )
    snapshot = current.view()
    if fault == "snapshot":
        snapshot["revision"] = 2
    elif fault == "receipt":
        receipt["manifest_sha256"] = "b" * 64
    selected = workspace / "other-workspace" if fault == "assigned" else workspace
    with pytest.raises(RuntimeError):
        smoke.verify_notebook_export(
            receipt,
            workspace=selected,
            expected_snapshot=snapshot,
            prerequisites=prerequisites,
            launch_id=LAUNCH,
        )
