"""Pure fault projection; the optional original record check is read-only."""

import base64
from dataclasses import replace
import hashlib
import json
from pathlib import Path
import subprocess

import pytest

from rocell.application.camera_fault_diagnostics import (
    CameraFaultDiagnosticError,
    camera_fault_diagnostic,
)
from rocell.application.physical_onboarding_attempts import canonical_json_bytes
from rocell.application.rehearsal_owned_camera_evidence import (
    RehearsalOwnedCameraEvidence,
    retain_owned_camera_evidence,
    verify_owned_camera_evidence,
)
from test_owned_camera_configuration_campaign import configured_inputs
from test_rehearsal_owned_camera_evidence import complete_inputs


def rejection_inputs():
    """Explicit fixture of a rejected packet, never a verified native receipt."""
    inputs = configured_inputs()
    inputs["native_receipt"] = None
    inputs["error"] = {
        "code": "INVALID_CAMERA_CONTRACT",
        "error_type": "CameraWorkerError",
        "message": "INVALID_CAMERA_CONTRACT: requested control did not read back exactly",
    }
    return inputs


def test_exact_client_rejection_explains_fault_without_native_observations():
    evidence = retain_owned_camera_evidence(**rejection_inputs())
    before = evidence.payload
    result = camera_fault_diagnostic(evidence)
    assert result["schema"] == "rocell.camera_fault_diagnostic.v1"
    assert result["status"] == "FAULT_REPORTED"
    assert result["reason_category"] == "CONTROL_READBACK_MISMATCH_REPORTED"
    assert result["basis"] == "RETAINED_CALLER_ERROR_EXACT_MATCH"
    assert result["reported_code"] == "INVALID_CAMERA_CONTRACT"
    assert "not a verified observation" in result["reason"]
    assert result["evidence_sha256"] == evidence.evidence_sha256
    assert evidence.payload == before
    assert evidence.view()["native"] is None
    assert evidence.view()["status"] == "RETAINED_INCOMPLETE_REHEARSAL"
    for field in (
        "retry_this_attempt_allowed",
        "automatic_retry_allowed",
        "clear_quarantine_allowed",
        "physical_authority",
        "qualified",
    ):
        assert result[field] is False
    assert len(json.dumps(result).encode()) < 2048


@pytest.mark.parametrize(
    "change", ["prefix", "suffix", "code", "type", "missing", "extra"]
)
def test_only_complete_exact_error_signature_is_classified(change):
    inputs = rejection_inputs()
    error = inputs["error"]
    if change == "prefix":
        error["message"] = "UNTRUSTED " + error["message"]
    elif change == "suffix":
        error["message"] += " password=PRIVATE-SECRET"
    elif change == "code":
        error["code"] = "PRIVATE-SECRET"
    elif change == "type":
        error["error_type"] = "PRIVATE-SECRET"
    elif change == "missing":
        del error["error_type"]
    else:
        error["message"] = error["message"].replace("exactly", "exactly\u200b")
    result = camera_fault_diagnostic(retain_owned_camera_evidence(**inputs))
    assert result["reason_category"] == "UNCLASSIFIED_CALLER_ERROR"
    assert result["reported_code"] == "UNCLASSIFIED"
    assert "PRIVATE-SECRET" not in json.dumps(result)
    assert error["message"] not in json.dumps(result)


def test_no_requested_controls_cannot_be_explained_as_control_rejection():
    inputs = complete_inputs()
    inputs["error"] = rejection_inputs()["error"]
    result = camera_fault_diagnostic(retain_owned_camera_evidence(**inputs))
    assert result["reason_category"] == "UNCLASSIFIED_CALLER_ERROR"


@pytest.mark.parametrize(
    "status,category",
    [("CANCELLED", "OPERATION_CANCELLED"), ("TIMED_OUT", "OPERATION_TIMED_OUT")],
)
def test_cancellation_and_timeout_are_fixed_process_observations(status, category):
    inputs = rejection_inputs()
    inputs["process_result"] = replace(
        inputs["process_result"], status=status, primary_error="PRIVATE-SECRET"
    )
    result = camera_fault_diagnostic(retain_owned_camera_evidence(**inputs))
    assert result["reason_category"] == category
    assert result["basis"] == "RETAINED_PROCESS_STATUS"
    assert result["reported_code"] == status
    assert "PRIVATE-SECRET" not in json.dumps(result)


@pytest.mark.parametrize("errors,tree", [((), False), (("PRIVATE-SECRET",), True)])
def test_cleanup_uncertainty_has_priority_and_does_not_echo_resource_names(
    errors, tree
):
    inputs = rejection_inputs()
    inputs["process_result"] = replace(
        inputs["process_result"],
        status="TIMED_OUT",
        cleanup_errors=errors,
        tree_exit_confirmed=tree,
    )
    result = camera_fault_diagnostic(retain_owned_camera_evidence(**inputs))
    assert result["reason_category"] == "PROCESS_CLEANUP_UNCONFIRMED"
    assert "PRIVATE-SECRET" not in json.dumps(result)
    assert result["clear_quarantine_allowed"] is False


@pytest.mark.parametrize(
    "fault,category",
    [
        ("process", "PROCESS_EXECUTION_UNCONFIRMED"),
        ("wire", "NATIVE_EVIDENCE_UNVERIFIED"),
        ("capture", "CAPTURE_RETENTION_UNVERIFIED"),
        ("missing", "REQUEST_OR_PROCESS_EVIDENCE_UNAVAILABLE"),
    ],
)
def test_other_holds_remain_separate(fault, category):
    inputs = complete_inputs()
    if fault == "process":
        inputs["process_result"] = replace(inputs["process_result"], status="FAILED")
    elif fault == "wire":
        inputs["process_result"] = replace(
            inputs["process_result"], stdout=b"PRIVATE-SECRET", parsed_result=None
        )
        inputs["native_receipt"] = None
    elif fault == "capture":
        inputs["capture"] = None
    else:
        for name in (
            "activation_request",
            "process_result",
            "native_receipt",
            "capture",
            "capture_envelope",
            "source_contract",
        ):
            inputs[name] = None
    result = camera_fault_diagnostic(retain_owned_camera_evidence(**inputs))
    assert result["reason_category"] == category
    assert "PRIVATE-SECRET" not in json.dumps(result)


def test_no_fault_does_not_issue_permission_and_views_are_detached():
    evidence = retain_owned_camera_evidence(**complete_inputs())
    result = camera_fault_diagnostic(evidence)
    assert result["status"] == "NO_REPORTED_FAULT"
    assert result["reason_category"] == "NONE"
    assert result["reported_code"] is None
    assert result["retry_this_attempt_allowed"] is False
    result["physical_authority"] = True
    assert camera_fault_diagnostic(evidence)["physical_authority"] is False


@pytest.mark.parametrize("payload", [b"{}", b"null", b"not-json", b"[]"])
def test_dataclass_construction_is_not_evidence_validation(payload):
    with pytest.raises(CameraFaultDiagnosticError, match="bounded, valid"):
        camera_fault_diagnostic(RehearsalOwnedCameraEvidence(payload))


def test_unknown_schema_and_raw_hash_tampering_are_rejected():
    evidence = retain_owned_camera_evidence(**rejection_inputs())
    for field in ("schema", "stdout"):
        document = evidence.to_dict()
        if field == "schema":
            document[field] = "PRIVATE-SECRET"
        else:
            document[field]["sha256"] = "0" * 64
        forged = RehearsalOwnedCameraEvidence(canonical_json_bytes(document))
        with pytest.raises(CameraFaultDiagnosticError) as caught:
            camera_fault_diagnostic(forged)
        assert "PRIVATE-SECRET" not in str(caught.value)
    with pytest.raises(CameraFaultDiagnosticError):
        camera_fault_diagnostic(evidence.to_dict())


@pytest.mark.parametrize(
    "payload",
    [b"x" * (128 * 1024 + 1), "not-bytes", b""],
    ids=("over-limit", "not-bytes", "empty"),
)
def test_mutated_payload_budget_is_checked_before_json_decode(monkeypatch, payload):
    evidence = RehearsalOwnedCameraEvidence(b"{}")
    object.__setattr__(evidence, "payload", payload)

    def forbidden(*args):
        raise AssertionError("An invalid payload must not be decoded")

    monkeypatch.setattr(RehearsalOwnedCameraEvidence, "to_dict", forbidden)
    with pytest.raises(CameraFaultDiagnosticError):
        camera_fault_diagnostic(evidence)


def test_projection_has_no_file_process_device_or_recovery_calls(monkeypatch):
    evidence = retain_owned_camera_evidence(**rejection_inputs())

    def forbidden(*args, **kwargs):
        raise AssertionError("Projection must be pure")

    monkeypatch.setattr("builtins.open", forbidden)
    monkeypatch.setattr(Path, "open", forbidden)
    monkeypatch.setattr(Path, "read_bytes", forbidden)
    monkeypatch.setattr(Path, "stat", forbidden)
    monkeypatch.setattr(subprocess, "run", forbidden)
    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(
        "rocell.providers.windows.camera_worker_client.validate_capture_artifacts",
        forbidden,
    )
    monkeypatch.setattr(
        "rocell.providers.windows.camera_worker_client.WindowsCameraWorkerClient.capture",
        forbidden,
    )
    assert (
        camera_fault_diagnostic(evidence)["reason_category"]
        == "CONTROL_READBACK_MISMATCH_REPORTED"
    )


def test_original_retained_failure_read_only_when_available():
    """Historical structural/hash readback, NOT a full M1 audit/current approval."""
    directory = (
        Path(__file__).resolve().parents[3]
        / "software/runs/wizard-rehearsal/wizard-10fae4dbb9af43e5be77b17bb98247a5"
        / "cells/cell-b42429414c74719e11191e63b6d215fcddadf1900d2e9e5e7a867591e77c2dbf"
        / "rehearsal-records"
    )
    attempt = "attempt-38f34693a33e48838c193c8733b6076b"
    evidence_path = directory / f"evidence-{attempt}-retained.json"
    if not evidence_path.is_file():
        pytest.skip(
            "Optional original retained failure is not part of the source package"
        )
    result_path = directory / f"result-{attempt}-sealed_uncertain.json"
    originals = {path: path.read_bytes() for path in (evidence_path, result_path)}
    records = []
    for raw in originals.values():
        assert len(raw) <= 512 * 1024
        record = json.loads(raw)
        core = {key: value for key, value in record.items() if key != "record_sha256"}
        assert (
            hashlib.sha256(canonical_json_bytes(core)).hexdigest()
            == record["record_sha256"]
        )
        records.append(record)
    entry = records[0]["data"]["evidence"][0]
    payload = base64.b64decode(entry["payload_base64"], validate=True)
    expected_sha = "fb21b59256ce21aa8fe7d7508a54c03e580b5ffe13c29d0c4e1195f2ce3d749f"
    assert len(payload) == entry["payload_bytes"] == 10669
    assert (
        hashlib.sha256(payload).hexdigest() == entry["payload_sha256"] == expected_sha
    )
    document = json.loads(payload)
    for record in records:
        assert (
            record["data"]["attempt_id"] == document["binding"]["attempt_id"] == attempt
        )
        assert record["data"]["permit_sha256"] == document["binding"]["permit_sha256"]
    result_record = records[1]["data"]["result"]
    assert result_record["state"] == "SEALED_UNCERTAIN"
    assert result_record["quarantine_latched"] is True
    assert result_record["receipt"]["evidence_sha256s"] == [expected_sha]
    evidence = verify_owned_camera_evidence(payload, document["binding"])
    projection = camera_fault_diagnostic(evidence)
    assert projection["reason_category"] == "CONTROL_READBACK_MISMATCH_REPORTED"
    assert projection["clear_quarantine_allowed"] is False
    assert projection["evidence_sha256"] == expected_sha
    assert evidence.view()["process"]["tree_exit_confirmed"] is True
    assert evidence.view()["native"] is None
    assert all(path.read_bytes() == raw for path, raw in originals.items())
