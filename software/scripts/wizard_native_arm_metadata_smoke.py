"""Explicit actual-app rehearsal: no native metadata collection or device open.

Run after source edits stop, supplying the independently recorded source hash.
All child actions are incapable fixtures; exports use the user's workspace folder.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.application.physical_onboarding_durability import read_bounded_regular_file


CLOSED_ACTIONS = frozenset(
    {
        "rehearse_device_inventory",
        "review_arm_candidate",
        "rehearse_native_arm_metadata",
        "record_note",
        "export_logs",
    }
)


def action(service, name, values):
    if name not in CLOSED_ACTIONS:
        raise ValueError("Only the fixed incapable rehearsal workflow is allowed")
    ticket = service.prepare_action(name, values, service.view()["revision"])
    receipt = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        operation = service.operation(receipt["operation_id"])
        if operation["status"] in {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED"}:
            print(
                json.dumps(
                    {
                        "action": name,
                        "operation_id": operation["operation_id"],
                        "status": operation["status"],
                    }
                ),
                flush=True,
            )
            if operation["status"] != "SUCCEEDED":
                # One separate export for a known failure, never replay or an
                # export recursion. Unknown/running outcomes start no action.
                if name != "export_logs":
                    try:
                        action(service, "export_logs", {})
                    except Exception:
                        pass  # Preserve the original failure as the primary cause.
                raise RuntimeError(json.dumps(operation["result"]))
            assert operation["completion_log_persisted"] is True
            return operation
        time.sleep(0.02)
    raise TimeoutError("Original diagnostic outcome unknown; no additional action")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--source", required=True)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[2]
    if source_fingerprint(workspace) != args.source:
        raise RuntimeError("Source must match the independently supplied frozen hash")
    service = ArrivalWizardService(workspace, mode="rehearsal")
    try:
        assert service.view()["native_arm_metadata"]["status"] == "NOT_INSPECTED"
        action(service, "rehearse_device_inventory", {"scenario": "nominal"})
        candidates = service.view()["device_selection"]["devices"]["SERIAL"][
            "candidates"
        ]
        assert (
            len(candidates) == 1
        )  # Closed fixture, never choose real hardware automatically.
        action(
            service,
            "review_arm_candidate",
            {
                "choice_id": candidates[0]["choice_id"],
                "reviewer_id": "rehearsal-reviewer",
                "metadata_only": True,
            },
        )
        observed = action(
            service,
            "rehearse_native_arm_metadata",
            {"scenario": "nominal", "metadata_only": True},
        )
        report = observed["result"]["steps"][0]["report"]
        assert report["status"] == "METADATA_CORRELATED"
        assert observed["result"]["metadata_inventory_performed"] is False
        assert all(
            observed["result"][key] == 0
            for key in (
                "device_open_count",
                "serial_write_count",
                "power_event_count",
                "motion_command_count",
                "contact_command_count",
            )
        )
        for index in range(9):
            action(
                service,
                "record_note",
                {
                    "note": f"Incapable native arm metadata retention check {index + 1}; no physical evidence."
                },
            )
        assert service.operation(observed["operation_id"])["result"] is None
        exported = action(service, "export_logs", {})
        directory = Path(exported["result"]["receipt"]["path"])
        assert directory.parent == workspace / "software/runs/wizard-exports"
        assert verify_export(directory)["valid"] is True
        payload = read_bounded_regular_file(
            directory / "attachment-native-arm-metadata.json", maximum_bytes=1024 * 1024
        )
        retained = json.loads(payload)
        assert retained["publication"] == "CURRENT"
        assert retained["result"]["steps"][0]["report"] == report
        view = service.view()
        assert len(view["stages"]) == 15
        assert all(stage["state"] == "PHYSICAL_PENDING" for stage in view["stages"])
        assert (
            view["native_arm_metadata"]["report"]["report_sha256"]
            == report["report_sha256"]
        )
        assert not view["native_arm_metadata"]["connected"]
        assert source_fingerprint(workspace) == args.source
        print(
            json.dumps(
                {
                    "source": args.source,
                    "session_id": service.session_id,
                    "report_sha256": report["report_sha256"],
                    "export": str(directory),
                    "manifest_sha256": exported["result"]["receipt"].get(
                        "manifest_sha256"
                    ),
                    "physical_authority": False,
                }
            ),
            flush=True,
        )
    finally:
        service.shutdown()


if __name__ == "__main__":
    main()
