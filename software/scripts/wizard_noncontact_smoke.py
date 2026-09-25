"""Public NC-01 smoke: same original store, retained gaps, no hardware or replay.

Run this script with --expected-source-sha256 to build the first thirteen
rehearsal stages and then collect/assess/review/reopen stage fourteen. Each
operation is attempted once. Original stores/exports remain intact on failure.
The final result must be thirteen PASS, noncontact BLOCKED and handoff PENDING.
"""

from __future__ import annotations

import argparse
from contextlib import contextmanager, ExitStack
from copy import deepcopy
import hashlib
import json
from pathlib import Path
import re
import time
from unittest.mock import patch

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_onboarding_durability import read_bounded_regular_file
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import verify_export
from rocell.providers.windows.native_camera_protocol import canonical


CLOSED_ACTIONS = frozenset(
    {
        "rehearsal_initialize",
        "rehearsal_collect",
        "rehearsal_assess",
        "rehearsal_review",
        "rehearsal_discover",
        "rehearsal_reopen",
        "rehearsal_camera_settings",
        "rehearsal_camera_campaign",
        "rehearsal_arm_feedback_campaign",
        "rehearsal_owned_arm_feedback_campaign",
        "record_note",
        "export_logs",
    }
)
ZERO_COUNTERS = (
    "device_open_count",
    "serial_write_count",
    "power_event_count",
    "motion_command_count",
    "contact_command_count",
)
ATTACHMENT = "attachment-noncontact-readiness.json"


def emit(label, value):
    print(label, json.dumps(value, sort_keys=True, ensure_ascii=True), flush=True)


def require(condition, message):
    if not condition:
        raise RuntimeError(message)


def require_frozen_source(workspace: Path, source: str) -> None:
    require(
        type(source) is str
        and re.fullmatch(r"[0-9a-f]{64}", source) is not None
        and source != "0" * 64,
        "Exact nonzero frozen source hash required",
    )
    require(
        source_fingerprint(workspace) == source,
        "Frozen source mismatch; do not migrate/replay",
    )


class TerminalActionFailure(RuntimeError):
    """Original terminal failure, with a separate best-effort export outcome."""

    def __init__(self, operation: dict) -> None:
        super().__init__("Original operation failed; inspect/export without retry")
        self.operation = deepcopy(operation)
        self.failure_export_attempted = False
        self.failure_export_operation: dict | None = None
        self.failure_export_error: Exception | None = None


class ActionOutcomeUnknown(TimeoutError):
    """A polling deadline is not evidence of a terminal worker outcome."""

    further_actions_prohibited = True

    def __init__(self, operation_id: str, last_observed_operation: dict | None) -> None:
        super().__init__(
            "Original action outcome unknown; shutdown cancels, never retries"
        )
        self.operation_id = operation_id
        self.last_observed_operation = deepcopy(last_observed_operation)


def _action_once(service: ArrivalWizardService, name: str, values: dict) -> dict:
    """Dispatch once and observe; this function never initiates another action."""
    require(name in CLOSED_ACTIONS, "Action is not in the closed rehearsal smoke")
    ticket = service.prepare_action(name, values, service.view()["revision"])
    dispatched = service.execute_action(ticket["ticket_id"])
    deadline = time.monotonic() + 250
    operation = None
    while time.monotonic() < deadline:
        operation = service.operation(dispatched["operation_id"])
        if operation["status"] in {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}:
            emit(
                "action",
                {
                    "action": name,
                    "operation_id": operation["operation_id"],
                    "status": operation["status"],
                    "result_sha256": operation["result_sha256"],
                },
            )
            if operation["status"] != "SUCCEEDED":
                emit("original failed operation; no replay", operation)
                raise TerminalActionFailure(operation)
            require(
                operation["completion_log_persisted"] is True,
                "Completion log is not retained",
            )
            result = operation["result"]
            require(
                result.get("physical_authority") is False,
                "Action claimed physical authority",
            )
            if name not in {"record_note", "export_logs"}:
                require(
                    all(
                        type(result.get(key)) is int and result[key] == 0
                        for key in ZERO_COUNTERS
                    ),
                    "Unexpected physical effect count",
                )
                require(
                    result.get("metadata_inventory_performed") is False,
                    "Unexpected device inventory",
                )
            return operation
        time.sleep(0.1)
    raise ActionOutcomeUnknown(dispatched["operation_id"], operation)


def action(service: ArrivalWizardService, name: str, **values: object) -> dict:
    """One action; a known terminal failure gets one same-live-service export.

    A polling deadline with an unknown running outcome is not a terminal
    failure and cannot trigger another action. An export failure is secondary:
    the original operation remains the exception delivered to the caller.
    """
    try:
        return _action_once(service, name, values)
    except TerminalActionFailure as original:
        if name != "export_logs":
            # Mark before prepare: even a rejected export is one attempt. The
            # legacy owned-feedback wrapper also observes this marker, so it
            # cannot add a second export after this helper returns its failure.
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
            except Exception as export_error:
                original.failure_export_error = export_error
                if isinstance(export_error, TerminalActionFailure):
                    original.failure_export_operation = deepcopy(export_error.operation)
                emit(
                    "failure diagnostic export did not complete",
                    {
                        "original_operation_id": original.operation["operation_id"],
                        "error_type": type(export_error).__name__,
                        "export_outcome": (
                            "UNKNOWN"
                            if isinstance(export_error, TimeoutError)
                            else "FAILED_OR_REJECTED"
                        ),
                        "additional_export_attempt_allowed": False,
                    },
                )
        raise


@contextmanager
def replay_guards():
    """Guard actual execution entry points; fixed source/pure evidence reads stay allowed."""
    from rocell.application import rehearsal_arm_identity_stage as identity
    from rocell.application import rehearsal_optics_stages as optics
    from rocell.application import rehearsal_power_stages as power
    from rocell.application import rehearsal_reference_stage as reference
    from rocell.application import rehearsal_noncontact_stage as noncontact
    from rocell.application import owned_arm_feedback_rehearsal_campaign as owned
    from rocell.application import virtual_session
    from rocell.application.arm_feedback_rehearsal_campaign import (
        ArmFeedbackRehearsalCampaign,
    )
    from rocell.application.camera_rehearsal_campaign import SyntheticBinaryCameraWorker
    from rocell.application.owned_camera_rehearsal_campaign import (
        OwnedBinaryCameraWorker,
    )
    from rocell.providers.windows.arm_feedback_worker import ArmFeedbackWorker
    from rocell.providers.windows.owned_arm_feedback_runner import (
        IncapableOwnedArmFeedbackRunner,
    )
    from rocell.providers.windows.camera_worker_client import WindowsCameraWorkerClient
    from rocell.calibration import rigid_correspondence
    from rocell.geometry.urdf import UrdfModel

    with ExitStack() as guards:
        for owner, method in (
            (ArmFeedbackWorker, "run"),
            (owned, "prepare_owned_arm_feedback_campaign"),
            (owned.OwnedArmFeedbackRehearsalCampaign, "run_scoped_campaign"),
            (IncapableOwnedArmFeedbackRunner, "run"),
            (ArmFeedbackRehearsalCampaign, "run_retained_campaign"),
            (ArmFeedbackRehearsalCampaign, "run_campaign"),
            (SyntheticBinaryCameraWorker, "run_campaign"),
            (OwnedBinaryCameraWorker, "run_campaign"),
            (OwnedBinaryCameraWorker, "run_retained_campaign"),
            (identity, "evaluate_rehearsal_arm_identity_stage"),
            (optics, "evaluate_rehearsal_optics_stage"),
            (power, "evaluate_rehearsal_power_stage"),
            (reference, "evaluate_rehearsal_reference_stage"),
            (reference, "fit_rigid_correspondence"),
            (reference, "run_static_phase1_calibration_rehearsal"),
            (rigid_correspondence, "fit_rigid_correspondence"),
            (UrdfModel, "forward_kinematics"),
            (noncontact, "evaluate_rehearsal_noncontact_stage"),
            (noncontact, "assess_current_collision_readiness"),
            (noncontact, "assess_target_accuracy_budget"),
            (virtual_session, "run_virtual_session"),
            (virtual_session, "run_default_virtual_session"),
            (WindowsCameraWorkerClient, "enumerate_metadata"),
            (WindowsCameraWorkerClient, "resolve_identity_metadata"),
            (WindowsCameraWorkerClient, "probe"),
            (WindowsCameraWorkerClient, "capture"),
        ):
            guards.enter_context(
                patch.object(
                    owner,
                    method,
                    side_effect=AssertionError(
                        "Reopen/assessment/review attempted an evaluator, plant or device replay"
                    ),
                )
            )
        yield


def assert_state(service, source, *, stage_state, original=None):
    view = service.view()
    current = view["commissioning_rehearsal"]
    require(service.source_sha256 == source, "Launch source changed")
    require(
        current["stage"] == "noncontact_acceptance"
        and current["stage_state"] == stage_state,
        "Noncontact lifecycle state differs",
    )
    require(
        [row["state"] for row in current["stages"]]
        == ["PASS"] * 13 + [stage_state, "PENDING"],
        "Noncontact gaps advanced the handoff or changed predecessors",
    )
    require(
        current["attempt_event_count"] == 15,
        "NC-01 created an unexpected device campaign attempt",
    )
    require(
        current["physical_authority"] is False, "Rehearsal claimed physical authority"
    )
    require(
        len(view["stages"]) == 15
        and all(row["state"] == "PHYSICAL_PENDING" for row in view["stages"]),
        "Physical stage progress changed",
    )
    require(view["camera"]["image_id"] is None, "Reopen substituted a camera image")
    if original is not None:
        for key in ("session_id", "cell_id", "directory"):
            require(
                current[key] == original[key], "Reopen selected a replacement store"
            )
    return deepcopy(current)


def assert_gaps(current):
    result = current["noncontact_evaluation"]
    require(
        result is not None and result["outcome"] == "BLOCKED",
        "Nominal readiness must remain blocked",
    )
    require(
        result["physical_authority"] is False, "Gap report acquired physical authority"
    )
    nominal = [row for row in result["checks"] if row["check_kind"] == "NOMINAL"]
    controls = [
        row
        for row in result["checks"]
        if row["check_kind"] in {"EXPECTED_FAULT", "INVARIANT"}
    ]
    require(
        len(nominal) == 3 and all(row["passed"] is False for row in nominal),
        "Three actual nominal gaps must be retained",
    )
    require(
        len(controls) == 5 and all(row["passed"] is True for row in controls),
        "The five independent diagnostic controls differ",
    )
    return deepcopy(result)


def export_gap(service, workspace, source, original, expected_receipt=None):
    operation = action(service, "export_logs")
    receipt = operation["result"]["receipt"]
    folder = Path(receipt["path"])
    require(
        folder.parent == workspace / "software/runs/wizard-exports",
        "Export left assigned folder",
    )
    verification = verify_export(folder)
    require(
        verification["valid"] is True
        and verification["manifest_sha256"] == receipt["manifest_sha256"],
        "Export manifest verification failed",
    )
    require(
        verification["provenance"]["source_binding_sha256"] == source,
        "Export source binding changed",
    )
    entries = [row for row in verification["files"] if row["name"] == ATTACHMENT]
    require(len(entries) == 1, "Dedicated full noncontact attachment missing")
    raw = read_bounded_regular_file(folder / ATTACHMENT, maximum_bytes=1024 * 1024)
    entry = entries[0]
    require(
        len(raw) == entry["bytes"]
        and hashlib.sha256(raw).hexdigest() == entry["sha256"],
        "Attachment bytes differ from manifest",
    )
    wrapper = json.loads(raw)
    require(
        wrapper["schema"] == "rocell.noncontact_diagnostic_export.v1"
        and wrapper["publication"] == "CURRENT_GAP_REPORT"
        and wrapper["original_bytes_preserved"] is True
        and wrapper["physical_authority"] is False,
        "Export is not an exact current gap report",
    )
    full = wrapper["receipt"]
    require(
        full["schema"] == "rocell.rehearsal_noncontact_receipt.v1"
        and full["session_id"] == original["session_id"]
        and full["cell_id"] == original["cell_id"]
        and full["workspace_source_sha256"] == source
        and full["physical_observation"] is False,
        "Attachment receipt changed original identity",
    )
    require(
        hashlib.sha256(canonical(full["evaluation"])).hexdigest()
        == full["evaluation_sha256"],
        "Full evaluation bytes/hash changed",
    )
    require(
        full["evaluation_sha256"]
        == original["noncontact_evaluation"]["evaluation_sha256"],
        "Export substituted another evaluation",
    )
    if expected_receipt is not None:
        require(
            canonical(full) == canonical(expected_receipt),
            "Export lost/changed the original full receipt",
        )
    checked = {
        "path": str(folder),
        "manifest_sha256": verification["manifest_sha256"],
        "files": len(verification["files"]),
        "attachment_bytes": len(raw),
        "attachment_sha256": entry["sha256"],
        "receipt_sha256": hashlib.sha256(canonical(full)).hexdigest(),
    }
    emit("verified original noncontact export", checked)
    return full, checked


def run_noncontact_stage(workspace: Path, source: str, before: dict) -> None:
    """Continue only the provided original reviewed stage-13 snapshot; no retry."""
    from wizard_arm_setup_rehearsal_smoke import reopen_original

    require_frozen_source(workspace, source)
    require(
        before["stage"] == "noncontact_acceptance"
        and before["stage_state"] == "PENDING",
        "Exact reviewed stage-thirteen checkpoint required",
    )
    current = deepcopy(before)
    exports = []
    full = None
    launches = []
    # Each new launch proves retained restoration. No loop retries a failed
    # action: phases are distinct expected states in the same original store.
    for phase in ("collect", "assess", "review", "verify-blocked"):
        require_frozen_source(workspace, source)
        service = ArrivalWizardService(workspace)
        launches.append(service.session_id)
        try:
            require(service.source_sha256 == source, "New launch source changed")
            if phase == "collect":
                with replay_guards():
                    reopen_original(service, current)
                assert_state(service, source, stage_state="PENDING", original=before)
                operation = action(
                    service,
                    "rehearsal_collect",
                    operator_id="noncontact-smoke-operator",
                )
                current = assert_state(
                    service, source, stage_state="WAITING_OPERATOR", original=before
                )
                assert_gaps(current)
                full, checked = export_gap(service, workspace, source, current)
                exports.append(checked)
                for index in range(9):
                    action(
                        service,
                        "record_note",
                        note=f"NC-01 retention check {index + 1}/9; no measurement, motion or acceptance.",
                    )
                require(
                    service.operation(operation["operation_id"])["result"] is None,
                    "Generic last-eight result history was not actually exceeded",
                )
                _, checked = export_gap(service, workspace, source, current, full)
                exports.append(checked)
            else:
                with replay_guards():
                    reopen_original(service, current)
                    restored = assert_state(
                        service,
                        source,
                        stage_state=current["stage_state"],
                        original=before,
                    )
                    require(
                        restored["noncontact_evaluation"]
                        == current["noncontact_evaluation"],
                        "Retained gap projection changed on another launch",
                    )
                    if phase == "assess":
                        action(service, "rehearsal_assess")
                        current = assert_state(
                            service,
                            source,
                            stage_state="REVIEW_PENDING",
                            original=before,
                        )
                        require(
                            current["assessment"]["outcome"] == "BLOCKED"
                            and len(current["assessment"]["reason_codes"]) == 3,
                            "Assessment hid actual nominal gaps",
                        )
                    elif phase == "review":
                        action(
                            service,
                            "rehearsal_review",
                            reviewer_id="noncontact-independent-reviewer",
                            accept_assessment=True,
                        )
                        current = assert_state(
                            service, source, stage_state="BLOCKED", original=before
                        )
                    else:
                        current = assert_state(
                            service, source, stage_state="BLOCKED", original=before
                        )
                    assert_gaps(current)
                    _, checked = export_gap(service, workspace, source, current, full)
                    exports.append(checked)
            require_frozen_source(workspace, source)
        finally:
            service.shutdown()
    emit(
        "verified original noncontact workflow",
        {
            "source_sha256": source,
            "session_id": current["session_id"],
            "cell_id": current["cell_id"],
            "directory": current["directory"],
            "journal_head_sha256": current["journal_head_sha256"],
            "evaluation_sha256": current["noncontact_evaluation"]["evaluation_sha256"],
            "stage_states": [row["state"] for row in current["stages"]],
            "attempt_event_count": current["attempt_event_count"],
            "stage14_actions": 25,
            "launches": launches,
            "exports": exports,
            "nominal_failed": 3,
            "diagnostic_controls_passed": 5,
            "physical_authority": False,
            "physical_stages_pending": 15,
        },
    )


def main():
    parser = argparse.ArgumentParser(description=__doc__, allow_abbrev=False)
    parser.add_argument("--expected-source-sha256", required=True)
    args = parser.parse_args()
    from wizard_arm_setup_rehearsal_smoke import main as full_workflow

    full_workflow(
        ["--noncontact", "--expected-source-sha256", args.expected_source_sha256]
    )


if __name__ == "__main__":
    main()
