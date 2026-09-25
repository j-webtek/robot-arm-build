"""Fixed diagnostic worker, never a general command or device executor.

Run only by the local wizard's closed registry. Input is bounded semantic JSON;
all CLI arguments and module names are resolved here. No physical camera open,
serial connection, power instruction or motion command is registered.
"""

from __future__ import annotations

from contextlib import redirect_stdout, redirect_stderr
import io
import json
from pathlib import Path
import platform
import sys
import time
from typing import Any

MAX_OUTPUT = 4 * 1024 * 1024


class BoundedText(io.StringIO):
    def __init__(self, limit: int = MAX_OUTPUT) -> None:
        super().__init__()
        self.limit = limit
        self.written = 0

    def write(self, text: str) -> int:
        self.written += len(text.encode("utf-8"))
        if self.written > self.limit:
            raise ValueError("Diagnostic output exceeded its byte budget")
        return super().write(text)


def _cli(workspace: Path, args: list[str]) -> dict[str, Any]:
    from rocell.cli import main

    stdout, stderr = BoundedText(), BoundedText(128 * 1024)
    with redirect_stdout(stdout), redirect_stderr(stderr):
        code = main(["--workspace", str(workspace), *args])
    output = stdout.getvalue()
    try:
        report = json.loads(output)
    except (ValueError, TypeError):
        report = {"output": output}
    return {"exit_code": code, "report": report, "stderr": stderr.getvalue()}


def _inventory() -> dict[str, Any]:
    from rocell.application.physical_device_inventory import (
        SubprocessArgvCommandRunner,
        compose_physical_device_inventory_report,
        inventory_linux_video_cameras_from_sysfs,
        inventory_serial_ports_with_pyserial,
        inventory_windows_pnp_cameras,
    )

    system = platform.system()
    if system == "Windows":
        cameras = inventory_windows_pnp_cameras(SubprocessArgvCommandRunner())
    elif system == "Linux":
        cameras = inventory_linux_video_cameras_from_sysfs()
    else:
        raise ValueError("Metadata inventory is supported on Windows/Linux only")
    return compose_physical_device_inventory_report(
        platform_system=system,
        captured_at_unix_ns=time.time_ns(),
        camera_inventory=cameras,
        serial_inventory=inventory_serial_ports_with_pyserial(),
    ).to_dict()


def run(
    workspace: Path, action_id: str, supplied: dict[str, Any], cell_id: str
) -> dict[str, Any]:
    from rocell.application.wizard_actions import ACTION_BY_ID, validate_action_input

    if action_id not in ACTION_BY_ID:
        raise ValueError("Unknown registered diagnostic action")
    action = ACTION_BY_ID[action_id]
    values = validate_action_input(action, supplied)
    if action.hold or action.worker in {"unavailable", "export", "note", "stop"}:
        raise ValueError("This action cannot be executed by a diagnostic worker")
    steps: list[dict[str, Any]] = []
    if action.worker == 'product_ghost_case_review':
        from .product_ghost_export_review import review_product_case
        steps.append({'name':'product_ghost_case_review','exit_code':0,
                      'report':review_product_case(workspace,values['export_id'])})
    elif action.worker == 'ghost_endpoints':
        from .ghost_endpoint_rehearsal import rehearse_ghost_endpoints
        index=values['fault_trial']
        if index != int(index):
            raise ValueError('Fault trial must be an integer')
        steps.append({'name':'ghost_endpoints','exit_code':0,'report':rehearse_ghost_endpoints(
            workspace,values['text'],fault=values['fault'],fault_trial=int(index))})
    elif action.worker == 'ghost_keyboard':
        from .ghost_keyboard import rehearse_ghost_keyboard
        steps.append({'name':'ghost_keyboard','exit_code':0,
                      'report':rehearse_ghost_keyboard(workspace,values['text'])})
    elif action.worker == 'tap_capture_review':
        from .tap_capture_review import review_tap_capture
        steps.append({'name':'tap_capture_review','exit_code':0,
                      'report':review_tap_capture(values['capture_json'])})
    elif action.worker == 'input_capture_review':
        from .input_capture_review import review_input_capture
        steps.append({'name':'input_capture_review','exit_code':0,
                      'report':review_input_capture(values['capture_json'])})
    elif action.worker == 'cartesian_export_review':
        from .cartesian_export_review import review_cartesian_export
        steps.append({'name':'cartesian_export_review','exit_code':0,
                      'report':review_cartesian_export(workspace,values['export_id'])})
    elif action.worker == 'endpoint_request_review':
        from .wizard_endpoint_review import review_endpoint_request
        steps.append({'name':'endpoint_request_review','exit_code':0,
                      'report':review_endpoint_request(values['request_json'])})
    elif action.worker == 'bench_review_key_setup':
        from .wizard_bench_key_setup import run_key_setup
        report = run_key_setup(workspace,values)
        steps.append({'name':'bench_review_key_setup','exit_code':0,'report':report})
    elif action.worker == 'first_motion_review':
        from .first_motion_contract import review_first_motion_request
        steps.append({'name':'first_motion_review','exit_code':0,
                      'report':review_first_motion_request(values['request_json'])})
    elif action.worker == 'first_motion_rehearsal':
        from .first_motion_rehearsal import rehearse
        steps.append({'name':'first_motion_rehearsal','exit_code':0,
                      'report':rehearse(values['scenario'])})
    elif action.worker == 'movement_endpoint_rehearsal':
        from .wizard_endpoint_rehearsal import run_endpoint_rehearsal
        report = run_endpoint_rehearsal(workspace, values)
        steps.append({'name':'movement_endpoint_rehearsal','exit_code':0,'report':report})
    elif action.worker == 'movement_saved_capture':
        from .wizard_movement_capture import run_saved_capture
        report = run_saved_capture(workspace, values['export_name'])
        steps.append({'name':'movement_saved_capture','exit_code':0,'report':report})
    elif action.worker == 'positional_campaign_rehearsal':
        from .positional_campaign_rehearsal import run_persisted_wizard_rehearsal
        report,journal = run_persisted_wizard_rehearsal(workspace,values)
        steps.append({'name':'positional_campaign_rehearsal','exit_code':0,
                      'report':report})
        steps.append({'name':'positional_campaign_journal','exit_code':0,'report':journal})
    elif action.worker == 'wrist_correction_rehearsal':
        from .wrist_correction_pipeline_rehearsal import run_correction_pipeline_rehearsal
        report=run_correction_pipeline_rehearsal(workspace,values['scenario'])
        steps.append({'name':'wrist_correction_rehearsal',
                      'exit_code':0 if report['expected_outcome_matched'] else 1,'report':report})
    elif action.worker == 'pose_policy_review':
        from .pose_policy_review import build_review
        report=build_review(workspace/'software',**values)
        steps.append({'name':'pose_policy_review','exit_code':0,'report':report})
    elif action.worker == "movement_campaign":
        from .wizard_movement_campaign import run_campaign
        report = run_campaign(action_id, values, workspace)
        steps.append({"name":"movement_campaign","exit_code":0,"report":report})
    elif action.worker == "baseline":
        from rocell.rc03 import import_build_snapshot

        # The same strict import used by application planning validates the
        # selected hardware snapshot instead of duplicating its hash rules.
        snapshot = import_build_snapshot(workspace)
        steps.append(
            {
                "name": "build_alignment",
                "exit_code": 0,
                "report": {
                    "manifest_id": snapshot.manifest_id,
                    "active_build_id": snapshot.active_build_id,
                    "physical_release_status": snapshot.physical_release_status,
                    "hard_blockers": list(snapshot.hard_blockers),
                },
            }
        )
        for label, args in (
            (
                "host",
                ["host-doctor", "--profile", "hardware", "--require-pass", "--json"],
            ),
            ("foundation", ["physical-onboard", "verify-foundation", "--json"]),
            (
                "connections",
                ["rehearse-physical-connections", "--require-expected", "--json"],
            ),
        ):
            steps.append({"name": label, **_cli(workspace, args)})
    elif action.worker in ("boundary_tests","positional_boundary_tests"):
        import pytest

        targets = (
            "test_arm_protocol.py",
            "test_camera_sources.py",
            "test_uvc_inventory.py",
            "test_physical_device_inventory.py",
            "test_physical_onboarding_m1_cli.py",
        )
        if action.worker == 'positional_boundary_tests':
            # Closed source-owned list: browser input cannot add paths or pytest
            # options. These suites use synthetic I/O and reject native release.
            targets = (
                'test_positional_campaign_authority.py',
                'test_positional_campaign_native_protocol.py',
                'test_positional_campaign_launch.py',
                'test_positional_campaign_receipt.py',
                'test_positional_campaign_serial_api.py',
                'test_positional_campaign_serial_connection.py',
                'test_positional_campaign_native_capture.py',
                'test_positional_campaign_native_review.py',
                'test_positional_campaign_native_retention.py',
                'test_positional_campaign_native_export.py',
                'test_positional_campaign_child_execution.py',
                'test_positional_campaign_native_package.py',
                'test_positional_campaign_reference_reader.py',
                'test_positional_campaign_invocation.py',
                'test_positional_campaign_native_registration.py',
                'test_positional_campaign_process_codec.py',
                'test_positional_campaign_process_owner.py',
                'test_arm_controller_metadata_windows.py',
                'test_campaign_pinned_retention.py',
                'test_positional_campaign_capacity_v3.py',
                'test_wizard_positional_campaign_native.py',
                'test_wizard_positional_campaign_execution.py',
                'test_positional_campaign_bootstrap.py',
                'test_positional_campaign_prelaunch.py',
                'test_positional_stop_assessment.py',
                'test_positional_stop_reconstruction.py',
                'test_positional_current_context.py',
                'test_positional_campaign_admission.py',
                'test_positional_campaign_capture.py',
                'test_positional_owned_campaign.py',
                'test_positional_campaign_reconstruction.py',
                'test_positional_campaign_export.py',
                'test_positional_campaign_journal.py',
                'test_positional_campaign.py',
                'test_wrist_endpoint_verification.py',
                'test_servo_freshness_proposal.py',
                'test_wrist_correction_proposal.py',
                'test_wrist_correction_preview.py',
                'test_wrist_correction_review_authority.py',
                'test_wrist_correction_consumption.py',
                'test_wrist_correction_result_review.py',
                'test_wrist_correction_result_publication.py',
                'test_wizard_wrist_correction_rehearsal.py',
                'test_wrist_correction_plan_binding.py',
                'test_wrist_correction_current_context.py',
                'test_wrist_correction_command_binding.py',
                'test_wrist_correction_serial_api.py',
                'test_wrist_correction_serial_connection.py',
                'test_wrist_correction_capture.py',
                'test_wrist_correction_owned_trial.py',
                'test_wrist_correction_native_protocol.py',
                'test_wrist_correction_evidence_store.py',
                'test_wrist_correction_worker_claim.py',
                'test_wrist_correction_trial_execution.py',
                'test_wrist_correction_native_result.py',
                'test_wrist_correction_parent_review.py',
                'test_wrist_correction_native_package.py',
                'test_wrist_correction_native_registration.py',
                'test_wrist_correction_prelaunch.py',
                'test_wrist_correction_child_execution.py',
                'test_wrist_correction_invocation.py',
                'test_wrist_correction_parent_retention.py',
                'test_wrist_correction_process_finalization.py',
                'test_wrist_correction_process_owner.py',
                'test_wrist_correction_worker_preparation.py',
                'test_wrist_correction_export.py',
                'test_wizard_wrist_correction_coordinator.py',
                'test_wrist_correction_saved_sources.py',
                'test_wrist_correction_assessment_binding.py',
                'test_wizard_saved_wrist_correction.py',
                'test_wizard_wrist_correction_http.py',
                'test_wrist_correction_final_readback.py',
                'test_wrist_correction_final_capture.py',
                'test_wrist_correction_owned_final_capture.py',
                'test_wrist_correction_final_review.py',
                'test_wrist_correction_final_consumption.py',
                'test_wrist_correction_final_dispatch.py',
                'test_wrist_correction_final_result_review.py',
            )
        output = BoundedText()
        with redirect_stdout(output), redirect_stderr(output):
            code = pytest.main(
                [
                    *(
                        str(workspace / "software/tests/unit" / target)
                        for target in targets
                    ),
                    "-q",
                    "-p",
                    "no:cacheprovider",
                ]
            )
        steps.append(
            {
                "name": "registered_positional_suite" if action.worker == 'positional_boundary_tests' else "registered_boundary_suite",
                "exit_code": int(code),
                "report": {"output": output.getvalue(), "test_files": list(targets)},
            }
        )
    elif action.worker == "arm_feedback_contract":
        from rocell.providers.windows.arm_feedback_worker import (
            rehearse_arm_feedback_campaign,
        )

        report = rehearse_arm_feedback_campaign(values["scenario"])
        steps.append(
            {
                "name": "one_shot_arm_feedback_contract",
                "exit_code": 0 if report["expected_outcome_matched"] else 1,
                "report": report,
            }
        )
    elif action.worker == "inventory":
        steps.append(
            {"name": "metadata_inventory", "exit_code": 0, "report": _inventory()}
        )
    elif action.worker == "inventory_fixture":
        from rocell.application.wizard_inventory_fixture import (
            rehearsal_device_inventory,
        )

        steps.append(
            {
                "name": "metadata_inventory",
                "exit_code": 0,
                "report": rehearsal_device_inventory(values["scenario"]),
            }
        )
    elif action.worker in {"native_arm_metadata", "native_arm_metadata_fixture"}:
        from rocell.application.wizard_native_arm_metadata import (
            COLLECTION_TIMEOUT_MS,
            decode_controller_snapshot,
            rehearse_native_arm_metadata_snapshot,
        )

        if action.worker == "native_arm_metadata_fixture":
            # The closed fixture never imports the native acquirer or a serial
            # provider. Its observations remain explicitly incapable evidence.
            report = rehearse_native_arm_metadata_snapshot(values["scenario"])
        else:
            if platform.system() != "Windows":
                raise ValueError("Native controller metadata requires Windows")
            from threading import Event
            from rocell.providers.windows.controller_metadata import (
                WindowsControllerMetadataAcquirer,
            )

            # This explicit child-only action loads CM metadata APIs, not a port.
            # The parent diagnostic process supplies the hard timeout/Stop
            # boundary for a stalled native call; this local deadline never
            # renews or grants an energization/serial/camera permission.
            acquirer = WindowsControllerMetadataAcquirer(
                deadline_ns=time.monotonic_ns() + COLLECTION_TIMEOUT_MS * 1_000_000,
                cancellation=Event(),
            )
            report = json.loads(
                decode_controller_snapshot(acquirer(), "physical").payload()
            )
        steps.append(
            {"name": "native_arm_metadata_snapshot", "exit_code": 0, "report": report}
        )
    elif action.worker == "board_preview":
        from rocell.application.context import load_simulation_context

        context = load_simulation_context(
            workspace, workspace / "software/config/system_manifest.json"
        )
        steps.append(
            {
                "name": "nominal_board",
                "exit_code": 0,
                "report": {
                    "status": "NOMINAL_SCHEMATIC_NOT_CAMERA_CAPTURE",
                    "manifest_id": context.snapshot.manifest_id,
                    "coordinate_state": "NOMINAL_UNMEASURED",
                    "source": "active-project/RoCell_v0_3/config/workcell_layout.json",
                },
            }
        )
    elif action.worker == "prebuild_vision_checks":
        from rocell.application.wizard_actions import CAMERA_FAULTS

        # Reuse the same source-bound synthetic vision and connection checks as
        # the individual wizard actions. This is deliberately not a second
        # camera provider or a shortcut into physical commissioning.
        checks = [
            (
                "synthetic_static_vision",
                ["rehearse-b0477-stack", "--require-pass", "--json"],
            ),
            *(
                (
                    "camera_connection_" + fault.replace("-", "_"),
                    [
                        "rehearse-physical-connections",
                        "--fault",
                        fault,
                        "--require-expected",
                        "--json",
                    ],
                )
                for fault in CAMERA_FAULTS
            ),
        ]
        for name, args in checks:
            # A diagnostic failure stays in the report. Independent, incapable
            # scenarios may continue; they never retry a hardware operation.
            steps.append({"name": name, **_cli(workspace, args)})
    else:
        args_by_worker = {
            "camera_profile": ["camera-profile", "--json"],
            "connection_rehearsal": [
                "rehearse-physical-connections",
                "--fault",
                values.get("fault", "none"),
                "--require-expected",
                "--json",
            ],
            "camera_stack": ["rehearse-b0477-stack", "--require-pass", "--json"],
            "calibration_rehearsal": ["rehearse-b0477-intrinsics", "--json"],
            "verify_v2": [
                "physical-onboard",
                "verify-v2-runtime",
                "--cell-id",
                cell_id,
                "--json",
            ],
            # Bind text to its option even when it begins with '--'. It is
            # semantic user data, never another argparse option or command.
            "plan_task": [
                "plan",
                "--device",
                values.get("device", "keyboard"),
                "--text=" + values.get("text", ""),
                "--json",
            ],
            "simulate_task": [
                "simulate",
                "--device",
                values.get("device", "keyboard"),
                "--text=" + values.get("text", ""),
                "--json",
            ],
        }
        if action.worker not in args_by_worker:
            raise ValueError("Worker has no registered diagnostic implementation")
        steps.append(
            {"name": action.worker, **_cli(workspace, args_by_worker[action.worker])}
        )
    return {
        "schema": "rocell.wizard_worker_result.v1",
        "action_id": action_id,
        "status": (
            "SUCCEEDED" if all(item["exit_code"] == 0 for item in steps) else "FAILED"
        ),
        "steps": steps,
        "device_open_count": 0,
        "serial_write_count": 0,
        "power_event_count": 0,
        "motion_command_count": 0,
        "contact_command_count": 0,
        "metadata_inventory_performed": action.worker
        in {"inventory", "native_arm_metadata"},
        "physical_authority": False,
    }


def main() -> int:
    try:
        payload = sys.stdin.buffer.read(16 * 1024 + 1)
        if len(payload) > 16 * 1024:
            raise ValueError("Request too large")

        def unique(pairs: list[tuple[str, Any]]) -> dict[str, Any]:
            result: dict[str, Any] = {}
            for key, value in pairs:
                if key in result:
                    raise ValueError("Duplicate request field")
                result[key] = value
            return result

        request = json.loads(payload, object_pairs_hook=unique)
        if type(request) is not dict or set(request) != {
            "workspace",
            "action_id",
            "input",
            "cell_id",
        }:
            raise ValueError("Invalid worker request schema")
        workspace = Path(request["workspace"]).resolve(strict=True)
        if Path(__file__).resolve().parents[4] != workspace:
            raise ValueError("Worker source is not bound to selected workspace")
        if (
            type(request["cell_id"]) is not str
            or not 1 <= len(request["cell_id"]) <= 64
        ):
            raise ValueError("Invalid cell identifier")
        result = run(
            workspace, request["action_id"], request["input"], request["cell_id"]
        )
        output = json.dumps(result, allow_nan=False, ensure_ascii=True).encode("utf-8")
        if len(output) > MAX_OUTPUT:
            raise ValueError("Result exceeded budget")
        sys.stdout.buffer.write(output)
        return 0
    except Exception as exc:
        sys.stdout.write(
            json.dumps(
                {
                    "schema": "rocell.wizard_worker_error.v1",
                    "status": "FAILED",
                    "code": "DIAGNOSTIC_WORKER_FAILED",
                    "message": str(exc)[:2000],
                    "error_type": type(exc).__name__,
                    "physical_authority": False,
                }
            )
        )
        return 1


if __name__ == "__main__":
    raise SystemExit(main())
