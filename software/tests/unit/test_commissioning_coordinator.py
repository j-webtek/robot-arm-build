"""Incapable protocol tests only: this store is not a durability adapter."""

from __future__ import annotations

from concurrent.futures import ThreadPoolExecutor
from contextlib import contextmanager
from dataclasses import replace
from threading import Event
from typing import Any

import pytest

import rocell.application.cell_commissioning_coordinator as core
from rocell.application.cell_commissioning_coordinator import (
    AdmissionSnapshot,
    AttemptResult,
    CampaignBudget,
    CampaignRegistration,
    CellCommissioningCoordinator,
    CommissioningCoordinatorError,
    CommissioningMode,
    EnergizationEnvelope,
    ExactOperationPermit,
    INCAPABLE_COMPOSITION,
    ObservedPowerState,
    RegisteredActionRequest,
    WorkerReceipt,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import AttemptBinding, AttemptState
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.safety.effects import EffectCertainty, EffectClass


class Clock:
    now = 1000000

    def __call__(self) -> int:
        return self.now


class InMemoryProtocolStore:
    composition = INCAPABLE_COMPOSITION

    def __init__(self, snapshot: AdmissionSnapshot) -> None:
        self.snapshot = snapshot
        self.trace: list[str] = []
        self.held_leases: tuple[LeaseSpec, ...] = ()
        self.envelope: EnergizationEnvelope | None = None
        self.attempts: dict[str, AttemptState] = {}
        self.request_keys: set[str] = set()
        self.used_envelopes: set[str] = set()
        self.results: dict[str, AttemptResult] = {}
        self.fail: str | None = None
        self.wrong_leases = False

    @contextmanager
    def transaction(self, leases: tuple[LeaseSpec, ...]) -> Any:
        self.trace.append("LEASES_ACQUIRED")
        self.held_leases = tuple(reversed(leases)) if self.wrong_leases else leases
        try:
            yield self
        finally:
            self.trace.append("LEASES_RELEASED")
            self.held_leases = ()

    def read_admission(self, request: RegisteredActionRequest) -> AdmissionSnapshot:
        self.trace.append("ADMISSION_RECHECKED")
        return self.snapshot

    def read_envelope(
        self, request: RegisteredActionRequest
    ) -> EnergizationEnvelope | None:
        return self.envelope

    def begin_intent(
        self, binding: AttemptBinding, permit: ExactOperationPermit
    ) -> None:
        assert self.held_leases
        self.trace.append("INTENT_DURABLE")
        if permit.request.request_key in self.request_keys:
            raise CommissioningCoordinatorError(
                "request already consumed cell-globally"
            )
        if permit.envelope and permit.envelope.envelope_id in self.used_envelopes:
            raise CommissioningCoordinatorError(
                "energy envelope already consumed cell-globally"
            )
        self.request_keys.add(permit.request.request_key)
        if permit.envelope:
            self.used_envelopes.add(permit.envelope.envelope_id)
        self.attempts[binding.attempt_id] = AttemptState.INTENT_DURABLE
        self.snapshot = replace(self.snapshot, unresolved_attempts=1)
        if self.fail == "INTENT_DURABLE":
            raise OSError("injected uncertain intent publication")

    def consume_permit(self, permit: ExactOperationPermit) -> None:
        assert self.attempts[permit.attempt_id] is AttemptState.INTENT_DURABLE
        self.attempts[permit.attempt_id] = AttemptState.EFFECT_ARMED
        self.trace.append("EFFECT_ARMED")
        if self.fail == "EFFECT_ARMED":
            raise OSError("injected ambiguous consume publication")

    def transition(
        self, attempt_id: str, state: AttemptState, receipt: WorkerReceipt | None
    ) -> None:
        self.trace.append(state.value)
        if self.fail == state.value:
            raise OSError("injected transition failure")
        self.attempts[attempt_id] = state
        if state in {AttemptState.SEALED_KNOWN, AttemptState.ABORTED_PRE_EFFECT}:
            self.snapshot = replace(self.snapshot, unresolved_attempts=0)

    def retain_result(self, result: AttemptResult) -> None:
        self.trace.append("RESULT_RETAINED")
        if self.fail == "RESULT_RETAINED":
            raise OSError("injected evidence publication failure")
        self.results[result.attempt_id] = result

    def seal_uncertain(self, attempt_id: str, reason_codes: tuple[str, ...]) -> None:
        self.trace.append("QUARANTINE_LATCHED")
        if self.fail == "QUARANTINE_LATCHED":
            raise OSError("injected quarantine publication failure")
        self.attempts[attempt_id] = AttemptState.SEALED_UNCERTAIN
        self.snapshot = replace(
            self.snapshot, quarantine_latched=True, unresolved_attempts=1
        )


class IncapableWorker:
    composition = INCAPABLE_COMPOSITION
    worker_executable_sha256 = "b" * 64

    def __init__(self, store: InMemoryProtocolStore) -> None:
        self.store = store
        self.calls = 0
        self.fault: str | None = None
        self.mutate_receipt: dict[str, Any] = {}
        self.clock: Clock | None = None

    def run_campaign(
        self, permit: ExactOperationPermit, *, deadline_ns: int, cancellation: Event
    ) -> WorkerReceipt:
        assert self.store.attempts[permit.attempt_id] is AttemptState.EFFECT_ARMED
        assert self.store.held_leases
        self.calls += 1
        self.store.trace.append("INCAPABLE_WORKER_DISPATCHED")
        if self.fault == "raise":
            raise TimeoutError("injected worker failure")
        if self.fault == "cancel":
            cancellation.set()
        if self.fault == "deadline":
            assert self.clock
            self.clock.now = deadline_ns + 1
        receipt = WorkerReceipt(
            attempt_id=permit.attempt_id,
            permit_sha256=permit.permit_sha256,
            worker_executable_sha256=self.worker_executable_sha256,
            selected_identity_sha256=permit.admission.selected_identity_sha256,
            effect_certainty=EffectCertainty.CONFIRMED,
            cleanup_confirmed=True,
            final_power_state=ObservedPowerState.DEENERGIZED,
            opens=1,
            reads=1,
            writes=0,
            frames=(
                0
                if permit.registration.effect_class is EffectClass.SERIAL_OPEN_OR_WRITE
                else 1
            ),
            closes=1,
            output_bytes=512,
            evidence_sha256s=("c" * 64,),
        )
        return replace(receipt, **self.mutate_receipt)


def test_external_cancellation_is_shared_before_dispatch() -> None:
    coordinator, store, worker, clock, request = _components()
    permit = coordinator.prepare(request)
    cancellation = Event()
    cancellation.set()
    result = coordinator.execute(permit, cancellation=cancellation)
    assert result.state is AttemptState.ABORTED_PRE_EFFECT
    assert worker.calls == 0
    assert coordinator.execute(permit, cancellation=Event()) == result


def test_external_cancellation_during_cleanup_prevents_known_seal() -> None:
    coordinator, store, worker, clock, request = _components()
    permit = coordinator.prepare(request)
    cancellation = Event()
    original = store.transition

    def transition(
        attempt_id: str, state: AttemptState, receipt: WorkerReceipt | None
    ) -> None:
        original(attempt_id, state, receipt)
        if state is AttemptState.CLEANUP_CONFIRMED:
            cancellation.set()

    store.transition = transition
    result = coordinator.execute(permit, cancellation=cancellation)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert result.quarantine_latched
    assert worker.calls == 1
    assert "SEALED_KNOWN" not in store.trace


def _components(*, serial: bool = False) -> tuple[
    CellCommissioningCoordinator,
    InMemoryProtocolStore,
    IncapableWorker,
    Clock,
    RegisteredActionRequest,
]:
    snapshot = AdmissionSnapshot(
        cell_id="CELL-A",
        session_id="session-1",
        mode=CommissioningMode.REHEARSAL,
        stage=(
            PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION
            if serial
            else PhysicalOnboardingStage.CAMERA_MODE_CONTROLS
        ),
        stage_state=V2StageState.WAITING_OPERATOR,
        stage_revision=1,
        source_binding_sha256="1" * 64,
        stage_plan_sha256="2" * 64,
        journal_head_sha256="3" * 64,
        global_attempt_head_sha256="4" * 64,
        quarantine_head_sha256="5" * 64,
        evidence_inventory_sha256="6" * 64,
        hazard_assessment_sha256="a" * 64,
        durability_qualification_sha256="d" * 64,
        configuration_epoch_hashes=("7" * 64,) * 8,
        selected_identity_sha256="8" * 64,
        quarantine_latched=False,
        unresolved_attempts=0,
    )
    store = InMemoryProtocolStore(snapshot)
    worker = IncapableWorker(store)
    registration = CampaignRegistration(
        action_id="serial-feedback" if serial else "camera-preview",
        stage=snapshot.stage,
        effect_class=(
            EffectClass.SERIAL_OPEN_OR_WRITE
            if serial
            else EffectClass.BOUNDED_CAMERA_CAMPAIGN
        ),
        worker_id="incapable-worker",
        worker_executable_sha256=worker.worker_executable_sha256,
        operation_sha256="9" * 64,
        resources=(LeaseLevel.ARM_CONTROLLER,) if serial else (LeaseLevel.CAMERA,),
        budget=CampaignBudget(
            1000, 1024, 1, 1, 1 if serial else 0, 0 if serial else 1, 1
        ),
    )
    clock = Clock()
    worker.clock = clock
    coordinator = CellCommissioningCoordinator(
        persistence=store,
        registrations=(registration,),
        workers={registration.worker_id: worker},
        monotonic_ns=clock,
    )
    request = RegisteredActionRequest(
        "CELL-A",
        "session-1",
        registration.action_id,
        "request-1",
        snapshot.challenge_sha256,
    )
    if serial:
        store.envelope = EnergizationEnvelope(
            envelope_id="power-1",
            operation_sha256=registration.operation_sha256,
            power_topology_sha256="a" * 64,
            safety_review_sha256="b" * 64,
            installed_object_inventory_sha256="c" * 64,
            configuration_epoch_vector_sha256=core._hash(
                snapshot.configuration_epoch_hashes
            ),
            operator_id="operator-1",
            observer_id="observer-2",
            issued_at_ns=clock.now,
            expires_at_ns=clock.now + core.MAX_PERMIT_TTL_NS,
        )
    return coordinator, store, worker, clock, request


def test_constructor_and_prepare_never_dispatch_or_publish_intent() -> None:
    coordinator, store, worker, _, request = _components()
    assert store.trace == []
    assert worker.calls == 0
    permit = coordinator.prepare(request)
    assert worker.calls == 0 and store.attempts == {}
    assert store.trace == ["LEASES_ACQUIRED", "ADMISSION_RECHECKED", "LEASES_RELEASED"]
    assert coordinator.prepare(request) == permit
    assert permit.admission.mode is CommissioningMode.REHEARSAL
    assert len(permit.nonce) == len(permit.permit_sha256) == 64


def test_one_attempt_is_armed_before_one_worker_and_retains_before_known_seal() -> None:
    coordinator, store, worker, _, request = _components()
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    assert result.physical_authority == "NONE"
    assert result.composition == INCAPABLE_COMPOSITION
    assert worker.calls == 1
    tail = store.trace[3:]
    assert tail == [
        "LEASES_ACQUIRED",
        "ADMISSION_RECHECKED",
        "INTENT_DURABLE",
        "EFFECT_ARMED",
        "INCAPABLE_WORKER_DISPATCHED",
        "EFFECT_OBSERVED",
        "CLEANUP_CONFIRMED",
        "RESULT_RETAINED",
        "SEALED_KNOWN",
        "LEASES_RELEASED",
    ]
    assert coordinator.execute(permit) is result
    assert worker.calls == 1


def test_simultaneous_duplicate_execute_dispatches_once() -> None:
    coordinator, _, worker, _, request = _components()
    permit = coordinator.prepare(request)
    with ThreadPoolExecutor(max_workers=2) as pool:
        first = pool.submit(coordinator.execute, permit)
        second = pool.submit(coordinator.execute, permit)
        assert first.result() == second.result()
    assert worker.calls == 1


@pytest.mark.parametrize(
    "field,value",
    [
        ("source_binding_sha256", "a" * 64),
        ("stage_revision", 2),
        ("selected_identity_sha256", "b" * 64),
        ("journal_head_sha256", "c" * 64),
        ("global_attempt_head_sha256", "d" * 64),
        ("quarantine_head_sha256", "e" * 64),
        ("evidence_inventory_sha256", "f" * 64),
        ("configuration_epoch_hashes", ("9" * 64,) * 8),
        ("hazard_assessment_sha256", "e" * 64),
        ("durability_qualification_sha256", "f" * 64),
    ],
)
def test_stale_permit_challenge_rejected_without_intent_or_worker(
    field: str, value: Any
) -> None:
    coordinator, store, worker, _, request = _components()
    permit = coordinator.prepare(request)
    store.snapshot = replace(store.snapshot, **{field: value})
    with pytest.raises(CommissioningCoordinatorError, match="stale"):
        coordinator.execute(permit)
    assert not store.attempts and worker.calls == 0


def test_wrong_lease_order_blocks_prepare() -> None:
    coordinator, store, worker, _, request = _components()
    store.wrong_leases = True
    with pytest.raises(CommissioningCoordinatorError, match="ordered leases"):
        coordinator.prepare(request)
    assert worker.calls == 0


def test_physical_mode_is_explicitly_unqualified() -> None:
    coordinator, store, worker, _, request = _components()
    store.snapshot = replace(store.snapshot, mode=CommissioningMode.PHYSICAL_DIAGNOSTIC)
    request = replace(
        request, expected_challenge_sha256=store.snapshot.challenge_sha256
    )
    with pytest.raises(CommissioningCoordinatorError, match="physical M1"):
        coordinator.prepare(request)
    assert worker.calls == 0


def test_reviewed_prerequisite_blockers_cannot_be_bypassed_by_fresh_challenge() -> None:
    coordinator, store, worker, _, request = _components()
    store.snapshot = replace(
        store.snapshot, open_blocker_ids=("CAMERA_ARCHITECTURE_HOLD",)
    )
    request = replace(
        request, expected_challenge_sha256=store.snapshot.challenge_sha256
    )
    with pytest.raises(CommissioningCoordinatorError, match="prerequisite blockers"):
        coordinator.prepare(request)
    assert worker.calls == 0


def test_expiry_substitution_and_worker_hash_drift_do_not_dispatch() -> None:
    coordinator, _, worker, clock, request = _components()
    permit = coordinator.prepare(request)
    with pytest.raises(CommissioningCoordinatorError, match="substituted"):
        coordinator.execute(replace(permit, attempt_id="different-attempt"))
    worker.worker_executable_sha256 = "a" * 64
    with pytest.raises(CommissioningCoordinatorError, match="worker identity"):
        coordinator.execute(permit)
    worker.worker_executable_sha256 = "b" * 64
    clock.now = permit.expires_at_ns
    with pytest.raises(CommissioningCoordinatorError, match="expired"):
        coordinator.execute(permit)
    assert worker.calls == 0


def test_cancel_before_arm_has_known_zero_dispatch_abort() -> None:
    coordinator, store, worker, _, request = _components()
    permit = coordinator.prepare(request)
    coordinator.cancel(permit)
    result = coordinator.execute(permit)
    assert result.state is AttemptState.ABORTED_PRE_EFFECT
    assert not result.quarantine_latched
    assert "EFFECT_ARMED" not in store.trace
    assert worker.calls == 0


@pytest.mark.parametrize("fault", ["raise", "cancel", "deadline"])
def test_worker_exception_timeout_and_cancellation_latch_global_uncertainty(
    fault: str,
) -> None:
    coordinator, store, worker, _, request = _components()
    worker.fault = fault
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert store.snapshot.quarantine_latched and worker.calls == 1
    assert coordinator.execute(permit) is result
    with pytest.raises(CommissioningCoordinatorError, match="held"):
        coordinator.prepare(replace(request, request_key="new-request"))


@pytest.mark.parametrize(
    "mutation",
    [
        {"cleanup_confirmed": False},
        {"effect_certainty": EffectCertainty.UNCERTAIN},
        {"selected_identity_sha256": "a" * 64},
        {"output_bytes": 1025},
        {"writes": 1},
        {"opens": True},
        {"frames": -1},
        {"evidence_sha256s": ("bad",)},
        {"composition": "PHYSICAL"},
        {"attempt_id": "another-attempt"},
    ],
)
def test_receipt_binding_accounting_and_cleanup_faults_are_uncertain(
    mutation: dict[str, Any],
) -> None:
    coordinator, store, worker, _, request = _components()
    worker.mutate_receipt = mutation
    result = coordinator.execute(coordinator.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert store.snapshot.quarantine_latched and worker.calls == 1


@pytest.mark.parametrize(
    "boundary,expected_calls",
    [
        ("INTENT_DURABLE", 0),
        ("EFFECT_ARMED", 0),
        ("EFFECT_OBSERVED", 1),
        ("CLEANUP_CONFIRMED", 1),
        ("SEALED_KNOWN", 1),
    ],
)
def test_publication_failure_never_replays_worker(
    boundary: str, expected_calls: int
) -> None:
    coordinator, store, worker, _, request = _components()
    store.fail = boundary
    permit = coordinator.prepare(request)
    if boundary == "INTENT_DURABLE":
        with pytest.raises(OSError):
            coordinator.execute(permit)
    else:
        result = coordinator.execute(permit)
        assert result.state is AttemptState.SEALED_UNCERTAIN
        assert store.snapshot.quarantine_latched
    assert worker.calls == expected_calls
    with pytest.raises(CommissioningCoordinatorError, match="held"):
        coordinator.prepare(replace(request, request_key="new-request"))


def test_quarantine_publication_failure_is_not_retried() -> None:
    coordinator, store, worker, _, request = _components()
    worker.fault = "raise"
    store.fail = "QUARANTINE_LATCHED"
    permit = coordinator.prepare(request)
    with pytest.raises(OSError):
        coordinator.execute(permit)
    assert store.trace.count("QUARANTINE_LATCHED") == 1
    with pytest.raises(CommissioningCoordinatorError, match="held"):
        coordinator.execute(permit)
    assert worker.calls == 1


def test_serial_requires_new_exact_energy_envelope_and_final_power_off() -> None:
    coordinator, store, worker, _, request = _components(serial=True)
    envelope = store.envelope
    store.envelope = None
    with pytest.raises(CommissioningCoordinatorError, match="energization envelope"):
        coordinator.prepare(request)
    store.envelope = envelope
    worker.mutate_receipt = {
        "writes": 1,
        "final_power_state": ObservedPowerState.UNKNOWN,
    }
    result = coordinator.execute(coordinator.prepare(request))
    assert "FINAL_DEENERGIZATION_UNCONFIRMED" in result.reason_codes
    assert result.quarantine_latched


def test_one_energy_envelope_cannot_authorize_second_campaign() -> None:
    coordinator, store, worker, _, request = _components(serial=True)
    worker.mutate_receipt = {"writes": 1}
    first = coordinator.execute(coordinator.prepare(request))
    assert first.state is AttemptState.SEALED_KNOWN
    second = coordinator.prepare(replace(request, request_key="request-2"))
    with pytest.raises(
        CommissioningCoordinatorError, match="energy envelope already consumed"
    ):
        coordinator.execute(second)
    assert worker.calls == 1


def test_restart_never_accepts_old_process_permit_or_clears_global_quarantine() -> None:
    coordinator, store, worker, clock, request = _components()
    permit = coordinator.prepare(request)
    worker.fault = "raise"
    coordinator.execute(permit)
    restarted = CellCommissioningCoordinator(
        persistence=store,
        registrations=(permit.registration,),
        workers={permit.registration.worker_id: worker},
        monotonic_ns=clock,
    )
    with pytest.raises(CommissioningCoordinatorError, match="restarted"):
        restarted.execute(permit)
    new_request = replace(
        request,
        request_key="request-2",
        expected_challenge_sha256=store.snapshot.challenge_sha256,
    )
    with pytest.raises(CommissioningCoordinatorError, match="quarantine"):
        restarted.prepare(new_request)
    assert worker.calls == 1


def test_closed_registry_rejects_escalation_unknown_actions_and_extra_workers() -> None:
    coordinator, store, worker, clock, request = _components()
    permit = coordinator.prepare(request)
    with pytest.raises(CommissioningCoordinatorError, match="not registered"):
        coordinator.prepare(replace(request, action_id="raw-motion"))
    with pytest.raises(CommissioningCoordinatorError, match="resource leases"):
        replace(permit.registration, effect_class=EffectClass.SERIAL_OPEN_OR_WRITE)
    with pytest.raises(CommissioningCoordinatorError, match="unregistered worker"):
        CellCommissioningCoordinator(
            persistence=store,
            registrations=(permit.registration,),
            workers={permit.registration.worker_id: worker, "hidden-worker": worker},
            monotonic_ns=clock,
        )
    with pytest.raises(CommissioningCoordinatorError, match="another action"):
        coordinator.prepare(replace(request, expected_challenge_sha256="f" * 64))
    with pytest.raises(CommissioningCoordinatorError, match="device-I/O budget"):
        replace(
            permit.registration, effect_class=EffectClass.NO_DEVICE_IO, resources=()
        )


def test_serial_envelope_must_cover_entire_bounded_campaign() -> None:
    coordinator, store, worker, clock, request = _components(serial=True)
    assert store.envelope is not None
    store.envelope = replace(store.envelope, expires_at_ns=clock.now + 1)
    permit = coordinator.prepare(request)
    with pytest.raises(
        CommissioningCoordinatorError, match="cover the bounded campaign"
    ):
        coordinator.execute(permit)
    assert worker.calls == 0 and store.attempts == {}


def test_clock_regression_and_permit_budget_fail_closed(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    coordinator, _, worker, clock, request = _components()
    permit = coordinator.prepare(request)
    clock.now -= 1
    with pytest.raises(CommissioningCoordinatorError, match="clock regressed"):
        coordinator.execute(permit)
    assert worker.calls == 0
    other, _, _, _, other_request = _components()
    monkeypatch.setattr(core, "MAX_PREPARED_PERMITS", 0)
    with pytest.raises(CommissioningCoordinatorError, match="budget exhausted"):
        other.prepare(other_request)
