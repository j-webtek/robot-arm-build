"""Stage-5 original-reader composition with MODELED storage/device facts.

The complete preceding codecs, journal and original-role readers run. This is
not a physical-camera or NTFS acceptance test; it cannot grant device access.
"""

from copy import deepcopy

import pytest

from rocell.application import physical_camera_session as session
from rocell.application import physical_camera_usb_complete_readback as complete_reader
from rocell.application.physical_camera_mode_entry import (
    SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA,
    FALSE_FIELDS,
    build_camera_mode_entry,
    camera_mode_entry_event,
    camera_mode_entry_label,
)
from rocell.application.physical_camera_mode_entry_readback import (
    CameraModeOriginalError,
    camera_mode_entry_binding,
    read_camera_mode_entry_layout,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.providers.windows.usb_identity_protocol import canonical
from test_physical_camera_usb_complete_readback import (
    ready,
    received_ready,
    identity_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    empty_campaigns,
    complete_subjects,
    refresh_read,
    change_last_event,
)


ENTRY_ID = "cameramode-" + "a" * 32
ENTRY_LAUNCH = "wizard-" + "f" * 32


def test_complete_original_then_retained_and_committed_entry(ready, monkeypatch):
    complete_subjects(ready, monkeypatch)
    original = refresh_read(ready)
    original_copy = deepcopy(original)
    binding = camera_mode_entry_binding(original, entry_launch_id=ENTRY_LAUNCH)
    state = ready[2]
    now = state["snapshot"]().committed_events[-1].occurred_at_ns + 1
    entry = build_camera_mode_entry(
        entry_id=ENTRY_ID,
        binding=binding,
        operator_id="MODELED-camera-setup-operator",
        recorded_at_utc_ns=now,
    )
    reference = state["add"](
        entry.payload,
        label=camera_mode_entry_label(ENTRY_ID),
        stage=STAGE_ORDER[4],
    )
    captured = []
    verify = complete_reader._verify_usb_complete_prefix

    def capture(*args, **kwargs):
        captured.append((args, kwargs))
        return verify(*args, **kwargs)

    monkeypatch.setattr(complete_reader, "_verify_usb_complete_prefix", capture)
    partial = refresh_read(ready)
    assert partial["schema"] == SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA
    assert partial["camera_mode_entry"]["state"] == "INCOMPLETE"
    assert partial["camera_mode_entry"]["events"] == []
    assert state["snapshot"]().stages[4].state is V2StageState.PENDING

    # Continue this modeled producer to observe the second write boundary. A
    # real failed/abandoned partial operation is diagnostic-only, not resumed.
    state["advance"](
        V2StageState.WAITING_OPERATOR,
        camera_mode_entry_event(ENTRY_ID),
        (reference,),
        stage=STAGE_ORDER[4],
    )
    change_last_event(state, occurred_at_ns=now + 1)
    entered = refresh_read(ready)
    row = entered["camera_mode_entry"]
    assert row["state"] == "ENTERED"
    assert row["entry"]["document"] == entry.to_dict()
    assert row["entry"]["reference"] == reference.to_dict()
    assert len(row["events"]) == 1
    assert all(row["entry"]["document"][flag] is False for flag in FALSE_FIELDS)
    for key in (
        "usb_qualification_baseline",
        "usb_qualification_absence",
        "usb_qualification_reconnect",
        "usb_qualification_reboot",
        "usb_qualification_complete",
        "configuration_epochs",
    ):
        assert entered[key] == partial[key] == original[key]
    assert original == original_copy
    assert session._decode_cached_source_workflow(canonical(entered)) == entered
    assert all(s.state is V2StageState.PENDING for s in state["snapshot"]().stages[5:])
    args, kwargs = captured[-1]
    assert args[1] == state["snapshot"]()  # Same full journal, never a sliced past.
    kwargs = {k: v for k, v in kwargs.items() if k != "camera_mode_entry"}
    with pytest.raises(session.PhysicalCameraSessionError):
        complete_reader.verify_usb_complete_workflow(*args, **kwargs)


@pytest.mark.parametrize("packages", [None, {}, [], {"a": {}}, {"a": {}, "b": {}}])
def test_malformed_package_rejected_without_predecessor(packages):
    with pytest.raises(CameraModeOriginalError, match="CAMERA_MODE_ORIGINAL_INVALID"):
        read_camera_mode_entry_layout(None, packages)


@pytest.mark.parametrize(
    "workflow", [None, {}, [], {"schema": SOURCE_WORKFLOW_CAMERA_MODE_SCHEMA}]
)
def test_dependency_extraction_requires_the_complete_predecessor(workflow):
    with pytest.raises(CameraModeOriginalError, match="CAMERA_MODE_ORIGINAL_INVALID"):
        camera_mode_entry_binding(workflow, entry_launch_id=ENTRY_LAUNCH)
