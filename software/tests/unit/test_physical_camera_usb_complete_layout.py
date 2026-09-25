"""Cheap MODELED layout tests, not heterogeneous reconstruction or M1 evidence.

All subjects and the predecessor are made up to exercise structural rules.
Their superficially positive verdicts must never be accepted by the original
owner without the independent full-series reconstruction and actual M1 audit.
"""

from copy import deepcopy
from dataclasses import FrozenInstanceError, replace
from pathlib import Path
import subprocess

import pytest

from rocell.application import physical_camera_usb_complete_layout as m
from rocell.application import physical_usb_complete_series as codec
from rocell.application.physical_camera_usb_complete_constants import usb_complete_event
from rocell.application.physical_onboarding_v2 import (
    V2SessionHeader,
    V2StageSnapshot,
    V2NextAction,
)


SID = "usbseries-" + "8" * 32
PID = "usbphase-" + "9" * 32
STAGE = m.STAGE_ORDER[3]


@pytest.fixture(autouse=True)
def no_effects(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("layout check attempted filesystem or process access")

    monkeypatch.setattr(Path, "open", denied)
    monkeypatch.setattr(Path, "read_bytes", denied)
    monkeypatch.setattr(subprocess, "Popen", denied)


def ref(raw, label, stage=STAGE):
    package = m.digest(label.encode("ascii"))
    return m.EvidenceReference(
        "evidence-" + package, stage, package, "b" * 64, m.digest(raw), len(raw)
    )


def case(event_count=3, role_count=3, rejected=False):
    header = V2SessionHeader.build(
        session_id="MODELED-session",
        cell_id="MODELED-cell",
        created_at_ns=1,
        source_binding_sha256="a" * 64,
        publication_durability="PORTABLE_UNQUALIFIED",
        durability_qualification_sha256="0" * 64,
    )
    binding = {
        key: ("a" * 64 if key.endswith("sha256") else "MODELED-" + key)
        for key in codec.qualification._BINDING
    }
    policy = codec.qualification.usb_identity_stage_policy()
    binding.update(
        session_id=header.session_id,
        cell_id=header.cell_id,
        header_sha256=header.header_sha256,
        stage_policy_sha256=policy.sha256,
        stage_catalog_sha256=policy.to_dict()["base_catalog_sha256"],
        stage_order_sha256=policy.to_dict()["canonical_stage_order_sha256"],
    )
    common = dict(series_id=SID, binding=binding, plan_sha256="c" * 64)
    phases = []
    for name in codec.PHASES:
        raw = ("MODELED-" + name).encode("ascii")
        phases.append(codec.qualification._manifest(name, raw, ref(raw, name)))
    series = codec.CompleteUsbSeries(
        m.canonical(codec._document("series", **common, phases=phases))
    )
    assessment = codec.CompleteUsbAssessment(
        m.canonical(
            codec._document(
                "assessment",
                **common,
                series_sha256=series.sha256,
                verdict=codec.ELIGIBLE,
                checks=[dict(check_id=key, passed=True) for key in codec.CHECK_IDS],
                missing_requirements=[],
                phases=[
                    dict(
                        phase=name,
                        phase_sha256=row["sha256"],
                        status=status,
                        missing_checks=[],
                    )
                    for name, row, status in zip(
                        codec.PHASES, phases, codec.PHASE_STATUS
                    )
                ],
                comparisons=[
                    dict(field=field, status="MATCHED")
                    for field in codec.reboot.COMPARISON_FIELDS
                ],
            )
        )
    )
    review = codec.CompleteUsbReview(
        m.canonical(
            codec._document(
                "review",
                **common,
                series_sha256=series.sha256,
                assessment_sha256=assessment.sha256,
                verdict="BLOCKED" if rejected else codec.REVIEW_ELIGIBLE,
                decision="REJECT" if rejected else "ACKNOWLEDGE_EXACT",
                reviewer_id="MODELED-reviewer",
                review_launch_id="MODELED-review-launch",
                reviewed_at_utc_ns=350,
                distinct_operator_labels=True,
            )
        )
    )
    subjects = (series, assessment, review)
    references = {
        subject.role: ref(subject.payload, "MODELED-" + subject.role)
        for subject in subjects
    }
    packages = {
        references[subject.role].evidence_id: dict(
            kind=subject.role,
            series_id=SID,
            record=dict(
                document=subject.to_dict(),
                evidence_sha256=subject.sha256,
                reference=references[subject.role].to_dict(),
                retention="M1_FULL_BYTES_READ_BACK",
            ),
        )
        for subject in subjects[:role_count]
    }
    phase_ref = ref(b"MODELED NOT A REAL REBOOT PHASE", "MODELED-phase")
    events = []
    base_refs = []

    def event(stage, previous, state, time, evidence, detail):
        made = m.V2JournalEvent.build(
            header=header,
            sequence=len(events),
            stage=stage,
            previous_state=previous,
            state=state,
            occurred_at_ns=time,
            previous_event_sha256=events[-1].event_sha256 if events else "0" * 64,
            evidence=tuple(sorted(evidence, key=lambda r: r.evidence_id)),
            detail_code=detail,
        )
        events.append(made)

    S = m.V2StageState
    for index, stage in enumerate(m.STAGE_ORDER[:3]):
        item = ref(b"MODELED stage reference", "MODELED-stage-" + str(index), stage)
        base_refs.append(item)
        for offset, (old, new) in enumerate(
            (
                (S.PENDING, S.WAITING_OPERATOR),
                (S.WAITING_OPERATOR, S.REVIEW_PENDING),
                (S.REVIEW_PENDING, S.PASS),
            )
        ):
            event(stage, old, new, 2 + index * 3 + offset, (item,), "MODELED_PREFIX")
    event(STAGE, S.PENDING, S.WAITING_OPERATOR, 90, (phase_ref,), "MODELED_PREFIX")
    event(
        STAGE,
        S.WAITING_OPERATOR,
        S.BLOCKED,
        100,
        (phase_ref,),
        m.usb_reboot_event("RETAINED", PID),
    )
    original_count = len(events)
    suffix = (
        (S.BLOCKED, S.WAITING_OPERATOR, 200, (phase_ref,), "ASSESSMENT_REQUESTED"),
        (
            S.WAITING_OPERATOR,
            S.REVIEW_PENDING,
            300,
            tuple(references[role] for role in ("series", "assessment")),
            "ASSESSMENT_RETAINED",
        ),
        (
            S.REVIEW_PENDING,
            S.BLOCKED if rejected else S.PASS,
            400,
            tuple(references.values()),
            "REVIEWED",
        ),
    )
    for old, new, when, evidence, kind in suffix[:event_count]:
        event(STAGE, old, new, when, evidence, usb_complete_event(kind, SID))
    stages = tuple(
        V2StageSnapshot(
            stage,
            (S.PASS if index < 3 else events[-1].state if index == 3 else S.PENDING),
            (index * 3 + 2 if index < 3 else len(events) - 1 if index == 3 else None),
            tuple(
                r.evidence_id for e in events if e.stage is stage for r in e.evidence
            ),
        )
        for index, stage in enumerate(m.STAGE_ORDER)
    )
    snapshot = m.V2SessionSnapshot(
        header,
        stages,
        tuple(events),
        (),
        tuple(
            sorted(
                (
                    *base_refs,
                    phase_ref,
                    *(references[subject.role] for subject in subjects[:role_count]),
                ),
                key=lambda r: r.evidence_id,
            )
        ),
        m.V2CommittedHead.build(header, tuple(events)),
        V2NextAction("MODELED_ONLY", STAGE, events[-1].state, True),
    )
    kwargs = dict(
        expected_header_sha256=header.header_sha256,
        expected_binding=binding,
        predecessor_phase_id=PID,
        predecessor_reference=phase_ref,
        predecessor_finished_at_utc_ns=99,
    )
    return snapshot, packages, kwargs, original_count


def verify(current):
    snapshot, packages, kwargs, _ = current
    return m.verify_complete_usb_suffix_layout(snapshot, packages, **kwargs)


@pytest.mark.parametrize(
    "event_count,role_count", [(1, 0), (1, 1), (1, 2), (2, 2), (2, 3), (3, 3)]
)
def test_each_complete_or_partly_published_prefix_is_diagnostic_only(
    event_count, role_count
):
    current = case(event_count, role_count)
    before = deepcopy(current)
    result = verify(current)
    assert result.prefix_event_count == current[-1]
    assert len(result.events) == event_count and len(result.records) == role_count
    assert result.original_store_authenticated is False
    assert current == before
    with pytest.raises(FrozenInstanceError):
        result.series_id = SID


@pytest.mark.parametrize(
    "event_count,role_count", [(1, 3), (2, 0), (2, 1), (3, 0), (3, 1), (3, 2)]
)
def test_roles_cannot_arrive_in_the_wrong_publication_boundary(event_count, role_count):
    with pytest.raises(m.CompleteUsbLayoutError):
        verify(case(event_count, role_count))


def test_rejected_review_has_blocked_stage_not_pass():
    current = case(rejected=True)
    result = verify(current)
    assert result.events[-1].state is m.V2StageState.BLOCKED
    assert not result.original_store_authenticated


@pytest.mark.parametrize(
    "fault",
    [
        "wrong-header",
        "pending-journal",
        "changed-head",
        "duplicate-reference",
        "missing-inventory",
        "changed-source",
        "wrong-stage",
        "extra-field",
        "export-instead-of-original",
        "changed-series",
        "mismatched-evidence-hash",
        "aliased-kind",
        "missing-first-role",
        "reused-predecessor",
        "wrong-predecessor",
        "late-predecessor",
        "bool-time",
    ],
)
def test_bad_or_aliased_original_layout_is_refused(fault):
    snapshot, packages, kwargs, count = case()
    first_id = next(iter(packages))
    package = packages[first_id]
    if fault == "wrong-header":
        kwargs["expected_header_sha256"] = "f" * 64
    elif fault == "pending-journal":
        snapshot = replace(
            snapshot, uncommitted_events=(snapshot.committed_events[-1],)
        )
    elif fault == "changed-head":
        snapshot = replace(snapshot, head=replace(snapshot.head, head_sha256="f" * 64))
    elif fault == "duplicate-reference":
        snapshot = replace(
            snapshot, evidence=snapshot.evidence + (snapshot.evidence[0],)
        )
    elif fault == "missing-inventory":
        snapshot = replace(
            snapshot,
            evidence=tuple(
                ref for ref in snapshot.evidence if ref.evidence_id != first_id
            ),
        )
    elif fault == "changed-source":
        kwargs["expected_binding"] = dict(
            kwargs["expected_binding"], source_sha256="f" * 64
        )
    elif fault == "wrong-stage":
        package["record"]["reference"]["stage"] = m.STAGE_ORDER[0].value
    elif fault == "extra-field":
        package["record"]["success"] = True
    elif fault == "export-instead-of-original":
        package["record"]["retention"] = "EXPORTED_COPY"
    elif fault == "changed-series":
        package["series_id"] = "usbseries-" + "a" * 32
    elif fault == "mismatched-evidence-hash":
        package["record"]["evidence_sha256"] = "f" * 64
    elif fault == "aliased-kind":
        packages[list(packages)[1]]["kind"] = "series"
    elif fault == "missing-first-role":
        del packages[first_id]
    elif fault == "reused-predecessor":
        kwargs["predecessor_reference"] = m._parse_evidence_reference(
            package["record"]["reference"]
        )
    elif fault == "wrong-predecessor":
        kwargs["predecessor_phase_id"] = "usbphase-" + "a" * 32
    elif fault == "late-predecessor":
        kwargs["predecessor_finished_at_utc_ns"] = 200
    elif fault == "bool-time":
        kwargs["predecessor_finished_at_utc_ns"] = True
    with pytest.raises(m.CompleteUsbLayoutError):
        verify((snapshot, packages, kwargs, count))


@pytest.mark.parametrize(
    "fault",
    [
        "first-kind",
        "another-id",
        "same-state",
        "wrong-citations",
        "reversed-time",
        "broken-link",
        "wrong-session",
        "wrong-sequence",
        "rejected-as-pass",
    ],
)
def test_rehashed_suffix_event_changes_are_still_rejected(fault):
    snapshot, packages, kwargs, count = case(rejected=fault == "rejected-as-pass")
    events = list(snapshot.committed_events)
    index = count if fault == "first-kind" else len(events) - 1
    old = events[index]
    changes = {}
    if fault == "first-kind":
        changes["detail_code"] = usb_complete_event("REVIEWED", SID)
    elif fault == "another-id":
        changes["detail_code"] = usb_complete_event("REVIEWED", "usbseries-" + "f" * 32)
    elif fault == "same-state":
        changes["previous_state"] = old.state
    elif fault == "wrong-citations":
        changes["evidence"] = old.evidence[:1]
    elif fault == "reversed-time":
        changes["occurred_at_ns"] = 299
    elif fault == "broken-link":
        changes["previous_event_sha256"] = "f" * 64
    elif fault == "wrong-session":
        changes["session_id"] = "another-session"
    elif fault == "wrong-sequence":
        changes["sequence"] = old.sequence + 1
    elif fault == "rejected-as-pass":
        changes["state"] = m.V2StageState.PASS
    made = replace(old, **changes)
    # V2's canonical event hash includes its own newline convention.
    from rocell.application.physical_onboarding_v2 import _stable_hash

    events[index] = replace(made, event_sha256=_stable_hash(made.core_dict()))
    snapshot = replace(
        snapshot,
        committed_events=tuple(events),
        head=m.V2CommittedHead.build(snapshot.header, tuple(events)),
    )
    with pytest.raises(m.CompleteUsbLayoutError):
        verify((snapshot, packages, kwargs, count))


@pytest.mark.parametrize(
    "fault",
    [
        "fourth-event",
        "unrelated-trailing-event",
        "stage-five-started",
        "stage-order-changed",
        "stage-state-mismatch",
    ],
)
def test_no_extra_suffix_or_later_stage_is_silently_ignored(fault):
    snapshot, packages, kwargs, count = case()
    if fault in {"fourth-event", "unrelated-trailing-event"}:
        previous = snapshot.committed_events[-1]
        event = m.V2JournalEvent.build(
            header=snapshot.header,
            sequence=previous.sequence + 1,
            stage=STAGE,
            previous_state=previous.state,
            state=m.V2StageState.INVALIDATED,
            occurred_at_ns=500,
            previous_event_sha256=previous.event_sha256,
            evidence=previous.evidence,
            detail_code=(
                usb_complete_event("REVIEWED", SID)
                if fault == "fourth-event"
                else "UNRELATED_EVENT"
            ),
        )
        events = snapshot.committed_events + (event,)
        snapshot = replace(
            snapshot,
            committed_events=events,
            head=m.V2CommittedHead.build(snapshot.header, events),
        )
    else:
        stages = list(snapshot.stages)
        if fault == "stage-five-started":
            stages[4] = replace(stages[4], state=m.V2StageState.WAITING_OPERATOR)
        elif fault == "stage-order-changed":
            stages[0], stages[1] = stages[1], stages[0]
        else:
            stages[3] = replace(stages[3], state=m.V2StageState.BLOCKED)
        snapshot = replace(snapshot, stages=tuple(stages))
    with pytest.raises(m.CompleteUsbLayoutError):
        verify((snapshot, packages, kwargs, count))


@pytest.mark.parametrize(
    "role,field,value",
    [
        ("series", "series_id", "usbseries-" + "f" * 32),
        ("assessment", "series_sha256", "f" * 64),
        ("assessment", "plan_sha256", "f" * 64),
        ("review", "assessment_sha256", "f" * 64),
        ("review", "series_sha256", "f" * 64),
        ("review", "plan_sha256", "f" * 64),
        ("review", "reviewed_at_utc_ns", 299),
    ],
)
def test_rehashed_subjects_still_need_exact_cross_role_bindings(role, field, value):
    snapshot, packages, kwargs, count = case()
    package = next(row for row in packages.values() if row["kind"] == role)
    record = package["record"]
    old_ref = m._parse_evidence_reference(record["reference"])
    record["document"][field] = value
    raw = m.canonical(record["document"])
    newer = replace(old_ref, payload_sha256=m.digest(raw), payload_bytes=len(raw))
    record.update(evidence_sha256=newer.payload_sha256, reference=newer.to_dict())
    # Keep every superficial hash/link consistent so the semantic layout check,
    # not just a stale payload hash, has to reject this modeled substitution.
    from rocell.application.physical_onboarding_v2 import _stable_hash

    events = []
    for old in snapshot.committed_events:
        event = replace(
            old,
            evidence=tuple(newer if item == old_ref else item for item in old.evidence),
            previous_event_sha256=events[-1].event_sha256 if events else "0" * 64,
        )
        events.append(replace(event, event_sha256=_stable_hash(event.core_dict())))
    snapshot = replace(
        snapshot,
        evidence=tuple(
            newer if item == old_ref else item for item in snapshot.evidence
        ),
        committed_events=tuple(events),
        head=m.V2CommittedHead.build(snapshot.header, tuple(events)),
    )
    with pytest.raises(m.CompleteUsbLayoutError):
        verify((snapshot, packages, kwargs, count))
