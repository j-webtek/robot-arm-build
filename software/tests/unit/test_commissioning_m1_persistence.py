"""Real qualified NTFS/OS-lease rehearsal storage, with incapable workers only."""

from __future__ import annotations

from dataclasses import asdict, replace
import hashlib
import json
import os
import time
from pathlib import Path
from threading import Event
from typing import Any

import pytest

from rocell.application.cell_commissioning_coordinator import (
    CampaignBudget,
    CampaignRegistration,
    CellCommissioningCoordinator,
    CommissioningCoordinatorError,
    ExactOperationPermit,
    INCAPABLE_COMPOSITION,
    ObservedPowerState,
    RegisteredActionRequest,
    WorkerReceipt,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistence,
    M1CommissioningPersistenceError,
    M1RehearsalTransaction,
    RehearsalAdmissionFacts,
    rehearsal_source_binding,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import (
    AttemptBinding,
    AttemptState,
    PhysicalOnboardingAttemptLedger,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_leases import (
    LeaseLevel,
    LeaseSpec,
    PhysicalOnboardingLeaseError,
)
from rocell.application.physical_onboarding_m1 import (
    PhysicalOnboardingM1Error,
    PhysicalOnboardingM1Runtime,
)
from rocell.application.physical_onboarding_v2 import (
    PhysicalOnboardingV2Error,
    PhysicalOnboardingV2Session,
    V2SessionHeader,
    V2StageState,
    PORTABLE_UNQUALIFIED,
)
from rocell.safety.effects import EffectCertainty, EffectClass


SOURCE = "a" * 64
CELL = "wizard-rehearsal-" + "b" * 16
SESSION = "rehearsal-" + "c" * 32
FIRST = PhysicalOnboardingStage.WORKSPACE_SOURCES
WINDOWS = pytest.mark.skipif(
    os.name != "nt", reason="actual M1 publication requires local Windows NTFS"
)


def _facts(request: RegisteredActionRequest, snapshot: Any) -> RehearsalAdmissionFacts:
    return RehearsalAdmissionFacts(
        {"source": SOURCE, "hardware_incapable": True},
        tuple({"epoch": index, "source": SOURCE} for index in range(8)),
        None,
    )


def _runtime(
    tmp_path: Path, *, waiting: bool = True
) -> tuple[PhysicalOnboardingM1Runtime, M1CommissioningPersistence]:
    root = tmp_path / "isolated-rehearsal"
    root.mkdir()
    runtime = PhysicalOnboardingM1Runtime.initialize(
        root,
        source_binding_sha256=rehearsal_source_binding(SOURCE),
        cell_id=CELL,
        created_at_ns=1000,
    )
    runtime.create_session(
        SESSION, created_at_ns=2000, mode="REHEARSAL", workspace_source_sha256=SOURCE
    )
    adapter = M1CommissioningPersistence(
        runtime, workspace_source_sha256=SOURCE, admission_facts=_facts
    )
    if waiting:
        with adapter.stage_transaction(
            SESSION,
            expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
        ) as tx:
            tx.commit_stage_state(
                FIRST,
                V2StageState.WAITING_OPERATOR,
                occurred_at_ns=2001,
                detail_code="REHEARSAL_EVIDENCE_PENDING",
                expected_head_sha256=tx.snapshot().head.head_sha256,
            )
    return runtime, adapter


class IncapableWorker:
    composition = INCAPABLE_COMPOSITION
    worker_executable_sha256 = "b" * 64

    def __init__(
        self, runtime: PhysicalOnboardingM1Runtime, *, fail: bool = False
    ) -> None:
        self.runtime, self.fail, self.calls = runtime, fail, 0

    def run_campaign(
        self, permit: ExactOperationPermit, *, deadline_ns: int, cancellation: Event
    ) -> WorkerReceipt:
        self.calls += 1
        actual = self.runtime.verify(SESSION)
        assert actual.attempt_event_count == 2
        assert permit.attempt_id in actual.unresolved_attempt_ids
        assert len(actual.active_lease_owners) == 2
        if self.fail:
            raise TimeoutError("synthetic bounded-worker interruption")
        return WorkerReceipt(
            permit.attempt_id,
            permit.permit_sha256,
            self.worker_executable_sha256,
            permit.admission.selected_identity_sha256,
            EffectCertainty.CONFIRMED,
            True,
            ObservedPowerState.DEENERGIZED,
            0,
            0,
            0,
            0,
            0,
            128,
            (),
        )


def _core(
    runtime: PhysicalOnboardingM1Runtime,
    adapter: M1CommissioningPersistence,
    *,
    key: str = "request-one",
    fail: bool = False,
) -> tuple[CellCommissioningCoordinator, IncapableWorker, RegisteredActionRequest]:
    worker = IncapableWorker(runtime, fail=fail)
    registration = CampaignRegistration(
        "rehearsal-source-check",
        FIRST,
        EffectClass.NO_DEVICE_IO,
        "incapable-source-worker",
        worker.worker_executable_sha256,
        "d" * 64,
        (),
        CampaignBudget(120000, 1024, 0, 0, 0, 0, 0),
    )
    request = RegisteredActionRequest(
        CELL, SESSION, registration.action_id, key, "a" * 64
    )
    with adapter.transaction(
        (LeaseSpec(LeaseLevel.CELL, CELL), LeaseSpec(LeaseLevel.SESSION, SESSION))
    ) as tx:
        request = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )
    return (
        CellCommissioningCoordinator(
            persistence=adapter,
            registrations=(registration,),
            workers={registration.worker_id: worker},
        ),
        worker,
        request,
    )


def _records(runtime: PhysicalOnboardingM1Runtime) -> Path:
    return (
        runtime.deployment_root
        / "cells"
        / f"cell-{runtime.cell.cell_key_sha256}"
        / "rehearsal-records"
    )


def test_domain_binding_and_frozen_server_documents_are_deterministic() -> None:
    assert rehearsal_source_binding(SOURCE) != SOURCE
    assert rehearsal_source_binding(SOURCE) == rehearsal_source_binding(SOURCE)
    mutable = {"mode": "initial"}
    facts = RehearsalAdmissionFacts(mutable, ({"epoch": 1},) * 8, None)
    before = facts._hazard
    mutable["mode"] = "changed"
    assert facts._hazard == before
    for invalid in ("0" * 64, "bad", True, [], None):
        with pytest.raises(M1CommissioningPersistenceError):
            rehearsal_source_binding(invalid)
    with pytest.raises(M1CommissioningPersistenceError, match="eight"):
        RehearsalAdmissionFacts({}, ({},), None)


def test_v2_physical_default_serialization_and_explicit_rehearsal_roundtrip(
    tmp_path: Path,
) -> None:
    kwargs = dict(
        session_id="old-session",
        cell_id="cell-a",
        created_at_ns=1000,
        source_binding_sha256=SOURCE,
        publication_durability=PORTABLE_UNQUALIFIED,
        durability_qualification_sha256="0" * 64,
    )
    default = V2SessionHeader.build(**kwargs)
    explicit = V2SessionHeader.build(**kwargs, mode="PHYSICAL_DIAGNOSTIC")
    assert default.to_dict() == explicit.to_dict()
    # Golden pre-extension physical header digest: the value extension must not
    # introduce a new field or alter the existing physical serialization.
    assert (
        default.header_sha256
        == "9c5d3184f1e41f6a8c6bdceba8df8dacff8daed8c14dae094d352a25e4d1c621"
    )
    session = PhysicalOnboardingV2Session.create(
        tmp_path,
        session_id=SESSION,
        cell_id=CELL,
        source_binding_sha256=rehearsal_source_binding(SOURCE),
        created_at_ns=1000,
        mode="REHEARSAL",
    )
    reopened = PhysicalOnboardingV2Session.open(session.directory)
    assert reopened.snapshot().header.mode == "REHEARSAL"
    assert reopened.snapshot().header.to_dict() == session.snapshot().header.to_dict()
    assert reopened.snapshot().header.to_dict()["physical_release_effect"] == "NONE"
    for invalid in ([], {}, "physical", True):
        with pytest.raises(PhysicalOnboardingV2Error):
            V2SessionHeader.build(**kwargs, mode=invalid)
    with pytest.raises(PhysicalOnboardingV2Error, match="namespace"):
        V2SessionHeader.build(**kwargs, mode="REHEARSAL")


@WINDOWS
def test_qualified_stage_transaction_has_exact_os_leases_and_expires(
    tmp_path: Path,
) -> None:
    runtime, adapter = _runtime(tmp_path, waiting=False)
    before = adapter.verification(SESSION)
    with adapter.stage_transaction(
        SESSION, expected_challenge_sha256=before.challenge_sha256
    ) as tx:
        assert tx.held_leases == (
            LeaseSpec(LeaseLevel.CELL, CELL),
            LeaseSpec(LeaseLevel.SESSION, SESSION),
        )
        assert len(tx.verification().active_lease_owners) == 2
        with pytest.raises(PhysicalOnboardingLeaseError):
            with runtime.rehearsal_transaction(SESSION):
                pytest.fail("second writer must never enter")
        snapshot = tx.snapshot()
        tx.commit_stage_state(
            FIRST,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=2001,
            detail_code="REHEARSAL_READY",
            expected_head_sha256=snapshot.head.head_sha256,
        )
    assert not adapter.verification(SESSION).active_lease_owners
    with pytest.raises(M1CommissioningPersistenceError, match="scope"):
        tx.snapshot()
    with pytest.raises(PhysicalOnboardingLeaseError, match="challenge"):
        with adapter.stage_transaction(
            SESSION, expected_challenge_sha256=before.challenge_sha256
        ):
            pytest.fail("stale stage transaction admitted")


@WINDOWS
def test_stage_intake_retains_evidence_before_exact_review_commit(
    tmp_path: Path,
) -> None:
    _, adapter = _runtime(tmp_path)
    before = adapter.verification(SESSION)
    with adapter.stage_transaction(
        SESSION, expected_challenge_sha256=before.challenge_sha256
    ) as tx:
        snapshot = tx.snapshot()
        with pytest.raises(PhysicalOnboardingV2Error):
            tx.commit_stage_state(
                FIRST,
                V2StageState.PASS,
                occurred_at_ns=2002,
                detail_code="FORBIDDEN_SKIP",
                expected_head_sha256=snapshot.head.head_sha256,
            )
        evidence = tx.store_evidence(
            FIRST,
            b'{"composition":"HARDWARE_INCAPABLE_REHEARSAL"}',
            label="synthetic source assessment",
            media_type="application/json",
            captured_at_ns=2002,
            expected_head_sha256=snapshot.head.head_sha256,
        )
        reviewed = tx.commit_stage_state(
            FIRST,
            V2StageState.REVIEW_PENDING,
            occurred_at_ns=2003,
            detail_code="REHEARSAL_REVIEW_PENDING",
            expected_head_sha256=snapshot.head.head_sha256,
            evidence=(evidence,),
        )
        passed = tx.commit_stage_state(
            FIRST,
            V2StageState.PASS,
            occurred_at_ns=2004,
            detail_code="REHEARSAL_REVIEW_ACCEPTED",
            expected_head_sha256=reviewed.head.head_sha256,
            evidence=(evidence,),
        )
        assert passed.state_for(FIRST) is V2StageState.PASS
    assert len(adapter.snapshot(SESSION).evidence) == 1


@WINDOWS
def test_real_core_publishes_lifecycle_then_restart_rejects_durable_request(
    tmp_path: Path,
) -> None:
    runtime, adapter = _runtime(tmp_path)
    core, worker, request = _core(runtime, adapter)
    permit = core.prepare(request)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    assert core.execute(permit) == result
    assert worker.calls == 1
    verified = adapter.verification(SESSION)
    assert verified.attempt_event_count == 5 and verified.effects_allowed
    assert len(list(_records(runtime).glob("*.json"))) == 4
    restarted = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=rehearsal_source_binding(SOURCE),
        cell_id=CELL,
    )
    new_adapter = M1CommissioningPersistence(
        restarted, workspace_source_sha256=SOURCE, admission_facts=_facts
    )
    new_core, new_worker, duplicate = _core(restarted, new_adapter)
    with pytest.raises(CommissioningCoordinatorError, match="restarted"):
        new_core.execute(permit)
    second = new_core.prepare(duplicate)
    with pytest.raises(M1CommissioningPersistenceError, match="durably consumed"):
        new_core.execute(second)
    assert new_worker.calls == 0
    assert new_adapter.verification(SESSION).attempt_event_count == 5


@WINDOWS
def test_actual_admission_heads_are_derived_from_qualified_m1(tmp_path: Path) -> None:
    runtime, adapter = _runtime(tmp_path)
    _, _, request = _core(runtime, adapter)
    with adapter.transaction(
        (LeaseSpec(LeaseLevel.CELL, CELL), LeaseSpec(LeaseLevel.SESSION, SESSION))
    ) as tx:
        admission = tx.read_admission(request)
        verification = tx.verification()
        assert admission.journal_head_sha256 == verification.session_head_sha256
        assert admission.global_attempt_head_sha256 == verification.attempt_head_sha256
        assert admission.quarantine_head_sha256 == verification.quarantine_head_sha256
        assert (
            admission.evidence_inventory_sha256
            == verification.evidence_inventory_sha256
        )
        assert (
            admission.durability_qualification_sha256
            == runtime.qualification_anchor.report_sha256
        )
        assert admission.source_binding_sha256 == rehearsal_source_binding(SOURCE)


@WINDOWS
def test_worker_interruption_seals_uncertainty_and_cell_quarantine(
    tmp_path: Path,
) -> None:
    runtime, adapter = _runtime(tmp_path)
    core, worker, request = _core(runtime, adapter, fail=True)
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert worker.calls == 1
    verified = adapter.verification(SESSION)
    assert verified.quarantined and verified.quarantine_count == 1
    assert result.attempt_id in verified.uncertain_attempt_ids
    with pytest.raises(Exception, match="quarantine"):
        runtime.create_session(
            "rehearsal-" + "d" * 32, mode="REHEARSAL", workspace_source_sha256=SOURCE
        )


@WINDOWS
def test_orphan_reservation_after_intent_publication_failure_blocks_replay(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, adapter = _runtime(tmp_path)
    core, worker, request = _core(runtime, adapter)
    permit = core.prepare(request)

    def fail_intent(*args: Any, **kwargs: Any) -> None:
        raise OSError("injected intent publication interruption")

    monkeypatch.setattr(PhysicalOnboardingAttemptLedger, "begin_attempt", fail_intent)
    with pytest.raises(OSError, match="publication"):
        core.execute(permit)
    assert worker.calls == 0
    assert runtime.verify(SESSION).attempt_event_count == 0
    assert len(list(_records(runtime).glob("request-*.json"))) == 1
    with pytest.raises(M1CommissioningPersistenceError, match="lacks committed intent"):
        _core(runtime, adapter, key="fresh-key")


@WINDOWS
@pytest.mark.parametrize("tamper", ["missing", "hash", "forged_receipt"])
def test_known_result_evidence_tamper_blocks_future_admission(
    tmp_path: Path, tamper: str
) -> None:
    runtime, adapter = _runtime(tmp_path)
    core, _, request = _core(runtime, adapter)
    result = core.execute(core.prepare(request))
    path = _records(runtime) / f"result-{result.attempt_id}-sealed_known.json"
    if tamper == "missing":
        path.unlink()
    else:
        record = json.loads(path.read_bytes())
        record["data"]["result"]["receipt"]["opens"] = 1
        if tamper == "forged_receipt":
            record["record_sha256"] = hashlib.sha256(
                canonical_json_bytes(
                    {
                        key: value
                        for key, value in record.items()
                        if key != "record_sha256"
                    }
                )
            ).hexdigest()
        path.write_bytes(canonical_json_bytes(record))
    with pytest.raises(M1CommissioningPersistenceError):
        _core(runtime, adapter, key="fresh-key")


@WINDOWS
def test_physical_header_cannot_be_reinterpreted_and_rehearsal_source_is_required(
    tmp_path: Path,
) -> None:
    runtime, adapter = _runtime(tmp_path)
    physical_id = "rehearsal-" + "e" * 32
    runtime.create_session(physical_id, created_at_ns=3000)
    assert runtime.session_snapshot(physical_id).header.mode == "PHYSICAL_DIAGNOSTIC"
    with pytest.raises(M1CommissioningPersistenceError, match="physical diagnostic"):
        adapter.snapshot(physical_id)
    with pytest.raises(PhysicalOnboardingM1Error, match="REHEARSAL"):
        with runtime.rehearsal_transaction(physical_id):
            pytest.fail("physical header admitted")
    with pytest.raises(PhysicalOnboardingM1Error, match="domain-separated"):
        runtime.create_session(
            "rehearsal-" + "f" * 32, mode="REHEARSAL", workspace_source_sha256="f" * 64
        )
    with pytest.raises(M1CommissioningPersistenceError, match="domain-separated"):
        M1CommissioningPersistence(
            runtime, workspace_source_sha256="f" * 64, admission_facts=_facts
        )


@WINDOWS
def test_exact_device_os_lease_order_without_any_device_access(tmp_path: Path) -> None:
    runtime, adapter = _runtime(tmp_path)
    leases = (
        LeaseSpec(LeaseLevel.CELL, CELL),
        LeaseSpec(LeaseLevel.SESSION, SESSION),
        LeaseSpec(LeaseLevel.CAMERA, CELL),
        LeaseSpec(LeaseLevel.ARM_CONTROLLER, CELL),
    )
    with adapter.transaction(leases) as tx:
        assert tx.held_leases == leases
    with pytest.raises(PhysicalOnboardingM1Error, match="ordered"):
        with adapter.transaction((*leases[:2], *reversed(leases[2:]))):
            pytest.fail("reversed device order admitted")
    assert runtime.verify(SESSION).attempt_event_count == 0


@WINDOWS
def test_same_scope_evidence_change_cannot_use_cached_admission(tmp_path: Path) -> None:
    runtime, adapter = _runtime(tmp_path)
    core, worker, request = _core(runtime, adapter)
    permit = core.prepare(request)
    admission = permit.admission
    binding = AttemptBinding(
        permit.attempt_id,
        SESSION,
        admission.stage.value,
        permit.registration.effect_class,
        permit.registration.action_id,
        permit.permit_sha256,
        admission.source_binding_sha256,
        admission.stage_plan_sha256,
        admission.journal_head_sha256,
        admission.evidence_inventory_sha256,
        time.time_ns(),
    )
    with adapter.transaction(
        (LeaseSpec(LeaseLevel.CELL, CELL), LeaseSpec(LeaseLevel.SESSION, SESSION))
    ) as tx:
        assert tx.read_admission(request) == admission
        tx.store_evidence(
            FIRST,
            b'{"new_reviewed_fact":true}',
            label="new synthetic evidence",
            media_type="application/json",
            captured_at_ns=2002,
            expected_head_sha256=admission.journal_head_sha256,
        )
        with pytest.raises(M1CommissioningPersistenceError, match="freshly read"):
            tx.begin_intent(binding, permit)
    assert runtime.verify(SESSION).attempt_event_count == 0
    assert not _records(runtime).exists()
    assert worker.calls == 0


@WINDOWS
def test_adapter_constructor_does_not_read_or_write_store(
    tmp_path: Path, monkeypatch: pytest.MonkeyPatch
) -> None:
    runtime, _ = _runtime(tmp_path)

    def forbidden(*args: Any, **kwargs: Any) -> None:
        pytest.fail("inert adapter constructor performed store I/O")

    monkeypatch.setattr(PhysicalOnboardingM1Runtime, "verify", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    M1CommissioningPersistence(
        runtime, workspace_source_sha256=SOURCE, admission_facts=_facts
    )
