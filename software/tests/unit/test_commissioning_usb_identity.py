"""Exact USB domain tests. Modeled facts/workers are never device qualification.

Windows cases use genuine isolated NTFS M1/leases and original readback, but
explicitly modeled prerequisite PASS entries and an incapable in-process worker.
No USB, native inventory, serial, process or received-hardware call is made.
"""

from dataclasses import asdict, replace
import json
import os
from pathlib import Path
import subprocess

import pytest

from rocell.application import commissioning_m1_persistence as persistence_module
from rocell.application.cell_commissioning_coordinator import (
    AdmissionSnapshot,
    CampaignBudget,
    CampaignEvidence,
    CommissioningCoordinatorError,
    PHYSICAL_USB_IDENTITY_COMPOSITION,
    PhysicalUsbIdentityCoordinator,
    RegisteredActionRequest,
    RetainedUncertainCampaignExecution,
    UsbIdentityAdmissionSnapshot,
    USB_IDENTITY_ACTION_ID,
)
from rocell.application.commissioning_usb_identity_persistence import (
    PhysicalUsbIdentityAdmissionFacts,
    M1PhysicalUsbIdentityPersistence,
    decode_physical_usb_identity_permit,
    _verify_admission_evidence,
)
from rocell.application.commissioning_camera_persistence import (
    decode_physical_camera_permit,
)
from rocell.application.commissioning_physical_persistence import (
    decode_physical_diagnostic_permit,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
    _decode_permit,
)
from rocell.application.physical_onboarding import STAGE_ORDER, PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import (
    AttemptState,
    canonical_json_bytes,
)
from rocell.application.physical_onboarding_leases import LeaseLevel
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.application.physical_onboarding_v2 import V2StageState
from rocell.application.usb_identity_stage_policy import usb_identity_stage_policy
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient

from test_commissioning_coordinator import Clock
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
    components as camera_components,
)
from test_commissioning_camera_persistence import runtime_and_adapter, core_and_request


POLICY = usb_identity_stage_policy()
STAGE = PhysicalOnboardingStage.CAMERA_IDENTITY
WINDOWS = pytest.mark.skipif(os.name != "nt", reason="genuine NTFS and OS ownership")


@pytest.fixture(autouse=True)
def no_device_calls(monkeypatch):
    def denied(*args, **kwargs):
        pytest.fail("incapable contract must not start processes or access devices")

    monkeypatch.setattr(subprocess, "Popen", denied)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, denied)


def usb_registration(**changes):
    return replace(
        registration(
            action_id=USB_IDENTITY_ACTION_ID,
            stage=STAGE,
            budget=CampaignBudget(25000, 128 * 1024, 32, 128, 0, 0, 32),
        ),
        **changes,
    )


def usb_snapshot(**changes):
    return replace(
        UsbIdentityAdmissionSnapshot(
            **asdict(admission(stage=STAGE)), usb_query_policy_sha256=POLICY.sha256
        ),
        **changes,
    )


class UsbProtocolStore(CameraProtocolStore):
    composition = PHYSICAL_USB_IDENTITY_COMPOSITION


class IncapableUsbWorker(IncapableCameraContractWorker):
    composition = PHYSICAL_USB_IDENTITY_COMPOSITION

    def run_scoped_campaign(self, permit, **kwargs):
        execution = super().run_scoped_campaign(permit, **kwargs)
        if self.fault in {"unknown-counts", "cancel", "omit-ack"}:
            return RetainedUncertainCampaignExecution(
                execution.evidence, ("USB_COUNTS_UNKNOWN",)
            )
        return execution


def usb_core(adapter, *, fault=None, clock=None, registered=None, policy_sha=None):
    worker = IncapableUsbWorker(fault=fault)
    item = registered or usb_registration()
    core = PhysicalUsbIdentityCoordinator(
        persistence=adapter,
        registrations=(item,),
        workers={item.worker_id: worker},
        retained_campaign_actions=(item.action_id,),
        scoped_campaign_actions=(item.action_id,),
        usb_query_policy_sha256=POLICY.sha256 if policy_sha is None else policy_sha,
        **({} if clock is None else {"monotonic_ns": clock}),
    )
    return core, worker


def protocol_components(**kwargs):
    store = UsbProtocolStore(usb_snapshot())
    core, worker = usb_core(store, clock=Clock(), **kwargs)
    request = RegisteredActionRequest(
        CELL,
        SESSION,
        USB_IDENTITY_ACTION_ID,
        "usb-one",
        store.snapshot.challenge_sha256,
    )
    return core, store, worker, request


def usb_facts(request=None, snapshot=None):
    return PhysicalUsbIdentityAdmissionFacts(
        {"provenance": "MODELED_INCAPABLE_STORAGE_TEST", "source": SOURCE},
        tuple({"domain": i, "provenance": "MODELED_UNQUALIFIED"} for i in range(8)),
        {"selected_identity": "INCAPABLE_NO_DEVICE", "source": SOURCE},
        stage_policy=POLICY,
    )


def test_new_policy_snapshot_is_additive_inert_and_lossless():
    core, store, worker, request = protocol_components()
    assert store.trace == [] and worker.calls == 0
    permit = core.prepare(request)
    assert type(permit.admission) is UsbIdentityAdmissionSnapshot
    assert permit.admission.usb_query_policy_sha256 == POLICY.sha256
    assert permit.envelope is None and worker.calls == 0
    wire = json.loads(canonical_json_bytes(asdict(permit)))
    assert decode_physical_usb_identity_permit(wire) == permit
    for old_decoder in (
        decode_physical_camera_permit,
        decode_physical_diagnostic_permit,
        _decode_permit,
    ):
        with pytest.raises((ValueError, RuntimeError)):
            old_decoder(wire)
    base = asdict(permit.admission)
    del base["usb_query_policy_sha256"]
    assert (
        AdmissionSnapshot(**base).challenge_sha256 != permit.admission.challenge_sha256
    )
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN and worker.calls == 1
    assert store.trace.index("FULL_EVIDENCE_RETAINED") < store.trace.index(
        "SEALED_KNOWN"
    )


@pytest.mark.parametrize(
    "changes",
    [
        {"action_id": "other-action"},
        {"stage": PhysicalOnboardingStage.CAMERA_MODE_CONTROLS},
        {"budget": CampaignBudget(24999, 128 * 1024, 32, 128, 0, 0, 32)},
        {"budget": CampaignBudget(25000, 128 * 1024, 32, 128, 1, 0, 32)},
        {"budget": CampaignBudget(25000, 128 * 1024, 32, 128, 0, 1, 32)},
        {"budget": CampaignBudget(25000, 128 * 1024, 31, 128, 0, 0, 32)},
    ],
)
def test_exact_amendment_registration_not_general_stage_allowlist(changes):
    with pytest.raises(CommissioningCoordinatorError):
        usb_core(
            UsbProtocolStore(usb_snapshot()), registered=usb_registration(**changes)
        )


def test_independent_policy_pin_and_exact_snapshot_type():
    core, store, worker, request = protocol_components(policy_sha="8" * 64)
    with pytest.raises(CommissioningCoordinatorError):
        core.prepare(request)
    assert worker.calls == 0
    base = asdict(store.snapshot)
    del base["usb_query_policy_sha256"]
    store.snapshot = AdmissionSnapshot(**base)
    core, worker = usb_core(store, clock=Clock())
    request = replace(
        request, expected_challenge_sha256=store.snapshot.challenge_sha256
    )
    with pytest.raises(CommissioningCoordinatorError):
        core.prepare(request)


@pytest.mark.parametrize("fault", ["unknown-counts", "cancel"])
def test_missing_counts_retains_originals_without_invented_receipt(fault):
    core, store, worker, request = protocol_components(fault=fault)
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert result.receipt is None and result.quarantine_latched
    assert store.evidence[0].payload == PAYLOAD
    assert "USB_COUNTS_UNKNOWN" in result.reason_codes
    assert worker.calls == 1


def test_missing_acknowledgement_cannot_retain_unknown_counts():
    core, store, worker, request = protocol_components(fault="omit-ack")
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN and not store.evidence


def test_historical_camera_domain_rejects_new_uncertain_type():
    core, store, worker, request = camera_components()
    original = worker.run_scoped_campaign

    def uncertain(permit, **kwargs):
        execution = original(permit, **kwargs)
        return RetainedUncertainCampaignExecution(
            execution.evidence, ("USB_COUNTS_UNKNOWN",)
        )

    worker.run_scoped_campaign = uncertain
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.receipt is None
    assert store.evidence == ()


@pytest.mark.parametrize(
    "reasons",
    [
        (),
        [],
        ([],),
        (True,),
        ("raw endpoint text",),
        ("A", "A"),
        ("X" * 65,),
        tuple("CODE_" + str(i) for i in range(17)),
    ],
)
def test_unknown_count_reason_schema_is_bounded_and_raw_free(reasons):
    with pytest.raises(CommissioningCoordinatorError):
        RetainedUncertainCampaignExecution(
            (CampaignEvidence("rocell.test.v1", "test", PAYLOAD),), reasons
        )


def test_uncertain_forged_dataclass_is_revalidated_before_retention():
    core, store, worker, request = protocol_components()
    original = worker.run_scoped_campaign

    def forged(permit, **kwargs):
        execution = original(permit, **kwargs)
        value = RetainedUncertainCampaignExecution(
            execution.evidence, ("USB_COUNTS_UNKNOWN",)
        )
        object.__setattr__(value, "evidence", ())
        return value

    worker.run_scoped_campaign = forged
    result = core.execute(core.prepare(request))
    assert result.state is AttemptState.SEALED_UNCERTAIN and not store.evidence


@pytest.mark.parametrize(
    "field",
    ["stage_policy", "hazard_assessment", "configuration_epochs", "selected_identity"],
)
def test_full_fact_mutation_is_not_a_hash_only_approval(field):
    facts = usb_facts()
    snapshot = usb_snapshot(
        hazard_assessment_sha256=persistence_module._sha256(facts._hazard),
        configuration_epoch_hashes=tuple(
            persistence_module._sha256(item) for item in facts._epochs
        ),
        selected_identity_sha256=persistence_module._sha256(facts._identity),
    )
    original = facts.retained_documents()
    _verify_admission_evidence(original, snapshot)
    if field == "configuration_epochs":
        original[field][0]["changed"] = True
    else:
        original[field]["changed"] = True
    with pytest.raises((ValueError, RuntimeError)):
        _verify_admission_evidence(original, snapshot)
    _verify_admission_evidence(facts.retained_documents(), snapshot)


def _modeled_ready(runtime, camera):
    with camera.stage_transaction(
        SESSION, expected_challenge_sha256=camera.verification(SESSION).challenge_sha256
    ) as tx:
        timestamp = 2100
        for stage in STAGE_ORDER[: STAGE_ORDER.index(STAGE) + 1]:
            tx.commit_stage_state(
                stage,
                V2StageState.WAITING_OPERATOR,
                occurred_at_ns=timestamp,
                detail_code="MODELED_NO_HARDWARE_STAGE",
                expected_head_sha256=tx.snapshot().head.head_sha256,
            )
            timestamp += 1
            if stage is STAGE:
                break
            ref = tx.store_evidence(
                stage,
                PAYLOAD,
                label="modeled incapable prerequisite",
                media_type="application/json",
                captured_at_ns=timestamp,
                expected_head_sha256=tx.snapshot().head.head_sha256,
            )
            for state in (V2StageState.REVIEW_PENDING, V2StageState.PASS):
                tx.commit_stage_state(
                    stage,
                    state,
                    occurred_at_ns=timestamp,
                    detail_code="MODELED_NOT_QUALIFICATION",
                    expected_head_sha256=tx.snapshot().head.head_sha256,
                    evidence=(ref,),
                )
                timestamp += 1


def actual_usb_fixture(tmp_path):
    runtime, camera = runtime_and_adapter(tmp_path, ready=False)
    _modeled_ready(runtime, camera)
    adapter = M1PhysicalUsbIdentityPersistence(
        runtime,
        workspace_source_sha256=SOURCE,
        stage_policy=POLICY,
        expected_usb_query_policy_sha256=POLICY.sha256,
        admission_facts=usb_facts,
    )
    return runtime, camera, adapter


def actual_request(adapter, key="actual-usb-one"):
    request = RegisteredActionRequest(
        CELL, SESSION, USB_IDENTITY_ACTION_ID, key, "1" * 64
    )
    with adapter.transaction(LEASES) as tx:
        request = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )
    return request


def root_for(runtime, leaf):
    return (
        runtime.deployment_root
        / "cells"
        / ("cell-" + runtime.cell.cell_key_sha256)
        / leaf
    )


@WINDOWS
def test_actual_m1_usb_camera_coexistence_readback_restart_and_sibling_tamper(tmp_path):
    runtime, camera, adapter = actual_usb_fixture(tmp_path)
    core, worker = usb_core(adapter)
    permit = core.prepare(actual_request(adapter))
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_KNOWN, (result, worker.error)
    assert worker.calls == 1 and result.receipt.final_power_state.value == "UNKNOWN"
    assert len(runtime._attempts.snapshot().events) == 5
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert tx.read_campaign_result(permit.attempt_id) == result
        assert tx.read_campaign_evidence(permit.attempt_id)[0].payload == PAYLOAD
        assert (
            tx.read_campaign_admission_evidence(permit.attempt_id)
            == usb_facts().retained_documents()
        )
        assert len(tx._audit_records()) == 5
    with pytest.raises(CommissioningCoordinatorError):
        worker.authority.revalidate(permit)
    # Explicit modeled transition only, NOT a production stage-4 acceptance.
    with camera.stage_transaction(
        SESSION, expected_challenge_sha256=camera.verification(SESSION).challenge_sha256
    ) as tx:
        assert tx._audit_records() == {}
        ref = tx.store_evidence(
            STAGE,
            PAYLOAD,
            label="modeled USB stage fixture",
            media_type="application/json",
            captured_at_ns=3000,
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
        for state, timestamp in (
            (V2StageState.REVIEW_PENDING, 3001),
            (V2StageState.PASS, 3002),
        ):
            tx.commit_stage_state(
                STAGE,
                state,
                occurred_at_ns=timestamp,
                detail_code="MODELED_NO_QUALIFICATION",
                expected_head_sha256=tx.snapshot().head.head_sha256,
                evidence=(ref,),
            )
        tx.commit_stage_state(
            PhysicalOnboardingStage.CAMERA_MODE_CONTROLS,
            V2StageState.WAITING_OPERATOR,
            occurred_at_ns=3003,
            detail_code="MODELED_CAMERA_FOLLOWUP",
            expected_head_sha256=tx.snapshot().head.head_sha256,
        )
    camera_core, camera_worker, camera_request = core_and_request(
        camera, key="different-camera-request"
    )
    camera_permit = camera_core.prepare(camera_request)
    camera_result = camera_core.execute(camera_permit)
    assert camera_result.state is AttemptState.SEALED_KNOWN, (
        camera_result,
        camera_worker.error,
    )
    assert len(runtime._attempts.snapshot().events) == 10
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        assert tx.read_campaign_result(permit.attempt_id) == result
        assert len(tx._audit_records()) == 5
        assert len(tx._audit_records(include_family=True)) == 10
    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        cell_id=CELL,
        source_binding_sha256=runtime.source_binding_sha256,
    )
    reader = M1PhysicalUsbIdentityPersistence(
        reopened,
        workspace_source_sha256=SOURCE,
        stage_policy=POLICY,
        expected_usb_query_policy_sha256=POLICY.sha256,
        admission_facts=usb_facts,
    )
    with reader.stage_transaction(
        SESSION, expected_challenge_sha256=reader.verification(SESSION).challenge_sha256
    ) as tx:
        assert tx.read_campaign_result(permit.attempt_id) == result
    new_core, unused_worker = usb_core(reader)
    with pytest.raises(CommissioningCoordinatorError):
        new_core.execute(permit)
    assert unused_worker.calls == 0
    # Tamper only the isolated test copy: legacy camera audit must notice USB.
    path = next(
        root_for(runtime, "physical-usb-identity-records").glob("request-*.json")
    )
    document = json.loads(path.read_bytes())
    document["data"]["admission_evidence"]["hazard_assessment"]["changed"] = True
    document["record_sha256"] = persistence_module._sha256(
        canonical_json_bytes(
            {k: v for k, v in document.items() if k != "record_sha256"}
        )
    )
    path.write_bytes(canonical_json_bytes(document))
    with pytest.raises(M1CommissioningPersistenceError):
        with camera.stage_transaction(
            SESSION,
            expected_challenge_sha256=camera.verification(SESSION).challenge_sha256,
        ):
            pass


@WINDOWS
def test_actual_m1_unknown_counts_retains_bytes_readable_under_quarantine(tmp_path):
    runtime, camera, adapter = actual_usb_fixture(tmp_path)
    core, worker = usb_core(adapter, fault="unknown-counts")
    permit = core.prepare(actual_request(adapter))
    result = core.execute(permit)
    assert result.state is AttemptState.SEALED_UNCERTAIN and result.receipt is None
    assert runtime.verify(SESSION).quarantined
    with adapter.stage_transaction(
        SESSION,
        expected_challenge_sha256=adapter.verification(SESSION).challenge_sha256,
    ) as tx:
        assert tx.read_campaign_result(permit.attempt_id) == result
        assert tx.read_campaign_evidence(permit.attempt_id)[0].payload == PAYLOAD
        assert tx.held_leases == LEASES[:2]
    with camera.stage_transaction(
        SESSION, expected_challenge_sha256=camera.verification(SESSION).challenge_sha256
    ) as tx:
        assert tx._audit_records() == {}
    assert worker.calls == 1
