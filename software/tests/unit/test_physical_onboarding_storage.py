from __future__ import annotations

import json
import multiprocessing
import os
from pathlib import Path
from typing import Callable

import pytest

from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import (
    AttemptBinding,
    AttemptLedgerSuffixError,
    AttemptState,
    DurableLedgerPublisher,
    PhysicalOnboardingAttemptLedger,
)
from rocell.application.physical_onboarding_durability import (
    DurabilityCheckpoint,
    run_on_volume_startup_self_test,
)
from rocell.application.physical_onboarding_leases import windows_lockfileex_self_test
from rocell.application.physical_onboarding_quarantine import (
    PhysicalOnboardingQuarantineLedger,
)
from rocell.application.physical_onboarding_storage import (
    PhysicalOnboardingStorageError,
    QualifiedWindowsOnboardingPublication,
)
from rocell.application.physical_onboarding_v2 import (
    SessionPublicationProtocol,
    PhysicalOnboardingV2Session,
    V2StageState,
)
from rocell.safety.effects import EffectClass


SOURCE = "a" * 64


def _sha(label: str) -> str:
    import hashlib

    return hashlib.sha256(label.encode("ascii")).hexdigest()


def _adapter(
    tmp_path: Path,
    *,
    mutation_guard: Callable[[], None] | None = None,
    fault_injector: Callable[[str], None] | None = None,
) -> tuple[Path, QualifiedWindowsOnboardingPublication]:
    root = tmp_path / "physical-onboarding"
    root.mkdir()
    anchor = run_on_volume_startup_self_test(
        root,
        source_binding_sha256=SOURCE,
        lease_probe=windows_lockfileex_self_test,
        checked_at_ns=1_000,
    )
    startup = run_on_volume_startup_self_test(
        root,
        source_binding_sha256=SOURCE,
        lease_probe=windows_lockfileex_self_test,
        checked_at_ns=2_000,
    )
    assert anchor.qualified_for_effects
    assert startup.qualified_for_effects
    adapter = QualifiedWindowsOnboardingPublication(
        deployment_root=root.resolve(),
        source_binding_sha256=SOURCE,
        qualification_anchor=anchor,
        startup_report=startup,
        mutation_guard=mutation_guard or (lambda: None),
        fault_injector=fault_injector,
    )
    return root.resolve(), adapter


def _binding(attempt_id: str = "attempt-1") -> AttemptBinding:
    return AttemptBinding(
        attempt_id=attempt_id,
        session_id="session-1",
        stage="camera_frame_freshness",
        effect_class=EffectClass.NO_DEVICE_IO,
        operation_id="storage.zero-io-proof",
        operation_binding_sha256=_sha("operation"),
        source_binding_sha256=SOURCE,
        stage_plan_sha256=_sha("stage-plan"),
        session_journal_head_sha256=_sha("session-head"),
        evidence_inventory_sha256=_sha("evidence"),
        intent_at_ns=100,
    )


def _concurrent_attempt_writer(
    root_text: str,
    anchor: object,
    startup: object,
    attempt_id: str,
    ready: object,
    start: object,
    result: object,
) -> None:
    """Spawn-safe contender used to exercise the immutable event CAS token."""

    from rocell.application.physical_onboarding_durability import (
        DurabilityQualificationReport,
    )

    try:
        if not isinstance(anchor, DurabilityQualificationReport) or not isinstance(
            startup, DurabilityQualificationReport
        ):
            raise TypeError("qualification reports did not survive process transfer")
        root = Path(root_text)
        adapter = QualifiedWindowsOnboardingPublication(
            deployment_root=root,
            source_binding_sha256=SOURCE,
            qualification_anchor=anchor,
            startup_report=startup,
            mutation_guard=lambda: None,
        )
        attempts = PhysicalOnboardingAttemptLedger.open(
            root / "attempts", adapter, expected_cell_id="cell-1"
        )
        quarantine = PhysicalOnboardingQuarantineLedger.open(
            root / "quarantine", adapter, expected_cell_id="cell-1"
        )
        ready.set()
        if not start.wait(15):
            raise RuntimeError("concurrent writer start timed out")
        attempts.begin_attempt(_binding(attempt_id), quarantine)
        result.put(f"SUCCESS:{attempt_id}")
    except BaseException as exc:
        result.put(f"ERROR:{attempt_id}:{type(exc).__name__}:{exc}")
        try:
            ready.set()
        except BaseException:
            pass


pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="qualified physical-onboarding storage is Windows NTFS only"
)


def test_adapter_conforms_to_both_protocols_and_uses_stable_anchor(
    tmp_path: Path,
) -> None:
    calls: list[str] = []
    root, adapter = _adapter(tmp_path, mutation_guard=lambda: calls.append("guard"))

    assert isinstance(adapter, SessionPublicationProtocol)
    assert isinstance(adapter, DurableLedgerPublisher)
    assert adapter.effectful_durability_qualified is True
    assert adapter.startup_report.report_sha256 != (
        adapter.qualification_anchor.report_sha256
    )
    assert adapter.qualification_sha256(root / "not-created-yet") == (
        adapter.qualification_anchor.report_sha256
    )
    assert adapter.durability_qualification_sha256 == (
        adapter.qualification_anchor.report_sha256
    )
    assert calls == []


def test_attempt_and_quarantine_round_trip_through_production_adapter(
    tmp_path: Path,
) -> None:
    guard_calls: list[int] = []
    root, adapter = _adapter(
        tmp_path, mutation_guard=lambda: guard_calls.append(len(guard_calls))
    )
    attempts = PhysicalOnboardingAttemptLedger.create(
        root / "attempts",
        adapter,
        ledger_id="attempt-ledger-1",
        cell_id="cell-1",
        created_at_ns=10,
    )
    quarantine = PhysicalOnboardingQuarantineLedger.create(
        root / "quarantine",
        adapter,
        ledger_id="quarantine-ledger-1",
        cell_id="cell-1",
        created_at_ns=11,
    )

    intent = attempts.begin_attempt(_binding(), quarantine)
    aborted = attempts.transition(
        intent.attempt_id,
        AttemptState.ABORTED_PRE_EFFECT,
        quarantine,
        occurred_at_ns=101,
    )

    assert aborted.state is AttemptState.ABORTED_PRE_EFFECT
    assert attempts.snapshot().head_sha256 != intent.attempt_head_before_sha256
    assert quarantine.snapshot().latched is False
    assert set(adapter.list_relative_files(root / "attempts", maximum_entries=20)) == {
        "header.json",
        "head.json",
        "events/event-00000000.json",
        "events/event-00000001.json",
    }
    assert len(guard_calls) > 0


def test_stale_expected_head_is_rejected_before_another_event_is_published(
    tmp_path: Path,
) -> None:
    root, adapter = _adapter(tmp_path)
    attempts = PhysicalOnboardingAttemptLedger.create(
        root / "attempts",
        adapter,
        ledger_id="attempt-ledger-1",
        cell_id="cell-1",
        created_at_ns=10,
    )
    quarantine = PhysicalOnboardingQuarantineLedger.create(
        root / "quarantine",
        adapter,
        ledger_id="quarantine-ledger-1",
        cell_id="cell-1",
        created_at_ns=11,
    )
    old_head = json.loads((root / "attempts" / "head.json").read_text("ascii"))[
        "head_sha256"
    ]
    attempts.begin_attempt(_binding(), quarantine)
    event_payload = (root / "attempts" / "events" / "event-00000000.json").read_bytes()
    head_payload = (root / "attempts" / "head.json").read_bytes()

    with pytest.raises(PhysicalOnboardingStorageError, match="stale"):
        adapter.commit_append(
            root / "attempts",
            event_relative_path="events/event-00000001.json",
            event_payload=event_payload,
            head_payload=head_payload,
            expected_head_sha256=old_head,
        )

    assert not (root / "attempts" / "events" / "event-00000001.json").exists()


def test_two_process_cas_race_commits_at_most_one_intent(tmp_path: Path) -> None:
    root, adapter = _adapter(tmp_path)
    attempts = PhysicalOnboardingAttemptLedger.create(
        root / "attempts",
        adapter,
        ledger_id="attempt-ledger-1",
        cell_id="cell-1",
        created_at_ns=10,
    )
    PhysicalOnboardingQuarantineLedger.create(
        root / "quarantine",
        adapter,
        ledger_id="quarantine-ledger-1",
        cell_id="cell-1",
        created_at_ns=11,
    )
    context = multiprocessing.get_context("spawn")
    ready_a = context.Event()
    ready_b = context.Event()
    start = context.Event()
    result = context.Queue()
    contenders = [
        context.Process(
            target=_concurrent_attempt_writer,
            args=(
                str(root),
                adapter.qualification_anchor,
                adapter.startup_report,
                attempt_id,
                ready,
                start,
                result,
            ),
        )
        for attempt_id, ready in (("attempt-a", ready_a), ("attempt-b", ready_b))
    ]
    for contender in contenders:
        contender.start()
    assert ready_a.wait(15) and ready_b.wait(15)
    start.set()
    outcomes = [result.get(timeout=20), result.get(timeout=20)]
    for contender in contenders:
        contender.join(timeout=20)
        assert contender.exitcode == 0

    assert sum(item.startswith("SUCCESS:") for item in outcomes) == 1
    assert sum(item.startswith("ERROR:") for item in outcomes) == 1
    snapshot = attempts.snapshot()
    assert len(snapshot.events) == 1
    assert snapshot.events[0].state is AttemptState.INTENT_DURABLE


def test_failure_after_event_publication_leaves_detectable_uncommitted_suffix(
    tmp_path: Path,
) -> None:
    root, normal = _adapter(tmp_path)
    PhysicalOnboardingAttemptLedger.create(
        root / "attempts",
        normal,
        ledger_id="attempt-ledger-1",
        cell_id="cell-1",
        created_at_ns=10,
    )
    quarantine = PhysicalOnboardingQuarantineLedger.create(
        root / "quarantine",
        normal,
        ledger_id="quarantine-ledger-1",
        cell_id="cell-1",
        created_at_ns=11,
    )

    def fail_after_event(checkpoint: str) -> None:
        if checkpoint == DurabilityCheckpoint.LEDGER_AFTER_RECORD_PUBLISH.value:
            raise RuntimeError("injected stop after immutable event")

    faulting = QualifiedWindowsOnboardingPublication(
        deployment_root=root,
        source_binding_sha256=SOURCE,
        qualification_anchor=normal.qualification_anchor,
        startup_report=normal.startup_report,
        mutation_guard=lambda: None,
        fault_injector=fail_after_event,
    )
    attempts = PhysicalOnboardingAttemptLedger.open(
        root / "attempts", faulting, expected_cell_id="cell-1"
    )
    with pytest.raises(RuntimeError, match="injected stop"):
        attempts.begin_attempt(_binding(), quarantine)

    assert (root / "attempts" / "events" / "event-00000000.json").is_file()
    head = json.loads((root / "attempts" / "head.json").read_text("ascii"))
    assert head["event_count"] == 0
    with pytest.raises(AttemptLedgerSuffixError):
        attempts.snapshot()


def test_session_publication_supports_evidence_above_four_mib(
    tmp_path: Path,
) -> None:
    root, adapter = _adapter(tmp_path)
    session = PhysicalOnboardingV2Session.create(
        root,
        session_id="arrival-v2-storage",
        cell_id="cell-1",
        source_binding_sha256=SOURCE,
        created_at_ns=1_000_000,
        publication=adapter,
    )
    initial = session.snapshot()
    waiting = session.commit_stage_state(
        PhysicalOnboardingStage.WORKSPACE_SOURCES,
        V2StageState.WAITING_OPERATOR,
        occurred_at_ns=1_000_001,
        detail_code="WAITING_FOR_OPERATOR",
        expected_head_sha256=initial.head.head_sha256,
    )
    payload = b"x" * (5 * 1024 * 1024)
    evidence = session.store_evidence(
        PhysicalOnboardingStage.WORKSPACE_SOURCES,
        payload,
        label="large bounded evidence",
        media_type="application/octet-stream",
        captured_at_ns=1_000_002,
        expected_head_sha256=waiting.head.head_sha256,
    )

    assert evidence.payload_bytes == len(payload)
    assert (
        session.directory / "evidence" / evidence.evidence_id / "payload.bin"
    ).read_bytes() == payload


def test_paths_outside_qualified_root_and_guard_failure_are_rejected(
    tmp_path: Path,
) -> None:
    outside = tmp_path / "outside"
    outside.mkdir()
    root, adapter = _adapter(tmp_path)
    with pytest.raises(PhysicalOnboardingStorageError, match="outside"):
        adapter.qualification_sha256(outside.resolve())

    rejecting = QualifiedWindowsOnboardingPublication(
        deployment_root=root,
        source_binding_sha256=SOURCE,
        qualification_anchor=adapter.qualification_anchor,
        startup_report=adapter.startup_report,
        mutation_guard=lambda: (_ for _ in ()).throw(RuntimeError("lost lease")),
    )
    with pytest.raises(PhysicalOnboardingStorageError, match="guard"):
        rejecting.write_new_file(root / "must-not-exist.bin", b"bounded")
    assert not (root / "must-not-exist.bin").exists()
