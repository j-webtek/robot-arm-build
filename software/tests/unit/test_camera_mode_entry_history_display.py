"""Pure historical boot display; model facts are never original admission."""

from copy import deepcopy

import pytest

from rocell.application.physical_camera_mode_entry import (
    SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA,
)
from rocell.application.physical_usb_reconnect_service import _entry_history_boot
from test_host_boot_observation import modeled_observation
from test_physical_camera_usb_qualification import reference


@pytest.fixture
def history():
    boot = modeled_observation()  # Explicit incapable/CIM model, no process.
    record = dict(
        document=boot.to_dict(),
        evidence_sha256=boot.sha256,
        reference=reference(boot.payload, "MODELED-boot-history").to_dict(),
        retention="M1_FULL_BYTES_READ_BACK",
    )
    return boot, dict(
        schema=SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA,
        camera_mode_entry=dict(state="ENTERED"),
        usb_qualification_complete=dict(state="REVIEWED_PASS"),
        usb_qualification_absence=dict(host_boot=record),
        usb_qualification_reconnect=dict(host_boot=deepcopy(record)),
    )


@pytest.mark.parametrize(
    "phase", ["usb_qualification_absence", "usb_qualification_reconnect"]
)
@pytest.mark.parametrize("state", ["ENTERED", "INCOMPLETE"])
def test_exact_boot_bytes_only_without_workflow_relabel(history, phase, state):
    boot, workflow = history
    workflow["camera_mode_entry"]["state"] = state
    original = deepcopy(workflow)
    retained = _entry_history_boot(workflow, phase)
    assert retained.payload == boot.payload and retained.sha256 == boot.sha256
    assert workflow == original


@pytest.mark.parametrize(
    "fault",
    ["legacy", "future", "entry", "review", "hash", "length", "retention", "phase"],
)
def test_bad_history_is_not_reinterpreted_as_a_current_predecessor(history, fault):
    _, workflow = history
    phase = "usb_qualification_absence"
    record = workflow[phase]["host_boot"]
    if fault in {"legacy", "future"}:
        workflow["schema"] = "rocell.physical_camera_source_workflow_readback." + (
            "v14" if fault == "legacy" else "v16"
        )
    elif fault == "entry":
        workflow["camera_mode_entry"]["state"] = "PASS"
    elif fault == "review":
        workflow["usb_qualification_complete"]["state"] = "REVIEW_PENDING"
    elif fault == "hash":
        record["evidence_sha256"] = "f" * 64
    elif fault == "length":
        record["reference"]["payload_bytes"] += 1
    elif fault == "retention":
        record["retention"] = "COLLECTED_NOT_M1_RETAINED"
    else:
        phase = "usb_qualification_reboot"
    assert _entry_history_boot(workflow, phase) is None
