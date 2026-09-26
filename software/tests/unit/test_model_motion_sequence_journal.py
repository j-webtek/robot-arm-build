from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocell.application.model_motion_sequence_coordinator import (
    ModelMotionSequenceCoordinator,
)
from rocell.application.model_motion_sequence_journal import (
    DurableModelMotionSequenceJournal,
    ModelMotionSequenceJournalError,
    SequenceJournalPhase,
    SequenceRecoveryDisposition,
    load_model_motion_sequence_journal,
)

from test_model_motion_sequence_coordinator import (
    _observed,
    _ready_gate,
    _result,
    _setup,
)


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "sequence-journals"
    root.mkdir()
    return root


def _ready_coordinator():
    context, batch, ingress = _setup()
    gate, _ = _ready_gate(ingress)
    coordinator = ModelMotionSequenceCoordinator(
        batch, ingress, context, planner_gate=gate
    )
    coordinator.evaluate_next(_observed("a"), evaluation_monotonic_ns=110)
    return batch, ingress, coordinator


def test_journal_create_and_reopen_bind_exact_batch(tmp_path: Path) -> None:
    _, batch, ingress = _setup()
    journal = DurableModelMotionSequenceJournal.create(
        _root(tmp_path), batch, ingress, created_at_ns=10
    )
    snapshot = DurableModelMotionSequenceJournal.open(journal.directory).snapshot()
    document = snapshot.to_dict()

    assert snapshot.phase is SequenceJournalPhase.SEQUENCE_CREATED
    assert snapshot.batch_sha256 == batch.batch_sha256
    assert snapshot.ingress_sha256 == ingress["ingress_sha256"]
    assert snapshot.recovery_disposition is (
        SequenceRecoveryDisposition.RESUME_WITH_FRESH_STATE
    )
    assert document["automatic_retry_allowed"] is False
    assert document["hardware_access"] is False
    assert document["hardware_commands_generated"] == 0


def test_dispatch_boundary_is_durable_before_coordinator_advances(
    tmp_path: Path,
) -> None:
    batch, ingress, coordinator = _ready_coordinator()
    journal = DurableModelMotionSequenceJournal.create(
        _root(tmp_path), batch, ingress, created_at_ns=10
    )
    ready = coordinator.snapshot()
    journal.commit_action_ready(
        action_index=0,
        event_time_ns=20,
        planner_gate_sha256=ready["planner_gate_sha256"][-1],
        coordinator_snapshot_sha256=ready["sequence_snapshot_sha256"],
    )

    execution_request = "6" * 64
    committed = journal.commit_dispatch_boundary(
        action_index=0,
        event_time_ns=30,
        execution_request_sha256=execution_request,
    )
    assert committed.recovery_disposition is (
        SequenceRecoveryDisposition.RETRY_FORBIDDEN_OUTCOME_UNCERTAIN
    )
    coordinator.commit_dispatch_boundary(execution_request)
    result = _result(batch, coordinator)
    journal.record_verified_result(result, event_time_ns=40)
    coordinator.record_result(result)

    reopened = load_model_motion_sequence_journal(journal.directory)
    assert reopened.phase is SequenceJournalPhase.ACTION_VERIFIED
    assert reopened.recovery_disposition is (
        SequenceRecoveryDisposition.RESUME_WITH_FRESH_STATE
    )
    assert coordinator.action_index == 1


def test_restart_at_dispatch_boundary_forbids_replay(tmp_path: Path) -> None:
    batch, ingress, coordinator = _ready_coordinator()
    journal = DurableModelMotionSequenceJournal.create(
        _root(tmp_path), batch, ingress, created_at_ns=10
    )
    snapshot = coordinator.snapshot()
    journal.commit_action_ready(
        action_index=0,
        event_time_ns=20,
        planner_gate_sha256=snapshot["planner_gate_sha256"][-1],
        coordinator_snapshot_sha256=snapshot["sequence_snapshot_sha256"],
    )
    journal.commit_dispatch_boundary(
        action_index=0,
        event_time_ns=30,
        execution_request_sha256="6" * 64,
    )

    restarted = DurableModelMotionSequenceJournal.open(journal.directory).snapshot()
    assert restarted.phase is SequenceJournalPhase.DISPATCH_BOUNDARY_COMMITTED
    assert restarted.recovery_disposition is (
        SequenceRecoveryDisposition.RETRY_FORBIDDEN_OUTCOME_UNCERTAIN
    )
    with pytest.raises(ModelMotionSequenceJournalError, match="transition"):
        journal.commit_dispatch_boundary(
            action_index=0,
            event_time_ns=40,
            execution_request_sha256="7" * 64,
        )


def test_journal_rejects_tamper_and_tail_truncation(tmp_path: Path) -> None:
    batch, ingress, coordinator = _ready_coordinator()
    first_root = _root(tmp_path)
    journal = DurableModelMotionSequenceJournal.create(
        first_root, batch, ingress, created_at_ns=10
    )
    snapshot = coordinator.snapshot()
    journal.commit_action_ready(
        action_index=0,
        event_time_ns=20,
        planner_gate_sha256=snapshot["planner_gate_sha256"][-1],
        coordinator_snapshot_sha256=snapshot["sequence_snapshot_sha256"],
    )
    event_path = journal.directory / "event-000001.json"
    document = json.loads(event_path.read_text(encoding="utf-8"))
    document["action_index"] = 1
    event_path.write_text(
        json.dumps(document, indent=2, sort_keys=True) + "\n", encoding="utf-8"
    )
    with pytest.raises(
        ModelMotionSequenceJournalError, match="noncanonical|content hash"
    ):
        journal.snapshot()

    second_root = tmp_path / "second"
    second_root.mkdir()
    clean = DurableModelMotionSequenceJournal.create(
        second_root, batch, ingress, created_at_ns=10
    )
    clean.commit_action_ready(
        action_index=0,
        event_time_ns=20,
        planner_gate_sha256=snapshot["planner_gate_sha256"][-1],
        coordinator_snapshot_sha256=snapshot["sequence_snapshot_sha256"],
    )
    (clean.directory / "event-000001.json").unlink()
    with pytest.raises(ModelMotionSequenceJournalError, match="head differs"):
        clean.snapshot()


def test_invalid_action_order_and_duplicate_journal_are_rejected(
    tmp_path: Path,
) -> None:
    _, batch, ingress = _setup()
    root = _root(tmp_path)
    journal = DurableModelMotionSequenceJournal.create(
        root, batch, ingress, created_at_ns=10
    )
    with pytest.raises(ModelMotionSequenceJournalError, match="transition"):
        journal.commit_dispatch_boundary(
            action_index=0,
            event_time_ns=20,
            execution_request_sha256="6" * 64,
        )
    with pytest.raises(ModelMotionSequenceJournalError, match="already exists"):
        DurableModelMotionSequenceJournal.create(
            root, batch, ingress, created_at_ns=11
        )


def test_two_action_history_can_complete_only_in_order(tmp_path: Path) -> None:
    batch, ingress, coordinator = _ready_coordinator()
    journal = DurableModelMotionSequenceJournal.create(
        _root(tmp_path), batch, ingress, created_at_ns=10
    )
    now = 20
    for index in range(2):
        snapshot = coordinator.snapshot()
        journal.commit_action_ready(
            action_index=index,
            event_time_ns=now,
            planner_gate_sha256=snapshot["planner_gate_sha256"][-1],
            coordinator_snapshot_sha256=snapshot["sequence_snapshot_sha256"],
        )
        journal.commit_dispatch_boundary(
            action_index=index,
            event_time_ns=now + 10,
            execution_request_sha256=str(index + 6) * 64,
        )
        coordinator.commit_dispatch_boundary(str(index + 6) * 64)
        result = _result(batch, coordinator)
        journal.record_verified_result(result, event_time_ns=now + 20)
        coordinator.record_result(result)
        now += 30
        if index == 0:
            coordinator.evaluate_next(
                _observed("b", available=300), evaluation_monotonic_ns=310
            )

    completed = journal.complete(
        action_index=1,
        event_time_ns=now,
        completion_evidence_sha256=coordinator.snapshot()[
            "sequence_snapshot_sha256"
        ],
    )
    assert completed.phase is SequenceJournalPhase.COMPLETED
    assert completed.recovery_disposition is (
        SequenceRecoveryDisposition.COMPLETE_NO_ACTION
    )
    assert coordinator.snapshot()["phase"] == "COMPLETED"
