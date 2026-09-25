"""Actual isolated NTFS M1/leases, explicitly MODELED physical-shaped subjects.

No process, USB, CIM, camera, serial or received-hardware call is permitted.
The in-process worker reports only its own zero-effect storage exercise. Modeled
predecessor stage entries do not qualify any source, camera, boot or USB trial.
"""

from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import subprocess
from threading import Event
import time
from types import SimpleNamespace

import pytest

from rocell.application import commissioning_m1_persistence as pm
from rocell.application import commissioning_usb_presence_persistence as m
from rocell.application import physical_camera_prerequisites as prerequisites_module
from rocell.application import physical_onboarding_v2 as v2
from rocell.application.cell_commissioning_coordinator import (
    CampaignBudget,
    CommissioningCoordinatorError,
    PHYSICAL_USB_PRESENCE_COMPOSITION,
    PhysicalUsbPresenceCoordinator,
    RegisteredActionRequest,
    RetainedUncertainCampaignExecution,
    USB_PRESENCE_ACTION_ID,
    USB_PRESENCE_WORKER_ID,
    UsbPresenceAdmissionSnapshot,
)
from rocell.application.commissioning_camera_persistence import (
    decode_physical_camera_permit,
)
from rocell.application.commissioning_usb_identity_persistence import (
    M1PhysicalUsbIdentityPersistence,
    decode_physical_usb_identity_permit,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.physical_usb_presence_binding import (
    build_usb_presence_phase_binding,
)
from rocell.application.usb_presence_stage_policy import usb_presence_stage_policy
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.providers.windows.usb_presence_registration import (
    usb_presence_runtime_candidate,
)
from rocell.providers.windows.usb_presence_review import review_usb_presence_runtime

from test_commissioning_coordinator import Clock
from test_commissioning_usb_identity import (
    POLICY as OLD_USB_POLICY,
    _modeled_ready,
    actual_request as usb_request,
    core_and_request,
    root_for,
    runtime_and_adapter,
    usb_core,
    usb_facts,
)
from test_physical_camera_coordinator import (
    CELL,
    SESSION,
    SOURCE,
    LEASES,
    PAYLOAD,
    CameraProtocolStore,
    IncapableCameraContractWorker,
    admission,
    registration,
)
from test_physical_camera_prerequisites import workspace
from test_physical_camera_usb_qualification import reference
from test_physical_usb_presence_binding import presence_fixture
import test_physical_received_camera as received_fixture


POLICY = usb_presence_stage_policy()
STAGE = PhysicalOnboardingStage.CAMERA_IDENTITY
WINDOWS = pytest.mark.skipif(
    os.name != "nt", reason="Real isolated NTFS and Windows leases"
)


@pytest.fixture(autouse=True)
def no_process_or_device(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail(
            "Presence persistence tests cannot start a process or query devices"
        )

    monkeypatch.setattr(subprocess, "Popen", denied)
    monkeypatch.setattr(os, "system", denied)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, denied)


def subjects(workspace, monkeypatch, *, header):
    # These are test-producer constants, not any production validator override.
    # Every original codec is rebuilt against the actual storage header/context.
    prerequisites = prerequisites_module.collect_physical_camera_prerequisites(
        workspace,
        source_sha256=SOURCE,
        session_id=SESSION,
        launch_session_id=received_fixture.ORIGIN,
        cancellation=Event(),
        deadline_ns=time.monotonic_ns() + 30_000_000_000,
    )
    with monkeypatch.context() as context:
        for field, value in {
            "SOURCE": SOURCE,
            "SESSION": SESSION,
            "CELL": CELL,
            "HEADER": header,
        }.items():
            context.setattr(received_fixture, field, value)
        original = presence_fixture(prerequisites)
    phase = build_usb_presence_phase_binding(**original)
    runtime = usb_presence_runtime_candidate(workspace, source_sha256=SOURCE)
    operation = "6" * 64
    review = review_usb_presence_runtime(
        runtime,
        phase_binding=phase,
        policy=POLICY,
        operation_sha256=operation,
        operator_id="MODELED-operator",
        reviewer_id="MODELED-reviewer",
        launch_session_id="wizard-modeled-presence-review",
        reviewed_at_ns=phase.to_dict()["not_before_utc_ns"] + 1,
    )
    return SimpleNamespace(
        phase=phase, runtime=runtime, review=review, operation=operation
    )


def facts(case):
    return m.PhysicalUsbPresenceAdmissionFacts(
        {
            "provenance": "MODELED_INCAPABLE_STORAGE_TEST",
            "source": SOURCE,
            "revision": case.revision,
        },
        tuple({"domain": i, "provenance": "MODELED_UNQUALIFIED"} for i in range(8)),
        case.phase.to_dict(),
        stage_policy=POLICY,
        phase_binding=case.phase,
        runtime_review=case.review,
        runtime_review_reference=case.reference,
        runtime_review_event=case.event,
    )


def registered(case, **changes):
    return registration(
        action_id=USB_PRESENCE_ACTION_ID,
        worker_id=USB_PRESENCE_WORKER_ID,
        worker_executable_sha256=case.runtime.to_dict()["helper"]["sha256"],
        operation_sha256=case.operation,
        stage=STAGE,
        budget=CampaignBudget(25000, 128 * 1024, 0, 4, 0, 0, 0),
        **changes,
    )


class InProcessPresenceWorker(IncapableCameraContractWorker):
    composition = PHYSICAL_USB_PRESENCE_COMPOSITION

    def __init__(self, helper_sha, *, fault=None):
        super().__init__(fault=fault)
        # Registration identity is MODELED; no executable is ever launched.
        self.worker_executable_sha256 = helper_sha

    def run_scoped_campaign(self, permit, **kwargs):
        result = super().run_scoped_campaign(permit, **kwargs)
        if self.fault == "unknown-counts":
            return RetainedUncertainCampaignExecution(
                result.evidence, ("PRESENCE_COUNTS_UNKNOWN",)
            )
        return result


def core(adapter, case, *, fault=None, clock=None, item_override=None):
    item = registered(case) if item_override is None else item_override
    worker = InProcessPresenceWorker(item.worker_executable_sha256, fault=fault)
    owner = PhysicalUsbPresenceCoordinator(
        persistence=adapter,
        registrations=(item,),
        workers={item.worker_id: worker},
        retained_campaign_actions=(item.action_id,),
        scoped_campaign_actions=(item.action_id,),
        usb_presence_policy_sha256=POLICY.sha256,
        **({} if clock is None else {"monotonic_ns": clock}),
    )
    return owner, worker


def adapter(runtime, case):
    return m.M1PhysicalUsbPresencePersistence(
        runtime,
        workspace_source_sha256=SOURCE,
        stage_policy=POLICY,
        expected_usb_presence_policy_sha256=POLICY.sha256,
        admission_facts=lambda request, snapshot: facts(case),
    )


def request(store, key="actual-modeled-presence"):
    item = RegisteredActionRequest(CELL, SESSION, USB_PRESENCE_ACTION_ID, key, "1" * 64)
    with store.transaction(LEASES) as tx:
        observed = tx.read_admission(item)
        assert type(observed) is UsbPresenceAdmissionSnapshot
        item = replace(item, expected_challenge_sha256=observed.challenge_sha256)
    return item


def actual_case(workspace, monkeypatch):
    runtime, camera = runtime_and_adapter(workspace, ready=False)
    _modeled_ready(runtime, camera)
    header = runtime.session_snapshot(SESSION).header.header_sha256
    case = subjects(workspace, monkeypatch, header=header)
    timestamp = case.review.to_dict()["reviewed_at_ns"]
    suffix = case.phase.to_dict()["binding"]["trial_id"][9:].upper()
    with camera.stage_transaction(
        SESSION, expected_challenge_sha256=camera.verification(SESSION).challenge_sha256
    ) as tx:
        ref = tx.store_evidence(
            STAGE,
            case.review.payload,
            label="MODELED-original-presence-runtime-review",
            media_type="application/json",
            captured_at_ns=timestamp,
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        for offset, state, code in (
            (1, v2.V2StageState.REVIEW_PENDING, "MODELED_PRESENCE_REVIEW_CANDIDATE"),
            (
                2,
                v2.V2StageState.BLOCKED,
                "CAMERA_USB_PRESENCE_RUNTIME_REVIEWED_" + suffix,
            ),
            (
                3,
                v2.V2StageState.WAITING_OPERATOR,
                "CAMERA_USB_PRESENCE_QUERY_REQUESTED_" + suffix,
            ),
        ):
            tx.commit_stage_state(
                STAGE,
                state,
                occurred_at_ns=timestamp + offset,
                detail_code=code,
                expected_head_sha256=tx.snapshot().head.head_sha256,
                evidence=(ref,),
            )
        case.reference = ref
        case.event = tx.snapshot().committed_events[-2]
    case.revision = 0
    print("PRESERVED_MODELED_NTFS_STORE=" + str(runtime.deployment_root), flush=True)
    return runtime, camera, adapter(runtime, case), case


class PresenceProtocolStore(CameraProtocolStore):
    composition = PHYSICAL_USB_PRESENCE_COMPOSITION


@pytest.fixture
def modeled(workspace, monkeypatch):
    case = subjects(workspace, monkeypatch, header="4" * 64)
    case.reference = reference(case.review.payload, "MODELED-runtime-review")
    event = v2.V2JournalEvent(
        session_id=SESSION,
        session_header_sha256="4" * 64,
        sequence=2,
        stage=STAGE,
        previous_state=v2.V2StageState.REVIEW_PENDING,
        state=v2.V2StageState.BLOCKED,
        occurred_at_ns=case.review.to_dict()["reviewed_at_ns"] + 1,
        previous_event_sha256="3" * 64,
        evidence=(case.reference,),
        detail_code="CAMERA_USB_PRESENCE_RUNTIME_REVIEWED_"
        + case.phase.to_dict()["binding"]["trial_id"][9:].upper(),
        event_sha256="0" * 64,
    )
    case.event = replace(event, event_sha256=v2._stable_hash(event.core_dict()))
    case.revision = 0
    f = facts(case)
    snapshot = UsbPresenceAdmissionSnapshot(
        **asdict(
            admission(
                stage=STAGE,
                hazard_assessment_sha256=pm._sha256(f._hazard),
                configuration_epoch_hashes=tuple(
                    pm._sha256(item) for item in f._epochs
                ),
                selected_identity_sha256=case.phase.sha256,
            )
        ),
        usb_presence_policy_sha256=POLICY.sha256,
        phase_binding_sha256=case.phase.sha256,
        runtime_review_sha256=case.review.sha256,
    )
    store = PresenceProtocolStore(snapshot)
    owner, worker = core(store, case, clock=Clock())
    req = RegisteredActionRequest(
        CELL,
        SESSION,
        USB_PRESENCE_ACTION_ID,
        "pure-presence",
        snapshot.challenge_sha256,
    )
    return case, f, snapshot, store, owner, worker, req


def test_pure_exact_permit_and_full_review_facts_are_additive(modeled):
    case, f, snapshot, store, owner, worker, req = modeled
    permit = owner.prepare(req)
    raw = json.loads(canonical_json_bytes(asdict(permit)))
    assert m.decode_physical_usb_presence_permit(raw) == permit
    m.verify_usb_presence_admission_evidence(
        f.retained_documents(), snapshot, permit=permit
    )
    assert permit.admission.runtime_review_sha256 == case.review.sha256
    for old in (
        decode_physical_camera_permit,
        decode_physical_usb_identity_permit,
        pm._decode_permit,
    ):
        with pytest.raises((ValueError, RuntimeError)):
            old(raw)
    assert worker.calls == 0 and permit.envelope is None


@pytest.mark.parametrize(
    "field",
    [
        "stage_policy",
        "hazard_assessment",
        "configuration_epochs",
        "selected_identity",
        "runtime_review",
        "runtime_review_reference",
        "runtime_review_event",
    ],
)
def test_pure_full_fact_mutation_cannot_replace_original_hashes(modeled, field):
    _, f, snapshot, *_ = modeled
    value = f.retained_documents()
    if field == "configuration_epochs":
        value[field][0]["changed"] = True
    else:
        value[field]["changed"] = True
    with pytest.raises((ValueError, RuntimeError)):
        m.verify_usb_presence_admission_evidence(value, snapshot)
    m.verify_usb_presence_admission_evidence(f.retained_documents(), snapshot)


@pytest.mark.parametrize("field", ["operation_sha256", "worker_executable_sha256"])
def test_pure_review_cannot_cover_a_different_registered_worker_or_operation(
    modeled, field
):
    _, f, snapshot, _, owner, _, req = modeled
    permit = owner.prepare(req)
    changed = replace(
        permit, registration=replace(permit.registration, **{field: "9" * 64})
    )
    with pytest.raises((ValueError, RuntimeError)):
        m.verify_usb_presence_admission_evidence(
            f.retained_documents(), snapshot, permit=changed
        )


@WINDOWS
def test_actual_ntfs_review_permit_terminal_full_readback_and_sibling_audit(
    workspace, monkeypatch
):
    runtime, camera, store, case = actual_case(workspace, monkeypatch)
    owner, worker = core(store, case)
    permit = owner.prepare(request(store))
    result = owner.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN, (result, worker.error)
    assert worker.calls == 1 and result.receipt.opens == 0
    assert result.receipt.final_power_state.value == "UNKNOWN"
    assert owner.execute(permit) == result and worker.calls == 1
    with store.stage_transaction(
        SESSION, expected_challenge_sha256=store.verification(SESSION).challenge_sha256
    ) as tx:
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert tx.read_campaign_result(permit.attempt_id) == result
        assert tx.read_campaign_evidence(permit.attempt_id)[0].payload == PAYLOAD
        assert (
            tx.read_campaign_admission_evidence(permit.attempt_id)
            == facts(case).retained_documents()
        )
        assert tx.read_stage_evidence(case.reference) == case.review.payload
        assert len(tx._audit_records()) == 5
    with pytest.raises(CommissioningCoordinatorError):
        worker.authority.revalidate(permit)

    # A separately named older USB query shares the full original cell audit.
    usb_store = M1PhysicalUsbIdentityPersistence(
        runtime,
        workspace_source_sha256=SOURCE,
        stage_policy=OLD_USB_POLICY,
        expected_usb_query_policy_sha256=OLD_USB_POLICY.sha256,
        admission_facts=usb_facts,
    )
    usb_owner, usb_worker = usb_core(usb_store)
    usb_permit = usb_owner.prepare(usb_request(usb_store, "separate-modeled-query"))
    usb_result = usb_owner.execute(usb_permit)
    assert usb_result.state is AttemptState.SEALED_KNOWN, (usb_result, usb_worker.error)

    # Explicit modeled stage movement only, not a physical acceptance claim.
    timestamp = case.event.occurred_at_ns + 10
    with camera.stage_transaction(
        SESSION, expected_challenge_sha256=camera.verification(SESSION).challenge_sha256
    ) as tx:
        for offset, state in enumerate(
            (v2.V2StageState.REVIEW_PENDING, v2.V2StageState.PASS)
        ):
            tx.commit_stage_state(
                STAGE,
                state,
                occurred_at_ns=timestamp + offset,
                detail_code="MODELED_STORAGE_ONLY_NOT_QUALIFICATION",
                expected_head_sha256=tx.snapshot().head.head_sha256,
                evidence=(case.reference,),
            )
        tx.commit_stage_state(
            PhysicalOnboardingStage.CAMERA_MODE_CONTROLS,
            v2.V2StageState.WAITING_OPERATOR,
            occurred_at_ns=timestamp + 2,
            detail_code="MODELED_CAMERA_FOLLOWUP",
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
    camera_owner, camera_worker, camera_req = core_and_request(
        camera, key="separate-modeled-camera"
    )
    camera_permit = camera_owner.prepare(camera_req)
    camera_result = camera_owner.execute(camera_permit)
    assert camera_result.state is AttemptState.SEALED_KNOWN, (
        camera_result,
        camera_worker.error,
    )
    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        cell_id=CELL,
        source_binding_sha256=runtime.source_binding_sha256,
    )
    reader = adapter(reopened, case)
    with reader.stage_transaction(
        SESSION, expected_challenge_sha256=reader.verification(SESSION).challenge_sha256
    ) as tx:
        assert tx.read_campaign_result(permit.attempt_id) == result
        assert (
            tx.read_campaign_admission_evidence(permit.attempt_id)
            == facts(case).retained_documents()
        )
        assert len(tx._audit_records()) == 5
        assert len(tx._audit_records(include_family=True)) == 15
    restarted, unused = core(reader, case)
    with pytest.raises(CommissioningCoordinatorError):
        restarted.execute(permit)
    assert unused.calls == 0

    # Deliberately corrupt only this isolated test store. New presence reads
    # must audit an older sibling too, not just its own five records.
    path = next(
        root_for(runtime, "physical-usb-identity-records").glob("request-*.json")
    )
    value = json.loads(path.read_bytes())
    value["data"]["admission_evidence"]["hazard_assessment"]["changed"] = True
    value["record_sha256"] = pm._sha256(
        canonical_json_bytes({k: v for k, v in value.items() if k != "record_sha256"})
    )
    path.write_bytes(canonical_json_bytes(value))
    with pytest.raises(m.M1CommissioningPersistenceError):
        with reader.stage_transaction(
            SESSION,
            expected_challenge_sha256=reader.verification(SESSION).challenge_sha256,
        ):
            pass


@WINDOWS
def test_actual_ntfs_unknown_counts_reopen_retains_bytes_without_replay(
    workspace, monkeypatch
):
    runtime, camera, store, case = actual_case(workspace, monkeypatch)
    owner, worker = core(store, case, fault="unknown-counts")
    permit = owner.prepare(request(store))
    result = owner.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.receipt is None
    assert "PRESENCE_COUNTS_UNKNOWN" in result.reason_codes and worker.calls == 1
    assert owner.execute(permit) == result and worker.calls == 1
    assert runtime.verify(SESSION).quarantined
    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        cell_id=CELL,
        source_binding_sha256=runtime.source_binding_sha256,
    )
    reader = adapter(reopened, case)
    with reader.stage_transaction(
        SESSION, expected_challenge_sha256=reader.verification(SESSION).challenge_sha256
    ) as tx:
        assert tx.read_campaign_result(permit.attempt_id) == result
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert tx.read_campaign_evidence(permit.attempt_id)[0].payload == PAYLOAD
        assert (
            tx.read_campaign_admission_evidence(permit.attempt_id)
            == facts(case).retained_documents()
        )
        assert tx.held_leases == LEASES[:2]
    with camera.stage_transaction(
        SESSION, expected_challenge_sha256=camera.verification(SESSION).challenge_sha256
    ) as tx:
        assert (
            tx._audit_records() == {}
            and len(tx._audit_records(include_family=True)) == 3
        )
        assert not any(
            name.startswith("receipt-")
            for name in tx._audit_records(include_family=True)
        )
    restarted, unused = core(reader, case)
    with pytest.raises(CommissioningCoordinatorError):
        restarted.execute(permit)
    assert unused.calls == 0


@WINDOWS
def test_actual_ntfs_changed_current_facts_refuse_before_intent_or_worker(
    workspace, monkeypatch
):
    runtime, _, store, case = actual_case(workspace, monkeypatch)
    # Purely well-formed supplied subjects are not enough: a different original
    # header must be refused before a permit, even with the same cell/session.
    other = subjects(workspace, monkeypatch, header="4" * 64)
    original_phase, original_review = case.phase, case.review
    case.phase, case.review = other.phase, other.review
    with pytest.raises(m.M1CommissioningPersistenceError, match="header differs"):
        request(store, "wrong-modeled-header")
    case.phase, case.review = original_phase, original_review
    for field in ("operation_sha256", "worker_executable_sha256"):
        wrong, unused = core(
            store, case, item_override=replace(registered(case), **{field: "9" * 64})
        )
        bad_permit = wrong.prepare(request(store, "wrong-reviewed-" + field))
        with pytest.raises(m.M1CommissioningPersistenceError):
            wrong.execute(bad_permit)
        assert unused.calls == 0 and not runtime._attempts.snapshot().events
        with store.stage_transaction(
            SESSION,
            expected_challenge_sha256=store.verification(SESSION).challenge_sha256,
        ) as tx:
            assert tx._audit_records() == {}
    owner, worker = core(store, case)
    permit = owner.prepare(request(store))
    case.revision = 1
    with pytest.raises(
        CommissioningCoordinatorError,
        match="stale source/revision/head/identity/epoch challenge",
    ):
        owner.execute(permit)
    assert worker.calls == 0 and not runtime._attempts.snapshot().events
    with store.stage_transaction(
        SESSION, expected_challenge_sha256=store.verification(SESSION).challenge_sha256
    ) as tx:
        assert tx._audit_records() == {}
        with pytest.raises(m.M1CommissioningPersistenceError):
            tx.read_campaign_permit(permit.attempt_id)
        with pytest.raises(m.M1CommissioningPersistenceError, match="terminal"):
            tx.read_campaign_result(permit.attempt_id)
    restarted, unused = core(
        adapter(
            PhysicalOnboardingM1Runtime.open(
                runtime.deployment_root,
                cell_id=CELL,
                source_binding_sha256=runtime.source_binding_sha256,
            ),
            case,
        ),
        case,
    )
    with pytest.raises(CommissioningCoordinatorError):
        restarted.execute(permit)
    assert unused.calls == 0
