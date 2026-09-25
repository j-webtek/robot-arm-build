"""Original source successors: real codecs with modeled observations/leases.

The separate NTFS case uses actual durable originals; no test runs a device,
ownership experiment or physical release. Positive isolation/ownership facts
are explicitly modeled and do not qualify the received installation.
"""

from contextlib import contextmanager
from dataclasses import replace
import os
from pathlib import Path
import threading
import time

import pytest

from rocell.application import physical_camera_session as module
from rocell.application import physical_onboarding_v2 as v2
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.providers.windows.native_camera_protocol import canonical, digest

from test_physical_camera_intake_session import (
    SOURCE_CODES,
    complete as complete_intake,
    intake_model,
    read,
)
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


QUALIFICATION = "sourcequal-" + "4" * 32
SECOND = "sourcequal-" + "5" * 32
RAW = b"Modeled isolation statement attachment. NOT HARDWARE EVIDENCE.\n"


def label(role, qualification=QUALIFICATION):
    name = (
        "isolation-original"
        if role == "isolation_original"
        else "qualification-" + role
    )
    return f"workspace-source-{name}-v1:{qualification}"


def code(phase, qualification=QUALIFICATION):
    return "WORKSPACE_SOURCE_QUALIFICATION_" + phase + "_" + qualification[11:].upper()


@pytest.fixture
def source_model(intake_model):
    """Keep actual typed whole-journal snapshots, including explicit stage 2."""
    owner, prerequisites, state = intake_model

    def snapshot():
        states = [v2.V2StageState.PENDING for _ in STAGE_ORDER]
        ids = [[] for _ in STAGE_ORDER]
        sequences = [None for _ in STAGE_ORDER]
        for event in state["events"]:
            index = STAGE_ORDER.index(event.stage)
            # Fault tests may intentionally build invalid transitions. The
            # production reader must refuse those, rather than this fixture.
            states[index] = event.state
            ids[index].extend(ref.evidence_id for ref in event.evidence)
            sequences[index] = event.sequence
        return v2.V2SessionSnapshot(
            state["header"],
            tuple(
                v2.V2StageSnapshot(stage, states[i], sequences[i], tuple(ids[i]))
                for i, stage in enumerate(STAGE_ORDER)
            ),
            tuple(state["events"]),
            state.get("uncommitted", ()),
            tuple(sorted(state["references"], key=lambda ref: ref.evidence_id)),
            v2.V2CommittedHead.build(state["header"], state["events"]),
            v2._derive_next_action(states),
        )

    original_scope = owner._store.stage_transaction

    @contextmanager
    def scope(*args, **kwargs):
        with original_scope(*args, **kwargs) as tx:
            old = tx.snapshot
            tx.snapshot = snapshot
            try:
                yield tx
            finally:
                tx.snapshot = old

    owner._store.stage_transaction = scope
    state["snapshot"] = snapshot

    def advance(next_state, detail, refs=(), *, stage=STAGE_ORDER[0], sort=True):
        previous = snapshot().stages[STAGE_ORDER.index(stage)].state
        events = state["events"]
        events.append(
            v2.V2JournalEvent.build(
                header=state["header"],
                sequence=len(events),
                stage=stage,
                previous_state=previous,
                state=next_state,
                occurred_at_ns=2000 + len(events),
                previous_event_sha256=events[-1].event_sha256 if events else "0" * 64,
                evidence=(
                    tuple(sorted(refs, key=lambda ref: ref.evidence_id))
                    if sort
                    else tuple(refs)
                ),
                detail_code=detail,
            )
        )

    state["advance"] = advance
    return owner, prerequisites, state


def start(
    source_model, *, qualification=QUALIFICATION, previous=None, intake_refs=None
):
    _, _, state = source_model
    refs = (
        list(state["source_refs"].values())
        if previous is None
        else list(previous.values())
    )
    if intake_refs:
        refs.extend(intake_refs.values())
    state["advance"](
        v2.V2StageState.WAITING_OPERATOR, code("STARTED", qualification), refs
    )


def refresh_read(source_model, **kwargs):
    owner, _, state = source_model
    return read(owner, state["header"].header_sha256, **kwargs)


def incomplete_ownership(*, workspace, directory):
    """Exact production codec for an explicitly unperformed modeled experiment."""
    from rocell.application import physical_ownership_qualification as ownership

    document = {
        "schema": ownership.SCHEMA,
        "binding": {
            "workspace": str(workspace),
            "directory": str(directory),
            "source_sha256": SOURCE,
        },
        "runtime": {
            "executable": str(workspace / "modeled-python.exe"),
            "executable_sha256": "1" * 64,
            "child": str(workspace / ownership.CHILD_PATH),
            "child_sha256": "2" * 64,
            "lease_source_sha256": "3" * 64,
            "durability_source_sha256": "4" * 64,
        },
        "started_at_ns": 1,
        "elapsed_ns": 0,
        "durability": None,
        "lease_experiment": {"clean": None, "crash": None, "pid_mismatch": None},
        "m1_experiment": None,
        "terminal_error": {
            "code": "MODELED_EXPERIMENT_NOT_RUN",
            "type": "TestObservation",
        },
        "residuals": list(ownership.RESIDUALS),
        "device_effects": dict(ownership.ZERO_EFFECTS),
        "physical_authority": False,
        "hardware_qualified": False,
    }
    document["checks"] = ownership._derived_checks(document)
    result = ownership.PhysicalOwnershipQualification(canonical(document))
    assert result.safe_summary()["status"] == "HELD"
    return result


def qualification_records(
    prerequisites,
    descriptor,
    header,
    source_artifacts,
    *,
    qualification=QUALIFICATION,
    original_ref=None,
    predecessor=None,
    ownership=None,
    observed=False,
):
    from rocell.application import physical_source_qualification as codec
    from rocell.application.physical_source_stage_evidence import WorkspaceSourceReceipt

    software_document = source_artifacts["receipt"].to_dict()
    software_document["binding"].update(
        operator_id="qualification-operator", collection_launch_id="wizard-" + "9" * 32
    )
    software = WorkspaceSourceReceipt(canonical(software_document))
    binding = {
        "qualification_id": qualification,
        "source_sha256": SOURCE,
        "cell_id": CELL,
        "session_id": SESSION,
        "header_sha256": header,
        "origin_launch_id": LAUNCH,
        "collection_launch_id": "wizard-" + "9" * 32,
        "operator_id": "qualification-operator",
        "prerequisites_sha256": prerequisites.evidence_sha256,
        "store_directory": descriptor["directory"],
        "predecessor_source": {
            role: source_artifacts[role].sha256
            for role in ("receipt", "assessment", "review")
        },
        "predecessor_qualification": (
            None
            if predecessor is None
            else {
                role: predecessor[role].sha256
                for role in ("receipt", "assessment", "review")
            }
        ),
    }
    ownership = ownership or incomplete_ownership(
        workspace=Path(descriptor["workspace"]),
        directory=codec.ownership_directory(binding),
    )
    receipt = codec.build_source_qualification_receipt(
        binding=binding,
        software_receipt=software,
        ownership_report=ownership,
        isolation={
            "status": "OBSERVED_DISCONNECTED" if observed else "UNKNOWN",
            "statement": (
                "Explicitly modeled isolation observation; not a hardware claim."
                if observed
                else "Hardware not received; isolation remains unknown."
            ),
            "original_reference": (
                None if original_ref is None else original_ref.to_dict()
            ),
            "basename": None if original_ref is None else "unknown.txt",
            "recorded_at_ns": 10000,
        },
    )
    assessment = codec.assess_source_qualification(receipt)
    review = codec.review_source_qualification(
        receipt,
        assessment,
        reviewer_id="qualification-reviewer",
        review_launch_id=LAUNCH,
        reviewed_at_ns=11000,
    )
    return {"receipt": receipt, "assessment": assessment, "review": review}


def retained_cycle(
    source_model,
    *,
    phase="reviewed",
    qualification=QUALIFICATION,
    previous=None,
    predecessor=None,
    raw=False,
    ownership=None,
    observed=False,
):
    owner, prerequisites, state = source_model
    start(source_model, qualification=qualification, previous=previous)
    original = (
        state["add"](
            RAW, label=label("isolation_original", qualification), media="text/plain"
        )
        if raw
        else None
    )
    records = qualification_records(
        prerequisites,
        owner.descriptor(),
        state["header"].header_sha256,
        state["source_artifacts"],
        qualification=qualification,
        original_ref=original,
        predecessor=predecessor,
        ownership=ownership,
        observed=observed,
    )
    refs = {
        "receipt": state["add"](
            records["receipt"].payload, label=label("receipt", qualification)
        )
    }
    if phase != "receipt-only":
        refs["assessment"] = state["add"](
            records["assessment"].payload, label=label("assessment", qualification)
        )
    cited = [*refs.values(), *([] if original is None else [original])]
    if phase in {"review-pending", "review-retained", "reviewed"}:
        state["advance"](
            v2.V2StageState.REVIEW_PENDING, code("ASSESSED", qualification), cited
        )
    if phase in {"review-retained", "reviewed"}:
        refs["review"] = state["add"](
            records["review"].payload, label=label("review", qualification)
        )
    if phase == "reviewed":
        verdict = records["review"].to_dict()["verdict"]
        state["advance"](
            v2.V2StageState(verdict),
            code("REVIEWED_" + verdict, qualification),
            [*cited, refs["review"]],
        )
    return records, refs, original


def covered_ownership(source_model, qualification=QUALIFICATION):
    from test_physical_ownership_qualification import modeled_report

    descriptor = source_model[0].descriptor()
    return modeled_report(
        source_sha256=SOURCE,
        directory=Path(descriptor["directory"])
        / ("source-ownership-" + qualification[11:]),
        workspace=Path(descriptor["workspace"]),
        covered=True,
    )


@pytest.mark.parametrize("enter_stage2", [False, True])
@pytest.mark.parametrize("intake", [False, True])
def test_actual_codecs_reviewed_pass_requires_separate_explicit_stage2_event(
    source_model, enter_stage2, intake
):
    owner, _, state = source_model
    previous = None
    if intake:
        _, intake_refs, _ = complete_intake(source_model, reviewed=True)
        previous = {
            **{"source_" + key: ref for key, ref in state["source_refs"].items()},
            **intake_refs,
        }
    records, refs, _ = retained_cycle(
        source_model,
        previous=previous,
        raw=True,
        observed=True,
        ownership=covered_ownership(source_model),
    )
    assert records["assessment"].to_dict()["verdict"] == "PASS"
    if enter_stage2:
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            "STATIC_CAMERA_CONTRACT_REQUESTED_" + QUALIFICATION[11:].upper(),
            stage=STAGE_ORDER[1],
        )
    before = state["snapshot"]()
    result = refresh_read(source_model)
    assert result["state"] == "PASS"
    assert result["qualification_cycles"][0]["state"] == "REVIEWED_PASS"
    assert result["original_source_state"] == "BLOCKED"
    assert result["assessment"]["document"]["verdict"] == "BLOCKED"
    assert result["static_camera_request"] == (
        before.committed_events[-1].to_dict() if enter_stage2 else None
    )
    assert owner.view()["stages"][1]["state"] == (
        "WAITING_OPERATOR" if enter_stage2 else "PENDING"
    )
    assert all(stage["state"] == "PENDING" for stage in owner.view()["stages"][2:])
    assert state["snapshot"]() == before
    assert result["physical_authority"] is result["device_io_performed"] is False
    assert module._decode_cached_source_workflow(canonical(result)) == result
    pending, depth_max, nodes = [(result, 0)], 0, 0
    while pending:
        item, depth = pending.pop()
        nodes += 1
        depth_max = max(depth_max, depth)
        if type(item) is dict:
            for key, child in item.items():
                pending.extend(((key, depth + 1), (child, depth + 1)))
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
    assert depth_max <= module.MAX_SOURCE_WORKFLOW_CACHE_DEPTH
    assert nodes <= module.MAX_SOURCE_WORKFLOW_CACHE_NODES
    print(
        f"V4_COVERED_CACHE bytes={len(canonical(result))} depth={depth_max} nodes={nodes}"
    )


@pytest.mark.parametrize(
    "phase,expected",
    [
        ("assessment-retained", "ASSESSMENT_RETAINED_NOT_COMMITTED"),
        ("review-retained", "REVIEW_RETAINED_NOT_COMMITTED"),
    ],
)
def test_eligible_retained_subject_does_not_imply_committed_pass(
    source_model, phase, expected
):
    records, _, _ = retained_cycle(
        source_model,
        phase=phase,
        raw=True,
        observed=True,
        ownership=covered_ownership(source_model),
    )
    assert records["assessment"].to_dict()["verdict"] == "PASS"
    result = refresh_read(source_model)
    assert result["qualification_cycles"][0]["state"] == expected
    assert result["state"] in {"WAITING_OPERATOR", "REVIEW_PENDING"}
    assert result["static_camera_request"] is None


@pytest.mark.parametrize(
    "fault",
    [
        "wrong-stage2-id",
        "cross-stage-reference",
        "duplicate-stage2",
        "stage3",
        "successor-after-pass",
        "blocked-verdict-pass-event",
    ],
)
def test_pass_does_not_relax_later_stage_or_exact_review_grammar(source_model, fault):
    _, _, state = source_model
    records, refs, _ = retained_cycle(
        source_model,
        raw=True,
        observed=fault != "blocked-verdict-pass-event",
        ownership=covered_ownership(source_model),
    )
    static = "STATIC_CAMERA_CONTRACT_REQUESTED_" + QUALIFICATION[11:].upper()
    if fault == "wrong-stage2-id":
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            "STATIC_CAMERA_CONTRACT_REQUESTED_" + SECOND[11:].upper(),
            stage=STAGE_ORDER[1],
        )
    elif fault == "cross-stage-reference":
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            static,
            (refs["review"],),
            stage=STAGE_ORDER[1],
        )
    elif fault in {"duplicate-stage2", "stage3"}:
        state["advance"](v2.V2StageState.WAITING_OPERATOR, static, stage=STAGE_ORDER[1])
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            static,
            stage=STAGE_ORDER[1] if fault == "duplicate-stage2" else STAGE_ORDER[2],
        )
    elif fault == "successor-after-pass":
        start(source_model, qualification=SECOND, previous=refs)
    else:
        state["events"][-1] = replace(
            state["events"][-1],
            state=v2.V2StageState.PASS,
            detail_code=code("REVIEWED_PASS"),
        )
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(source_model)


@pytest.mark.parametrize(
    "phase,expected",
    [
        ("receipt-only", "INCOMPLETE"),
        ("assessment-retained", "ASSESSMENT_RETAINED_NOT_COMMITTED"),
        ("review-pending", "REVIEW_PENDING"),
        ("review-retained", "REVIEW_RETAINED_NOT_COMMITTED"),
        ("reviewed", "REVIEWED_BLOCKED"),
    ],
)
@pytest.mark.parametrize("raw", [False, True])
def test_real_qualification_codecs_preserve_every_retained_commit_boundary(
    source_model, phase, expected, raw
):
    owner, _, state = source_model
    records, refs, original = retained_cycle(source_model, phase=phase, raw=raw)
    before = state["snapshot"]()
    result = refresh_read(source_model)
    cycle = result["qualification_cycles"][0]
    assert cycle["state"] == expected
    for role in refs:
        assert canonical(cycle[role]["document"]) == records[role].payload
        assert cycle[role]["reference"] == refs[role].to_dict()
    assert records["assessment"].to_dict()["verdict"] == "BLOCKED"
    assert result["static_camera_request"] is None
    assert state["snapshot"]() == before
    assert owner.retained_source_workflow() == result
    assert RAW not in canonical(result)


@pytest.mark.parametrize("covered", [False, True])
def test_eight_blocked_successors_bind_exact_previous_trio_with_bounded_cache(
    source_model,
    covered,
):
    owner, _, state = source_model
    previous = predecessor = None
    for index in range(8):
        qualification = f"sourcequal-{index + 20:032x}"
        predecessor, previous, _ = retained_cycle(
            source_model,
            qualification=qualification,
            previous=previous,
            predecessor=predecessor,
            ownership=(
                covered_ownership(source_model, qualification) if covered else None
            ),
        )
    result = refresh_read(source_model)
    assert len(result["qualification_cycles"]) == 8
    assert len(state["references"]) == 28
    assert all(
        row["state"] == "REVIEWED_BLOCKED" for row in result["qualification_cycles"]
    )
    wire = canonical(result)
    assert len(wire) <= module.MAX_SOURCE_WORKFLOW_BYTES
    assert module._decode_cached_source_workflow(wire) == result
    assert owner.retained_source_workflow() == result
    pending, maximum_depth, nodes = [(result, 0)], 0, 0
    while pending:
        item, depth = pending.pop()
        maximum_depth = max(maximum_depth, depth)
        nodes += 1
        if type(item) is dict:
            for key, child in item.items():
                pending.extend(((key, depth + 1), (child, depth + 1)))
        elif type(item) is list:
            pending.extend((child, depth + 1) for child in item)
    assert maximum_depth <= module.MAX_SOURCE_WORKFLOW_CACHE_DEPTH
    assert nodes <= module.MAX_SOURCE_WORKFLOW_CACHE_NODES
    print(
        f"V4_EIGHT_CACHE ownership_covered={covered} bytes={len(wire)} "
        f"depth={maximum_depth} nodes={nodes}"
    )


def test_blocked_successor_correction_preserves_both_exact_reviewed_subjects(
    source_model,
):
    original, previous, _ = retained_cycle(source_model)
    corrected, refs, _ = retained_cycle(
        source_model,
        qualification=SECOND,
        previous=previous,
        predecessor=original,
        raw=True,
        observed=True,
        ownership=covered_ownership(source_model, SECOND),
    )
    result = refresh_read(source_model)
    assert [row["state"] for row in result["qualification_cycles"]] == [
        "REVIEWED_BLOCKED",
        "REVIEWED_PASS",
    ]
    for index, subjects in enumerate((original, corrected)):
        for role in ("receipt", "assessment", "review"):
            assert (
                canonical(result["qualification_cycles"][index][role]["document"])
                == subjects[role].payload
            )
    assert result["state"] == "PASS" and result["static_camera_request"] is None


def test_self_consistent_wrong_workspace_owner_report_is_not_original_context(
    source_model,
):
    from test_physical_ownership_qualification import modeled_report

    owner, _, _ = source_model
    bound = owner.descriptor()
    wrong_workspace = Path(bound["workspace"]).parent / "other-modeled-workspace"
    report = modeled_report(
        source_sha256=SOURCE,
        directory=Path(bound["directory"]) / ("source-ownership-" + QUALIFICATION[11:]),
        workspace=wrong_workspace,
        covered=True,
    )
    # The real nested codec is structurally valid, with matching source and
    # experiment directory. Only the original-store context detects this swap.
    records, _, _ = retained_cycle(
        source_model, ownership=report, raw=True, observed=True
    )
    assert records["assessment"].to_dict()["verdict"] == "PASS"
    with pytest.raises(module.PhysicalCameraSessionError) as error:
        refresh_read(source_model)
    assert error.value.code == "CAMERA_SESSION_SOURCE_QUALIFICATION_CHAIN"


@pytest.mark.parametrize(
    "fault",
    [
        "wrong-predecessor",
        "wrong-original-source",
        "wrong-directory",
        "wrong-isolation-ref",
        "wrong-basename",
        "wrong-media-signature",
        "review-verdict",
        "review-event-refs",
        "duplicate-receipt",
        "ninth-cycle",
    ],
)
def test_complete_subject_tampering_cannot_be_promoted_by_rehashed_references(
    source_model, fault
):
    _, _, state = source_model
    if fault == "ninth-cycle":
        predecessor = previous = None
        for index in range(9):
            predecessor, previous, _ = retained_cycle(
                source_model,
                qualification=f"sourcequal-{index + 20:032x}",
                previous=previous,
                predecessor=predecessor,
            )
    else:
        records, refs, original = retained_cycle(source_model, raw=True)
        if fault == "duplicate-receipt":
            state["add"](records["receipt"].payload, label=label("receipt"))
        elif fault == "review-event-refs":
            state["events"][-1] = replace(
                state["events"][-1], evidence=(refs["review"],)
            )
        elif fault == "wrong-media-signature":
            replacement = replace(
                original, payload_sha256=digest(b"\0bad"), payload_bytes=4
            )
            state["references"][state["references"].index(original)] = replacement
            state["payloads"][original.evidence_id] = b"\0bad"
        else:
            role = "review" if fault == "review-verdict" else "receipt"
            document = records[role].to_dict()
            if fault == "wrong-predecessor":
                document["binding"]["predecessor_qualification"] = {
                    key: "f" * 64 for key in ("receipt", "assessment", "review")
                }
            elif fault == "wrong-original-source":
                document["binding"]["predecessor_source"]["review"] = "f" * 64
            elif fault == "wrong-directory":
                document["binding"]["store_directory"] += "-replacement"
            elif fault == "wrong-isolation-ref":
                document["isolation"]["original_reference"] = state["references"][
                    0
                ].to_dict()
            elif fault == "wrong-basename":
                document["isolation"]["basename"] = "not-a-pdf.pdf"
            else:
                document["verdict"] = "PASS"
            raw = canonical(document)
            original_ref = refs[role]
            replacement = replace(
                original_ref, payload_sha256=digest(raw), payload_bytes=len(raw)
            )
            state["references"][state["references"].index(original_ref)] = replacement
            state["payloads"][original_ref.evidence_id] = raw
            state["events"][:] = [
                replace(
                    event,
                    evidence=tuple(
                        replacement if ref == original_ref else ref
                        for ref in event.evidence
                    ),
                )
                for event in state["events"]
            ]
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(source_model)


@pytest.mark.parametrize("raw", [False, True])
@pytest.mark.parametrize("intake", [False, True])
def test_start_or_raw_only_is_original_partial_without_replay(
    source_model, raw, intake
):
    owner, _, state = source_model
    refs = None
    if intake:
        _, refs, _ = complete_intake(source_model, reviewed=True)
    start(source_model, intake_refs=refs)
    original_ref = (
        state["add"](RAW, label=label("isolation_original"), media="text/plain")
        if raw
        else None
    )
    before = state["snapshot"]()
    result = refresh_read(source_model)
    assert result["schema"] == module.SOURCE_WORKFLOW_QUALIFICATION_SCHEMA
    assert result["state"] == "WAITING_OPERATOR"
    assert result["original_source_state"] == "BLOCKED"
    assert result["assessment"]["document"]["verdict"] == "BLOCKED"
    assert len(result["intake_collections"]) == int(intake)
    cycle = result["qualification_cycles"][0]
    assert cycle["qualification_id"] == QUALIFICATION and cycle["state"] == "INCOMPLETE"
    assert cycle["receipt"] is cycle["assessment"] is cycle["review"] is None
    assert (
        cycle["isolation_original"] is None
        if original_ref is None
        else cycle["isolation_original"]["reference"] == original_ref.to_dict()
    )
    assert result["static_camera_request"] is None
    assert state["snapshot"]() == before
    assert state["enters"] == state["exits"] == 1
    assert all(item["state"] == "PENDING" for item in owner.view()["stages"][1:])
    assert RAW not in canonical(result)
    cycle["state"] = "REVIEWED_PASS"
    assert (
        owner.retained_source_workflow()["qualification_cycles"][0]["state"]
        == "INCOMPLETE"
    )


@pytest.mark.parametrize(
    "fault",
    [
        "orphan",
        "duplicate-raw",
        "raw-media",
        "wrong-stage",
        "unknown-label",
        "raw-hash",
        "uncommitted",
        "prefix-code",
        "start-refs",
        "start-unsorted",
        "assessment-without-records",
        "review-without-records",
        "stage2-before-pass",
        "interleaved-intake",
        "extra-stage2-package",
    ],
)
def test_closed_partial_grammar_and_original_roles_reject_faults(source_model, fault):
    _, _, state = source_model
    if fault != "orphan":
        start(source_model)
    ref = state["add"](RAW, label=label("isolation_original"), media="text/plain")
    if fault == "duplicate-raw":
        state["add"](
            RAW + b"second", label=label("isolation_original"), media="text/plain"
        )
    elif fault in {"raw-media", "unknown-label"}:
        manifest = canonical(
            {
                "label": (
                    label("isolation_original")
                    if fault == "raw-media"
                    else "arbitrary-source-qualification"
                ),
                "media_type": (
                    "application/octet-stream" if fault == "raw-media" else "text/plain"
                ),
            }
        )
        state["manifests"][ref.evidence_id] = manifest
        state["references"][-1] = replace(ref, manifest_sha256=digest(manifest))
    elif fault == "wrong-stage":
        state["references"][-1] = replace(ref, stage=STAGE_ORDER[1])
    elif fault == "raw-hash":
        state["payloads"][ref.evidence_id] = b"not the retained bytes"
    elif fault == "uncommitted":
        state["uncommitted"] = (
            replace(state["events"][-1], detail_code="UNCOMMITTED_UNKNOWN"),
        )
    elif fault == "prefix-code":
        state["events"][1] = replace(state["events"][1], detail_code="OTHER_ASSESSMENT")
    elif fault == "start-refs":
        state["events"][-1] = replace(state["events"][-1], evidence=())
    elif fault == "start-unsorted":
        state["events"][-1] = replace(
            state["events"][-1], evidence=tuple(reversed(state["events"][-1].evidence))
        )
    elif fault == "assessment-without-records":
        state["advance"](v2.V2StageState.REVIEW_PENDING, code("ASSESSED"), (ref,))
    elif fault == "review-without-records":
        state["advance"](v2.V2StageState.BLOCKED, code("REVIEWED_BLOCKED"))
    elif fault == "stage2-before-pass":
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            "STATIC_CAMERA_CONTRACT_REQUESTED_" + QUALIFICATION[11:].upper(),
            stage=STAGE_ORDER[1],
        )
    elif fault == "interleaved-intake":
        state["advance"](
            v2.V2StageState.REVIEW_PENDING,
            "PHYSICAL_INTAKE_SUBMITTED_" + "6" * 32,
            (ref,),
        )
    elif fault == "extra-stage2-package":
        state["add"](
            b"{}", label="static-camera-contract-unreviewed", stage=STAGE_ORDER[1]
        )
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(source_model)


@pytest.mark.parametrize(
    "fault", ["lease-exit", "coherence", "late-source", "late-stop", "late-deadline"]
)
def test_late_partial_failure_preserves_original_historical_bytes(source_model, fault):
    owner, _, state = source_model
    start(source_model)
    state["add"](RAW, label=label("isolation_original"), media="text/plain")
    cancellation = threading.Event()
    if fault == "lease-exit":
        state["exit_failure"] = True
    if fault == "coherence":
        state["after_change"] = "session_head_sha256"

    def progress(message):
        if "finished" in message:
            if fault == "late-source":
                state["source"] = "f" * 64
            if fault == "late-stop":
                cancellation.set()
            if fault == "late-deadline":
                state["now"] += module.DIAGNOSTIC_TIMEOUT_NS

    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(source_model, cancellation=cancellation, progress=progress)
    assert (
        owner.retained_source_workflow()["qualification_cycles"][0]["state"]
        == "INCOMPLETE"
    )
    assert owner.view()["status"] == "HELD" and owner._store is None


@pytest.mark.skipif(os.name != "nt", reason="actual isolated NTFS and original leases")
def test_actual_ntfs_partial_successor_reopens_original_bytes_without_collection(
    workspace, monkeypatch
):
    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    prerequisites = generate(workspace)
    owner = session_fixture(workspace)
    initial = perform(owner)
    header = initial["verification"]["session"]["header_sha256"]
    sources = collect_chain(prerequisites, header, monkeypatch)
    with owner.stage_transaction(
        expected_challenge_sha256=initial["verification"]["challenge_sha256"]
    ) as tx:

        def commit(state, detail, refs=()):
            tx.commit_stage_state(
                STAGE_ORDER[0],
                state,
                occurred_at_ns=time.time_ns(),
                detail_code=detail,
                expected_head_sha256=tx.snapshot().head.head_sha256,
                evidence=tuple(sorted(refs, key=lambda ref: ref.evidence_id)),
            )

        def retain(payload, name, media="application/json"):
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
        retain(prerequisites.payload, module.PREREQUISITE_LABEL)
        refs = {
            role: retain(sources[role].payload, f"workspace-source-{role}-v1")
            for role in ("receipt", "assessment")
        }
        commit(v2.V2StageState.REVIEW_PENDING, SOURCE_CODES[1], refs.values())
        refs["review"] = retain(sources["review"].payload, "workspace-source-review-v1")
        commit(v2.V2StageState.BLOCKED, SOURCE_CODES[2], refs.values())
        commit(v2.V2StageState.WAITING_OPERATOR, code("STARTED"), refs.values())
        original = retain(RAW, label("isolation_original"), "text/plain")
        expected_head = tx.snapshot().head

    from rocell.application import physical_source_stage_evidence as source_module

    monkeypatch.setattr(
        source_module,
        "collect_workspace_source_receipt",
        lambda *a, **k: pytest.fail("restart recollected source facts"),
    )
    reopened = session_fixture(workspace)
    before = perform(reopened, "refresh")
    result = read(reopened, header)
    assert result["session_head_sha256"] == expected_head.head_sha256
    cycle = result["qualification_cycles"][0]
    assert cycle["state"] == "INCOMPLETE"
    assert cycle["isolation_original"]["reference"] == original.to_dict()
    assert cycle["receipt"] is cycle["assessment"] is cycle["review"] is None
    assert RAW not in canonical(result)
    assert (
        result["state"] == "WAITING_OPERATOR"
        and result["static_camera_request"] is None
    )
    assert reopened.view()["stages"] == before["stages"]
    assert all(stage["state"] == "PENDING" for stage in before["stages"][1:])
    with reopened.stage_transaction(
        expected_challenge_sha256=reopened.view()["verification"]["challenge_sha256"]
    ) as tx:
        assert tx.read_stage_evidence(original) == RAW
        assert tx.snapshot().head == expected_head


@pytest.mark.skipif(os.name != "nt", reason="actual isolated NTFS and original leases")
def test_actual_ntfs_modeled_pass_restarts_at_each_commit_boundary_without_replay(
    workspace, monkeypatch
):
    """Actual original M1 storage; isolation and owner coverage are MODELED ONLY."""
    from rocell.application import physical_source_stage_evidence as source_module
    from test_physical_ownership_qualification import modeled_report

    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    prerequisites = generate(workspace)
    owner = session_fixture(workspace)
    initial = perform(owner)
    header = initial["verification"]["session"]["header_sha256"]
    descriptor = owner.descriptor()
    sources = collect_chain(prerequisites, header, monkeypatch)
    covered = modeled_report(
        source_sha256=SOURCE,
        directory=Path(descriptor["directory"])
        / ("source-ownership-" + QUALIFICATION[11:]),
        workspace=Path(descriptor["workspace"]),
        covered=True,
    )

    def commit(tx, state, detail, refs=(), *, stage=STAGE_ORDER[0]):
        tx.commit_stage_state(
            stage,
            state,
            occurred_at_ns=time.time_ns(),
            detail_code=detail,
            expected_head_sha256=tx.snapshot().head.head_sha256,
            evidence=tuple(sorted(refs, key=lambda ref: ref.evidence_id)),
        )

    def retain(tx, payload, name, media="application/json"):
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

    with owner.stage_transaction(
        expected_challenge_sha256=initial["verification"]["challenge_sha256"]
    ) as tx:
        commit(tx, v2.V2StageState.WAITING_OPERATOR, SOURCE_CODES[0])
        retain(tx, prerequisites.payload, module.PREREQUISITE_LABEL)
        source_refs = {
            role: retain(tx, sources[role].payload, f"workspace-source-{role}-v1")
            for role in ("receipt", "assessment")
        }
        commit(
            tx, v2.V2StageState.REVIEW_PENDING, SOURCE_CODES[1], source_refs.values()
        )
        source_refs["review"] = retain(
            tx, sources["review"].payload, "workspace-source-review-v1"
        )
        commit(tx, v2.V2StageState.BLOCKED, SOURCE_CODES[2], source_refs.values())
        commit(
            tx, v2.V2StageState.WAITING_OPERATOR, code("STARTED"), source_refs.values()
        )
        original = retain(tx, RAW, label("isolation_original"), "text/plain")
        subjects = qualification_records(
            prerequisites,
            descriptor,
            header,
            sources,
            original_ref=original,
            ownership=covered,
            observed=True,
        )
        assert subjects["assessment"].to_dict()["verdict"] == "PASS"
        refs = {
            role: retain(tx, subjects[role].payload, label(role))
            for role in ("receipt", "assessment")
        }
        expected_head = tx.snapshot().head

    monkeypatch.setattr(
        source_module,
        "collect_workspace_source_receipt",
        lambda *a, **k: pytest.fail("restart recollected source facts"),
    )

    def reopen(expected_state, expected_canonical, *, stage2=False):
        reopened = session_fixture(workspace)
        before = perform(reopened, "refresh")
        result = read(reopened, header)
        assert result["session_head_sha256"] == expected_head.head_sha256
        assert result["qualification_cycles"][0]["state"] == expected_state
        assert result["state"] == expected_canonical
        assert result["assessment"]["document"]["verdict"] == "BLOCKED"
        assert (result["static_camera_request"] is not None) is stage2
        assert before["stages"] == reopened.view()["stages"]
        assert before["stages"][1]["state"] == (
            "WAITING_OPERATOR" if stage2 else "PENDING"
        )
        assert all(row["state"] == "PENDING" for row in before["stages"][2:])
        for role in refs:
            assert (
                canonical(result["qualification_cycles"][0][role]["document"])
                == subjects[role].payload
            )
        assert RAW not in canonical(result)
        return reopened

    owner = reopen("ASSESSMENT_RETAINED_NOT_COMMITTED", "WAITING_OPERATOR")
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        commit(
            tx,
            v2.V2StageState.REVIEW_PENDING,
            code("ASSESSED"),
            [original, *refs.values()],
        )
        refs["review"] = retain(tx, subjects["review"].payload, label("review"))
        expected_head = tx.snapshot().head
    owner = reopen("REVIEW_RETAINED_NOT_COMMITTED", "REVIEW_PENDING")
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        commit(
            tx, v2.V2StageState.PASS, code("REVIEWED_PASS"), [original, *refs.values()]
        )
        expected_head = tx.snapshot().head
    owner = reopen("REVIEWED_PASS", "PASS")
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        assert tx.read_stage_evidence(original) == RAW
        commit(
            tx,
            v2.V2StageState.WAITING_OPERATOR,
            "STATIC_CAMERA_CONTRACT_REQUESTED_" + QUALIFICATION[11:].upper(),
            stage=STAGE_ORDER[1],
        )
        expected_head = tx.snapshot().head
    reopen("REVIEWED_PASS", "PASS", stage2=True)
