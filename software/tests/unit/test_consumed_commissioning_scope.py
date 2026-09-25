"""Coordinator protocol tests only; no devices, native process or real storage."""

from dataclasses import replace
from threading import Event

import pytest

import rocell.application.cell_commissioning_coordinator as core
from rocell.application.consumed_commissioning_scope import ConsumedCommissioningScope
from rocell.application.physical_onboarding import PhysicalOnboardingStage as Stage
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.safety.effects import EffectCertainty, EffectClass
from test_commissioning_coordinator import _components, InMemoryProtocolStore


class RetainingProtocolStore(InMemoryProtocolStore):
    def assert_consumed_permit(self, permit):
        assert (
            self.held_leases
            and self.attempts[permit.attempt_id] is AttemptState.EFFECT_ARMED
        )
        assert self.trace.count("ACKNOWLEDGED") == 0
        self.trace.append("ACKNOWLEDGED")

    def revalidate_consumed_permit(self, permit):
        assert (
            self.held_leases
            and self.attempts[permit.attempt_id] is AttemptState.EFFECT_ARMED
        )
        assert self.trace.count("ACKNOWLEDGED") == 1
        self.trace.append("CURRENT_SCOPE_REVALIDATED")
        if self.fail == "revalidate":
            raise core.CommissioningCoordinatorError("Injected stale evidence")

    def retain_campaign_evidence(self, permit, evidence):
        assert self.trace.count("ACKNOWLEDGED") == 1
        self.trace.append("FULL_BYTES_RETAINED")


class ScopedWorker:
    worker_executable_sha256 = "b" * 64

    def __init__(self, composition, store, clock, fault=None):
        self.composition, self.store, self.clock, self.fault = (
            composition,
            store,
            clock,
            fault,
        )
        self.calls = 0
        self.saved = None

    def run_scoped_campaign(self, permit, *, deadline_ns, cancellation, authorization):
        self.calls += 1
        self.saved = authorization
        self.store.trace.append("WORKER_ENTERED")
        if self.fault != "no-ack":
            authorization.acknowledge(permit)
        if self.fault == "duplicate-ack":
            authorization.acknowledge(permit)
        if self.fault == "cancel":
            cancellation.set()
        if self.fault == "deadline":
            self.clock.now = deadline_ns
        if self.fault == "close":
            authorization.close_scope()
        if self.fault == "retained-revalidation-failure":
            self.store.fail = "revalidate"
            with pytest.raises(core.CommissioningCoordinatorError):
                authorization.revalidate(permit)
        elif self.fault not in {"no-check", "no-ack"}:
            authorization.revalidate(permit)
        if self.fault == "check-flood":
            for _ in range(8):
                authorization.revalidate(permit)
        artifact = core.CampaignEvidence(
            "unit.scoped.v1",
            "no-device-protocol-only",
            b"actual unit-test protocol bytes",
        )
        receipt = core.WorkerReceipt(
            permit.attempt_id,
            permit.permit_sha256,
            self.worker_executable_sha256,
            permit.admission.selected_identity_sha256,
            EffectCertainty.CONFIRMED,
            True,
            core.ObservedPowerState.UNKNOWN,
            0,
            0,
            0,
            0,
            0,
            len(artifact.payload),
            (artifact.payload_sha256,),
            self.composition,
        )
        if self.fault == "invent-power":
            receipt = replace(
                receipt, final_power_state=core.ObservedPowerState.DEENERGIZED
            )
        if self.fault == "device-count":
            receipt = replace(receipt, opens=1)
        if self.fault == "wrong-bytes":
            receipt = replace(receipt, output_bytes=1)
        if self.fault == "wrong-domain":
            receipt = replace(receipt, composition="UNKNOWN")
        return core.RetainedCampaignExecution(receipt, (artifact,))


def test_revoked_scope_retains_returned_failure_evidence_without_known_completion():
    coordinator, store, worker, _, request, _ = components(
        fault="retained-revalidation-failure"
    )
    result = coordinator.execute(coordinator.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert result.quarantine_latched is True
    assert store.trace.count("FULL_BYTES_RETAINED") == 1
    assert worker.calls == 1


def components(*, physical=False, fault=None):
    _, old, _, clock, request = _components()
    composition = (
        core.PHYSICAL_DIAGNOSTIC_COMPOSITION if physical else core.INCAPABLE_COMPOSITION
    )
    snapshot = replace(
        old.snapshot,
        stage=Stage.WORKSPACE_SOURCES,
        selected_identity_sha256=None,
        mode=(
            core.CommissioningMode.PHYSICAL_DIAGNOSTIC
            if physical
            else core.CommissioningMode.REHEARSAL
        ),
    )
    store = RetainingProtocolStore(snapshot)
    store.composition = composition
    worker = ScopedWorker(composition, store, clock, fault)
    registration = core.CampaignRegistration(
        "source-files",
        snapshot.stage,
        EffectClass.NO_DEVICE_IO,
        "scope-unit",
        worker.worker_executable_sha256,
        "9" * 64,
        (),
        core.CampaignBudget(1000, 1024, 0, 0, 0, 0, 0),
    )
    kind = (
        core.PhysicalDiagnosticPreflightCoordinator
        if physical
        else core.CellCommissioningCoordinator
    )
    coordinator = kind(
        persistence=store,
        registrations=(registration,),
        workers={registration.worker_id: worker},
        retained_campaign_actions=(registration.action_id,),
        scoped_campaign_actions=(registration.action_id,),
        monotonic_ns=clock,
    )
    request = replace(
        request,
        action_id=registration.action_id,
        expected_challenge_sha256=snapshot.challenge_sha256,
    )
    return coordinator, store, worker, clock, request, registration


@pytest.mark.parametrize("physical", [False, True])
def test_exact_acknowledgement_revalidation_retention_and_scope_close(physical):
    coordinator, store, worker, clock, request, registration = components(
        physical=physical
    )
    permit = coordinator.prepare(request)
    assert worker.calls == 0
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    assert (
        result.composition == worker.composition and result.physical_authority == "NONE"
    )
    assert store.trace.count("EFFECT_ARMED") == store.trace.count("ACKNOWLEDGED") == 1
    assert store.trace.count("CURRENT_SCOPE_REVALIDATED") == 1
    assert store.trace.index("FULL_BYTES_RETAINED") < store.trace.index("SEALED_KNOWN")
    assert store.snapshot.stage_state is V2StageState.WAITING_OPERATOR
    with pytest.raises(core.CommissioningCoordinatorError):
        worker.saved.revalidate(permit)
    assert coordinator.execute(permit) is result and worker.calls == 1


@pytest.mark.parametrize("physical", [False, True])
@pytest.mark.parametrize(
    "fault",
    [
        "no-ack",
        "no-check",
        "duplicate-ack",
        "cancel",
        "deadline",
        "close",
        "check-flood",
        "wrong-bytes",
        "wrong-domain",
        "device-count",
    ],
)
def test_worker_faults_quarantine_without_retry(physical, fault):
    coordinator, store, worker, clock, request, _ = components(
        physical=physical, fault=fault
    )
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert result.composition == worker.composition
    assert "SEALED_KNOWN" not in store.trace
    assert coordinator.execute(permit) is result and worker.calls == 1
    with pytest.raises(core.CommissioningCoordinatorError):
        worker.saved.acknowledge(permit)


def test_physical_no_io_cannot_invent_deenergized_observation():
    coordinator, store, worker, _, request, _ = components(
        physical=True, fault="invent-power"
    )
    result = coordinator.execute(coordinator.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert "NO_DEVICE_IO_CANNOT_OBSERVE_POWER_STATE" in result.reason_codes


def test_transaction_revalidation_failure_is_not_a_second_consumption():
    coordinator, store, worker, _, request, _ = components()
    store.fail = "revalidate"
    result = coordinator.execute(coordinator.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert store.trace.count("EFFECT_ARMED") == store.trace.count("ACKNOWLEDGED") == 1
    assert store.trace.count("CURRENT_SCOPE_REVALIDATED") == 1


@pytest.mark.parametrize(
    "mutate", ["lease", "permit", "cancel", "deadline", "false-result", "close"]
)
def test_after_callback_boundary_rechecked_and_failure_latched(mutate):
    coordinator, store, worker, clock, request, _ = components()
    original = store.assert_consumed_permit

    def bad(permit):
        original(permit)
        if mutate == "lease":
            store.held_leases = ()
        if mutate == "permit":
            object.__setattr__(permit, "expires_at_ns", permit.expires_at_ns + 1)
        if mutate == "cancel":
            worker.saved._cancel.set()
        if mutate == "deadline":
            clock.now = worker.saved._deadline
        if mutate == "close":
            worker.saved.close_scope()
        if mutate == "false-result":
            return False

    store.assert_consumed_permit = bad
    permit = coordinator.prepare(request)
    result = coordinator.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert "CURRENT_SCOPE_REVALIDATED" not in store.trace


@pytest.mark.parametrize(
    "field,value",
    [
        ("effect_class", EffectClass.READ_ONLY_OS_INVENTORY),
        ("stage", Stage.CAMERA_MODE_CONTROLS),
    ],
)
def test_physical_preflight_constructor_is_not_general_physical_release(field, value):
    _, store, worker, clock, _, registration = components(physical=True)
    changed = replace(registration, **{field: value})
    with pytest.raises(core.CommissioningCoordinatorError, match="NO_DEVICE_IO"):
        core.PhysicalDiagnosticPreflightCoordinator(
            persistence=store,
            registrations=(changed,),
            workers={changed.worker_id: worker},
            monotonic_ns=clock,
            retained_campaign_actions=(changed.action_id,),
            scoped_campaign_actions=(changed.action_id,),
        )
    assert worker.calls == 0 and not store.trace


def test_default_coordinator_cannot_admit_new_physical_domain():
    _, store, worker, clock, _, registration = components(physical=True)
    with pytest.raises(core.CommissioningCoordinatorError, match="physical M1"):
        core.CellCommissioningCoordinator(
            persistence=store,
            registrations=(registration,),
            workers={registration.worker_id: worker},
        )


def test_physical_preflight_refuses_unretained_worker():
    _, store, worker, clock, _, registration = components(physical=True)
    with pytest.raises(core.CommissioningCoordinatorError, match="full retained"):
        core.PhysicalDiagnosticPreflightCoordinator(
            persistence=store,
            registrations=(registration,),
            workers={registration.worker_id: worker},
        )


def test_scoped_deadline_cannot_outlive_original_permit_after_slow_consume():
    coordinator, store, worker, clock, request, _ = components()
    original = store.consume_permit

    def slow(permit):
        original(permit)
        clock.now = permit.expires_at_ns - 1

    store.consume_permit = slow
    result = coordinator.execute(coordinator.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert worker.calls == 0


def test_physical_preflight_preserves_composition_on_pre_effect_cancel():
    coordinator, store, worker, _, request, _ = components(physical=True)
    cancellation = Event()
    cancellation.set()
    result = coordinator.execute(
        coordinator.prepare(request), cancellation=cancellation
    )
    assert result.state is AttemptState.ABORTED_PRE_EFFECT
    assert result.composition == core.PHYSICAL_DIAGNOSTIC_COMPOSITION
    assert worker.calls == 0


@pytest.mark.parametrize("interrupt", [False, True])
def test_completed_context_rejection_retains_and_never_renews(interrupt):
    coordinator, store, worker, _, request, _ = components()
    original = worker.run_scoped_campaign
    failure = (
        KeyboardInterrupt("late modeled interrupt")
        if interrupt
        else ValueError("late modeled refusal")
    )

    def run(permit, **kwargs):
        returned = original(permit, **kwargs)
        scope = kwargs["authorization"]
        with pytest.raises(core.CommissioningCoordinatorError):
            scope.reject_completed_context(None)
        scope.reject_completed_context(failure)
        with pytest.raises(core.CommissioningCoordinatorError):
            scope.revalidate(permit)
        with pytest.raises(core.CommissioningCoordinatorError):
            scope.reject_completed_context(
                ValueError("cannot replace the first failure")
            )
        return returned

    worker.run_scoped_campaign = run
    permit = coordinator.prepare(request)
    if interrupt:
        with pytest.raises(KeyboardInterrupt) as caught:
            coordinator.execute(permit)
        assert caught.value is failure
    else:
        assert coordinator.execute(permit).state is AttemptState.SEALED_UNCERTAIN
    result = store.results[permit.attempt_id]
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert store.trace.index("FULL_BYTES_RETAINED") < store.trace.index(
        "QUARANTINE_LATCHED"
    )
    assert worker.calls == 1
