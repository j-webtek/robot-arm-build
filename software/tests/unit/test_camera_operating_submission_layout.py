"""Complete-snapshot layout models; not M1 publication or native authentication.

Existing full modeled v16 predecessors are used unchanged. Only the new compact
submission's proposal/native assessment context is synthetic for structural tests.
The eventual original reader must authenticate those inputs independently.
"""

from copy import deepcopy
from dataclasses import replace
import json

import pytest

from rocell.application import camera_operating_submission_layout as module
from rocell.application.camera_operating_submission import (
    build_camera_operating_submission,
    camera_operating_submission_label,
    camera_operating_submission_event,
)
from rocell.application.camera_probe_preparation_layout import (
    _original_record,
    verify_camera_probe_preparation_layout,
)
from rocell.application.physical_camera_mode_entry_layout import (
    _camera_mode_entry_extension,
    verify_camera_mode_entry_layout,
)
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_v2 import V2StageState as S, V2CommittedHead
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_operating_submission import seed
from test_camera_probe_preparation_readback import (
    ready,
    received_ready,
    identity_ready,
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    empty_campaigns,
    prepare_reviewed,
    change_last_event,
)


_MODELED_LAYOUT_SEED = None


@pytest.fixture
def submitted(request, monkeypatch, seed):
    global _MODELED_LAYOUT_SEED
    # These are pure structural mutations of one immutable modeled history.
    # Build the expensive full predecessor once, then deep-copy only values:
    # no transaction, owner, path reader or currentness observation is cached.
    if _MODELED_LAYOUT_SEED is not None:
        return deepcopy(_MODELED_LAYOUT_SEED)
    ready = request.getfixturevalue("ready")
    entered, preparation, review = prepare_reviewed(ready, monkeypatch)
    state = ready[2]
    before = state["snapshot"]()
    entry = entered["camera_mode_entry"]["entry"]
    packages = {}
    for kind, subject in (("preparation", preparation), ("review", review)):
        matches = [
            ref for ref in before.evidence if ref.payload_sha256 == subject.sha256
        ]
        assert len(matches) == 1
        packages[matches[0].evidence_id] = dict(
            kind=kind,
            preparation_id=preparation.to_dict()["preparation_id"],
            record=_original_record(subject, matches[0]),
        )
    # This test intentionally models the new native context. It never claims
    # that these fictional subjects are present in the original campaign store.
    proposal = json.loads(seed["proposal_payload"])
    proposal["entry_binding"] = deepcopy(entry["document"]["binding"])
    proposal["subjects"]["entry_sha256"] = entry["evidence_sha256"]
    for key in ("source_sha256", "session_id"):
        proposal["probe_binding"][key] = proposal["entry_binding"][key]
    report = json.loads(seed["assessment_payload"])
    report["proposal_sha256"] = digest(canonical(proposal))
    report["preflight"]["proposal_sha256"] = report["proposal_sha256"]
    report["preflight_sha256"] = digest(canonical(report["preflight"]))
    report.update(
        session_id=before.header.session_id,
        header_sha256=before.header.header_sha256,
        journal_head_sha256=before.head.head_sha256,
    )
    binding = dict(
        **{
            k: proposal["entry_binding"][k]
            for k in ("source_sha256", "cell_id", "session_id", "header_sha256")
        },
        entry_sha256=entry["evidence_sha256"],
        probe_preparation_sha256=preparation.sha256,
        probe_review_sha256=review.sha256,
        journal_head_sha256=before.head.head_sha256,
        original_records_sha256=report["original_records_sha256"],
    )
    now = max(
        before.committed_events[-1].occurred_at_ns + 1, seed["recorded_at_utc_ns"]
    )
    subject = build_camera_operating_submission(
        **{k: seed[k] for k in ("submission_id", "operator_id")},
        recorded_at_utc_ns=now,
        binding=binding,
        proposal_payload=canonical(proposal),
        assessment_payload=canonical(report),
    )
    ref = state["add"](
        subject.payload,
        label=camera_operating_submission_label(seed["submission_id"]),
        stage=STAGE_ORDER[4],
    )
    partial = state["snapshot"]()
    state["advance"](
        S.REVIEW_PENDING,
        camera_operating_submission_event(seed["submission_id"]),
        (ref,),
        stage=STAGE_ORDER[4],
    )
    change_last_event(state, occurred_at_ns=now + 1)
    _MODELED_LAYOUT_SEED = dict(
        snapshot=state["snapshot"](),
        partial=partial,
        before=before,
        entry=entry,
        packages=packages,
        record=_original_record(subject, ref),
    )
    return deepcopy(_MODELED_LAYOUT_SEED)


def check(fixture, **changes):
    args = dict(
        snapshot=fixture["snapshot"],
        entry_record=fixture["entry"],
        probe_packages=fixture["packages"],
        record=fixture["record"],
    )
    args.update(changes)
    return module.verify_camera_operating_submission_layout(**args)


def test_closed_layout_retains_exact_original_prefix_and_no_approval(submitted):
    original = deepcopy(submitted)
    layout = check(submitted)
    assert layout.state == "SUBMITTED_REVIEW_REQUIRED"
    assert layout.original_store_authenticated is False
    assert layout.submission.to_dict() == submitted["record"]["document"]
    assert layout.events == submitted["snapshot"].committed_events[-1:]
    ids, count = _camera_mode_entry_extension(submitted["snapshot"], layout)
    assert len(ids) == 4 and count == 4
    assert ids == frozenset(
        ref.evidence_id
        for ref in submitted["snapshot"].evidence
        if ref.stage is STAGE_ORDER[4]
    )
    assert submitted == original
    assert all(row.state is S.PENDING for row in submitted["snapshot"].stages[5:])


def test_retained_record_without_event_is_incomplete_not_replayable(submitted):
    layout = check(submitted, snapshot=submitted["partial"])
    assert layout.state == "INCOMPLETE" and layout.events == ()
    assert submitted["partial"].stages[4].state is S.WAITING_OPERATOR
    ids, count = _camera_mode_entry_extension(submitted["partial"], layout)
    assert len(ids) == 4 and count == 3


def test_old_public_layouts_reject_both_partial_and_committed_successor(submitted):
    for snapshot in (submitted["partial"], submitted["snapshot"]):
        with pytest.raises(ValueError):
            verify_camera_probe_preparation_layout(
                snapshot, submitted["entry"], submitted["packages"]
            )
        with pytest.raises(ValueError):
            verify_camera_mode_entry_layout(
                snapshot,
                submitted["entry"],
                expected_entry_id=submitted["entry"]["document"]["entry_id"],
                expected_binding=submitted["entry"]["document"]["binding"],
            )
    # The genuine earlier snapshot still uses its original exact v16 contract.
    old = verify_camera_probe_preparation_layout(
        submitted["before"], submitted["entry"], submitted["packages"]
    )
    assert old.state == "REVIEWED_FOR_ADMISSION"


@pytest.mark.parametrize(
    "fault",
    [
        "missing",
        "duplicate",
        "unknown",
        "future",
        "wrong-row",
        "head",
        "uncited-event",
        "self-transition",
        "wrong-time",
        "wrong-code",
        "wrong-previous",
    ],
)
def test_changed_complete_snapshot_is_rejected(submitted, fault):
    snapshot = submitted["snapshot"]
    if fault == "missing":
        snapshot = replace(
            snapshot,
            evidence=tuple(
                ref
                for ref in snapshot.evidence
                if ref.evidence_id != submitted["record"]["reference"]["evidence_id"]
            ),
        )
    elif fault == "duplicate":
        snapshot = replace(
            snapshot, evidence=(*snapshot.evidence, snapshot.evidence[-1])
        )
    elif fault in ("unknown", "future"):
        ref = replace(
            snapshot.evidence[-1],
            evidence_id="evidence-" + "f" * 64,
            stage=STAGE_ORDER[5] if fault == "future" else STAGE_ORDER[4],
        )
        snapshot = replace(snapshot, evidence=(*snapshot.evidence, ref))
    elif fault == "wrong-row":
        rows = list(snapshot.stages)
        rows[4] = replace(rows[4], state=S.PASS)
        snapshot = replace(snapshot, stages=tuple(rows))
    elif fault == "head":
        snapshot = replace(snapshot, head=submitted["before"].head)
    else:
        event = snapshot.committed_events[-1]
        args = {
            "uncited-event": dict(evidence=()),
            "self-transition": dict(state=S.WAITING_OPERATOR),
            "wrong-time": dict(occurred_at_ns=1),
            "wrong-code": dict(detail_code="CAMERA_OPERATING_SUBMITTED_" + "f" * 32),
            "wrong-previous": dict(previous_event_sha256="f" * 64),
        }[fault]
        event = replace(event, **args)
        events = (*snapshot.committed_events[:-1], event)
        snapshot = replace(
            snapshot,
            committed_events=events,
            head=V2CommittedHead.build(snapshot.header, events),
        )
    with pytest.raises(ValueError):
        check(submitted, snapshot=snapshot)


@pytest.mark.parametrize(
    "fault", ["state", "events", "reference", "submission", "probe"]
)
def test_predecessor_allowance_revalidates_forged_frozen_layout(submitted, fault):
    layout = check(submitted)
    if fault == "state":
        object.__setattr__(layout, "state", "APPROVED")
    elif fault == "events":
        object.__setattr__(layout, "events", ())
    elif fault == "reference":
        object.__setattr__(layout, "reference", layout.probe.preparation_reference)
    elif fault == "submission":
        object.__setattr__(layout, "submission", layout.submission.to_dict())
    else:
        object.__setattr__(layout, "probe", {})
    with pytest.raises(ValueError):
        _camera_mode_entry_extension(submitted["snapshot"], layout)
