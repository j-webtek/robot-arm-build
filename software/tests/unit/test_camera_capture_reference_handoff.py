"""Real file ingestion and capture-time candidate; durable retention is NOT tested."""

from threading import Event

import pytest

from rocell.application import camera_capture_reference as module
from rocell.application.camera_operating_evidence_preflight import (
    CameraNativeEvidenceSubject,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.camera_worker_client import CameraWorkerError
from test_camera_activation_application_handoff import (
    workflow_fixture,
    write_pixels,
    accept,
    PIXELS,
    no_device_calls,
)
from test_native_camera_activation_supervisor import no_physical_owner

KEY = "operation-" + "6" * 32


def test_reference_uses_this_owned_ingestion_hash_and_native_originals(
    tmp_path, monkeypatch
):
    f = workflow_fixture(tmp_path, monkeypatch, configuration_verification=True)
    write_pixels(f)
    result = accept(
        f, configuration_verification=True, capture_reference_request_key=KEY
    )
    candidate = f.workflow.retained_diagnostics()["capture_reference_candidate"]
    assert candidate["retention"] == "LAUNCH_DIAGNOSTIC_ONLY_NOT_M1_ORIGINAL"
    reference = module.verify_capture_reference(
        canonical(candidate["document"]),
        expected_reference_sha256=candidate["sha256"],
        expected_request_key=KEY,
        native=CameraNativeEvidenceSubject(
            f.capture,
            f.evidence,
            f.evidence[0].payload_sha256,
            f.evidence[1].payload_sha256,
        ),
        configuration_payload=f.configuration.payload,
        expected_settings_epoch=f.configuration.settings_epoch,
    )
    assert reference.to_dict()["frame"]["sha256"] == digest(PIXELS)
    assert reference.to_dict()["manifest_sha256"] == result.dataset.manifest_sha256
    assert reference.to_dict()["ingest_envelope_sha256"] == result.envelope_sha256
    assert reference.to_dict()["frame"]["length_bytes"] == 16
    assert f.workflow.view()["status"] == "CONTENT_VERIFIED"
    assert not reference.to_dict()["original_store_authenticated"]


def test_historical_ingestion_without_request_binding_does_not_invent_reference(
    tmp_path, monkeypatch
):
    f = workflow_fixture(tmp_path, monkeypatch)
    write_pixels(f)
    accept(f)
    assert "capture_reference_candidate" not in f.workflow.retained_diagnostics()


@pytest.mark.parametrize("key", ["../../somewhere", "", True, "a" * 65])
def test_invalid_reference_key_fails_before_any_pixel_files(tmp_path, monkeypatch, key):
    f = workflow_fixture(tmp_path, monkeypatch, configuration_verification=True)
    with pytest.raises(ValueError, match="EXACT_CAPTURE_REFERENCE_REQUEST_REQUIRED"):
        accept(f, configuration_verification=True, capture_reference_request_key=key)
    assert "capture_reference_candidate" not in f.workflow.retained_diagnostics()
    assert f.workflow.last_preview() is None


def test_reference_cannot_be_requested_on_general_capture_route(tmp_path, monkeypatch):
    f = workflow_fixture(tmp_path, monkeypatch)
    with pytest.raises(ValueError, match="EXACT_CAPTURE_REFERENCE_REQUEST_REQUIRED"):
        accept(f, capture_reference_request_key=KEY)


@pytest.mark.parametrize("fault", ["short", "reference_failure", "late_stop"])
def test_failed_or_late_capture_never_publishes_current_pixels(
    tmp_path, monkeypatch, fault
):
    f = workflow_fixture(tmp_path, monkeypatch, configuration_verification=True)
    write_pixels(f, PIXELS[:-1] if fault == "short" else PIXELS)
    stopped = Event()
    build = module.build_capture_reference

    def changed(*a, **kw):
        if fault == "reference_failure":
            raise module.CameraCaptureReferenceError()
        result = build(*a, **kw)
        if fault == "late_stop":
            stopped.set()
        return result

    monkeypatch.setattr(module, "build_capture_reference", changed)
    with pytest.raises(CameraWorkerError if fault == "short" else ValueError):
        accept(
            f,
            configuration_verification=True,
            capture_reference_request_key=KEY,
            cancellation=stopped,
        )
    assert f.workflow.view()["status"] == "HELD" and f.workflow.last_preview() is None
    candidate = f.workflow.retained_diagnostics().get("capture_reference_candidate")
    assert (candidate is not None) is (fault == "late_stop")
    if candidate:
        assert candidate["retention"] == "LAUNCH_DIAGNOSTIC_ONLY_NOT_M1_ORIGINAL"
        assert candidate["document"]["physical_authority"] is False


def test_failed_new_attempt_does_not_relabel_an_old_candidate(tmp_path, monkeypatch):
    f = workflow_fixture(tmp_path, monkeypatch, configuration_verification=True)
    write_pixels(f)
    accept(f, configuration_verification=True, capture_reference_request_key=KEY)
    old = f.workflow.retained_diagnostics()["capture_reference_candidate"]
    original = f.workflow
    staged = original.staged_copy()
    # Real service uses a staged copy. An early failed new call must not carry
    # the previous reference into its diagnostics; the original stays intact.
    f.workflow = staged
    with pytest.raises(ValueError):
        accept(
            f,
            configuration_verification=True,
            capture_reference_request_key="invalid/path",
        )
    assert "capture_reference_candidate" not in staged.retained_diagnostics()
    assert old["document"]["request_key"] == KEY
    assert original.retained_diagnostics()["capture_reference_candidate"] == old
