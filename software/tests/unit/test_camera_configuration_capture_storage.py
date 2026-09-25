"""Actual NTFS/M1 leases, incapable native producer and modeled admission.

The synthetic predecessor is storage-only evidence. These tests cannot admit
the public wizard or establish real camera/settings qualification.
"""

from dataclasses import replace

import pytest

from rocell.application.camera_activation_campaign_contract import (
    CONFIGURATION_CAPTURE_ACTION_ID,
    CONFIGURATION_CAPTURE_WORKER_ID,
    validate_camera_activation_binding,
)
from rocell.application.cell_commissioning_coordinator import (
    PhysicalCameraAcquisitionCoordinator,
    CommissioningCoordinatorError,
)
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    verify_camera_admission_evidence,
)
from rocell.application.physical_onboarding import PhysicalOnboardingStage
from rocell.application.physical_onboarding_attempts import AttemptState
from test_camera_activation_campaign_contract import profile
from test_camera_activation_original_storage import (
    actual_components,
    reopen,
    facts,
    SOURCE,
    SESSION,
    LEASES,
    WINDOWS,
    forbid_device_and_process_calls,
    no_physical_owner,
)


@WINDOWS
@pytest.mark.parametrize("fault", [None, "bad-result"])
def test_stage5_settings_capture_full_pair_facts_and_no_replay_after_reopen(
    tmp_path, monkeypatch, fault
):
    import test_camera_activation_original_storage as fixture

    item = replace(
        profile("capture"),
        action_id=CONFIGURATION_CAPTURE_ACTION_ID,
        worker_id=CONFIGURATION_CAPTURE_WORKER_ID,
        stage=PhysicalOnboardingStage.CAMERA_MODE_CONTROLS,
    )
    monkeypatch.setattr(fixture, "profile", lambda purpose: item)
    runtime, _, _, worker, request = actual_components(
        tmp_path, monkeypatch, "capture", fault
    )

    def scoped(tx, action, snapshot):
        assert tx.held_leases == LEASES
        assert tx.snapshot() == snapshot
        return facts(action, snapshot)  # Explicitly INCAPABLE_CONTRACT_TEST.

    adapter = M1PhysicalCameraPersistence(
        runtime, workspace_source_sha256=SOURCE, scoped_admission_facts=scoped
    )
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=adapter,
        registrations=(item,),
        workers={item.worker_id: worker},
        retained_campaign_actions=(item.action_id,),
        scoped_campaign_actions=(item.action_id,),
        monotonic_ns=worker.clock,
    )
    permit = core.prepare(request)
    result = core.execute(permit)
    assert permit.admission.stage is PhysicalOnboardingStage.CAMERA_MODE_CONTROLS
    assert result.state is (
        AttemptState.SEALED_KNOWN if fault is None else AttemptState.SEALED_UNCERTAIN
    )
    assert (result.receipt is None) == (fault is not None)
    assert result.physical_authority == "NONE" and worker.calls == 1
    fresh_runtime, fresh = reopen(runtime)
    with fresh.transaction(LEASES) as tx:
        assert tx.read_campaign_permit(permit.attempt_id) == permit
        assert tx.read_campaign_result(permit.attempt_id) == result
        evidence = tx.read_camera_activation_evidence(permit.attempt_id)
        assert evidence == worker.execution.evidence
        validate_camera_activation_binding(permit, evidence)
        original = tx.read_campaign_admission_evidence(permit.attempt_id)
        verify_camera_admission_evidence(original, permit)
        assert original == facts(request, tx.snapshot()).retained_documents()
    assert not fresh_runtime.verify(SESSION).active_lease_owners
    assert core.execute(permit) == result and worker.calls == 1
    reopened_core = PhysicalCameraAcquisitionCoordinator(
        persistence=fresh,
        registrations=(item,),
        workers={item.worker_id: worker},
        retained_campaign_actions=(item.action_id,),
        scoped_campaign_actions=(item.action_id,),
        monotonic_ns=worker.clock,
    )
    with pytest.raises(CommissioningCoordinatorError, match="unknown"):
        reopened_core.execute(permit)
    assert worker.calls == 1
