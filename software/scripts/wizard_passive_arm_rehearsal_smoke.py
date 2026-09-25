"""Actual wizard nominal passive IPC rehearsal and verified export; no devices."""

import json
from pathlib import Path
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_diagnostic_export import verify_export


def action(service, name, values):
    if name not in {"rehearse_passive_arm_connection", "export_logs"}:
        raise ValueError(
            "Only the fixed incapable rehearsal/export sequence is allowed"
        )
    ticket = service.prepare_action(name, values, service.view()["revision"])
    receipt = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + 45
    while time.monotonic() < deadline:
        operation = service.operation(receipt["operation_id"])
        if operation["status"] in {"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED"}:
            if (
                operation["status"] != "SUCCEEDED"
                or not operation["completion_log_persisted"]
            ):
                raise RuntimeError(
                    f"{name}: retained operation {operation['operation_id']} did not succeed; no replay"
                )
            return operation
        time.sleep(0.05)
    raise TimeoutError("Original outcome unknown; no retry or subsequent action")


def main():
    workspace = Path(__file__).resolve().parents[2]
    service = ArrivalWizardService(workspace, mode="rehearsal")
    try:
        operation = action(
            service,
            "rehearse_passive_arm_connection",
            {"scenario": "lifecycle-nominal"},
        )
        result = operation["result"]
        for key in (
            "device_open_count",
            "serial_write_count",
            "power_event_count",
            "motion_command_count",
            "contact_command_count",
        ):
            if result[key] != 0:
                raise RuntimeError("Unexpected device effects")
        report = result["steps"][0]["report"]
        if (
            report["passive_summary"]["status"] != "OBSERVED_CLOSED"
            or report["passive_summary"]["origin"] != "SYNTHETIC_REHEARSAL"
        ):
            raise RuntimeError("Unexpected passive fixture outcome")
        exported = action(service, "export_logs", {})
        directory = Path(exported["result"]["receipt"]["path"])
        if verify_export(directory)["valid"] is not True:
            raise RuntimeError("Export verification failed")
        print(
            json.dumps(
                {
                    "operation_id": operation["operation_id"],
                    "source_sha256": service.source_sha256,
                    "status": "REHEARSAL_AND_EXPORT_VERIFIED",
                    "export_directory": str(directory),
                    "physical_authority": False,
                    "connected": False,
                },
                indent=2,
            )
        )
    finally:
        service.shutdown()


if __name__ == "__main__":
    main()
