"""Real guarded synthetic files and ingestion; native/original admission modeled."""

from pathlib import Path
from threading import Event

import pytest

from rocell.application import camera_capture_checksum_reader as reader
from rocell.application.camera_capture_checksum import (
    capture_metadata,
    CameraCaptureChecksum,
)
from rocell.application.camera_operating_evidence_preflight import (
    CameraNativeEvidenceSubject,
)
from rocell.application.camera_operating_pixels import (
    verify_sealed_operating_capture_pixels,
)
from rocell.providers.windows.native_camera_protocol import canonical, digest
from rocell.providers.windows.camera_worker_client import CameraWorkerError
from rocell.application.physical_onboarding_durability import (
    PhysicalOnboardingDurabilityError,
)
from test_camera_activation_application_handoff import (
    workflow_fixture,
    write_pixels,
    accept,
    PIXELS,
    no_device_calls,
)
from test_native_camera_activation_supervisor import no_physical_owner

KEY = "operation-" + "7" * 32


@pytest.fixture
def capture(tmp_path, monkeypatch):
    f = workflow_fixture(
        tmp_path,
        monkeypatch,
        configuration_verification=True,
        sealed_configuration_capture=True,
    )
    write_pixels(f)
    checked, _, _ = capture_metadata(f.evidence)
    data = checked.run.to_dict()
    # Native observations use a labeled model clock. The real file reader uses
    # that same modeled epoch here; later ingestion keeps its real file deadline.
    with monkeypatch.context() as patch:
        patch.setattr(reader, "monotonic_ns", lambda: data["finished_ns"] + 1)
        f.checksum = reader._collect_owned_capture_checksum(
            f.evidence,
            request_key=KEY,
            cancellation=Event(),
            deadline_ns=data["parent_deadline_ns"],
        )
    assert f.checksum.to_dict()["status"] == "CAPTURE_BYTES_HASHED"
    f.path = Path(f.capture.camera_plan.request.output_directory) / "frame-000000.yuy2"
    return f


def ingest(f, **kwargs):
    options = dict(
        configuration_verification=True,
        capture_reference_request_key=KEY,
        capture_checksum=f.checksum,
    )
    options.update(kwargs)
    return accept(f, **options)


def test_new_ingestion_compares_earlier_checksum_and_keeps_distinct_diagnostics(
    capture,
):
    result = ingest(capture)
    assert result.verification.content_verified
    assert result.latest_preview.native_sha256 == digest(PIXELS)
    rows = capture.workflow.retained_diagnostics()
    original = rows["capture_checksum"]
    assert original["sha256"] == capture.checksum.sha256
    assert original["document"] == capture.checksum.to_dict()
    assert original["original_stage_record_retained"] is False
    assert (
        rows["capture_reference_candidate"]["retention"]
        == "LAUNCH_DIAGNOSTIC_ONLY_NOT_M1_ORIGINAL"
    )
    assert capture.workflow.view()["last_frame"]["live"] is False
    assert capture.workflow.view()["hardware_qualified"] is False


@pytest.mark.parametrize("fault", ["changed", "missing", "short", "extra"])
def test_changed_pixels_after_checksum_do_not_create_dataset_or_publish(capture, fault):
    if fault == "changed":
        capture.path.write_bytes(bytes([PIXELS[0] ^ 1]) + PIXELS[1:])
    elif fault == "missing":
        capture.path.unlink()
    elif fault == "short":
        capture.path.write_bytes(PIXELS[:-1])
    else:
        capture.path.with_name("unreported.bin").write_bytes(b"MODELED")
    # The existing path guard raises FileNotFoundError before receipt
    # materialization for absence. Do not broaden every fault to Exception or
    # change production rejection merely to normalize this test's error type.
    expected = (
        FileNotFoundError
        if fault == "missing"
        else (ValueError, CameraWorkerError, PhysicalOnboardingDurabilityError)
    )
    with pytest.raises(expected):
        ingest(capture)
    assert capture.workflow.view()["last_frame"] is None
    assert not (capture.path.parent.parent.parent / "capture-datasets").exists()
    assert (
        capture.workflow.retained_diagnostics()["capture_checksum"]["sha256"]
        == capture.checksum.sha256
    )


@pytest.mark.parametrize(
    "fault", ["omitted", "shape", "key", "digest", "profile", "stop"]
)
def test_no_downgrade_or_unbound_subject_reaches_publication(capture, fault):
    args = {}
    if fault == "omitted":
        args["capture_checksum"] = None
    elif fault == "shape":
        args["capture_checksum"] = capture.checksum.to_dict()
    elif fault == "key":
        args["capture_reference_request_key"] = "other-request"
    elif fault == "profile":
        args["configuration_verification"] = False
    elif fault == "stop":
        args["cancellation"] = Event()
        args["cancellation"].set()
    else:
        data = capture.checksum.to_dict()
        data["frame"]["sha256"] = "a" * 64
        args["capture_checksum"] = CameraCaptureChecksum(canonical(data))
    with pytest.raises(ValueError):
        ingest(capture, **args)
    assert capture.workflow.view()["last_frame"] is None
    assert not (capture.path.parent.parent.parent / "capture-datasets").exists()


def test_new_subject_cannot_relabel_a_legacy_plan(tmp_path, monkeypatch):
    f = workflow_fixture(tmp_path, monkeypatch, configuration_verification=True)
    write_pixels(f)
    checked, _, _ = capture_metadata(f.evidence)
    data = checked.run.to_dict()
    with monkeypatch.context() as patch:
        patch.setattr(reader, "monotonic_ns", lambda: data["finished_ns"] + 1)
        f.checksum = reader._collect_owned_capture_checksum(
            f.evidence,
            request_key=KEY,
            cancellation=Event(),
            deadline_ns=data["parent_deadline_ns"],
        )
    with pytest.raises(ValueError, match="PREPARATION_CONTEXT_MISMATCH"):
        ingest(f)


def test_operating_pixel_check_uses_sealed_reference_without_launch_packet(capture):
    native = CameraNativeEvidenceSubject(
        capture.capture,
        capture.evidence,
        capture.evidence[0].payload_sha256,
        capture.evidence[1].payload_sha256,
    )
    arguments = dict(
        checksum=capture.checksum,
        request_key=KEY,
        assigned_parent=capture.path.parent.parent.parent,
        settings_epoch=capture.configuration.settings_epoch,
        cancelled=lambda: False,
    )
    result = verify_sealed_operating_capture_pixels(native, **arguments)
    assert result["schema"] == "rocell.camera_operating_pixel_check.v2"
    assert result["status"] == "VERIFIED_AT_READ" and result["verified_bytes"] == 16
    assert result["result_sha256"] is None  # No invented launch completion.
    assert result["capture_checksum_sha256"] == capture.checksum.sha256
    assert result["original_stage_record_retained"] is False
    capture.path.write_bytes(bytes([PIXELS[0] ^ 1]) + PIXELS[1:])
    changed = verify_sealed_operating_capture_pixels(native, **arguments)
    assert changed["status"] == "PIXEL_FILE_UNAVAILABLE_OR_CHANGED"
    assert changed["native_frame_sha256"] == digest(PIXELS)
    assert (
        changed["verified_bytes"] == 0 and changed["content_verified_at_read"] is False
    )
