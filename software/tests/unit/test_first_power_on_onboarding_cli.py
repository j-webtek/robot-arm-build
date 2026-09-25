from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
import hashlib
from io import StringIO
import json
from pathlib import Path
import re
import tempfile
from typing import Any

import pytest

from rocell.cli import build_parser, main
from rocell.errors import ExitCode


WORKSPACE = Path(__file__).resolve().parents[3]
DIGEST = re.compile(r"^[0-9a-f]{64}$")

FIRST_POWER_ON_STAGES = (
    "workspace_sources",
    "static_camera_contract",
    "camera_receipt",
    "camera_identity",
    "camera_mode_controls",
    "camera_frame_freshness",
    "optics_intrinsics",
    "static_registration",
    "arm_identity",
    "power_safety",
    "power_on_observation",
    "feedback_only_connection",
    "reference_frame_calibration",
    "noncontact_acceptance",
    "physical_handoff",
)

FIRST_POWER_ON_SCENARIOS = (
    "nominal",
    "camera-receipt-mismatch",
    "camera-missing",
    "camera-wrong-identity",
    "camera-usb2",
    "camera-settings-drift",
    "camera-frame-stale",
    "camera-frame-rewrapped",
    "intrinsics-tampered",
    "camera-tag-loss",
    "arm-identity-mismatch",
    "startup-safety-blocked",
    "startup-motion-unobserved",
    "arm-timeout",
    "arm-malformed-feedback",
    "arm-disconnect",
    "arm-reset-banner",
    "arm-incomplete-feedback",
    "arm-stale-feedback",
    "calibration-stale",
    "noncontact-path-blocked",
)


def _run_json_cli(*arguments: str) -> tuple[int, dict[str, Any], str]:
    """Run one valid JSON-mode CLI request without relying on capture fixtures."""

    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(
            [
                "--workspace",
                str(WORKSPACE),
                *arguments,
                "--json",
            ]
        )
    output = stdout.getvalue()
    assert output, f"CLI emitted no JSON; stderr={stderr.getvalue()!r}"
    return exit_code, json.loads(output), stderr.getvalue()


@pytest.fixture(scope="module")
def nominal_cli_document() -> dict[str, Any]:
    exit_code, document, error = _run_json_cli(
        "rehearse-first-power-on",
        "--scenario",
        "nominal",
        "--require-expected",
    )
    assert exit_code == int(ExitCode.OK)
    assert error == ""
    return document


def _scenario_choices() -> tuple[str, ...]:
    """Read argparse's public choice values for the onboarding subcommand."""

    parser = build_parser()
    command_action = next(
        action for action in parser._actions if action.dest == "command"
    )
    onboarding_parser = command_action.choices["rehearse-first-power-on"]
    scenario_action = next(
        action for action in onboarding_parser._actions if action.dest == "scenario"
    )
    return tuple(scenario_action.choices)


def _assert_zero_authority(rehearsal: dict[str, Any]) -> None:
    assert rehearsal["authority"] == {
        "simulation_only": True,
        "hardware_accessed": False,
        "camera_enumerations": 0,
        "live_camera_frames": 0,
        "arm_port_opens": 0,
        "arm_feedback_commands": 0,
        "arm_motion_commands": 0,
        "contact_commands": 0,
        "commissioned": False,
        "safe_to_power_robot_conferred": False,
        "motion_authorized": False,
        "contact_authorized": False,
        "physical_release_effect": "NONE",
    }
    assert rehearsal["simulated_operations"]["motion_commands"] == 0
    assert rehearsal["simulated_operations"]["contact_commands"] == 0


def test_first_power_on_cli_exposes_exactly_twenty_one_scenarios() -> None:
    assert len(FIRST_POWER_ON_SCENARIOS) == 21
    assert _scenario_choices() == FIRST_POWER_ON_SCENARIOS
    assert "camera-frame-rewrapped" in _scenario_choices()


def test_first_power_on_cli_nominal_is_complete_but_has_zero_authority(
    nominal_cli_document: dict[str, Any],
) -> None:
    document = nominal_cli_document
    assert document["schema"] == "rocell.first_power_on_rehearsal_cli.v2"
    assert document["checkpoint"] is None
    assert "fake boundaries only" in document["interpretation"]

    rehearsal = document["rehearsal"]
    assert rehearsal["schema"] == "rocell.first_power_on_rehearsal.v2"
    assert rehearsal["purpose"] == (
        "ZERO_HARDWARE_FIRST_POWER_ON_PROCEDURE_REHEARSAL"
    )
    assert rehearsal["status"] == (
        "SIMULATION_WORKFLOW_COMPLETE_PHYSICAL_ONBOARDING_NOT_STARTED"
    )
    assert rehearsal["scenario"] == "nominal"
    assert rehearsal["expected_block_stage"] is None
    assert rehearsal["expected_fault_detail_code"] is None
    assert rehearsal["expected_outcome_observed"] is True
    assert rehearsal["progress"] == {
        "stage_count": 15,
        "recorded_stage_count": 15,
        "rehearsal_complete": True,
        "first_blocked_stage": None,
        "next_stage": None,
        "stopped_after": None,
        "resumed_from_checkpoint_sha256": None,
    }
    assert [record["stage"] for record in rehearsal["records"]] == list(
        FIRST_POWER_ON_STAGES
    )
    assert rehearsal["simulated_operations"] == {
        "camera_frames": 15,
        "feedback_queries": 2,
        "virtual_waypoints_executed": 109,
        "virtual_contact_attempts": 9,
        "virtual_contacts_accepted": 9,
        "virtual_observations": 9,
        "motion_commands": 0,
        "contact_commands": 0,
    }
    assert rehearsal["fault_diagnostics"] == {
        "observed_detail_code": None,
        "expected_failed_check_ids": [],
        "observed_failed_check_ids": [],
        "expected_stage_operations": None,
        "observed_stage_operations": {
            "emulated_camera_frames": 0,
            "emulated_feedback_queries": 0,
            "virtual_waypoints_executed": 0,
            "virtual_contact_attempts": 0,
            "virtual_contacts_accepted": 0,
            "virtual_observations": 0,
        },
        "stages_not_run": [],
        "cleanup_result": "NOT_APPLICABLE_NO_RESOURCE_OPENED",
        "cleanup_satisfied": True,
        "next_safe_action": rehearsal["next_safe_action"],
    }
    assert document["rehearsal_report_sha256"] == rehearsal["report_sha256"]
    assert DIGEST.fullmatch(rehearsal["report_sha256"])
    assert DIGEST.fullmatch(rehearsal["run_binding_sha256"])
    _assert_zero_authority(rehearsal)


@pytest.mark.parametrize(
    (
        "scenario",
        "blocked_stage",
        "detail_code",
        "failed_checks",
        "recorded_stages",
        "record_camera_frames",
        "record_feedback_queries",
    ),
    (
        (
            "camera-frame-rewrapped",
            "camera_frame_freshness",
            "CAMERA_FRAME_REWRAPPED",
            ["raw_frame_bytes_advanced"],
            6,
            2,
            0,
        ),
        (
            "arm-timeout",
            "feedback_only_connection",
            "ARM_FEEDBACK_TIMEOUT_BLOCKED",
            ["feedback_complete", "serial_exchange"],
            12,
            0,
            1,
        ),
    ),
    ids=("same-bytes-rewrapped-as-fresh", "feedback-timeout"),
)
def test_first_power_on_cli_fault_requires_its_exact_observable_signature(
    scenario: str,
    blocked_stage: str,
    detail_code: str,
    failed_checks: list[str],
    recorded_stages: int,
    record_camera_frames: int,
    record_feedback_queries: int,
) -> None:
    exit_code, document, error = _run_json_cli(
        "rehearse-first-power-on",
        "--scenario",
        scenario,
        "--require-expected",
    )

    assert exit_code == int(ExitCode.OK)
    assert error == ""
    rehearsal = document["rehearsal"]
    assert rehearsal["status"] == "SYNTHETIC_REHEARSAL_BLOCKED"
    assert rehearsal["expected_block_stage"] == blocked_stage
    assert rehearsal["expected_fault_detail_code"] == detail_code
    assert rehearsal["expected_outcome_observed"] is True
    assert rehearsal["progress"]["first_blocked_stage"] == blocked_stage
    assert rehearsal["progress"]["recorded_stage_count"] == recorded_stages

    blocked_record = rehearsal["records"][-1]
    assert blocked_record["stage"] == blocked_stage
    assert blocked_record["status"] == "BLOCKED"
    assert blocked_record["detail_code"] == detail_code
    assert sorted(
        check["check_id"]
        for check in blocked_record["checks"]
        if not check["passed"]
    ) == failed_checks
    assert blocked_record["evidence"]["emulated_camera_frames"] == (
        record_camera_frames
    )
    assert blocked_record["evidence"]["emulated_feedback_queries"] == (
        record_feedback_queries
    )

    diagnostics = rehearsal["fault_diagnostics"]
    assert diagnostics["observed_detail_code"] == detail_code
    assert diagnostics["expected_failed_check_ids"] == failed_checks
    assert diagnostics["observed_failed_check_ids"] == failed_checks
    expected_stage_operations = {
        "emulated_camera_frames": record_camera_frames,
        "emulated_feedback_queries": record_feedback_queries,
        "virtual_waypoints_executed": 0,
        "virtual_contact_attempts": 0,
        "virtual_contacts_accepted": 0,
        "virtual_observations": 0,
    }
    assert diagnostics["expected_stage_operations"] == expected_stage_operations
    assert diagnostics["observed_stage_operations"] == expected_stage_operations
    # The exact cleanup receipt is scenario-owned (feedback faults may close a
    # fake transport while camera faults have no opened resource).  The CLI
    # must still expose a non-empty result and an explicit Boolean verdict.
    assert isinstance(diagnostics["cleanup_result"], str)
    assert diagnostics["cleanup_result"]
    assert isinstance(diagnostics["cleanup_satisfied"], bool)
    assert diagnostics["stages_not_run"] == list(
        FIRST_POWER_ON_STAGES[recorded_stages:]
    )
    _assert_zero_authority(rehearsal)


def test_first_power_on_cli_checkpoint_binds_source_report_and_explicit_resume() -> None:
    runs = WORKSPACE / "software" / "runs"
    runs.mkdir(parents=True, exist_ok=True)
    with tempfile.TemporaryDirectory(prefix="onboarding-cli-", dir=runs) as folder:
        checkpoint = Path(folder) / "prefix.json"
        relative = checkpoint.relative_to(WORKSPACE)
        initial_exit, initial, initial_error = _run_json_cli(
            "rehearse-first-power-on",
            "--scenario",
            "nominal",
            "--stop-after",
            "camera_frame_freshness",
            "--checkpoint",
            str(relative),
            "--require-expected",
        )

        assert initial_exit == int(ExitCode.OK)
        assert initial_error == ""
        initial_rehearsal = initial["rehearsal"]
        assert initial_rehearsal["status"] == (
            "SYNTHETIC_REHEARSAL_CHECKPOINT_READY"
        )
        assert initial_rehearsal["expected_outcome_observed"] is True
        assert initial_rehearsal["progress"]["recorded_stage_count"] == 6
        assert initial_rehearsal["progress"]["next_stage"] == "optics_intrinsics"
        assert initial["checkpoint"] == {
            "path": relative.as_posix(),
            "created": True,
        }
        assert checkpoint.is_file()

        checkpoint_document = json.loads(checkpoint.read_text(encoding="utf-8"))
        checkpoint_digest = checkpoint_document["checkpoint_sha256"]
        assert DIGEST.fullmatch(checkpoint_digest)
        assert checkpoint_document["schema"] == (
            "rocell.first_power_on_checkpoint.v2"
        )
        assert checkpoint_document["workflow_schema"] == (
            "rocell.first_power_on_rehearsal.v2"
        )
        assert checkpoint_document["records"] == initial_rehearsal["records"]
        assert checkpoint_document["source_report"] == {
            "report_sha256": initial_rehearsal["report_sha256"],
            "stopped_after": "camera_frame_freshness",
            "resumed_from_checkpoint_sha256": None,
        }
        assert initial["rehearsal_report_sha256"] == (
            checkpoint_document["source_report"]["report_sha256"]
        )
        assert checkpoint_document["source_bindings"] == (
            initial_rehearsal["source_bindings"]
        )
        assert checkpoint_document["run_binding_sha256"] == (
            initial_rehearsal["run_binding_sha256"]
        )

        bindings = checkpoint_document["source_bindings"]
        bound_paths = [binding["path"] for binding in bindings]
        assert bound_paths == sorted(bound_paths)
        assert len(bound_paths) == len(set(bound_paths))
        expected_python_sources = {
            path.relative_to(WORKSPACE).as_posix()
            for path in (WORKSPACE / "software/src/rocell").rglob("*.py")
        }
        assert expected_python_sources <= set(bound_paths)
        required_inputs = {
            "software/config/camera_profiles/arducam_b0477_imx283_16mm.json",
            "software/tests/fixtures/camera/b0477_nominal_rehearsal.json",
            "hardware/static_overhead_camera/config/support_design.json",
            "active-project/RoCell_v0_3/BUILD_TRACKER.json",
        }
        assert required_inputs <= set(bound_paths)
        for binding in bindings:
            if binding["path"].startswith("@runtime/"):
                assert DIGEST.fullmatch(binding["sha256"])
                continue
            source = WORKSPACE / binding["path"]
            assert binding["sha256"] == hashlib.sha256(source.read_bytes()).hexdigest()

        resumed_exit, resumed_document, resumed_error = _run_json_cli(
            "rehearse-first-power-on",
            "--scenario",
            "nominal",
            "--resume",
            str(relative),
            "--require-expected",
        )

        assert resumed_exit == int(ExitCode.OK)
        assert resumed_error == ""
        resumed = resumed_document["rehearsal"]
        assert resumed["status"] == (
            "SIMULATION_WORKFLOW_COMPLETE_PHYSICAL_ONBOARDING_NOT_STARTED"
        )
        assert resumed["progress"]["recorded_stage_count"] == 15
        assert resumed["progress"]["resumed_from_checkpoint_sha256"] == (
            checkpoint_digest
        )
        # Resume replays and exact-compares the bound prefix; it does not trust
        # and skip the prior probes. Later records belong to this resumed run,
        # so compare the security-relevant prefix to the checkpoint itself.
        checkpoint_records = checkpoint_document["records"]
        assert resumed["records"][: len(checkpoint_records)] == checkpoint_records
        assert [record["stage"] for record in resumed["records"]] == list(
            FIRST_POWER_ON_STAGES
        )
        assert resumed["source_bindings"] == checkpoint_document[
            "source_bindings"
        ]
        _assert_zero_authority(resumed)


@pytest.mark.parametrize(
    ("require_expected", "expected_exit"),
    ((False, ExitCode.OK), (True, ExitCode.CONFIGURATION_ERROR)),
    ids=("diagnostic-mode", "require-exact-fault-observation"),
)
def test_first_power_on_cli_fault_stopped_early_is_not_an_expected_fault(
    require_expected: bool,
    expected_exit: ExitCode,
) -> None:
    arguments = [
        "rehearse-first-power-on",
        "--scenario",
        "arm-timeout",
        "--stop-after",
        "camera_receipt",
    ]
    if require_expected:
        arguments.append("--require-expected")
    exit_code, document, error = _run_json_cli(*arguments)

    assert exit_code == int(expected_exit)
    assert error == ""
    rehearsal = document["rehearsal"]
    assert rehearsal["status"] == "SYNTHETIC_REHEARSAL_CHECKPOINT_READY"
    assert rehearsal["expected_block_stage"] == "feedback_only_connection"
    assert rehearsal["expected_fault_detail_code"] == (
        "ARM_FEEDBACK_TIMEOUT_BLOCKED"
    )
    assert rehearsal["expected_outcome_observed"] is False
    assert rehearsal["progress"] == {
        "stage_count": 15,
        "recorded_stage_count": 3,
        "rehearsal_complete": False,
        "first_blocked_stage": None,
        "next_stage": "camera_identity",
        "stopped_after": "camera_receipt",
        "resumed_from_checkpoint_sha256": None,
    }
    assert rehearsal["fault_diagnostics"]["observed_detail_code"] is None
    assert rehearsal["fault_diagnostics"]["observed_failed_check_ids"] == []
    assert rehearsal["fault_diagnostics"]["expected_stage_operations"] == {
        "emulated_camera_frames": 0,
        "emulated_feedback_queries": 1,
        "virtual_waypoints_executed": 0,
        "virtual_contact_attempts": 0,
        "virtual_contacts_accepted": 0,
        "virtual_observations": 0,
    }
    assert rehearsal["fault_diagnostics"]["observed_stage_operations"] == {
        "emulated_camera_frames": 0,
        "emulated_feedback_queries": 0,
        "virtual_waypoints_executed": 0,
        "virtual_contact_attempts": 0,
        "virtual_contacts_accepted": 0,
        "virtual_observations": 0,
    }
    assert rehearsal["simulated_operations"]["feedback_queries"] == 0
    _assert_zero_authority(rehearsal)
