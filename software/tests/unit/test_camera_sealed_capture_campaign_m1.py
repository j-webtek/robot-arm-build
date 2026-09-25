"""Actual producer/guarded pixels/M1 reopening with incapable native admission.

The original setup/source/runtime qualifications are modeled, not bypassed in
the public wizard. The campaign, consumed scope, file reader, immutable storage,
receipt sealing and fresh-store readback below are real production code.
"""

from dataclasses import replace
from pathlib import Path

import pytest

from rocell.application import physical_camera_activation_campaign as campaign_module
from rocell.application.camera_sealed_capture_evidence import (
    SealedCameraCaptureEvidence,
)
from rocell.application.cell_commissioning_coordinator import (
    PhysicalCameraAcquisitionCoordinator,
    RegisteredActionRequest,
)
from rocell.application.commissioning_camera_persistence import (
    M1PhysicalCameraPersistence,
    PhysicalCameraAdmissionFacts,
    physical_camera_source_binding,
)
from rocell.application.physical_camera_activation_campaign import (
    PhysicalCameraActivationCampaign,
)
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.physical_onboarding_m1 import PhysicalOnboardingM1Runtime
from rocell.providers.windows import native_camera_activation_supervisor as supervisor
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_activation_application_handoff import PIXELS
from test_commissioning_camera_persistence import (
    runtime_and_adapter,
    WINDOWS,
    forbid_device_and_process_calls,
)
import test_commissioning_camera_persistence as original_fixture
from test_native_camera_activation_evidence import modeled
from test_native_camera_activation_registration import ready
from test_native_camera_activation_protocol import fixture as result_fixture
from test_native_camera_activation_supervisor import ModelOwner, no_physical_owner
from test_physical_camera_activation_campaign import campaign
from test_physical_camera_coordinator import CELL, SESSION, SOURCE, LEASES

pytestmark = [WINDOWS, pytest.mark.slow]


@pytest.mark.parametrize("pixels", [True, False])
def test_owned_capture_real_original_retention_and_fresh_readback(
    tmp_path, monkeypatch, pixels
):
    worker = campaign(
        tmp_path,
        "capture",
        configuration_verification=True,
        sealed_configuration_capture=True,
    )
    monkeypatch.setattr(original_fixture, "STAGE", worker.registration().stage)
    runtime, _ = runtime_and_adapter(tmp_path)
    plan = worker.plan()
    plan["assigned_parent_directory"] = str(
        runtime.deployment_root / "native-camera-output"
    )
    worker = PhysicalCameraActivationCampaign.from_plan(plan)

    def modeled_facts(request, snapshot):
        return PhysicalCameraAdmissionFacts(
            {"provenance": "INCAPABLE_PRODUCER_STORAGE_TEST", "source_sha256": SOURCE},
            tuple({"epoch": i, "source_sha256": SOURCE} for i in range(8)),
            plan["selection"],
        )

    store = M1PhysicalCameraPersistence(
        runtime,
        workspace_source_sha256=SOURCE,
        admission_facts=modeled_facts,
    )
    worker._bind_application_guard(lambda: None)
    monkeypatch.setattr(campaign_module, "source_fingerprint", lambda _: SOURCE)
    monkeypatch.setattr(
        campaign_module, "verify_reviewed_activation_runtime", lambda *a, **k: {}
    )
    reg = worker.registration()
    core = PhysicalCameraAcquisitionCoordinator(
        persistence=store,
        registrations=(reg,),
        workers={reg.worker_id: worker},
        retained_campaign_actions=(reg.action_id,),
        scoped_campaign_actions=(reg.action_id,),
    )
    request = RegisteredActionRequest(
        CELL, SESSION, reg.action_id, "owned-sealed-original", "1" * 64
    )
    with store.transaction(LEASES) as tx:
        request = replace(
            request,
            expected_challenge_sha256=tx.read_admission(request).challenge_sha256,
        )
    permit = core.prepare(request)
    prepared = worker.preparation_for_permit(permit)
    raw_owner, args = modeled(tmp_path, "capture")
    args["ready_wire"] = ready(prepared)
    _, _, raw = result_fixture("capture")
    raw.update(
        request_sha256=prepared.admission_request.request_sha256,
        permit_sha256=permit.permit_sha256,
    )
    raw_owner.stdout = args["ready_wire"] + canonical(raw) + b"\n"
    owner = ModelOwner(raw_owner, args)
    cleanup = owner.cleanup
    path = Path(prepared.camera_plan.request.output_directory) / "frame-000000.yuy2"
    calls = []

    def complete(deadline):
        result = cleanup(deadline)
        if pixels:
            path.parent.mkdir(parents=True)
            path.write_bytes(PIXELS)
        return result

    def new_owner():
        calls.append("MODELED_NATIVE_OWNER")
        return owner

    owner.cleanup = complete
    monkeypatch.setattr(supervisor, "_new_owner", new_owner)
    result = core.execute(permit)
    assert result.state is (
        AttemptState.SEALED_KNOWN if pixels else AttemptState.SEALED_UNCERTAIN
    ), result
    assert owner.cleaned and calls == ["MODELED_NATIVE_OWNER"]
    assert type(worker.evidence) is SealedCameraCaptureEvidence
    expected = worker.evidence
    assert result.receipt.evidence_sha256s == expected.evidence_sha256s
    assert result.receipt.opens == result.receipt.frames == result.receipt.closes == 1
    assert result.receipt.cleanup_confirmed is pixels
    reopened = PhysicalOnboardingM1Runtime.open(
        runtime.deployment_root,
        source_binding_sha256=physical_camera_source_binding(SOURCE),
        cell_id=CELL,
    )
    fresh = M1PhysicalCameraPersistence(
        reopened,
        workspace_source_sha256=SOURCE,
        admission_facts=modeled_facts,
    )
    with fresh.transaction(LEASES) as tx:
        assert tx.read_campaign_result(permit.attempt_id) == result
        retained = tx.read_camera_activation_evidence(permit.attempt_id)
        assert retained == expected
        if pixels:
            assert retained.checksum.to_dict()["frame"]["sha256"] == digest(
                path.read_bytes()
            )
        else:
            assert retained.checksum.to_dict()["status"] == "PIXEL_READ_FAILED"
    assert core.execute(permit) == result and calls == ["MODELED_NATIVE_OWNER"]
    assert not reopened.verify(SESSION).active_lease_owners
