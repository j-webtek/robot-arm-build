"""Actual design files and original-journal codecs; no received hardware.

Source isolation/ownership predecessors are explicitly modeled. Static design
records come from the actual fixed-file collector. Pure tests model storage
leases only; the separate NTFS test retains and reopens actual original bytes.
"""

from dataclasses import replace
import os
from pathlib import Path
from threading import Event
import time

import pytest

from rocell.application import physical_camera_session as module
from rocell.application import physical_onboarding_v2 as v2
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.providers.windows.native_camera_protocol import canonical, digest

from test_physical_source_qualification_readback import (
    source_model,
    retained_cycle,
    covered_ownership,
    refresh_read,
    QUALIFICATION,
)
from test_physical_camera_intake_session import (
    intake_model,
    complete as complete_intake,
)
from test_physical_camera_session_readback import model, no_devices, workspace, generate
from test_physical_camera_session import SOURCE, LAUNCH, session_fixture, perform

WORKSPACE = Path(__file__).resolve().parents[3]
CONTRACT = "staticcontract-" + "6" * 32
OTHER_CONTRACT = "staticcontract-" + "7" * 32


def label(role, contract=CONTRACT):
    return f"static-camera-contract-{role}-v1:{contract}"


def code(phase, contract=CONTRACT):
    return f"STATIC_CAMERA_CONTRACT_{phase}_{contract[15:].upper()}"


def enter_static(source_model, *, cycles=1, intake=False, early_originals=0):
    """Exact typed source prefix; positive isolation remains modeled only."""
    _, _, state = source_model
    intake_refs = None
    if intake:
        _, intake_refs, _ = complete_intake(source_model, reviewed=True)
    advance = state["advance"]
    first_start = True

    def cite_intake(next_state, detail, refs=(), **kwargs):
        nonlocal first_start
        if first_start and detail.startswith("WORKSPACE_SOURCE_QUALIFICATION_STARTED_"):
            first_start = False
            refs = [*refs, *(intake_refs or {}).values()]
        return advance(next_state, detail, refs, **kwargs)

    state["advance"] = cite_intake
    previous = predecessor = None
    try:
        for index in range(cycles):
            qualification = f"sourcequal-{index + 40:032x}"
            final = index == cycles - 1
            predecessor, previous, _ = retained_cycle(
                source_model,
                qualification=qualification,
                previous=previous,
                predecessor=predecessor,
                raw=final or index < early_originals,
                observed=final,
                ownership=covered_ownership(source_model, qualification),
            )
    finally:
        state["advance"] = advance
    state["advance"](
        v2.V2StageState.WAITING_OPERATOR,
        "STATIC_CAMERA_CONTRACT_REQUESTED_" + qualification[11:].upper(),
        stage=STAGE_ORDER[1],
    )
    state["qualified_sources"] = predecessor
    return predecessor


@pytest.fixture
def static_ready(source_model):
    enter_static(source_model)
    return source_model


def actual_static_subjects(source_model, monkeypatch, *, contract=CONTRACT):
    """Real fixed design bytes/calculations, explicitly modeled source hash."""
    from rocell.application import physical_static_contract as codec

    owner, prerequisites, state = source_model
    sources = state["qualified_sources"]
    descriptor = owner.descriptor()
    binding = {
        "contract_id": contract,
        "source_sha256": SOURCE,
        "cell_id": descriptor["cell_id"],
        "session_id": descriptor["session_id"],
        "header_sha256": state["header"].header_sha256,
        "origin_launch_id": descriptor["launch_id"],
        "collection_launch_id": "wizard-" + "8" * 32,
        "operator_id": "static-operator",
        "prerequisites_sha256": prerequisites.evidence_sha256,
        "source_qualification": {role: value.sha256 for role, value in sources.items()},
        "static_request_event_sha256": next(
            event.event_sha256
            for event in state["events"]
            if event.detail_code.startswith("STATIC_CAMERA_CONTRACT_REQUESTED_")
        ),
        "store_directory": descriptor["directory"],
    }
    monkeypatch.setattr(codec, "source_fingerprint", lambda _: SOURCE)
    receipt = codec.collect_static_camera_contract(
        WORKSPACE,
        binding=binding,
        source_qualification=sources["receipt"],
        cancellation=Event(),
        progress=lambda _: None,
        deadline_ns=time.monotonic_ns() + 30_000_000_000,
    )
    assessment = codec.assess_static_camera_contract(receipt)
    review = codec.review_static_camera_contract(
        receipt,
        assessment,
        reviewer_id="static-reviewer",
        review_launch_id=LAUNCH,
        reviewed_at_ns=time.time_ns(),
    )
    return {"receipt": receipt, "assessment": assessment, "review": review}


def retain_static(source_model, subjects, *, phase="reviewed", camera_entry=False):
    _, _, state = source_model
    contract = subjects["receipt"].to_dict()["binding"]["contract_id"]
    refs = {
        "receipt": state["add"](
            subjects["receipt"].payload,
            label=label("receipt", contract),
            stage=STAGE_ORDER[1],
        )
    }
    if phase != "receipt-only":
        refs["assessment"] = state["add"](
            subjects["assessment"].payload,
            label=label("assessment", contract),
            stage=STAGE_ORDER[1],
        )
    if phase in {"review-pending", "review-retained", "reviewed"}:
        state["advance"](
            v2.V2StageState.REVIEW_PENDING,
            code("COLLECTED", contract),
            refs.values(),
            stage=STAGE_ORDER[1],
        )
    if phase in {"review-retained", "reviewed"}:
        refs["review"] = state["add"](
            subjects["review"].payload,
            label=label("review", contract),
            stage=STAGE_ORDER[1],
        )
    if phase == "reviewed":
        verdict = subjects["review"].to_dict()["verdict"]
        state["advance"](
            v2.V2StageState(verdict),
            code("REVIEWED_" + verdict, contract),
            refs.values(),
            stage=STAGE_ORDER[1],
        )
    if camera_entry:
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            "CAMERA_RECEIPT_REQUESTED_" + contract[15:].upper(),
            stage=STAGE_ORDER[2],
        )
    return refs


def test_before_collection_retains_exact_v4_shape(static_ready):
    result = refresh_read(static_ready)
    assert result["schema"] == module.SOURCE_WORKFLOW_QUALIFICATION_SCHEMA
    assert "static_contract" not in result and "camera_receipt_request" not in result
    assert result["state"] == "PASS"
    assert result["static_camera_request"]["state"] == "WAITING_OPERATOR"


@pytest.mark.parametrize(
    "phase,expected",
    [
        ("receipt-only", "INCOMPLETE"),
        ("assessment-retained", "ASSESSMENT_RETAINED_NOT_COMMITTED"),
        ("review-pending", "REVIEW_PENDING"),
        ("review-retained", "REVIEW_RETAINED_NOT_COMMITTED"),
        ("reviewed", "REVIEWED_PASS"),
    ],
)
def test_actual_producer_every_partial_and_committed_boundary(
    static_ready, monkeypatch, phase, expected
):
    from rocell.application import physical_static_contract as codec

    owner, _, state = static_ready
    original = refresh_read(static_ready)
    subjects = actual_static_subjects(static_ready, monkeypatch)
    assert subjects["assessment"].to_dict()["verdict"] == "PASS"
    refs = retain_static(static_ready, subjects, phase=phase)
    monkeypatch.setattr(
        codec, "collect_static_camera_contract", lambda *a, **kw: pytest.fail("replay")
    )
    before = state["snapshot"]()
    result = refresh_read(static_ready)
    assert result["schema"] == module.SOURCE_WORKFLOW_STATIC_SCHEMA
    assert result["static_contract"]["state"] == expected
    assert result["static_contract"]["contract_id"] == CONTRACT
    assert result["camera_receipt_request"] is None
    assert state["snapshot"]() == before
    for role in refs:
        record = result["static_contract"][role]
        assert record["reference"] == refs[role].to_dict()
        assert canonical(record["document"]) == subjects[role].payload
    for key in (
        "receipt",
        "assessment",
        "review",
        "qualification_cycles",
        "static_camera_request",
    ):
        assert result[key] == original[key]
    assert result["physical_authority"] is result["device_io_performed"] is False
    assert all(row.state is v2.V2StageState.PENDING for row in before.stages[2:])
    assert owner.retained_source_workflow() == result


def test_review_pass_never_enters_received_camera_until_explicit_event(
    static_ready, monkeypatch
):
    _, _, state = static_ready
    subjects = actual_static_subjects(static_ready, monkeypatch)
    retain_static(static_ready, subjects)
    first = refresh_read(static_ready)
    assert first["static_contract"]["state"] == "REVIEWED_PASS"
    assert first["camera_receipt_request"] is None
    state["advance"](
        v2.V2StageState.WAITING_OPERATOR,
        "CAMERA_RECEIPT_REQUESTED_" + CONTRACT[15:].upper(),
        stage=STAGE_ORDER[2],
    )
    result = refresh_read(static_ready)
    assert result["camera_receipt_request"] == state["events"][-1].to_dict()
    assert not result["camera_receipt_request"]["evidence"]
    assert state["snapshot"]().stages[2].state is v2.V2StageState.WAITING_OPERATOR


@pytest.mark.parametrize("force_entry", [False, True])
def test_modeled_retained_source_conflict_reviews_blocked_and_holds_stage3(
    static_ready, monkeypatch, force_entry
):
    from rocell.application import physical_static_contract as codec

    # Explicit source-conflict model, not an edited verdict/check boolean:
    # retain a valid support JSON with different exact original bytes. The real
    # pure parser then detects its hash differs from the qualified source.
    subjects = actual_static_subjects(static_ready, monkeypatch)
    data = subjects["receipt"].to_dict()
    row = next(
        row
        for row in data["source_files"]
        if row["relative_path"] == codec.SUPPORT_PATH
    )
    row["utf8"] += "\n"
    raw = row["utf8"].encode("utf-8")
    row.update(bytes=len(raw), sha256=digest(raw))
    data.update(codec._derived(data["source_files"], data["software_receipt"]))
    receipt = codec.StaticCameraContractReceipt(canonical(data))
    assessment = codec.assess_static_camera_contract(receipt)
    assert assessment.to_dict()["verdict"] == "BLOCKED"
    review = codec.review_static_camera_contract(
        receipt,
        assessment,
        reviewer_id="static-reviewer",
        review_launch_id=LAUNCH,
        reviewed_at_ns=time.time_ns(),
    )
    retain_static(
        static_ready,
        {"receipt": receipt, "assessment": assessment, "review": review},
        camera_entry=force_entry,
    )
    if force_entry:
        with pytest.raises(module.PhysicalCameraSessionError):
            refresh_read(static_ready)
    else:
        result = refresh_read(static_ready)
        assert result["static_contract"]["state"] == "REVIEWED_BLOCKED"
        assert result["camera_receipt_request"] is None


@pytest.mark.parametrize(
    "fault",
    [
        "orphan",
        "wrong-stage",
        "wrong-media",
        "unknown-label",
        "duplicate",
        "other-cycle",
        "bad-hash",
        "assessment-only",
        "review-before-collected",
        "wrong-collected-id",
        "wrong-collected-refs",
        "stage3-before-review",
        "stage3-wrong-id",
        "stage3-cross-reference",
        "repeat-stage3",
        "later-stage",
        "uncommitted",
        "prefix-source-code",
        "prefix-static-code",
    ],
)
def test_closed_static_roles_and_full_journal_refuse_faults(
    static_ready, monkeypatch, fault
):
    _, _, state = static_ready
    subjects = actual_static_subjects(static_ready, monkeypatch)
    phase = "review-pending" if fault == "stage3-before-review" else "reviewed"
    refs = retain_static(static_ready, subjects, phase=phase)
    if fault == "orphan":
        state["events"] = state["events"][:3]
    elif fault in {"wrong-stage", "bad-hash"}:
        old = refs["receipt"]
        state["references"][state["references"].index(old)] = replace(
            old,
            **(
                {"stage": STAGE_ORDER[0]}
                if fault == "wrong-stage"
                else {"payload_sha256": "f" * 64}
            ),
        )
    elif fault in {"wrong-media", "unknown-label"}:
        old = refs["receipt"]
        manifest = canonical(
            {
                "label": (
                    label("receipt")
                    if fault == "wrong-media"
                    else "unknown-static-role"
                ),
                "media_type": (
                    "text/plain" if fault == "wrong-media" else "application/json"
                ),
            }
        )
        state["manifests"][old.evidence_id] = manifest
        state["references"][state["references"].index(old)] = replace(
            old, manifest_sha256=digest(manifest)
        )
    elif fault in {"duplicate", "other-cycle"}:
        state["add"](
            subjects["receipt"].payload,
            label=label(
                "receipt", CONTRACT if fault == "duplicate" else OTHER_CONTRACT
            ),
            stage=STAGE_ORDER[1],
        )
    elif fault == "assessment-only":
        state["references"].remove(refs["receipt"])
    elif fault == "review-before-collected":
        state["events"] = state["events"][:-2]
    elif fault in {"wrong-collected-id", "wrong-collected-refs"}:
        state["events"][-2] = replace(
            state["events"][-2],
            **(
                {"detail_code": code("COLLECTED", OTHER_CONTRACT)}
                if fault == "wrong-collected-id"
                else {"evidence": (refs["receipt"],)}
            ),
        )
    elif fault.startswith("stage3") or fault == "repeat-stage3":
        state["advance"](
            v2.V2StageState.WAITING_OPERATOR,
            "CAMERA_RECEIPT_REQUESTED_"
            + (OTHER_CONTRACT if fault == "stage3-wrong-id" else CONTRACT)[15:].upper(),
            (refs["review"],) if fault == "stage3-cross-reference" else (),
            stage=STAGE_ORDER[2],
        )
        if fault == "repeat-stage3":
            state["advance"](
                v2.V2StageState.WAITING_OPERATOR,
                "CAMERA_RECEIPT_REQUESTED_" + CONTRACT[15:].upper(),
                stage=STAGE_ORDER[2],
            )
    elif fault == "later-stage":
        state["add"](b"{}", label="not-implemented", stage=STAGE_ORDER[3])
    elif fault == "uncommitted":
        state["uncommitted"] = (state["events"][-1],)
    else:
        index = 1 if fault == "prefix-source-code" else -3
        state["events"][index] = replace(
            state["events"][index], detail_code="WRONG_ORIGINAL_PREFIX"
        )
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(static_ready)


@pytest.mark.parametrize(
    "key",
    [
        "source_sha256",
        "cell_id",
        "session_id",
        "header_sha256",
        "origin_launch_id",
        "prerequisites_sha256",
        "source_qualification",
        "static_request_event_sha256",
        "store_directory",
    ],
)
def test_rehashed_static_receipt_cannot_change_original_binding(
    static_ready, monkeypatch, key
):
    _, _, state = static_ready
    subjects = actual_static_subjects(static_ready, monkeypatch)
    refs = retain_static(static_ready, subjects, phase="receipt-only")
    document = subjects["receipt"].to_dict()
    old = document["binding"][key]
    if type(old) is dict:
        document["binding"][key] = {name: "f" * 64 for name in old}
    elif key.endswith("sha256"):
        document["binding"][key] = "f" * 64
    else:
        document["binding"][key] = old + "-different"
    raw = canonical(document)
    original = refs["receipt"]
    state["references"][state["references"].index(original)] = replace(
        original, payload_sha256=digest(raw), payload_bytes=len(raw)
    )
    state["payloads"][original.evidence_id] = raw
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(static_ready)


@pytest.mark.parametrize(
    "fault", ["lease-exit", "coherence", "late-stop", "late-source", "late-deadline"]
)
def test_late_static_failure_preserves_exact_historical_subjects(
    static_ready, monkeypatch, fault
):
    owner, _, state = static_ready
    subjects = actual_static_subjects(static_ready, monkeypatch)
    retain_static(static_ready, subjects)
    cancellation = Event()
    state["exit_failure"] = fault == "lease-exit"
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
        refresh_read(static_ready, cancellation=cancellation, progress=progress)
    retained = owner.retained_source_workflow()["static_contract"]
    assert all(
        canonical(retained[role]["document"]) == subjects[role].payload
        for role in subjects
    )
    assert owner.view()["status"] == "HELD" and owner._store is None


def test_stage_owned_budgets_allow_32_source_plus_3_static_without_expanding_source(
    source_model, monkeypatch
):
    _, _, state = source_model
    enter_static(source_model, cycles=7, intake=True, early_originals=2)
    assert len(state["references"]) == 32
    subjects = actual_static_subjects(source_model, monkeypatch)
    retain_static(source_model, subjects)
    assert len(state["references"]) == 35
    result = refresh_read(source_model)
    wire = canonical(result)
    assert module._decode_cached_source_workflow(wire) == result
    assert len(wire) <= module.MAX_STATIC_WORKFLOW_BYTES
    print(f"V5_MAX_ORIGINAL_CACHE bytes={len(wire)}")
    state["add"](b"{}", label="unexpected-source-role")
    with pytest.raises(module.PhysicalCameraSessionError) as error:
        refresh_read(source_model)
    assert error.value.code == "CAMERA_SESSION_READBACK_LIMIT"


def initial_epoch(source_model):
    """Model the exact original creation point, not a runtime replacement store."""
    from rocell.application.physical_configuration_epochs import (
        build_physical_configuration_epochs,
    )

    _, prerequisites, state = source_model
    header, first = state["header"], state["events"][0]
    source_states = [v2.V2StageState.WAITING_OPERATOR] + [v2.V2StageState.PENDING] * (
        len(STAGE_ORDER) - 1
    )
    creation = v2.V2SessionSnapshot(
        header,
        tuple(
            v2.V2StageSnapshot(
                stage, source_states[index], 0 if index == 0 else None, ()
            )
            for index, stage in enumerate(STAGE_ORDER)
        ),
        (first,),
        (),
        (state["references"][0],),
        v2.V2CommittedHead.build(header, (first,)),
        v2._derive_next_action(source_states),
    )
    artifact = build_physical_configuration_epochs(
        prerequisites, creation, evidence_bindings=()
    )
    state["add"](artifact.payload, label=module.CONFIGURATION_EPOCH_LABEL)
    return artifact


def test_original_epoch_restores_against_real_35_reference_current_snapshot(
    source_model, monkeypatch
):
    from rocell.application import physical_configuration_epochs as epochs

    _, prerequisites, state = source_model
    artifact = initial_epoch(source_model)
    enter_static(source_model, cycles=7, intake=True, early_originals=1)
    assert len(state["references"]) == 32
    subjects = actual_static_subjects(source_model, monkeypatch)
    retain_static(source_model, subjects, camera_entry=True)
    assert len(state["references"]) == 35
    current = state["snapshot"]()
    result = refresh_read(source_model)
    assert canonical(result["configuration_epochs"]["document"]) == artifact.payload
    assert result["session_head_sha256"] == current.head.head_sha256
    assert state["snapshot"]() == current
    assert result["camera_receipt_request"] is not None
    # The public v1 verifier and builder retain their original creation domain.
    with pytest.raises(epochs.PhysicalConfigurationEpochError) as error:
        epochs.verify_physical_configuration_epochs(
            artifact.payload,
            prerequisites=prerequisites,
            snapshot=current,
            expected_sha256=artifact.sha256,
        )
    assert error.value.code == "INVENTORY_LIMIT"
    with pytest.raises(epochs.PhysicalConfigurationEpochError):
        epochs.build_physical_configuration_epochs(prerequisites, current)
    assert (
        epochs._verify_physical_configuration_epochs_after_static(
            artifact.payload,
            prerequisites=prerequisites,
            snapshot=current,
            expected_sha256=artifact.sha256,
        ).payload
        == artifact.payload
    )


@pytest.mark.parametrize("stage", [STAGE_ORDER[2], STAGE_ORDER[-1]])
def test_private_epoch_restore_rejects_arbitrary_later_stage_inventory(
    source_model, monkeypatch, stage
):
    from rocell.application import physical_configuration_epochs as epochs

    _, prerequisites, state = source_model
    artifact = initial_epoch(source_model)
    enter_static(source_model)
    retain_static(source_model, actual_static_subjects(source_model, monkeypatch))
    state["add"](b"{}", label="arbitrary-later-stage", stage=stage)
    current = state["snapshot"]()
    assert len(current.evidence) < 35
    with pytest.raises(epochs.PhysicalConfigurationEpochError) as error:
        epochs._verify_physical_configuration_epochs_after_static(
            artifact.payload,
            prerequisites=prerequisites,
            snapshot=current,
            expected_sha256=artifact.sha256,
        )
    assert error.value.code == "INVENTORY_LIMIT"
    with pytest.raises(module.PhysicalCameraSessionError):
        refresh_read(source_model)


@pytest.mark.skipif(os.name != "nt", reason="actual isolated original NTFS/M1 storage")
def test_actual_ntfs_static_originals_reopen_partial_pass_and_explicit_stage3(
    workspace, monkeypatch
):
    """Real files/store; source isolation and owner coverage are modeled only."""
    from test_physical_source_qualification_readback import (
        qualification_records,
        label as source_label,
        code as source_code,
        RAW,
    )
    from test_physical_camera_source_workflow_readback import collect_chain
    from test_physical_camera_intake_session import SOURCE_CODES, read
    from test_physical_ownership_qualification import modeled_report
    from rocell.application import physical_static_contract as codec

    monkeypatch.setattr(module, "source_fingerprint", lambda _: SOURCE)
    prerequisites = generate(workspace)
    owner = session_fixture(workspace)
    initial = perform(owner)
    header = initial["verification"]["session"]["header_sha256"]
    source_subjects = collect_chain(prerequisites, header, monkeypatch)
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

    def retain(tx, stage, payload, name, media="application/json"):
        ref = tx.store_evidence(
            stage,
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
        stage = STAGE_ORDER[0]
        commit(tx, stage, v2.V2StageState.WAITING_OPERATOR, SOURCE_CODES[0])
        retain(tx, stage, prerequisites.payload, module.PREREQUISITE_LABEL)
        source_refs = {
            role: retain(
                tx, stage, source_subjects[role].payload, f"workspace-source-{role}-v1"
            )
            for role in ("receipt", "assessment")
        }
        commit(
            tx,
            stage,
            v2.V2StageState.REVIEW_PENDING,
            SOURCE_CODES[1],
            source_refs.values(),
        )
        source_refs["review"] = retain(
            tx, stage, source_subjects["review"].payload, "workspace-source-review-v1"
        )
        commit(
            tx, stage, v2.V2StageState.BLOCKED, SOURCE_CODES[2], source_refs.values()
        )
        commit(
            tx,
            stage,
            v2.V2StageState.WAITING_OPERATOR,
            source_code("STARTED"),
            source_refs.values(),
        )
        original = retain(
            tx, stage, RAW, source_label("isolation_original"), "text/plain"
        )
        qualified = qualification_records(
            prerequisites,
            descriptor,
            header,
            source_subjects,
            original_ref=original,
            ownership=ownership,
            observed=True,
        )
        refs = {
            role: retain(tx, stage, qualified[role].payload, source_label(role))
            for role in ("receipt", "assessment")
        }
        commit(
            tx,
            stage,
            v2.V2StageState.REVIEW_PENDING,
            source_code("ASSESSED"),
            [original, *refs.values()],
        )
        refs["review"] = retain(
            tx, stage, qualified["review"].payload, source_label("review")
        )
        commit(
            tx,
            stage,
            v2.V2StageState.PASS,
            source_code("REVIEWED_PASS"),
            [original, *refs.values()],
        )
        commit(
            tx,
            STAGE_ORDER[1],
            v2.V2StageState.WAITING_OPERATOR,
            "STATIC_CAMERA_CONTRACT_REQUESTED_" + QUALIFICATION[11:].upper(),
        )
        original_snapshot = tx.snapshot()

    # The actual collector reads controlled design files, not modeled PASS data.
    subjects = actual_static_subjects(
        (
            owner,
            prerequisites,
            {
                "qualified_sources": qualified,
                "header": original_snapshot.header,
                "events": original_snapshot.committed_events,
            },
        ),
        monkeypatch,
    )
    assert subjects["assessment"].to_dict()["verdict"] == "PASS"
    monkeypatch.setattr(
        codec,
        "collect_static_camera_contract",
        lambda *a, **kw: pytest.fail("restart recollected design"),
    )

    def reopened(expected_state, *, stage3=False):
        fresh = session_fixture(workspace)
        before = perform(fresh, "refresh")
        result = read(fresh, header)
        assert result["static_contract"]["state"] == expected_state
        assert result["session_head_sha256"] == expected_head.head_sha256
        assert (result["camera_receipt_request"] is not None) is stage3
        assert before["stages"] == fresh.view()["stages"]
        assert before["stages"][2]["state"] == (
            "WAITING_OPERATOR" if stage3 else "PENDING"
        )
        for role in static_refs:
            assert (
                canonical(result["static_contract"][role]["document"])
                == subjects[role].payload
            )
        assert result["assessment"]["document"]["verdict"] == "BLOCKED"
        assert result["qualification_cycles"][-1]["state"] == "REVIEWED_PASS"
        assert all(row["state"] == "PENDING" for row in before["stages"][3:])
        return fresh

    perform(owner, "refresh")
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        static_refs = {
            role: retain(tx, STAGE_ORDER[1], subjects[role].payload, label(role))
            for role in ("receipt", "assessment")
        }
        expected_head = tx.snapshot().head
    owner = reopened("ASSESSMENT_RETAINED_NOT_COMMITTED")
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        commit(
            tx,
            STAGE_ORDER[1],
            v2.V2StageState.REVIEW_PENDING,
            code("COLLECTED"),
            static_refs.values(),
        )
        static_refs["review"] = retain(
            tx, STAGE_ORDER[1], subjects["review"].payload, label("review")
        )
        expected_head = tx.snapshot().head
    owner = reopened("REVIEW_RETAINED_NOT_COMMITTED")
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        commit(
            tx,
            STAGE_ORDER[1],
            v2.V2StageState.PASS,
            code("REVIEWED_PASS"),
            static_refs.values(),
        )
        expected_head = tx.snapshot().head
    owner = reopened("REVIEWED_PASS")
    with owner.stage_transaction(
        expected_challenge_sha256=owner.view()["verification"]["challenge_sha256"]
    ) as tx:
        commit(
            tx,
            STAGE_ORDER[2],
            v2.V2StageState.WAITING_OPERATOR,
            "CAMERA_RECEIPT_REQUESTED_" + CONTRACT[15:].upper(),
        )
        expected_head = tx.snapshot().head
    reopened("REVIEWED_PASS", stage3=True)
