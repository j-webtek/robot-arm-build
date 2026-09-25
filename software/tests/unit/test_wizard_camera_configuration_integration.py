"""Real NTFS retained probe -> config -> capture -> reopen, with no hardware.

Only the fixed incapable Job child is available. Stage evidence is collected
normally; no cloned ledger, injected PASS, automatic repair or replay is used.
"""

import base64
import json
import os
from pathlib import Path

import pytest

from rocell.application.commissioning_rehearsal_service import (
    CommissioningRehearsalService,
)
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application import commissioning_rehearsal_service as service_module
from rocell.application import owned_camera_probe_campaign as probe_module
from rocell.application import owned_camera_rehearsal_campaign as capture_module
from rocell.providers.windows import camera_worker_client as camera_module
from test_commissioning_rehearsal_service import invoke, collect, assess_review
from test_wizard_owned_camera_integration import retained


WORKSPACE = Path(__file__).resolve().parents[3]
pytestmark = [
    pytest.mark.slow,
    pytest.mark.skipif(os.name != "nt", reason="Actual Job process and NTFS M1"),
]


def reopen(service, name):
    restored = CommissioningRehearsalService(
        WORKSPACE, service.directory.parent / name, source_sha256=service.source_sha256
    )
    invoke(restored, "discover")
    choices = restored.reopen_choices()
    assert len(choices) == 1
    result = invoke(restored, "reopen", choice_id=choices[0]["choice_id"])
    assert result["status"] == "SUCCEEDED", restored.view()
    assert (
        restored.directory == service.directory
        and restored.session_id == service.session_id
    )
    return restored


def test_actual_probe_configuration_capture_review_reopen_and_stage_six_reuse(
    tmp_path, monkeypatch
):
    def forbidden(*args, **kwargs):
        pytest.fail("No hardware, default subprocess or legacy fallback is available")

    monkeypatch.setattr(service_module, "SyntheticBinaryCameraWorker", forbidden)
    monkeypatch.setattr(camera_module.subprocess, "Popen", forbidden)
    for name in ("enumerate_metadata", "resolve_identity_metadata"):
        monkeypatch.setattr(camera_module.WindowsCameraWorkerClient, name, forbidden)
    calls = {"probe": 0, "capture": 0}
    original_probe = probe_module.OwnedCameraProbeWorker.run_retained_campaign
    original_capture = capture_module.OwnedBinaryCameraWorker.run_retained_campaign

    def probe_call(self, *args, **kwargs):
        calls["probe"] += 1
        return original_probe(self, *args, **kwargs)

    def capture_call(self, *args, **kwargs):
        calls["capture"] += 1
        return original_capture(self, *args, **kwargs)

    monkeypatch.setattr(
        probe_module.OwnedCameraProbeWorker, "run_retained_campaign", probe_call
    )
    monkeypatch.setattr(
        capture_module.OwnedBinaryCameraWorker, "run_retained_campaign", capture_call
    )
    source = source_fingerprint(WORKSPACE)
    print("configuration M1 source", source, flush=True)
    service = CommissioningRehearsalService(
        WORKSPACE, tmp_path / "configured-store", source_sha256=source
    )
    invoke(service, "initialize")
    for index in range(4):
        print("configuration M1 prerequisite", index + 1, flush=True)
        collect(service)
        assess_review(service)
    collect(service)
    assert source_fingerprint(WORKSPACE) == source
    print("configuration M1 actual finite probe", flush=True)
    probe_result = invoke(service, "camera_probe", fault="none")
    assert probe_result["status"] == "SUCCEEDED", service.view()
    probe_view = service.view()["camera_configuration"]
    assert probe_view["status"] == "PROBE_COMPLETE"
    assert len(probe_view["capabilities"]["controls"]) == 6
    assert service._receipt is None and service.latest_preview() is None
    assert service.blocked_reason("rehearsal_camera_probe")
    assert service.blocked_reason("rehearsal_camera_campaign")
    assert service.blocked_reason("rehearsal_owned_camera_campaign")
    assert calls == {"probe": 1, "capture": 0}
    print("configuration M1 partial probe-only reopen", flush=True)
    service = reopen(service, "unused-after-probe")
    assert service.view()["camera_configuration"] == probe_view
    assert service.view()["stage_state"] == "WAITING_OPERATOR"
    assert calls == {"probe": 1, "capture": 0}
    fields = service.camera_configuration_fields()
    values = {field["name"]: field["default"] for field in fields if "default" in field}
    values.update(
        mode_choice_id=fields[0]["options"][0]["value"],
        gain_mode="manual",
        gain_value=32,
        exposure_mode="auto",
    )
    invoke(service, "camera_configuration", **values)
    staged = service.view()["camera_configuration"]
    assert staged["status"] == "CONFIGURATION_STAGED" and staged["readback"] is None
    assert staged["candidate"]["applied"] is False
    assert calls == {"probe": 1, "capture": 0}
    print("configuration M1 configured capture", flush=True)
    result = invoke(service, "owned_camera_campaign", frame_count=1, fault="none")
    assert result["status"] == "SUCCEEDED", service.view()
    projection = service.view()["camera_configuration"]
    assert projection["status"] == "READBACK_COMPLETE"
    assert projection["readback"]["status"] == "REQUESTED_SETTINGS_OBSERVED_REHEARSAL"
    assert all(row["matched"] for row in projection["readback"]["controls"])
    document, records = retained(service)
    assert len(document["activation_request"]["controls"]) == 2
    assert document["native_receipt"]["counts"]["control_set_attempts"] == 2
    wire = json.loads(base64.b64decode(document["stdout"]["data"]))
    assert wire["schema"] == "rocell.owned_camera_fixture_result.v2"
    assert (
        document["binding"]["settings_epoch"]
        == service._configuration_receipt["effective_settings_epoch"]
    )
    assert (
        document["binding"]["settings_epoch"] != staged["candidate"]["settings_epoch"]
    )
    assert document["error"] is None
    invoke(service, "assess")
    assert service.view()["assessment"]["outcome"] == "PASS"
    print("configuration M1 exact pending-review reopen", flush=True)
    service = reopen(service, "unused-after-capture")
    assert service.view()["camera_configuration"] == projection
    assert service.latest_preview() is None
    assert calls == {"probe": 1, "capture": 1}
    invoke(service, "review", reviewer_id="reviewer-b", accept_assessment=True)
    collect(service)
    assert service.view()["camera_configuration"]["readback"] is None
    assert service.view()["camera_configuration"]["candidate"] == staged["candidate"]
    assert service.blocked_reason("rehearsal_camera_configuration")
    print("configuration M1 stage-six exact configuration reuse", flush=True)
    result = invoke(service, "owned_camera_campaign", frame_count=1, fault="none")
    assert result["status"] == "SUCCEEDED", service.view()
    assess_review(service)
    assert calls == {"probe": 1, "capture": 2}
    assert service.view()["stage"] == "optics_intrinsics"
    assert service.view()["physical_authority"] is False
    assert source_fingerprint(WORKSPACE) == source
    print(
        "configuration M1 complete; physical camera and arm still unqualified",
        flush=True,
    )
