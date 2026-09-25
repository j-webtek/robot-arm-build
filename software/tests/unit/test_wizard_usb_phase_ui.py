"""Finite cached renderers; every observation below is explicitly MODELED."""

from copy import deepcopy
import pytest

from rocell.application.physical_usb_identity_service import FLAGS, PHASE_COLLECT
from rocell.application.physical_usb_trial_service import MEANING
from rocell.ui.terminal import _UsbQualificationDisplay
from test_wizard_usb_qualification_ui import (
    view_for,
    complete_setup,
    prerequisite_summary,
)
from test_wizard_usb_identity_ui import modeled_view
from test_wizard_workspace_source_ui import render_snapshot
from test_wizard_camera_identity_navigation import render
from test_wizard_camera_next_step_ui import offered


def phase_view(complete_setup, *, boot_held=False, unknown=False):
    view = view_for(complete_setup)
    old = modeled_view(complete_setup)["usb_identity"]
    card = view["usb_qualification"]
    card.update(
        schema="rocell.wizard_usb_qualification.v2",
        status="BASELINE_ACTIVE",
        meaning=MEANING,
        next_action=PHASE_COLLECT,
    )
    start = 1_800_000_000_000_000_000
    ledger = dict(
        schema="rocell.usb_phase_metadata_acquisition_ledger.v1",
        source_sha256=card["source_sha256"],
        session_id=card["original_context"]["session_id"],
        launch_session_id=view["session_id"],
        trial_id=card["plan"]["binding"]["trial_id"],
        phase_id="usbphase-" + "1" * 32,
        phase_started_at_utc_ns=start,
        entries=[],
    )
    for j, (role, action) in enumerate(
        (
            ("GENERIC_INVENTORY", "inventory_devices"),
            ("NATIVE_INVENTORY", "native_camera_inventory"),
            ("NATIVE_IDENTITY", "native_camera_identity"),
        )
    ):
        ledger["entries"].append(
            dict(
                role=role,
                action_id=action,
                operation_id="operation-modeled-" + str(j),
                started_at_utc_ns=start + 10000 + j * 10000,
                finished_at_utc_ns=start + 11000 + j * 10000,
                published_at_utc_ns=start + 12000 + j * 10000,
                document_sha256="a" * 64,
                result_sha256="b" * 64,
                completion_logged=True,
            )
        )
    preparation = dict(
        schema="rocell.usb_trial_baseline_preparation_summary.v1",
        phase_id=ledger["phase_id"],
        plan_sha256=card["plan"]["plan_sha256"],
        preparation_sha256="c" * 64,
        enrollment_sha256="d" * 64,
        operation_sha256="e" * 64,
        operator_id="Modeled Operator",
        phase_started_at_utc_ns=start,
        prepared_at_utc_ns=start + 90000,
        acquisition_count=3,
        meaning="FRESH_DECLARED_METADATA_AND_FILES_NOT_QUERY_PERMISSION",
        stage_pass=False,
        **FLAGS,
    )
    review = dict(
        identity_sha256="f" * 64,
        policy_review_sha256="a" * 64,
        runtime_review_sha256="b" * 64,
        operator_id="Modeled Operator",
        reviewer_id="Modeled Reviewer",
        review_launch_id=view["session_id"],
        boot_request_sha256="c" * 64,
    )
    card["baseline"] = dict(
        phase_id=ledger["phase_id"],
        state="REVIEWED",
        phase_start_event_sha256="d" * 64,
        phase_started_at_utc_ns=start,
        acquisition_ledger=ledger,
        preparation=preparation,
        target=old["inspection"]["target"],
        review=review,
        host_boot=None,
        execution=None,
        observation=None,
        phase_record=None,
        **FLAGS,
    )
    if boot_held or unknown:
        card.update(
            status="INCOMPLETE_HELD", next_action="physical_usb_identity_export"
        )
        card["baseline"].update(
            state="BOOT_HELD" if boot_held else "ORIGINAL_CAMPAIGN_HELD",
            host_boot=dict(
                schema="rocell.wizard_usb_trial_boot_summary.v1",
                original_state="BOOT_HELD" if boot_held else "BOOT_RETAINED",
                observation_sha256="e" * 64,
                status="HELD" if boot_held else "OBSERVED_HOST_BOOT",
                origin="INJECTED_CIM_EXECUTOR",
                host_key_sha256=None if boot_held else "a" * 64,
                boot_key_sha256=None if boot_held else "b" * 64,
                last_boot_up_time_utc=(
                    None if boot_held else "2026-09-09T01:02:03.000000Z"
                ),
                process_status="FAILED" if boot_held else "SUCCEEDED",
                tree_exit_confirmed=True,
                blockers=["HOST_BOOT_EXECUTION_UNCONFIRMED"] if boot_held else [],
                physical_authority=False,
                hardware_qualified=False,
                device_io_performed=False,
            ),
        )
    if unknown:
        execution = deepcopy(old["execution"])
        execution.update(
            status="CLEANUP_UNCERTAIN",
            counter_coverage="NOT_REPORTED",
            actual_counts=None,
            usb_cleanup_confirmed=False,
            error="NATIVE_RECEIPT_NOT_RETAINED",
        )
        card["baseline"]["execution"] = execution
    view["physical_camera_setup"]["session"]["stages"][3]["state"] = "BLOCKED"
    view["actions"] = [offered(PHASE_COLLECT), offered("physical_usb_identity_export")]
    return view


@pytest.mark.parametrize("case", ["reviewed", "boot_held", "unknown"])
def test_phase_values_no_query_holds_and_unknown_counts_are_distinct(
    complete_setup, case
):
    view = phase_view(
        complete_setup, boot_held=case == "boot_held", unknown=case == "unknown"
    )
    before = deepcopy(view)
    assert (
        _UsbQualificationDisplay.validate(view["usb_qualification"], view)
        == view["usb_qualification"]
    )
    for text in render_snapshot(view):
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in text
        assert "Modeled Operator" in text and "Modeled Reviewer" in text
        assert "LOGGED IN THIS PHASE" in text
        if case == "boot_held":
            assert (
                "HOST_BOOT_EXECUTION_UNCONFIRMED" in text
                and "did not follow an unconfirmed boot" in text
            )
        if case == "unknown":
            assert "UNKNOWN" in text and "INJECTED_CIM_EXECUTOR" in text
    assert view == before


@pytest.mark.parametrize(
    "change",
    [
        lambda b: b.update(physical_authority=True),
        lambda b: b.update(state="PASS"),
        lambda b: b["preparation"].update(stage_pass=True),
        lambda b: b["preparation"].update(plan_sha256="f" * 64),
        lambda b: b["acquisition_ledger"]["entries"][0].update(completion_logged=False),
        lambda b: b["acquisition_ledger"]["entries"].reverse(),
        lambda b: b["acquisition_ledger"].update(source_sha256="f" * 64),
        lambda b: b["review"].update(reviewer_id="Modeled Operator"),
        lambda b: b["review"].update(review_launch_id="another-launch"),
        lambda b: b.update(extra=True),
    ],
)
def test_phase_projection_rejects_false_or_mismatched_current_claims(
    complete_setup, change
):
    view = phase_view(complete_setup)
    change(view["usb_qualification"]["baseline"])
    assert _UsbQualificationDisplay.validate(view["usb_qualification"], view) is None
    assert all(
        "USB_QUALIFICATION_NOT_VERIFIED" in text for text in render_snapshot(view)
    )


def test_rehearsal_next_step_is_navigation_only(complete_setup):
    view = phase_view(complete_setup)
    view["mode"] = "rehearsal"
    view["actions"] = [offered("camera_rehearsal")]
    page = render(view, "camera_rehearsal")
    assert page["navigations"] == ["camera-action-camera_rehearsal"]
    assert "synthetic data" in page["text"]


def test_observed_model_boot_remains_original_held_without_usb(complete_setup):
    from rocell.application.physical_usb_trial_boot import _terminal
    from test_host_boot_observation import request
    from test_physical_usb_trial_boot import owned_report

    # The actual immutable observer producer, with an injected memory executor:
    # no process/CIM query. Its canonical UTC is six fractional digits, and
    # intrinsic observation success does not change the original HELD state.
    report = owned_report(request())
    summary = report.safe_summary()
    view = phase_view(complete_setup, boot_held=True)
    boot = view["usb_qualification"]["baseline"]["host_boot"]
    boot.update(
        observation_sha256=report.sha256,
        original_state=_terminal(report),
        status=summary["status"],
        origin=summary["origin"],
        host_key_sha256=summary["host_key_sha256"],
        boot_key_sha256=summary["boot_key_sha256"],
        last_boot_up_time_utc=summary["response"]["last_boot_up_time_utc"],
        process_status=summary["process_status"],
        blockers=summary["blockers"],
    )
    assert boot["original_state"] == "BOOT_HELD"
    for text in render_snapshot(view):
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in text
        assert "OBSERVED HOST BOOT" in text.replace("_", " ")
        assert "INJECTED_CIM_EXECUTOR" in text
        assert "BOOT HELD" in text.replace("_", " ")
        assert "did not follow an unconfirmed boot" in text


@pytest.mark.parametrize("state", ["BOOT_HELD", "BOOT_UNCERTAIN"])
def test_parent_zero_query_result_requires_an_original_boot_hold(state):
    from rocell.application.arrival_wizard_service import ArrivalWizardService
    from rocell.application.wizard_actions import WizardError
    from test_arrival_usb_identity import result

    value = result(action=PHASE_COLLECT, coverage="NO_DEVICE_IO", opens=0)
    report = value["steps"][0]["report"]
    report.update(
        execution=None,
        usb_query_attempted=False,
        host_boot=dict(original_state=state, device_io_performed=False),
    )
    ArrivalWizardService._validate_usb_identity_result(PHASE_COLLECT, value)
    changes = (
        lambda v: v.update(device_open_count=None),
        lambda v: v.update(device_open_count=1),
        lambda v: v.update(counter_coverage="NOT_REPORTED"),
        lambda v: v["steps"][0]["report"].update(usb_query_attempted=True),
        lambda v: v["steps"][0]["report"].update(host_boot=None),
        lambda v: v["steps"][0]["report"]["host_boot"].update(
            original_state="BOOT_RETAINED"
        ),
    )
    for change in changes:
        bad = deepcopy(value)
        change(bad)
        with pytest.raises(WizardError):
            ArrivalWizardService._validate_usb_identity_result(PHASE_COLLECT, bad)
