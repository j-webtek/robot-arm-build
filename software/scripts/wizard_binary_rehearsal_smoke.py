"""Explicit end-to-end rehearsal using the same API as browser/terminal clients.

Creates a new isolated rehearsal and diagnostic export. No private state edits,
device inventory, camera open, serial endpoint, power or motion is involved.
Optional --serve keeps the resulting camera preview available for manual UI QA.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.ui.server import create_wizard_server, run_wizard_server


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[2]
    service = ArrivalWizardService(workspace)

    def action(name: str, **values: object) -> dict:
        ticket = service.prepare_action(
            name, values, expected_revision=service.view()["revision"]
        )
        result = service.execute_action(ticket["ticket_id"])
        deadline = time.monotonic() + 300
        while time.monotonic() < deadline:
            operation = service.operation(result["operation_id"])
            if operation["status"] not in {"PENDING", "RUNNING", "QUEUED"}:
                print(name, operation["status"], flush=True)
                if operation["status"] != "SUCCEEDED":
                    raise RuntimeError(str(operation))
                return operation
            time.sleep(0.1)
        raise RuntimeError(
            "Smoke deadline exceeded; inspect retained state, do not replay"
        )

    try:
        print("source", service.source_sha256, flush=True)
        action("rehearsal_initialize")
        for _ in range(4):
            action(
                "rehearsal_collect",
                operator_id="smoke-operator",
                candidate="synthetic-b0477",
            )
            action("rehearsal_assess")
            action(
                "rehearsal_review", reviewer_id="smoke-reviewer", accept_assessment=True
            )
        action(
            "rehearsal_collect",
            operator_id="smoke-operator",
            candidate="synthetic-b0477",
        )
        action("rehearsal_camera_settings", brightness_offset=-12)
        action("rehearsal_camera_campaign", frame_count=1, fault="none")
        action("rehearsal_assess")
        action("rehearsal_review", reviewer_id="smoke-reviewer", accept_assessment=True)
        action("arm_feedback_contract", scenario="nominal")
        action("arm_feedback_contract", scenario="boot-bytes")
        action("export_logs")
        print(
            "rehearsal",
            service.view()["commissioning_rehearsal"]["directory"],
            flush=True,
        )
        print("exports", service.view().get("exports"), flush=True)
        assert service.view()["camera"]["image_id"] is not None
        if args.serve:
            server = create_wizard_server(service)
            print("Browser QA:", server.launch_url, flush=True)
            run_wizard_server(server)
    finally:
        service.shutdown()


if __name__ == "__main__":
    main()
