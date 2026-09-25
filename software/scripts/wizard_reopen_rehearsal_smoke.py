"""Exercise original-session reopening through the normal wizard API.

All writes are new, separate rehearsal/diagnostic records under software/runs.
No devices, OS device inventory, prior approvals or commands are replayed.
With --serve, leave the second launch at explicit selection for browser QA.
Without it, reopen, freshly review and independently verify a diagnostic export.
"""

from __future__ import annotations

import argparse
from pathlib import Path
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.ui.server import create_wizard_server, run_wizard_server


def action(service: ArrivalWizardService, name: str, **values: object) -> dict:
    ticket = service.prepare_action(name, values, service.view()["revision"])
    receipt = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + 180
    while time.monotonic() < deadline:
        operation = service.operation(receipt["operation_id"])
        if operation["status"] not in {"PENDING", "RUNNING", "QUEUED"}:
            print(name, operation["status"], flush=True)
            if operation["status"] != "SUCCEEDED":
                raise RuntimeError(str(operation))
            return operation
        time.sleep(0.1)
    raise RuntimeError("Smoke deadline exceeded; inspect retained state, do not replay")


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[2]
    original = ArrivalWizardService(workspace)
    try:
        print("source", original.source_sha256, flush=True)
        action(original, "rehearsal_initialize")
        action(original, "rehearsal_collect", operator_id="reopen-smoke-operator")
        action(original, "rehearsal_assess")
        before = original.view()["commissioning_rehearsal"]
        print("original session", before["session_id"], flush=True)
        print("original directory", before["directory"], flush=True)
    finally:
        original.shutdown()

    reopened = ArrivalWizardService(workspace)
    try:
        unused_directory = Path(reopened.view()["commissioning_rehearsal"]["directory"])
        action(reopened, "rehearsal_discover")
        choices = reopened.view()["commissioning_rehearsal"]["discovery"]["choices"]
        choice = next(c for c in choices if c["session_id"] == before["session_id"])
        assert choice["source_matches"] is True
        assert not unused_directory.exists()
        if args.serve:
            print(
                "Select original session explicitly:", before["session_id"], flush=True
            )
            server = create_wizard_server(reopened)
            print("Browser QA:", server.launch_url, flush=True)
            run_wizard_server(server)
            return
        action(reopened, "rehearsal_reopen", choice_id=choice["choice_id"])
        after = reopened.view()["commissioning_rehearsal"]
        for key in (
            "session_id",
            "cell_id",
            "directory",
            "journal_head_sha256",
            "assessment",
        ):
            assert after[key] == before[key], key
        assert after["stage_state"] == "REVIEW_PENDING"
        assert reopened.view()["camera"]["image_id"] is None
        assert not unused_directory.exists()
        action(
            reopened,
            "rehearsal_review",
            reviewer_id="reopen-smoke-reviewer",
            accept_assessment=True,
        )
        assert (
            reopened.view()["commissioning_rehearsal"]["stage"]
            == "static_camera_contract"
        )
        assert all(s["state"] == "PHYSICAL_PENDING" for s in reopened.view()["stages"])
        action(reopened, "export_logs")
        exports = reopened.view()["exports"]["items"]
        print("exports", exports, flush=True)
        # Use the path returned by the export operation; never infer a latest file.
        export_path = Path(exports[-1]["path"])
        print("independent verification", verify_export(export_path), flush=True)
    finally:
        reopened.shutdown()


if __name__ == "__main__":
    main()
