"""Pure physical-shaped native metadata and explicit temporary-file checks only."""

import ctypes
from dataclasses import asdict, replace
import hashlib
import io
from pathlib import Path
import subprocess

import pytest

from rocell.providers.windows import camera_worker_client as client
from test_windows_camera_worker import BINDING, BUDGET, MODE, receipt


def request(directory):
    return client.CameraActivationRequest(
        "metadata-capture",
        "a" * 64,
        "capture",
        BINDING,
        MODE,
        (),
        BUDGET,
        "c" * 64,
        "d" * 64,
        str(directory),
    )


def parse(raw, directory):
    return client.WindowsCameraWorkerClient._parse_receipt_metadata(
        raw, "capture", BINDING, MODE, (BUDGET, directory), ()
    )


@pytest.fixture(autouse=True)
def no_native_dispatch(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("receipt test attempted a native/process/device operation")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(ctypes, "CDLL", forbidden)


def test_capture_metadata_is_pure_and_never_invents_file_hashes(tmp_path, monkeypatch):
    raw = receipt("capture")

    def forbidden(*args, **kwargs):
        pytest.fail("pure metadata parse attempted file access")

    with monkeypatch.context() as guard:
        for name in ("open", "stat", "lstat", "iterdir", "read_bytes", "mkdir"):
            guard.setattr(Path, name, forbidden)
        metadata = parse(raw, tmp_path / "does-not-exist")
    assert type(metadata) is client.NativeCameraReceiptMetadata
    assert type(metadata.frames[0]) is client.NativeFrameMetadata
    assert asdict(metadata.frames[0]) == raw["frames"][0]
    assert not hasattr(metadata.frames[0], "sha256")
    assert metadata.cleanup_confirmed is True
    assert metadata.counts["frames_written"] == 1
    raw["frames"][0]["length_bytes"] = 999
    raw["counts"]["frames_written"] = 999
    assert metadata.frames[0].length_bytes == 16
    assert metadata.counts["frames_written"] == 1
    with pytest.raises(TypeError):
        metadata.counts["frames_written"] = 999


def test_failed_cleanup_metadata_stays_failed_without_reading_artifacts(tmp_path):
    raw = receipt("capture")
    raw["status"], raw["reason_code"] = "FAILED", "SOURCE_SHUTDOWN_FAILED"
    raw["cleanup"]["source_shutdown_hr"] = -1
    metadata = parse(raw, tmp_path / "missing")
    assert metadata.status == "FAILED"
    assert metadata.cleanup_confirmed is False
    assert metadata.effect_uncertain is True
    assert len(metadata.frames) == 1


@pytest.mark.parametrize(
    "defect",
    [
        "filename",
        "row-bounds",
        "sequence",
        "length",
        "count",
        "samples",
        "mode",
        "control-count",
        "cleanup",
        "extra-field",
        "invented-hash",
    ],
)
def test_metadata_keeps_the_existing_strict_wire_checks(tmp_path, monkeypatch, defect):
    raw = receipt("capture")
    frame = raw["frames"][0]
    if defect == "filename":
        frame["filename"] = "../frame-000000.yuy2"
    elif defect == "row-bounds":
        frame["row0_offset_bytes"] = 15
    elif defect == "sequence":
        frame["host_sequence"] = 1
    elif defect == "length":
        frame["length_bytes"] = 17
    elif defect == "count":
        raw["counts"]["frames_written"] = 2
    elif defect == "samples":
        raw["counts"]["samples_received"] = 2
    elif defect == "mode":
        raw["observed_mode"]["width"] = 6
    elif defect == "control-count":
        raw["counts"]["control_set_attempts"] = 1
    elif defect == "cleanup":
        raw["cleanup"]["source_released"] = False
    elif defect == "extra-field":
        raw["physical_qualified"] = True
    else:
        frame["sha256"] = "e" * 64

    def forbidden(*args, **kwargs):
        pytest.fail("invalid metadata reached artifact I/O")

    with monkeypatch.context() as guard:
        guard.setattr(Path, "open", forbidden)
        guard.setattr(Path, "stat", forbidden)
        with pytest.raises(client.CameraWorkerError):
            parse(raw, tmp_path)


def test_explicit_artifact_validation_hashes_exact_temp_bytes_and_matches_legacy(
    tmp_path,
):
    raw = receipt("capture")
    payload = bytes(range(16))
    (tmp_path / "frame-000000.yuy2").write_bytes(payload)
    value = client.validate_capture_artifacts(raw, request=request(tmp_path))
    legacy = client.WindowsCameraWorkerClient._parse_receipt(
        raw, "capture", BINDING, MODE, (BUDGET, tmp_path), ()
    )
    assert type(value) is client.NativeCameraReceipt
    assert value == legacy
    assert value.frames[0].sha256 == hashlib.sha256(payload).hexdigest()
    assert value.frames[0].media_timestamp_100ns == -200
    assert not hasattr(value, "physical_authority")


@pytest.mark.parametrize("defect", ["missing", "short", "extra"])
def test_artifact_validation_refuses_incomplete_or_unreported_files(tmp_path, defect):
    if defect != "missing":
        (tmp_path / "frame-000000.yuy2").write_bytes(
            bytes(range(8 if defect == "short" else 16))
        )
    if defect == "extra":
        (tmp_path / "unreported.txt").write_bytes(b"retained unexpected file")
    with pytest.raises((client.CameraWorkerError, FileNotFoundError)):
        client.validate_capture_artifacts(receipt("capture"), request=request(tmp_path))


@pytest.mark.parametrize("length", [8, 17])
def test_artifact_read_is_bounded_and_detects_changed_length(
    tmp_path, monkeypatch, length
):
    file = tmp_path / "frame-000000.yuy2"
    file.write_bytes(bytes(range(16)))
    original_open = Path.open

    def changed_open(path, *args, **kwargs):
        if path == file:
            return io.BytesIO(bytes(range(length)))
        return original_open(path, *args, **kwargs)

    monkeypatch.setattr(Path, "open", changed_open)
    with pytest.raises(client.CameraWorkerError, match="size changed while hashing"):
        client.validate_capture_artifacts(receipt("capture"), request=request(tmp_path))


def test_handbuilt_metadata_is_not_an_artifact_validation_input(tmp_path, monkeypatch):
    metadata = parse(receipt("capture"), tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("a hand-built metadata value reached file I/O")

    monkeypatch.setattr(Path, "open", forbidden)
    with pytest.raises(client.CameraWorkerError):
        client.validate_capture_artifacts(metadata, request=request(tmp_path))


def test_explicit_artifact_validator_honors_a_requested_stride_before_io(
    tmp_path, monkeypatch
):
    exact = replace(request(tmp_path), mode=replace(MODE, stride_bytes=-8))

    def forbidden(*args, **kwargs):
        pytest.fail("stride-mismatched request reached file I/O")

    monkeypatch.setattr(Path, "open", forbidden)
    with pytest.raises(client.CameraWorkerError, match="sample stride differs"):
        client.validate_capture_artifacts(receipt("capture"), request=exact)


@pytest.mark.parametrize(
    "field,value",
    [
        ("operation", "probe"),
        ("source_sha256", "bad"),
        ("binding", {}),
        ("mode", None),
        ("controls", []),
        ("output_directory", "../elsewhere"),
    ],
)
def test_artifact_validator_rechecks_exact_request_before_io(
    tmp_path, monkeypatch, field, value
):
    changed = replace(request(tmp_path), **{field: value})

    def forbidden(*args, **kwargs):
        pytest.fail("invalid request reached file I/O")

    monkeypatch.setattr(Path, "open", forbidden)
    with pytest.raises(client.CameraWorkerError):
        client.validate_capture_artifacts(receipt("capture"), request=changed)
