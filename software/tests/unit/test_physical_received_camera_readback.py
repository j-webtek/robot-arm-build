"""Original stage-3 storage with explicit modeled observations, never hardware.

Pure cases model only original M1 scopes while using actual immutable V2
snapshots and all production codecs. The NTFS case separately uses real stored
originals and restart; no case runs inventory, a device or native camera code.
"""

from dataclasses import replace
from pathlib import Path
from threading import Event
from types import SimpleNamespace
import os
import time

import pytest

from rocell.application import physical_camera_session as module
from rocell.application import physical_onboarding_v2 as v2
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_intake_notebook import PhysicalIntakeNotebook
from rocell.application.physical_onboarding_receipts import BoundEvidence
from rocell.providers.windows.native_camera_protocol import canonical, digest

from test_physical_static_contract_readback import (
    source_model,
    intake_model,
    model,
    no_devices,
    workspace,
    enter_static,
    actual_static_subjects,
    retain_static,
    refresh_read,
    initial_epoch,
)
from test_physical_camera_session import SOURCE, LAUNCH
from test_physical_received_camera import (
    fixture as modeled_receipt,
    LAUNCH as COLLECTION_LAUNCH,
)

RECEIVED = "receivedcamera-" + "a" * 32
SECOND = "receivedcamera-" + "b" * 32
RAW = b"MODELED PURCHASE AND OBSERVATION ORIGINAL. NOT RECEIVED HARDWARE.\n"
PNG = b"\x89PNG\r\n\x1a\nMODELED OPAQUE TEST ORIGINAL. NOT A CAMERA IMAGE."


def label(role, receipt_id=RECEIVED, index=0):
    return f"received-camera-{role}-v1:{receipt_id}" + (
        f":{index:02}" if role == "original" else ""
    )


def code(phase, receipt_id=RECEIVED):
    return "CAMERA_RECEIPT_COLLECTION_" + phase + "_" + receipt_id[15:].upper()


@pytest.fixture
def received_ready(source_model, monkeypatch):
    enter_static(source_model)
    subjects = actual_static_subjects(source_model, monkeypatch)
    retain_static(source_model, subjects, camera_entry=True)
    source_model[2]["static_subjects"] = subjects
    return source_model


def received_subjects(
    case,
    *,
    receipt_id=RECEIVED,
    observed=False,
    predecessor=None,
    previous_refs=None,
    phase="reviewed",
    identity=False,
    media_count=None,
    maximum_text=False,
):
    """Actual notebook/submission/assess/review codecs over modeled physical facts."""
    from rocell.application import physical_received_camera_submission as codec

    owner, prerequisites, state = case
    submitted_at = (
        100 if predecessor is None else predecessor[2].to_dict()["reviewed_at_ns"] + 100
    )
    if predecessor is not None:
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            code("STARTED", receipt_id),
            [previous_refs[k] for k in ("submission", "assessment", "review")],
            stage=STAGE_ORDER[2],
        )
    if phase == "started":
        return SimpleNamespace(subjects={}, refs={}, predecessor=predecessor)
    notebook, _, inspection, _ = modeled_receipt(prerequisites, observed=observed)
    if not observed:
        for i, row in enumerate(notebook.to_dict()["rows"]):
            notebook = notebook.record(
                record_id=row["record_id"],
                observation_status="UNKNOWN",
                observed_value="Hardware not received; no measurement.",
                method="Explicit modeled unknown.",
                evidence_note="Test only; no physical facts.",
                operator_id="modeled-operator",
                recorded_at_ns=i + 1,
            )
    if maximum_text:
        for i, row in enumerate(notebook.to_dict()["rows"]):
            notebook = notebook.record(
                record_id=row["record_id"],
                observation_status="UNKNOWN",
                observed_value="U" * 256,
                method="M" * 512,
                evidence_note="E" * 1024,
                operator_id="O" * 64,
                recorded_at_ns=i + 20,
            )
    refs = {
        "notebook": state["add"](
            notebook.payload, label=label("notebook", receipt_id), stage=STAGE_ORDER[2]
        )
    }
    subjects = {"notebook": notebook}
    if phase == "notebook":
        return SimpleNamespace(subjects=subjects, refs=refs, predecessor=predecessor)
    count = (2 if observed else 0) if media_count is None else media_count
    attachments = []
    for index in range(count):
        raw, name, media = (
            (PNG, f"modeled-{index}.png", "image/png")
            if index == 1
            else (RAW, f"modeled-{index}.txt", "text/plain")
        )
        ref = state["add"](
            raw,
            label=label("original", receipt_id, index),
            stage=STAGE_ORDER[2],
            media=media,
        )
        refs[f"original_{index}"] = ref
        attachments.append(codec.ReceivedCameraAttachment(ref, name, media))
    if phase == "originals":
        return SimpleNamespace(subjects=subjects, refs=refs, predecessor=predecessor)
    if observed:
        inspection = replace(
            inspection,
            binding=replace(
                inspection.binding,
                source_binding_sha256=state["header"].source_binding_sha256,
                session_header_sha256=state["header"].header_sha256,
                session_id=owner.descriptor()["session_id"],
                cell_id=owner.descriptor()["cell_id"],
                evidence=tuple(
                    BoundEvidence.from_reference(ref)
                    for ref in sorted(refs.values(), key=lambda ref: ref.evidence_id)
                ),
            ),
            purchase_record_evidence_id=refs["original_0"].evidence_id,
            inspection_image_evidence_ids=(refs["original_1"].evidence_id,),
        )
    else:
        inspection = None
    binding = {
        "receipt_id": receipt_id,
        "source_sha256": SOURCE,
        "cell_id": owner.descriptor()["cell_id"],
        "session_id": owner.descriptor()["session_id"],
        "header_sha256": state["header"].header_sha256,
        "origin_launch_id": owner.descriptor()["launch_id"],
        "collection_launch_id": COLLECTION_LAUNCH,
        "operator_id": "modeled-operator",
        "prerequisites_sha256": prerequisites.evidence_sha256,
        "static_contract": {k: v.sha256 for k, v in state["static_subjects"].items()},
        "camera_request_event_sha256": next(
            e.event_sha256
            for e in state["events"]
            if e.detail_code.startswith("CAMERA_RECEIPT_REQUESTED_")
        ),
    }
    submission = codec.build_received_camera_submission(
        prerequisites,
        notebook,
        binding=binding,
        notebook_reference=refs["notebook"],
        inspection=inspection,
        attachments=tuple(
            sorted(attachments, key=lambda item: item.reference.evidence_id)
        ),
        row_links=tuple(
            codec.ReceivedCameraRowLink(
                row["record_id"], refs["original_0"].evidence_id if observed else None
            )
            for row in notebook.to_dict()["rows"]
        ),
        submitted_at_ns=submitted_at,
        evidence_inventory=state["snapshot"]().evidence,
        predecessor=predecessor,
    )
    subjects["submission"] = submission
    refs["submission"] = state["add"](
        submission.payload, label=label("submission", receipt_id), stage=STAGE_ORDER[2]
    )
    if phase == "submission":
        return SimpleNamespace(subjects=subjects, refs=refs, predecessor=predecessor)
    assessment = codec.assess_received_camera_submission(submission)
    subjects["assessment"] = assessment
    refs["assessment"] = state["add"](
        assessment.payload, label=label("assessment", receipt_id), stage=STAGE_ORDER[2]
    )
    if phase != "assessment":
        state["advance"](
            v2.V2StageState.REVIEW_PENDING,
            code("SUBMITTED", receipt_id),
            refs.values(),
            stage=STAGE_ORDER[2],
        )
    if phase in {"assessment", "review-pending"}:
        return SimpleNamespace(subjects=subjects, refs=refs, predecessor=predecessor)
    review = codec.review_received_camera_submission(
        submission,
        assessment,
        decision="ACKNOWLEDGE_EXACT",
        reviewer_id="modeled-reviewer",
        review_launch_id=LAUNCH,
        reviewed_at_ns=submitted_at + 1,
    )
    subjects["review"] = review
    refs["review"] = state["add"](
        review.payload, label=label("review", receipt_id), stage=STAGE_ORDER[2]
    )
    if phase == "reviewed":
        state["advance"](
            v2.V2StageState(review.to_dict()["verdict"]),
            code("REVIEWED_" + review.to_dict()["verdict"], receipt_id),
            refs.values(),
            stage=STAGE_ORDER[2],
        )
    if identity:
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            "CAMERA_IDENTITY_REQUESTED_" + receipt_id[15:].upper(),
            stage=STAGE_ORDER[3],
        )
    return SimpleNamespace(
        subjects=subjects, refs=refs, predecessor=(submission, assessment, review)
    )


def test_empty_first_attempt_is_exact_v5(received_ready):
    result = refresh_read(received_ready)
    assert result["schema"] == module.SOURCE_WORKFLOW_STATIC_SCHEMA
    assert "received_camera_cycles" not in result


@pytest.mark.parametrize(
    "phase,expected",
    [
        ("notebook", "INCOMPLETE"),
        ("originals", "INCOMPLETE"),
        ("submission", "INCOMPLETE"),
        ("assessment", "ASSESSMENT_RETAINED_NOT_COMMITTED"),
        ("review-pending", "REVIEW_PENDING"),
        ("review-retained", "REVIEW_RETAINED_NOT_COMMITTED"),
        ("reviewed", "REVIEWED_PASS"),
    ],
)
def test_every_retained_boundary_exact_bytes_without_replay(
    received_ready, monkeypatch, phase, expected
):
    from rocell.application import physical_received_camera_submission as codec

    owner, _, state = received_ready
    made = received_subjects(received_ready, observed=True, phase=phase)
    before = state["snapshot"]()
    monkeypatch.setattr(
        codec,
        "build_received_camera_submission",
        lambda *a, **kw: pytest.fail("replay"),
    )
    result = refresh_read(received_ready)
    assert result["schema"] == module.SOURCE_WORKFLOW_RECEIVED_SCHEMA
    cycle = result["received_camera_cycles"][0]
    assert cycle["state"] == expected and cycle["sequence"] == 1
    for role, artifact in made.subjects.items():
        assert canonical(cycle[role]["document"]) == artifact.payload
        assert cycle[role]["reference"] == made.refs[role].to_dict()
    assert result["camera_identity_request"] is None and state["snapshot"]() == before
    assert RAW not in canonical(result) and PNG not in canonical(result)
    assert owner.retained_source_workflow() == result
    cycle["state"] = "tampered"
    assert (
        owner.retained_source_workflow()["received_camera_cycles"][0]["state"]
        == expected
    )


@pytest.mark.parametrize("identity", [False, True])
def test_modeled_receipt_pass_requires_separate_identity_entry(
    received_ready, identity
):
    received_subjects(received_ready, observed=True, identity=identity)
    result = refresh_read(received_ready)
    assert result["received_camera_cycles"][0]["state"] == "REVIEWED_PASS"
    assert (result["camera_identity_request"] is not None) is identity
    assert result["physical_authority"] is result["device_io_performed"] is False


@pytest.mark.parametrize("phase", ["started", "notebook", "reviewed"])
def test_explicit_successor_after_unknown_blocked_keeps_originals(
    received_ready, phase
):
    first = received_subjects(received_ready)
    assert first.subjects["assessment"].to_dict()["verdict"] == "BLOCKED"
    second = received_subjects(
        received_ready,
        receipt_id=SECOND,
        predecessor=first.predecessor,
        previous_refs=first.refs,
        phase=phase,
    )
    result = refresh_read(received_ready)
    cycles = result["received_camera_cycles"]
    assert len(cycles) == 2 and cycles[0]["state"] == "REVIEWED_BLOCKED"
    assert (
        canonical(cycles[0]["submission"]["document"])
        == first.subjects["submission"].payload
    )
    assert cycles[1]["sequence"] == 2 and cycles[1]["state"] == (
        "REVIEWED_BLOCKED" if phase == "reviewed" else "INCOMPLETE"
    )
    if phase == "started":
        assert all(cycles[1][key] is None for key in module.RECEIVED_ROLE_BYTES)


@pytest.mark.parametrize(
    "fault",
    [
        "unknown-label",
        "wrong-stage",
        "raw-hash",
        "raw-media",
        "extra-raw",
        "missing-raw",
        "duplicate-notebook",
        "raw-no-notebook",
        "submission-no-notebook",
        "wrong-event-refs",
        "wrong-cycle",
        "extra-start",
        "identity-before-pass",
        "identity-wrong-id",
        "future-stage",
        "source-prefix",
        "static-prefix",
        "uncommitted",
    ],
)
def test_closed_roles_originals_and_journal_refuse_faults(received_ready, fault):
    _, _, state = received_ready
    made = received_subjects(
        received_ready,
        observed=True,
        phase="review-pending" if fault == "identity-before-pass" else "reviewed",
    )
    if fault in {"unknown-label", "raw-media"}:
        old = made.refs["original_0"]
        manifest = canonical(
            {
                "label": (
                    "unknown-role" if fault == "unknown-label" else label("original")
                ),
                "media_type": "image/png" if fault == "raw-media" else "text/plain",
            }
        )
        state["manifests"][old.evidence_id] = manifest
        state["references"][state["references"].index(old)] = replace(
            old, manifest_sha256=digest(manifest)
        )
    elif fault in {"wrong-stage", "raw-hash"}:
        old = made.refs["original_0"]
        state["references"][state["references"].index(old)] = replace(
            old,
            **(
                {"stage": STAGE_ORDER[0]}
                if fault == "wrong-stage"
                else {"payload_sha256": "f" * 64}
            ),
        )
    elif fault == "extra-raw":
        state["add"](
            RAW,
            label=label("original", index=2),
            stage=STAGE_ORDER[2],
            media="text/plain",
        )
    elif fault == "missing-raw":
        state["references"].remove(made.refs["original_0"])
    elif fault == "duplicate-notebook":
        state["add"](
            made.subjects["notebook"].payload,
            label=label("notebook"),
            stage=STAGE_ORDER[2],
        )
    elif fault in {"raw-no-notebook", "submission-no-notebook"}:
        state["references"].remove(made.refs["notebook"])
    elif fault in {"wrong-event-refs", "wrong-cycle"}:
        state["events"][-1] = replace(
            state["events"][-1],
            **(
                {"evidence": (made.refs["review"],)}
                if fault == "wrong-event-refs"
                else {"detail_code": code("REVIEWED_PASS", SECOND)}
            ),
        )
    elif fault == "extra-start":
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            code("STARTED", SECOND),
            [made.refs[k] for k in ("submission", "assessment", "review")],
            stage=STAGE_ORDER[2],
        )
    elif fault.startswith("identity"):
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            "CAMERA_IDENTITY_REQUESTED_"
            + (SECOND if fault == "identity-wrong-id" else RECEIVED)[15:].upper(),
            stage=STAGE_ORDER[3],
        )
    elif fault == "future-stage":
        state["add"](b"{}", label="arbitrary", stage=STAGE_ORDER[3])
    elif fault in {"source-prefix", "static-prefix"}:
        index = 1 if fault == "source-prefix" else -4
        state["events"][index] = replace(
            state["events"][index], detail_code="UNKNOWN_PREFIX"
        )
    elif fault == "uncommitted":
        state["uncommitted"] = (state["events"][-1],)
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(received_ready)


@pytest.mark.parametrize(
    "fault", ["lease-exit", "coherence", "late-stop", "late-source", "late-deadline"]
)
def test_late_failure_keeps_exact_verified_v6_history(
    received_ready, monkeypatch, fault
):
    owner, _, state = received_ready
    made = received_subjects(received_ready, observed=True)
    cancellation = Event()
    state["exit_failure"] = fault == "lease-exit"
    if fault == "coherence":
        state["after_change"] = "session_head_sha256"
    if fault.startswith("late-"):
        original = module._verify_original_source_roles

        def fail_after(*args, **kwargs):
            result = original(*args, **kwargs)
            if fault == "late-stop":
                cancellation.set()
            elif fault == "late-source":
                state["source"] = "f" * 64
            else:
                state["now"] += module.DIAGNOSTIC_TIMEOUT_NS
            return result

        monkeypatch.setattr(module, "_verify_original_source_roles", fail_after)
    with pytest.raises((module.PhysicalCameraSessionError, RuntimeError)):
        refresh_read(received_ready, cancellation=cancellation)
    result = owner.retained_source_workflow()
    assert (
        canonical(result["received_camera_cycles"][0]["submission"]["document"])
        == made.subjects["submission"].payload
    )
    assert owner.view()["status"] == "HELD"


def test_four_cycles_full_original_epoch_and_source_static_prefix(received_ready):
    previous = refs = None
    for index in range(4):
        made = received_subjects(
            received_ready,
            receipt_id=f"receivedcamera-{index + 100:032x}",
            predecessor=previous,
            previous_refs=refs,
            observed=index == 3,
            identity=index == 3,
        )
        previous, refs = made.predecessor, made.refs
    result = refresh_read(received_ready)
    assert len(result["received_camera_cycles"]) == 4
    assert [row["state"] for row in result["received_camera_cycles"]] == [
        "REVIEWED_BLOCKED"
    ] * 3 + ["REVIEWED_PASS"]
    assert result["camera_identity_request"] is not None
    assert len(canonical(result)) < module.MAX_RECEIVED_WORKFLOW_BYTES


@pytest.mark.parametrize(
    "key",
    [
        "source_sha256",
        "session_id",
        "cell_id",
        "header_sha256",
        "origin_launch_id",
        "prerequisites_sha256",
        "static_contract",
        "camera_request_event_sha256",
        "receipt_id",
    ],
)
def test_rehashed_submission_cannot_rebind_original_context(received_ready, key):
    _, _, state = received_ready
    made = received_subjects(received_ready, phase="submission")
    document = made.subjects["submission"].to_dict()
    old = document["binding"][key]
    document["binding"][key] = (
        {name: "f" * 64 for name in old}
        if type(old) is dict
        else "f" * 64 if key.endswith("sha256") else old[:-1] + "9"
    )
    raw = canonical(document)
    original = made.refs["submission"]
    state["references"][state["references"].index(original)] = replace(
        original, payload_sha256=digest(raw), payload_bytes=len(raw)
    )
    state["payloads"][original.evidence_id] = raw
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(received_ready)


def test_full_source32_static3_received80_budget_and_epoch(source_model, monkeypatch):
    from rocell.application import physical_configuration_epochs as epochs

    original_epoch = initial_epoch(source_model)
    enter_static(source_model, cycles=7, intake=True, early_originals=1)
    _, prerequisites, state = source_model
    assert len(state["references"]) == 32
    static = actual_static_subjects(source_model, monkeypatch)
    retain_static(source_model, static, camera_entry=True)
    state["static_subjects"] = static
    previous = refs = None
    for index in range(4):
        made = received_subjects(
            source_model,
            receipt_id=f"receivedcamera-{index + 80:032x}",
            predecessor=previous,
            previous_refs=refs,
            media_count=16,
            maximum_text=True,
        )
        previous, refs = made.predecessor, made.refs
    assert len(state["references"]) == 115
    snapshot = state["snapshot"]()
    result = refresh_read(source_model)
    assert (
        canonical(result["configuration_epochs"]["document"]) == original_epoch.payload
    )
    assert len(result["received_camera_cycles"]) == 4
    assert all(len(row["originals"]) == 16 for row in result["received_camera_cycles"])
    wire = canonical(result)
    assert module._decode_cached_source_workflow(wire) == result
    assert len(wire) <= module.MAX_RECEIVED_WORKFLOW_BYTES
    pending, nodes, depth = [(result, 0)], 0, 0
    while pending:
        value, level = pending.pop()
        nodes += 1
        depth = max(depth, level)
        if type(value) is dict:
            for key, child in value.items():
                pending.extend(((key, level + 1), (child, level + 1)))
        elif type(value) is list:
            pending.extend((child, level + 1) for child in value)
    assert nodes <= module.MAX_SOURCE_WORKFLOW_CACHE_NODES
    assert depth <= module.MAX_SOURCE_WORKFLOW_CACHE_DEPTH
    print(
        f"v6 bounded cache: {len(wire)} bytes, depth {depth}, {nodes} nodes, 115 references"
    )
    with pytest.raises(epochs.PhysicalConfigurationEpochError):
        epochs.verify_physical_configuration_epochs(
            original_epoch.payload,
            prerequisites=prerequisites,
            snapshot=snapshot,
            expected_sha256=original_epoch.sha256,
        )
    with pytest.raises(epochs.PhysicalConfigurationEpochError):
        epochs._verify_physical_configuration_epochs_after_static(
            original_epoch.payload,
            prerequisites=prerequisites,
            snapshot=snapshot,
            expected_sha256=original_epoch.sha256,
        )
    assert (
        epochs._verify_physical_configuration_epochs_after_received_camera(
            original_epoch.payload,
            prerequisites=prerequisites,
            snapshot=snapshot,
            expected_sha256=original_epoch.sha256,
        ).payload
        == original_epoch.payload
    )
    # A fifth explicit cycle cannot broaden the fixed original grammar.
    state["advance"](
        v2.V2StageState.WAITING_OPERATOR,
        code("STARTED", "receivedcamera-" + "f" * 32),
        [refs[k] for k in ("submission", "assessment", "review")],
        stage=STAGE_ORDER[2],
    )
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(source_model)


def test_stage3_media_set_budget_is_not_global_source_budget(received_ready):
    _, _, state = received_ready
    made = received_subjects(received_ready, phase="originals", media_count=3)
    for index in range(3):
        old = made.refs[f"original_{index}"]
        # Bounded byte prefixes are actual originals; expand explicitly in test
        # to exceed only this cycle's4MiB, still below stage3 aggregate budget.
        payload = state["payloads"][old.evidence_id] + b"x" * (
            2 * 1024 * 1024 - old.payload_bytes
        )
        state["payloads"][old.evidence_id] = payload
        state["references"][state["references"].index(old)] = replace(
            old, payload_bytes=len(payload), payload_sha256=digest(payload)
        )
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(received_ready)


@pytest.mark.parametrize("kind", ["original", "notebook"])
def test_older_ancestor_reference_is_not_relabelled_current_cycle(received_ready, kind):
    from rocell.application import physical_received_camera_submission as codec

    _, prerequisites, state = received_ready
    first = received_subjects(received_ready, media_count=1)
    second = received_subjects(
        received_ready,
        receipt_id=SECOND,
        media_count=1,
        predecessor=first.predecessor,
        previous_refs=first.refs,
    )
    third = received_subjects(
        received_ready,
        receipt_id="receivedcamera-" + "c" * 32,
        media_count=1,
        predecessor=second.predecessor,
        previous_refs=second.refs,
        phase="submission",
    )
    data = third.subjects["submission"].to_dict()
    if kind == "original":
        data["attachments"][0]["reference"] = first.refs["original_0"].to_dict()
    else:
        data["notebook_reference"] = first.refs["notebook"].to_dict()
    raw = canonical(data)
    # The codec can authenticate references, but only original M1 labels prove
    # collection ownership across all ancestors. Exercise that exact seam.
    codec.verify_received_camera_submission(
        raw,
        prerequisites=prerequisites,
        expected_binding=data["binding"],
        evidence_inventory=state["snapshot"]().evidence,
        expected_submission_sha256=digest(raw),
        predecessor=second.predecessor,
    )
    old = third.refs["submission"]
    state["references"][state["references"].index(old)] = replace(
        old, payload_sha256=digest(raw), payload_bytes=len(raw)
    )
    state["payloads"][old.evidence_id] = raw
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(received_ready)


@pytest.mark.skipif(os.name != "nt", reason="actual isolated NTFS/M1 original storage")
def test_actual_ntfs_original_received_camera_reopen_partial_review_and_identity(
    workspace, monkeypatch
):
    """Real storage/readback; isolation, ownership and received facts modeled.

    This is not physical camera dispatch or acquired camera evidence. All device
    and child-process entrypoints remain forbidden by the shared fixture.
    """
    from test_physical_camera_session import session_fixture, perform
    from test_physical_camera_session_readback import generate
    from test_physical_camera_source_workflow_readback import collect_chain
    from test_physical_camera_intake_session import SOURCE_CODES, read
    from test_physical_source_qualification_readback import (
        qualification_records,
        label as source_label,
        code as source_code,
        QUALIFICATION,
        RAW as ISOLATION_RAW,
    )
    from test_physical_ownership_qualification import modeled_report
    from test_physical_static_contract_readback import (
        label as static_label,
        code as static_code,
        CONTRACT,
    )
    from rocell.application import physical_received_camera_submission as codec

    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    prerequisites = generate(workspace)
    owner = session_fixture(workspace)
    initial = perform(owner)
    header = initial["verification"]["session"]["header_sha256"]
    sources = collect_chain(prerequisites, header, monkeypatch)
    descriptor = owner.descriptor()
    ownership = modeled_report(
        source_sha256=SOURCE,
        directory=Path(descriptor["directory"])
        / ("source-ownership-" + QUALIFICATION[11:]),
        workspace=workspace,
        covered=True,
    )

    def commit(tx, stage, next_state, detail, refs=()):
        tx.commit_stage_state(
            stage,
            next_state,
            occurred_at_ns=time.time_ns(),
            detail_code=detail,
            evidence=tuple(sorted(refs, key=lambda ref: ref.evidence_id)),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )

    def retain(tx, payload, *, label, stage=STAGE_ORDER[2], media="application/json"):
        ref = tx.store_evidence(
            stage,
            payload,
            label=label,
            media_type=media,
            captured_at_ns=time.time_ns(),
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        assert tx.read_stage_evidence(ref) == payload
        return ref

    with owner.stage_transaction(
        expected_challenge_sha256=initial["verification"]["challenge_sha256"]
    ) as tx:
        stage = STAGE_ORDER[0]
        commit(tx, stage, v2.V2StageState.WAITING_OPERATOR, SOURCE_CODES[0])
        retain(tx, prerequisites.payload, label=module.PREREQUISITE_LABEL, stage=stage)
        original_refs = {
            role: retain(
                tx,
                sources[role].payload,
                label=f"workspace-source-{role}-v1",
                stage=stage,
            )
            for role in ("receipt", "assessment")
        }
        commit(
            tx,
            stage,
            v2.V2StageState.REVIEW_PENDING,
            SOURCE_CODES[1],
            original_refs.values(),
        )
        original_refs["review"] = retain(
            tx,
            sources["review"].payload,
            label="workspace-source-review-v1",
            stage=stage,
        )
        commit(
            tx, stage, v2.V2StageState.BLOCKED, SOURCE_CODES[2], original_refs.values()
        )
        commit(
            tx,
            stage,
            v2.V2StageState.WAITING_OPERATOR,
            source_code("STARTED"),
            original_refs.values(),
        )
        raw_ref = retain(
            tx,
            ISOLATION_RAW,
            label=source_label("isolation_original"),
            stage=stage,
            media="text/plain",
        )
        qualified = qualification_records(
            prerequisites,
            descriptor,
            header,
            sources,
            original_ref=raw_ref,
            ownership=ownership,
            observed=True,
        )
        qualified_refs = {
            role: retain(
                tx, qualified[role].payload, label=source_label(role), stage=stage
            )
            for role in ("receipt", "assessment")
        }
        commit(
            tx,
            stage,
            v2.V2StageState.REVIEW_PENDING,
            source_code("ASSESSED"),
            [raw_ref, *qualified_refs.values()],
        )
        qualified_refs["review"] = retain(
            tx, qualified["review"].payload, label=source_label("review"), stage=stage
        )
        commit(
            tx,
            stage,
            v2.V2StageState.PASS,
            source_code("REVIEWED_PASS"),
            [raw_ref, *qualified_refs.values()],
        )
        commit(
            tx,
            STAGE_ORDER[1],
            v2.V2StageState.WAITING_OPERATOR,
            "STATIC_CAMERA_CONTRACT_REQUESTED_" + QUALIFICATION[11:].upper(),
        )
        original = tx.snapshot()
    static = actual_static_subjects(
        (
            owner,
            prerequisites,
            {
                "qualified_sources": qualified,
                "header": original.header,
                "events": original.committed_events,
            },
        ),
        monkeypatch,
    )
    perform(owner, "refresh")
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        static_refs = {
            role: retain(
                tx, static[role].payload, label=static_label(role), stage=STAGE_ORDER[1]
            )
            for role in ("receipt", "assessment")
        }
        commit(
            tx,
            STAGE_ORDER[1],
            v2.V2StageState.REVIEW_PENDING,
            static_code("COLLECTED"),
            static_refs.values(),
        )
        static_refs["review"] = retain(
            tx,
            static["review"].payload,
            label=static_label("review"),
            stage=STAGE_ORDER[1],
        )
        commit(
            tx,
            STAGE_ORDER[1],
            v2.V2StageState.PASS,
            static_code("REVIEWED_PASS"),
            static_refs.values(),
        )
        commit(
            tx,
            STAGE_ORDER[2],
            v2.V2StageState.WAITING_OPERATOR,
            "CAMERA_RECEIPT_REQUESTED_" + CONTRACT[15:].upper(),
        )
    perform(owner, "refresh")
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        current = tx.snapshot()
        case = (
            owner,
            prerequisites,
            {
                "header": current.header,
                "events": current.committed_events,
                "static_subjects": static,
                "snapshot": tx.snapshot,
                "add": lambda payload, **kwargs: retain(tx, payload, **kwargs),
            },
        )
        made = received_subjects(case, observed=True, phase="assessment")
        expected_head = tx.snapshot().head

    def reopen(expected_state, *, identity=False):
        fresh = session_fixture(workspace)
        current = perform(fresh, "refresh")
        result = read(fresh, header)
        assert result["schema"] == module.SOURCE_WORKFLOW_RECEIVED_SCHEMA
        assert result["session_head_sha256"] == expected_head.head_sha256
        cycle = result["received_camera_cycles"][0]
        assert cycle["state"] == expected_state
        assert (result["camera_identity_request"] is not None) is identity
        assert current["stages"][3]["state"] == (
            "WAITING_OPERATOR" if identity else "PENDING"
        )
        for role, artifact in made.subjects.items():
            assert canonical(cycle[role]["document"]) == artifact.payload
        assert len(cycle["originals"]) == 2
        assert RAW not in canonical(result) and PNG not in canonical(result)
        assert result["assessment"]["document"]["verdict"] == "BLOCKED"
        assert result["qualification_cycles"][-1]["state"] == "REVIEWED_PASS"
        return fresh

    owner = reopen("ASSESSMENT_RETAINED_NOT_COMMITTED")
    review = codec.review_received_camera_submission(
        made.subjects["submission"],
        made.subjects["assessment"],
        decision="ACKNOWLEDGE_EXACT",
        reviewer_id="modeled-reviewer",
        review_launch_id=LAUNCH,
        reviewed_at_ns=101,
    )
    monkeypatch.setattr(
        codec,
        "build_received_camera_submission",
        lambda *a, **kw: pytest.fail("restart replay"),
    )
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        commit(
            tx,
            STAGE_ORDER[2],
            v2.V2StageState.REVIEW_PENDING,
            code("SUBMITTED"),
            made.refs.values(),
        )
        made.refs["review"] = retain(tx, review.payload, label=label("review"))
        made.subjects["review"] = review
        expected_head = tx.snapshot().head
    owner = reopen("REVIEW_RETAINED_NOT_COMMITTED")
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        commit(
            tx,
            STAGE_ORDER[2],
            v2.V2StageState.PASS,
            code("REVIEWED_PASS"),
            made.refs.values(),
        )
        expected_head = tx.snapshot().head
    owner = reopen("REVIEWED_PASS")
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        commit(
            tx,
            STAGE_ORDER[3],
            v2.V2StageState.WAITING_OPERATOR,
            "CAMERA_IDENTITY_REQUESTED_" + RECEIVED[15:].upper(),
        )
        expected_head = tx.snapshot().head
    reopen("REVIEWED_PASS", identity=True)
