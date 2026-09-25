"""Finite public file-only camera setup; real M1 storage, no hardware fixtures.

Creates a unique assigned camera diagnostic store, retains actual fixed build
requirements, verifies original records, and exports full results. No inventory,
native helper, camera, serial, power, motion or contact operation is selected.
Stops on the first failure without replay or deleting original evidence.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_camera_prerequisites import (
    verify_physical_camera_prerequisites,
)
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.native_camera_protocol import canonical


def require(value, message):
    if not value:
        raise RuntimeError(message)


def emit(label, value):
    print(label, json.dumps(value, sort_keys=True, ensure_ascii=True), flush=True)


def action(service, name):
    require(
        name
        in {
            "physical_camera_initialize",
            "physical_camera_prerequisites",
            "physical_camera_refresh",
            "export_logs",
        },
        "Closed file-only action set",
    )
    ticket = service.prepare_action(name, {}, service.view()["revision"])
    emit("explicit action", {"action": name, "effects": ticket["effects"]})
    receipt = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + 250
    while time.monotonic() < deadline:
        result = service.operation(receipt["operation_id"])
        if result["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            emit(
                "completed",
                {
                    "operation_id": result["operation_id"],
                    "action": name,
                    "status": result["status"],
                    "result_sha256": result["result_sha256"],
                },
            )
            if result["status"] != "SUCCEEDED":
                emit("retained failure", result)
            require(
                result["status"] == "SUCCEEDED",
                "Failed original operation retained; do not replay",
            )
            return result
        time.sleep(0.05)
    raise TimeoutError("Original outcome unknown; cancellation/shutdown, not replay")


def assert_no_hardware(view):
    require(
        view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED",
        "Unexpected connection",
    )
    require(view["physical_camera"]["last_frame"] is None, "Unexpected physical image")
    require(
        all(x["state"] == "PHYSICAL_PENDING" for x in view["stages"]),
        "Physical progress incorrectly promoted",
    )
    for name in (
        "physical_camera_probe",
        "physical_camera_capture",
        "arm_connect",
        "execute_task",
    ):
        require(
            not next(x for x in view["actions"] if x["action_id"] == name)["enabled"],
            "Device action enabled",
        )


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--expected-source-sha256", required=True)
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[2]
    require(
        source_fingerprint(workspace) == args.expected_source_sha256,
        "Freeze mismatch before launch",
    )
    service = ArrivalWizardService(workspace, mode="physical")
    try:
        require(
            service.source_sha256 == args.expected_source_sha256,
            "Launch source changed",
        )
        emit(
            "launch",
            {"session_id": service.session_id, "source_sha256": service.source_sha256},
        )
        assert_no_hardware(service.view())
        action(service, "physical_camera_initialize")
        initialized = service.view()["physical_camera_setup"]
        require(
            all(x["state"] == "PENDING" for x in initialized["session"]["stages"]),
            "New session must start entirely pending",
        )
        outcome = action(service, "physical_camera_prerequisites")
        collected = service.view()["physical_camera_setup"]
        require(
            collected["publication"]["status"] == "CURRENT",
            "Requirements publication held",
        )
        require(collected["prerequisites"] is not None, "Missing actual requirements")
        recorded = collected["session"]["stages"]
        require(
            recorded[0]["state"] == "WAITING_OPERATOR"
            and all(x["state"] == "PENDING" for x in recorded[1:]),
            "Requirements must not pass a stage",
        )
        retained = outcome["result"]["steps"][0]["report"]["prerequisites"]
        document = outcome["result"]["steps"][0]["report"]["prerequisite_document"]
        require(
            retained["retention"] == "M1_FULL_BYTES_READ_BACK",
            "Original M1 retention missing",
        )
        bound = collected["session"]["binding"]
        verify_physical_camera_prerequisites(
            canonical(document),
            expected_source_sha256=service.source_sha256,
            expected_session_id=bound["session_id"],
            expected_launch_session_id=service.session_id,
            expected_evidence_sha256=retained["evidence_sha256"],
        )
        action(service, "physical_camera_refresh")
        refreshed = service.view()["physical_camera_setup"]
        require(
            refreshed["prerequisites"] == collected["prerequisites"],
            "Refresh lost original verified requirements",
        )
        require(
            refreshed["session"]["stages"] == recorded,
            "Refresh mutated physical stage state",
        )
        assert_no_hardware(service.view())
        exported = action(service, "export_logs")
        receipt = exported["result"]["receipt"]
        folder = Path(receipt["path"])
        require(
            folder.parent == workspace / "software/runs/wizard-exports",
            "Assigned export changed",
        )
        require(verify_export(folder)["valid"] is True, "Export verification failed")
        results = [
            json.loads(p.read_bytes()) for p in folder.glob("attachment-result-*.json")
        ]
        require(len(results) == 3, "Three original setup results must be exported")
        original = next(
            x for x in results if x["action_id"] == "physical_camera_prerequisites"
        )
        require(original == outcome["result"], "Export changed retained requirements")
        require(
            source_fingerprint(workspace) == service.source_sha256,
            "Source changed during check",
        )
        emit(
            "verified file-only camera setup",
            {
                "source_sha256": service.source_sha256,
                "session": bound,
                "actions": 4,
                "requirements_sha256": retained["evidence_sha256"],
                "physical_pending_stages": 15,
                "camera_store_waiting_operator_stages": 1,
                "camera_store_pending_stages": 14,
                "hardware_qualified": False,
                "physical_authority": False,
                "export": receipt,
            },
        )
        return 0
    finally:
        service.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
