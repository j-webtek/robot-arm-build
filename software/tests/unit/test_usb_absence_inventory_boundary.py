"""Real presence facts over typed original snapshots; OS and storage MODELED.

No process/device/CIM or M1 effect is executed. This isolates the refusal before
facts return: an unchanged journal head is not an unchanged evidence inventory.
"""

from dataclasses import replace
from types import SimpleNamespace

import pytest

from rocell.application.physical_usb_absence_service import _UsbTrialAbsence
from rocell.application.physical_usb_presence_campaign import (
    PhysicalUsbPresenceCampaign,
)
from rocell.application.cell_commissioning_coordinator import RegisteredActionRequest
from rocell.application.usb_presence_stage_policy import usb_presence_stage_policy
from rocell.application.wizard_actions import WizardError
from test_physical_camera_usb_absence_readback import (
    ready,
    identity_ready,
    received_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    empty_campaigns,
    absence_subjects,
    refresh_read,
    STAGE_ORDER,
    canonical,
    LAUNCH,
)
from test_physical_camera_usb_qualification import reference


def test_same_head_extra_original_reference_refuses_before_facts_return(
    ready, monkeypatch
):
    made = absence_subjects(ready, monkeypatch, stop="query")
    workflow = refresh_read(ready)
    snapshot = ready[2]["snapshot"]()
    original = workflow["binding"]
    owner = SimpleNamespace(
        setup=SimpleNamespace(
            session=SimpleNamespace(descriptor=lambda: dict(original))
        ),
        workspace=made.runtime.to_dict()["workspace"],
        source_sha256=original["source_sha256"],
        launch_id=LAUNCH,
    )
    helper = _UsbTrialAbsence(owner)
    campaign = PhysicalUsbPresenceCampaign(
        made.subjects["operation"], review=made.subjects["runtime_review"]
    )
    request = RegisteredActionRequest(
        original["cell_id"],
        original["session_id"],
        campaign.registration().action_id,
        "MODELED-no-reservation",
        "f" * 64,
    )
    guards = []
    facts = helper._facts(
        workflow,
        ready[1],
        campaign,
        usb_presence_stage_policy(),
        lambda: guards.append("checked"),
    )
    good = facts(request, snapshot)
    assert good.phase_binding.sha256 == made.binding.sha256
    extra = reference(
        canonical({"MODELED": "unreviewed addition"}), "unreviewed-extra-original"
    )
    assert extra.stage is STAGE_ORDER[3]
    changed = replace(
        snapshot,
        evidence=tuple(
            sorted((*snapshot.evidence, extra), key=lambda r: r.evidence_id)
        ),
    )
    assert (
        changed.head == snapshot.head
        and changed.committed_events == snapshot.committed_events
    )
    before = len(guards)
    with pytest.raises(WizardError):
        facts(request, changed)
    assert len(guards) > before
