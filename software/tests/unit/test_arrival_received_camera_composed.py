"""Public Arrival + real received services/codecs, modeled M1/physical facts.

Controlled source files and test inbox originals are real. No device, native
worker, host metadata enumeration, qualified hardware or real M1 is claimed.
"""

from copy import deepcopy
import json
from pathlib import Path
import subprocess

import pytest

from rocell.application import physical_received_camera_service as module
from rocell.application import arrival_wizard_service as arrival_module
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.physical_received_camera_export import (
    restore_received_camera_family,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_arrival_static_onboarding_composed import (
    static_composed,
    composed,
    public,
    make_service,
    modeled,
    setup_flow,
    source_model,
    intake_model,
    model,
    workspace,
    RAW,
    values,
)
from test_arrival_wizard_service import _run, _ticket, _complete
from test_physical_received_camera_service import (
    record_values,
    RAW as RECEIVED_RAW,
    PNG,
)
from test_wizard_workspace_source_ui import render_snapshot


@pytest.fixture
def received_composed(static_composed, monkeypatch):
    arrival, source, design, state, runner, calls = static_composed
    owner = module.PhysicalReceivedCameraService(design.setup)
    arrival._received_camera = owner
    monkeypatch.setattr(module, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(module, "monotonic_ns", lambda: state["now"])
    owner.observe_setup()
    source.inbox.root.mkdir(parents=True, exist_ok=True)
    (source.inbox.root / "modeled-isolation.txt").write_bytes(RAW)
    public(arrival, "physical_source_isolation_files_discover")
    supplied = values()
    supplied.update(
        isolation_state="OBSERVED_DISCONNECTED",
        isolation_statement="MODELED disconnected observation, not received hardware.",
        isolation_choice=source.inbox.choices()[0]["value"],
    )
    public(arrival, "physical_source_qualify", supplied)
    public(
        arrival,
        "physical_source_qualification_review",
        {"file_only": True, "reviewer_id": "source-reviewer"},
    )
    public(arrival, "physical_static_contract_begin", {"file_only": True})
    public(
        arrival,
        "physical_static_contract_collect",
        {"file_only": True, "operator_id": "static-operator"},
    )
    public(
        arrival,
        "physical_static_contract_review",
        {"file_only": True, "reviewer_id": "static-reviewer"},
    )
    public(arrival, "physical_camera_receipt_begin", {"file_only": True})
    return arrival, owner, state, runner


def start_fill(arrival, *, observed=False):
    public(arrival, module.START, {"file_only": True, "mode": "BLANK"})
    for row in arrival.view()["received_camera_onboarding"]["draft"]["rows"]:
        public(arrival, module.RECORD, record_values(row, observed=observed))


def submission_values(arrival, owner, observed):
    values = {
        "file_only": True,
        "operator_id": "receipt-operator",
        "inspection_state": "UNKNOWN",
    }
    if not observed:
        return values
    owner.inbox.root.mkdir(parents=True, exist_ok=True)
    (owner.inbox.root / "modeled-purchase.txt").write_bytes(RECEIVED_RAW)
    (owner.inbox.root / "modeled-image.png").write_bytes(PNG)
    public(arrival, module.DISCOVER, {"file_only": True})
    choices = {
        item["basename"]: item["choice_id"] for item in owner.inbox.view()["files"]
    }
    values.update(
        inspection_state="RECORDED",
        inspection_observed_now=True,
        observed_manufacturer="Arducam",
        observed_product_id="B0477",
        observed_camera_serial="MODELED-TEST-ONLY",
        observed_lens_focal_length_mm="16",
        body_condition="ACCEPTABLE",
        lens_condition="ACCEPTABLE",
        connector_condition="ACCEPTABLE",
        identity_label_legible=True,
        purchase_record_matches=True,
        package_contents_complete=True,
        inspection_uncertain="CERTAIN",
        purchase_choice=choices["modeled-purchase.txt"],
        inspection_image_choice=choices["modeled-image.png"],
        **{
            "attachment_" + row["record_id"]: choices["modeled-purchase.txt"]
            for row in owner.view()["draft"]["rows"]
        },
    )
    # The root field migration preserves direct-service bool compatibility;
    # public forms use its currently declared closed choices only.
    field = next(
        f for f in owner.fields(module.SUBMIT) if f["name"] == "inspection_uncertain"
    )
    if field["type"] == "checkbox":
        values["inspection_uncertain"] = False
    return values


def export_directory(operation):
    for step in operation["result"]["steps"]:
        if "metadata_export" in step["report"]:
            return Path(step["report"]["metadata_export"]["path"])
    raise AssertionError(operation)


@pytest.mark.parametrize("used", [7, 30])
def test_start_preview_advises_exact_budget_without_creating_draft(
    received_composed, used
):
    arrival, owner, state, runner = received_composed
    arrival._primary_operations = used
    before = (
        state["reads"],
        state["enters"],
        deepcopy(state["payloads"]),
        owner.retained_diagnostics(),
    )
    ticket = _ticket(arrival, module.START, {"file_only": True, "mode": "BLANK"})
    effects = " ".join(ticket["effects"])
    assert f"{32-used} of 32 primary actions remaining" in effects
    assert "about 21 actions" in effects
    assert "BEFORE starting the draft" in effects
    assert "does not automatically restore it on restart" in effects
    assert (
        state["reads"],
        state["enters"],
        state["payloads"],
        owner.retained_diagnostics(),
    ) == before
    assert arrival._primary_operations == used and owner.view()["draft"] is None
    assert ticket["physical_authority"] is False and not runner.calls


@pytest.mark.parametrize("observed", [False, True])
def test_public_received_original_review_identity_and_two_exports(
    received_composed, monkeypatch, observed
):
    arrival, owner, state, runner = received_composed
    before = deepcopy(state["payloads"])
    snapshots = []
    with monkeypatch.context() as guard:
        guard.setattr(
            subprocess,
            "Popen",
            lambda *a, **k: pytest.fail(
                "file-only public path launched process/device"
            ),
        )
        start_fill(arrival, observed=observed)
        snapshots.append(arrival.view())
        supplied = submission_values(arrival, owner, observed)
        reads = (state["reads"], state["enters"])
        ticket = _ticket(arrival, module.SUBMIT, supplied)
        assert reads == (state["reads"], state["enters"])
        dispatched = arrival.execute_action(ticket["ticket_id"])
        completed = _complete(arrival, dispatched["operation_id"])
        assert completed["status"] == "SUCCEEDED", completed
        assert (
            arrival.execute_action(ticket["ticket_id"])["operation_id"]
            == completed["operation_id"]
        )
        snapshots.append(arrival.view())
        public(
            arrival,
            module.REVIEW,
            {
                "file_only": True,
                "reviewer_id": "receipt-reviewer",
                "decision": "ACKNOWLEDGE_EXACT",
            },
        )
        if observed:
            public(arrival, module.IDENTITY, {"file_only": True})
        snapshots.append(arrival.view())
        exported = public(arrival, module.EXPORT, {"file_only": True})
        directory = export_directory(exported)
        assert verify_export(directory)["valid"]
        cycle_packet = json.loads(
            (directory / "attachment-received-camera-cycle-01.json").read_text(
                encoding="utf-8"
            )
        )
        original_cycle = owner.retained_diagnostics()["cycles"][0]
        assert (
            restore_received_camera_family(
                cycle_packet,
                expected_original_family_sha256=digest(canonical(original_cycle)),
            )
            == original_cycle
        )
        assert cycle_packet["original_bytes_preserved"] is True
        assert cycle_packet["credential_redaction_applied"] is False
        snapshots.append(arrival.view())
        ordinary = public(arrival, "export_logs")
        general = Path(ordinary["result"]["receipt"]["path"])
        assert verify_export(general)["valid"]
        report = json.loads((general / "report.json").read_text(encoding="utf-8"))
        pointer = report["snapshot"]["received_camera_onboarding"]
        assert pointer["schema"] == "rocell.wizard_received_camera_export_pointer.v1"
        assert pointer["original_received_documents_included"] is False
        assert pointer["metadata_export"]["path"] == str(directory)
        assert len(list(general.glob("attachment-*"))) <= 8
        assert not list(general.glob("attachment-*received*"))
        assert not runner.calls
        assert all(state["payloads"][key] == value for key, value in before.items())
        original = owner.setup.original_source_workflow()["received_camera_cycles"][0]
        for role in ("notebook", "submission", "assessment", "review"):
            assert (
                digest(canonical(original[role]["document"]))
                == original[role]["evidence_sha256"]
            )
        assert owner.view()["status"] == (
            "REVIEWED_PASS" if observed else "REVIEWED_BLOCKED"
        )
        assert owner.view()["stage_states"]["camera_identity"] == (
            "WAITING_OPERATOR" if observed else "PENDING"
        )
    for view in snapshots:
        browser, terminal = render_snapshot(view)
        assert "RECEIVED_CAMERA_NOT_VERIFIED" not in browser
        assert "RECEIVED_CAMERA_NOT_VERIFIED" not in terminal
        assert "Received camera and passive workcell" in terminal
        assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in browser
        assert "STATIC_CAMERA_ONBOARDING_NOT_VERIFIED" not in browser
    browser, terminal = render_snapshot(report["snapshot"])
    assert "RECEIVED METADATA POINTER ONLY" in browser
    assert "RECEIVED_CAMERA_NOT_VERIFIED" not in browser
    assert "RECEIVED_CAMERA_NOT_VERIFIED" not in terminal
    assert "RECEIVED METADATA POINTER ONLY" in terminal


@pytest.mark.parametrize("fault", ["stop", "source", "log"])
def test_actual_submit_late_failure_retained_export_no_replay(
    received_composed, monkeypatch, fault
):
    arrival, owner, state, runner = received_composed
    start_fill(arrival)
    actual = owner.perform
    calls = []

    def perform(action, *args, **kwargs):
        calls.append(action)
        assert not arrival._lock._is_owned()
        result = actual(action, *args, **kwargs)
        if action == module.SUBMIT:
            assert arrival.view()["received_camera_onboarding"]["collection"] is None
            if fault == "stop":
                kwargs["cancellation"].set()
            if fault == "source":
                monkeypatch.setattr(
                    arrival_module, "source_fingerprint", lambda _: "f" * 64
                )
        return result

    monkeypatch.setattr(owner, "perform", perform)
    if fault == "log":
        append = arrival._log.append

        def fail(name, details):
            if name == "ACTION_FINISHED":
                raise OSError("modeled completion log failure")
            return append(name, details)

        monkeypatch.setattr(arrival._log, "append", fail)
    ticket = _ticket(arrival, module.SUBMIT, submission_values(arrival, owner, False))
    completed = _complete(
        arrival, arrival.execute_action(ticket["ticket_id"])["operation_id"]
    )
    # The original transaction already committed; a late Stop does not relabel
    # that known completion as unexecuted, but must withdraw current publication.
    assert completed["status"] == (
        "SUCCEEDED" if fault == "stop" else "FAILED"
    ), completed
    assert (
        arrival.execute_action(ticket["ticket_id"])["operation_id"]
        == completed["operation_id"]
    )
    assert calls == [module.SUBMIT]
    assert (
        arrival.view()["received_camera_onboarding"]["publication"]["status"]
        == "HISTORICAL_HELD"
    )
    retained = owner.retained_diagnostics()
    assert retained is not None
    assert (
        owner.setup.original_source_workflow()["received_camera_cycles"][0]["state"]
        == "REVIEW_PENDING"
    )
    # Recovery export stays explicit and available even under failed log/source
    # and the primary-action cap; it never replays a stored submission.
    arrival._primary_operations = 32
    export_ticket = _ticket(arrival, module.EXPORT, {"file_only": True})
    exported = _complete(
        arrival, arrival.execute_action(export_ticket["ticket_id"])["operation_id"]
    )
    directory = export_directory(exported)
    assert verify_export(directory)["valid"]
    assert calls == [module.SUBMIT, module.EXPORT]
    assert owner.view()["publication"]["status"] == "HISTORICAL_HELD"
    assert not runner.calls
