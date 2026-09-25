from __future__ import annotations

import json
from pathlib import Path
import threading

import pytest

from rocell.application.physical_onboarding_attempts import (
    AttemptBinding,
    AttemptLedgerIntegrityError,
    AttemptLedgerSuffixError,
    AttemptState,
    AttemptTransitionError,
    PhysicalOnboardingAttemptLedger,
)
from rocell.application.physical_onboarding_quarantine import (
    PhysicalOnboardingQuarantineLedger,
)
from rocell.safety.effects import EffectClass


def _sha(label: str) -> str:
    import hashlib

    return hashlib.sha256(label.encode("ascii")).hexdigest()


class TestDurablePublisher:
    """Test-only publisher; production code requires a qualified OS adapter."""

    __test__ = False

    def __init__(self) -> None:
        self.qualification = _sha("qualified-volume-receipt")
        self.qualified = True
        self.append_calls = 0
        self.fail_next_append = False
        self._lock = threading.Lock()

    def qualification_sha256(self, root: Path) -> str:
        if not self.qualified:
            raise RuntimeError("volume is not qualified")
        return self.qualification

    def initialize_ledger(
        self, root: Path, *, header_payload: bytes, head_payload: bytes
    ) -> None:
        root.mkdir(parents=True, exist_ok=False)
        (root / "events").mkdir()
        (root / "header.json").write_bytes(header_payload)
        (root / "head.json").write_bytes(head_payload)

    def read_bounded(
        self, root: Path, relative_path: str, *, maximum_bytes: int
    ) -> bytes:
        payload = (root / Path(relative_path)).read_bytes()
        if len(payload) > maximum_bytes:
            raise RuntimeError("resource bound")
        return payload

    def list_relative_files(
        self, root: Path, *, maximum_entries: int
    ) -> tuple[str, ...]:
        files = tuple(
            sorted(
                path.relative_to(root).as_posix()
                for path in root.rglob("*")
                if path.is_file()
            )
        )
        if len(files) > maximum_entries:
            raise RuntimeError("entry bound")
        return files

    def commit_append(
        self,
        root: Path,
        *,
        event_relative_path: str,
        event_payload: bytes,
        head_payload: bytes,
        expected_head_sha256: str,
    ) -> None:
        self.append_calls += 1
        if self.fail_next_append:
            self.fail_next_append = False
            raise RuntimeError("injected publication failure")
        with self._lock:
            current = json.loads((root / "head.json").read_text("ascii"))
            if current["head_sha256"] != expected_head_sha256:
                raise RuntimeError("stale committed head")
            event_path = root / Path(event_relative_path)
            event_path.write_bytes(event_payload)
            (root / "head.json").write_bytes(head_payload)


@pytest.fixture
def ledgers(
    tmp_path: Path,
) -> tuple[
    TestDurablePublisher,
    PhysicalOnboardingAttemptLedger,
    PhysicalOnboardingQuarantineLedger,
]:
    publisher = TestDurablePublisher()
    attempts = PhysicalOnboardingAttemptLedger.create(
        tmp_path / "attempts",
        publisher,
        ledger_id="attempt-ledger-1",
        cell_id="cell-1",
        created_at_ns=10,
    )
    quarantine = PhysicalOnboardingQuarantineLedger.create(
        tmp_path / "quarantine",
        publisher,
        ledger_id="quarantine-ledger-1",
        cell_id="cell-1",
        created_at_ns=11,
    )
    return publisher, attempts, quarantine


def binding(
    attempt_id: str = "attempt-1",
    *,
    session_id: str = "session-1",
    intent_at_ns: int = 100,
) -> AttemptBinding:
    return AttemptBinding(
        attempt_id=attempt_id,
        session_id=session_id,
        stage="camera_frame_freshness",
        effect_class=EffectClass.BOUNDED_CAMERA_CAMPAIGN,
        operation_id="camera.freshness.bounded-campaign",
        operation_binding_sha256=_sha("operation"),
        source_binding_sha256=_sha("controlled-source"),
        stage_plan_sha256=_sha("stage-plan"),
        session_journal_head_sha256=_sha("session-head-0"),
        evidence_inventory_sha256=_sha("evidence-0"),
        intent_at_ns=intent_at_ns,
    )


def test_exact_known_attempt_path_binds_all_provenance_and_both_heads(
    ledgers: tuple[
        TestDurablePublisher,
        PhysicalOnboardingAttemptLedger,
        PhysicalOnboardingQuarantineLedger,
    ],
) -> None:
    _, attempts, quarantine = ledgers
    intent = attempts.begin_attempt(binding(), quarantine)
    armed = attempts.transition(
        "attempt-1", AttemptState.EFFECT_ARMED, quarantine, occurred_at_ns=101
    )
    observed = attempts.transition(
        "attempt-1",
        AttemptState.EFFECT_OBSERVED,
        quarantine,
        occurred_at_ns=102,
        session_journal_head_sha256=_sha("session-head-1"),
        evidence_inventory_sha256=_sha("evidence-1"),
    )
    cleanup = attempts.transition(
        "attempt-1", AttemptState.CLEANUP_CONFIRMED, quarantine, occurred_at_ns=103
    )
    sealed = attempts.transition(
        "attempt-1", AttemptState.SEALED_KNOWN, quarantine, occurred_at_ns=104
    )

    snapshot = attempts.snapshot()
    assert [event.state for event in snapshot.events] == [
        AttemptState.INTENT_DURABLE,
        AttemptState.EFFECT_ARMED,
        AttemptState.EFFECT_OBSERVED,
        AttemptState.CLEANUP_CONFIRMED,
        AttemptState.SEALED_KNOWN,
    ]
    assert len({event.attempt_head_before_sha256 for event in snapshot.events}) == 5
    assert all(
        event.quarantine_head_sha256 == quarantine.snapshot().head_sha256
        for event in snapshot.events
    )
    assert sealed.source_binding_sha256 == intent.source_binding_sha256
    assert sealed.stage_plan_sha256 == intent.stage_plan_sha256
    assert sealed.operation_binding_sha256 == intent.operation_binding_sha256
    assert observed.session_journal_head_sha256 == _sha("session-head-1")
    assert observed.evidence_inventory_sha256 == _sha("evidence-1")
    assert cleanup.previous_attempt_event_sha256 == observed.event_sha256
    assert sealed.to_dict()["physical_authority"] is False
    assert sealed.to_dict()["automatic_retry_allowed"] is False
    assert armed.effect_class is EffectClass.BOUNDED_CAMERA_CAMPAIGN


def test_only_frozen_transitions_are_accepted_and_attempt_ids_never_reuse(
    ledgers: tuple[
        TestDurablePublisher,
        PhysicalOnboardingAttemptLedger,
        PhysicalOnboardingQuarantineLedger,
    ],
) -> None:
    _, attempts, quarantine = ledgers
    attempts.begin_attempt(binding(), quarantine)
    with pytest.raises(AttemptTransitionError):
        attempts.transition(
            "attempt-1", AttemptState.EFFECT_OBSERVED, quarantine, occurred_at_ns=101
        )
    attempts.transition(
        "attempt-1", AttemptState.ABORTED_PRE_EFFECT, quarantine, occurred_at_ns=102
    )
    with pytest.raises(AttemptTransitionError):
        attempts.transition(
            "attempt-1", AttemptState.EFFECT_ARMED, quarantine, occurred_at_ns=103
        )
    with pytest.raises(AttemptTransitionError, match="never be reused"):
        attempts.begin_attempt(binding(), quarantine)


def test_publication_failure_is_surfaced_after_exactly_one_call_without_retry(
    ledgers: tuple[
        TestDurablePublisher,
        PhysicalOnboardingAttemptLedger,
        PhysicalOnboardingQuarantineLedger,
    ],
) -> None:
    publisher, attempts, quarantine = ledgers
    publisher.fail_next_append = True
    before = publisher.append_calls
    with pytest.raises(RuntimeError, match="injected publication failure"):
        attempts.begin_attempt(binding(), quarantine)
    assert publisher.append_calls == before + 1
    assert attempts.snapshot().events == ()


def test_noncanonical_tamper_unknown_file_and_suffix_deletion_fail_closed(
    ledgers: tuple[
        TestDurablePublisher,
        PhysicalOnboardingAttemptLedger,
        PhysicalOnboardingQuarantineLedger,
    ],
) -> None:
    _, attempts, quarantine = ledgers
    attempts.begin_attempt(binding(), quarantine)
    root = attempts.root
    event_path = root / "events" / "event-00000000.json"
    original = event_path.read_bytes()

    document = json.loads(original)
    event_path.write_bytes((json.dumps(document, indent=2) + "\n").encode("ascii"))
    with pytest.raises(AttemptLedgerIntegrityError, match="canonical"):
        attempts.snapshot()
    event_path.write_bytes(original)

    (root / "unexpected.json").write_text("{}\n", encoding="ascii")
    with pytest.raises(AttemptLedgerIntegrityError, match="unknown path"):
        attempts.snapshot()
    (root / "unexpected.json").unlink()

    event_path.unlink()
    with pytest.raises(AttemptLedgerSuffixError):
        attempts.snapshot()


def test_committed_head_anchor_and_current_volume_qualification_fail_closed(
    ledgers: tuple[
        TestDurablePublisher,
        PhysicalOnboardingAttemptLedger,
        PhysicalOnboardingQuarantineLedger,
    ],
) -> None:
    publisher, attempts, quarantine = ledgers
    old_head = attempts.snapshot().head_sha256
    attempts.begin_attempt(binding(), quarantine)
    with pytest.raises(AttemptLedgerIntegrityError, match="anchor mismatch"):
        attempts.snapshot(expected_head_sha256=old_head)
    publisher.qualification = _sha("different-qualified-volume-receipt")
    with pytest.raises(AttemptLedgerIntegrityError, match="qualification"):
        attempts.snapshot()
