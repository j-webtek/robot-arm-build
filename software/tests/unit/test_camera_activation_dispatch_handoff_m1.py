"""V2 production dispatch wrapper with actual NTFS/M1 retention and OS leases.

Predecessor evidence, current identity, software approval and process facts are
explicit test models. Only the real store, core, parsers and data handoff are
under test; no native helper, camera, arm, or physical qualification is used.
"""

import os

import pytest

from rocell.application import physical_camera_dispatch as dispatch
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    M1PhysicalCameraTransaction,
    PhysicalCameraAdmissionFacts,
    physical_camera_source_binding,
)
from rocell.application.commissioning_m1_persistence import (
    M1CommissioningPersistenceError,
)
from rocell.application.physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
)
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from test_camera_activation_application_handoff import no_device_calls
from test_camera_activation_dispatch_handoff import install_owner, perform
from test_commissioning_camera_persistence import runtime_and_adapter
import test_commissioning_camera_persistence as storage_fixture
from test_native_camera_activation_supervisor import no_physical_owner
from test_physical_camera_activation_campaign import campaign
from test_physical_camera_coordinator import CELL, SESSION, SOURCE, LEASES
from test_physical_camera_dispatch import RecordingSink


pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(os.name != "nt", reason="actual Windows leases/NTFS"),
]


@pytest.mark.parametrize(
    "purpose,fault", [("probe", None), ("capture", None), ("probe", "bad-result")]
)
def test_production_v2_dispatch_original_pair_survives_reopen(
    tmp_path, monkeypatch, purpose, fault
):
    plan = campaign(tmp_path, purpose).plan()
    monkeypatch.setattr(
        storage_fixture, "STAGE", campaign(tmp_path, purpose).registration().stage
    )
    runtime, _ = runtime_and_adapter(tmp_path)
    plan["assigned_parent_directory"] = str(
        runtime.deployment_root / "native-camera-output"
    )
    worker = PhysicalCameraActivationCampaign.from_plan(plan)

    def modeled_facts(request, snapshot):
        return PhysicalCameraAdmissionFacts(
            {"provenance": "MODELED_DISPATCH_CONTEXT_NOT_PHYSICAL_ADMISSION"},
            tuple({"modeled_epoch": i} for i in range(8)),
            plan["selection"],
        )

    adapter = M1PhysicalCameraPersistence(
        runtime, workspace_source_sha256=SOURCE, admission_facts=modeled_facts
    )
    owners = install_owner(tmp_path, monkeypatch, purpose=purpose, fault=fault)
    owner = dispatch.PhysicalCameraDispatchOwner(
        adapter, worker, revalidate_context=lambda: None
    )
    reads = []
    for name in (
        "read_campaign_permit",
        "read_campaign_result",
        "read_camera_activation_evidence",
    ):
        original = getattr(M1PhysicalCameraTransaction, name)

        def read(transaction, attempt, *, original=original, name=name):
            assert transaction.held_leases in (LEASES, LEASES[:2])
            value = original(transaction, attempt)
            reads.append((name, transaction, value))
            return value

        monkeypatch.setattr(M1PhysicalCameraTransaction, name, read)

    class Sink(RecordingSink):
        def check_exited(self):
            assert [item[0] for item in reads] == [
                "read_campaign_permit",
                "read_campaign_result",
                "read_camera_activation_evidence",
            ]
            assert len({id(item[1]) for item in reads}) == 1
            for _, transaction, _ in reads:
                with pytest.raises(
                    M1CommissioningPersistenceError, match="scope has ended"
                ):
                    transaction._check_scope()
            assert not runtime.verify(SESSION).active_lease_owners

        def accept_retained_probe(self, *args, **kwargs):
            self.check_exited()
            super().accept_retained_probe(*args, **kwargs)

        def stage_retained_capture(self, *args, **kwargs):
            self.check_exited()
            super().stage_retained_capture(*args, **kwargs)

    sink = Sink()
    if fault is None:
        assert perform(owner, sink)["status"] == "SUCCEEDED"
        assert len(sink.received) == 1
    else:
        with pytest.raises(ValueError, match="NOT_KNOWN"):
            perform(owner, sink)
        assert not sink.received and sink.invalidations == 1
    assert len(owners) == 1
    permit, result, evidence = [item[2] for item in reads]
    assert len(evidence) == 2
    assert result.quarantine_latched == (fault is not None)
    if fault:
        assert result.receipt is None
    else:
        assert result.receipt.evidence_sha256s == tuple(
            item.payload_sha256 for item in evidence
        )
    assert owner.retained_diagnostics()["original_evidence"] is not None
    assert owner.retained_diagnostics()["readback_scope"] == "EXITED"

    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        cell_id=CELL,
    )
    fresh = M1PhysicalCameraPersistence(
        reopened, workspace_source_sha256=SOURCE, admission_facts=modeled_facts
    )
    with fresh.transaction(LEASES) as tx:
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert tx.read_campaign_result(permit.attempt_id) == result
        assert tx.read_camera_activation_evidence(permit.attempt_id) == evidence
    assert not reopened.verify(SESSION).active_lease_owners
    assert len(owners) == 1
