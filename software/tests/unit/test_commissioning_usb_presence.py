"""Closed presence-domain protocol tests, with no process or hardware access.

The store and workers are in-process incapable doubles. A known modeled
receipt is not a native observation, a physical absence, or qualification.
"""

from contextlib import contextmanager
from dataclasses import asdict, replace
import json
import subprocess
from threading import Event

import pytest

from rocell.application.cell_commissioning_coordinator import (
    AdmissionSnapshot,
    CampaignBudget,
    CommissioningCoordinatorError,
    EnergizationEnvelope,
    INCAPABLE_COMPOSITION,
    MAX_PERMIT_TTL_NS,
    PHYSICAL_CAMERA_COMPOSITION,
    PHYSICAL_DIAGNOSTIC_COMPOSITION,
    PHYSICAL_USB_IDENTITY_COMPOSITION,
    PHYSICAL_USB_PRESENCE_COMPOSITION,
    PhysicalUsbIdentityCoordinator,
    PhysicalUsbPresenceCoordinator,
    RegisteredActionRequest,
    RetainedCampaignExecution,
    RetainedUncertainCampaignExecution,
    USB_PRESENCE_ACTION_ID,
    USB_PRESENCE_MINIMUM_WINDOW_NS,
    USB_PRESENCE_WORKER_ID,
    UsbIdentityAdmissionSnapshot,
    UsbPresenceAdmissionSnapshot,
)
from rocell.application.commissioning_camera_persistence import (
    decode_physical_camera_permit,
)
from rocell.application.commissioning_m1_persistence import _decode_permit
from rocell.application.commissioning_physical_persistence import (
    decode_physical_diagnostic_permit,
)
from rocell.application.commissioning_usb_identity_persistence import (
    decode_physical_usb_identity_permit,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_leases import LeaseLevel
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.usb_presence_stage_policy import usb_presence_stage_policy
from rocell.safety.effects import EffectClass

from test_commissioning_coordinator import Clock
from test_physical_camera_coordinator import (
    CELL,
    SESSION,
    LEASES,
    PAYLOAD,
    CameraProtocolStore,
    IncapableCameraContractWorker,
    admission,
    registration,
)


POLICY = usb_presence_stage_policy()
PHASE = "9" * 64
STAGE = PhysicalOnboardingStage.CAMERA_IDENTITY
BUDGET = CampaignBudget(25000, 128 * 1024, 0, 4, 0, 0, 0)


@pytest.fixture(autouse=True)
def no_process_or_native_call(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail(
            "presence coordinator contract may not create a process or query OS"
        )

    monkeypatch.setattr(subprocess, "Popen", denied)
    import ctypes

    if hasattr(ctypes, "WinDLL"):
        monkeypatch.setattr(ctypes, "WinDLL", denied)


def presence_registration(**changes):
    return replace(
        registration(
            action_id=USB_PRESENCE_ACTION_ID,
            worker_id=USB_PRESENCE_WORKER_ID,
            stage=STAGE,
            budget=BUDGET,
        ),
        **changes,
    )


def presence_snapshot(**changes):
    return replace(
        UsbPresenceAdmissionSnapshot(
            **asdict(admission(stage=STAGE, selected_identity_sha256=PHASE)),
            usb_presence_policy_sha256=POLICY.sha256,
            phase_binding_sha256=PHASE,
            runtime_review_sha256="7" * 64,
        ),
        **changes,
    )


class PresenceProtocolStore(CameraProtocolStore):
    composition = PHYSICAL_USB_PRESENCE_COMPOSITION


class IncapablePresenceWorker(IncapableCameraContractWorker):
    composition = PHYSICAL_USB_PRESENCE_COMPOSITION

    def __init__(self, *, fault=None):
        super().__init__(fault=fault)
        self.deadlines = []
        self.receipt_changes = {}

    def run_scoped_campaign(self, permit, **kwargs):
        self.deadlines.append(kwargs["deadline_ns"])
        execution = super().run_scoped_campaign(permit, **kwargs)
        if self.fault in {"unknown-counts", "cancel", "omit-ack"}:
            return RetainedUncertainCampaignExecution(
                execution.evidence, ("USB_PRESENCE_ACCOUNTING_UNKNOWN",)
            )
        return RetainedCampaignExecution(
            replace(execution.receipt, **self.receipt_changes), execution.evidence
        )


def presence_core(store, worker=None, *, clock=None, registered=None, **changes):
    worker = worker or IncapablePresenceWorker()
    item = registered or presence_registration()
    arguments = dict(
        persistence=store,
        registrations=(item,),
        workers={item.worker_id: worker},
        retained_campaign_actions=(item.action_id,),
        scoped_campaign_actions=(item.action_id,),
        usb_presence_policy_sha256=POLICY.sha256,
        monotonic_ns=clock or Clock(),
    )
    arguments.update(changes)
    return PhysicalUsbPresenceCoordinator(**arguments)


def components(*, fault=None):
    store = PresenceProtocolStore(presence_snapshot())
    worker = IncapablePresenceWorker(fault=fault)
    clock = Clock()
    core = presence_core(store, worker, clock=clock)
    request = RegisteredActionRequest(
        CELL,
        SESSION,
        USB_PRESENCE_ACTION_ID,
        "presence-one",
        store.snapshot.challenge_sha256,
    )
    return core, store, worker, clock, request


def test_closed_domain_is_inert_and_matches_independent_policy_and_runtime():
    from rocell.providers.windows.usb_presence_registration import REQUIRED_LIFETIME_NS

    core, store, worker, clock, request = components()
    assert not store.trace and worker.calls == 0
    permit = core.prepare(request)
    assert not store.attempts and worker.calls == 0 and permit.envelope is None
    assert type(permit.admission) is UsbPresenceAdmissionSnapshot
    assert permit.admission.selected_identity_sha256 == PHASE
    assert permit.admission.phase_binding_sha256 == PHASE
    assert permit.admission.usb_presence_policy_sha256 == POLICY.sha256
    assert permit.admission.runtime_review_sha256 == "7" * 64
    assert permit.registration.budget == BUDGET
    assert USB_PRESENCE_MINIMUM_WINDOW_NS == REQUIRED_LIFETIME_NS == 15_000_000_000
    policy = POLICY.to_dict()
    assert policy["budget"] == asdict(BUDGET)
    assert policy["action_id"] == USB_PRESENCE_ACTION_ID
    assert policy["worker_id"] == USB_PRESENCE_WORKER_ID
    assert policy["composition"] == PHYSICAL_USB_PRESENCE_COMPOSITION
    assert permit.registration.resources == (LeaseLevel.CAMERA,)


def test_presence_snapshot_has_additive_hash_and_old_decoders_remain_closed():
    core, store, worker, clock, request = components()
    permit = core.prepare(request)
    data = asdict(permit.admission)
    del data["usb_presence_policy_sha256"], data["phase_binding_sha256"]
    del data["runtime_review_sha256"]
    old = AdmissionSnapshot(**data)
    assert old.challenge_sha256 != permit.admission.challenge_sha256
    wire = json.loads(canonical_json_bytes(asdict(permit)))
    for decoder in (
        _decode_permit,
        decode_physical_diagnostic_permit,
        decode_physical_camera_permit,
        decode_physical_usb_identity_permit,
    ):
        with pytest.raises((ValueError, RuntimeError)):
            decoder(wire)


@pytest.mark.parametrize(
    "changes",
    [
        {"action_id": "physical-native-usb-identity"},
        {"worker_id": "scoped-physical-native-usb-identity"},
        {"stage": PhysicalOnboardingStage.CAMERA_MODE_CONTROLS},
        {"stage": PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION},
        {"effect_class": EffectClass.READ_ONLY_OS_INVENTORY, "resources": ()},
        {"effect_class": EffectClass.NO_DEVICE_IO, "resources": ()},
        {"resources": ()},
        {"resources": (LeaseLevel.ARM_CONTROLLER,)},
        {"resources": (LeaseLevel.CAMERA, LeaseLevel.ARM_CONTROLLER)},
        *(
            {"budget": replace(BUDGET, **{field: value})}
            for field, value in (
                ("timeout_ms", 24999),
                ("timeout_ms", 25001),
                ("maximum_output_bytes", 128 * 1024 - 1),
                ("maximum_opens", 1),
                ("maximum_reads", 3),
                ("maximum_reads", 5),
                ("maximum_writes", 1),
                ("maximum_frames", 1),
                ("maximum_closes", 1),
            )
        ),
    ],
)
def test_exact_presence_registration_cannot_be_another_domain_or_budget(changes):
    with pytest.raises(CommissioningCoordinatorError):
        presence_core(
            PresenceProtocolStore(presence_snapshot()),
            registered=presence_registration(**changes),
        )


@pytest.mark.parametrize("missing", ["retained", "scoped", "method"])
def test_presence_requires_exact_retained_scoped_action(missing):
    worker = IncapablePresenceWorker()
    if missing == "method":
        worker.run_scoped_campaign = None
    with pytest.raises(CommissioningCoordinatorError):
        presence_core(
            PresenceProtocolStore(presence_snapshot()),
            worker,
            retained_campaign_actions=(
                () if missing == "retained" else (USB_PRESENCE_ACTION_ID,)
            ),
            scoped_campaign_actions=(
                () if missing != "method" else (USB_PRESENCE_ACTION_ID,)
            ),
        )


@pytest.mark.parametrize(
    "composition",
    [
        INCAPABLE_COMPOSITION,
        PHYSICAL_DIAGNOSTIC_COMPOSITION,
        PHYSICAL_CAMERA_COMPOSITION,
        PHYSICAL_USB_IDENTITY_COMPOSITION,
    ],
)
@pytest.mark.parametrize("target", ["store", "worker"])
def test_presence_rejects_other_domain_store_or_worker(composition, target):
    store, worker = (
        PresenceProtocolStore(presence_snapshot()),
        IncapablePresenceWorker(),
    )
    setattr(store if target == "store" else worker, "composition", composition)
    with pytest.raises(CommissioningCoordinatorError):
        presence_core(store, worker)


@pytest.mark.parametrize(
    "field",
    ["usb_presence_policy_sha256", "phase_binding_sha256", "runtime_review_sha256"],
)
@pytest.mark.parametrize("value", [None, True, "0" * 64, "e" * 63, "E" * 64])
def test_presence_snapshot_rejects_non_digest_fields(field, value):
    with pytest.raises(CommissioningCoordinatorError):
        presence_snapshot(**{field: value})


@pytest.mark.parametrize("value", [None, "8" * 64])
def test_presence_selected_identity_is_phase_not_previous_endpoint(value):
    with pytest.raises(CommissioningCoordinatorError, match="exact phase binding"):
        presence_snapshot(selected_identity_sha256=value)


def test_presence_policy_pin_is_independent_and_snapshot_type_is_exact():
    core, store, worker, clock, request = components()
    wrong_pin = presence_core(store, worker, usb_presence_policy_sha256="8" * 64)
    with pytest.raises(CommissioningCoordinatorError, match="pinned presence policy"):
        wrong_pin.prepare(request)
    for replacement in (
        admission(stage=STAGE),
        UsbIdentityAdmissionSnapshot(
            **asdict(admission(stage=STAGE)), usb_query_policy_sha256=POLICY.sha256
        ),
    ):
        store.snapshot = replacement
        request = replace(
            request, expected_challenge_sha256=replacement.challenge_sha256
        )
        with pytest.raises(CommissioningCoordinatorError, match="presence policy"):
            core.prepare(request)
    assert worker.calls == 0 and not store.attempts


def test_even_a_forged_frozen_snapshot_cannot_separate_phase_and_selected_identity():
    core, store, worker, clock, request = components()
    object.__setattr__(store.snapshot, "phase_binding_sha256", "8" * 64)
    request = replace(
        request, expected_challenge_sha256=store.snapshot.challenge_sha256
    )
    with pytest.raises(CommissioningCoordinatorError, match="exact phase binding"):
        core.prepare(request)
    assert worker.calls == 0 and not store.attempts


def test_presence_constructor_is_closed_and_cannot_supply_identity_policy_keyword():
    class UnregisteredPresence(PhysicalUsbPresenceCoordinator):
        pass

    with pytest.raises(CommissioningCoordinatorError, match="unregistered coordinator"):
        UnregisteredPresence(
            usb_presence_policy_sha256=POLICY.sha256,
            persistence=PresenceProtocolStore(presence_snapshot()),
            registrations=(),
            workers={},
        )
    with pytest.raises(CommissioningCoordinatorError):
        PhysicalUsbIdentityCoordinator(
            usb_query_policy_sha256=POLICY.sha256,
            persistence=PresenceProtocolStore(presence_snapshot()),
            registrations=(presence_registration(),),
            workers={},
        )
    with pytest.raises(CommissioningCoordinatorError):
        presence_core(
            PresenceProtocolStore(presence_snapshot()),
            usb_presence_policy_sha256="0" * 64,
        )


def test_known_modeled_receipt_is_retained_once_with_no_power_or_qualification():
    core, store, worker, clock, request = components()
    permit = core.prepare(request)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    assert result.composition == PHYSICAL_USB_PRESENCE_COMPOSITION
    assert result.physical_authority == "NONE" and not result.quarantine_latched
    assert result.receipt.final_power_state.value == "UNKNOWN"
    assert result.receipt.selected_identity_sha256 == PHASE
    assert store.evidence[0].payload == PAYLOAD
    assert store.trace.index("EFFECT_ARMED") < store.trace.index("ACKNOWLEDGED_ONCE")
    assert store.trace.index("FULL_EVIDENCE_RETAINED") < store.trace.index(
        "SEALED_KNOWN"
    )
    assert store.trace.count("CONSUMED_SCOPE_REVALIDATED") == 2
    assert store.held_leases == ()
    assert core.execute(permit) is result and worker.calls == 1
    with pytest.raises(CommissioningCoordinatorError):
        worker.authority.revalidate(permit)
    fresh = presence_core(store)
    with pytest.raises(CommissioningCoordinatorError, match="unknown, restarted"):
        fresh.execute(permit)


def test_presence_cannot_carry_an_energy_envelope():
    core, store, worker, clock, request = components()
    store.envelope = EnergizationEnvelope(
        "energy",
        *("a" * 64 for _ in range(5)),
        "operator",
        "observer",
        clock.now,
        clock.now + MAX_PERMIT_TTL_NS,
    )
    with pytest.raises(CommissioningCoordinatorError, match="non-power"):
        core.prepare(request)
    assert worker.calls == 0 and not store.attempts


@pytest.mark.parametrize(
    "field,value",
    [
        ("opens", 1),
        ("reads", 5),
        ("writes", 1),
        ("frames", 1),
        ("closes", 1),
        ("reads", True),
        ("reads", None),
        ("selected_identity_sha256", "8" * 64),
        ("cleanup_confirmed", False),
    ],
)
def test_bad_modeled_accounting_cannot_seal_known(field, value):
    core, store, worker, clock, request = components()
    worker.receipt_changes[field] = value
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert store.evidence[0].payload == PAYLOAD and worker.calls == 1
    assert "SEALED_KNOWN" not in store.trace


@pytest.mark.parametrize("fault", ["unknown-counts", "cancel"])
def test_unknown_original_effects_are_retained_without_a_zero_count_receipt(fault):
    core, store, worker, clock, request = components(fault=fault)
    permit = core.prepare(request)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.receipt is None
    assert "USB_PRESENCE_ACCOUNTING_UNKNOWN" in result.reason_codes
    if fault == "cancel":
        assert "CONSUMED_SCOPE_REVALIDATION_FAILED" in result.reason_codes
    assert store.evidence[0].payload == PAYLOAD
    assert store.trace.index("FULL_EVIDENCE_RETAINED") < store.trace.index(
        "QUARANTINE_LATCHED"
    )
    assert core.execute(permit) is result and worker.calls == 1


def test_unknown_evidence_without_consumed_acknowledgement_is_not_retained():
    core, store, worker, clock, request = components(fault="omit-ack")
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.receipt is None
    assert not store.evidence and worker.calls == 1


@pytest.mark.parametrize("fault", ["omit-check", "duplicate-ack", "power-claim"])
def test_scope_or_power_claim_faults_cannot_seal_known(fault):
    core, store, worker, clock, request = components(fault=fault)
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert "SEALED_KNOWN" not in store.trace


@pytest.mark.parametrize("delay", [6_000_000_000, 31_000_000_000])
def test_first_presence_issuance_follows_complete_read_and_lease_cleanup(
    monkeypatch, delay
):
    core, store, worker, clock, request = components()
    original = store.transaction
    before = clock.now

    @contextmanager
    def slow_read_scope(leases):
        assert leases == LEASES
        with original(leases) as tx:
            clock.now += delay
            yield tx
        clock.now += delay
        assert not core._permits and not store.attempts

    monkeypatch.setattr(store, "transaction", slow_read_scope)
    permit = core.prepare(request)
    assert permit.issued_at_ns == before + 2 * delay == clock.now
    assert (
        permit.expires_at_ns - permit.issued_at_ns
        == MAX_PERMIT_TTL_NS
        == 30_000_000_000
    )
    assert worker.calls == 0 and not store.attempts
    clock.now = permit.expires_at_ns + 1
    assert core.prepare(request) is permit
    with pytest.raises(CommissioningCoordinatorError, match="expired"):
        core.execute(permit)


def test_failed_prepare_cleanup_never_issues_or_caches_a_presence_permit(monkeypatch):
    core, store, worker, clock, request = components()
    original = store.transaction

    @contextmanager
    def failed_cleanup(leases):
        with original(leases) as tx:
            yield tx
        raise OSError("modeled cleanup failure")

    monkeypatch.setattr(store, "transaction", failed_cleanup)
    for _ in range(2):
        with pytest.raises(CommissioningCoordinatorError, match="cleanup failed"):
            core.prepare(request)
    assert not core._permits and not core._prepared_requests
    assert not store.attempts and worker.calls == 0


@pytest.mark.parametrize(
    "delay_ns", [0, 4_000_000_000, 6_000_000_000, 10_000_000_000, 15_000_000_000]
)
def test_presence_deadline_clips_to_original_expiry_without_renewal(
    monkeypatch, delay_ns
):
    core, store, worker, clock, request = components()
    permit = core.prepare(request)
    consume = store.consume_permit

    def delayed_consume(exact):
        consume(exact)
        clock.now += delay_ns

    monkeypatch.setattr(store, "consume_permit", delayed_consume)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN and worker.calls == 1
    deadline = min(clock.now + 25_000_000_000, permit.expires_at_ns)
    assert worker.deadlines == [deadline]
    assert 15_000_000_000 <= deadline - clock.now <= 25_000_000_000
    assert deadline <= permit.expires_at_ns == permit.issued_at_ns + 30_000_000_000


@pytest.mark.parametrize("delay_ns", [15_000_000_001, 29_000_000_000, 30_000_000_000])
def test_less_than_original_fifteen_seconds_is_uncertain_without_dispatch(
    monkeypatch, delay_ns
):
    core, store, worker, clock, request = components()
    permit = core.prepare(request)
    consume = store.consume_permit

    def delayed_consume(exact):
        consume(exact)
        clock.now += delay_ns

    monkeypatch.setattr(store, "consume_permit", delayed_consume)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert result.receipt is None and not store.evidence and worker.calls == 0
    assert "EFFECT_ARMED" in store.trace and not worker.deadlines
    assert core.execute(permit) is result


@pytest.mark.parametrize(
    "changes",
    [
        {"source_binding_sha256": "7" * 64},
        {"usb_presence_policy_sha256": "8" * 64},
        {"runtime_review_sha256": "8" * 64},
        {"phase_binding_sha256": "6" * 64, "selected_identity_sha256": "6" * 64},
        {"journal_head_sha256": "5" * 64},
        {"quarantine_latched": True},
        {"unresolved_attempts": 1},
        {"stage_state": V2StageState.REVIEW_PENDING},
    ],
)
def test_fresh_execute_read_cannot_reuse_changed_phase_or_original_context(changes):
    core, store, worker, clock, request = components()
    permit = core.prepare(request)
    store.snapshot = replace(store.snapshot, **changes)
    with pytest.raises(CommissioningCoordinatorError):
        core.execute(permit)
    assert not store.attempts and worker.calls == 0


def test_cancel_before_consumption_is_a_retained_no_effect_abort():
    core, store, worker, clock, request = components()
    permit = core.prepare(request)
    stop = Event()
    stop.set()
    result = core.execute(permit, cancellation=stop)
    assert result.state is AttemptState.ABORTED_PRE_EFFECT
    assert result.receipt is None and not result.quarantine_latched
    assert "EFFECT_ARMED" not in store.trace and worker.calls == 0
    assert core.execute(permit, cancellation=Event()) is result


def test_late_read_only_revalidation_failure_retains_returned_diagnostics(monkeypatch):
    core, store, worker, clock, request = components()
    original = worker.run_scoped_campaign

    def failing_final_scope(exact, **kwargs):
        execution = original(exact, **kwargs)
        clock.now = kwargs["deadline_ns"] + 1
        return execution

    monkeypatch.setattr(worker, "run_scoped_campaign", failing_final_scope)
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.quarantine_latched
    assert store.evidence[0].payload == PAYLOAD and worker.calls == 1


def test_late_lease_cleanup_failure_keeps_known_original_and_blocks_cached_replay(
    monkeypatch,
):
    core, store, worker, clock, request = components()
    permit = core.prepare(request)
    original = store.transaction

    @contextmanager
    def failed_cleanup(leases):
        with original(leases) as tx:
            yield tx
        raise OSError("modeled post-result lease cleanup failure")

    monkeypatch.setattr(store, "transaction", failed_cleanup)
    for _ in range(2):
        with pytest.raises(CommissioningCoordinatorError, match="cleanup failed"):
            core.execute(permit)
    assert store.results[permit.attempt_id].state is AttemptState.SEALED_KNOWN
    assert store.evidence[0].payload == PAYLOAD and worker.calls == 1
    assert store.trace.count("EFFECT_ARMED") == 1
