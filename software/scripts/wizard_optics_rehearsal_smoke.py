"""Run eight rehearsal stages through the public wizard API.

Creates new isolated records under software/runs, including two full-size
synthetic camera frames and verified diagnostic exports. No device inventory,
camera/serial endpoint, energy or robot command is used. Existing sessions are
never modified. The one session created here is reopened without probe replay.
Run only with workspace source stable for the entire test.

With --serve, pause after reopening the retained stage-eight assessment so the
browser can inspect its checks and perform a fresh, distinct review explicitly.
Without it, the API performs that review and confirms the stage-nine checkpoint.
Use wizard_arm_setup_rehearsal_smoke.py for the eleven-stage continuation.
"""

from __future__ import annotations

import argparse
from pathlib import Path

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.ui.server import create_wizard_server, run_wizard_server
from wizard_reopen_rehearsal_smoke import action


def export(service: ArrivalWizardService) -> None:
    action(service, "export_logs")
    path = Path(service.view()["exports"]["items"][-1]["path"])
    verification = verify_export(path)
    assert verification["status"] == "VERIFIED_DIAGNOSTIC_EXPORT", verification
    print("verified diagnostic export", path, verification, flush=True)


def main() -> None:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--serve", action="store_true")
    args = parser.parse_args()
    workspace = Path(__file__).resolve().parents[2]
    original = ArrivalWizardService(workspace)
    try:
        print("source", original.source_sha256, flush=True)
        action(original, "rehearsal_initialize")
        for index in range(8):
            action(original, "rehearsal_collect", operator_id="optics-smoke-operator")
            if index == 4:
                action(original, "rehearsal_camera_settings", brightness_offset=0)
            if index in (4, 5):
                action(
                    original, "rehearsal_camera_campaign", frame_count=1, fault="none"
                )
            action(original, "rehearsal_assess")
            current = original.view()["commissioning_rehearsal"]
            assert current["assessment"]["outcome"] == "PASS", current["assessment"]
            if index < 7:
                action(
                    original,
                    "rehearsal_review",
                    reviewer_id="optics-smoke-reviewer",
                    accept_assessment=True,
                )
        before = original.view()["commissioning_rehearsal"]
        assert before["stage"] == "static_registration"
        assert before["stage_state"] == "REVIEW_PENDING"
        assert before["optics_evaluation"]["outcome"] == "REHEARSAL_CHECKS_PASSED"
        assert all(row["passed"] for row in before["optics_evaluation"]["checks"])
        print("original session", before["session_id"], flush=True)
        print("original directory", before["directory"], flush=True)
        # Preserve full collected technical reports in this launch's export;
        # the second launch has its own log, not a copy of historical operations.
        export(original)
    finally:
        original.shutdown()

    reopened = ArrivalWizardService(workspace)
    try:
        assert reopened.source_sha256 == original.source_sha256, "Source changed"
        unused = Path(reopened.view()["commissioning_rehearsal"]["directory"])
        action(reopened, "rehearsal_discover")
        choices = reopened.view()["commissioning_rehearsal"]["discovery"]["choices"]
        choice = next(c for c in choices if c["session_id"] == before["session_id"])
        assert choice["source_matches"] is True
        action(reopened, "rehearsal_reopen", choice_id=choice["choice_id"])
        after = reopened.view()["commissioning_rehearsal"]
        for key in (
            "session_id",
            "cell_id",
            "directory",
            "journal_head_sha256",
            "assessment",
            "optics_evaluation",
        ):
            assert before[key] == after[key], key
        assert after["stage_state"] == "REVIEW_PENDING"
        assert not unused.exists()
        assert reopened.view()["camera"]["image_id"] is None
        assert all(s["state"] == "PHYSICAL_PENDING" for s in reopened.view()["stages"])
        if args.serve:
            print("Reopened assessment awaits explicit browser review", flush=True)
            server = create_wizard_server(reopened)
            print("Browser QA:", server.launch_url, flush=True)
            run_wizard_server(server)
            return
        action(
            reopened,
            "rehearsal_review",
            reviewer_id="optics-reopen-reviewer",
            accept_assessment=True,
        )
        final = reopened.view()["commissioning_rehearsal"]
        assert final["stage"] == "arm_identity"
        assert [row["state"] for row in final["stages"][:8]] == ["PASS"] * 8
        export(reopened)
        print(
            "Eight rehearsal stages reviewed; arm-identity checkpoint reached, physical stages held",
            flush=True,
        )
    finally:
        reopened.shutdown()


if __name__ == "__main__":
    main()
