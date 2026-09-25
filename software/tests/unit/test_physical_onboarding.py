from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocell.application.first_power_on_onboarding import (
    STAGE_ORDER as REHEARSAL_STAGE_ORDER,
)
from rocell.application.physical_onboarding import (
    DIAGNOSTIC_CAPABILITY,
    MAX_EVIDENCE_BYTES,
    STAGE_ORDER,
    EvidenceReference,
    PhysicalOnboardingError,
    PhysicalOnboardingSession,
    PhysicalOnboardingStage,
    StageState,
)


SOURCE_HASH = "a" * 64
START = 1_000_000


def _create(tmp_path: Path, session_id: str = "arrival-001") -> PhysicalOnboardingSession:
    return PhysicalOnboardingSession.create(
        tmp_path,
        session_id=session_id,
        cell_id="cell-a",
        source_binding_sha256=SOURCE_HASH,
        created_at_ns=START,
    )


def _evidence(
    session: PhysicalOnboardingSession,
    stage: PhysicalOnboardingStage,
    sequence: int,
) -> EvidenceReference:
    return session.store_evidence(
        stage,
        f"evidence-{stage.value}-{sequence}".encode("ascii"),
        label=f"receipt-{sequence}",
        media_type="application/octet-stream",
        captured_at_ns=START + sequence,
    )


def _pass_stage(
    session: PhysicalOnboardingSession,
    stage: PhysicalOnboardingStage,
    sequence: int,
) -> None:
    session.commit_stage_state(
        stage,
        StageState.ACQUIRING,
        occurred_at_ns=START + sequence * 10,
        detail_code="DIAGNOSTIC_ACQUISITION_STARTED",
    )
    retained = _evidence(session, stage, sequence)
    terminal = (
        StageState.COMPLETE_DIAGNOSTIC
        if stage is PhysicalOnboardingStage.PHYSICAL_HANDOFF
        else StageState.PASS
    )
    session.commit_stage_state(
        stage,
        terminal,
        occurred_at_ns=START + sequence * 10 + 1,
        detail_code=(
            "DIAGNOSTIC_HANDOFF_COMPLETE"
            if terminal is StageState.COMPLETE_DIAGNOSTIC
            else "DIAGNOSTIC_GATE_PASSED"
        ),
        evidence=(retained,),
    )


def test_stage_order_exactly_matches_canonical_fifteen_stage_plan() -> None:
    assert len(STAGE_ORDER) == 15
    assert tuple(stage.value for stage in STAGE_ORDER) == tuple(
        stage.value for stage in REHEARSAL_STAGE_ORDER
    )


def test_new_session_is_immutable_zero_authority_and_has_one_next_action(
    tmp_path: Path,
) -> None:
    session = _create(tmp_path)
    snapshot = session.snapshot()

    assert snapshot.header.source_binding_sha256 == SOURCE_HASH
    assert snapshot.next_action.stage is PhysicalOnboardingStage.WORKSPACE_SOURCES
    assert snapshot.next_action.code == "START_VERIFY_CONTROLLED_WORKSPACE"
    assert all(item.state is StageState.PENDING for item in snapshot.stages)
    assert snapshot.capability == DIAGNOSTIC_CAPABILITY
    assert snapshot.capability.motion_authorized is False
    assert snapshot.capability.contact_authorized is False
    assert snapshot.capability.automatic_effect_replay_allowed is False

    with pytest.raises(PhysicalOnboardingError, match="already exists"):
        _create(tmp_path)


def test_prerequisites_reject_out_of_order_stage_and_pass_requires_evidence(
    tmp_path: Path,
) -> None:
    session = _create(tmp_path)

    with pytest.raises(PhysicalOnboardingError, match="cannot run before"):
        session.commit_stage_state(
            PhysicalOnboardingStage.CAMERA_RECEIPT,
            StageState.ACQUIRING,
            occurred_at_ns=START + 10,
            detail_code="OUT_OF_ORDER_ATTEMPT",
        )

    session.commit_stage_state(
        PhysicalOnboardingStage.WORKSPACE_SOURCES,
        StageState.ACQUIRING,
        occurred_at_ns=START + 11,
        detail_code="DIAGNOSTIC_ACQUISITION_STARTED",
    )
    with pytest.raises(PhysicalOnboardingError, match="requires retained evidence"):
        session.commit_stage_state(
            PhysicalOnboardingStage.WORKSPACE_SOURCES,
            StageState.PASS,
            occurred_at_ns=START + 12,
            detail_code="DIAGNOSTIC_GATE_PASSED",
        )


def test_resume_verifies_chain_and_never_replays_acquiring_effect(
    tmp_path: Path,
) -> None:
    session = _create(tmp_path)
    session.commit_stage_state(
        PhysicalOnboardingStage.WORKSPACE_SOURCES,
        StageState.ACQUIRING,
        occurred_at_ns=START + 10,
        detail_code="DIAGNOSTIC_ACQUISITION_STARTED",
    )

    resumed = PhysicalOnboardingSession.open(session.directory).snapshot()

    assert len(resumed.events) == 1
    assert resumed.next_action.stage is PhysicalOnboardingStage.WORKSPACE_SOURCES
    assert resumed.next_action.stage_state is StageState.ACQUIRING
    assert resumed.next_action.code.startswith("RECONCILE_IN_FLIGHT_")
    assert resumed.next_action.automatic_effect_replay_allowed is False


def test_tail_deletion_is_detected_and_cannot_restore_a_replayable_state(
    tmp_path: Path,
) -> None:
    session = _create(tmp_path)
    session.commit_stage_state(
        PhysicalOnboardingStage.WORKSPACE_SOURCES,
        StageState.ACQUIRING,
        occurred_at_ns=START + 10,
        detail_code="DIAGNOSTIC_ACQUISITION_STARTED",
    )
    (session.directory / "journal" / "event-000000.json").unlink()

    with pytest.raises(PhysicalOnboardingError, match="high-water"):
        PhysicalOnboardingSession.open(session.directory)


def test_event_tamper_is_detected_before_resume(tmp_path: Path) -> None:
    session = _create(tmp_path)
    session.commit_stage_state(
        PhysicalOnboardingStage.WORKSPACE_SOURCES,
        StageState.ACQUIRING,
        occurred_at_ns=START + 10,
        detail_code="DIAGNOSTIC_ACQUISITION_STARTED",
    )
    event_path = session.directory / "journal" / "event-000000.json"
    document = json.loads(event_path.read_text(encoding="utf-8"))
    document["detail_code"] = "TAMPERED"
    event_path.write_bytes(
        (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )

    with pytest.raises(PhysicalOnboardingError, match="event hash mismatch"):
        PhysicalOnboardingSession.open(session.directory)


def test_evidence_is_content_addressed_manifest_last_and_cannot_be_overwritten(
    tmp_path: Path,
) -> None:
    session = _create(tmp_path)
    stage = PhysicalOnboardingStage.WORKSPACE_SOURCES
    reference = session.store_evidence(
        stage,
        b"controlled-workspace-receipt",
        label="workspace-receipt",
        media_type="application/octet-stream",
        captured_at_ns=START + 1,
    )
    package = session.directory / "evidence" / reference.evidence_id
    manifest = json.loads((package / "manifest.json").read_text(encoding="utf-8"))

    assert package.name == f"evidence-{reference.package_sha256}"
    assert manifest["manifest_written_last"] is True
    assert manifest["motion_authorized"] is False
    assert manifest["contact_authorized"] is False

    with pytest.raises(PhysicalOnboardingError, match="already exists"):
        session.store_evidence(
            stage,
            b"controlled-workspace-receipt",
            label="workspace-receipt",
            media_type="application/octet-stream",
            captured_at_ns=START + 1,
        )

    (package / "payload.bin").write_bytes(b"tampered-workspace-receipt")
    with pytest.raises(PhysicalOnboardingError, match="hash or size mismatch"):
        session.snapshot()


def test_invalidation_cascades_and_restarts_at_first_invalidated_stage(
    tmp_path: Path,
) -> None:
    session = _create(tmp_path)
    for sequence, stage in enumerate(STAGE_ORDER[:3], start=1):
        _pass_stage(session, stage, sequence)

    snapshot = session.invalidate_from(
        PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT,
        occurred_at_ns=START + 100,
        detail_code="CAMERA_CONTRACT_CHANGED",
    )

    assert snapshot.state_for(PhysicalOnboardingStage.WORKSPACE_SOURCES) is StageState.PASS
    assert snapshot.state_for(PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT) is StageState.INVALIDATED
    assert snapshot.state_for(PhysicalOnboardingStage.CAMERA_RECEIPT) is StageState.INVALIDATED
    assert snapshot.next_action.stage is PhysicalOnboardingStage.STATIC_CAMERA_CONTRACT
    assert snapshot.next_action.code.startswith("REACQUIRE_INVALIDATED_")

    with pytest.raises(PhysicalOnboardingError, match="cannot run before"):
        session.commit_stage_state(
            PhysicalOnboardingStage.CAMERA_RECEIPT,
            StageState.ACQUIRING,
            occurred_at_ns=START + 101,
            detail_code="INVALID_SKIP_ATTEMPT",
        )


def test_uncertain_side_effect_is_terminal_and_forbids_reacquisition(
    tmp_path: Path,
) -> None:
    session = _create(tmp_path)
    stage = PhysicalOnboardingStage.WORKSPACE_SOURCES
    session.commit_stage_state(
        stage,
        StageState.ACQUIRING,
        occurred_at_ns=START + 10,
        detail_code="DIAGNOSTIC_ACQUISITION_STARTED",
    )
    snapshot = session.commit_stage_state(
        stage,
        StageState.SIDE_EFFECT_UNCERTAIN,
        occurred_at_ns=START + 11,
        detail_code="DIAGNOSTIC_EFFECT_UNCERTAIN",
    )

    assert snapshot.next_action.code == "MANUAL_REVIEW_SIDE_EFFECT_UNCERTAIN"
    assert snapshot.next_action.operator_required is True
    assert snapshot.next_action.automatic_effect_replay_allowed is False

    with pytest.raises(PhysicalOnboardingError, match="invalid onboarding transition"):
        session.commit_stage_state(
            stage,
            StageState.ACQUIRING,
            occurred_at_ns=START + 12,
            detail_code="AUTOMATIC_RETRY_ATTEMPTED",
        )
    with pytest.raises(PhysicalOnboardingError, match="forbid"):
        _evidence(session, stage, 20)


def test_upstream_invalidation_cannot_erase_downstream_uncertainty(
    tmp_path: Path,
) -> None:
    session = _create(tmp_path)
    first, second = STAGE_ORDER[:2]
    _pass_stage(session, first, 1)
    session.commit_stage_state(
        second,
        StageState.ACQUIRING,
        occurred_at_ns=START + 20,
        detail_code="DIAGNOSTIC_ACQUISITION_STARTED",
    )
    session.commit_stage_state(
        second,
        StageState.SIDE_EFFECT_UNCERTAIN,
        occurred_at_ns=START + 21,
        detail_code="DIAGNOSTIC_EFFECT_UNCERTAIN",
    )

    snapshot = session.invalidate_from(
        first,
        occurred_at_ns=START + 22,
        detail_code="UPSTREAM_SOURCE_CHANGED",
    )

    assert snapshot.state_for(first) is StageState.INVALIDATED
    assert snapshot.state_for(second) is StageState.SIDE_EFFECT_UNCERTAIN


def test_strict_header_fields_and_evidence_resource_bound(tmp_path: Path) -> None:
    session = _create(tmp_path)
    header_path = session.directory / "header.json"
    document = json.loads(header_path.read_text(encoding="utf-8"))
    document["unexpected"] = True
    header_path.write_bytes(
        (json.dumps(document, indent=2, sort_keys=True) + "\n").encode("utf-8")
    )
    with pytest.raises(PhysicalOnboardingError, match="fields differ"):
        session.snapshot()

    bounded = _create(tmp_path, session_id="arrival-002")
    with pytest.raises(PhysicalOnboardingError, match="resource limit"):
        bounded.store_evidence(
            PhysicalOnboardingStage.WORKSPACE_SOURCES,
            b"x" * (MAX_EVIDENCE_BYTES + 1),
            label="oversized",
            media_type="application/octet-stream",
            captured_at_ns=START + 1,
        )


def test_complete_all_stages_is_still_diagnostic_only(tmp_path: Path) -> None:
    session = _create(tmp_path)
    for sequence, stage in enumerate(STAGE_ORDER, start=1):
        _pass_stage(session, stage, sequence)

    snapshot = PhysicalOnboardingSession.open(session.directory).snapshot()
    assert snapshot.diagnostic_complete is True
    assert snapshot.next_action.code == "NO_ACTION_DIAGNOSTIC_COMPLETE"
    assert snapshot.next_action.stage is None
    assert snapshot.capability.scope == "DIAGNOSTIC_ONLY"
    assert snapshot.capability.motion_authorized is False
    assert snapshot.capability.contact_authorized is False
