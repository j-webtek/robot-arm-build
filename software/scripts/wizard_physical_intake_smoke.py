"""Public file-only M1/intake/export smoke; never simulate a physical observation.

Initialize one unique camera store, retain its actual requirement document,
record one explicit UNKNOWN/not-arrived draft, then verify its dedicated export
after nine later notes evict the generic notebook action results. Stop at the
first failure: no operation replay, replacement store or device action.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import time

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_camera_prerequisites import (
    verify_physical_camera_prerequisites,
)
from rocell.application.physical_onboarding_durability import read_bounded_regular_file
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.native_camera_protocol import canonical


CLOSED_ACTIONS = frozenset(
    {
        "physical_camera_initialize",
        "physical_camera_prerequisites",
        "physical_intake_start",
        "physical_intake_record",
        "record_note",
        "export_logs",
    }
)
NOTEBOOK_ATTACHMENT = "attachment-physical-intake-notebook.json"
UNKNOWN_NOTE = {
    "record_id": "INT-001",
    "observation_status": "UNKNOWN",
    "observed_value": "Hardware has not arrived; public no-device smoke.",
    "method": "Operator development note; no measurement performed",
    "evidence_note": "No attachment supplied; no bytes verified",
    "operator_id": "development-smoke",
}
ZERO_COUNTERS = (
    "device_open_count",
    "serial_write_count",
    "power_event_count",
    "motion_command_count",
    "contact_command_count",
)


def require(ok, message):
    if not ok:
        raise RuntimeError(message)


def emit(label, value):
    print(label, json.dumps(value, sort_keys=True, ensure_ascii=True), flush=True)


def action(service, name, values=None):
    require(
        name in CLOSED_ACTIONS, "Only the closed no-device intake action set is allowed"
    )
    ticket = service.prepare_action(
        name, {} if values is None else values, service.view()["revision"]
    )
    emit("explicit action", {"action": name, "effects": ticket["effects"]})
    receipt = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + 250
    while time.monotonic() < deadline:
        outcome = service.operation(receipt["operation_id"])
        if outcome["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            emit(
                "completed",
                {
                    "action": name,
                    "operation_id": outcome["operation_id"],
                    "status": outcome["status"],
                    "result_sha256": outcome["result_sha256"],
                },
            )
            if outcome["status"] != "SUCCEEDED":
                emit("retained failure; no replay", outcome)
            require(
                outcome["status"] == "SUCCEEDED",
                "Original action failed; inspect retained diagnostics without replay",
            )
            require(
                outcome["completion_log_persisted"] is True,
                "Action completion log was not retained",
            )
            result = outcome["result"]
            require(
                result.get("physical_authority") is False,
                "Action claimed physical authority",
            )
            if name not in {"record_note", "export_logs"}:
                for counter in ZERO_COUNTERS:
                    require(
                        type(result.get(counter)) is int and result[counter] == 0,
                        "Unexpected device/effect count",
                    )
                require(
                    result.get("metadata_inventory_performed") is False,
                    "Unexpected device metadata inventory",
                )
            return outcome
        time.sleep(0.05)
    raise TimeoutError(
        "Original outcome unknown; shutdown requests cancellation, not action replay"
    )


def assert_no_hardware(view):
    require(
        view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED",
        "Unexpected connection",
    )
    require(view["physical_camera"]["last_frame"] is None, "Unexpected physical frame")
    require(
        all(row["state"] == "PHYSICAL_PENDING" for row in view["stages"]),
        "Physical progress was promoted",
    )
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


def snapshot_from_action(outcome):
    return outcome["result"]["steps"][0]["report"]["notebook"]


def verify_snapshot(snapshot, *, prerequisites, launch_id):
    # Import the exact pure draft model only when validating an observed public
    # snapshot. This script has no notebook-file import or replay interface.
    from rocell.application.physical_intake_notebook import PhysicalIntakeNotebook

    require(
        type(snapshot) is dict and type(snapshot.get("snapshot_sha256")) is str,
        "Missing full notebook snapshot",
    )
    raw = canonical(
        {key: value for key, value in snapshot.items() if key != "snapshot_sha256"}
    )
    notebook = PhysicalIntakeNotebook.from_payload(
        raw, prerequisites=prerequisites, expected_sha256=snapshot["snapshot_sha256"]
    )
    require(
        notebook.view() == snapshot,
        "Public notebook changed during strict verification",
    )
    require(
        snapshot["binding"]["launch_session_id"] == launch_id,
        "Notebook is not from this application launch",
    )
    require(
        snapshot["binding"]["prerequisites_sha256"] == prerequisites.evidence_sha256,
        "Notebook substituted the original requirements",
    )
    for name in (
        "physical_authority",
        "hardware_qualified",
        "canonical_stage_pass",
        "device_io_performed",
        "attachment_bytes_verified",
    ):
        require(
            snapshot[name] is False,
            "Draft notebook claimed physical acceptance or verified bytes",
        )
    require(
        len(snapshot["rows"]) == 16,
        "Notebook does not contain the exact sixteen original questions",
    )
    return notebook


def verify_notebook_export(
    receipt, *, workspace, expected_snapshot, prerequisites, launch_id
):
    folder = Path(receipt["path"])
    require(
        folder.parent == workspace / "software/runs/wizard-exports",
        "Assigned export folder changed",
    )
    verified = verify_export(folder)
    require(verified["valid"] is True, "Export verification failed")
    require(
        verified["manifest_sha256"] == receipt["manifest_sha256"],
        "Export receipt manifest hash differs",
    )
    manifest = json.loads(
        read_bounded_regular_file(folder / "manifest.json", maximum_bytes=1024 * 1024)
    )
    matches = [row for row in manifest["files"] if row["name"] == NOTEBOOK_ATTACHMENT]
    require(
        len(matches) == 1,
        "Latest notebook dedicated attachment is missing or ambiguous",
    )
    entry = matches[0]
    payload = read_bounded_regular_file(
        folder / NOTEBOOK_ATTACHMENT, maximum_bytes=1024 * 1024
    )
    require(
        len(payload) == entry["bytes"]
        and hashlib.sha256(payload).hexdigest() == entry["sha256"],
        "Dedicated notebook bytes/hash differ from the immutable export manifest",
    )
    wrapper = json.loads(payload)
    require(
        wrapper["schema"] == "rocell.physical_intake_export.v1"
        and wrapper["status"] == "CURRENT_DRAFT"
        and wrapper["physical_authority"] is False
        and wrapper["hardware_qualified"] is False,
        "Notebook export is not the current unqualified draft",
    )
    require(
        wrapper["notebook"] == expected_snapshot,
        "Export did not preserve the latest complete draft",
    )
    verify_snapshot(
        wrapper["notebook"], prerequisites=prerequisites, launch_id=launch_id
    )
    return {
        "path": str(folder),
        "manifest_sha256": verified["manifest_sha256"],
        "attachment": NOTEBOOK_ATTACHMENT,
        "attachment_sha256": entry["sha256"],
        "attachment_bytes": entry["bytes"],
    }


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--expected-source-sha256", required=True)
    args = parser.parse_args()
    require(
        re.fullmatch(r"[0-9a-f]{64}", args.expected_source_sha256) is not None
        and args.expected_source_sha256 != "0" * 64,
        "Exact frozen source digest required",
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
        emit(
            "launch",
            {"session_id": service.session_id, "source_sha256": service.source_sha256},
        )
        assert_no_hardware(service.view())
        action(service, "physical_camera_initialize")
        require(
            all(
                row["state"] == "PENDING"
                for row in service.view()["physical_camera_setup"]["session"]["stages"]
            ),
            "New original store must be entirely pending",
        )
        collected = action(service, "physical_camera_prerequisites")
        setup = service.view()["physical_camera_setup"]
        require(
            setup["publication"]["status"] == "CURRENT",
            "Original requirement publication held",
        )
        stages, binding = setup["session"]["stages"], setup["session"]["binding"]
        require(
            stages[0]["state"] == "WAITING_OPERATOR"
            and all(row["state"] == "PENDING" for row in stages[1:]),
            "Requirements must not accept a physical stage",
        )
        report = collected["result"]["steps"][0]["report"]
        require(
            report["prerequisites"]["retention"] == "M1_FULL_BYTES_READ_BACK",
            "Original requirement bytes not retained",
        )
        original_payload = canonical(report["prerequisite_document"])
        prerequisites = verify_physical_camera_prerequisites(
            original_payload,
            expected_source_sha256=service.source_sha256,
            expected_session_id=binding["session_id"],
            expected_launch_session_id=binding["launch_id"],
            expected_evidence_sha256=report["prerequisites"]["evidence_sha256"],
        )
        started = action(service, "physical_intake_start")
        initial = snapshot_from_action(started)
        verify_snapshot(
            initial, prerequisites=prerequisites, launch_id=service.session_id
        )
        require(
            initial["revision"] == 0 and initial["previous_sha256"] is None,
            "Draft did not start as a new notebook",
        )
        require(
            all(row["observation"] is None for row in initial["rows"]),
            "A requirement populated an observation automatically",
        )
        recorded = action(service, "physical_intake_record", dict(UNKNOWN_NOTE))
        latest = snapshot_from_action(recorded)
        verify_snapshot(
            latest, prerequisites=prerequisites, launch_id=service.session_id
        )
        require(
            latest["revision"] == 1
            and latest["previous_sha256"] == initial["snapshot_sha256"],
            "Draft revision chain changed",
        )
        require(
            latest["coverage"]
            == {"total": 16, "observed": 0, "unknown": 1, "unrecorded": 15},
            "UNKNOWN incorrectly counted as measured coverage",
        )
        row = next(row for row in latest["rows"] if row["record_id"] == "INT-001")
        observation = row["observation"]
        require(
            observation["status"] == "UNKNOWN",
            "The development note became a physical observation",
        )
        for key in ("observed_value", "method", "evidence_note", "operator_id"):
            require(
                observation[key] == UNKNOWN_NOTE[key],
                "Operator development note was altered",
            )
        for index in range(9):
            action(
                service,
                "record_note",
                {
                    "note": f"Intake export retention check {index + 1}/9; no hardware, measurement, attachment or approval performed."
                },
            )
        require(
            service.operation(recorded["operation_id"])["result"] is None,
            "Generic last-eight retention was not actually exceeded",
        )
        view = service.view()
        require(
            view["physical_intake"]["notebook"] == latest,
            "Current draft was lost after unrelated notes",
        )
        require(
            view["physical_camera_setup"]["prerequisites"] == setup["prerequisites"],
            "Notebook changed original requirements",
        )
        require(
            view["physical_camera_setup"]["session"]["stages"] == stages,
            "Draft notes changed canonical camera stage state",
        )
        require(
            prerequisites.payload == original_payload,
            "Original requirement payload changed",
        )
        assert_no_hardware(view)
        exported = action(service, "export_logs")
        checked = verify_notebook_export(
            exported["result"]["receipt"],
            workspace=workspace,
            expected_snapshot=latest,
            prerequisites=prerequisites,
            launch_id=service.session_id,
        )
        require(
            source_fingerprint(workspace) == service.source_sha256,
            "Source changed during smoke",
        )
        assert_no_hardware(service.view())
        emit(
            "verified no-device intake notebook",
            {
                "source_sha256": service.source_sha256,
                "session": binding,
                "actions": 14,
                "requirements_sha256": prerequisites.evidence_sha256,
                "notebook_sha256": latest["snapshot_sha256"],
                "revision": latest["revision"],
                "observed": 0,
                "unknown": 1,
                "accepted": False,
                "hardware_qualified": False,
                "physical_authority": False,
                "export": checked,
            },
        )
        return 0
    finally:
        service.shutdown()


if __name__ == "__main__":
    raise SystemExit(main())
