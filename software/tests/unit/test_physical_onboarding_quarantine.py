from __future__ import annotations

import json
from pathlib import Path

import pytest

from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    PhysicalOnboardingAttemptLedger,
)
from rocell.application.physical_onboarding_quarantine import (
    CellQuarantinedError,
    PhysicalOnboardingQuarantineLedger,
    QuarantineLedgerIntegrityError,
    QuarantineLedgerSuffixError,
    QuarantineReason,
    recover_physical_onboarding_startup,
)
from test_physical_onboarding_attempts import TestDurablePublisher, binding


def _ledgers(
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


def test_intent_only_recovery_aborts_pre_effect_and_is_idempotent(
    tmp_path: Path,
) -> None:
    _, attempts, quarantine = _ledgers(tmp_path)
    attempts.begin_attempt(binding(), quarantine)

    first = recover_physical_onboarding_startup(
        attempts, quarantine, occurred_at_ns=200
    )
    assert first.aborted_pre_effect == ("attempt-1",)
    assert first.sealed_uncertain == ()
    assert first.quarantines_latched == ()
    assert attempts.snapshot().latest_event("attempt-1").state is (
        AttemptState.ABORTED_PRE_EFFECT
    )
    assert not quarantine.snapshot().latched

    second = recover_physical_onboarding_startup(
        attempts, quarantine, occurred_at_ns=201
    )
    assert not second.changed
    attempts.begin_attempt(
        binding("attempt-2", session_id="new-session", intent_at_ns=202), quarantine
    )


@pytest.mark.parametrize(
    "unsealed_state",
    [
        AttemptState.EFFECT_ARMED,
        AttemptState.EFFECT_OBSERVED,
        AttemptState.CLEANUP_CONFIRMED,
    ],
)
def test_any_armed_unsealed_restart_becomes_uncertain_and_globally_latched(
    tmp_path: Path, unsealed_state: AttemptState
) -> None:
    _, attempts, quarantine = _ledgers(tmp_path)
    attempts.begin_attempt(binding(), quarantine)
    attempts.transition(
        "attempt-1", AttemptState.EFFECT_ARMED, quarantine, occurred_at_ns=101
    )
    if unsealed_state in {
        AttemptState.EFFECT_OBSERVED,
        AttemptState.CLEANUP_CONFIRMED,
    }:
        attempts.transition(
            "attempt-1", AttemptState.EFFECT_OBSERVED, quarantine, occurred_at_ns=102
        )
    if unsealed_state is AttemptState.CLEANUP_CONFIRMED:
        attempts.transition(
            "attempt-1", AttemptState.CLEANUP_CONFIRMED, quarantine, occurred_at_ns=103
        )

    report = recover_physical_onboarding_startup(
        attempts, quarantine, occurred_at_ns=200
    )
    assert report.sealed_uncertain == ("attempt-1",)
    assert report.quarantines_latched == ("attempt-1",)
    assert attempts.snapshot().latest_event("attempt-1").state is (
        AttemptState.SEALED_UNCERTAIN
    )
    quarantine_event = quarantine.snapshot().events[0]
    assert quarantine_event.reason is QuarantineReason.SIDE_EFFECT_UNCERTAIN
    assert quarantine_event.attempt_head_sha256 == report.final_attempt_head_sha256
    assert report.final_attempt_head_sha256 != report.final_quarantine_head_sha256
    with pytest.raises(CellQuarantinedError):
        attempts.begin_attempt(
            binding("attempt-2", session_id="new-session"), quarantine
        )

    repeated = recover_physical_onboarding_startup(
        attempts, quarantine, occurred_at_ns=201
    )
    assert not repeated.changed
    assert len(quarantine.snapshot().events) == 1


def test_crash_between_uncertain_seal_and_quarantine_latch_is_fail_closed(
    tmp_path: Path,
) -> None:
    _, attempts, quarantine = _ledgers(tmp_path)
    attempts.begin_attempt(binding(), quarantine)
    attempts.transition(
        "attempt-1", AttemptState.EFFECT_ARMED, quarantine, occurred_at_ns=101
    )
    attempts.transition(
        "attempt-1", AttemptState.SEALED_UNCERTAIN, quarantine, occurred_at_ns=102
    )
    assert not quarantine.snapshot().latched

    with pytest.raises(CellQuarantinedError, match="startup recovery"):
        attempts.begin_attempt(
            binding("attempt-2", session_id="new-session"), quarantine
        )
    report = recover_physical_onboarding_startup(
        attempts, quarantine, occurred_at_ns=200
    )
    assert report.sealed_uncertain == ()
    assert report.quarantines_latched == ("attempt-1",)
    assert quarantine.snapshot().latched


def test_known_seal_does_not_latch_quarantine(tmp_path: Path) -> None:
    _, attempts, quarantine = _ledgers(tmp_path)
    attempts.begin_attempt(binding(), quarantine)
    for timestamp, state in enumerate(
        (
            AttemptState.EFFECT_ARMED,
            AttemptState.EFFECT_OBSERVED,
            AttemptState.CLEANUP_CONFIRMED,
            AttemptState.SEALED_KNOWN,
        ),
        start=101,
    ):
        attempts.transition("attempt-1", state, quarantine, occurred_at_ns=timestamp)
    report = recover_physical_onboarding_startup(
        attempts, quarantine, occurred_at_ns=200
    )
    assert not report.changed
    assert not quarantine.snapshot().latched


def test_quarantine_tamper_unknown_suffix_and_deleted_suffix_fail_closed(
    tmp_path: Path,
) -> None:
    _, attempts, quarantine = _ledgers(tmp_path)
    attempts.begin_attempt(binding(), quarantine)
    attempts.transition(
        "attempt-1", AttemptState.EFFECT_ARMED, quarantine, occurred_at_ns=101
    )
    recover_physical_onboarding_startup(attempts, quarantine, occurred_at_ns=200)
    event_path = quarantine.root / "events" / "event-00000000.json"
    original = event_path.read_bytes()
    document = json.loads(original)
    document["session_id"] = "forged-session"
    event_path.write_bytes(
        (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "ascii"
        )
    )
    with pytest.raises(QuarantineLedgerIntegrityError, match="hash mismatch"):
        quarantine.snapshot()
    event_path.write_bytes(original)

    extra = quarantine.root / "events" / "event-00000001.json"
    extra.write_bytes(original)
    with pytest.raises(QuarantineLedgerSuffixError):
        quarantine.snapshot()
    extra.unlink()

    event_path.unlink()
    with pytest.raises(QuarantineLedgerSuffixError):
        quarantine.snapshot()


def test_unqualified_volume_prevents_all_reconstruction_and_mutation(
    tmp_path: Path,
) -> None:
    publisher, attempts, quarantine = _ledgers(tmp_path)
    publisher.qualified = False
    with pytest.raises(RuntimeError, match="not qualified"):
        attempts.snapshot()
    with pytest.raises(RuntimeError, match="not qualified"):
        quarantine.snapshot()
