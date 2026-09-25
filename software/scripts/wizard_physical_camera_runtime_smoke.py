"""Explicit fixed-file camera runtime review and lossless export; no devices.

Requires the independently supplied frozen production source before constructing
the public application. Only inspect/review, nine notes and export are allowed;
no M1 store creation, native execution, inventory, build, repair or action replay.
"""

from __future__ import annotations

import argparse
import base64
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_onboarding_durability import read_bounded_regular_file
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.native_camera_protocol import canonical


CLOSED_ACTIONS = frozenset(
    {
        "physical_camera_runtime_inspect",
        "physical_camera_runtime_review",
        "record_note",
        "export_logs",
    }
)
INSPECTION_ATTACHMENT = "attachment-camera-runtime-inspection.json"
ZERO_COUNTERS = (
    "device_open_count",
    "serial_write_count",
    "power_event_count",
    "motion_command_count",
    "contact_command_count",
)
FALSE_FLAGS = (
    "dispatch_enabled",
    "driver_qualified",
    "hardware_qualified",
    "connected",
    "physical_authority",
)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def emit(label, value):
    print(label, json.dumps(value, sort_keys=True, ensure_ascii=True), flush=True)


class TerminalActionFailure(RuntimeError):
    """Original terminal operation, plus its one separate export outcome."""

    def __init__(self, operation):
        super().__init__("Original file-only action failed; no action replay")
        self.operation = deepcopy(operation)
        self.failure_export_attempted = False
        self.failure_export_operation = None
        self.failure_export_error = None


class ActionOutcomeUnknown(TimeoutError):
    further_actions_prohibited = True

    def __init__(self, operation_id, last_observed_operation):
        super().__init__("Original outcome unknown; no additional action or replay")
        self.operation_id = operation_id
        self.last_observed_operation = deepcopy(last_observed_operation)


def _action_once(service, name, values=None):
    """One dispatch only; terminal failures retain the complete original result."""
    require(name in CLOSED_ACTIONS, "Only the closed file-only action set is allowed")
    ticket = service.prepare_action(
        name, {} if values is None else values, service.view()["revision"]
    )
    emit("explicit action", {"action": name, "effects": ticket["effects"]})
    receipt = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + 90
    operation = None
    while time.monotonic() < deadline:
        operation = service.operation(receipt["operation_id"])
        if operation["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            emit(
                "completed",
                {
                    "action": name,
                    "operation_id": operation["operation_id"],
                    "status": operation["status"],
                    "result_sha256": operation["result_sha256"],
                },
            )
            if operation["status"] != "SUCCEEDED":
                raise TerminalActionFailure(operation)
            require(
                operation["completion_log_persisted"] is True,
                "Action completion log was not retained",
            )
            result = operation["result"]
            require(result.get("physical_authority") is False, "Physical authority")
            if name.startswith("physical_camera_runtime_"):
                require(
                    all(
                        type(result.get(k)) is int and result[k] == 0
                        for k in ZERO_COUNTERS
                    ),
                    "Unexpected or invalid device/effect count",
                )
                require(
                    result.get("metadata_inventory_performed") is False,
                    "Unexpected metadata inventory",
                )
            return operation
        time.sleep(0.02)
    raise ActionOutcomeUnknown(receipt["operation_id"], operation)


def action(service, name, values=None):
    """Export once on known terminal failure, before the caller shuts down.

    Never replay the failed action or recurse when export fails. Unknown running
    outcomes start no further action. Secondary export errors cannot replace the
    original terminal result.
    """
    try:
        return _action_once(service, name, values)
    except TerminalActionFailure as original:
        if name != "export_logs":
            original.failure_export_attempted = True
            try:
                original.failure_export_operation = _action_once(
                    service, "export_logs", {}
                )
                receipt = original.failure_export_operation["result"].get("receipt")
                emit(
                    "failure diagnostic export retained",
                    {
                        "original_operation_id": original.operation["operation_id"],
                        "export_operation_id": original.failure_export_operation[
                            "operation_id"
                        ],
                        "status": original.failure_export_operation["status"],
                        "receipt": (
                            {
                                key: receipt.get(key)
                                for key in (
                                    "path",
                                    "status",
                                    "valid",
                                    "manifest_sha256",
                                )
                            }
                            if type(receipt) is dict
                            else None
                        ),
                        "additional_export_attempt_allowed": False,
                    },
                )
            except Exception as error:
                original.failure_export_error = error
                if isinstance(error, TerminalActionFailure):
                    original.failure_export_operation = deepcopy(error.operation)
                emit(
                    "failure diagnostic export did not complete",
                    {
                        "original_operation_id": original.operation["operation_id"],
                        "error_type": type(error).__name__,
                        "export_outcome": (
                            "UNKNOWN"
                            if isinstance(error, TimeoutError)
                            else "FAILED_OR_REJECTED"
                        ),
                        "additional_export_attempt_allowed": False,
                    },
                )
        raise


def assert_no_hardware(view, *, initial_setup):
    require(
        view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED",
        "Unexpected connection",
    )
    require(view["physical_camera"]["last_frame"] is None, "Unexpected frame")
    require(
        all(row["state"] == "PHYSICAL_PENDING" for row in view["stages"]),
        "Physical stage promotion",
    )
    require(
        view["physical_camera_setup"] == initial_setup,
        "File inspection changed original-store setup or initialized M1",
    )
    runtime = view["physical_camera"]["runtime_inspection"]
    require(all(runtime.get(k) is False for k in FALSE_FLAGS), "Runtime authority")
    for name in (
        "physical_camera_probe",
        "physical_camera_capture",
        "arm_connect",
        "execute_task",
    ):
        require(
            not next(row for row in view["actions"] if row["action_id"] == name)[
                "enabled"
            ],
            "A physical execution action became enabled",
        )


def verify_runtime_export(
    receipt,
    *,
    workspace,
    expected_source_sha256,
    launch_session_id,
    probe_candidate,
    capture_candidate,
    expected_report_sha256,
    expected_review,
    expected_document=None,
    publication="CURRENT_FILE_REPORT",
):
    from rocell.application.physical_camera_runtime_inspection import (
        verify_physical_camera_runtime_inspection,
    )

    folder = Path(receipt["path"])
    require(
        folder.parent == workspace / "software/runs/wizard-exports",
        "Assigned export folder changed",
    )
    verified = verify_export(folder)
    require(verified["valid"] is True, "Export verification failed")
    require(
        verified["manifest_sha256"] == receipt["manifest_sha256"],
        "Export manifest differs from receipt",
    )
    manifest = json.loads(
        read_bounded_regular_file(folder / "manifest.json", maximum_bytes=1024 * 1024)
    )
    rows = [row for row in manifest["files"] if row["name"] == INSPECTION_ATTACHMENT]
    require(len(rows) == 1, "Missing or ambiguous dedicated inspection attachment")
    row = rows[0]
    payload = read_bounded_regular_file(
        folder / INSPECTION_ATTACHMENT, maximum_bytes=512 * 1024
    )
    require(
        len(payload) == row["bytes"]
        and hashlib.sha256(payload).hexdigest() == row["sha256"],
        "Dedicated inspection bytes differ from manifest",
    )
    wrapper = json.loads(payload)
    require(
        wrapper["schema"] == "rocell.physical_camera_runtime_inspection_export.v1"
        and wrapper["publication"] == publication
        and wrapper["original_bytes_preserved"] is True
        and wrapper["physical_authority"] is False,
        "Not a lossless inspection export with the expected publication status",
    )
    require(
        wrapper["inspection_sha256"] == expected_report_sha256,
        "Original report hash changed",
    )
    require(wrapper["review"] == expected_review, "Original logged review changed")
    if expected_document is not None:
        require(
            wrapper["inspection"] == expected_document,
            "Original full inspection changed",
        )
    report = verify_physical_camera_runtime_inspection(
        canonical(wrapper["inspection"]),
        expected_source_sha256=expected_source_sha256,
        expected_launch_session_id=launch_session_id,
        expected_probe_candidate=probe_candidate,
        expected_capture_candidate=capture_candidate,
        expected_report_sha256=expected_report_sha256,
    )
    require(
        report.to_dict() == wrapper["inspection"], "Verifier changed original report"
    )
    return report, {
        "path": str(folder),
        "manifest_sha256": verified["manifest_sha256"],
        "attachment": INSPECTION_ATTACHMENT,
        "attachment_sha256": row["sha256"],
        "attachment_bytes": row["bytes"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--expected-source-sha256", required=True)
    args = parser.parse_args()
    require(
        re.fullmatch(r"[0-9a-f]{64}", args.expected_source_sha256) is not None
        and args.expected_source_sha256 != "0" * 64,
        "Exact independently supplied frozen source digest required",
    )
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
        initial_setup = service.view()["physical_camera_setup"]
        assert_no_hardware(service.view(), initial_setup=initial_setup)
        inspected = action(
            service,
            "physical_camera_runtime_inspect",
            {
                "operator_id": "runtime-inspection-smoke",
                "file_inspection_only": True,
            },
        )
        state = service.view()["physical_camera"]["runtime_inspection"]
        require(
            state["status"] == "INSPECTION_RETAINED", "Inspection was not published"
        )
        inspected_summary = state["inspection"]
        report_sha256 = inspected_summary["report_sha256"]
        original_document = inspected["result"]["steps"][0]["report"]["inspection"]
        require(
            hashlib.sha256(canonical(original_document)).hexdigest() == report_sha256,
            "Published full inspection differs from its cached hash",
        )
        reviewed = action(
            service,
            "physical_camera_runtime_review",
            {
                "reviewer_id": "runtime-file-review-smoke",
                "file_review_only": True,
            },
        )
        state = service.view()["physical_camera"]["runtime_inspection"]
        require(state["status"] == "REVIEW_RECORDED", "File review was not recorded")
        original_review = state["review"]
        require(
            original_review["inspection_sha256"] == report_sha256,
            "Review changed its subject",
        )
        for index in range(9):
            action(
                service,
                "record_note",
                {
                    "note": f"Runtime file report retention check {index + 1}/9; no device, native helper, M1 store, build or physical acceptance."
                },
            )
        for operation in (inspected, reviewed):
            require(
                service.operation(operation["operation_id"])["result"] is None,
                "Generic results were not evicted",
            )
        require(
            service.view()["physical_camera"]["runtime_inspection"] == state,
            "Notes changed cached inspection/review",
        )
        assert_no_hardware(service.view(), initial_setup=initial_setup)
        exported = action(service, "export_logs")
        report, checked = verify_runtime_export(
            exported["result"]["receipt"],
            workspace=workspace,
            expected_source_sha256=service.source_sha256,
            launch_session_id=service.session_id,
            probe_candidate=service._physical_camera.probe_runtime,
            capture_candidate=service._physical_camera.capture_runtime,
            expected_report_sha256=report_sha256,
            expected_review=original_review,
            expected_document=original_document,
        )
        require(
            report.safe_summary() == inspected_summary,
            "Export changed cached inspection facts",
        )
        # The report's exact closed schema determines the baseline checks below;
        # they inspect retained file observations, never execute a helper.
        baseline = verify_installed_baseline(report)
        require(
            source_fingerprint(workspace) == service.source_sha256,
            "Source changed during smoke",
        )
        assert_no_hardware(service.view(), initial_setup=initial_setup)
        emit(
            "verified installed-file runtime inspection only",
            {
                "session_id": service.session_id,
                "source_sha256": service.source_sha256,
                "inspection_sha256": report.sha256,
                "actions": 12,
                "review": original_review,
                "baseline": baseline,
                "export": checked,
                **{key: False for key in FALSE_FLAGS},
            },
        )
        return 0
    finally:
        service.shutdown()


def verify_installed_baseline(report):
    """Require the fixed historical probe gap; derive capture facts from bytes."""
    document = report.to_dict()
    require(document["terminal_error"] is None, "Installed inspection did not finish")
    require(all(document[key] is False for key in FALSE_FLAGS), "Inspection authority")
    require(
        all(
            type(value) is int and value == 0 for value in document["effects"].values()
        ),
        "Inspection performed a process/device effect",
    )
    files = {row["relative_path"]: row for row in document["files"]}
    purposes = document["purposes"]
    for purpose in ("probe", "capture"):
        require(
            purposes[purpose]["binary_status"] == "MATCHED"
            and purposes[purpose]["build_status"] == "MATCHED",
            "Installed executable/build record does not match the fixed candidate",
        )
    probe_manifest = json.loads(
        base64.b64decode(document["manifests"]["probe"], validate=True)
    )
    worker_path = "software/native/windows_camera/camera_worker.cpp"
    observed_worker = files[worker_path]
    require(
        observed_worker["observation"] == "OBSERVED"
        and observed_worker["observed_sha256"]
        != probe_manifest["source_files"]["camera_worker.cpp"],
        "Expected historical probe source-closure gap is absent or unobserved",
    )
    require(
        purposes["probe"]["source_status"] == "GAPS"
        and any(
            gap["relative_path"] == worker_path for gap in purposes["probe"]["gaps"]
        ),
        "Historical probe source mismatch was hidden",
    )
    capture_manifest = json.loads(
        base64.b64decode(document["manifests"]["capture"], validate=True)
    )
    actual_matches = sum(
        files["software/native/windows_camera/" + path]["observation"] == "OBSERVED"
        and files["software/native/windows_camera/" + path]["observed_sha256"]
        == expected
        for path, expected in capture_manifest["source_files"].items()
    )
    counts = purposes["capture"]["source_counts"]
    require(
        counts["total"] == len(capture_manifest["source_files"])
        and counts["matched"] == actual_matches
        and counts["gaps"] == counts["total"] - actual_matches
        and counts["unverified"] == 0,
        "Capture source facts do not follow retained observations",
    )
    require(
        purposes["capture"]["source_status"]
        == ("MATCHED" if actual_matches == counts["total"] else "GAPS"),
        "Capture closure was assumed instead of derived",
    )
    return {
        "probe": purposes["probe"],
        "capture": purposes["capture"],
        "observed_camera_worker_sha256": observed_worker["observed_sha256"],
        "probe_record_camera_worker_sha256": probe_manifest["source_files"][
            "camera_worker.cpp"
        ],
        "capture_record_camera_worker_sha256": capture_manifest["source_files"][
            "camera_worker.cpp"
        ],
        "coverage": document["coverage"],
        "meaning": "Installed-file agreement and historical source gap only; no executed helper or qualified camera.",
    }


if __name__ == "__main__":
    raise SystemExit(main())
