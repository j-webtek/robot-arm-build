"""Historical inspector only: incapable evidence, temporary structural envelopes.

These envelopes deliberately are not qualified M1 ledgers. The success case
redirects the assigned export root to tmp_path but uses the real exporter and
verifier. No original incident records, processes or device APIs are accessed.
"""

import base64
import hashlib
import importlib.util
import json
from pathlib import Path
import subprocess
import sys

import pytest

from rocell.application.wizard_diagnostic_export import (
    WizardDiagnosticExporter,
    verify_export,
)
from rocell.providers.windows.arm_feedback_worker import ArmFeedbackWorker
from rocell.providers.windows.nonpurging_serial_api import WindowsNativeSerialApi
from test_arm_owned_evidence import owned_fixture


SCRIPT = Path(__file__).parents[2] / "scripts/inspect_owned_arm_failure.py"


def _json(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode("ascii")


def _entry(document):
    payload = _json(document)
    return {
        "payload_base64": base64.b64encode(payload).decode("ascii"),
        "payload_bytes": len(payload),
        "payload_sha256": hashlib.sha256(payload).hexdigest(),
    }


@pytest.fixture
def inspection_case(tmp_path, monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("historical inspection attempted worker/process/device replay")

    monkeypatch.setattr(subprocess, "Popen", forbidden)
    monkeypatch.setattr(WindowsNativeSerialApi, "_kernel", forbidden)
    spec = importlib.util.spec_from_file_location("owned_arm_inspector_test", SCRIPT)
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    request, inner, _, _, _, _, _, _, _, evidence, _, _ = owned_fixture()
    monkeypatch.setattr(ArmFeedbackWorker, "run", forbidden)
    started = inner.feedback.requested_monotonic_ns
    # Only the fields this explicitly structural inspector consumes are modeled;
    # no session header, journal, reviewed predecessor or permit audit is implied.
    document = {
        "schema": module.SCHEMA,
        "plan": {"source_sha256": inner.source_sha256},
        "permit_sha256": request.to_dict()["permit_sha256"],
        "owned_evidence": evidence.to_dict(),
        "owned_evidence_sha256": evidence.evidence_sha256,
        "request_started_monotonic_ns": started,
        "worker_finished_monotonic_ns": started + 1_000_000_000,
    }
    record = {
        "kind": "CAMPAIGN_EVIDENCE",
        "data": {
            "attempt_id": inner.campaign_id,
            "permit_sha256": request.to_dict()["permit_sha256"],
            "evidence": [_entry(document)],
        },
    }
    path = tmp_path / "structural-record.json"
    monkeypatch.setattr(sys, "argv", [str(SCRIPT), str(path)])
    # Source selection is not this inspector's audit. Keep the test independent
    # of current workspace source churn and assert its explicitly separate label.
    monkeypatch.setattr(module, "source_fingerprint", lambda workspace: "e" * 64)
    return module, record, document, evidence, path


def test_structural_inspection_exports_only_raw_free_diagnostics(
    inspection_case, tmp_path, monkeypatch, capsys
):
    module, record, document, evidence, path = inspection_case
    original = _json(record)
    path.write_bytes(original)
    exports = tmp_path / "assigned-exports"
    exports.mkdir()
    # Redirect the script's fixed assigned root, not its serialization or checks.
    monkeypatch.setattr(
        module,
        "WizardDiagnosticExporter",
        lambda root: WizardDiagnosticExporter(exports),
    )
    module.main()
    printed = json.loads(capsys.readouterr().out)
    destination = Path(printed["export"])
    assert destination.parent == exports
    assert verify_export(destination)["valid"] is True
    assert path.read_bytes() == original
    report = json.loads((destination / "report.json").read_bytes())
    snapshot = report["snapshot"]
    summary = snapshot["historical_owned_arm_diagnostic"]
    attachment = json.loads(
        (destination / "attachment-historical-owned-arm.json").read_bytes()
    )
    assert attachment == summary
    assert summary["status"] == "HISTORICAL_STRUCTURAL_INSPECTION_ONLY"
    for flag in (
        "full_m1_audit_performed",
        "current_qualification",
        "worker_replayed",
        "physical_authority",
    ):
        assert summary[flag] is False
    assert summary["original_record_sha256"] == hashlib.sha256(original).hexdigest()
    assert (
        summary["campaign_payload_sha256"]
        == record["data"]["evidence"][0]["payload_sha256"]
    )
    assert (
        summary["campaign_payload_bytes"]
        == record["data"]["evidence"][0]["payload_bytes"]
    )
    assert summary["process_summary"] == evidence.safe_summary()
    assert snapshot["source_binding_sha256"] == document["plan"]["source_sha256"]
    assert snapshot["inspector_source_sha256"] == "e" * 64
    assert snapshot["physical_authority"] is False
    assert summary["process_summary"]["device_cleanup_proven"] is False
    assert (
        summary["process_summary"]["final_power_state"]
        == "UNKNOWN_REQUIRES_SEPARATE_OBSERVATION"
    )
    # Exact raw records remain in the original, not in this diagnostic export.
    private = evidence.to_dict()["process"]
    rendered = b"\n".join(file.read_bytes() for file in destination.iterdir())
    for field in ("stdout", "stderr"):
        encoded = private[field]["base64"]
        if encoded:
            assert encoded.encode("ascii") not in rendered
    assert b'"base64"' not in rendered
    assert b'"owned_evidence"' not in rendered
    assert b'"feedback_evidence"' not in rendered
    assert b'"payload_base64"' not in rendered


@pytest.mark.parametrize(
    "defect,match",
    [
        ("byte-count", "payload integrity"),
        ("payload-hash", "payload integrity"),
        ("attempt", "attempt mismatch"),
        ("permit", "permit mismatch"),
        ("owned-hash", "Owned evidence hash"),
        ("campaign-schema", "Wrong campaign schema"),
        ("kind", "exact campaign evidence"),
        ("multiple-evidence", "exact campaign evidence"),
        ("wrapper-permit", "Wrapper/owned permit mismatch"),
        ("plan-source", "Wrapper/owned source mismatch"),
        ("negative-duration", "Wrapper/owned process timing mismatch"),
        ("boolean-timestamp", "Wrapper/owned process timing mismatch"),
        ("understated-process-duration", "Wrapper/owned process timing mismatch"),
    ],
)
def test_tampered_structural_or_hash_joins_are_denied_before_export(
    inspection_case, monkeypatch, defect, match
):
    module, record, document, _, path = inspection_case
    entry = record["data"]["evidence"][0]
    if defect == "byte-count":
        entry["payload_bytes"] += 1
    elif defect == "payload-hash":
        entry["payload_sha256"] = "f" * 64
    elif defect == "attempt":
        record["data"]["attempt_id"] = "attempt-" + "f" * 32
    elif defect == "permit":
        record["data"]["permit_sha256"] = "f" * 64
    elif defect == "owned-hash":
        document["owned_evidence_sha256"] = "f" * 64
        record["data"]["evidence"] = [_entry(document)]
    elif defect == "campaign-schema":
        document["schema"] = "rocell.wrong_campaign.v1"
        record["data"]["evidence"] = [_entry(document)]
    elif defect == "kind":
        record["kind"] = "RESULT"
    elif defect == "multiple-evidence":
        record["data"]["evidence"].append(dict(entry))
    else:
        if defect == "wrapper-permit":
            document["permit_sha256"] = "f" * 64
        elif defect == "plan-source":
            document["plan"]["source_sha256"] = "f" * 64
        elif defect == "negative-duration":
            document["worker_finished_monotonic_ns"] = (
                document["request_started_monotonic_ns"] - 1
            )
        elif defect == "boolean-timestamp":
            document["request_started_monotonic_ns"] = True
        else:
            elapsed = document["owned_evidence"]["process"]["report"]["elapsed_ns"]
            assert elapsed > 0
            document["worker_finished_monotonic_ns"] = (
                document["request_started_monotonic_ns"] + elapsed - 1
            )
        record["data"]["evidence"] = [_entry(document)]
    original = _json(record)
    path.write_bytes(original)

    def no_export(*args, **kwargs):
        pytest.fail("invalid historical record reached export")

    monkeypatch.setattr(module, "WizardDiagnosticExporter", no_export)
    with pytest.raises(ValueError, match=match):
        module.main()
    assert path.read_bytes() == original


@pytest.mark.parametrize("defect", ["invalid-base64", "invalid-json", "oversize"])
def test_malformed_or_oversize_record_is_rejected_without_modifying_it(
    inspection_case, monkeypatch, defect
):
    module, record, _, _, path = inspection_case
    if defect == "invalid-base64":
        record["data"]["evidence"][0]["payload_base64"] = "not base64 !"
        original = _json(record)
    elif defect == "invalid-json":
        original = b'{"kind":not-json}'
    else:
        original = b" " * (512 * 1024 + 1)
    path.write_bytes(original)

    def no_export(*args, **kwargs):
        pytest.fail("malformed historical record reached export")

    monkeypatch.setattr(module, "WizardDiagnosticExporter", no_export)
    with pytest.raises(ValueError):
        module.main()
    assert path.read_bytes() == original
