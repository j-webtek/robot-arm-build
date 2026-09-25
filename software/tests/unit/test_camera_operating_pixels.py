"""Real tiny files and native codecs; process/camera effects are modeled only."""

from copy import deepcopy
from pathlib import Path
import os

import pytest

from rocell.application import camera_operating_pixels as module
from rocell.application.camera_capture_dataset import CameraDatasetCancelled
from rocell.application.camera_operating_evidence_preflight import (
    CameraNativeEvidenceSubject,
)
from rocell.providers.windows.native_camera_protocol import digest
from test_camera_activation_application_handoff import (
    observation,
    PIXELS,
    no_device_calls,
)
from test_physical_camera_activation_campaign import campaign
from test_native_camera_activation_supervisor import no_physical_owner

OPERATION = "operation-" + "8" * 32
EPOCH = "b" * 64


def packet_for(result, *, operation=OPERATION):
    return dict(
        source_sha256=result["steps"][0]["report"]["source_sha256"],
        queue=dict(operation_id=operation, claimed=True),
        completion=dict(
            operation_id=operation,
            action_id=module.CAPTURE_ACTION_ID,
            status="SUCCEEDED",
            completion_log_persisted=True,
            result=result,
            result_sha256=module._logged_digest(result),
        ),
        physical_authority=False,
        hardware_qualified=False,
    )


@pytest.fixture
def saved(tmp_path, monkeypatch):
    worker = campaign(tmp_path, "capture", configuration_verification=True)
    prepared = worker._prepare("attempt-pixel-test", "e" * 64)
    evidence = observation(tmp_path, monkeypatch, prepared)
    native = CameraNativeEvidenceSubject(
        prepared, evidence, evidence[0].payload_sha256, evidence[1].payload_sha256
    )
    request = prepared.camera_plan.request
    capture = Path(request.output_directory)
    capture.mkdir(parents=True)
    file = capture / "frame-000000.yuy2"
    file.write_bytes(PIXELS)
    frame = dict(
        attempt_id=request.campaign_id,
        frame_index=0,
        image_id=None,
        native_frame_sha256=digest(PIXELS),
        capture_evidence_sha256=native.expected_evidence_sha256,
        settings_epoch=EPOCH,
        endpoint_sha256=request.binding.endpoint_sha256,
        manifest_sha256="c" * 64,
        preview_sha256="d" * 64,
        frame_content_verified=True,
        live=False,
        provenance="DERIVED_PREVIEW_OF_RETAINED_PHYSICAL_YUY2",
    )
    report = dict(
        source_sha256=request.source_sha256,
        session_id="MODELED-session",
        workflow_sha256="f" * 64,
        last_frame=frame,
    )
    result = dict(
        schema="rocell.wizard_retained_native_camera_data.v1",
        action_id=module.CAPTURE_ACTION_ID,
        status="SUCCEEDED",
        physical_authority=False,
        steps=[dict(name="retained_native_camera_data", exit_code=0, report=report)],
    )
    packet = packet_for(result)
    return native, file, packet, Path(worker.plan()["assigned_parent_directory"])


def reference(saved, packet=None):
    native, _, original, _ = saved
    return module.logged_pixel_reference(
        original if packet is None else packet,
        request_key=OPERATION,
        source_sha256=native.preparation.camera_plan.request.source_sha256,
        session_id="MODELED-session",
    )


def verify(saved, **overrides):
    native, _, _, parent = saved
    args = dict(
        reference=reference(saved),
        request_key=OPERATION,
        assigned_parent=parent,
        settings_epoch=EPOCH,
        cancelled=lambda: False,
    )
    args.update(overrides)
    return module.verify_operating_capture_pixels(native, **args)


def test_saved_bytes_match_earlier_completion_without_new_files(saved):
    before = {p: p.read_bytes() for p in saved[3].rglob("*") if p.is_file()}
    report = verify(saved)
    assert report["status"] == "VERIFIED_AT_READ"
    assert report["verified_bytes"] == len(PIXELS)
    assert report["native_frame_sha256"] == digest(PIXELS)
    assert report["content_verified_at_read"]
    assert not any(
        report[k]
        for k in (
            "frame_freshness_assessed",
            "original_stage_record_retained",
            "physical_authority",
        )
    )
    assert before == {p: p.read_bytes() for p in saved[3].rglob("*") if p.is_file()}


@pytest.mark.parametrize(
    "fault",
    [
        "hash",
        "failed",
        "unlogged",
        "source",
        "session",
        "frame",
        "boolean",
        "wrong_action",
        "missing",
    ],
)
def test_bad_completion_cannot_supply_a_pixel_checksum(saved, fault):
    packet = deepcopy(saved[2])
    done = packet["completion"]
    report = done["result"]["steps"][0]["report"]
    if fault == "hash":
        done["result_sha256"] = "1" * 64
    elif fault == "failed":
        done["status"] = "FAILED"
    elif fault == "unlogged":
        done["completion_log_persisted"] = False
    elif fault == "source":
        packet["source_sha256"] = "1" * 64
    elif fault == "session":
        report["session_id"] = "different"
    elif fault == "frame":
        report["last_frame"]["frame_index"] = 1
    elif fault == "boolean":
        report["last_frame"]["frame_index"] = False
    elif fault == "wrong_action":
        done["action_id"] = "physical_camera_probe"
    else:
        done.pop("result")
    if fault in {"session", "frame", "boolean"}:
        done["result_sha256"] = module._logged_digest(done["result"])
    assert reference(saved, packet) is None


def test_missing_reference_does_not_open_or_hash_a_file(saved, monkeypatch):
    monkeypatch.setattr(
        module, "_locked_file", lambda *a: pytest.fail("Unexpected file open")
    )
    assert verify(saved, reference=None)["status"] == "LOGGED_REFERENCE_UNAVAILABLE"


@pytest.mark.parametrize(
    "key",
    [
        "operation_id",
        "attempt_id",
        "capture_evidence_sha256",
        "settings_epoch",
        "endpoint_sha256",
    ],
)
def test_original_subject_mismatch_prevents_pixel_read(saved, monkeypatch, key):
    ref = reference(saved)
    ref[key] = "different"
    monkeypatch.setattr(
        module, "_locked_file", lambda *a: pytest.fail("Unexpected file open")
    )
    assert verify(saved, reference=ref)["status"] == "REFERENCE_MISMATCH"


@pytest.mark.parametrize(
    "fault", ["changed", "short", "long", "missing", "extra", "hardlink"]
)
def test_bad_files_stay_unverified_without_repair(saved, fault):
    file = saved[1]
    if fault == "changed":
        file.write_bytes(bytes([0]) + PIXELS[1:])
    elif fault == "short":
        file.write_bytes(PIXELS[:-1])
    elif fault == "long":
        file.write_bytes(PIXELS + b"x")
    elif fault == "missing":
        file.unlink()
    elif fault == "extra":
        (file.parent / "unreported.yuy2").write_bytes(PIXELS)
    else:
        os.link(file, file.parent.parent / "additional-link.yuy2")
    report = verify(saved)
    assert report["status"] == "PIXEL_FILE_UNAVAILABLE_OR_CHANGED"
    assert report["verified_bytes"] == 0 and not report["content_verified_at_read"]
    if fault == "missing":
        assert not file.exists()


@pytest.mark.parametrize("after", [0, 2, 4])
def test_stop_or_expired_deadline_never_returns_a_verified_result(saved, after):
    calls = []

    def cancelled():
        calls.append(None)
        return len(calls) > after

    with pytest.raises(CameraDatasetCancelled):
        verify(saved, cancelled=cancelled)


def test_assigned_parent_cannot_redirect_reads(saved, tmp_path):
    assert (
        verify(saved, assigned_parent=tmp_path / "different")["status"]
        == "REFERENCE_MISMATCH"
    )
