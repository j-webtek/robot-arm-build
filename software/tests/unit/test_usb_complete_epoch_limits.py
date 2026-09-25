"""V14 capacity checks on modeled typed snapshots, not role qualification."""

from copy import deepcopy
from dataclasses import replace

import pytest

from rocell.application import physical_camera_session as session
from rocell.application import physical_configuration_epochs as epochs
from rocell.application.physical_camera_usb_complete_constants import (
    SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA,
    USB_COMPLETE_ROLE_BYTES,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.providers.windows.usb_identity_protocol import canonical
from test_usb_reboot_epoch_limits import boundary as reboot_boundary
from test_physical_configuration_epochs import reference
from test_physical_camera_usb_complete_layout import case as layout_case


@pytest.fixture(scope="module")
def boundary(reboot_boundary):
    prerequisites, snapshot, artifact = reboot_boundary
    extra = tuple(
        reference(STAGE_ORDER[3], salt=f"MODELED-v14-only-{i}") for i in range(3)
    )
    return (
        prerequisites,
        replace(
            snapshot,
            evidence=tuple(
                sorted((*snapshot.evidence, *extra), key=lambda r: r.evidence_id)
            ),
        ),
        artifact,
    )


def verify(case, changed=None):
    prerequisites, snapshot, artifact = case
    return epochs._verify_physical_configuration_epochs_after_usb_complete(
        artifact.payload,
        prerequisites=prerequisites,
        snapshot=snapshot if changed is None else changed,
        expected_sha256=artifact.sha256,
    )


def test_only_three_references_added_without_expanding_old_readers(boundary):
    prerequisites, snapshot, artifact = boundary
    assert len(snapshot.evidence) == 185
    assert sum(r.stage is STAGE_ORDER[3] for r in snapshot.evidence) == 70
    assert verify(boundary).payload == artifact.payload
    for old in (
        epochs.verify_physical_configuration_epochs,
        epochs._verify_physical_configuration_epochs_after_usb_reboot,
    ):
        with pytest.raises(ValueError):
            old(
                artifact.payload,
                prerequisites=prerequisites,
                snapshot=snapshot,
                expected_sha256=artifact.sha256,
            )
    with pytest.raises(ValueError):
        epochs.build_physical_configuration_epochs(prerequisites, snapshot)


@pytest.mark.parametrize("stage", range(5))
def test_no_additional_reference_or_later_stage(boundary, stage):
    snapshot = boundary[1]
    extra = reference(STAGE_ORDER[stage], salt="MODELED-over-complete-limit")
    changed = replace(
        snapshot,
        evidence=tuple(
            sorted((*snapshot.evidence, extra), key=lambda r: r.evidence_id)
        ),
    )
    with pytest.raises(ValueError):
        verify(boundary, changed)


def test_exact_56_kib_addition_not_an_extra_query_campaign(boundary):
    snapshot = boundary[1]
    assert sum(USB_COMPLETE_ROLE_BYTES.values()) == 56 * 1024
    cap = (8964 + 56) * 1024
    stage4 = [r for r in snapshot.evidence if r.stage is STAGE_ORDER[3]]
    first = stage4[0]
    at = replace(first, payload_bytes=cap - sum(r.payload_bytes for r in stage4[1:]))
    changed = replace(
        snapshot, evidence=tuple(at if r == first else r for r in snapshot.evidence)
    )
    assert verify(boundary, changed).payload == boundary[2].payload
    over = replace(
        changed,
        evidence=tuple(
            replace(r, payload_bytes=r.payload_bytes + 1) if r == at else r
            for r in changed.evidence
        ),
    )
    with pytest.raises(ValueError):
        verify(boundary, over)


def test_closed_cache_envelope_fits_without_raising_legacy_or_node_caps():
    # Documents have separate byte caps. Bound their wrapper/event overhead
    # using longest allowed IDs/counters, keeping the exact six citations.
    snapshot, packages, _, prefix = layout_case()
    records = {p["kind"]: deepcopy(p["record"]) for p in packages.values()}
    for record in records.values():
        record["document"] = {}
        record["reference"]["payload_bytes"] = 32 * 1024 * 1024
    events = [event.to_dict() for event in snapshot.committed_events[prefix:]]
    for event in events:
        event.update(session_id="s" * 64, sequence=511, occurred_at_ns=2**63 - 1)
        for ref in event["evidence"]:
            ref["payload_bytes"] = 32 * 1024 * 1024
    envelope = dict(
        schema=SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA,
        usb_qualification_complete=dict(
            series_id="usbseries-" + "f" * 32,
            state="ASSESSMENT_REQUESTED",
            events=events,
            **records,
            meaning="Original camera-identity review only; no capture, arm, motion or contact permission.",
        ),
    )
    assert sum(len(event["evidence"]) for event in events) == 6
    assert len(canonical(envelope)) < 16 * 1024
    assert (
        session.MAX_USB_COMPLETE_WORKFLOW_BYTES
        == session.MAX_USB_REBOOT_WORKFLOW_BYTES + 72 * 1024
    )
    assert (
        session._SOURCE_WORKFLOW_BYTE_LIMITS[session.SOURCE_WORKFLOW_USB_REBOOT_SCHEMA]
        == session.MAX_USB_REBOOT_WORKFLOW_BYTES
    )
    assert session.MAX_IDENTITY_WORKFLOW_CACHE_NODES == 262_144
