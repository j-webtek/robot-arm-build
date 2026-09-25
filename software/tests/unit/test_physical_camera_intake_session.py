"""Original M1 supplementary intake, never received-hardware qualification.

Modeled scopes use real V2 events and pure codecs. Separate isolated NTFS cases
retain original file bytes and reopen without any inbox, native or device call.
"""

from contextlib import contextmanager
from dataclasses import replace
import os
import threading
import time

import pytest

from rocell.application import physical_camera_session as module
from rocell.application import physical_onboarding_v2 as v2
from rocell.application.commissioning_camera_persistence import (
    physical_camera_source_binding,
)
from rocell.application.physical_intake_notebook import PhysicalIntakeNotebook
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_physical_camera_session_readback import generate, model, no_devices, workspace
from test_physical_camera_session import (
    CELL,
    SESSION,
    SOURCE,
    LAUNCH,
    perform,
    session_fixture,
)
from test_physical_camera_source_workflow_readback import collect_chain

COLLECTION = "intake-" + "1" * 32
SECOND = "intake-" + "2" * 32
RAW = b"Explicitly unknown. Test-only document; no hardware measurement.\n"
SOURCE_CODES = (
    "CAMERA_PREREQUISITES_REQUESTED",
    "WORKSPACE_SOURCES_ASSESSMENT_SAVED",
    "WORKSPACE_SOURCES_REVIEWED_BLOCKED",
)


def label(kind, collection=COLLECTION, index=0):
    return f"physical-intake-{kind}-v1:{collection}" + (
        f":{index:02}" if kind == "original" else ""
    )


def code(phase, collection=COLLECTION):
    return f"PHYSICAL_INTAKE_{phase}_" + collection.removeprefix("intake-").upper()


def read(owner, header, **kwargs):
    return owner.read_original_source_workflow(
        expected_header_sha256=header,
        cancellation=kwargs.pop("cancellation", threading.Event()),
        progress=kwargs.pop("progress", lambda _: None),
        **kwargs,
    )


def notebook(prerequisites):
    result = PhysicalIntakeNotebook.start(prerequisites, launch_session_id=LAUNCH)
    for row in result.to_dict()["rows"]:
        result = result.record(
            record_id=row["record_id"],
            observation_status="UNKNOWN",
            observed_value="Hardware not received; no measurement.",
            method="Modeled operator note only.",
            evidence_note="Test-only explanatory original.",
            operator_id="intake-operator",
            recorded_at_ns=10000,
        )
    return result


def submission(
    prerequisites,
    header,
    raw_ref,
    inventory,
    *,
    collection=COLLECTION,
    predecessor=None,
):
    from rocell.application.physical_intake_submission import (
        IntakeAttachment,
        IntakeRowAttachment,
        build_physical_intake_submission,
    )

    return build_physical_intake_submission(
        prerequisites,
        notebook(prerequisites),
        cell_id=CELL,
        header_sha256=header,
        collection_id=collection,
        operator_id="intake-operator",
        submitted_at_ns=(
            11000
            if predecessor is None
            else predecessor.to_dict()["submitted_at_ns"] + 2000
        ),
        attachments=(IntakeAttachment(raw_ref, "unknown.txt", "text/plain"),),
        row_attachments=(IntakeRowAttachment("INT-001", raw_ref.evidence_id),),
        evidence_inventory=tuple(inventory),
        predecessor=predecessor,
    )


@pytest.fixture
def intake_model(model, monkeypatch):
    owner, prerequisites, state = model
    header = v2.V2SessionHeader.build(
        session_id=SESSION,
        cell_id=CELL,
        created_at_ns=1000,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        publication_durability=v2.WINDOWS_NTFS_QUALIFIED,
        durability_qualification_sha256="8" * 64,
    )
    events = []

    def advance(next_state, detail_code, refs=(), *, sort=True):
        refs = (
            tuple(sorted(refs, key=lambda ref: ref.evidence_id))
            if sort
            else tuple(refs)
        )
        events.append(
            v2.V2JournalEvent.build(
                header=header,
                sequence=len(events),
                stage=STAGE_ORDER[0],
                previous_state=events[-1].state if events else v2.V2StageState.PENDING,
                state=next_state,
                occurred_at_ns=2000 + len(events),
                previous_event_sha256=events[-1].event_sha256 if events else "0" * 64,
                evidence=refs,
                detail_code=detail_code,
            )
        )

    def snapshot():
        states = [events[-1].state, *([v2.V2StageState.PENDING] * 14)]
        cited = tuple(ref.evidence_id for event in events for ref in event.evidence)
        return v2.V2SessionSnapshot(
            header,
            tuple(
                v2.V2StageSnapshot(
                    stage,
                    states[i],
                    len(events) - 1 if not i else None,
                    cited if not i else (),
                )
                for i, stage in enumerate(STAGE_ORDER)
            ),
            tuple(events),
            (),
            tuple(sorted(state["references"], key=lambda ref: ref.evidence_id)),
            v2.V2CommittedHead.build(header, events),
            v2._derive_next_action(states),
        )

    advance(v2.V2StageState.WAITING_OPERATOR, SOURCE_CODES[0])
    artifacts = collect_chain(prerequisites, header.header_sha256, monkeypatch)
    source_refs = {
        role: state["add"](artifact.payload, label=f"workspace-source-{role}-v1")
        for role, artifact in artifacts.items()
    }
    advance(
        v2.V2StageState.REVIEW_PENDING,
        SOURCE_CODES[1],
        [source_refs[r] for r in ("receipt", "assessment")],
        sort=False,
    )
    advance(
        v2.V2StageState.BLOCKED, SOURCE_CODES[2], list(source_refs.values()), sort=False
    )
    store = owner._store
    original_scope, original_verification = store.stage_transaction, store.verification

    @contextmanager
    def scope(*args, **kwargs):
        with original_scope(*args, **kwargs) as tx:
            old = tx.snapshot
            tx.snapshot = snapshot
            try:
                yield tx
            finally:
                tx.snapshot = old

    def verification(session):
        result = original_verification(session)
        result.session_header_sha256 = header.header_sha256
        result.session_head_sha256 = snapshot().head.head_sha256
        if state["verification_calls"] > 1 and state["after_change"]:
            setattr(result, state["after_change"], "9" * 64)
        return result

    store.stage_transaction, store.verification = scope, verification
    state.update(
        snapshot=snapshot,
        advance=advance,
        events=events,
        header=header,
        store=store,
        source_refs=source_refs,
        source_artifacts=artifacts,
    )
    return owner, prerequisites, state


def start(state, collection=COLLECTION, previous=None):
    refs = state["source_refs"] if previous is None else previous
    state["advance"](
        v2.V2StageState.WAITING_OPERATOR,
        code("STARTED", collection),
        list(refs.values()),
    )


def complete(
    intake_model,
    *,
    reviewed=False,
    review_uncommitted=False,
    collection=COLLECTION,
    predecessor=None,
    previous=None,
    reused=None,
):
    from rocell.application.physical_intake_submission import (
        assess_physical_intake_submission,
        review_physical_intake_submission,
    )

    _, prerequisites, state = intake_model
    start(state, collection, previous)
    raw_ref = reused or state["add"](
        RAW, label=label("original", collection), media="text/plain"
    )
    item = submission(
        prerequisites,
        state["header"].header_sha256,
        raw_ref,
        state["references"],
        collection=collection,
        predecessor=predecessor,
    )
    assessment = assess_physical_intake_submission(item)
    records = {"submission": item, "assessment": assessment}
    refs = {
        role: state["add"](artifact.payload, label=label(role, collection))
        for role, artifact in records.items()
    }
    state["advance"](
        v2.V2StageState.REVIEW_PENDING,
        code("SUBMITTED", collection),
        [raw_ref, *refs.values()],
    )
    if reviewed or review_uncommitted:
        review = review_physical_intake_submission(
            item,
            assessment,
            reviewer_id="intake-reviewer",
            review_launch_id=LAUNCH,
            reviewed_at_ns=12000,
            decision="ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW",
        )
        records["review"] = review
        refs["review"] = state["add"](review.payload, label=label("review", collection))
    if reviewed:
        state["advance"](
            v2.V2StageState.BLOCKED,
            code("REVIEWED", collection),
            [raw_ref, *refs.values()],
        )
    return records, refs, raw_ref


@pytest.mark.parametrize("with_raw", [False, True])
def test_started_partial_collection_is_retained_without_constructing_submission(
    intake_model, with_raw, monkeypatch
):
    owner, _, state = intake_model
    start(state)
    if with_raw:
        state["add"](RAW, label=label("original"), media="text/plain")
    from rocell.application import physical_intake_submission as codec

    monkeypatch.setattr(
        codec,
        "build_physical_intake_submission",
        lambda *a, **k: pytest.fail("readback replay"),
    )
    result = read(owner, state["header"].header_sha256)
    assert result["schema"] == module.SOURCE_WORKFLOW_INTAKE_SCHEMA
    assert (
        result["state"] == "WAITING_OPERATOR"
        and result["original_source_state"] == "BLOCKED"
    )
    current = result["intake_collections"][0]
    assert current["state"] == "INCOMPLETE"
    assert current["submission"] is current["assessment"] is current["review"] is None
    assert len(current["attachments"]) == int(with_raw)
    assert RAW not in canonical(result)
    assert state["enters"] == state["exits"] == 1


@pytest.mark.parametrize(
    "reviewed,uncommitted,expected",
    [
        (False, False, "REVIEW_PENDING"),
        (False, True, "REVIEW_RETAINED_NOT_COMMITTED"),
        (True, False, "REVIEWED_BLOCKED"),
    ],
)
def test_exact_complete_collection_preserves_full_roles_but_only_raw_descriptors(
    intake_model, reviewed, uncommitted, expected
):
    owner, _, state = intake_model
    records, refs, raw_ref = complete(
        intake_model, reviewed=reviewed, review_uncommitted=uncommitted
    )
    before = canonical(state["snapshot"]().to_verification_dict())
    result = read(owner, state["header"].header_sha256)
    current = result["intake_collections"][0]
    assert current["state"] == expected
    assert current["attachments"] == [
        {
            "label": label("original"),
            "index": 0,
            "media_type": "text/plain",
            "evidence_sha256": digest(RAW),
            "retention": "M1_FULL_BYTES_READ_BACK",
            "reference": raw_ref.to_dict(),
        }
    ]
    for role, artifact in records.items():
        assert canonical(current[role]["document"]) == artifact.payload
        assert current[role]["reference"] == refs[role].to_dict()
    assert canonical(state["snapshot"]().to_verification_dict()) == before
    assert RAW not in canonical(result)
    assert owner.view()["physical_authority"] is False
    current["attachments"][0]["reference"]["payload_bytes"] = 999
    assert (
        owner.retained_source_workflow()["intake_collections"][0]["attachments"][0][
            "reference"
        ]
        == raw_ref.to_dict()
    )


def test_append_only_successor_reuses_exact_original_reference(intake_model):
    owner, _, state = intake_model
    first, first_refs, raw_ref = complete(intake_model, reviewed=True)
    second, _, _ = complete(
        intake_model,
        collection=SECOND,
        predecessor=first["submission"],
        previous=first_refs,
        reused=raw_ref,
    )
    result = read(owner, state["header"].header_sha256)
    assert len(result["intake_collections"]) == 2
    assert result["intake_collections"][0]["state"] == "REVIEWED_BLOCKED"
    assert result["intake_collections"][1]["state"] == "REVIEW_PENDING"
    assert (
        result["intake_collections"][1]["submission"]["document"]
        == second["submission"].to_dict()
    )
    assert result["intake_collections"][1]["attachments"][0]["label"] == label(
        "original"
    )


@pytest.mark.parametrize("limit", ["references", "bytes"])
def test_raw_inventory_limits_apply_before_any_payload_read(intake_model, limit):
    owner, _, state = intake_model
    start(state)
    if limit == "references":
        for _ in range(module.MAX_READBACK_STAGE_REFERENCES):
            state["add"](RAW, label=label("original"), media="text/plain")
    else:
        ref = state["add"](RAW, label=label("original"), media="text/plain")
        state["references"][-1] = replace(
            ref, payload_bytes=module.MAX_READBACK_STAGE_BYTES + 1
        )
    with pytest.raises(module.PhysicalCameraSessionError, match="READBACK_LIMIT"):
        read(owner, state["header"].header_sha256)
    assert state["reads"] == 0 and owner.retained_source_workflow() is None


@pytest.mark.parametrize(
    "fault",
    [
        "duplicate-index",
        "index-gap",
        "unknown-label",
        "wrong-media",
        "payload-drift",
        "orphan-collection",
        "source-prefix",
        "citation-order",
        "missing-citation",
        "unfinished-predecessor",
    ],
)
def test_invalid_or_ambiguous_collection_is_held_without_replay(intake_model, fault):
    owner, _, state = intake_model
    if fault in {"citation-order", "missing-citation", "unfinished-predecessor"}:
        complete(intake_model)
    else:
        start(state)
    if fault == "duplicate-index":
        state["add"](RAW, label=label("original"), media="text/plain")
        state["add"](RAW, label=label("original"), media="text/plain")
    elif fault == "index-gap":
        state["add"](RAW, label=label("original", index=1), media="text/plain")
    elif fault in {
        "unknown-label",
        "wrong-media",
        "payload-drift",
        "orphan-collection",
    }:
        ref = state["add"](
            RAW,
            label=label(
                "original", SECOND if fault == "orphan-collection" else COLLECTION
            )
            + (":extra" if fault == "unknown-label" else ""),
            media=(
                "application/octet-stream" if fault == "wrong-media" else "text/plain"
            ),
        )
        if fault == "payload-drift":
            state["payloads"][ref.evidence_id] = b"changed"
    elif fault == "source-prefix":
        state["events"][0] = replace(
            state["events"][0], detail_code="UNSUPPORTED_SOURCE_OPEN"
        )
    elif fault in {"citation-order", "missing-citation"}:
        event = state["events"][-1]
        refs = (
            tuple(reversed(event.evidence))
            if fault == "citation-order"
            else event.evidence[1:]
        )
        state["events"][-1] = replace(event, evidence=refs)
    else:
        state["advance"](v2.V2StageState.BLOCKED, code("REVIEWED"), ())
        start(state, SECOND)
    with pytest.raises(module.PhysicalCameraSessionError):
        read(owner, state["header"].header_sha256)
    assert owner.view()["status"] == "HELD" and owner.retained_source_workflow() is None


@pytest.mark.parametrize(
    "fault", ["lease-exit", "coherence", "late-stop", "late-source", "late-deadline"]
)
def test_late_failure_preserves_verified_original_intake_only_as_historical(
    intake_model, fault
):
    owner, _, state = intake_model
    complete(intake_model)
    cancellation = threading.Event()
    if fault == "lease-exit":
        state["exit_failure"] = True
    if fault == "coherence":
        state["after_change"] = "session_head_sha256"

    def progress(message):
        if "finished" in message:
            if fault == "late-stop":
                cancellation.set()
            if fault == "late-source":
                state["source"] = "f" * 64
            if fault == "late-deadline":
                state["now"] += module.DIAGNOSTIC_TIMEOUT_NS

    with pytest.raises(module.PhysicalCameraSessionError):
        read(
            owner,
            state["header"].header_sha256,
            cancellation=cancellation,
            progress=progress,
        )
    retained = owner.retained_source_workflow()
    assert retained["intake_collections"][0]["state"] == "REVIEW_PENDING"
    assert owner.view()["status"] == "HELD" and owner._store is None
    assert RAW not in canonical(retained)


@pytest.mark.parametrize("part", ["submission", "assessment", "review"])
def test_changed_full_subject_is_rejected_even_when_reference_hash_is_updated(
    intake_model, part
):
    owner, _, state = intake_model
    records, refs, _ = complete(intake_model, reviewed=True)
    document = records[part].to_dict()
    document["binding"]["header_sha256"] = "f" * 64
    raw = canonical(document)
    old = refs[part]
    replacement = replace(old, payload_sha256=digest(raw), payload_bytes=len(raw))
    state["references"][state["references"].index(old)] = replacement
    state["payloads"][old.evidence_id] = raw
    # Update modeled journal citations too, so the actual subject codec rather
    # than a stale reference catches the forged original context.
    state["events"][:] = [
        replace(
            event,
            evidence=tuple(
                replacement if ref == old else ref for ref in event.evidence
            ),
        )
        for event in state["events"]
    ]
    with pytest.raises(module.PhysicalCameraSessionError, match="INTAKE_CHAIN"):
        read(owner, state["header"].header_sha256)


@pytest.mark.parametrize("phase", ["submission-only", "assessment-before-event"])
def test_complete_document_before_journal_commit_stays_incomplete(intake_model, phase):
    from rocell.application.physical_intake_submission import (
        assess_physical_intake_submission,
    )

    owner, prerequisites, state = intake_model
    start(state)
    raw_ref = state["add"](RAW, label=label("original"), media="text/plain")
    item = submission(
        prerequisites, state["header"].header_sha256, raw_ref, state["references"]
    )
    state["add"](item.payload, label=label("submission"))
    if phase == "assessment-before-event":
        state["add"](
            assess_physical_intake_submission(item).payload, label=label("assessment")
        )
    result = read(owner, state["header"].header_sha256)
    assert result["intake_collections"][0]["state"] == "INCOMPLETE"
    assert result["state"] == "WAITING_OPERATOR"


@pytest.mark.skipif(os.name != "nt", reason="isolated actual Windows NTFS storage")
@pytest.mark.parametrize("completed", [False, True])
def test_actual_original_intake_bytes_reopen_without_inbox_or_replay(
    workspace, monkeypatch, completed
):
    from rocell.application.physical_intake_submission import (
        assess_physical_intake_submission,
        review_physical_intake_submission,
    )

    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    prerequisites = generate(workspace)
    owner = session_fixture(workspace)
    initial = perform(owner)
    header = initial["verification"]["session"]["header_sha256"]
    sources = collect_chain(prerequisites, header, monkeypatch)
    # This temporary input is not an observation or the production inbox. It
    # is deleted before restart; only original M1 bytes may be read afterward.
    inbox = workspace / "test-input.txt"
    inbox.write_bytes(RAW)
    with owner.stage_transaction(
        expected_challenge_sha256=initial["verification"]["challenge_sha256"]
    ) as tx:

        def commit(state, detail, references=()):
            return tx.commit_stage_state(
                STAGE_ORDER[0],
                state,
                occurred_at_ns=time.time_ns(),
                detail_code=detail,
                expected_head_sha256=tx.snapshot().head.head_sha256,
                evidence=tuple(sorted(references, key=lambda ref: ref.evidence_id)),
            )

        def store(payload, name, media="application/json"):
            ref = tx.store_evidence(
                STAGE_ORDER[0],
                payload,
                label=name,
                media_type=media,
                captured_at_ns=time.time_ns(),
                expected_head_sha256=tx.snapshot().head.head_sha256,
            )
            assert tx.read_stage_evidence(ref) == payload
            return ref

        commit(v2.V2StageState.WAITING_OPERATOR, SOURCE_CODES[0])
        prerequisite_ref = store(prerequisites.payload, module.PREREQUISITE_LABEL)
        source_refs = {
            role: store(sources[role].payload, f"workspace-source-{role}-v1")
            for role in ("receipt", "assessment")
        }
        commit(v2.V2StageState.REVIEW_PENDING, SOURCE_CODES[1], source_refs.values())
        source_refs["review"] = store(
            sources["review"].payload, "workspace-source-review-v1"
        )
        commit(v2.V2StageState.BLOCKED, SOURCE_CODES[2], source_refs.values())
        commit(v2.V2StageState.WAITING_OPERATOR, code("STARTED"), source_refs.values())
        original_ref = store(inbox.read_bytes(), label("original"), "text/plain")
        records = {}
        if completed:
            item = submission(
                prerequisites, header, original_ref, tx.snapshot().evidence
            )
            assessment = assess_physical_intake_submission(item)
            records = {"submission": item, "assessment": assessment}
            refs = {
                role: store(artifact.payload, label(role))
                for role, artifact in records.items()
            }
            commit(
                v2.V2StageState.REVIEW_PENDING,
                code("SUBMITTED"),
                [original_ref, *refs.values()],
            )
            records["review"] = review_physical_intake_submission(
                item,
                assessment,
                reviewer_id="intake-reviewer",
                review_launch_id=LAUNCH,
                reviewed_at_ns=12000,
                decision="ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW",
            )
            refs["review"] = store(records["review"].payload, label("review"))
            commit(
                v2.V2StageState.BLOCKED,
                code("REVIEWED"),
                [original_ref, *refs.values()],
            )
    inbox.unlink()
    reopened = session_fixture(workspace)
    before = perform(reopened, "refresh")
    result = read(reopened, header)
    current = result["intake_collections"][0]
    assert current["state"] == ("REVIEWED_BLOCKED" if completed else "INCOMPLETE")
    assert result["original_source_state"] == "BLOCKED"
    assert result["prerequisites"]["reference"] == prerequisite_ref.to_dict()
    assert current["attachments"][0]["reference"] == original_ref.to_dict()
    for role, artifact in records.items():
        assert canonical(current[role]["document"]) == artifact.payload
    assert not inbox.exists() and RAW not in canonical(result)
    after = reopened.view()
    assert after["stages"] == before["stages"]
    for key in ("session", "attempt_ledger", "quarantine"):
        assert after["verification"][key] == before["verification"][key]
    assert all(stage["state"] == "PENDING" for stage in after["stages"][1:])
    # An explicit original-store byte read is independent of the absent inbox.
    with reopened.stage_transaction(
        expected_challenge_sha256=after["verification"]["challenge_sha256"]
    ) as tx:
        assert tx.read_stage_evidence(original_ref) == RAW
