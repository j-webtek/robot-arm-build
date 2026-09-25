"""Synthetic native observations and real guarded files; no hardware or M1 seal."""

from contextlib import contextmanager
from pathlib import Path
from threading import Event
import os
import hashlib

import pytest

from rocell.application import camera_capture_checksum as contract
from rocell.application import camera_capture_checksum_reader as reader
from rocell.providers.windows.native_camera_protocol import canonical, digest
from test_camera_activation_application_handoff import (
    workflow_fixture,
    write_pixels,
    PIXELS,
    no_device_calls,
)
from test_native_camera_activation_supervisor import no_physical_owner

KEY = "operation-" + "7" * 32


@pytest.mark.parametrize("fault", [None, "bad-result", "cleanup-missing-resource"])
def test_metadata_matches_verified_native_projection_and_revalidates_each_call(
    tmp_path, monkeypatch, fault
):
    from dataclasses import asdict
    from rocell.application.physical_camera_configuration import _verified_observation

    f = workflow_fixture(
        tmp_path, monkeypatch, configuration_verification=True, capture_fault=fault
    )
    observed = _verified_observation(
        f.evidence,
        prepared=f.capture,
        expected_evidence_sha256=f.evidence[0].payload_sha256,
        expected_supervision_sha256=f.evidence[1].payload_sha256,
    )
    reads = []
    validate = contract.validate_camera_activation_evidence

    def counted(evidence):
        reads.append(evidence)
        return validate(evidence)

    monkeypatch.setattr(contract, "validate_camera_activation_evidence", counted)
    for _ in range(2):
        checked, mode, metadata = contract.capture_metadata(f.evidence)
        assert (metadata is not None) is (
            observed.status == "SUCCEEDED_NATIVE_DIAGNOSTIC"
        )
        if metadata is not None:
            assert observed.process_cleanup_confirmed
            assert mode == observed.native_receipt.observed_mode
            assert metadata == asdict(observed.native_receipt.frames[0])
    assert len(reads) == 2  # Fresh exact-pair validation, not a process cache.


@pytest.fixture
def capture(tmp_path, monkeypatch):
    fixture = workflow_fixture(tmp_path, monkeypatch, configuration_verification=True)
    write_pixels(fixture)
    checked, _, _ = contract.capture_metadata(fixture.evidence)
    fixture.deadline = checked.run.to_dict()["parent_deadline_ns"]
    fixture.tick = checked.run.to_dict()["finished_ns"] + 1
    monkeypatch.setattr(reader, "monotonic_ns", lambda: fixture.tick)
    fixture.cancellation = Event()
    return fixture


def collect(f, **kwargs):
    args = dict(request_key=KEY, cancellation=f.cancellation, deadline_ns=f.deadline)
    args.update(kwargs)
    return reader._collect_owned_capture_checksum(f.evidence, **args)


def verify(f, subject, **kwargs):
    args = dict(
        evidence=f.evidence, expected_request_key=KEY, expected_sha256=subject.sha256
    )
    args.update(kwargs)
    return contract.verify_capture_checksum(subject.payload, **args)


def test_guarded_read_and_independent_native_join(capture):
    subject = collect(capture)
    assert verify(capture, subject) == subject
    data = subject.to_dict()
    assert data["status"] == "CAPTURE_BYTES_HASHED"
    assert data["frame"]["sha256"] == digest(PIXELS)
    assert data["verified_pixel_bytes"] == 16
    assert data["read_started_ns"] == data["read_finished_ns"] == capture.tick
    assert "NOT_EXPOSURE" in data["timestamp_semantics"]
    assert all(data[key] is False for key in contract.FALSE_FIELDS)
    assert "manifest_sha256" not in data
    data["frame"]["sha256"] = "a" * 64
    assert subject.to_dict()["frame"]["sha256"] == digest(PIXELS)


def test_unattested_read_preserves_unknown_times_not_native_time_substitution(capture):
    subject = contract.build_capture_checksum(
        capture.evidence,
        request_key=KEY,
        status="PIXEL_READ_NOT_ATTESTED",
        frame=None,
        read_started_ns=None,
        read_finished_ns=None,
    )
    assert verify(capture, subject) == subject
    data = subject.to_dict()
    assert data["native_finished_ns"] is not None
    assert data["read_started_ns"] is data["read_finished_ns"] is data["frame"] is None
    assert data["verified_pixel_bytes"] == 0 and data["observed_mode"] is not None
    for field in ("read_started_ns", "read_finished_ns", "verified_pixel_bytes"):
        changed = dict(data, **{field: capture.tick})
        with pytest.raises(contract.CameraCaptureChecksumError):
            contract.CameraCaptureChecksum(canonical(changed))


@pytest.mark.parametrize(
    "fault", ["missing", "short", "extra", "hardlink", "directory", "missing_directory"]
)
def test_unavailable_or_changed_file_is_not_a_success(capture, fault):
    path = (
        Path(capture.capture.camera_plan.request.output_directory) / "frame-000000.yuy2"
    )
    if fault == "missing":
        path.unlink()
    elif fault == "short":
        path.write_bytes(PIXELS[:-1])
    elif fault == "extra":
        path.with_name("extra.bin").write_bytes(b"extra")
    elif fault == "hardlink":
        os.link(path, path.parent.parent / "linked-frame")
    elif fault == "missing_directory":
        path.unlink()
        path.parent.rmdir()
    else:
        path.unlink()
        path.mkdir()
    data = collect(capture).to_dict()
    assert data["status"] == "PIXEL_READ_FAILED"
    assert data["frame"] is None and data["verified_pixel_bytes"] == 0


@pytest.mark.parametrize(
    "fault", ["stop", "deadline", "late_stop", "late_deadline", "exit_error"]
)
def test_stop_deadline_and_scope_exit_are_not_published_as_verified(
    capture, monkeypatch, fault
):
    if fault == "stop":
        capture.cancellation.set()
    elif fault == "deadline":
        capture.tick = capture.deadline
    else:
        original = reader._locked_file

        @contextmanager
        def changed(*args, **kwargs):
            with original(*args, **kwargs) as stream:
                yield stream
            if fault == "late_stop":
                capture.cancellation.set()
            elif fault == "late_deadline":
                capture.tick = capture.deadline
            else:
                raise OSError("MODELED_EXIT_FAILURE")

        monkeypatch.setattr(reader, "_locked_file", changed)
    data = collect(capture).to_dict()
    assert data["status"] == (
        "PIXEL_READ_FAILED" if fault == "exit_error" else "PIXEL_READ_INTERRUPTED"
    )
    assert data["frame"] is None and data["verified_pixel_bytes"] == 0
    assert verify(capture, contract.CameraCaptureChecksum(canonical(data)))


@pytest.mark.parametrize(
    "kwargs",
    [
        dict(request_key="../path"),
        dict(request_key="a" * 65),
        dict(cancellation=True),
        dict(deadline_ns=True),
        dict(deadline_ns=1),
    ],
)
def test_exact_inputs_before_file_access(capture, monkeypatch, kwargs):
    monkeypatch.setattr(
        reader, "_locked_file", lambda *a, **k: pytest.fail("file access")
    )
    with pytest.raises(contract.CameraCaptureChecksumError):
        collect(capture, **kwargs)


@pytest.mark.parametrize("value", [True, -1, 2**63, 1])
def test_invalid_or_reversed_host_clock_is_not_normalized(capture, monkeypatch, value):
    monkeypatch.setattr(reader, "monotonic_ns", lambda: value)
    with pytest.raises(contract.CameraCaptureChecksumError):
        collect(capture)


@pytest.mark.parametrize("field", contract.FALSE_FIELDS)
@pytest.mark.parametrize("value", [True, 0, "false"])
def test_false_authority_fields_are_literal(capture, field, value):
    data = collect(capture).to_dict()
    data[field] = value
    with pytest.raises(contract.CameraCaptureChecksumError):
        contract.CameraCaptureChecksum(canonical(data))


@pytest.mark.parametrize(
    "field,value",
    [
        ("origin", "IMPORTED_EXPORT"),
        ("request_key", "../path"),
        ("status", "PASS"),
        ("native_run_sha256", "0" * 64),
        ("verified_pixel_bytes", True),
        ("read_started_ns", None),
        ("read_finished_ns", 2**63),
        ("timestamp_semantics", "EXPOSURE_TIME"),
    ],
)
def test_malformed_record_rejected(capture, field, value):
    data = collect(capture).to_dict()
    data[field] = value
    with pytest.raises(contract.CameraCaptureChecksumError):
        contract.CameraCaptureChecksum(canonical(data))


@pytest.mark.parametrize("value", [True, 0, -1, 999999])
def test_invalid_mode_has_a_bounded_contract_failure(capture, value):
    data = collect(capture).to_dict()
    data["observed_mode"]["width"] = value
    with pytest.raises(contract.CameraCaptureChecksumError):
        contract.CameraCaptureChecksum(canonical(data))


def test_exact_native_metadata_and_expected_hash_are_independent(capture):
    subject = collect(capture)
    data = subject.to_dict()
    data["frame"]["media_timestamp_100ns"] += 1
    forged = contract.CameraCaptureChecksum(canonical(data))
    with pytest.raises(contract.CameraCaptureChecksumError):
        verify(capture, forged)
    with pytest.raises(contract.CameraCaptureChecksumError):
        verify(capture, subject, expected_sha256="a" * 64)
    with pytest.raises(contract.CameraCaptureChecksumError):
        verify(capture, subject, expected_request_key="another-request")


def test_closed_bounded_canonical_payload(capture):
    subject = collect(capture)
    for raw in (
        b" " * (contract.MAX_BYTES + 1),
        b'{"schema":1,"schema":2}',
        b"[]",
        b"{",
        subject.payload + b"\n",
    ):
        with pytest.raises(contract.CameraCaptureChecksumError):
            contract.CameraCaptureChecksum(raw)


def test_failed_native_observation_never_opens_pixels(tmp_path, monkeypatch):
    f = workflow_fixture(
        tmp_path,
        monkeypatch,
        capture_fault="cleanup-error",
        configuration_verification=True,
    )
    checked, _, _ = contract.capture_metadata(f.evidence)
    monkeypatch.setattr(
        reader, "_locked_file", lambda *a, **k: pytest.fail("file access")
    )
    subject = reader._collect_owned_capture_checksum(
        f.evidence,
        request_key=KEY,
        cancellation=Event(),
        deadline_ns=checked.run.to_dict()["parent_deadline_ns"],
    )
    assert subject.to_dict()["status"] == "NATIVE_CAPTURE_NOT_COMPLETE"
    assert subject.to_dict()["read_started_ns"] is None
    assert verify(f, subject) == subject


def test_missing_native_finish_time_stays_unknown(capture, monkeypatch):
    from rocell.application.camera_activation_campaign_evidence import (
        CameraActivationArtifact,
    )

    evidence = []
    for artifact in capture.evidence:
        import json

        data = json.loads(artifact.payload)
        data["finished_ns"] = None
        evidence.append(CameraActivationArtifact(artifact.role, canonical(data)))
    capture.evidence = tuple(evidence)
    monkeypatch.setattr(
        reader, "_locked_file", lambda *a, **k: pytest.fail("file access")
    )
    subject = collect(capture)
    assert subject.to_dict()["status"] == "NATIVE_CAPTURE_NOT_COMPLETE"
    assert subject.to_dict()["native_finished_ns"] is None
    assert verify(capture, subject) == subject


@pytest.mark.parametrize("confirm", [True, False])
def test_directory_cleanup_attempts_every_handle_and_confirms_when_required(confirm):
    from rocell.application.wizard_diagnostic_export import (
        _close_directory_handles,
        WizardDiagnosticExportError,
    )

    closed = []

    class Kernel:
        def CloseHandle(self, handle):
            closed.append(handle)
            return handle != 2

    if confirm:
        with pytest.raises(WizardDiagnosticExportError, match="cleanup unconfirmed"):
            _close_directory_handles(Kernel(), [1, 2, 3], confirm)
    else:
        _close_directory_handles(Kernel(), [1, 2, 3], confirm)
    assert closed == [3, 2, 1]


def test_full_resolution_synthetic_file_uses_bounded_reads(tmp_path, monkeypatch):
    from test_camera_operating_evidence_preflight import case

    _, factory = case(tmp_path, monkeypatch, version="v2")
    native = factory("full-checksum-frame").native
    checked, _, metadata = contract.capture_metadata(native.evidence)
    output = Path(native.preparation.camera_plan.request.output_directory)
    output.mkdir(parents=True)
    length = metadata["length_bytes"]
    assert length == 5472 * 3648 * 2
    block = bytes([16, 128, 56, 128]) * (reader.BLOCK_BYTES // 4)
    expected = hashlib.sha256()
    with (output / metadata["filename"]).open("xb") as stream:
        remaining = length
        while remaining:
            chunk = block[: min(len(block), remaining)]
            stream.write(chunk)
            expected.update(chunk)
            remaining -= len(chunk)
    monkeypatch.setattr(
        reader, "monotonic_ns", lambda: checked.run.to_dict()["finished_ns"] + 1
    )
    original = reader._locked_file
    sizes = []

    @contextmanager
    def observed(*args, **kwargs):
        with original(*args, **kwargs) as stream:

            class Reader:
                def read(self, size):
                    sizes.append(size)
                    return stream.read(size)

            yield Reader()

    monkeypatch.setattr(reader, "_locked_file", observed)
    subject = reader._collect_owned_capture_checksum(
        native.evidence,
        request_key=KEY,
        cancellation=Event(),
        deadline_ns=checked.run.to_dict()["parent_deadline_ns"],
    )
    assert subject.to_dict()["status"] == "CAPTURE_BYTES_HASHED"
    assert subject.to_dict()["frame"]["sha256"] == expected.hexdigest()
    assert subject.to_dict()["verified_pixel_bytes"] == length
    assert max(sizes) <= reader.BLOCK_BYTES and len(sizes) > 30
