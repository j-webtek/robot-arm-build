"""Closed camera-domain contracts with incapable workers; no physical providers.

The in-memory store below is a protocol double, not qualified persistence.
Actual publication/lease tests live in test_commissioning_camera_persistence.
"""

from __future__ import annotations

from dataclasses import asdict, replace
import json
from threading import Event
from typing import Any

import pytest

from rocell.application.cell_commissioning_coordinator import (
    AdmissionSnapshot,
    CampaignBudget,
    CampaignEvidence,
    CampaignRegistration,
    CellCommissioningCoordinator,
    CommissioningCoordinatorError,
    CommissioningMode,
    EnergizationEnvelope,
    ExactOperationPermit,
    INCAPABLE_COMPOSITION,
    ObservedPowerState,
    PHYSICAL_CAMERA_COMPOSITION,
    PHYSICAL_DIAGNOSTIC_COMPOSITION,
    PhysicalCameraAcquisitionCoordinator,
    PhysicalDiagnosticPreflightCoordinator,
    RegisteredActionRequest,
    RetainedCampaignExecution,
    WorkerReceipt,
)
from rocell.application.commissioning_camera_persistence import (
    decode_physical_camera_permit,
    physical_camera_source_binding,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
    _decode_permit,
)
from rocell.application.commissioning_physical_persistence import (
    decode_physical_diagnostic_permit,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_leases import LeaseLevel, LeaseSpec
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.safety.effects import EffectCertainty, EffectClass

from test_commissioning_coordinator import Clock, InMemoryProtocolStore


SOURCE = "a" * 64
CELL = "wizard-physical-camera-" + "b" * 16
SESSION = "physical-camera-" + "c" * 32
STAGE = PhysicalOnboardingStage.CAMERA_MODE_CONTROLS
ACTION = "test-incapable-camera-contract"
LEASES = (
    LeaseSpec(LeaseLevel.CELL, CELL),
    LeaseSpec(LeaseLevel.SESSION, SESSION),
    LeaseSpec(LeaseLevel.CAMERA, CELL),
)
PAYLOAD = b'{"provenance":"INCAPABLE_CONTRACT_TEST","device_effects":0}'


def registration(**changes: Any) -> CampaignRegistration:
    return replace(
        CampaignRegistration(
            ACTION,
            STAGE,
            EffectClass.BOUNDED_CAMERA_CAMPAIGN,
            "incapable-contract-worker",
            "d" * 64,
            SOURCE,
            (LeaseLevel.CAMERA,),
            CampaignBudget(20000, 4096, 1, 1, 0, 1, 1),
        ),
        **changes,
    )


def admission(**changes: Any) -> AdmissionSnapshot:
    return replace(
        AdmissionSnapshot(
            CELL,
            SESSION,
            CommissioningMode.PHYSICAL_DIAGNOSTIC,
            STAGE,
            V2StageState.WAITING_OPERATOR,
            1,
            physical_camera_source_binding(SOURCE),
            *(["e" * 64] * 7),
            ("f" * 64,) * 8,
            "9" * 64,
            False,
            0,
        ),
        **changes,
    )


class CameraProtocolStore(InMemoryProtocolStore):
    composition = PHYSICAL_CAMERA_COMPOSITION

    def __init__(self, snapshot: AdmissionSnapshot) -> None:
        super().__init__(snapshot)
        self.acknowledged = False
        self.evidence: tuple[CampaignEvidence, ...] = ()

    def assert_consumed_permit(self, permit: ExactOperationPermit) -> None:
        assert self.held_leases == LEASES
        assert self.attempts[permit.attempt_id] is AttemptState.EFFECT_ARMED
        assert not self.acknowledged
        self.acknowledged = True
        self.trace.append("ACKNOWLEDGED_ONCE")

    def revalidate_consumed_permit(self, permit: ExactOperationPermit) -> None:
        assert self.acknowledged and self.held_leases == LEASES
        self.trace.append("CONSUMED_SCOPE_REVALIDATED")

    def retain_campaign_evidence(self, permit: Any, evidence: Any) -> None:
        assert self.acknowledged
        self.evidence = evidence
        self.trace.append("FULL_EVIDENCE_RETAINED")


class IncapableCameraContractWorker:
    """Never imports a provider or claims an open/frame/power observation."""

    composition = PHYSICAL_CAMERA_COMPOSITION
    worker_executable_sha256 = "d" * 64

    def __init__(self, *, fault: str | None = None) -> None:
        self.fault, self.calls = fault, 0
        self.authority: Any = None
        self.error: BaseException | None = None

    def run_scoped_campaign(
        self,
        permit: ExactOperationPermit,
        *,
        deadline_ns: int,
        cancellation: Event,
        authorization: Any,
    ) -> RetainedCampaignExecution:
        self.calls += 1
        self.authority = authorization
        try:
            if self.fault != "omit-ack":
                authorization.acknowledge(permit)
            if self.fault == "duplicate-ack":
                authorization.acknowledge(permit)
            if self.fault != "omit-check":
                authorization.revalidate(permit)
                authorization.revalidate(permit)
            if self.fault == "cancel":
                cancellation.set()
            item = CampaignEvidence(
                "rocell.incapable-camera-contract.v1", "contract", PAYLOAD
            )
            receipt = WorkerReceipt(
                permit.attempt_id,
                permit.permit_sha256,
                self.worker_executable_sha256,
                permit.admission.selected_identity_sha256,
                EffectCertainty.CONFIRMED,
                True,
                (
                    ObservedPowerState.UNKNOWN
                    if self.fault != "power-claim"
                    else ObservedPowerState.DEENERGIZED
                ),
                0,
                0,
                0,
                0,
                0,
                len(PAYLOAD),
                (item.payload_sha256,),
                composition=self.composition,
            )
            return RetainedCampaignExecution(receipt, (item,))
        except BaseException as exc:
            self.error = exc
            raise


def components(*, fault: str | None = None, selected: Any = None):
    snapshot = admission() if selected is None else selected
    store = CameraProtocolStore(snapshot)
    worker = IncapableCameraContractWorker(fault=fault)
    registered = registration()
    clock = Clock()
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=store,
        registrations=(registered,),
        workers={registered.worker_id: worker},
        retained_campaign_actions=(ACTION,),
        scoped_campaign_actions=(ACTION,),
        monotonic_ns=clock,
    )
    request = RegisteredActionRequest(
        CELL, SESSION, ACTION, "one-use", snapshot.challenge_sha256
    )
    return core, store, worker, request


def test_camera_domain_is_inert_and_requires_retained_scoped_worker() -> None:
    core, store, worker, request = components()
    assert not store.trace and worker.calls == 0
    permit = core.prepare(request)
    assert permit.envelope is None and worker.calls == 0
    assert "INTENT_DURABLE" not in store.trace
    assert permit.registration.resources == (LeaseLevel.CAMERA,)


@pytest.mark.parametrize("missing", ["retained", "scoped", "method"])
def test_every_camera_action_requires_exact_retention_and_scope(missing: str) -> None:
    worker = IncapableCameraContractWorker()
    if missing == "method":
        worker.run_scoped_campaign = None  # type: ignore[assignment]
    with pytest.raises(CommissioningCoordinatorError):
        PhysicalCameraAcquisitionCoordinator(
            persistence=CameraProtocolStore(admission()),
            registrations=(registration(),),
            workers={registration().worker_id: worker},
            retained_campaign_actions=() if missing == "retained" else (ACTION,),
            scoped_campaign_actions=(
                () if missing in {"retained", "scoped"} else (ACTION,)
            ),
        )


@pytest.mark.parametrize(
    "change",
    [
        {"stage": PhysicalOnboardingStage.WORKSPACE_SOURCES},
        {"stage": PhysicalOnboardingStage.FEEDBACK_ONLY_CONNECTION},
        {"effect_class": EffectClass.READ_ONLY_OS_INVENTORY},
        {"effect_class": EffectClass.NO_DEVICE_IO},
        {"resources": ()},
        {"resources": (LeaseLevel.ARM_CONTROLLER,)},
        {"resources": (LeaseLevel.CAMERA, LeaseLevel.ARM_CONTROLLER)},
        {"budget": CampaignBudget(25001, 4096, 1, 1, 0, 1, 1)},
    ],
)
def test_camera_registration_does_not_broaden_stage_effect_or_lease(
    change: Any,
) -> None:
    with pytest.raises(CommissioningCoordinatorError):
        item = registration(**change)
        PhysicalCameraAcquisitionCoordinator(
            persistence=CameraProtocolStore(admission()),
            registrations=(item,),
            workers={item.worker_id: IncapableCameraContractWorker()},
            retained_campaign_actions=(ACTION,),
            scoped_campaign_actions=(ACTION,),
        )


@pytest.mark.parametrize(
    "stage", [STAGE, PhysicalOnboardingStage.CAMERA_FRAME_FRESHNESS]
)
def test_only_the_two_camera_stages_are_registered(stage: Any) -> None:
    item = registration(stage=stage)
    PhysicalCameraAcquisitionCoordinator(
        persistence=CameraProtocolStore(admission(stage=stage)),
        registrations=(item,),
        workers={item.worker_id: IncapableCameraContractWorker()},
        retained_campaign_actions=(ACTION,),
        scoped_campaign_actions=(ACTION,),
    )


@pytest.mark.parametrize(
    "domain", [INCAPABLE_COMPOSITION, PHYSICAL_DIAGNOSTIC_COMPOSITION]
)
def test_other_store_or_worker_compositions_are_not_camera_authority(
    domain: str,
) -> None:
    for target in ("store", "worker"):
        store, worker = (
            CameraProtocolStore(admission()),
            IncapableCameraContractWorker(),
        )
        setattr(store if target == "store" else worker, "composition", domain)
        with pytest.raises(CommissioningCoordinatorError):
            PhysicalCameraAcquisitionCoordinator(
                persistence=store,
                registrations=(registration(),),
                workers={registration().worker_id: worker},
                retained_campaign_actions=(ACTION,),
                scoped_campaign_actions=(ACTION,),
            )


@pytest.mark.parametrize(
    "constructor",
    [CellCommissioningCoordinator, PhysicalDiagnosticPreflightCoordinator],
)
def test_camera_store_cannot_be_reinterpreted_by_other_coordinator(
    constructor: Any,
) -> None:
    with pytest.raises(CommissioningCoordinatorError):
        constructor(
            persistence=CameraProtocolStore(admission()),
            registrations=(registration(),),
            workers={registration().worker_id: IncapableCameraContractWorker()},
        )


@pytest.mark.parametrize(
    "change",
    [
        {"selected_identity_sha256": None},
        {"mode": CommissioningMode.REHEARSAL},
        {"open_blocker_ids": ("UNREVIEWED_RUNTIME",)},
        {"stage_state": V2StageState.REVIEW_PENDING},
        {"quarantine_latched": True},
    ],
)
def test_unreviewed_or_wrong_domain_admission_never_dispatches(change: Any) -> None:
    core, _, worker, request = components(selected=admission(**change))
    with pytest.raises(CommissioningCoordinatorError):
        core.prepare(request)
    assert worker.calls == 0


def test_camera_rejects_energy_envelope_and_cannot_observe_power() -> None:
    core, store, worker, request = components()
    store.envelope = EnergizationEnvelope(
        "energy", SOURCE, *("a" * 64,) * 4, "operator", "observer", 0, 10000000
    )
    with pytest.raises(CommissioningCoordinatorError, match="non-power"):
        core.prepare(request)
    assert worker.calls == 0
    core, _, worker, request = components(fault="power-claim")
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert result.receipt.final_power_state is ObservedPowerState.DEENERGIZED


def test_scoped_one_use_retains_actual_bytes_and_revokes_callback() -> None:
    core, store, worker, request = components()
    permit = core.prepare(request)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN
    assert core.execute(permit) == result and worker.calls == 1
    assert result.composition == PHYSICAL_CAMERA_COMPOSITION
    assert result.physical_authority == "NONE"
    assert result.receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert store.evidence[0].payload == PAYLOAD
    assert store.trace.count("ACKNOWLEDGED_ONCE") == 1
    assert store.trace.count("CONSUMED_SCOPE_REVALIDATED") == 2
    assert store.trace.index("FULL_EVIDENCE_RETAINED") < store.trace.index(
        "SEALED_KNOWN"
    )
    assert not store.held_leases
    with pytest.raises(CommissioningCoordinatorError):
        worker.authority.revalidate(permit)


@pytest.mark.parametrize("fault", ["omit-ack", "omit-check", "duplicate-ack", "cancel"])
def test_incomplete_scope_checks_hold_without_replay(fault: str) -> None:
    core, _, worker, request = components(fault=fault)
    permit = core.prepare(request)
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert result.quarantine_latched and worker.calls == 1
    assert core.execute(permit) == result


def test_pre_dispatch_cancel_and_substituted_permit_never_run_worker() -> None:
    core, _, worker, request = components()
    permit = core.prepare(request)
    with pytest.raises(CommissioningCoordinatorError, match="substituted"):
        core.execute(
            replace(permit, registration=registration(operation_sha256="1" * 64))
        )
    cancelled = Event()
    cancelled.set()
    result = core.execute(permit, cancellation=cancelled)
    assert result.state is AttemptState.ABORTED_PRE_EFFECT and worker.calls == 0


def pure_permit() -> ExactOperationPermit:
    core, _, _, request = components()
    return core.prepare(request)


def test_camera_permit_is_readonly_decodable_but_cross_domain_refused() -> None:
    permit = pure_permit()
    value = json.loads(canonical_json_bytes(asdict(permit)))
    assert decode_physical_camera_permit(value) == permit
    for decoder in (_decode_permit, decode_physical_diagnostic_permit):
        with pytest.raises(M1CommissioningPersistenceError):
            decoder(value)


@pytest.mark.parametrize(
    "field,value",
    [
        ("effect_class", "NO_DEVICE_IO"),
        ("stage", "workspace_sources"),
        ("resources", []),
        ("resources", ["ARM_CONTROLLER"]),
        ("timeout", 25001),
        ("boolean-count", False),
        ("mode", "REHEARSAL"),
        ("namespace", "wizard-physical-diagnostic-" + "b" * 16),
        ("extra", True),
    ],
)
def test_camera_permit_decoder_rejects_domain_and_shape_tampering(
    field: str, value: Any
) -> None:
    document = json.loads(canonical_json_bytes(asdict(pure_permit())))
    if field == "timeout":
        document["registration"]["budget"]["timeout_ms"] = value
    elif field == "boolean-count":
        document["registration"]["budget"]["maximum_opens"] = value
    elif field in {"mode", "namespace"}:
        document["admission"]["mode" if field == "mode" else "cell_id"] = value
    elif field == "extra":
        document["physical_authority"] = value
    else:
        document["registration"][field] = value
    with pytest.raises(
        (M1CommissioningPersistenceError, CommissioningCoordinatorError)
    ):
        decode_physical_camera_permit(document)
