"""Export a bounded historical owned-arm record without reopening or replaying it.

This is a developer diagnostic inspector, not a commissioning audit or current
qualification. Use the matching source version's decoder. It leaves the original
M1 record unchanged and exports only hashes/counts/status, never raw serial bytes.
"""

from __future__ import annotations

import argparse
import base64
import hashlib
import json
from pathlib import Path

from rocell.application.arm_feedback_rehearsal_campaign import _canonical, _decode
from rocell.application.owned_arm_feedback_rehearsal_campaign import SCHEMA
from rocell.application.wizard_diagnostic_export import (
    WizardDiagnosticExporter,
    verify_export,
)
from rocell.application.wizard_diagnostic_coordinator import (
    require_regular_path,
    source_fingerprint,
)
from rocell.providers.windows.arm_owned_evidence import ArmOwnedEvidence


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument(
        "record",
        type=Path,
        help="One explicit original M1 CAMPAIGN_EVIDENCE JSON record",
    )
    args = parser.parse_args()
    record_path = args.record.absolute()
    require_regular_path(record_path, directory=False)
    with record_path.open("rb") as stream:
        raw = stream.read(512 * 1024 + 1)
    if len(raw) > 512 * 1024:
        raise ValueError("Record exceeds inspector budget")
    record = json.loads(raw)
    if (
        record.get("kind") != "CAMPAIGN_EVIDENCE"
        or len(record["data"]["evidence"]) != 1
    ):
        raise ValueError("One exact campaign evidence record required")
    entry = record["data"]["evidence"][0]
    payload = base64.b64decode(entry["payload_base64"], validate=True)
    payload_hash = hashlib.sha256(payload).hexdigest()
    if (
        len(payload) != entry["payload_bytes"]
        or payload_hash != entry["payload_sha256"]
    ):
        raise ValueError("Retained payload integrity mismatch")
    document = _decode(payload)
    if document["schema"] != SCHEMA:
        raise ValueError("Wrong campaign schema")
    owned = ArmOwnedEvidence(_canonical(document["owned_evidence"]))
    if owned.evidence_sha256 != document["owned_evidence_sha256"]:
        raise ValueError("Owned evidence hash mismatch")
    if (
        owned.outer_request.to_dict()["permit_sha256"]
        != record["data"]["permit_sha256"]
    ):
        raise ValueError("Record/owned permit mismatch")
    if owned.request.campaign_id != record["data"]["attempt_id"]:
        raise ValueError("Record/owned attempt mismatch")
    if document.get("permit_sha256") != owned.outer_request.to_dict()["permit_sha256"]:
        raise ValueError("Wrapper/owned permit mismatch")
    plan = document.get("plan")
    if (
        type(plan) is not dict
        or plan.get("source_sha256") != owned.request.source_sha256
    ):
        raise ValueError("Wrapper/owned source mismatch")
    started = document.get("request_started_monotonic_ns")
    finished = document.get("worker_finished_monotonic_ns")
    process_elapsed = owned.to_dict()["process"]["report"]["elapsed_ns"]
    # Direct displayed-metadata consistency only. This does not verify the
    # historical permit, power observation, predecessors or full M1 journal.
    if (
        type(started) is not int
        or type(finished) is not int
        or not 0 < started <= finished < 2**63
        or started != owned.request.feedback.requested_monotonic_ns
        or finished - started < process_elapsed
    ):
        raise ValueError("Wrapper/owned process timing mismatch")
    summary = {
        "schema": "rocell.historical_owned_arm_diagnostic.v1",
        "status": "HISTORICAL_STRUCTURAL_INSPECTION_ONLY",
        "full_m1_audit_performed": False,
        "current_qualification": False,
        "worker_replayed": False,
        "original_record": str(record_path),
        "original_record_sha256": hashlib.sha256(raw).hexdigest(),
        "campaign_payload_sha256": payload_hash,
        "campaign_payload_bytes": len(payload),
        "process_summary": owned.safe_summary(),
        "process_elapsed_ns": process_elapsed,
        "wrapper_elapsed_ns": finished - started,
        "physical_authority": False,
        "meaning": "Bounded stored-artifact integrity and structural decoding only. This does not authenticate the full M1 journal, restore the session, establish current authority or infer power state.",
    }
    workspace = Path(__file__).resolve().parents[2]
    exporter = WizardDiagnosticExporter(workspace / "software/runs/wizard-exports")
    exporter.prepare(create=False)
    receipt = exporter.export(
        {
            "mode": "rehearsal",
            "session_id": owned.request.feedback.run_id,
            "source_binding_sha256": document["plan"]["source_sha256"],
            "inspector_source_sha256": source_fingerprint(workspace),
            "historical_owned_arm_diagnostic": summary,
            "physical_authority": False,
        },
        [],
        attachments={"historical-owned-arm.json": _canonical(summary)},
    )
    checked = verify_export(Path(receipt["path"]))
    if checked["valid"] is not True:
        raise ValueError("Diagnostic export verification failed")
    print(
        json.dumps(
            {
                "export": receipt["path"],
                "verification": checked["status"],
                "payload_sha256": payload_hash,
                "process": summary["process_summary"]["process"],
                "process_elapsed_ns": summary["process_elapsed_ns"],
                "wrapper_elapsed_ns": summary["wrapper_elapsed_ns"],
            },
            indent=2,
        )
    )


if __name__ == "__main__":
    main()
