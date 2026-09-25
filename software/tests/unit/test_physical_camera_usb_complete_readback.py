"""Full v14 joins with MODELED storage, metadata, boot and USB observations.

The actual original-role readers and subject verifiers run. These tests do not
authenticate real M1 leases, launch a provider or qualify physical hardware.
"""

from copy import deepcopy
from types import SimpleNamespace

from rocell.application import physical_camera_session as session
from rocell.application import physical_camera_usb_complete_readback as reader
from rocell.application import physical_camera_usb_reboot_readback as reboot_reader
from rocell.application import physical_usb_complete_series as codec
from rocell.application.physical_camera_usb_complete_inputs import (
    original_usb_complete_inputs,
)
from rocell.application.physical_camera_usb_complete_constants import (
    SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA,
    USB_COMPLETE_ROLE_BYTES,
    usb_complete_event,
    usb_complete_label,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.providers.windows.usb_identity_protocol import canonical
import pytest

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
    change_last_event,
)


SERIES_ID = "usbseries-" + "7" * 32


def complete_subjects(
    case,
    monkeypatch,
    *,
    checkpoint=None,
    rejected=False,
    review_launch_id="MODELED-review-launch",
):
    """Publish into a fresh modeled case; never edit historical subjects."""
    reboot = reboot_subjects(case, monkeypatch)
    reboot_boot(reboot, monkeypatch)
    reboot_query(reboot)
    original = refresh_read(case)
    inputs = original_usb_complete_inputs(
        original, received=received_trio(case, original)
    )
    state = case[2]
    made = SimpleNamespace(
        original=original, inputs=inputs, refs={}, subjects={}, now=reboot.now
    )

    def capture(label):
        if checkpoint is not None:
            checkpoint(label, made)

    def advance(kind, stage_state, refs):
        made.now += 1000
        state["advance"](
            stage_state,
            usb_complete_event(kind, SERIES_ID),
            tuple(sorted(refs, key=lambda r: r.evidence_id)),
            stage=STAGE_ORDER[3],
        )
        change_last_event(state, occurred_at_ns=made.now)

    def retain(subject):
        made.subjects[subject.role] = subject
        made.refs[subject.role] = state["add"](
            subject.payload,
            label=usb_complete_label(subject.role, SERIES_ID),
            stage=STAGE_ORDER[3],
        )
        capture(subject.role)

    advance(
        "ASSESSMENT_REQUESTED",
        V2StageState.WAITING_OPERATOR,
        (reboot.refs["phase_record"],),
    )
    capture("requested")
    series = codec.build_complete_usb_series(series_id=SERIES_ID, **inputs)
    retain(series)
    assessment = codec.assess_complete_usb_series(series, **inputs)
    retain(assessment)
    advance("ASSESSMENT_RETAINED", V2StageState.REVIEW_PENDING, made.refs.values())
    capture("assessed")
    review = codec.review_complete_usb_series(
        series,
        assessment,
        reviewer_id="MODELED-distinct-final-reviewer",
        review_launch_id=review_launch_id,
        reviewed_at_utc_ns=made.now + 1,
        decision="REJECT" if rejected else "ACKNOWLEDGE_EXACT",
        **inputs,
    )
    retain(review)
    advance(
        "REVIEWED",
        V2StageState.BLOCKED if rejected else V2StageState.PASS,
        made.refs.values(),
    )
    capture("reviewed")
    return made


def test_full_original_complete_review_and_legacy_reader_refusal(ready, monkeypatch):
    made = complete_subjects(ready, monkeypatch)
    captured = []
    verify = reboot_reader._verify_usb_reboot_prefix

    def capture(*args, **kwargs):
        captured.append((args, kwargs))
        return verify(*args, **kwargs)

    monkeypatch.setattr(reboot_reader, "_verify_usb_reboot_prefix", capture)
    workflow = refresh_read(ready)
    row = workflow["usb_qualification_complete"]
    assert workflow["schema"] == SOURCE_WORKFLOW_USB_COMPLETE_SCHEMA
    assert row["state"] == "REVIEWED_PASS"
    assert len(row["events"]) == 3
    for role in USB_COMPLETE_ROLE_BYTES:
        assert row[role]["document"] == made.subjects[role].to_dict()
        assert row[role]["reference"] == made.refs[role].to_dict()
    for key in (
        "usb_qualification_baseline",
        "usb_qualification_absence",
        "usb_qualification_reconnect",
        "usb_qualification_reboot",
    ):
        assert workflow[key] == made.original[key]
    assert session._decode_cached_source_workflow(canonical(workflow)) == workflow
    assert (
        len(canonical(workflow)) - len(canonical(made.original))
        < sum(USB_COMPLETE_ROLE_BYTES.values()) + 16 * 1024
    )
    assert all(
        s.state is V2StageState.PENDING for s in ready[2]["snapshot"]().stages[4:]
    )
    assert all(made.subjects["review"].to_dict()[flag] is False for flag in codec.FLAGS)
    args, kwargs = captured[-1]
    # The old public v13 reader still rejects the real later suffix/inventory.
    kwargs = {
        k: v
        for k, v in kwargs.items()
        if k
        not in {
            "prefix_event_count",
            "usb_complete_evidence_ids",
            "camera_mode_entry",
        }
    }
    with pytest.raises(session.PhysicalCameraSessionError):
        reboot_reader.verify_usb_reboot_workflow(*args, **kwargs)


def test_each_publication_boundary_reopens_without_promoting_partial_review(
    ready, monkeypatch
):
    expected = dict(
        requested="ASSESSMENT_REQUESTED",
        series="INCOMPLETE",
        assessment="INCOMPLETE",
        assessed="REVIEW_PENDING",
        review="INCOMPLETE",
        reviewed="REVIEWED_BLOCKED",
    )
    seen = []

    def checkpoint(label, made):
        workflow = refresh_read(ready)
        row = workflow["usb_qualification_complete"]
        assert row["state"] == expected[label]
        assert {role for role in USB_COMPLETE_ROLE_BYTES if row[role]} == set(made.refs)
        assert (
            workflow["usb_qualification_reboot"]
            == made.original["usb_qualification_reboot"]
        )
        seen.append(label)

    complete_subjects(ready, monkeypatch, checkpoint=checkpoint, rejected=True)
    assert seen == list(expected)


def test_missing_reboot_originals_fail_before_predecessor_reader(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("missing original reached predecessor reader")

    monkeypatch.setattr(reboot_reader, "_verify_usb_reboot_prefix", denied)
    with pytest.raises(
        session.PhysicalCameraSessionError, match="CAMERA_SESSION_USB_COMPLETE_INVALID"
    ):
        reader.verify_usb_complete_workflow(*({} for _ in range(18)))
