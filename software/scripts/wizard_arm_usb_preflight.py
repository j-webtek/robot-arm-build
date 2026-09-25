"""Real USB metadata onboarding through the wizard; never opens a serial port.

Selection uses an explicit USB VID/PID/unit serial, not the first COM device.
The existing service owns process deadlines, correlation, logs, and exports.
This diagnostic does not commission the arm or remove live-backend holds.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_diagnostic_export import verify_export


ALLOWED_ACTIONS = frozenset(
    {
        "inventory_devices",
        "review_arm_candidate",
        "inspect_native_arm_metadata",
        "export_logs",
    }
)
TERMINAL = frozenset({"SUCCEEDED", "FAILED", "TIMED_OUT", "CANCELLED"})


class UnknownOutcome(RuntimeError):
    """Stop: do not export, retry, or start another action on a pending owner."""


def perform(service, name, values, *, timeout_s=60):
    if name not in ALLOWED_ACTIONS:
        raise ValueError("Only metadata and export actions are allowed")
    ticket = service.prepare_action(name, values, service.view()["revision"])
    receipt = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + timeout_s
    while time.monotonic() < deadline:
        operation = service.operation(receipt["operation_id"])
        if operation["status"] in TERMINAL:
            if operation["status"] != "SUCCEEDED":
                raise RuntimeError(
                    f"{name}: {operation['status']}; inspect diagnostic export"
                )
            if operation.get("completion_log_persisted") is not True:
                raise RuntimeError(f"{name}: completion log not persisted")
            return operation
        time.sleep(0.05)
    raise UnknownOutcome(f"{name}: outcome unknown; no automatic retry")


def select_candidate(view, vid, pid, unit_serial):
    """Match the explicit reviewed USB tuple; ambiguity never picks a winner."""
    candidates = view["device_selection"]["devices"]["SERIAL"]["candidates"]
    matches = [
        row
        for row in candidates
        if (row.get("vid"), row.get("pid"), row.get("unit_serial"))
        == (vid, pid, unit_serial)
    ]
    if len(matches) != 1:
        raise ValueError("Expected exactly one matching USB unit; no device selected")
    if matches[0].get("identity_blockers"):
        raise ValueError("Matching USB unit has identity blockers; inspect export")
    return matches[0]["choice_id"]


def run_preflight(service, *, vid, pid, unit_serial, reviewer, power_disconnected):
    # Do not convert an absent/false acknowledgement into a physical assertion.
    if power_disconnected is not True:
        raise ValueError("Confirm external actuator power is disconnected first")
    if service.mode != "physical":
        raise ValueError("Physical metadata service required; no rehearsal promotion")
    exported = False
    try:
        perform(service, "inventory_devices", {"power_disconnected": True})
        choice = select_candidate(service.view(), vid, pid, unit_serial)
        perform(
            service,
            "review_arm_candidate",
            {
                "choice_id": choice,
                "reviewer_id": reviewer,
                "metadata_only": True,
            },
        )
        perform(
            service,
            "inspect_native_arm_metadata",
            {
                "power_disconnected": True,
                "metadata_only": True,
            },
        )
        # Export before returning even when correlation retains a blocked result.
        exported = True
        operation = perform(service, "export_logs", {})
        directory = Path(operation["result"]["receipt"]["path"])
        if verify_export(directory)["valid"] is not True:
            raise RuntimeError("Diagnostic export verification failed")
        return {
            "status": service.view()["native_arm_metadata"]["report"]["status"],
            "native_arm_metadata": service.view()["native_arm_metadata"],
            "export_directory": str(directory),
            "connected": False,
            "physical_authority": False,
            "next_step": "Review metadata; qualify serial opening separately before feedback",
        }
    except UnknownOutcome:
        raise
    except Exception:
        # One best-effort export after a known failure. Never replay the action
        # or recursively retry a failed export; preserve the original exception.
        if not exported:
            try:
                perform(service, "export_logs", {})
            except Exception:
                pass
        raise


def usb_hex(value):
    if re.fullmatch(r"[0-9a-fA-F]{4}", value) is None:
        raise argparse.ArgumentTypeError("Use exactly four hexadecimal digits")
    return value.lower()


def main(argv=None):
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--vid", type=usb_hex, required=True)
    parser.add_argument("--pid", type=usb_hex, required=True)
    parser.add_argument("--usb-serial", required=True)
    parser.add_argument("--reviewer", required=True)
    parser.add_argument(
        "--external-power-disconnected", action="store_true", required=True
    )
    args = parser.parse_args(argv)
    workspace = Path(__file__).resolve().parents[2]
    service = ArrivalWizardService(workspace, mode="physical")
    try:
        result = run_preflight(
            service,
            vid=args.vid,
            pid=args.pid,
            unit_serial=args.usb_serial,
            reviewer=args.reviewer,
            power_disconnected=args.external_power_disconnected,
        )
        print(json.dumps(result, indent=2))
        if result["status"] != "METADATA_CORRELATED":
            raise SystemExit(2)
    finally:
        service.shutdown()


if __name__ == "__main__":
    main()
