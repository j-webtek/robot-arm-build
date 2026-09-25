"""Finite real fake-DOM and terminal renderers over modeled declaration views."""

from copy import deepcopy
import pytest

from rocell.application.physical_usb_identity_service import (
    DECLARE,
    FLAGS,
    QUALIFICATION_MEANING,
)
from rocell.ui.terminal import _UsbQualificationDisplay
from test_wizard_usb_identity_ui import (
    modeled_view,
    complete_setup,
    prerequisite_summary,
)
from test_wizard_workspace_source_ui import render_snapshot
from test_wizard_camera_identity_navigation import render
from test_wizard_camera_next_step_ui import offered


def view_for(complete_setup, status="DECLARED"):
    view = modeled_view(complete_setup)
    baseline = view["usb_identity"]
    baseline.update(status="HISTORICAL_HELD", next_action=None)
    baseline["publication"] = dict(status="HISTORICAL_HELD", operation_id=None)
    context = deepcopy(baseline["original_context"])
    plan = dict(
        plan_sha256="a" * 64,
        binding={
            **context,
            "trial_id": "usbtrial-" + "1" * 32,
            "identity_entry_sha256": "b" * 64,
            "stage_policy_sha256": "c" * 64,
            "stage_catalog_sha256": "d" * 64,
            "stage_order_sha256": "e" * 64,
        },
        operator_id="Original Operator",
        launch_session_id=view["session_id"],
        cable_label="cable_with_underscores_α",
        port_label="original_port_1",
        received_label=dict(
            manufacturer="MODELED_manufacturer",
            product_id="MODELED_product",
            serial="MODELED_serial",
            inspection_sha256="f" * 64,
        ),
        phases=["BASELINE", "RECONNECT_ABSENCE", "AFTER_RECONNECT", "AFTER_REBOOT"],
    )
    card = dict(
        schema="rocell.wizard_usb_qualification.v1",
        source_sha256=view["source_binding_sha256"],
        launch_session_id=view["session_id"],
        original_context=context,
        publication=dict(status="CURRENT", operation_id="original-log"),
        status=status,
        plan=plan,
        next_action=None,
        export_receipt=None,
        meaning=QUALIFICATION_MEANING,
        **FLAGS
    )
    view["physical_camera_setup"]["session"]["stages"][3]["state"] = "REVIEW_PENDING"
    if status == "NOT_DECLARED":
        card.update(plan=None, next_action=DECLARE)
        view["physical_camera_setup"]["session"]["stages"][3]["state"] = "BLOCKED"
    view["usb_qualification"] = card
    view["actions"] = [offered(DECLARE, enabled=status == "NOT_DECLARED")]
    return view


@pytest.mark.parametrize("status", ["NOT_DECLARED", "DECLARED", "INCOMPLETE_HELD"])
def test_plan_is_literal_and_never_phase_evidence(complete_setup, status):
    view = view_for(complete_setup, status)
    before = deepcopy(view)
    assert (
        _UsbQualificationDisplay.validate(view["usb_qualification"], view)
        == view["usb_qualification"]
    )
    for text in render_snapshot(view):
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in text
        assert "no phase evidence" in text
        assert "new app launch is not a reboot" in text
        if status != "NOT_DECLARED":
            assert "cable_with_underscores_α" in text and "MODELED_serial" in text
            for phase in view["usb_qualification"]["plan"]["phases"]:
                assert phase + ": NOT ACQUIRED" in text
    assert before == view


def test_navigation_is_inert_and_requires_server_eligibility(complete_setup):
    view = view_for(complete_setup, "NOT_DECLARED")
    assert render(view, DECLARE)["navigations"] == ["camera-action-" + DECLARE]
    view["actions"][0]["enabled"] = False
    assert not any(link["id"] == DECLARE for link in render(view)["links"])


def test_retained_trial_points_to_original_export_not_old_stage_forms(complete_setup):
    view = view_for(complete_setup)
    action = "physical_usb_identity_export"
    view["actions"] += [offered(action), offered("physical_received_camera_export")]
    page = render(view, action)
    assert [link["id"] for link in page["links"]] == [action]
    assert "No phase acquisition is available" in page["text"]
    assert page["navigations"] == ["camera-action-" + action]


@pytest.mark.parametrize("publication", ["PENDING", "HISTORICAL_HELD"])
def test_pending_and_history_do_not_promote_original_context(
    complete_setup, publication
):
    view = view_for(complete_setup)
    card = view["usb_qualification"]
    card["publication"] = dict(status=publication, operation_id=None)
    if publication == "PENDING":
        card.update(status="NOT_DECLARED", plan=None)
    else:
        card["status"] = "HISTORICAL_HELD"
        view["source_binding_sha256"] = "0" * 64
    for text in render_snapshot(view):
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in text
        assert (
            "Declaration publication pending"
            if publication == "PENDING"
            else "HISTORICAL ONLY"
        ) in text
        if publication == "PENDING":
            assert "cable_with_underscores_α" not in text


@pytest.mark.parametrize(
    "change",
    [
        lambda c: c.update(physical_authority=True),
        lambda c: c.update(camera_capture_authorized=True),
        lambda c: c.update(source_sha256="f" * 64),
        lambda c: c["original_context"].update(header_sha256="f" * 64),
        lambda c: c["plan"]["binding"].update(prerequisites_sha256="f" * 64),
        lambda c: c["plan"].update(phases=["BASELINE", "AFTER_REBOOT"]),
        lambda c: c["plan"].update(phases=["BASELINE"] * 4),
        lambda c: c["plan"].update(cable_label="é" * 65),
        lambda c: c["plan"].update(operator_id="é"),
        lambda c: c["plan"].update(port_label="port\nline"),
        lambda c: c["plan"].update(boot_verified=True),
        lambda c: c.update(next_action="physical_usb_identity_collect"),
        lambda c: c["publication"].update(status="PENDING"),
        lambda c: c.update(export_receipt={"path": "not a receipt"}),
    ],
)
def test_malformed_declaration_is_withheld(complete_setup, change):
    view = view_for(complete_setup)
    change(view["usb_qualification"])
    assert _UsbQualificationDisplay.validate(view["usb_qualification"], view) is None
    for text in render_snapshot(view):
        assert "USB_QUALIFICATION_NOT_VERIFIED" in text


def test_no_new_trial_reboot_or_phase_calls_from_legacy_snapshot(complete_setup):
    view = modeled_view(complete_setup)
    for text in render_snapshot(view):
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in text
        assert "No trial declaration" in text
