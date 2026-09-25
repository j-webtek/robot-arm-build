"""Public wizard + real file-only writer/codecs; original store/facts MODELED.

This lane tests routing, one-use intent, current-owner guards and actual export
files. It does not authenticate an M1 history, qualify storage or open hardware.
Current metadata publication production is tested separately through real actions.
"""

from copy import deepcopy
import hashlib
import json
from pathlib import Path
from time import monotonic_ns

import pytest

from rocell.application import camera_probe_setup_service as writer
from rocell.application import physical_camera_setup_service as setup_impl
from rocell.application.arrival_wizard_service import _json_payload
from rocell.application.wizard_actions import (
    ACTION_BY_ID,
    WizardError,
    validate_action_input,
)
from rocell.application.wizard_diagnostic_export import (
    verify_export,
    sanitize_diagnostic_record,
)
from rocell.application.camera_probe_setup_export import restore_probe_setup_export
from test_arrival_wizard_service import make_service, _run, _ticket, _complete
from test_camera_probe_setup_service import modeled
from test_camera_mode_entry_queue import ready as entry_ready
from test_camera_probe_preparation_readback import current_enrollment, prepared_subject

VALUES = dict(operator_id="MODELED operator", file_only=True)
EXPORT = "physical_camera_probe_export"


@pytest.fixture
def joined(make_service, modeled, monkeypatch):
    app, runner, source = make_service(mode="physical")
    c = modeled
    setup = entry_ready(app)
    # The minimal predecessor is enough for the probe writer boundary, not a
    # full USB-history display. Full-history reader/UI composition has its own lane.
    monkeypatch.setattr(app._usb_identity, "observe_setup", lambda: None)
    original = deepcopy(setup._source_workflow)
    original.pop("usb_qualification_complete")
    original.update(c.original)
    original["configuration_epochs"] = None
    c.bound.clear()
    c.bound.update(setup.session.descriptor())
    c.original = original
    setup._source_workflow = deepcopy(original)
    setup.session._cached["stages"][4]["state"] = "WAITING_OPERATOR"
    previous = original["usb_qualification_reboot"]["enrollment"]["document"]
    current = current_enrollment(
        previous, source=app.source_sha256, launch=app.session_id
    )
    app._native_camera = current
    # Explicitly MODELED provenance for this writer-routing lane. Separate
    # public metadata tests prove the actual producer of this private receipt.
    snapshot = current.export_snapshot()
    ids = snapshot["binding_artifact"]["payload"]
    operations = {
        ids["generic_operation_id"]: "inventory_devices",
        ids["inventory_operation_id"]: "native_camera_inventory",
        ids["identity_operation_id"]: "native_camera_identity",
        "MODELED-native-review": "native_camera_review",
    }
    for op, action in operations.items():
        app._operations[op] = dict(
            operation_id=op,
            action_id=action,
            status="SUCCEEDED",
            completion_log_persisted=True,
            result_retention="MODELED_NOT_ORIGINAL",
            message="MODELED metadata provenance",
        )
    app._probe_metadata_publication = dict(
        enrollment_sha256=hashlib.sha256(_json_payload(snapshot)).hexdigest(),
        operations=operations,
    )
    # An entry projection needs the real closed display fields, but this
    # deliberately minimal routing fixture is not original-reader evidence.
    entry = original["camera_mode_entry"]["entry"]
    entry["document"] = dict(
        entry_id="cameramode-" + "1" * 32,
        operator_id="MODELED",
        binding=dict(
            session_id=c.bound["session_id"],
            cell_id=c.bound["cell_id"],
            origin_launch_id=c.bound["launch_id"],
            entry_launch_id=app.session_id,
            header_sha256="b" * 64,
            selected_identity_sha256="d" * 64,
            complete_review_sha256="e" * 64,
        ),
    )
    setup._source_workflow = deepcopy(original)
    software = prepared_subject(original, c.bound).to_dict()["software"]
    monkeypatch.setattr(
        writer,
        "verify_reviewed_activation_runtime",
        lambda candidate, **kw: deepcopy(software[candidate.to_dict()["purpose"]]),
    )
    monkeypatch.setattr(writer, "monotonic_ns", monotonic_ns)
    monkeypatch.setattr(setup_impl, "source_fingerprint", lambda _: source["hash"])
    monkeypatch.setattr(setup.session, "stage_transaction", c.session.stage_transaction)
    monkeypatch.setattr(setup.session, "refresh", c.session.refresh)
    after = c.session.read_original_source_workflow

    def readback(**kwargs):
        value = after(**kwargs)
        value["camera_probe_preparation"][
            "meaning"
        ] = "MODELED original readback; no hardware or storage qualification"
        return value

    monkeypatch.setattr(setup.session, "read_original_source_workflow", readback)
    commit = c.tx.commit_stage_state

    def commit_stage(stage, state, **kwargs):
        result = commit(stage, state, **kwargs)
        setup.session._cached["stages"][4]["state"] = state.value
        return result

    monkeypatch.setattr(c.tx, "commit_stage_state", commit_stage)
    adopt = setup._adopt_source_workflow

    def adopt_and_retain(value):
        adopt(value)
        c.original = deepcopy(value)

    monkeypatch.setattr(setup, "_adopt_source_workflow", adopt_and_retain)
    c.setup = setup
    c.app, c.runner, c.source_state = app, runner, source
    return c


def bundle(app):
    result = _run(app, EXPORT)
    assert result["status"] == "SUCCEEDED", result
    receipt = result["result"]["steps"][0]["report"]["receipt"]
    folder = Path(receipt["path"])
    assert folder.parent == app.export_directory
    assert verify_export(folder)["status"] == "VERIFIED_DIAGNOSTIC_EXPORT"
    snapshot = json.loads((folder / "report.json").read_bytes())["snapshot"]
    parts = {
        p.name[len("attachment-") :]: p.read_bytes()
        for p in folder.glob("attachment-*.json")
    }
    return restore_probe_setup_export(snapshot, parts)


def test_public_prepare_review_and_export_use_the_same_writer(joined):
    c, app = joined, joined.app
    before = deepcopy(c.original)
    ticket = _ticket(app, writer.PREPARE, VALUES)
    assert "No camera is opened" in " ".join(ticket["effects"])
    assert c.original == before and not c.setup._probe_queues
    receipt = app.execute_action(ticket["ticket_id"])
    prepared = _complete(app, receipt["operation_id"])
    assert prepared["status"] == "SUCCEEDED", prepared
    assert prepared["completion_log_persisted"] is True
    assert c.setup.probe_record_view()["state"] == "PREPARED_REVIEW_REQUIRED"
    assert c.setup._publication["status"] == "CURRENT"
    assert (
        app.execute_action(ticket["ticket_id"])["operation_id"]
        == receipt["operation_id"]
    )
    assert len(c.stored) == 1
    first = c.setup.probe_record_view()["preparation_sha256"]
    review = _ticket(app, writer.REVIEW, VALUES)
    assert first in " ".join(review["effects"])
    reviewed = _complete(app, app.execute_action(review["ticket_id"])["operation_id"])
    assert reviewed["status"] == "SUCCEEDED", reviewed
    assert len(c.stored) == 2
    saved = bundle(app)
    assert saved["original"]["state"] == "REVIEWED_FOR_ADMISSION"
    assert saved["original"]["preparation"]["evidence_sha256"] == first
    assert saved["original"]["review"]["document"]["preparation_sha256"] == first
    for action in writer.ACTIONS:
        with pytest.raises(WizardError):
            _ticket(app, action, VALUES)
    assert not c.runner.calls
    assert (
        app.view()["camera"]["status"] == app.view()["arm"]["status"] == "NOT_CONNECTED"
    )


@pytest.mark.parametrize("action", sorted(writer.ACTIONS))
def test_consent_fields_are_closed_and_default_off(action):
    definition = ACTION_BY_ID[action]
    assert definition.worker == "physical_camera_setup" and definition.timeout_s == 180
    for values in (
        {},
        {**VALUES, "file_only": False},
        {**VALUES, "operator_id": "é" * 33},
        {**VALUES, "allow_hardware": True},
    ):
        with pytest.raises(WizardError):
            validate_action_input(definition, values)


def test_failed_intent_consumes_queue_and_exports_without_dispatch(joined, monkeypatch):
    app, c = joined.app, joined
    append = app._append_event
    monkeypatch.setattr(
        app,
        "_append_event",
        lambda kind, data: False if kind == "ACTION_EXECUTED" else append(kind, data),
    )
    result = _run(app, writer.PREPARE, VALUES)
    assert result["status"] == "FAILED"
    assert not c.stored and not c.setup._probe_queues[writer.PREPARE]["claimed"]
    saved = bundle(app)
    assert saved["original"] is None and saved["attempts"] == {}
    assert writer.PREPARE in saved["queues"]
    with pytest.raises(WizardError):
        _ticket(app, writer.PREPARE, VALUES)


@pytest.mark.parametrize("fault", ["stop", "owner", "source", "completion-log"])
def test_late_fault_retains_records_without_current_publication(
    joined, monkeypatch, fault
):
    c, app = joined, joined.app
    if fault == "completion-log":
        append = app._append_event
        monkeypatch.setattr(
            app,
            "_append_event",
            lambda kind, data: (
                False if kind == "ACTION_FINISHED" else append(kind, data)
            ),
        )
    else:
        commit = c.tx.commit_stage_state

        def fail_after_commit(*args, **kwargs):
            result = commit(*args, **kwargs)
            if fault == "stop":
                app._cancel.set()
            elif fault == "owner":
                app._native_camera.invalidate("MODELED_OWNER_CHANGED")
            else:
                c.source_state["hash"] = "f" * 64
                c.source = "f" * 64
            return result

        monkeypatch.setattr(c.tx, "commit_stage_state", fail_after_commit)
    result = _run(app, writer.PREPARE, VALUES)
    assert result["status"] != "SUCCEEDED", result
    assert c.setup._publication["status"] != "CURRENT"
    assert len(c.stored) == 1
    if fault == "completion-log":
        monkeypatch.setattr(app, "_append_event", append)
    saved = bundle(app)
    assert (
        saved["attempts"][writer.PREPARE]["record"]["retention"]
        == "M1_FULL_BYTES_READ_BACK"
    )
    assert saved["physical_authority"] is False and not c.runner.calls


def test_general_source_export_keeps_a_pointer_instead_of_deep_probe_bytes(
    make_service,
):
    app, _, _ = make_service(mode="physical")
    deep = {"MODELED": True}
    for _ in range(20):
        deep = {"nested": deep}
    original = dict(
        receipt={"document": {}},
        camera_probe_preparation=dict(
            state="INCOMPLETE",
            preparation={"evidence_sha256": "a" * 64, "document": deep},
            review=None,
        ),
    )
    app._physical_camera_setup._source_workflow = deepcopy(original)
    exported = app._physical_camera_setup.retained_source_diagnostics()
    assert exported == sanitize_diagnostic_record(exported)
    assert "camera_probe_preparation" not in exported["original"]
    assert exported["camera_probe_preparation_summary"]["required_action"] == EXPORT
    assert app._physical_camera_setup._source_workflow == original


def test_export_keeps_completed_receipt_even_if_its_completion_log_fails(
    joined, monkeypatch
):
    app, c = joined.app, joined
    append = app._append_event
    monkeypatch.setattr(
        app,
        "_append_event",
        lambda kind, data: False if kind == "ACTION_EXECUTED" else append(kind, data),
    )
    assert _run(app, writer.PREPARE, VALUES)["status"] == "FAILED"
    monkeypatch.setattr(app, "_append_event", lambda kind, data: False)
    app._log_error = dict(code="MODELED_LOG_FAILURE")
    result = _run(app, EXPORT)
    assert result["status"] == "FAILED"
    assert result["result_retention"] == "FULL_JSON_RETAINED_COMPLETION_LOG_FAILED"
    assert len(app._exports) == 1
    assert verify_export(Path(app._exports[0]["path"]))["valid"] is True
    assert not c.stored and not c.runner.calls


def test_export_refuses_body_changed_after_preview(joined, monkeypatch):
    app = joined.app
    append = app._append_event
    monkeypatch.setattr(
        app,
        "_append_event",
        lambda kind, data: False if kind == "ACTION_EXECUTED" else append(kind, data),
    )
    _run(app, writer.PREPARE, VALUES)
    ticket = _ticket(app, EXPORT)
    app._physical_camera_setup._probe_queues[writer.PREPARE][
        "operation_id"
    ] = "MODELED_CHANGED_AFTER_PREVIEW"
    result = _complete(app, app.execute_action(ticket["ticket_id"])["operation_id"])
    assert (
        result["status"] == "FAILED"
        and result["error"]["code"] == "CAMERA_PROBE_EXPORT_CHANGED"
    )
    assert not app._exports and not app.export_directory.exists()
