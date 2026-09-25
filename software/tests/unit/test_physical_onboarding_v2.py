from __future__ import annotations

import json
from pathlib import Path
from typing import cast

import pytest

from rocell.application.physical_onboarding import (
    PhysicalOnboardingSession,
    PhysicalOnboardingStage,
    STAGE_ORDER,
)
from rocell.application.physical_onboarding_v2 import (
    LEGACY_V1_READ_ONLY,
    SESSION_EVENT_SCHEMA_V2,
    SESSION_HEADER_SCHEMA_V2,
    SESSION_HEAD_SCHEMA_V2,
    V2_UNCOMMITTED_SUFFIX,
    LegacyV1ReadOnlyError,
    LegacyV1ReadOnlySession,
    PhysicalOnboardingV2Error,
    PhysicalOnboardingV2Session,
    PortableSessionPublication,
    V2SessionSnapshot,
    V2StageState,
    V2UncommittedSuffixError,
    open_onboarding_session,
)


SOURCE_HASH = "a" * 64
START = 1_000_000
FIRST = PhysicalOnboardingStage.WORKSPACE_SOURCES


def _create(
    tmp_path: Path, session_id: str = "arrival-v2-001"
) -> PhysicalOnboardingV2Session:
    return PhysicalOnboardingV2Session.create(
        tmp_path,
        session_id=session_id,
        cell_id="cell-a",
        source_binding_sha256=SOURCE_HASH,
        created_at_ns=START,
    )


def _waiting(
    session: PhysicalOnboardingV2Session, *, when: int = START + 1
) -> V2SessionSnapshot:
    before = session.snapshot()
    return session.commit_stage_state(
        FIRST,
        V2StageState.WAITING_OPERATOR,
        occurred_at_ns=when,
        detail_code="WAITING_FOR_OPERATOR",
        expected_head_sha256=before.head.head_sha256,
    )


def _tree_bytes(root: Path) -> dict[str, bytes]:
    return {
        path.relative_to(root).as_posix(): path.read_bytes()
        for path in sorted(root.rglob("*"))
        if path.is_file()
    }


def test_v2_create_uses_exact_plan_states_schemas_and_zero_authority(
    tmp_path: Path,
) -> None:
    session = _create(tmp_path)
    snapshot = session.snapshot()

    assert snapshot.header.schema == SESSION_HEADER_SCHEMA_V2
    assert snapshot.head.schema == SESSION_HEAD_SCHEMA_V2
    assert snapshot.head.event_count == 0
    assert len(snapshot.stages) == 15
    assert tuple(item.stage for item in snapshot.stages) == STAGE_ORDER
    assert all(item.state is V2StageState.PENDING for item in snapshot.stages)
    assert "ACQUIRING" not in {state.value for state in V2StageState}
    assert snapshot.next_action.stage is FIRST

    header = json.loads((session.directory / "header.json").read_text("utf-8"))
    assert header["schema"] == SESSION_HEADER_SCHEMA_V2
    assert header["ordered_stages"] == [stage.value for stage in STAGE_ORDER]
    assert header["device_io_authorized"] is False
    assert header["robot_power_authorized"] is False
    assert header["motion_authorized"] is False
    assert header["contact_authorized"] is False
    assert header["physical_release_effect"] == "NONE"
    assert isinstance(
        open_onboarding_session(session.directory), PhysicalOnboardingV2Session
    )


def test_v2_reviewed_evidence_flow_is_hash_chained_and_head_committed(
    tmp_path: Path,
) -> None:
    session = _create(tmp_path)
    waiting = _waiting(session)
    retained = session.store_evidence(
        FIRST,
        b"operator-reviewed-receipt",
        label="workspace receipt",
        media_type="application/octet-stream",
        captured_at_ns=START + 2,
        expected_head_sha256=waiting.head.head_sha256,
    )
    review = session.commit_stage_state(
        FIRST,
        V2StageState.REVIEW_PENDING,
        occurred_at_ns=START + 3,
        detail_code="EVIDENCE_READY_FOR_REVIEW",
        evidence=(retained,),
        expected_head_sha256=waiting.head.head_sha256,
    )
    passed = session.commit_stage_state(
        FIRST,
        V2StageState.PASS,
        occurred_at_ns=START + 4,
        detail_code="OPERATOR_REVIEW_PASSED",
        evidence=(retained,),
        expected_head_sha256=review.head.head_sha256,
    )

    assert [event.schema for event in passed.committed_events] == [
        SESSION_EVENT_SCHEMA_V2,
        SESSION_EVENT_SCHEMA_V2,
        SESSION_EVENT_SCHEMA_V2,
    ]
    assert passed.committed_events[0].previous_event_sha256 == "0" * 64
    assert (
        passed.committed_events[1].previous_event_sha256
        == passed.committed_events[0].event_sha256
    )
    assert (
        passed.committed_events[2].previous_event_sha256
        == passed.committed_events[1].event_sha256
    )
    assert passed.head.event_count == 3
    assert (
        passed.head.committed_event_sha256 == passed.committed_events[-1].event_sha256
    )
    assert passed.state_for(FIRST) is V2StageState.PASS
    assert passed.next_action.stage is STAGE_ORDER[1]
    assert passed.uncommitted_events == ()


def test_v2_rejects_acquiring_and_unreviewed_or_out_of_order_pass(
    tmp_path: Path,
) -> None:
    session = _create(tmp_path)
    initial = session.snapshot()

    with pytest.raises(PhysicalOnboardingV2Error, match="ACQUIRING"):
        session.commit_stage_state(
            FIRST,
            cast(V2StageState, "ACQUIRING"),
            occurred_at_ns=START + 1,
            detail_code="FORBIDDEN_STATE",
            expected_head_sha256=initial.head.head_sha256,
        )
    with pytest.raises(PhysicalOnboardingV2Error, match="cannot run before"):
        session.commit_stage_state(
            STAGE_ORDER[1],
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=START + 1,
            detail_code="OUT_OF_ORDER",
            expected_head_sha256=initial.head.head_sha256,
        )

    waiting = _waiting(session)
    with pytest.raises(
        PhysicalOnboardingV2Error, match="invalid V2 onboarding transition"
    ):
        session.commit_stage_state(
            FIRST,
            V2StageState.PASS,
            occurred_at_ns=START + 2,
            detail_code="UNREVIEWED_PASS",
            expected_head_sha256=waiting.head.head_sha256,
        )
    with pytest.raises(PhysicalOnboardingV2Error, match="requires retained evidence"):
        session.commit_stage_state(
            FIRST,
            V2StageState.REVIEW_PENDING,
            occurred_at_ns=START + 2,
            detail_code="MISSING_EVIDENCE",
            expected_head_sha256=waiting.head.head_sha256,
        )


class _FailHeadPublication:
    effectful_durability_qualified = False
    durability_qualification_sha256 = "0" * 64

    def __init__(self) -> None:
        self.delegate = PortableSessionPublication()

    def write_new_file(self, path: Path, payload: bytes) -> None:
        self.delegate.write_new_file(path, payload)

    def replace_file(self, path: Path, payload: bytes) -> None:
        del path, payload
        raise RuntimeError("injected head publication failure")

    def publish_new_directory(self, source: Path, destination: Path) -> None:
        self.delegate.publish_new_directory(source, destination)

    def sync_directory(self, path: Path) -> None:
        self.delegate.sync_directory(path)


class _QualifiedTestPublication:
    effectful_durability_qualified = True
    durability_qualification_sha256 = "b" * 64

    def __init__(self) -> None:
        self.delegate = PortableSessionPublication()

    def write_new_file(self, path: Path, payload: bytes) -> None:
        self.delegate.write_new_file(path, payload)

    def replace_file(self, path: Path, payload: bytes) -> None:
        self.delegate.replace_file(path, payload)

    def publish_new_directory(self, source: Path, destination: Path) -> None:
        self.delegate.publish_new_directory(source, destination)

    def sync_directory(self, path: Path) -> None:
        self.delegate.sync_directory(path)


def test_v2_publication_provenance_cannot_be_silently_upgraded_or_downgraded(
    tmp_path: Path,
) -> None:
    portable = _create(tmp_path, "portable-provenance")
    portable_header = portable.snapshot().header
    assert portable_header.publication_durability == "PORTABLE_UNQUALIFIED"
    assert portable_header.durability_qualification_sha256 == "0" * 64

    with pytest.raises(PhysicalOnboardingV2Error, match="provenance"):
        PhysicalOnboardingV2Session.open(
            portable.directory, publication=_QualifiedTestPublication()
        )

    qualified = PhysicalOnboardingV2Session.create(
        tmp_path,
        session_id="qualified-provenance",
        cell_id="cell-a",
        source_binding_sha256=SOURCE_HASH,
        created_at_ns=START,
        publication=_QualifiedTestPublication(),
    )
    qualified_header = qualified.snapshot().header
    assert qualified_header.publication_durability == "WINDOWS_NTFS_QUALIFIED"
    assert qualified_header.durability_qualification_sha256 == "b" * 64
    with pytest.raises(PhysicalOnboardingV2Error, match="provenance"):
        open_onboarding_session(qualified.directory)


def test_restart_detects_event_published_beyond_committed_head(tmp_path: Path) -> None:
    created = _create(tmp_path)
    session = PhysicalOnboardingV2Session.open(
        created.directory, publication=_FailHeadPublication()
    )
    initial = session.snapshot()

    with pytest.raises(RuntimeError, match="injected head publication failure"):
        session.commit_stage_state(
            FIRST,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=START + 1,
            detail_code="WAITING_FOR_OPERATOR",
            expected_head_sha256=initial.head.head_sha256,
        )

    restarted = open_onboarding_session(created.directory)
    snapshot = restarted.snapshot()
    assert snapshot.head.event_count == 0
    assert snapshot.committed_events == ()
    assert len(snapshot.uncommitted_events) == 1
    assert snapshot.state_for(FIRST) is V2StageState.PENDING
    assert snapshot.reconciliation_required is True
    assert snapshot.mutation_allowed is False
    assert snapshot.to_verification_dict()["read_only_reason"] == V2_UNCOMMITTED_SUFFIX
    with pytest.raises(V2UncommittedSuffixError, match=V2_UNCOMMITTED_SUFFIX):
        restarted.commit_stage_state(
            FIRST,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=START + 2,
            detail_code="RETRY_FORBIDDEN",
            expected_head_sha256=snapshot.head.head_sha256,
        )


def test_v2_detects_deleted_committed_tail_and_event_tamper(tmp_path: Path) -> None:
    deleted = _create(tmp_path, "deleted-tail")
    _waiting(deleted)
    (deleted.directory / "journal" / "event-000000.json").unlink()
    with pytest.raises(
        PhysicalOnboardingV2Error, match="committed event suffix was deleted"
    ):
        open_onboarding_session(deleted.directory)

    tampered = _create(tmp_path, "tampered-event")
    _waiting(tampered)
    event_path = tampered.directory / "journal" / "event-000000.json"
    event = json.loads(event_path.read_text("utf-8"))
    event["detail_code"] = "TAMPERED"
    event_path.write_bytes(
        (json.dumps(event, indent=2, sort_keys=True, ensure_ascii=True) + "\n").encode(
            "utf-8"
        )
    )
    with pytest.raises(PhysicalOnboardingV2Error, match="event hash mismatch"):
        open_onboarding_session(tampered.directory)


def test_v1_dispatch_is_verify_export_only_and_every_mutation_is_rejected(
    tmp_path: Path,
) -> None:
    v1 = PhysicalOnboardingSession.create(
        tmp_path,
        session_id="legacy-001",
        cell_id="cell-a",
        source_binding_sha256=SOURCE_HASH,
        created_at_ns=START,
    )
    before = _tree_bytes(v1.directory)
    compatibility = open_onboarding_session(v1.directory)

    assert isinstance(compatibility, LegacyV1ReadOnlySession)
    assert compatibility.read_only is True
    assert compatibility.verify().header.session_id == "legacy-001"
    assert compatibility.export_document()["read_only_reason"] == LEGACY_V1_READ_ONLY
    assert compatibility.export_bytes().endswith(b"\n")
    for name in (
        "store_evidence",
        "commit_stage_state",
        "invalidate_from",
        "reconcile",
    ):
        with pytest.raises(LegacyV1ReadOnlyError, match=LEGACY_V1_READ_ONLY):
            getattr(compatibility, name)()
    assert _tree_bytes(v1.directory) == before


def test_schema_dispatch_rejects_noncanonical_json(tmp_path: Path) -> None:
    session = _create(tmp_path)
    header_path = session.directory / "header.json"
    document = json.loads(header_path.read_text("utf-8"))
    header_path.write_text(json.dumps(document), encoding="utf-8")

    with pytest.raises(PhysicalOnboardingV2Error, match="not canonical JSON"):
        open_onboarding_session(session.directory)
