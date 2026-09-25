"""Cached original reconnect projections; storage/physical observations MODELED.

The real original codecs and owner run. Renderer tests use only a finite Node
fake DOM; no production process, CIM, USB, camera or arm access is performed.
"""

from copy import deepcopy

from rocell.application import physical_usb_reconnect_service as reconnect
from rocell.ui.terminal import _UsbQualificationDisplay, _TerminalWizard
from test_physical_camera_usb_reconnect_readback import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    workspace,
    empty_campaigns,
    refresh_read,
    reconnect_subjects,
    reconnect_boot,
    reconnect_query,
)
from test_physical_camera_intake_setup import setup_flow
from test_wizard_usb_absence_ui import adopt, snapshot
from test_wizard_usb_qualification_ui import complete_setup, prerequisite_summary
from test_usb_observed_projection import forbid_native_execution
from test_wizard_workspace_source_ui import render_snapshot
from test_wizard_camera_identity_navigation import render
from test_wizard_camera_next_step_ui import offered


def test_actual_codec_complete_owner_both_renderers_and_inert_navigation(
    ready, setup_flow, complete_setup, monkeypatch
):
    made = reconnect_subjects(ready, monkeypatch)
    prior_owner = adopt(setup_flow[0], made.original)
    before_begin = snapshot(prior_owner, complete_setup)
    assert before_begin["usb_qualification"]["reconnect"] is None
    assert before_begin["usb_qualification"]["next_action"] == reconnect.BEGIN
    before_begin["actions"] = [offered(reconnect.BEGIN), offered(reconnect.EXPORT)]
    page = render(before_begin, reconnect.BEGIN)
    assert page["navigations"] == ["camera-action-" + reconnect.BEGIN]
    before_begin["actions"][0]["enabled"] = False
    assert reconnect.BEGIN not in [row["id"] for row in render(before_begin)["links"]]
    reconnect_boot(made, monkeypatch)
    reconnect_query(made)
    workflow = refresh_read(ready)
    owner = adopt(setup_flow[0], workflow)
    view = snapshot(owner, complete_setup)
    view["actions"] = [offered(reconnect.EXPORT)] + [
        offered(action, enabled=False) for action in sorted(reconnect.ACTIONS)
    ]
    value = view["usb_qualification"]
    _UsbQualificationDisplay._validate(value, view)
    assert value["schema"] == "rocell.wizard_usb_qualification.v4"
    assert value["reconnect"]["state"] == "RETAINED_BLOCKED"
    lines = []
    terminal = _TerminalWizard(None, lambda _: "", lines.append, lambda _: None)
    terminal.show_usb_qualification(value, view)
    text = "\n".join(str(x) for x in lines)
    assert "AFTER_RECONNECT: RETAINED_BLOCKED" in text
    assert "AFTER_RECONNECT: NOT ACQUIRED" not in text
    assert "USB_QUALIFICATION_NOT_VERIFIED" not in text
    assert "AFTER_REBOOT" in text and "not a robot E-stop" in text
    for field in ("descriptor_serial", "driver_provider", "physical_usb_instance"):
        assert field in text
    for rendered in render_snapshot(view):
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in rendered
        assert "AFTER_RECONNECT: RETAINED_BLOCKED" in rendered
        assert "AFTER_RECONNECT: NOT ACQUIRED" not in rendered
        assert "AFTER_REBOOT" in rendered and "not a robot E-stop" in rendered
        for field in ("descriptor_serial", "driver_provider", "physical_usb_instance"):
            assert field in rendered
    page = render(view, reconnect.EXPORT)
    assert [row["id"] for row in page["links"]] == [reconnect.EXPORT]
    assert page["navigations"] == ["camera-action-" + reconnect.EXPORT]
    original = deepcopy(value)
    for path, replacement in (
        (("reconnect", "physical_authority"), True),
        (("reconnect", "operator_event", "launch_session_id"), "MODELED-old-launch"),
        (("reconnect", "acquisition_ledger", "entries", 0, "completion_logged"), 1),
        (("reconnect", "phase_record", "status"), "PASS"),
    ):
        bad = deepcopy(original)
        target = bad
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = replacement
        assert _UsbQualificationDisplay.validate(bad, view) is None
        invalid_view = deepcopy(view)
        invalid_view["usb_qualification"] = bad
        assert "USB_QUALIFICATION_NOT_VERIFIED" in render(invalid_view)["text"]
    owner.launch_id = "wizard-" + "f" * 32
    historical = owner.qualification_view()
    assert historical["status"] == "HISTORICAL_HELD"
    assert historical["publication"]["status"] == "HISTORICAL_HELD"
    assert historical["next_action"] == reconnect.EXPORT
    assert _UsbQualificationDisplay.validate(historical, view) is not None
    history_view = deepcopy(view)
    history_view["usb_qualification"] = historical
    for rendered in render_snapshot(history_view):
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in rendered
        assert (
            "HISTORICAL" in rendered and "AFTER_RECONNECT: RETAINED_BLOCKED" in rendered
        )
    page = render(history_view, reconnect.EXPORT)
    assert [row["id"] for row in page["links"]] == [reconnect.EXPORT]
