"""Public dispatch owner with actual NTFS/M1 storage, never a native camera.

The original predecessor stages, source and identity facts are explicitly
modeled storage inputs from runtime_and_adapter. The only runner is the sealed
test-only modeled packet producer. No C++ helper, device, acquired pixel file,
received-hardware acceptance or production runtime release is exercised.
"""

from contextlib import contextmanager
import os
import subprocess
import threading

import pytest

from rocell.application import physical_camera_dispatch as module
from rocell.application.cell_commissioning_coordinator import ObservedPowerState
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    M1PhysicalCameraTransaction,
    PhysicalCameraAdmissionFacts,
    physical_camera_source_binding,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.physical_native_camera_campaign import (
    PhysicalNativeCameraCampaign,
    verify_physical_native_camera_campaign_evidence,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
from rocell.providers.windows.owned_native_camera_evidence import (
    OwnedNativeCameraRunEvidence,
)
from rocell.safety.effects import EffectCertainty

from test_commissioning_camera_persistence import facts, runtime_and_adapter
from test_native_camera_bounded_effect import install_modeled_effect_runner
from test_physical_camera_coordinator import CELL, LEASES, SESSION, SOURCE
from test_physical_camera_dispatch import RecordingSink
from test_physical_camera_selection import physical_enrollment
from test_physical_native_camera_campaign import arguments


pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(os.name != "nt", reason="actual qualified NTFS and OS leases"),
]


@pytest.fixture(autouse=True)
def no_native_or_process(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("public dispatch storage test attempted a process or device")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    for name in ("enumerate_metadata", "resolve_identity_metadata", "probe", "capture"):
        monkeypatch.setattr(WindowsCameraWorkerClient, name, forbidden)
    # Windows filesystem/lease APIs remain real; do not replace their DLLs.
    monkeypatch.setattr(module, "source_fingerprint", lambda path: SOURCE)


def original_dispatch(tmp_path, monkeypatch, *, fault=None):
    runtime, adapter = runtime_and_adapter(tmp_path)
    args, kwargs = arguments(tmp_path)
    campaign = PhysicalNativeCameraCampaign(args[0], runtime.deployment_root, **kwargs)
    modeled = facts(None, None)

    def selected_facts(request, snapshot):
        assert snapshot.header.session_id == SESSION
        return PhysicalCameraAdmissionFacts(
            modeled.hazard_assessment_document,
            modeled.configuration_epoch_documents,
            campaign.plan()["selection"],
        )

    adapter._facts = selected_facts
    calls = install_modeled_effect_runner(monkeypatch, fault=fault)
    owner = module.PhysicalCameraDispatchOwner(
        adapter, campaign, revalidate_context=lambda: None
    )
    reads = []
    for name in (
        "read_campaign_permit",
        "read_campaign_result",
        "read_campaign_evidence",
    ):
        original = getattr(M1PhysicalCameraTransaction, name)

        def read(transaction, attempt_id, *, original=original, name=name):
            assert transaction.held_leases in (LEASES, LEASES[:2])
            value = original(transaction, attempt_id)
            reads.append((name, transaction, value))
            return value

        monkeypatch.setattr(M1PhysicalCameraTransaction, name, read)
    return runtime, adapter, campaign, calls, owner, reads, selected_facts


def perform(owner, sink):
    return owner.perform(
        request_key="actual-ntfs-modeled-native-once",
        sink=sink,
        enrollment=physical_enrollment(),
        cancellation=threading.Event(),
    )


class LeaseExitRecordingSink(RecordingSink):
    """Records only; deliberately does not claim ingestion or image publication."""

    def __init__(self, runtime, reads):
        super().__init__()
        self.runtime, self.reads = runtime, reads

    def accept_retained_probe(self, enrollment, evidence, **kwargs):
        assert [item[0] for item in self.reads] == [
            "read_campaign_permit",
            "read_campaign_result",
            "read_campaign_evidence",
        ]
        assert len({id(item[1]) for item in self.reads}) == 1
        for _, transaction, _ in self.reads:
            with pytest.raises(
                M1CommissioningPersistenceError, match="scope has ended"
            ):
                transaction._check_scope()
        verification = self.runtime.verify(SESSION)
        assert not verification.active_lease_owners
        assert not verification.quarantined
        assert evidence.payload == self.reads[2][2][0].payload
        assert kwargs["expected_evidence_sha256"] == self.reads[2][2][0].payload_sha256
        super().accept_retained_probe(enrollment, evidence, **kwargs)


def test_public_owner_known_handoff_uses_originals_after_actual_lease_exit(
    tmp_path, monkeypatch
):
    runtime, adapter, campaign, calls, owner, reads, selected_facts = original_dispatch(
        tmp_path, monkeypatch
    )
    sink = LeaseExitRecordingSink(runtime, reads)
    assert owner.view()["phase"] == "NOT_STARTED" and not calls and not reads
    outcome = perform(owner, sink)
    assert outcome == {"action_id": "physical_camera_probe", "status": "SUCCEEDED"}
    assert len(sink.received) == 1 and sink.invalidations == 0 and len(calls) == 1
    assert owner.view()["phase"] == "PENDING_COMPLETION_LOG"
    assert owner.view()["attempt_state"] == "SEALED_KNOWN"
    permit, result, artifacts = [item[2] for item in reads]
    assert result.state is AttemptState.SEALED_KNOWN
    assert result.permit_sha256 == permit.permit_sha256
    assert (
        permit.admission.selected_identity_sha256
        == campaign.plan()["selected_identity_sha256"]
    )
    assert result.receipt.effect_certainty is EffectCertainty.CONFIRMED
    assert result.receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert result.physical_authority == "NONE"
    assert result.receipt.evidence_sha256s == (artifacts[0].payload_sha256,)
    assert result.receipt.output_bytes == len(artifacts[0].payload)
    assert artifacts[0].label == "physical-native-camera-probe"
    assert campaign.evidence is None  # The public owner detached the input plan.
    prepared = sink.received[0][1]["expected_preparation"]
    assert not (
        runtime.deployment_root / ("native-camera-" + permit.attempt_id)
    ).exists()
    assert not prepared.runtime.to_dict()["dispatch_enabled"]
    assert (
        owner.retained_diagnostics()["original_evidence"]
        == sink.received[0][0].to_dict()
    )

    # A new original-store owner recovers the same bytes without executing again.
    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        cell_id=CELL,
    )
    fresh = M1PhysicalCameraPersistence(
        reopened, workspace_source_sha256=SOURCE, admission_facts=selected_facts
    )
    with fresh.transaction(LEASES) as tx:
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert tx.read_campaign_result(permit.attempt_id) == result
        retained = tx.read_campaign_evidence(permit.attempt_id)
        assert retained == artifacts
    checked = verify_physical_native_camera_campaign_evidence(
        OwnedNativeCameraRunEvidence(retained[0].payload),
        campaign=campaign,
        expected_permit=permit,
        expected_evidence_sha256=retained[0].payload_sha256,
    )
    assert checked.payload == sink.received[0][0].payload
    assert len(calls) == 1 and not reopened.verify(SESSION).active_lease_owners
    with pytest.raises(module.PhysicalCameraDispatchError, match="ALREADY_USED"):
        perform(owner, sink)
    assert len(calls) == 1 and len(sink.received) == 1


@pytest.mark.parametrize("fault", ["native-cleanup", "process-cleanup"])
def test_public_owner_retains_actual_uncertain_seal_without_handoff(
    tmp_path, monkeypatch, fault
):
    runtime, adapter, campaign, calls, owner, reads, _ = original_dispatch(
        tmp_path, monkeypatch, fault=fault
    )
    sink = RecordingSink()
    with pytest.raises(module.PhysicalCameraDispatchError, match="NOT_KNOWN"):
        perform(owner, sink)
    assert [item[0] for item in reads] == [
        "read_campaign_permit",
        "read_campaign_result",
        "read_campaign_evidence",
    ]
    permit, result, original_artifacts = [item[2] for item in reads]
    assert result.state is AttemptState.SEALED_UNCERTAIN
    assert result.quarantine_latched
    assert result.receipt.effect_certainty is EffectCertainty.UNCERTAIN
    assert result.receipt.final_power_state is ObservedPowerState.UNKNOWN
    assert not sink.received and sink.invalidations == 1 and len(calls) == 1
    assert owner.view()["phase"] == "FAILED_NO_REPLAY"
    verified = runtime.verify(SESSION)
    assert verified.quarantined and permit.attempt_id in verified.uncertain_attempt_ids
    assert not verified.active_lease_owners
    with adapter.stage_transaction(
        SESSION, expected_challenge_sha256=verified.challenge_sha256
    ) as tx:
        # Stage-only readback independently preserves diagnostics under quarantine.
        artifacts = tx.read_campaign_evidence(permit.attempt_id)
        assert artifacts == original_artifacts
    evidence = verify_physical_native_camera_campaign_evidence(
        OwnedNativeCameraRunEvidence(artifacts[0].payload),
        campaign=campaign,
        expected_permit=permit,
        expected_evidence_sha256=artifacts[0].payload_sha256,
    )
    document = evidence.to_dict()
    historical = owner.retained_diagnostics()
    assert historical["original_evidence"] == document
    assert historical["transaction"]["attempt_state"] == "SEALED_UNCERTAIN"
    historical["original_evidence"].clear()
    assert owner.retained_diagnostics()["original_evidence"] == document
    if fault == "native-cleanup":
        assert (
            document["validated_result"]["native_receipt"]["cleanup"][
                "source_shutdown_hr"
            ]
            == -1
        )
    else:
        assert document["cleanup_errors"] == ["CLOSE_FAILED:job"]
    assert result.receipt.evidence_sha256s == (evidence.evidence_sha256,)
    with pytest.raises(module.PhysicalCameraDispatchError, match="ALREADY_USED"):
        perform(owner, sink)
    assert len(calls) == 1 and not sink.received


def test_public_owner_actual_readback_exit_failure_prevents_handoff(
    tmp_path, monkeypatch
):
    runtime, adapter, _, calls, owner, reads, _ = original_dispatch(
        tmp_path, monkeypatch
    )
    original = adapter.transaction

    @contextmanager
    def fail_only_after_original_readback(leases):
        with original(leases) as transaction:
            yield transaction
        if reads:
            # Deliberate caller-scope failure after actual OS leases are closed.
            raise OSError("MODELED_READBACK_SCOPE_EXIT_FAILURE")

    monkeypatch.setattr(adapter, "transaction", fail_only_after_original_readback)
    sink = RecordingSink()
    with pytest.raises(OSError, match="MODELED_READBACK_SCOPE_EXIT_FAILURE"):
        perform(owner, sink)
    assert [item[0] for item in reads] == [
        "read_campaign_permit",
        "read_campaign_result",
        "read_campaign_evidence",
    ]
    assert reads[1][2].state is AttemptState.SEALED_KNOWN
    assert not sink.received and sink.invalidations == 1 and len(calls) == 1
    assert owner.view()["phase"] == "FAILED_NO_REPLAY"
    verified = runtime.verify(SESSION)
    assert not verified.active_lease_owners and not verified.quarantined
    with pytest.raises(module.PhysicalCameraDispatchError, match="ALREADY_USED"):
        perform(owner, sink)
    assert len(calls) == 1
