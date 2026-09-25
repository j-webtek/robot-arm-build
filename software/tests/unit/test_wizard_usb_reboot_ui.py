"""Real v13 codecs and both displays; all hardware/storage observations modeled.

The finite Node fake DOM tests rendering/navigation only. No native camera,
host-boot collector, USB or arm provider may execute in these tests.
"""

from copy import deepcopy

import pytest

from rocell.application import physical_usb_reboot_service as reboot
from rocell.application.physical_usb_identity_export import (
    prepare_usb_identity_diagnostics_export,
    restore_usb_identity_diagnostics,
)
from rocell.ui.terminal import (
    _PhysicalSetupDisplay,
    _UsbQualificationDisplay,
    _TerminalWizard,
)
from test_physical_camera_usb_reboot_readback import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    workspace,
    empty_campaigns,
    refresh_read,
    reboot_subjects,
    reboot_boot,
    reboot_query,
)
import test_physical_camera_usb_reboot_readback as original_fixture
from test_physical_camera_intake_setup import setup_flow
from test_wizard_usb_absence_ui import adopt, snapshot
from test_wizard_usb_qualification_ui import complete_setup, prerequisite_summary
from test_usb_observed_projection import forbid_native_execution
from test_wizard_workspace_source_ui import render_snapshot
from test_wizard_camera_identity_navigation import render
from test_wizard_camera_next_step_ui import offered
from test_wizard_physical_camera_restart_ui import registry

NEW_LAUNCH = "wizard-" + "e" * 32


def current_view(ready, setup_flow, complete_setup, monkeypatch, *, final):
    # Choose the valid new launch BEFORE constructing any new retained bytes.
    monkeypatch.setattr(original_fixture, "REBOOT_LAUNCH", NEW_LAUNCH)
    made = reboot_subjects(ready, monkeypatch)
    if final:
        reboot_boot(made, monkeypatch)
        reboot_query(made)
    workflow = refresh_read(ready)
    setup = setup_flow[0]
    setup.launch_id = NEW_LAUNCH
    owner = adopt(setup, workflow)
    assert owner.launch_id == NEW_LAUNCH
    view = snapshot(owner, complete_setup)
    # This is a modeled current Setup publication with the ORIGINAL binding.
    view["session_id"] = NEW_LAUNCH
    setup_view = view["physical_camera_setup"]
    setup_view.update(
        launch_session_id=NEW_LAUNCH,
        origin_launch_id=setup_view["session"]["binding"]["launch_id"],
        requirements_provenance="REOPENED_ORIGINAL_CONTEXT",
        reopening=registry(NEW_LAUNCH, setup_view["source_sha256"]),
    )
    assert _PhysicalSetupDisplay.setup(setup_view) == setup_view
    view["actions"] = [offered(reboot.EXPORT)] + [
        offered(action, enabled=not final and action == reboot.BOOT_COLLECT)
        for action in sorted(reboot.ACTIONS)
    ]
    return made, owner, view


@pytest.mark.parametrize("final", [False, True])
def test_current_new_launch_keeps_history_and_renders_exact_reboot(
    ready, setup_flow, complete_setup, monkeypatch, final
):
    made, owner, view = current_view(
        ready, setup_flow, complete_setup, monkeypatch, final=final
    )
    value = view["usb_qualification"]
    assert (
        value["schema"] == "rocell.wizard_usb_qualification.v6"
        if final
        else value["schema"] == "rocell.wizard_usb_qualification.v5"
    )
    assert value["reconnect"]["operator_event"]["launch_session_id"] != NEW_LAUNCH
    assert value["reboot"]["operator_event"]["launch_session_id"] == NEW_LAUNCH
    _UsbQualificationDisplay._validate(value, view)
    expected = "RETAINED_BLOCKED" if final else "REVIEWED"
    assert value["reboot"]["state"] == expected
    # Exercise the real complete v13 owner cache, not just minimal export shapes.
    diagnostic = owner.retained_diagnostics()
    report, parts = prepare_usb_identity_diagnostics_export(
        diagnostic, source_sha256=owner.source_sha256, launch_id=owner.launch_id
    )
    assert report["schema"] == "rocell.usb_identity_diagnostic_export.v6"
    assert restore_usb_identity_diagnostics(report, parts) == diagnostic
    lines = []
    terminal = _TerminalWizard(None, lambda _: "", lines.append, lambda _: None)
    terminal.show_usb_qualification(value, view)
    texts = ["\n".join(map(str, lines)), *render_snapshot(view)]
    for text in texts:
        assert "USB_QUALIFICATION_NOT_VERIFIED" not in text
        assert f"AFTER_REBOOT: {expected}" in text
        assert "AFTER_REBOOT: NOT ACQUIRED" not in text
        assert "not a robot E-stop" in text
    next_action = "physical_usb_complete_assess" if final else reboot.BOOT_COLLECT
    if final:
        view["actions"].append(offered(next_action))
    page = render(view, next_action)
    assert page["navigations"] == ["camera-action-" + next_action]
    original = deepcopy(value)
    mutations = [
        (("reboot", "physical_authority"), True),
        (("reboot", "operator_event", "launch_session_id"), "wizard-" + "b" * 32),
        (("reboot", "acquisition_ledger", "entries", 0, "completion_logged"), 1),
        (("reconnect", "state"), "INCOMPLETE"),
    ]
    if final:
        mutations += [
            (("reboot", "phase_record", "status"), "PASS"),
            (("reboot", "host_boot", "restart_status"), "BOOT_HELD"),
            (("reboot", "host_boot", "boot_relation"), "SAME_HOST_SAME_BOOT"),
        ]
    for path, replacement in mutations:
        bad = deepcopy(original)
        target = bad
        for key in path[:-1]:
            target = target[key]
        target[path[-1]] = replacement
        assert _UsbQualificationDisplay.validate(bad, view) is None
        bad_view = deepcopy(view)
        bad_view["usb_qualification"] = bad
        assert "USB_QUALIFICATION_NOT_VERIFIED" in render(bad_view)["text"]
    assert value == original
