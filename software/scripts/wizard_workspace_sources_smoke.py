"""One explicit file-only source assessment/review, export and original restart.

No OS device inventory, child process, camera or arm action is selected. A
failure stops this script without repeating the uncertain original operation.
All original stores and exports remain available for inspection.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_configuration_epochs import PhysicalConfigurationEpochs
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.native_camera_protocol import canonical
from wizard_physical_camera_setup_smoke import assert_no_hardware, require, emit

ALLOWED = frozenset(
    {
        "physical_camera_initialize",
        "physical_camera_prerequisites",
        "physical_camera_assess_sources",
        "physical_camera_review_sources",
        "physical_camera_discover",
        "physical_camera_reopen",
        "record_note",
        "export_logs",
    }
)


def action(service, name, values=None):
    require(name in ALLOWED, "Closed file-only action set")
    ticket = service.prepare_action(name, values or {}, service.view()["revision"])
    receipt = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + 250
    while time.monotonic() < deadline:
        outcome = service.operation(receipt["operation_id"])
        if outcome["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            emit(
                "action",
                {
                    "action_id": name,
                    "status": outcome["status"],
                    "operation_id": outcome["operation_id"],
                },
            )
            if outcome["status"] != "SUCCEEDED":
                emit("retained failure", outcome)
            require(
                outcome["status"] == "SUCCEEDED", "Original operation failed; no retry"
            )
            return outcome
        time.sleep(0.05)
    raise TimeoutError("Unknown original outcome; shutdown and inspect, never replay")


def export(service, workspace):
    outcome = action(service, "export_logs")
    receipt = outcome["result"]["receipt"]
    folder = Path(receipt["path"])
    require(
        folder.parent == workspace / "software/runs/wizard-exports",
        "Assigned export folder changed",
    )
    require(verify_export(folder)["valid"] is True, "Export verification failed")
    document = json.loads(
        (folder / "attachment-workspace-source-workflow.json").read_bytes()
    )
    require(
        document["original_bytes_preserved"] is True,
        "Export redacted original evidence",
    )
    require(
        document["publication"] == "REVIEWED_BLOCKED",
        "Original reviewed state not exported",
    )
    configuration = json.loads(
        (folder / "attachment-configuration-records.json").read_bytes()
    )
    require(
        configuration["original_bytes_preserved"] is True
        and configuration["publication"] == "CURRENT",
        "Original configuration record not exported exactly",
    )
    artifact = PhysicalConfigurationEpochs(canonical(configuration["document"]))
    require(
        artifact.sha256 == configuration["record"]["evidence_sha256"]
        and artifact.safe_summary()
        == service.view()["physical_camera_setup"]["configuration_records"]["summary"],
        "Exported configuration does not match the verified published record",
    )
    emit(
        "verified configuration export",
        {"path": str(folder), "record_sha256": artifact.sha256},
    )
    return receipt, document


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
            {"session_id": first.session_id, "source_sha256": first.source_sha256},
        )
        assert_no_hardware(first.view())
        action(first, "physical_camera_initialize")
        action(first, "physical_camera_prerequisites")
        action(
            first,
            "physical_camera_assess_sources",
            {"operator_id": "file-check-operator", "file_only": True},
        )
        require(
            first.view()["physical_camera_setup"]["source_workflow"]["status"]
            == "REVIEW_PENDING",
            "Assessment not published",
        )
        action(
            first,
            "physical_camera_review_sources",
            {"reviewer_id": "file-check-reviewer", "file_only": True},
        )
        original = first.view()["physical_camera_setup"]
        require(
            original["session"]["stages"][0]["state"] == "BLOCKED",
            "Expected reviewed BLOCKED stage",
        )
        require(
            all(row["state"] == "PENDING" for row in original["session"]["stages"][1:]),
            "Downstream stage advanced",
        )
        for index in range(9):
            action(
                first,
                "record_note",
                {"note": "File-only diagnostic rotation check " + str(index)},
            )
        first_export, first_document = export(first, workspace)
        assert_no_hardware(first.view())
        emit("first export", first_export)
    finally:
        first.shutdown()
    require(
        source_fingerprint(workspace) == args.expected_source_sha256,
        "Source changed before restart",
    )
    second = ArrivalWizardService(workspace, mode="physical")
    try:
        action(second, "physical_camera_discover")
        setup = second._physical_camera_setup
        choices = [
            row["value"]
            for row in setup.reopen_choices()
            if setup.reopen_preview(row["value"])["origin_launch_id"]
            == original["origin_launch_id"]
        ]
        require(len(choices) == 1, "Exact original store not uniquely discovered")
        action(second, "physical_camera_reopen", {"choice_id": choices[0]})
        reopened = second.view()["physical_camera_setup"]
        require(
            reopened["origin_launch_id"]
            == original["origin_launch_id"]
            != second.session_id,
            "Original launch was relabeled",
        )
        require(
            reopened["source_workflow"] == original["source_workflow"],
            "Original source summaries changed on restart",
        )
        require(
            reopened["configuration_records"] == original["configuration_records"],
            "Original configuration record changed or was rebuilt on restart",
        )
        require(
            reopened["session"]["stages"] == original["session"]["stages"],
            "Original stage state changed on restart",
        )
        second_export, second_document = export(second, workspace)
        for role in (
            "prerequisites",
            "receipt",
            "assessment",
            "review",
            "configuration_epochs",
        ):
            require(
                second_document[role + "_document"]
                == first_document[role + "_document"],
                "Original document changed: " + role,
            )
        assert_no_hardware(second.view())
        emit(
            "verified original restart",
            {
                "source_sha256": second.source_sha256,
                "origin_launch_id": reopened["origin_launch_id"],
                "current_launch_id": second.session_id,
                "review_sha256": reopened["source_workflow"]["review"]["review_sha256"],
                "physical_authority": False,
                "export": second_export,
            },
        )
        return 0
    finally:
        second.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
