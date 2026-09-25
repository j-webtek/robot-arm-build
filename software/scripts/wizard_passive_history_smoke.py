"""Actual wizard history inspection/export; never starts a device rehearsal."""

import argparse
import json
from pathlib import Path
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_diagnostic_export import verify_export


def perform(service, name, values):
    if name not in {"inspect_passive_arm_history", "export_logs"}:
        raise ValueError("History inspection/export only")
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
                raise RuntimeError("Inspection/export failed; no retry or replay")
            return operation
        time.sleep(0.05)
    raise TimeoutError("Unknown action outcome; no automatic retry")


def main():
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_id")
    args = parser.parse_args()
    service = ArrivalWizardService(
        Path(__file__).resolve().parents[2], mode="rehearsal"
    )
    try:
        perform(service, "inspect_passive_arm_history", {"session_id": args.session_id})
        history = service.view()["passive_arm_history"]
        if history["connected"] is not False or history["replay_allowed"] is not False:
            raise RuntimeError("Unexpected historical authority")
        exported = perform(service, "export_logs", {})
        path = Path(exported["result"]["receipt"]["path"])
        if not verify_export(path)["valid"]:
            raise RuntimeError("Export verification failed")
        print(
            json.dumps(
                dict(
                    status="HISTORY_INSPECTION_AND_EXPORT_VERIFIED",
                    session_id=args.session_id,
                    historical_source_matches_current=history["source_matches_current"],
                    export_directory=str(path),
                    connected=False,
                    replay_allowed=False,
                ),
                indent=2,
            )
        )
    finally:
        service.shutdown()


if __name__ == "__main__":
    main()
