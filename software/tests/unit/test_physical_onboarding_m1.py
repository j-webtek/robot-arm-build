from __future__ import annotations

from dataclasses import replace
import hashlib
import json
import os
from pathlib import Path

import pytest

from rocell.application.physical_onboarding import (
    STAGE_PLAN_SHA256,
    PhysicalOnboardingStage,
)
from rocell.application.physical_onboarding_attempts import (
    AttemptBinding,
    AttemptState,
    PhysicalOnboardingAttemptLedger,
)
from rocell.application.physical_onboarding_m1 import (
    DURABILITY_ANCHOR_FILENAME,
    M1_QUARANTINED_STATUS,
    M1_RECONCILIATION_STATUS,
    M1_STATUS,
    PhysicalOnboardingM1Error,
    PhysicalOnboardingM1Runtime,
)
from rocell.application.physical_onboarding_quarantine import (
    CellQuarantinedError,
    PhysicalOnboardingQuarantineLedger,
    QuarantineLedgerIntegrityError,
)
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_storage import (
    PhysicalOnboardingStorageError,
    QualifiedWindowsOnboardingPublication,
)
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.safety.effects import EffectClass


SOURCE = "a" * 64


pytestmark = pytest.mark.skipif(
    os.name != "nt", reason="M1 physical storage qualification is Windows NTFS only"
)


def _root(tmp_path: Path) -> Path:
    root = tmp_path / "physical-onboarding"
    root.mkdir()
    return root.resolve()


def _runtime(tmp_path: Path) -> PhysicalOnboardingM1Runtime:
    return PhysicalOnboardingM1Runtime.initialize(
        _root(tmp_path),
        source_binding_sha256=SOURCE,
        cell_id="cell-a",
        created_at_ns=1_000,
    )


def _unguarded_ledgers(
    runtime: PhysicalOnboardingM1Runtime,
) -> tuple[PhysicalOnboardingAttemptLedger, PhysicalOnboardingQuarantineLedger]:
    publication = QualifiedWindowsOnboardingPublication(
        deployment_root=runtime.deployment_root,
        source_binding_sha256=runtime.source_binding_sha256,
        qualification_anchor=runtime.qualification_anchor,
        startup_report=runtime.startup_report,
        mutation_guard=lambda: None,
    )
    cell_root = (
        runtime.deployment_root / "cells" / f"cell-{runtime.cell.cell_key_sha256}"
    )
    return (
        PhysicalOnboardingAttemptLedger.open(
            cell_root / "attempts",
            publication,
            expected_cell_id=runtime.cell.cell_id,
        ),
        PhysicalOnboardingQuarantineLedger.open(
            cell_root / "quarantine",
            publication,
            expected_cell_id=runtime.cell.cell_id,
        ),
    )


def _binding(
    runtime: PhysicalOnboardingM1Runtime,
    *,
    attempt_id: str,
    intent_at_ns: int,
) -> AttemptBinding:
    verification = runtime.verify("session-1")
    return AttemptBinding(
        attempt_id=attempt_id,
        session_id="session-1",
        stage="workspace_sources",
        effect_class=EffectClass.NO_DEVICE_IO,
        operation_id="m1.zero-io-recovery-test",
        operation_binding_sha256=hashlib.sha256(b"operation").hexdigest(),
        source_binding_sha256=runtime.source_binding_sha256,
        stage_plan_sha256=STAGE_PLAN_SHA256,
        session_journal_head_sha256=verification.session_head_sha256,
        evidence_inventory_sha256=verification.evidence_inventory_sha256,
        intent_at_ns=intent_at_ns,
    )


def test_initialize_create_reopen_and_verify_remain_zero_hardware(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    before = runtime.verify()
    assert before.session_id is None
    assert before.effects_allowed
    assert before.to_dict()["status"] == M1_STATUS
    assert (runtime.deployment_root / DURABILITY_ANCHOR_FILENAME).is_file()

    created = runtime.create_session("session-1", created_at_ns=2_000)
    assert created.session_id == "session-1"
    assert created.effects_allowed
    assert created.to_dict()["operation_effect"] == {
        "os_device_metadata_reads": 0,
        "device_opens": 0,
        "camera_frames_captured": 0,
        "serial_transactions": 0,
        "robot_power_operations": 0,
        "robot_commands_sent": 0,
    }
    assert created.to_dict()["effect_methods_exposed"] is False

    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=SOURCE,
        cell_id="cell-a",
    )
    verified = reopened.verify("session-1")
    assert verified.qualification_anchor_sha256 == (
        runtime.qualification_anchor.report_sha256
    )
    assert verified.startup_qualification_sha256 != "0" * 64
    assert verified.challenge_sha256 == reopened.verify("session-1").challenge_sha256


def test_low_level_session_mutation_is_rejected_without_live_runtime_leases(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.create_session("session-1", created_at_ns=2_000)
    session = runtime._open_session("session-1")
    snapshot = session.snapshot()

    with pytest.raises(PhysicalOnboardingStorageError, match="guard"):
        session.commit_stage_state(
            PhysicalOnboardingStage.WORKSPACE_SOURCES,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=2_001,
            detail_code="WAITING_FOR_OPERATOR",
            expected_head_sha256=snapshot.head.head_sha256,
        )


def test_committed_intent_only_restart_aborts_without_quarantine(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.create_session("session-1", created_at_ns=2_000)
    attempts, quarantine = _unguarded_ledgers(runtime)
    attempts.begin_attempt(
        _binding(runtime, attempt_id="attempt-1", intent_at_ns=3_000), quarantine
    )

    restarted = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=SOURCE,
        cell_id="cell-a",
    )
    report, verified = restarted.recover_startup("session-1", occurred_at_ns=4_000)
    assert report.aborted_pre_effect == ("attempt-1",)
    assert report.sealed_uncertain == ()
    assert report.quarantines_latched == ()
    assert verified.effects_allowed
    assert verified.quarantined is False
    assert verified.unresolved_attempt_ids == ()


def test_recovery_refuses_to_lock_one_session_for_another_sessions_attempt(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.create_session("session-1", created_at_ns=2_000)
    runtime.create_session("session-2", created_at_ns=2_100)
    attempts, quarantine = _unguarded_ledgers(runtime)
    attempts.begin_attempt(
        _binding(runtime, attempt_id="attempt-1", intent_at_ns=3_000), quarantine
    )

    with pytest.raises(Exception, match="exact session"):
        runtime.recover_startup("session-2", occurred_at_ns=4_000)
    assert attempts.snapshot().latest_event("attempt-1").state is (
        AttemptState.INTENT_DURABLE
    )


def test_armed_restart_latches_global_quarantine_and_blocks_new_session(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.create_session("session-1", created_at_ns=2_000)
    attempts, quarantine = _unguarded_ledgers(runtime)
    attempts.begin_attempt(
        _binding(runtime, attempt_id="attempt-1", intent_at_ns=3_000), quarantine
    )
    attempts.transition(
        "attempt-1",
        AttemptState.EFFECT_ARMED,
        quarantine,
        occurred_at_ns=3_001,
    )

    restarted = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=SOURCE,
        cell_id="cell-a",
    )
    report, verified = restarted.recover_startup("session-1", occurred_at_ns=4_000)
    assert report.sealed_uncertain == ("attempt-1",)
    assert report.quarantines_latched == ("attempt-1",)
    assert verified.effects_allowed is False
    assert verified.quarantined is True
    assert verified.to_dict()["status"] == M1_QUARANTINED_STATUS
    with pytest.raises(CellQuarantinedError):
        restarted.create_session("session-2", created_at_ns=5_000)


def test_new_session_rechecks_global_admission_after_leases_are_held(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _runtime(tmp_path)
    runtime.create_session("session-1", created_at_ns=2_000)
    attempts, quarantine = _unguarded_ledgers(runtime)
    original = PhysicalOnboardingM1Runtime._challenge_for_absent_session
    injected = False

    def inject_before_lock_challenge(
        selected_runtime: PhysicalOnboardingM1Runtime,
        session_id: str,
    ) -> str:
        nonlocal injected
        if selected_runtime is runtime and not injected:
            injected = True
            attempts.begin_attempt(
                _binding(runtime, attempt_id="attempt-race", intent_at_ns=3_000),
                quarantine,
            )
        return original(selected_runtime, session_id)

    monkeypatch.setattr(
        PhysicalOnboardingM1Runtime,
        "_challenge_for_absent_session",
        inject_before_lock_challenge,
    )

    with pytest.raises(CellQuarantinedError, match="startup recovery"):
        runtime.create_session("session-2", created_at_ns=4_000)
    assert not (runtime.deployment_root / "onboarding-session-2").exists()


def test_anchor_tamper_and_source_drift_fail_before_runtime_open(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    anchor_path = runtime.deployment_root / DURABILITY_ANCHOR_FILENAME
    original = anchor_path.read_bytes()
    document = json.loads(original)
    document["source_binding_sha256"] = "b" * 64
    anchor_path.write_bytes(
        (json.dumps(document, sort_keys=True, separators=(",", ":")) + "\n").encode(
            "ascii"
        )
    )
    with pytest.raises(Exception, match="hash|qualification"):
        PhysicalOnboardingM1Runtime.open(
            runtime.deployment_root,
            source_binding_sha256=SOURCE,
            cell_id="cell-a",
        )
    anchor_path.write_bytes(original)

    with pytest.raises(Exception, match="source"):
        PhysicalOnboardingM1Runtime.open(
            runtime.deployment_root,
            source_binding_sha256="b" * 64,
            cell_id="cell-a",
        )


def test_global_ledger_identity_is_bound_to_immutable_cell_descriptor(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    cell_root = (
        runtime.deployment_root / "cells" / f"cell-{runtime.cell.cell_key_sha256}"
    )
    publication = QualifiedWindowsOnboardingPublication(
        deployment_root=runtime.deployment_root,
        source_binding_sha256=runtime.source_binding_sha256,
        qualification_anchor=runtime.qualification_anchor,
        startup_report=runtime.startup_report,
        mutation_guard=lambda: None,
    )
    substitute = PhysicalOnboardingAttemptLedger.create(
        cell_root / "substitute-attempts",
        publication,
        ledger_id="different-attempt-ledger",
        cell_id=runtime.cell.cell_id,
        created_at_ns=2_000,
    )
    original = cell_root / "attempts"
    original.rename(runtime.deployment_root / "retained-original-attempts")
    substitute.root.rename(original)

    with pytest.raises(PhysicalOnboardingM1Error, match="cell descriptor"):
        PhysicalOnboardingM1Runtime.open(
            runtime.deployment_root,
            source_binding_sha256=SOURCE,
            cell_id="cell-a",
        )


def test_active_attempt_provenance_must_match_runtime_source(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    runtime.create_session("session-1", created_at_ns=2_000)
    attempts, quarantine = _unguarded_ledgers(runtime)
    forged = replace(
        _binding(runtime, attempt_id="attempt-forged", intent_at_ns=3_000),
        source_binding_sha256="b" * 64,
    )
    attempts.begin_attempt(forged, quarantine)

    with pytest.raises(PhysicalOnboardingM1Error, match="provenance"):
        runtime.verify("session-1")


def test_cell_descriptor_hard_link_is_rejected(tmp_path: Path) -> None:
    runtime = _runtime(tmp_path)
    cell_root = (
        runtime.deployment_root / "cells" / f"cell-{runtime.cell.cell_key_sha256}"
    )
    descriptor = cell_root / "cell.json"
    retained = runtime.deployment_root / "retained-cell-descriptor.json"
    descriptor.rename(retained)
    try:
        os.link(retained, descriptor)
    except OSError as exc:
        pytest.skip(f"hard links unavailable: {exc}")

    with pytest.raises(PhysicalOnboardingM1Error, match="cannot read"):
        PhysicalOnboardingM1Runtime.open(
            runtime.deployment_root,
            source_binding_sha256=SOURCE,
            cell_id="cell-a",
        )


def test_active_owner_metadata_is_visible_as_reconciliation_required(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    before = runtime.verify()
    held = runtime._leases.acquire(
        (LeaseSpec(LeaseLevel.CELL, runtime.cell.cell_id),),
        operation="M1_READINESS_TEST",
        expected_challenge_sha256=before.challenge_sha256,
        challenge_callback=lambda: runtime.verify().challenge_sha256,
        effectful=False,
        acquired_at_ns=5_000,
    )
    # Model a process exit: the kernel lock disappears but durable ACTIVE owner
    # metadata remains until an explicitly reviewed reconciliation.
    held._leases[0].lock.release()
    held._closed = True

    status = runtime.verify()
    assert status.effects_allowed is False
    assert status.active_lease_owners[0].startswith("CELL:cell-a:")
    assert status.to_dict()["status"] == M1_RECONCILIATION_STATUS
    assert status.to_dict()["leases"]["reconciliation_required"] is True


def test_global_verification_retries_one_transient_cross_ledger_read(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    runtime = _runtime(tmp_path)
    original = PhysicalOnboardingQuarantineLedger.verified_snapshots
    calls = 0

    def fail_once(
        ledger: PhysicalOnboardingQuarantineLedger,
        attempts: PhysicalOnboardingAttemptLedger,
    ) -> tuple[object, object]:
        nonlocal calls
        calls += 1
        if ledger is runtime._quarantine and calls == 1:
            raise QuarantineLedgerIntegrityError("transient mixed pair")
        return original(ledger, attempts)

    monkeypatch.setattr(
        PhysicalOnboardingQuarantineLedger,
        "verified_snapshots",
        fail_once,
    )
    assert runtime.verify().effects_allowed
    assert calls >= 3


def test_mutation_guard_rejects_a_live_lease_for_the_wrong_resource(
    tmp_path: Path,
) -> None:
    runtime = _runtime(tmp_path)
    wrong_spec = LeaseSpec(LeaseLevel.CELL, "different-cell")
    held = runtime._leases.acquire(
        (wrong_spec,),
        operation="WRONG_RESOURCE_TEST",
        expected_challenge_sha256="d" * 64,
        challenge_callback=lambda: "d" * 64,
        effectful=False,
        acquired_at_ns=6_000,
    )
    try:
        with pytest.raises(PhysicalOnboardingM1Error, match="exact required"):
            runtime._guard.activate(
                held,
                expected_specs=(LeaseSpec(LeaseLevel.CELL, runtime.cell.cell_id),),
                source_binding_sha256=runtime.source_binding_sha256,
            )
    finally:
        held.close(released_at_ns=7_000)
