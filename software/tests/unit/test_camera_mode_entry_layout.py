"""Fast modeled journal structure, not real original history or M1 qualification.

The fake prefix deliberately cannot pass the complete USB subject verifier.
These tests prove only the additional entry suffix, not its predecessor truth.
"""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import subprocess
from types import SimpleNamespace

import pytest

from rocell.application.physical_onboarding import EvidenceReference, STAGE_ORDER
from rocell.application.physical_onboarding_v2 import (
    V2SessionHeader,
    V2JournalEvent,
    V2CommittedHead,
    V2StageSnapshot,
    V2NextAction,
    V2SessionSnapshot,
    V2StageState as S,
)
from rocell.application.physical_camera_usb_complete_constants import usb_complete_event
from rocell.providers.windows.usb_identity_protocol import canonical, digest
from test_camera_mode_entry_contract import entry, binding, ENTRY_ID


@pytest.fixture
def layout():
    from rocell.application import physical_camera_mode_entry_layout

    return physical_camera_mode_entry_layout


@pytest.fixture(autouse=True)
def no_effects(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("pure layout attempted filesystem/process effects")

    monkeypatch.setattr(Path, "open", denied)
    monkeypatch.setattr(Path, "read_bytes", denied)
    monkeypatch.setattr(subprocess, "Popen", denied)


def reference(raw, label, stage):
    package = digest(label.encode("ascii"))
    return EvidenceReference(
        "evidence-" + package, stage, package, "b" * 64, digest(raw), len(raw)
    )


@pytest.fixture
def case(entry, binding):
    header = V2SessionHeader.build(
        session_id=binding["session_id"],
        cell_id=binding["cell_id"],
        created_at_ns=1,
        source_binding_sha256="c" * 64,
        publication_durability="PORTABLE_UNQUALIFIED",
        durability_qualification_sha256="0" * 64,
    )
    binding["header_sha256"] = header.header_sha256
    events, refs = [], []
    for index, stage in enumerate(STAGE_ORDER[:4]):
        ref = reference(
            b"MODELED incomplete predecessor", "prefix-" + str(index), stage
        )
        refs.append(ref)
        for old, new in (
            (S.PENDING, S.WAITING_OPERATOR),
            (S.WAITING_OPERATOR, S.REVIEW_PENDING),
            (S.REVIEW_PENDING, S.PASS),
        ):
            events.append(
                V2JournalEvent.build(
                    header=header,
                    sequence=len(events),
                    stage=stage,
                    previous_state=old,
                    state=new,
                    occurred_at_ns=10 + len(events),
                    previous_event_sha256=(
                        events[-1].event_sha256 if events else "0" * 64
                    ),
                    evidence=(ref,),
                    detail_code=(
                        usb_complete_event("REVIEWED", "usbseries-" + "7" * 32)
                        if index == 3 and new is S.PASS
                        else "MODELED_PREFIX_ONLY"
                    ),
                )
            )
    binding["complete_review_event_sha256"] = events[-1].event_sha256
    subject = entry.build_camera_mode_entry(
        entry_id=ENTRY_ID,
        binding=binding,
        operator_id="MODELED operator",
        recorded_at_utc_ns=50,
    )
    ref = reference(subject.payload, "entry", STAGE_ORDER[4])
    record = dict(
        document=subject.to_dict(),
        evidence_sha256=subject.sha256,
        reference=ref.to_dict(),
        retention="M1_FULL_BYTES_READ_BACK",
    )
    prefix_count = len(events)
    events.append(
        V2JournalEvent.build(
            header=header,
            sequence=len(events),
            stage=STAGE_ORDER[4],
            previous_state=S.PENDING,
            state=S.WAITING_OPERATOR,
            occurred_at_ns=60,
            previous_event_sha256=events[-1].event_sha256,
            evidence=(ref,),
            detail_code=entry.camera_mode_entry_event(ENTRY_ID),
        )
    )
    refs.append(ref)
    stages = []
    for stage in STAGE_ORDER:
        relevant = [event for event in events if event.stage is stage]
        stages.append(
            V2StageSnapshot(
                stage,
                relevant[-1].state if relevant else S.PENDING,
                relevant[-1].sequence if relevant else None,
                tuple(
                    sorted(
                        {
                            item.evidence_id
                            for event in relevant
                            for item in event.evidence
                        }
                    )
                ),
            )
        )
    snapshot = V2SessionSnapshot(
        header,
        tuple(stages),
        tuple(events),
        (),
        tuple(sorted(refs, key=lambda item: item.evidence_id)),
        V2CommittedHead.build(header, tuple(events)),
        V2NextAction("MODELED_ONLY", STAGE_ORDER[4], S.WAITING_OPERATOR, True),
    )
    return SimpleNamespace(
        snapshot=snapshot,
        record=record,
        entry=subject,
        ref=ref,
        binding=binding,
        prefix_count=prefix_count,
    )


def verify(layout, case):
    return layout.verify_camera_mode_entry_layout(
        case.snapshot,
        case.record,
        expected_entry_id=ENTRY_ID,
        expected_binding=case.binding,
    )


def test_exact_entry_suffix_does_not_authenticate_prefix_or_grant_permission(
    layout, case
):
    before = deepcopy(case.snapshot)
    result = verify(layout, case)
    assert result.state == "ENTERED"
    assert result.prefix_event_count == case.prefix_count
    assert result.events == case.snapshot.committed_events[-1:]
    assert result.reference == case.ref and result.entry.payload == case.entry.payload
    assert result.original_store_authenticated is False
    assert case.snapshot == before
    with pytest.raises((AttributeError, FrozenInstanceError)):
        result.state = "PASS"


def test_private_prefix_allowance_is_exact_and_inert(layout, case):
    result = verify(layout, case)
    assert layout._camera_mode_entry_extension(None, None) == (frozenset(), 0)
    assert layout._camera_mode_entry_extension(case.snapshot, result) == (
        frozenset((case.ref.evidence_id,)),
        1,
    )


@pytest.mark.parametrize(
    "fault", ["state", "count", "events", "snapshot", "arbitrary_ids"]
)
def test_private_prefix_allowance_revalidates_constructed_values(layout, case, fault):
    result = verify(layout, case)
    snapshot = case.snapshot
    if fault == "state":
        result = replace(result, state="PASS")
    elif fault == "count":
        result = replace(result, prefix_event_count=result.prefix_event_count - 1)
    elif fault == "events":
        result = replace(result, events=())
    elif fault == "snapshot":
        snapshot = replace(snapshot, evidence=())
    else:
        result = frozenset((case.ref.evidence_id,))
    with pytest.raises(layout.CameraModeEntryLayoutError):
        layout._camera_mode_entry_extension(snapshot, result)


def test_retained_entry_without_transition_is_incomplete_not_repairable(layout, case):
    events = case.snapshot.committed_events[:-1]
    stages = list(case.snapshot.stages)
    stages[4] = V2StageSnapshot(STAGE_ORDER[4], S.PENDING, None, ())
    case.snapshot = replace(
        case.snapshot,
        committed_events=events,
        stages=tuple(stages),
        head=V2CommittedHead.build(case.snapshot.header, events),
    )
    result = verify(layout, case)
    assert result.state == "INCOMPLETE" and result.events == ()
    assert result.original_store_authenticated is False


@pytest.mark.parametrize(
    "mutation",
    (
        "duplicate_inventory",
        "extra_mode_record",
        "future_record",
        "missing_record",
        "wrong_retention",
        "wrong_digest",
        "wrong_payload_length",
        "extra_record_key",
        "wrong_header",
        "uncommitted_event",
        "wrong_head",
        "future_state",
        "prior_stage_blocked",
        "pending_entry_state",
        "wrong_entry_sequence",
        "wrong_entry_evidence_ids",
        "wrong_expected_review",
        "wrong_expected_identity",
        "forged_event_hash",
        "extra_event",
    ),
)
def test_changed_or_unbounded_suffix_is_rejected(layout, case, mutation):
    snapshot = case.snapshot
    if mutation in {"duplicate_inventory", "extra_mode_record", "future_record"}:
        extra = (
            case.ref
            if mutation == "duplicate_inventory"
            else reference(
                b"extra",
                mutation,
                STAGE_ORDER[5] if mutation == "future_record" else STAGE_ORDER[4],
            )
        )
        snapshot = replace(snapshot, evidence=(*snapshot.evidence, extra))
    elif mutation == "missing_record":
        snapshot = replace(
            snapshot,
            evidence=tuple(ref for ref in snapshot.evidence if ref != case.ref),
        )
    elif mutation == "wrong_retention":
        case.record["retention"] = "CACHED"
    elif mutation == "wrong_digest":
        case.record["evidence_sha256"] = "e" * 64
    elif mutation == "wrong_payload_length":
        case.record["reference"]["payload_bytes"] += 1
    elif mutation == "extra_record_key":
        case.record["allow"] = True
    elif mutation == "wrong_header":
        case.binding["header_sha256"] = "e" * 64
    elif mutation == "uncommitted_event":
        snapshot = replace(snapshot, uncommitted_events=snapshot.committed_events[-1:])
    elif mutation == "wrong_head":
        snapshot = replace(
            snapshot,
            head=V2CommittedHead.build(snapshot.header, snapshot.committed_events[:-1]),
        )
    elif mutation in {
        "future_state",
        "prior_stage_blocked",
        "pending_entry_state",
        "wrong_entry_sequence",
        "wrong_entry_evidence_ids",
    }:
        stages = list(snapshot.stages)
        index = (
            5
            if mutation == "future_state"
            else 3 if mutation == "prior_stage_blocked" else 4
        )
        changes = {
            "future_state": dict(state=S.WAITING_OPERATOR),
            "prior_stage_blocked": dict(state=S.BLOCKED),
            "pending_entry_state": dict(state=S.PENDING),
            "wrong_entry_sequence": dict(last_event_sequence=0),
            "wrong_entry_evidence_ids": dict(evidence_ids=()),
        }[mutation]
        stages[index] = replace(stages[index], **changes)
        snapshot = replace(snapshot, stages=tuple(stages))
    elif mutation in {"wrong_expected_review", "wrong_expected_identity"}:
        key = (
            "complete_review_event_sha256"
            if mutation == "wrong_expected_review"
            else "selected_identity_sha256"
        )
        case.binding[key] = "e" * 64
    elif mutation == "forged_event_hash":
        events = (
            *snapshot.committed_events[:-1],
            replace(snapshot.committed_events[-1], event_sha256="e" * 64),
        )
        snapshot = replace(
            snapshot,
            committed_events=events,
            head=V2CommittedHead.build(snapshot.header, events),
        )
    else:
        events = (*snapshot.committed_events, snapshot.committed_events[-1])
        snapshot = replace(
            snapshot,
            committed_events=events,
            head=V2CommittedHead.build(snapshot.header, events),
        )
    case.snapshot = snapshot
    with pytest.raises(layout.CameraModeEntryLayoutError):
        verify(layout, case)


@pytest.mark.parametrize(
    "change",
    (
        dict(stage=STAGE_ORDER[5]),
        dict(state=S.PASS),
        dict(previous_state=S.REVIEW_PENDING),
        dict(occurred_at_ns=49),
        dict(detail_code="CAMERA_MODE_ENTRY_" + "8" * 32),
        dict(previous_event_sha256="d" * 64),
        dict(evidence=()),
    ),
)
def test_coherently_rehashed_wrong_entry_event_is_rejected(layout, case, change):
    old = case.snapshot.committed_events[-1]
    fields = {
        key: getattr(old, key)
        for key in (
            "sequence",
            "stage",
            "previous_state",
            "state",
            "occurred_at_ns",
            "previous_event_sha256",
            "evidence",
            "detail_code",
        )
    }
    fields.update(change)
    event = V2JournalEvent.build(header=case.snapshot.header, **fields)
    events = (*case.snapshot.committed_events[:-1], event)
    case.snapshot = replace(
        case.snapshot,
        committed_events=events,
        head=V2CommittedHead.build(case.snapshot.header, events),
    )
    with pytest.raises(layout.CameraModeEntryLayoutError):
        verify(layout, case)
