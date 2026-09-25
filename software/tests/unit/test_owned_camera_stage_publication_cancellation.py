"""Pure application ordering regressions, not real M1/process qualification.

The coordinator, worker and storage below are explicit inert stand-ins. They
model an already-known campaign followed by Stop during the *final stage
transaction's* entry. No ledger is created and no camera/process is launched.
"""

from contextlib import contextmanager
from copy import deepcopy
from pathlib import Path
from types import SimpleNamespace
import threading

import pytest

from rocell.application import commissioning_rehearsal_service as service_module
from rocell.application import owned_camera_rehearsal_campaign as campaign_module
from rocell.application.camera_rehearsal_campaign import camera_settings
from rocell.application.cell_commissioning_coordinator import AttemptResult
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.physical_onboarding_attempts import AttemptState
from rocell.application.wizard_actions import WizardError
from rocell.application.rehearsal_owned_camera_evidence import (
    retain_owned_camera_evidence,
)
from test_rehearsal_owned_camera_evidence import complete_inputs


@pytest.mark.parametrize("stage", STAGE_ORDER[4:6])
@pytest.mark.parametrize("stop_on_final_entry", [True, False])
def test_stop_during_final_stage_transaction_does_not_publish_or_return_preview(
    monkeypatch, tmp_path, stage, stop_on_final_entry
):
    cancellation = threading.Event()
    calls = []
    stored = []
    png = b"\x89PNG\r\n\x1a\nexplicit-inert-fixture"
    capture_document = {"schema": "test.inert_capture_metadata.v1"}
    known = AttemptResult(
        "attempt-" + "1" * 32,
        AttemptState.SEALED_KNOWN,
        "2" * 64,
        (),
        None,
        False,
    )
    # A known result without a real WorkerReceipt is intentional here: this is
    # solely a service-ordering fixture, never supplied to an actual M1 audit.
    # Actual pure retained bytes allow the diagnostic projection to validate its
    # input. The coordinator/store remain inert ordering stand-ins, not M1 proof.
    artifact = retain_owned_camera_evidence(**complete_inputs())
    capture = SimpleNamespace(
        to_dict=lambda: deepcopy(capture_document),
        latest_preview=SimpleNamespace(png_bytes=png),
    )
    fixture_plan = {"process_backend": "OWNED_INCAPABLE_CAMERA_PROCESS"}

    class InertWorker:
        def __init__(self, *args, **kwargs):
            calls.append("worker-constructed")
            self.evidence, self.capture = artifact, capture

        def plan(self):
            return deepcopy(fixture_plan)

        def registration(self, selected_stage):
            assert selected_stage is stage
            return SimpleNamespace(
                action_id="rehearsal-owned-camera-campaign",
                worker_id="incapable-owned-camera-campaign",
            )

    class InertCoordinator:
        def __init__(self, **kwargs):
            assert kwargs["retained_campaign_actions"] == (
                "rehearsal-owned-camera-campaign",
            )

        def prepare(self, request):
            assert not cancellation.is_set()
            assert request.expected_challenge_sha256 == "4" * 64
            calls.append("prepared")
            return request

        def execute(self, permit, *, cancellation):
            assert not cancellation.is_set()
            calls.append("already-known-fixture")
            return known

    @contextmanager
    def admission_transaction(_leases):
        calls.append("admission-entry")
        yield SimpleNamespace(
            verification=lambda: SimpleNamespace(challenge_sha256="4" * 64),
            read_admission=lambda _request: SimpleNamespace(challenge_sha256="4" * 64),
        )

    @contextmanager
    def final_stage_transaction():
        assert calls[-1] == "already-known-fixture"
        calls.append("final-stage-entry")
        if stop_on_final_entry:
            cancellation.set()
        try:
            yield object()
        finally:
            calls.append("final-stage-exit")

    def store_json(tx, stored_stage, value, label):
        stored.append((stored_stage, deepcopy(value), label))
        return SimpleNamespace(evidence_id="test-stage-receipt")

    def forbidden(*args, **kwargs):
        pytest.fail("Pure ordering test must not access a file/device or legacy worker")

    service = service_module.CommissioningRehearsalService(
        tmp_path, tmp_path / "never-created-store", source_sha256="5" * 64
    )
    service._store = SimpleNamespace(
        snapshot=lambda _session: SimpleNamespace(
            next_action=SimpleNamespace(stage=stage)
        ),
        transaction=admission_transaction,
    )
    service._operator = "fixture-operator"
    service._selected = {"endpoint": "incapable-fixture-only"}
    service._camera_settings = {
        "settings": camera_settings(0),
        "settings_epoch": "6" * 64,
    }
    service._cached.update(
        status="ACTIVE_REHEARSAL",
        stage=stage.value,
        stage_state="WAITING_OPERATOR",
        challenge_sha256="4" * 64,
    )
    monkeypatch.setattr(service, "_transaction", final_stage_transaction)
    monkeypatch.setattr(service, "_store_json", store_json)
    monkeypatch.setattr(service, "_refresh", lambda **kwargs: None)
    monkeypatch.setattr(campaign_module, "OwnedBinaryCameraWorker", InertWorker)
    monkeypatch.setattr(
        service_module, "CellCommissioningCoordinator", InertCoordinator
    )
    monkeypatch.setattr(service_module, "SyntheticBinaryCameraWorker", forbidden)
    # _campaign hashes the legacy source before choosing the new worker. Supply
    # inert bytes rather than performing even that unrelated filesystem read.
    monkeypatch.setattr(Path, "read_bytes", lambda _path: b"test-source-only")
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "mkdir", forbidden)
    values = {
        "frame_count": 1,
        "fault": "none",
        "_view_sha256": service_module._hash(service.view()),
    }

    def invoke():
        return service.perform(
            "rehearsal_owned_camera_campaign",
            values,
            cancellation=cancellation,
            progress=lambda _message: None,
        )

    if stop_on_final_entry:
        with pytest.raises(WizardError) as caught:
            invoke()
        assert caught.value.code == "REHEARSAL_CANCELLED_BEFORE_PUBLICATION"
        assert "camera stage receipt retention" in str(caught.value)
        assert stored == []
        assert service._receipt_reference is None
        assert service.latest_preview() is None
        assert service.view()["capture_dataset"] is None
        assert service.view()["camera_process"] is None
        assert service.view()["status"] == "HELD"
        assert service.view()["stage"] == stage.value
        assert service.view()["stage_state"] == "WAITING_OPERATOR"
        assert service._failed
        # Cancellation does not rewrite the already-observed known campaign.
        assert service._receipt["attempt_result"]["state"] == "SEALED_KNOWN"
        assert service._receipt["retained_campaign_sha256"] == artifact.evidence_sha256
        assert known.state is AttemptState.SEALED_KNOWN
        assert not known.quarantine_latched
        assert service._camera_process_diagnostic["attempt_result"]["state"] == (
            "SEALED_KNOWN"
        )
        assert service.blocked_reason("rehearsal_owned_camera_campaign") is not None
        # A new request cannot replay the stand-in worker after this local hold.
        cancellation.clear()
        fresh_values = {**values, "_view_sha256": service_module._hash(service.view())}
        with pytest.raises(WizardError) as repeated:
            service.perform(
                "rehearsal_owned_camera_campaign",
                fresh_values,
                cancellation=cancellation,
                progress=lambda _message: None,
            )
        assert repeated.value.code == "REHEARSAL_ACTION_BLOCKED"
    else:
        result = invoke()
        assert result["status"] == "SUCCEEDED"
        assert result["physical_authority"] is False
        assert len(stored) == 1
        assert stored[0][0] is stage
        assert stored[0][1]["attempt_result"]["state"] == "SEALED_KNOWN"
        assert service._receipt_reference.evidence_id == "test-stage-receipt"
        assert service.latest_preview() == png
        assert not service._failed

    assert calls.count("worker-constructed") == 1
    assert calls.count("prepared") == 1
    assert calls.count("already-known-fixture") == 1
    assert calls.count("final-stage-entry") == 1
    assert calls[-1] == "final-stage-exit"
