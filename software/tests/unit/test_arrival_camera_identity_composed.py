"""Actual Arrival/service/codecs; modeled physical metadata and M1 ownership.

The prefix is the existing real received service over the explicitly modeled
store. No device or metadata provider is called by the identity actions.
"""

from copy import deepcopy
import json
from pathlib import Path
import subprocess
from types import SimpleNamespace
import uuid

import pytest

from rocell.application import arrival_wizard_service as arrival_module
from rocell.application import physical_camera_identity_service as module
from rocell.application.physical_intake_evidence_service import (
    PhysicalIntakeEvidenceService,
)
from rocell.application.physical_source_qualification_service import (
    PhysicalSourceQualificationService,
)
from rocell.application.physical_static_camera_onboarding_service import (
    PhysicalStaticCameraOnboardingService,
)
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_device_selection import WizardDeviceSelection
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import make_service, _ticket, _complete, _run
from test_wizard_camera_identity_navigation import (
    identity_wait,
    received,
    static_service,
    modeled,
    setup_flow,
    source_model,
    intake_model,
    model,
    workspace,
    complete_modeled_storage_projection,
    render,
)
from test_physical_camera_identity_readback import identity_inputs


SUBMIT_VALUES = dict(
    file_only=True,
    operator_id="identity-operator",
    observation_state="UNKNOWN",
    observed_value="Unknown_USB_origin",
    method="Not_measured",
    evidence_note="No_USB_descriptor_evidence",
    observation_current=True,
)
REVIEW_VALUES = dict(
    file_only=True, reviewer_id="identity-reviewer", decision="ACKNOWLEDGE_EXACT"
)
EXPORT_VALUES = dict(file_only=True, confirm_metadata_export=True)


@pytest.fixture
def identity_composed(identity_wait, make_service, monkeypatch):
    received_owner, state, _ = identity_wait
    setup = received_owner.setup
    with monkeypatch.context() as fixed_launch:
        fixed_launch.setattr(
            arrival_module,
            "uuid",
            SimpleNamespace(uuid4=lambda: uuid.UUID(setup.launch_id[7:])),
        )
        arrival, runner, source = make_service(mode="physical")
    arrival._physical_camera_setup = setup
    arrival._physical_camera = setup._acquisition
    arrival._received_camera = received_owner
    arrival._source_qualification = PhysicalSourceQualificationService(setup)
    arrival._static_camera_onboarding = PhysicalStaticCameraOnboardingService(setup)
    arrival._physical_intake_evidence = PhysicalIntakeEvidenceService(setup)
    owner = module.PhysicalCameraIdentityService(setup)
    arrival._camera_identity_records = owner
    for service in (
        arrival._source_qualification,
        arrival._static_camera_onboarding,
        arrival._physical_intake_evidence,
        owner,
    ):
        service.observe_setup()
    supplied = identity_inputs(
        source=setup.source_sha256, launch=setup.launch_id, return_owners=True
    )
    arrival._native_camera = supplied["native_camera"]
    arrival._camera_helper = supplied["helper"]
    reviewed = arrival._native_camera.export_snapshot()["generic_review"]
    generic = WizardDeviceSelection("physical", setup.launch_id, setup.source_sha256)
    generic.ingest(reviewed["inventory_report"], operation_id=reviewed["operation_id"])
    generic.review(generic.choices("CAMERA")[0]["value"], "CAMERA", "generic-reviewer")
    arrival._device_selection = generic
    monkeypatch.setattr(module, "source_fingerprint", lambda _: state["source"])
    monkeypatch.setattr(module, "monotonic_ns", lambda: state["now"])
    original_perform = owner.perform

    def outside_lock(*args, **kwargs):
        assert not arrival._lock._is_owned()
        assert not any(key.startswith("_") for key in args[1])
        assert kwargs["native_camera"] is not arrival._native_camera
        assert kwargs["helper"] is not arrival._camera_helper
        return original_perform(*args, **kwargs)

    monkeypatch.setattr(owner, "perform", outside_lock)
    return arrival, owner, state, source, runner


def perform(arrival, action, values):
    operation = _run(arrival, action, values)
    assert operation["status"] == "SUCCEEDED", operation
    return operation


def rendered(arrival):
    value = arrival.view()
    from rocell.ui.terminal import _CameraIdentityDisplay
    from test_wizard_workspace_source_ui import render_snapshot

    assert (
        _CameraIdentityDisplay.validate(value["camera_identity_onboarding"], value)
        == value["camera_identity_onboarding"]
    )
    page = render(value)
    _, terminal = render_snapshot(value)
    assert "CAMERA_IDENTITY_NOT_VERIFIED" not in terminal
    assert "CAMERA_IDENTITY_NOT_VERIFIED" not in page["text"]
    assert "PHYSICAL_CAMERA_SETUP_NOT_VERIFIED" not in page["text"]
    assert "RECEIVED_CAMERA_NOT_VERIFIED" not in page["text"]
    assert "STATIC_CAMERA_ONBOARDING_NOT_VERIFIED" not in page["text"]
    assert "stage-5 entry" in page["text"]
    return value, page


def test_public_identity_original_retention_review_exports_and_no_replay(
    identity_composed, monkeypatch
):
    arrival, owner, state, source, runner = identity_composed
    before = deepcopy(state["payloads"])
    rendered(arrival)
    with monkeypatch.context() as guard:
        guard.setattr(
            subprocess,
            "Popen",
            lambda *a, **kw: pytest.fail("identity action launched process/device"),
        )
        reads = state["reads"], state["enters"]
        ticket = _ticket(arrival, module.SUBMIT, SUBMIT_VALUES)
        assert reads == (state["reads"], state["enters"])
        queued = arrival.execute_action(ticket["ticket_id"])
        result = _complete(arrival, queued["operation_id"])
        assert result["status"] == "SUCCEEDED", result
        assert (
            arrival.execute_action(ticket["ticket_id"])["operation_id"]
            == result["operation_id"]
        )
        assert owner.view()["status"] == "REVIEW_PENDING"
        perform(arrival, module.REVIEW, REVIEW_VALUES)
        assert owner.view()["status"] == "REVIEWED_BLOCKED"
        full = owner.retained_diagnostics()
        receipt = full["cycles"][0]["receipt"]["document"]
        assert receipt["observation"]["value"] == SUBMIT_VALUES["observed_value"]
        dedicated = perform(arrival, module.EXPORT, EXPORT_VALUES)
        directory = Path(
            dedicated["result"]["steps"][0]["report"]["metadata_export"]["path"]
        )
        verify_export(directory)
        generic = perform(arrival, "export_logs", {})
        general = Path(generic["result"]["receipt"]["path"])
        verify_export(general)
    view, page = rendered(arrival)
    assert view["camera_identity_onboarding"]["export_receipt"]["path"] == str(
        directory
    )
    assert view["received_camera_onboarding"]["status"] == "HISTORICAL_HELD"
    saved = json.loads((general / "report.json").read_text(encoding="utf-8"))
    pointer = saved["snapshot"]["camera_identity_onboarding"]
    assert pointer["schema"] == "rocell.wizard_camera_identity_export_pointer.v1"
    assert pointer["separate_metadata_export_required"] is True
    assert (
        pointer["cycles"][0]["receipt_sha256"]
        == owner.view()["cycles"][0]["receipt"]["sha256"]
    )
    assert "General export coverage pointer only" in render(saved["snapshot"])["text"]
    assert all(state["payloads"][key] == value for key, value in before.items())
    assert not runner.calls


@pytest.mark.parametrize("late", ["source", "stop", "log", "redaction"])
def test_late_publication_failure_retains_originals_and_export_remains_explicit(
    identity_composed, monkeypatch, late
):
    arrival, owner, state, source, runner = identity_composed
    previous = owner.perform
    original_log = arrival._log.append

    def after(*args, **kwargs):
        result = previous(*args, **kwargs)
        assert owner.view()["publication"]["status"] == "PENDING"
        assert arrival.view()["camera_identity_onboarding"]["cycles"] == []
        if late == "source":
            source["hash"] = "b" * 64
        elif late == "stop":
            kwargs["cancellation"].set()
        elif late == "log":
            monkeypatch.setattr(
                arrival._log,
                "append",
                lambda *a, **kw: (_ for _ in ()).throw(
                    OSError("modeled completion failure")
                ),
            )
        else:
            result["steps"][0]["report"]["meaning"] = "password=secret-fixture"
        return result

    monkeypatch.setattr(owner, "perform", after)
    operation = _run(arrival, module.SUBMIT, SUBMIT_VALUES)
    if late == "stop":
        # The already committed bytes cannot be undone. Current publication is
        # withheld while the durable operation remains honestly successful.
        assert operation["status"] == "SUCCEEDED", operation
        assert "cancellation cannot undo evidence" in operation["result"]["message"]
    else:
        assert operation["status"] == "FAILED", operation
    held = arrival.view()["camera_identity_onboarding"]
    assert held["publication"]["status"] == "HISTORICAL_HELD"
    assert held["next_action"] is None
    originals = owner.retained_diagnostics()
    assert originals["cycles"][0]["state"] == "REVIEW_PENDING"
    monkeypatch.setattr(owner, "perform", previous)
    monkeypatch.setattr(arrival._log, "append", original_log)
    exported = perform(arrival, module.EXPORT, EXPORT_VALUES)
    directory = Path(
        exported["result"]["steps"][0]["report"]["metadata_export"]["path"]
    )
    verify_export(directory)
    assert owner.retained_diagnostics()["cycles"] == originals["cycles"]
    rendered(arrival)
    assert not runner.calls


def test_changed_metadata_ticket_never_enters_original_transaction(identity_composed):
    arrival, owner, state, source, runner = identity_composed
    ticket = _ticket(arrival, module.SUBMIT, SUBMIT_VALUES)
    before = state["reads"], state["enters"], deepcopy(state["payloads"])
    arrival._native_camera.invalidate_identity(
        "NATIVE_IDENTITY_REPLACEMENT_NOT_VERIFIED"
    )
    with pytest.raises(WizardError):
        arrival.execute_action(ticket["ticket_id"])
    assert before == (state["reads"], state["enters"], state["payloads"])
    assert owner.retained_diagnostics() is None and not runner.calls


def test_four_original_collections_and_separate_export_stay_bounded(identity_composed):
    arrival, owner, state, source, runner = identity_composed
    original_hashes = []
    for index in range(4):
        perform(
            arrival,
            module.SUBMIT,
            dict(
                SUBMIT_VALUES,
                evidence_note=f"Unknown evidence for explicit collection {index+1}",
            ),
        )
        perform(arrival, module.REVIEW, REVIEW_VALUES)
        summary = owner.view()["cycles"]
        original_hashes.append(summary[-1]["receipt"]["sha256"])
        assert [cycle["receipt"]["sha256"] for cycle in summary] == original_hashes
    with pytest.raises(WizardError):
        _ticket(arrival, module.SUBMIT, SUBMIT_VALUES)
    export = perform(arrival, module.EXPORT, EXPORT_VALUES)
    receipt = export["result"]["steps"][0]["report"]["metadata_export"]
    verify_export(Path(receipt["path"]))
    assert len(receipt["files"]) <= 12 and receipt["total_bytes"] <= 8 * 1024 * 1024
    generic = perform(arrival, "export_logs", {})
    directory = Path(generic["result"]["receipt"]["path"])
    verify_export(directory)
    snapshot = json.loads((directory / "report.json").read_text(encoding="utf-8"))[
        "snapshot"
    ]
    assert len(snapshot["camera_identity_onboarding"]["cycles"]) == 4
    rendered(arrival)
    assert not runner.calls
