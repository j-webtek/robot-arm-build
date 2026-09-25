"""Exercise one contained incapable camera campaign through real Arrival APIs.

Creates a fresh separate rehearsal and diagnostic/export records under the
server-assigned software/runs folders. The child produces source-derived
native-format fixtures; no host device discovery, physical endpoint, robot
power, motion or contact is permitted. There are no doubles, legacy binary
campaign fallbacks, existing-session mutations or automatic operation retries.

Run only with source frozen and no other expensive commissioning tests active.
Every outcome attempts an assigned-folder diagnostic export, including a held
fault result. A local wait timeout requests the registered Stop action once,
then waits a bounded interval; it never assumes the original action did not run.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import re
import sys
import time
from typing import Any

from rocell.application.arrival_wizard_service import ArrivalWizardService
from rocell.application.physical_onboarding import STAGE_ORDER
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wizard_diagnostic_export import verify_export


FAULTS = (
    "none",
    "identity-mismatch",
    "cleanup-uncertain",
    "child-timeout",
    "malformed-result",
    "control-readback-drift",
)
TERMINAL = {"SUCCEEDED", "FAILED", "CANCELLED", "TIMED_OUT"}
ALLOWED_ACTIONS = {
    "rehearsal_initialize",
    "rehearsal_collect",
    "rehearsal_assess",
    "rehearsal_review",
    "rehearsal_camera_settings",
    "rehearsal_camera_probe",
    "rehearsal_camera_configuration",
    "rehearsal_owned_camera_campaign",
    "stop_operation",
    "export_logs",
}
MAX_ACTIONS = 24  # Normal path: 19 including export; always below Arrival's 32.
OPERATION_WAIT_S = 180
STOP_DRAIN_S = 60


def emit(label: str, value: object) -> None:
    print(label, json.dumps(value, sort_keys=True, ensure_ascii=True), flush=True)


def require(condition: bool, message: str) -> None:
    if not condition:
        raise RuntimeError(message)


class PublicSmoke:
    """One-shot public tickets only; polling is read-only and never a replay."""

    def __init__(self, service: ArrivalWizardService) -> None:
        self.service = service
        self.action_count = 0
        self.in_flight: str | None = None

    def wait(self, operation_id: str, *, seconds: float) -> dict[str, Any]:
        deadline = time.monotonic() + seconds
        next_update = 0.0
        while time.monotonic() < deadline:
            operation = self.service.operation(operation_id)
            if operation["status"] in TERMINAL:
                if self.in_flight == operation_id:
                    self.in_flight = None
                emit(
                    "operation completed",
                    {
                        "operation_id": operation_id,
                        "action_id": operation["action_id"],
                        "status": operation["status"],
                        "result_sha256": operation.get("result_sha256"),
                        "completion_log_persisted": operation.get(
                            "completion_log_persisted"
                        ),
                        "error": operation.get("error"),
                    },
                )
                return operation
            if time.monotonic() >= next_update:
                emit(
                    "operation pending; not replaying",
                    {
                        "operation_id": operation_id,
                        "status": operation["status"],
                        "message": operation.get("message"),
                    },
                )
                next_update = time.monotonic() + 15
            time.sleep(0.2)
        raise TimeoutError(
            f"Local wait exceeded for {operation_id}; outcome unknown, not replaying."
        )

    def action(self, name: str, *, allow_hold: bool = False, **values: Any) -> dict:
        require(name in ALLOWED_ACTIONS, "Action is outside this closed smoke plan.")
        require(self.action_count < MAX_ACTIONS, "Smoke action budget exhausted.")
        ticket = self.service.prepare_action(
            name, values, self.service.view()["revision"]
        )
        emit(
            "explicit action preview",
            {
                "action_id": name,
                "ticket_id": ticket["ticket_id"],
                "input": ticket["input"],
                "effects": ticket["effects"],
                "warnings": ticket["warnings"],
            },
        )
        # Running this script explicitly approves this fixed incapable test
        # sequence. There is no ambient hardware approval or fallback dispatch.
        self.action_count += 1
        receipt = self.service.execute_action(ticket["ticket_id"])
        operation_id = receipt["operation_id"]
        self.in_flight = operation_id
        emit("operation dispatched exactly once", receipt)
        operation = self.wait(operation_id, seconds=OPERATION_WAIT_S)
        if not allow_hold:
            require(
                operation["status"] == "SUCCEEDED",
                f"{name} held; inspect its retained result and export, do not replay.",
            )
        return operation

    def stop_and_drain(self) -> None:
        """Ask once through the registered action; never claim a robot E-stop."""
        target = self.in_flight
        if target is None:
            return
        operation = self.service.operation(target)
        if operation["status"] in TERMINAL:
            self.in_flight = None
            return
        emit(
            "requesting bounded diagnostic Stop, not a robot emergency stop",
            {"target_operation_id": target},
        )
        try:
            self.action("stop_operation", allow_hold=True)
        finally:
            # The housekeeping operation must not hide the original unsettled
            # operation. Continue observing only that original operation ID.
            self.in_flight = target
        self.wait(target, seconds=STOP_DRAIN_S)


def source_guard(workspace: Path, service: ArrivalWizardService, expected: str) -> None:
    require(
        service.source_sha256 == expected and source_fingerprint(workspace) == expected,
        "Workspace source changed; hold, export and review. Never retry this session automatically.",
    )


def physical_holds(service: ArrivalWizardService) -> None:
    view = service.view()
    require(view["mode"] == "rehearsal", "This smoke cannot use physical mode.")
    require(view["physical_authority"] is False, "Unexpected authority claim.")
    require(
        all(stage["state"] == "PHYSICAL_PENDING" for stage in view["stages"]),
        "A synthetic run must not pass physical stages.",
    )
    require(
        view["camera"]["status"] == view["arm"]["status"] == "NOT_CONNECTED",
        "A fixture run must not claim physical connections.",
    )


def assessment_and_review(smoke: PublicSmoke) -> None:
    smoke.action("rehearsal_assess")
    assessment = smoke.service.view()["commissioning_rehearsal"]["assessment"]
    emit("exact retained rehearsal assessment", assessment)
    require(
        assessment is not None and assessment["outcome"] == "PASS",
        "Rehearsal assessment did not pass; no review acceptance will be sent.",
    )
    smoke.action(
        "rehearsal_review",
        reviewer_id="owned-camera-smoke-reviewer",
        accept_assessment=True,
    )


def sha256_argument(value: str) -> str:
    if re.fullmatch(r"[a-f0-9]{64}", value) is None:
        raise argparse.ArgumentTypeError("Expected a lowercase SHA-256 digest.")
    return value


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--frame-count", type=int, choices=range(1, 5), default=1)
    parser.add_argument("--fault", choices=FAULTS, default="none")
    parser.add_argument(
        "--probe-and-configure",
        action="store_true",
        help="Before capture, retain one contained probe and stage manual gain32 plus automatic exposure from its reported controls. No physical device is used.",
    )
    parser.add_argument(
        "--assess-and-review",
        action="store_true",
        help="For a nominal complete campaign only, assess/review stage five; never run stage six.",
    )
    parser.add_argument("--expected-source-sha256", type=sha256_argument)
    args = parser.parse_args()
    if args.fault == "control-readback-drift" and not args.probe_and_configure:
        parser.error("Readback drift requires --probe-and-configure.")
    if args.assess_and_review and args.fault != "none":
        parser.error(
            "Fault runs export held evidence and cannot request review acceptance."
        )

    workspace = Path(__file__).resolve().parents[2]
    service = ArrivalWizardService(workspace, mode="rehearsal")
    smoke = PublicSmoke(service)
    exit_code = 0
    retained_fault: dict[str, Any] | None = None
    retained_fault_operation: str | None = None
    try:
        try:
            source = args.expected_source_sha256 or service.source_sha256
            source_guard(workspace, service, source)
            physical_holds(service)
            fresh = service.view()["commissioning_rehearsal"]
            require(
                fresh["status"] == "NOT_STARTED"
                and fresh["session_origin"] == "NEW_THIS_LAUNCH"
                and not Path(fresh["directory"]).exists(),
                "Expected a fresh unused rehearsal; no existing store is opened or changed.",
            )
            emit(
                "fresh smoke identity and assigned folders",
                {
                    "source_sha256": source,
                    "launch_session_id": service.session_id,
                    "rehearsal_session_id": fresh["session_id"],
                    "cell_id": fresh["cell_id"],
                    "rehearsal_directory": fresh["directory"],
                    "export_directory": service.view()["exports"]["directory"],
                    "frame_count": args.frame_count,
                    "fault": args.fault,
                    "physical_authority": False,
                },
            )
            smoke.action("rehearsal_initialize")
            for stage in STAGE_ORDER[:4]:
                require(
                    service.view()["commissioning_rehearsal"]["stage"] == stage.value,
                    "Canonical prerequisite stage drifted; do not skip or substitute checks.",
                )
                smoke.action(
                    "rehearsal_collect", operator_id="owned-camera-smoke-operator"
                )
                assessment_and_review(smoke)
            require(
                service.view()["commissioning_rehearsal"]["stage"]
                == STAGE_ORDER[4].value,
                "Expected the due stage-five camera campaign.",
            )
            smoke.action("rehearsal_collect", operator_id="owned-camera-smoke-operator")
            smoke.action("rehearsal_camera_settings", brightness_offset=0)
            if args.probe_and_configure:
                smoke.action("rehearsal_camera_probe", fault="none")
                view = service.view()["commissioning_rehearsal"]["camera_configuration"]
                require(
                    view is not None and view["status"] == "PROBE_COMPLETE",
                    "Probe did not retain complete capabilities.",
                )
                action = next(
                    item
                    for item in service.view()["actions"]
                    if item["action_id"] == "rehearsal_camera_configuration"
                )
                fields = action["fields"]
                require(
                    len(fields[0]["options"]) == 1,
                    "Fixed fixture must report exactly its registered mode; do not guess.",
                )
                configured = {
                    field["name"]: field["default"]
                    for field in fields
                    if "default" in field
                }
                configured.update(
                    mode_choice_id=fields[0]["options"][0]["value"],
                    gain_mode="manual",
                    gain_value=32,
                    exposure_mode="auto",
                )
                smoke.action("rehearsal_camera_configuration", **configured)
                candidate = service.view()["commissioning_rehearsal"][
                    "camera_configuration"
                ]
                require(
                    candidate["status"] == "CONFIGURATION_STAGED"
                    and candidate["readback"] is None,
                    "Staging must not claim applied settings.",
                )
            campaign = smoke.action(
                "rehearsal_owned_camera_campaign",
                frame_count=args.frame_count,
                fault=args.fault,
                allow_hold=True,
            )
            emit("actual public campaign result", campaign)
            projection = service.view()["commissioning_rehearsal"].get("camera_process")
            emit("actual retained camera-process projection", projection)
            source_guard(workspace, service, source)
            physical_holds(service)
            complete = (
                campaign["status"] == "SUCCEEDED"
                and isinstance(projection, dict)
                and projection["status"] == "RETAINED_COMPLETE_REHEARSAL"
            )
            if args.fault == "none":
                require(
                    complete,
                    "Nominal campaign is held; export evidence without fallback or replay.",
                )
                if args.probe_and_configure:
                    configuration = service.view()["commissioning_rehearsal"][
                        "camera_configuration"
                    ]
                    emit(
                        "retained configuration and independent readback", configuration
                    )
                    require(
                        configuration is not None
                        and configuration["status"] == "READBACK_COMPLETE"
                        and configuration["readback"]["status"]
                        == "REQUESTED_SETTINGS_OBSERVED_REHEARSAL",
                        "Configured capture lacks independent matching readback.",
                    )
                if args.assess_and_review:
                    assessment_and_review(smoke)
                    require(
                        service.view()["commissioning_rehearsal"]["stage"]
                        == STAGE_ORDER[5].value,
                        "Nominal reviewed stage five did not reach the pending stage-six checkpoint.",
                    )
                emit(
                    "smoke outcome",
                    "COMPLETE_INCAPABLE_REHEARSAL_NOT_PHYSICAL_QUALIFICATION",
                )
            else:
                require(
                    not complete,
                    "Injected fault unexpectedly reported complete; export and investigate.",
                )
                require(
                    isinstance(projection, dict)
                    and projection.get("status") == "RETAINED_INCOMPLETE_REHEARSAL"
                    and isinstance(projection.get("process"), dict)
                    and projection["process"].get("created") is True,
                    "No retained created-child fault result is visible; export the hold, but do not count this as an exercised fault scenario.",
                )
                if args.fault == "control-readback-drift":
                    # This scenario must now explain the exact retained caller
                    # rejection, not merely report a generic failed child.
                    retained_fault = service.view()["commissioning_rehearsal"][
                        "camera_fault_diagnostic"
                    ]
                    retained_fault_operation = campaign["operation_id"]
                    require(
                        retained_fault is not None
                        and retained_fault["reason_category"]
                        == "CONTROL_READBACK_MISMATCH_REPORTED"
                        and retained_fault["reported_code"] == "INVALID_CAMERA_CONTRACT"
                        and retained_fault["basis"]
                        == "RETAINED_CALLER_ERROR_EXACT_MATCH"
                        and retained_fault["retry_this_attempt_allowed"] is False
                        and retained_fault["automatic_retry_allowed"] is False
                        and retained_fault["clear_quarantine_allowed"] is False
                        and retained_fault["physical_authority"] is False,
                        "Retained fault explanation or no-retry boundaries differ.",
                    )
                    emit("exact retained camera fault explanation", retained_fault)
                emit(
                    "smoke outcome",
                    "FAULT_RESULT_RETAINED_NO_ASSESSMENT_OR_REVIEW_ACCEPTANCE",
                )
            source_guard(workspace, service, source)
            physical_holds(service)
        except (Exception, KeyboardInterrupt) as error:
            exit_code = 1
            emit(
                "smoke held; no fallback or replay",
                {"error_type": type(error).__name__, "message": str(error)},
            )
            try:
                smoke.stop_and_drain()
            except (Exception, KeyboardInterrupt) as cleanup_error:
                emit(
                    "diagnostic cleanup unresolved",
                    {
                        "error_type": type(cleanup_error).__name__,
                        "message": str(cleanup_error),
                        "physical_power_state": "NOT_OBSERVED",
                    },
                )
        finally:
            # Even source drift or a known failed campaign should remain
            # exportable through the normal housekeeping action. If an original
            # operation is still unresolved, an export hold is reported honestly.
            try:
                exported = smoke.action("export_logs", allow_hold=True)
                emit("actual diagnostic export operation", exported)
                require(
                    exported["status"] == "SUCCEEDED", "Diagnostic export was held."
                )
                path = Path(exported["result"]["receipt"]["path"])
                verified = verify_export(path)
                emit(
                    "independently verified assigned-folder export",
                    {"path": str(path), "verification": verified},
                )
                require(verified["valid"] is True, "Export verification failed.")
                if retained_fault is not None:
                    assert retained_fault_operation is not None
                    attachment = path / (
                        "attachment-result-"
                        + retained_fault_operation.removeprefix("operation-")
                        + ".json"
                    )
                    original_result = json.loads(attachment.read_bytes())
                    named = [
                        step["report"]["camera_fault_diagnostic"]
                        for step in original_result["steps"]
                        if step["name"] == "retained-incapable-owned-camera-diagnostics"
                    ]
                    report = json.loads((path / "report.json").read_bytes())
                    require(
                        named == [retained_fault]
                        and report["snapshot"]["commissioning_rehearsal"][
                            "camera_fault_diagnostic"
                        ]
                        == retained_fault,
                        "Export lost or changed the exact safe fault projection.",
                    )
                    emit(
                        "fault explanation verified in full result and export snapshot",
                        {
                            "evidence_sha256": retained_fault["evidence_sha256"],
                            "reason_category": retained_fault["reason_category"],
                            "automatic_retry_allowed": False,
                        },
                    )
                emit(
                    "final checkpoint",
                    {
                        "actions_started": smoke.action_count,
                        "rehearsal": service.view()["commissioning_rehearsal"],
                        "physical_stages": service.view()["stages"],
                    },
                )
            except (Exception, KeyboardInterrupt) as export_error:
                exit_code = 1
                emit(
                    "export unresolved; inspect original operation and assigned folders",
                    {
                        "error_type": type(export_error).__name__,
                        "message": str(export_error),
                    },
                )
    finally:
        service.shutdown()
    return exit_code


if __name__ == "__main__":
    sys.exit(main())
