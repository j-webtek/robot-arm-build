"""Pure physical-shaped capture records; no helper, process, camera or frame reads.

The supplied observations are protocol fixtures, not claims that native hardware
ran. Only the explicit small-file test calls the separate artifact validator.
"""

import base64
import ctypes
from pathlib import Path
import subprocess
from threading import Event
import time

import pytest

from rocell.providers.windows import owned_native_camera_evidence as module
from rocell.providers.windows.camera_worker_client import (
    CameraCampaignBudget,
    NativeCameraReceiptMetadata,
    WindowsCameraWorkerClient,
    validate_capture_artifacts,
)
from rocell.providers.windows.native_camera_capture_registration import (
    HELPER_RELATIVE_PATH,
    create_native_camera_capture_runtime_registration,
    prepare_owned_native_capture,
)
from rocell.providers.windows.native_camera_capture_protocol import (
    native_camera_capture_release,
)
from rocell.providers.windows.native_camera_protocol import (
    NativeCameraReady,
    READY_SCHEMA,
    RESULT_SCHEMA,
    canonical,
    digest,
)
from test_windows_camera_worker import BINDING, MODE, receipt


def preparation(tmp_path):
    runtime = create_native_camera_capture_runtime_registration(
        tmp_path,
        source_sha256="a" * 64,
        catalog_sha256="b" * 64,
        helper_sha256="c" * 64,
        build_record_sha256="d" * 64,
    )
    directory = tmp_path / "work"
    plan = WindowsCameraWorkerClient(
        tmp_path / HELPER_RELATIVE_PATH, "c" * 64
    ).prepare_capture(
        BINDING,
        MODE,
        directory / "capture-attempt-capture",
        source_sha256="a" * 64,
        campaign_id="attempt-capture",
        budget=CameraCampaignBudget(5000, 1, 16, 16),
    )
    return prepare_owned_native_capture(
        runtime,
        plan,
        session_id="session-capture",
        operation_sha256="e" * 64,
        permit_sha256="f" * 64,
        working_directory=directory,
    )


def fixture_evidence(tmp_path, *, native_ok=True, process_cleanup=True):
    prepared = preparation(tmp_path)
    request = prepared.admission_request
    ready = NativeCameraReady(
        canonical(
            {
                "schema": READY_SCHEMA,
                "request_sha256": request.request_sha256,
                "child_pid": 123,
                "challenge": "1" * 64,
            }
        )
    )
    ready_wire = ready.payload + b"\n"
    release = native_camera_capture_release(request, ready)
    inner = receipt("capture")
    if not native_ok:
        inner["status"], inner["reason_code"] = "FAILED", "SOURCE_SHUTDOWN_FAILED"
        inner["cleanup"]["source_shutdown_hr"] = -1
    result = {
        "schema": RESULT_SCHEMA,
        "request_sha256": request.request_sha256,
        "child_pid": 123,
        "challenge_sha256": ready.challenge_sha256,
        "permit_sha256": request.to_dict()["permit_sha256"],
        "native_receipt": inner,
    }
    observed = {
        "created": True,
        "resumed": True,
        "tree_exited": True,
        "returncode": 0 if native_ok else 1,
        "pid": 123,
        "written": len(request.wire()) + len(release),
        "peak_handles": 8,
        "peak_processes": 1,
        "stdout_eof": True,
        "stderr_eof": True,
        "pending": False,
        "handles_remaining": 0,
        "unclosed_handles_remaining": 0,
        "pins_remaining": 0,
        "stdout": ready_wire + canonical(result) + b"\n",
        "stderr": b"private diagnostic",
    }
    inputs = {
        "probe": prepared,
        "fixture": None,
        "deadline_ns": 20_000_000_000,
        "elapsed_ns": 1_000_000,
        "primary_error": None if native_ok else "NATIVE_DIAGNOSTIC_FAILED",
        "cleanup_errors": () if process_cleanup else ("CLOSE_FAILED:job",),
        "observed": observed,
        "ready_wire": ready_wire,
        "release_wire": release,
        "result": result,
        "native_validated": True,
        "admission_only_validated": False,
        "release_check_passed": True,
        "handshake": None,
    }
    return prepared, inputs, module.retain_owned_native_camera_run(**inputs)


@pytest.fixture(autouse=True)
def forbid_device_and_process(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("capture evidence test attempted native/process access")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(ctypes, "CDLL", forbidden)


def test_capture_evidence_is_pure_complete_raw_metadata_not_pixels(
    tmp_path, monkeypatch
):
    prepared, inputs, evidence = fixture_evidence(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("pure capture evidence verification attempted filesystem access")

    with monkeypatch.context() as guard:
        for name in ("open", "stat", "lstat", "iterdir", "mkdir", "resolve"):
            guard.setattr(Path, name, forbidden)
        verified = module.verify_owned_native_camera_run_evidence(
            evidence,
            expected_preparation_sha256=prepared.preparation_sha256,
            expected_evidence_sha256=evidence.evidence_sha256,
        )
        metadata = verified.native_receipt
        summary = verified.safe_summary()
    assert type(metadata) is NativeCameraReceiptMetadata
    assert not hasattr(metadata.frames[0], "sha256")
    assert verified.to_dict()["schema"] == module.CAPTURE_SCHEMA
    assert summary["schema"] == "rocell.owned_native_camera_capture_run_summary.v1"
    assert summary["provenance"] == "PHYSICAL_UNQUALIFIED"
    assert summary["capture_metadata"] == {
        "status": "OK",
        "frames_reported": 1,
        "total_frame_bytes_reported": 16,
    }
    assert summary["native_cleanup_confirmed"] is True
    assert summary["process_cleanup_confirmed"] is True
    for flag in (
        "frame_content_verified",
        "device_cleanup_proven",
        "hardware_qualified",
        "physical_authority",
    ):
        assert summary[flag] is False
    assert summary["final_power_state"] == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    assert (
        base64.b64decode(verified.to_dict()["stdout"]["base64"])
        == inputs["observed"]["stdout"]
    )
    assert b"private diagnostic" not in canonical(summary)
    assert b"frame-000000.yuy2" not in canonical(summary)
    detached = verified.to_dict()
    detached["validated_result"]["native_receipt"]["frames"][0]["length_bytes"] = 999
    assert verified.native_receipt.frames[0].length_bytes == 16


@pytest.mark.parametrize("native_ok,process_cleanup", [(False, True), (True, False)])
def test_process_cleanup_and_native_cleanup_are_independent(
    tmp_path, native_ok, process_cleanup
):
    _, _, evidence = fixture_evidence(
        tmp_path, native_ok=native_ok, process_cleanup=process_cleanup
    )
    summary = evidence.safe_summary()
    assert summary["status"] == "FAILED"
    assert summary["native_cleanup_confirmed"] is native_ok
    assert summary["process_cleanup_confirmed"] is process_cleanup
    assert summary["native_receipt_valid"] is True
    assert summary["frame_content_verified"] is False


def test_failed_native_metadata_cannot_be_declared_successful_process_evidence(
    tmp_path,
):
    _, _, evidence = fixture_evidence(tmp_path, native_ok=False)
    document = evidence.to_dict()
    document["primary_error"] = None
    document["status"] = "SUCCEEDED_NATIVE_DIAGNOSTIC"
    with pytest.raises(ValueError, match="NATIVE_DIAGNOSTIC_FAILURE_WITHOUT_HOLD"):
        module.OwnedNativeCameraRunEvidence(canonical(document))


@pytest.mark.parametrize(
    "defect",
    [
        "schema",
        "source",
        "permit",
        "endpoint",
        "raw-hash",
        "raw-count",
        "release",
        "prepared-hash",
        "qualified",
        "native-frame",
        "fixture-domain",
        "invented-frame-hash",
    ],
)
def test_capture_evidence_denies_rehashed_wrong_domain_or_binding(tmp_path, defect):
    prepared, _, evidence = fixture_evidence(tmp_path)
    document = evidence.to_dict()
    if defect == "schema":
        document["schema"] = module.SCHEMA
    elif defect == "source":
        document["source_sha256"] = "0" * 64
    elif defect in {"permit", "endpoint"}:
        key = "permit_sha256" if defect == "permit" else "endpoint"
        document["preparation"]["admission_request"][key] = "0" * 64
    elif defect == "raw-hash":
        document["stdout"]["retained_sha256"] = "0" * 64
    elif defect == "raw-count":
        document["stdout"]["retained_bytes"] += 1
    elif defect == "release":
        document["release_check_passed"] = False
    elif defect == "prepared-hash":
        document["preparation_sha256"] = "0" * 64
    elif defect == "qualified":
        document["hardware_qualified"] = True
    elif defect == "fixture-domain":
        document["fixture_preparation"] = {}
    else:
        frame = document["validated_result"]["native_receipt"]["frames"][0]
        frame["length_bytes" if defect == "native-frame" else "sha256"] = "0" * 64
    payload = canonical(document)
    with pytest.raises((ValueError, RuntimeError)):
        module.verify_owned_native_camera_run_evidence(
            document,
            expected_preparation_sha256=prepared.preparation_sha256,
            expected_evidence_sha256=digest(payload),
        )


def test_capture_metadata_then_explicit_fixed_temp_file_check(tmp_path):
    prepared, inputs, evidence = fixture_evidence(tmp_path)
    output = Path(prepared.camera_plan.request.output_directory)
    output.mkdir(parents=True)
    frame = bytes(range(16))
    (output / "frame-000000.yuy2").write_bytes(frame)
    typed = validate_capture_artifacts(
        inputs["result"]["native_receipt"],
        request=prepared.camera_plan.request,
    )
    assert typed.frames[0].sha256 == digest(frame)
    # File validation is a separate artifact; it never upgrades retained process
    # metadata into a pixel-verified or physical-qualified record in place.
    assert evidence.safe_summary()["frame_content_verified"] is False
    assert not hasattr(evidence.native_receipt.frames[0], "sha256")


def test_malformed_output_retains_available_raw_bytes_without_native_claim(tmp_path):
    _, inputs, _ = fixture_evidence(tmp_path)
    inputs.update(
        result=None, native_validated=False, primary_error="MALFORMED_NATIVE_RESULT"
    )
    inputs["observed"]["stdout"] = inputs["ready_wire"] + b"malformed-native-output\xff"
    value = module.retain_owned_native_camera_run(**inputs)
    assert value.native_receipt is None
    assert value.safe_summary()["capture_metadata"] is None
    assert value.safe_summary()["status"] == "FAILED"
    assert base64.b64decode(value.to_dict()["stdout"]["base64"]).endswith(b"\xff")


def test_current_physical_capture_stays_held_without_any_owner(tmp_path):
    prepared, inputs, _ = fixture_evidence(tmp_path)
    inputs.update(
        primary_error="PHYSICAL_PROVIDER_QUALIFICATION_HELD",
        observed={},
        ready_wire=b"",
        release_wire=b"",
        result=None,
        native_validated=False,
        release_check_passed=False,
    )
    evidence = module.retain_owned_native_camera_run(**inputs)
    assert evidence.safe_summary()["status"] == "HELD"
    assert evidence.safe_summary()["process_created"] is False
    assert evidence.native_receipt is None
    assert evidence.to_dict()["preparation_sha256"] == prepared.preparation_sha256


def test_exact_capture_parent_handshake_returns_metadata_without_file_reads(
    tmp_path, monkeypatch
):
    from rocell.providers.windows.native_camera_parent_admission import (
        NativeCameraParentHandshake,
    )

    prepared, inputs, _ = fixture_evidence(tmp_path)
    checks = []

    def current(exact):
        assert exact.payload == prepared.payload
        checks.append(exact.preparation_sha256)

    parent = NativeCameraParentHandshake(
        prepared,
        cancellation=Event(),
        revalidate_consumed_permit=current,
        _clock=lambda: 1_000_000_000,
    )

    def forbidden(*args, **kwargs):
        pytest.fail("capture parent metadata validation accessed a file")

    with monkeypatch.context() as guard:
        for name in ("open", "stat", "lstat", "iterdir", "mkdir"):
            guard.setattr(Path, name, forbidden)
        assert (
            parent.begin(deadline_ns=20_000_000_000)
            == prepared.admission_request.wire()
        )
        parent.check_start_boundary()
        assert (
            parent.accept_ready(inputs["ready_wire"], owned_child_pid=123)
            == inputs["release_wire"]
        )
        parent.check_release()
        raw, metadata = parent.accept_result(
            canonical(inputs["result"]) + b"\n", returncode=0
        )
    assert raw == inputs["result"]
    assert type(metadata) is NativeCameraReceiptMetadata
    assert not hasattr(metadata.frames[0], "sha256")
    assert len(checks) == 2
    assert parent.view()["physical_authority"] is False


def test_actual_production_runner_interface_holds_capture_before_owner_or_callback(
    tmp_path, monkeypatch
):
    from rocell.providers.windows import owned_native_camera_runner as runner_module

    prepared = preparation(tmp_path)

    def forbidden(*args, **kwargs):
        pytest.fail("held native capture attempted runtime/owner/authorization access")

    runner = runner_module.OwnedNativeCameraRunner(
        prepared, revalidate_consumed_permit=forbidden
    )
    with monkeypatch.context() as guard:
        guard.setattr(runner_module, "_new_owner", forbidden)
        for name in ("open", "stat", "lstat", "iterdir", "mkdir", "resolve"):
            guard.setattr(Path, name, forbidden)
        result = runner.run(
            cancellation=Event(), deadline_ns=time.monotonic_ns() + 20_000_000_000
        )
    assert result.to_dict()["schema"] == module.CAPTURE_SCHEMA
    assert result.safe_summary()["status"] == "HELD"
    assert result.safe_summary()["process_created"] is False
    assert result.native_receipt is None
    with pytest.raises(ValueError, match="ALREADY_CONSUMED"):
        runner.run(cancellation=Event(), deadline_ns=1)


def test_legacy_probe_failed_receipt_cannot_be_rehashed_as_success(tmp_path):
    from test_native_camera_parent_admission import preparation as probe_preparation
    from rocell.providers.windows.native_camera_protocol import native_camera_release

    _, inputs, _ = fixture_evidence(tmp_path)
    probe = probe_preparation(tmp_path)
    ready = NativeCameraReady(
        canonical(
            {
                "schema": READY_SCHEMA,
                "request_sha256": probe.admission_request.request_sha256,
                "child_pid": 123,
                "challenge": "1" * 64,
            }
        )
    )
    release = native_camera_release(probe.admission_request, ready)
    inner = receipt("probe")
    inner.update(status="FAILED", reason_code="SOURCE_SHUTDOWN_FAILED")
    inner["cleanup"]["source_shutdown_hr"] = -1
    raw = {
        "schema": RESULT_SCHEMA,
        "request_sha256": probe.admission_request.request_sha256,
        "child_pid": 123,
        "challenge_sha256": ready.challenge_sha256,
        "permit_sha256": probe.admission_request.to_dict()["permit_sha256"],
        "native_receipt": inner,
    }
    inputs.update(
        probe=probe,
        result=raw,
        ready_wire=ready.payload + b"\n",
        release_wire=release,
        primary_error="NATIVE_DIAGNOSTIC_FAILED",
    )
    inputs["observed"].update(
        returncode=1,
        written=len(probe.admission_request.wire()) + len(release),
        stdout=ready.payload + b"\n" + canonical(raw) + b"\n",
    )
    valid = module.retain_owned_native_camera_run(**inputs)
    assert valid.to_dict()["schema"] == module.SCHEMA
    assert valid.safe_summary()["status"] == "FAILED"
    document = valid.to_dict()
    document.update(primary_error=None, status="SUCCEEDED_NATIVE_DIAGNOSTIC")
    with pytest.raises(ValueError, match="NATIVE_DIAGNOSTIC_FAILURE_WITHOUT_HOLD"):
        module.OwnedNativeCameraRunEvidence(canonical(document))
