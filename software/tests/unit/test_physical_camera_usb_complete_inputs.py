"""Original-reader data join with explicitly modeled storage/device subjects."""

from copy import deepcopy

import pytest

from rocell.application import physical_camera_usb_complete_inputs as m
from rocell.application import physical_usb_complete_series as series
from test_physical_camera_usb_reboot_readback import (
    ready,
    received_ready,
    identity_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    empty_campaigns,
    reboot_subjects,
    reboot_boot,
    reboot_query,
    refresh_read,
    received_trio,
)


def test_completed_original_v13_inputs_join_complete_series(ready, monkeypatch):
    made = reboot_subjects(ready, monkeypatch)
    reboot_boot(made, monkeypatch)
    reboot_query(made)
    workflow = refresh_read(ready)
    before = deepcopy(workflow)
    args = m.original_usb_complete_inputs(
        workflow, received=received_trio(ready, workflow)
    )
    assert set(args) == {
        "predecessor",
        "reboot_payload",
        "reboot_reference",
        "reboot_permit",
        "reboot_sources",
        "reboot_references",
    }
    assert (
        set(args["reboot_sources"])
        == set(args["reboot_references"])
        == {
            "operation",
            "operator_event",
            "native_enrollment",
            "owned_usb_run",
            "host_boot",
        }
    )
    phase = workflow["usb_qualification_reboot"]["phase_record"]
    assert args["reboot_payload"] == m.canonical(phase["document"])
    assert args["reboot_reference"].to_dict() == phase["reference"]
    obj = series.build_complete_usb_series(series_id="usbseries-" + "7" * 32, **args)
    assessment = series.assess_complete_usb_series(obj, **args)
    assert assessment.to_dict()["verdict"] == series.ELIGIBLE
    assert workflow == before
    assert all(obj.to_dict()[flag] is False for flag in series.FLAGS)


@pytest.mark.parametrize(
    "candidate",
    [
        None,
        [],
        {},
        {"schema": "rocell.physical_camera_source_workflow_readback.v12"},
        {"schema": "rocell.usb_identity_diagnostic_export.v6"},
        {
            "schema": m.SOURCE_WORKFLOW_USB_REBOOT_SCHEMA,
            "usb_qualification_reboot": {
                "phase": "AFTER_REBOOT",
                "state": "ORIGINAL_CAMPAIGN_HELD",
            },
        },
    ],
)
def test_missing_held_or_export_inputs_fail_before_predecessor_join(
    candidate, monkeypatch
):
    def denied(*args, **kwargs):
        pytest.fail("invalid workflow reached predecessor reconstruction")

    monkeypatch.setattr(m, "original_usb_reboot_predecessor_v13", denied)
    with pytest.raises(m.CompleteUsbInputsError):
        m.original_usb_complete_inputs(candidate, received={})
