"""Two actual public wizard launches sharing one original camera-only store.

No fixtures or devices: explicit initialize, optional requirements, shutdown,
discover, selected original reopen, original refresh, held planning and export.
The pending variant demonstrates continuing a never-collected original store.
Only semantic stage/evidence files are compared; M1 storage qualification and
lease metadata may legitimately change during explicit reopening.
"""

import argparse
import hashlib
import json
from pathlib import Path
import time
import threading

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_camera_session import PhysicalCameraSession
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.native_camera_protocol import canonical


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def emit(label, value):
    print(label, json.dumps(value, sort_keys=True, ensure_ascii=True), flush=True)


def action(
    service,
    name,
    *,
    expected_status="SUCCEEDED",
    on_wait=None,
    expected_directory=None,
    **values
):
    require(
        name
        in {
            "physical_camera_initialize",
            "physical_camera_prerequisites",
            "physical_camera_discover",
            "physical_camera_reopen",
            "physical_camera_refresh",
            "physical_camera_plan",
            "export_logs",
            "stop_operation",
        },
        "Closed file-only diagnostic set",
    )
    ticket = service.prepare_action(name, values, service.view()["revision"])
    if expected_directory is not None:
        require(
            str(expected_directory) in " ".join(ticket["effects"]),
            "Preview does not identify the actual original target",
        )
    emit("explicit action", {"action": name, "effects": ticket["effects"]})
    receipt = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + 250
    while time.monotonic() < deadline:
        if on_wait is not None:
            on_wait()
        result = service.operation(receipt["operation_id"])
        if result["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            emit(
                "completed",
                {
                    "action": name,
                    "operation_id": result["operation_id"],
                    "status": result["status"],
                    "result_sha256": result["result_sha256"],
                },
            )
            if result["status"] != expected_status:
                emit("failure retained; no replay", result)
            require(
                result["status"] == expected_status,
                "Inspect original failed result; no automatic replay",
            )
            return result
        time.sleep(0.05)
    raise TimeoutError(
        "Original outcome unknown; shutdown requests cancellation, not replay"
    )


def semantic_snapshot(bound):
    root = Path(bound["directory"])
    paths = [root / "durability-anchor.json"]
    for folder in (root / ("onboarding-" + bound["session_id"]), root / "cells"):
        paths.extend(sorted(p for p in folder.rglob("*") if p.is_file()))
    return {
        str(p.relative_to(root)): hashlib.sha256(p.read_bytes()).hexdigest()
        for p in paths
    }


def report(result):
    return result["result"]["steps"][0]["report"]


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--expected-source-sha256", required=True)
    parser.add_argument("--pending-original", action="store_true")
    parser.add_argument(
        "--stop-after-original-read",
        action="store_true",
        help="Instrument one scheduler barrier AFTER actual original M1 readback, then issue public Stop and explicitly verify the same original. No storage/provider result is replaced.",
    )
    args = parser.parse_args()
    require(
        not (args.pending_original and args.stop_after_original_read),
        "Choose one finite scenario",
    )
    workspace = Path(__file__).resolve().parents[2]
    require(
        source_fingerprint(workspace) == args.expected_source_sha256, "Freeze mismatch"
    )
    first = ArrivalWizardService(workspace, mode="physical")
    second = None
    original_reader = PhysicalCameraSession.read_original_prerequisites
    reader_ready, reader_release = threading.Event(), threading.Event()
    stop_sent = False
    try:
        require(
            first.source_sha256 == args.expected_source_sha256, "Launch source changed"
        )
        action(first, "physical_camera_initialize")
        original_document = None
        if not args.pending_original:
            original_document = report(action(first, "physical_camera_prerequisites"))[
                "prerequisite_document"
            ]
        bound = first.view()["physical_camera_setup"]["session"]["binding"]
        original_stages = first.view()["physical_camera_setup"]["session"]["stages"]
        first_export = action(first, "export_logs")["result"]["receipt"]
        first.shutdown()
        immutable = semantic_snapshot(bound)
        second = ArrivalWizardService(workspace, mode="physical")
        default_directory = Path(
            second.view()["physical_camera_setup"]["session"]["binding"]["directory"]
        )
        require(not default_directory.exists(), "Second launch created a replacement")
        discovered = action(second, "physical_camera_discover")
        rows = second.view()["physical_camera_setup"]["reopening"]["stores"]
        originals = [row for row in rows if row["session_id"] == bound["session_id"]]
        require(
            len(originals) == 1 and originals[0]["selectable"] is True,
            "Original not uniquely selectable",
        )
        if args.stop_after_original_read:
            # Scheduling injection only: always perform the actual M1 read and
            # verification first. The real public Stop cancels the outer scope.
            def pause_after_real_read(owner, **kwargs):
                observed = original_reader(owner, **kwargs)
                if not reader_ready.is_set():
                    reader_ready.set()
                    require(
                        reader_release.wait(30),
                        "Test scheduling barrier expired; no replay",
                    )
                return observed

            PhysicalCameraSession.read_original_prerequisites = pause_after_real_read

            def request_public_stop():
                nonlocal stop_sent
                if reader_ready.is_set() and not stop_sent:
                    stop_sent = True
                    action(second, "stop_operation")
                    reader_release.set()

            failed = action(
                second,
                "physical_camera_reopen",
                choice_id=originals[0]["choice_id"],
                expected_status="FAILED",
                on_wait=request_public_stop,
            )
            require(
                stop_sent and failed["result"]["code"] == "CANCELLED",
                "Expected public Stop after real readback",
            )
            history = failed["result"]["retained_camera_setup"]["prerequisites"]
            require(
                history["document"] == original_document,
                "Late Stop lost actual original bytes",
            )
            require(
                second.view()["physical_camera_setup"]["prerequisites"] is None,
                "Stopped result promoted current requirements",
            )
            require(
                semantic_snapshot(bound) == immutable,
                "Stop rewrote original semantic records",
            )
            # This separate user-visible action revalidates the same immutable
            # descriptor. It does not reuse/revive the revoked selection token.
            opened = action(
                second, "physical_camera_refresh", expected_directory=bound["directory"]
            )
        else:
            opened = action(
                second, "physical_camera_reopen", choice_id=originals[0]["choice_id"]
            )
        opened_view = second.view()["physical_camera_setup"]
        require(
            opened_view["origin_launch_id"] == first.session_id != second.session_id,
            "Origin was relabeled",
        )
        require(
            opened_view["launch_session_id"] == second.session_id,
            "Current launch missing",
        )
        require(
            opened_view["session"]["binding"] == bound,
            "Original store identity changed",
        )
        require(
            opened_view["session"]["stages"] == original_stages,
            "Reopen mutated stage state",
        )
        require(
            semantic_snapshot(bound) == immutable,
            "Reopen rewrote original semantic records",
        )
        require(not default_directory.exists(), "Reopen initialized a replacement")
        if args.pending_original:
            require(
                opened_view["prerequisites"] is None,
                "Pending original invented a checklist",
            )
            collected = action(second, "physical_camera_prerequisites")
            original_document = report(collected)["prerequisite_document"]
            require(
                original_document["binding"]["launch_session_id"] == first.session_id,
                "Original document lineage changed",
            )
            require(
                original_document["selection"] is None
                and original_document["source_preflight"] is None,
                "New metadata silently relabeled",
            )
            immutable = semantic_snapshot(bound)
        else:
            require(
                report(opened)["prerequisite_document"] == original_document,
                "Original document regenerated",
            )
        refreshed = action(second, "physical_camera_refresh")
        require(
            report(refreshed)["prerequisite_document"] == original_document,
            "Refresh lost original bytes",
        )
        require(
            semantic_snapshot(bound) == immutable,
            "Refresh rewrote original semantic records",
        )
        plan = report(action(second, "physical_camera_plan"))["intent"]
        require(
            plan["assigned_parent_directory"] == bound["directory"],
            "Acquisition targets replacement store",
        )
        require(
            plan["camera_cell_id"] == bound["cell_id"]
            and plan["camera_session_id"] == bound["session_id"],
            "Acquisition and UI sessions differ",
        )
        require(
            plan["camera_store_origin_launch_id"] == first.session_id
            and plan["launch_session_id"] == second.session_id,
            "Planning origin/current context conflated",
        )
        require(
            plan["admitted"] is False and plan["native_campaign_plan"] is None,
            "Unexpected hardware context",
        )
        view = second.view()
        require(
            view["physical_camera_setup"]["requirements_provenance"]
            == "REOPENED_ORIGINAL_CONTEXT",
            "Historical context missing",
        )
        require(
            view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED",
            "Unexpected connection",
        )
        require(
            all(x["state"] == "PHYSICAL_PENDING" for x in view["stages"]),
            "Physical progress promoted",
        )
        exported = action(second, "export_logs")["result"]["receipt"]
        folder = Path(exported["path"])
        require(
            folder.parent == workspace / "software/runs/wizard-exports",
            "Assigned export folder changed",
        )
        require(
            verify_export(folder)["valid"] is True
            and verify_export(Path(first_export["path"]))["valid"] is True,
            "Export verification failed",
        )
        attachments = [
            json.loads(p.read_bytes()) for p in folder.glob("attachment-result-*.json")
        ]
        saved = next(
            x for x in attachments if x["action_id"] == "physical_camera_refresh"
        )
        require(
            saved["steps"][0]["report"]["prerequisite_document"] == original_document,
            "Export lost exact original requirements",
        )
        require(
            source_fingerprint(workspace) == args.expected_source_sha256,
            "Source changed during check",
        )
        emit(
            "verified original camera restart",
            {
                "source_sha256": args.expected_source_sha256,
                "pending_original": args.pending_original,
                "stop_after_actual_original_read": args.stop_after_original_read,
                "current_launch": second.session_id,
                "original_binding": bound,
                "semantic_file_count": len(immutable),
                "requirements_sha256": hashlib.sha256(
                    canonical(original_document)
                ).hexdigest(),
                "replacement_created": False,
                "hardware_qualified": False,
                "first_export": first_export,
                "second_export": exported,
            },
        )
        return 0
    finally:
        reader_release.set()
        PhysicalCameraSession.read_original_prerequisites = original_reader
        first.shutdown()
        if second is not None:
            second.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
