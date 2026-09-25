"""Production Setup/USB operations and original readers over MODELED storage.

No real device/process/admission executes. The fixture's monotonic clock and
storage/log publication are modeled: this is not an NTFS timing qualification.
"""

from contextlib import contextmanager
from copy import deepcopy
from threading import Event
import time
import subprocess
import pytest

from rocell.application import physical_usb_identity_service as service
from rocell.application import physical_usb_complete_service as complete
from rocell.application import physical_usb_identity_export as export
from rocell.application.arrival_wizard_service import ArrivalWizardService
from test_physical_camera_usb_reboot_readback import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    workspace,
    empty_campaigns,
    reboot_subjects,
    reboot_boot,
    reboot_query,
    refresh_read,
)
from test_physical_camera_intake_setup import setup_flow
from test_physical_camera_usb_absence_readback import change_last_event
from test_wizard_usb_absence_ui import adopt, snapshot
from test_wizard_usb_qualification_ui import complete_setup, prerequisite_summary
from test_wizard_workspace_source_ui import render_snapshot
from test_wizard_camera_identity_navigation import render
from test_wizard_camera_next_step_ui import offered
from rocell.ui.terminal import _UsbQualificationDisplay
from rocell.application.wizard_actions import ACTION_BY_ID
import test_physical_camera_usb_reboot_readback as original_fixture
from test_usb_observed_projection import forbid_native_execution


def test_actual_setup_assessment_review_and_full_export_join(
    ready, setup_flow, monkeypatch, complete_setup
):
    # Use a valid UI launch label BEFORE producing the new original fixture.
    # Existing stored subjects are never relabeled for display compatibility.
    monkeypatch.setattr(original_fixture, "REBOOT_LAUNCH", "wizard-" + "e" * 32)
    prior = reboot_subjects(ready, monkeypatch)
    reboot_boot(prior, monkeypatch)
    reboot_query(prior)
    workflow = refresh_read(ready)
    setup, _, state = setup_flow
    owner = adopt(setup, workflow)
    state["now"] = time.monotonic_ns()
    monkeypatch.setattr(service, "monotonic_ns", lambda: state["now"])
    monkeypatch.setattr(service, "source_fingerprint", lambda _: state["source"])
    last = [max(time.time_ns(), prior.now)]

    def utc():
        last[0] += 1000
        return last[0]

    monkeypatch.setattr(complete, "time_ns", utc)
    original_scope = state["store"].stage_transaction

    @contextmanager
    def scope(*args, **kwargs):
        with original_scope(*args, **kwargs) as tx:
            tx.store_evidence = lambda stage, payload, **kw: state["add"](
                payload, label=kw["label"], media=kw["media_type"], stage=stage
            )

            def commit(stage, status, **kw):
                state["advance"](status, kw["detail_code"], kw["evidence"], stage=stage)
                change_last_event(state, occurred_at_ns=kw["occurred_at_ns"])
                return tx.snapshot()

            tx.commit_stage_state = commit
            yield tx

    monkeypatch.setattr(state["store"], "stage_transaction", scope)
    previous = dict(state["payloads"])

    def display(expected_action):
        current = snapshot(owner, complete_setup)
        current["actions"] = [offered(complete.EXPORT)] + [
            offered(name, enabled=name == expected_action)
            for name in sorted(complete.ACTIONS)
        ]
        value = current["usb_qualification"]
        _UsbQualificationDisplay._validate(value, current)
        assert value["next_action"] == expected_action
        assert all(
            "USB_QUALIFICATION_NOT_VERIFIED" not in text
            for text in render_snapshot(current)
        )
        page = render(current, expected_action)
        assert page["navigations"] == ["camera-action-" + expected_action]
        assert page["requests"] == [
            {"path": "/api/view", "method": "GET", "body": None}
        ]
        return current

    for name in complete.ACTIONS:
        definition = ACTION_BY_ID[name]
        assert (
            definition.worker == "physical_usb_identity" and definition.timeout_s == 180
        )
        assert all(
            not field.get("default", False)
            for field in owner.fields(name)
            if field["type"] == "checkbox"
        )
    display(complete.ASSESS)

    def action(action_id, values):
        assert owner.blocked_reason(action_id) is None

        def no_process(*args, **kwargs):
            pytest.fail("file-only assessment/review attempted a process")

        # Block every process during the operation; only the separate finite
        # Node renderer outside this scope may run for the UI assertions.
        with monkeypatch.context() as guard:
            guard.setattr(subprocess, "Popen", no_process)
            result = owner.perform(
                action_id,
                values,
                expected_context_sha256=owner.context_sha256(),
                cancellation=Event(),
                progress=lambda _: None,
            )
        ArrivalWizardService._validate_usb_identity_result(action_id, result)
        assert (
            result["counter_coverage"] == "NO_DEVICE_IO"
            and result["device_open_count"] == 0
        )
        assert result["steps"][0]["report"]["usb_query_attempted"] is False
        assert owner.qualification_view()["complete"] is None
        assert owner.qualification_view()["next_action"] is None
        owner.validate_publication(result)
        setup.publication_completed("MODELED-complete-log-" + action_id)
        owner.publication_completed("MODELED-complete-log-" + action_id)
        assert previous.items() <= state["payloads"].items()
        assert owner.blocked_reason(action_id) is not None

    action(
        complete.ASSESS, dict(confirm_file_assessment=True, confirm_identity_only=True)
    )
    assert owner.qualification_view()["complete"]["state"] == "REVIEW_PENDING"
    assert owner.qualification_view()["next_action"] == complete.REVIEW
    pending = display(complete.REVIEW)
    # Both UIs reject changed summaries rather than promoting a cached verdict.
    for path, replacement in [
        (("complete", "state"), "REVIEWED_PASS"),
        (("complete", "assessment", "checks", 0, "passed"), 1),
        (("complete", "assessment", "phases", 0, "phase_sha256"), "f" * 64),
        (("camera_capture_authorized",), True),
        (("next_action",), complete.ASSESS),
    ]:
        bad = deepcopy(pending)
        target = bad["usb_qualification"]
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = replacement
        assert _UsbQualificationDisplay.validate(bad["usb_qualification"], bad) is None
        assert all(
            "USB_QUALIFICATION_NOT_VERIFIED" in text for text in render_snapshot(bad)
        )
    action(
        complete.REVIEW,
        dict(
            reviewer_id="MODELED-final-independent-reviewer",
            decision="ACKNOWLEDGE_EXACT",
            confirm_exact_assessment=True,
            confirm_identity_only=True,
        ),
    )
    view = owner.qualification_view()
    assert view["complete"]["state"] == "REVIEWED_PASS"
    assert view["complete"]["review"]["review_launch_id"] == owner.launch_id
    display(complete.EXPORT)
    assert all(view[key] is False for key in service.FLAGS)
    assert all(row.state.value == "PENDING" for row in state["snapshot"]().stages[4:])
    diagnostics = owner.retained_diagnostics()
    report, parts = export.prepare_usb_identity_diagnostics_export(
        diagnostics, source_sha256=owner.source_sha256, launch_id=owner.launch_id
    )
    assert report["schema"] == export.EXPORT_V7_SCHEMA
    assert export.restore_usb_identity_diagnostics(report, parts) == diagnostics
    assert diagnostics["qualification_complete"]["review"]["reference"] is not None
