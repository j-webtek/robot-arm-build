"""Explicit file-only public wizard lifecycle; never retry an uncertain write.

Uses the real current workspace, original M1 storage, public prepare/execute
actions and assigned exports. The sole input is a clearly labeled software
fixture; every physical observation remains UNKNOWN. No endpoint discovery,
native process, camera acquisition, serial operation or motion is requested.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import verify_export
from wizard_physical_camera_setup_smoke import assert_no_hardware, emit, require

ALLOWED = frozenset(
    {
        "physical_camera_initialize",
        "physical_camera_prerequisites",
        "physical_camera_assess_sources",
        "physical_camera_review_sources",
        "physical_camera_discover",
        "physical_camera_reopen",
        "physical_intake_start",
        "physical_intake_record",
        "physical_intake_files_discover",
        "physical_intake_submit",
        "physical_intake_review",
        "physical_intake_export_originals",
        "record_note",
        "export_logs",
    }
)
FIXTURE = "software-fixture-unknown-intake.txt"


def action(service, name, values=None):
    require(name in ALLOWED, "Closed file-only action set")
    ticket = service.prepare_action(name, values or {}, service.view()["revision"])
    dispatched = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + 250
    while time.monotonic() < deadline:
        result = service.operation(dispatched["operation_id"])
        if result["status"] in {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED"}:
            emit(
                "action",
                {
                    "action_id": name,
                    "status": result["status"],
                    "operation_id": result["operation_id"],
                },
            )
            if result["status"] != "SUCCEEDED":
                emit("retained failure; no retry", result)
            require(
                result["status"] == "SUCCEEDED",
                "Original action failed; inspect without retry",
            )
            assert_no_hardware(service.view())
            return result
        time.sleep(0.05)
    raise TimeoutError("Original outcome unknown; no retry or replacement")


def export(service, expected_submission):
    result = action(service, "export_logs")
    folder = Path(result["result"]["receipt"]["path"])
    require(
        folder.parent == service.workspace / "software/runs/wizard-exports",
        "Assigned export parent changed",
    )
    require(verify_export(folder)["valid"] is True, "Export verification failed")
    document = json.loads((folder / "attachment-intake-evidence.json").read_bytes())
    require(document["original_bytes_preserved"] is True, "Metadata was redacted")
    require(
        document["collections"][0]["submission"]["evidence_sha256"]
        == expected_submission,
        "Original submission hash changed",
    )
    emit(
        "verified metadata export",
        {"path": str(folder), "submission_sha256": expected_submission},
    )
    return folder


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--expected-source-sha256", required=True)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[2]
    require(
        source_fingerprint(workspace) == args.expected_source_sha256,
        "Source changed before launch",
    )
    first = ArrivalWizardService(workspace, mode="physical")
    try:
        emit(
            "first launch",
            {"launch_id": first.session_id, "source_sha256": first.source_sha256},
        )
        action(first, "physical_camera_initialize")
        action(first, "physical_camera_prerequisites")
        action(
            first,
            "physical_camera_assess_sources",
            {"operator_id": "source-check-operator", "file_only": True},
        )
        action(
            first,
            "physical_camera_review_sources",
            {"reviewer_id": "source-check-reviewer", "file_only": True},
        )
        original = first.view()["physical_camera_setup"]
        action(first, "physical_intake_start")
        for row in first.view()["physical_intake"]["notebook"]["rows"]:
            action(
                first,
                "physical_intake_record",
                {
                    "record_id": row["record_id"],
                    "observation_status": "UNKNOWN",
                    "observed_value": "Hardware unavailable; no physical observation made.",
                    "method": "Software-only onboarding walkthrough; not measured.",
                    "evidence_note": "Explanatory software fixture only; no physical evidence supplied.",
                    "operator_id": "software-walkthrough-operator",
                },
            )
        action(first, "physical_intake_files_discover")
        files = first.view()["physical_intake_evidence"]["discovery"]["files"]
        selected = [row for row in files if row["basename"] == FIXTURE]
        require(len(selected) == 1, "Explicit software fixture is missing or refused")
        rows = first.view()["physical_intake"]["notebook"]["rows"]
        values = {
            "file_only": True,
            "operator_id": "software-walkthrough-operator",
            **{
                "attachment_" + row["record_id"]: selected[0]["choice_id"]
                for row in rows
            },
        }
        action(first, "physical_intake_submit", values)
        submitted = first.view()["physical_intake_evidence"]["collection"]
        sha = submitted["submission"]["submission_sha256"]
        require(
            submitted["submission"]["coverage"]["unknown"] == 16,
            "Unknown became observed",
        )
        require(
            submitted["submission"]["coverage"]["attachment_count"] == 1,
            "Duplicate bytes retained",
        )
        first_export = export(first, sha)
    finally:
        first.shutdown()
    require(
        source_fingerprint(workspace) == args.expected_source_sha256,
        "Source changed before restart",
    )
    second = ArrivalWizardService(workspace, mode="physical")
    try:
        action(second, "physical_camera_discover")
        choices = [
            row["value"]
            for row in second._physical_camera_setup.reopen_choices()
            if second._physical_camera_setup.reopen_preview(row["value"])[
                "origin_launch_id"
            ]
            == original["origin_launch_id"]
        ]
        require(len(choices) == 1, "Original store not uniquely discoverable")
        action(second, "physical_camera_reopen", {"choice_id": choices[0]})
        restored = second.view()["physical_intake_evidence"]
        require(
            restored["collection"] == submitted,
            "Submission changed on original restart",
        )
        require(
            restored["discovery"]["status"] == "NOT_DISCOVERED",
            "Inbox was silently scanned",
        )
        require(
            second.view()["physical_intake"]["notebook"] is None,
            "Draft was automatically imported",
        )
        action(
            second,
            "physical_intake_review",
            {
                "file_only": True,
                "reviewer_id": "software-walkthrough-reviewer",
                "decision": "ACKNOWLEDGE_FOR_LATER_STAGE_REVIEW",
            },
        )
        raw = action(
            second,
            "physical_intake_export_originals",
            {"file_only": True, "include_private_originals": True},
        )
        raw_receipt = raw["result"]["steps"][0]["report"]["private_original_export"]
        require(
            raw_receipt["original_bytes_preserved"] is True, "Raw export bytes differ"
        )
        for index in range(9):
            action(
                second,
                "record_note",
                {
                    "note": f"Original intake retention after restart, rotation check {index}; no hardware."
                },
            )
        second_export = export(second, sha)
        setup = second.view()["physical_camera_setup"]
        require(
            setup["session"]["stages"][0]["state"] == "BLOCKED",
            "Source verdict changed",
        )
        require(
            all(row["state"] == "PENDING" for row in setup["session"]["stages"][1:]),
            "Downstream stage advanced",
        )
        require(
            setup["source_workflow"]["review"] == original["source_workflow"]["review"],
            "Original source review was rewritten",
        )
        emit(
            "verified original intake lifecycle",
            {
                "source_sha256": args.expected_source_sha256,
                "origin_launch_id": original["origin_launch_id"],
                "current_launch_id": second.session_id,
                "submission_sha256": sha,
                "first_export": str(first_export),
                "reopened_export": str(second_export),
                "private_original_export": raw_receipt,
                "physical_authority": False,
            },
        )
        return 0
    finally:
        second.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
