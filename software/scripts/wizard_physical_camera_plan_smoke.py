"""Finite public wizard planning/export check, with no hardware-capable action.

Uses the real Arrival service and current source fingerprint. It does not inject
devices or qualified stages, enumerate Windows metadata, open a native helper,
create an M1 camera session or replay an operation. Outputs go only to the
wizard's assigned workspace diagnostic/export folders.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.native_camera_protocol import canonical, digest


def emit(label: str, value: object) -> None:
    print(label, json.dumps(value, sort_keys=True, ensure_ascii=True), flush=True)


def require(value: bool, explanation: str) -> None:
    if not value:
        raise RuntimeError(explanation)


def action(service: ArrivalWizardService, name: str, **values: object) -> dict:
    require(
        name in {"physical_camera_plan", "export_logs"}, "Closed plan-only action set"
    )
    ticket = service.prepare_action(name, values, service.view()["revision"])
    emit("explicit action preview", {"action": name, "effects": ticket["effects"]})
    receipt = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + 30
    while time.monotonic() < deadline:
        result = service.operation(receipt["operation_id"])
        if result["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            emit(
                "operation completed",
                {
                    "operation_id": result["operation_id"],
                    "action": name,
                    "status": result["status"],
                    "result_sha256": result["result_sha256"],
                },
            )
            require(
                result["status"] == "SUCCEEDED",
                "Inspect retained failed operation; no automatic retry",
            )
            return result
        time.sleep(0.05)
    # Shutdown requests cancellation in the finally block. There is no replay
    # and no inference that an interrupted planning/logging operation did not run.
    raise TimeoutError("Planning wait expired; original outcome unknown, not replaying")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--expected-source-sha256", required=True)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[2]
    current = source_fingerprint(workspace)
    require(
        current == args.expected_source_sha256,
        "Freeze/source mismatch before service startup",
    )
    service = ArrivalWizardService(workspace, mode="physical")
    try:
        require(service.source_sha256 == current, "Source changed during construction")
        emit("launch", {"session_id": service.session_id, "source_sha256": current})
        for operation in ("probe", "capture"):
            result = action(service, "physical_camera_plan", operation=operation)
            report = result["result"]["steps"][0]["report"]
            plan = report["intent"]
            require(
                digest(canonical(plan)) == report["intent_sha256"],
                "Original plan hash mismatch",
            )
            require(
                plan["admitted"] is False and plan["physical_authority"] is False,
                "Unexpected admission",
            )
            require(
                plan["native_campaign_plan"] is None,
                "Fresh launch unexpectedly has reviewed metadata",
            )
            emit(
                "held intent retained",
                {
                    "operation": operation,
                    "intent_sha256": report["intent_sha256"],
                    "blockers": plan["blockers"],
                },
            )
        view = service.view()
        require(
            view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED",
            "Unexpected connected state",
        )
        require(
            all(stage["state"] == "PHYSICAL_PENDING" for stage in view["stages"]),
            "Physical stage promoted",
        )
        require(
            view["physical_camera"]["last_frame"] is None, "Unexpected physical frame"
        )
        exported = action(service, "export_logs")
        receipt = exported["result"]["receipt"]
        folder = Path(receipt["path"])
        require(
            folder.parent == workspace / "software/runs/wizard-exports",
            "Assigned export folder changed",
        )
        require(verify_export(folder)["valid"] is True, "Export verification failed")
        attachments = list(folder.glob("attachment-result-*.json"))
        require(len(attachments) == 2, "Both original plan reports must be retained")
        for path in attachments:
            retained = json.loads(path.read_bytes())
            report = retained["steps"][0]["report"]
            require(
                digest(canonical(report["intent"])) == report["intent_sha256"],
                "Exported intent hash changed",
            )
        require(source_fingerprint(workspace) == current, "Source changed during check")
        emit(
            "verified plan-only smoke",
            {
                "source_sha256": current,
                "actions": 3,
                "physical_pending_stages": len(view["stages"]),
                "hardware_qualified": False,
                "physical_authority": False,
                "received_hardware_observed": False,
                "export": receipt,
            },
        )
        return 0
    finally:
        service.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
