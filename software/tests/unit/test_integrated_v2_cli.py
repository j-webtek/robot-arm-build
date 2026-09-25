"""Public CLI coverage for the zero-hardware integrated V2 mission."""

from __future__ import annotations

from contextlib import redirect_stderr, redirect_stdout
from dataclasses import dataclass
from io import StringIO
import json
from pathlib import Path
from typing import Any, Iterator, Mapping, Sequence, cast

import pytest

from rocell.application.integrated_zero_hardware_mission import (
    INTEGRATED_JOURNAL_SET_FILENAME,
)
from rocell.cli import build_parser, main
from rocell.errors import ExitCode


WORKSPACE = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class _CliResult:
    exit_code: int
    stdout: str
    stderr: str

    def stdout_json(self) -> dict[str, Any]:
        assert self.stdout
        assert self.stderr == ""
        return cast(dict[str, Any], json.loads(self.stdout))

    def stderr_json(self) -> dict[str, Any]:
        assert self.stderr
        assert self.stdout == ""
        return cast(dict[str, Any], json.loads(self.stderr))


def _invoke(*arguments: str) -> _CliResult:
    stdout = StringIO()
    stderr = StringIO()
    with redirect_stdout(stdout), redirect_stderr(stderr):
        exit_code = main(
            (
                "--workspace",
                str(WORKSPACE),
                *arguments,
                "--json",
            )
        )
    return _CliResult(exit_code, stdout.getvalue(), stderr.getvalue())


def _all_mappings(value: object) -> Iterator[Mapping[str, object]]:
    if isinstance(value, Mapping):
        document = cast(Mapping[str, object], value)
        yield document
        for child in document.values():
            yield from _all_mappings(child)
    elif isinstance(value, Sequence) and not isinstance(value, (str, bytes)):
        for child in value:
            yield from _all_mappings(child)


def _assert_zero_authority(value: object) -> None:
    expected = {
        "simulation_only": True,
        "physical_authority": "ZERO",
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "wire_messages_generated": 0,
        "power_authorized": False,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "can_release_physical_gates": False,
        "physical_release_effect": "NONE",
    }
    seen: set[str] = set()
    for document in _all_mappings(value):
        for key, expected_value in expected.items():
            if key in document:
                seen.add(key)
                assert document[key] == expected_value
    assert seen == set(expected)


def test_integrated_v2_parser_defaults_are_explicit_and_nonphysical() -> None:
    parsed = build_parser().parse_args(
        (
            "simulate-integrated-v2",
            "--device",
            "keyboard",
            "--text",
            "test",
            "--journal-root",
            "journals/mission-v2",
        )
    )

    assert parsed.command == "simulate-integrated-v2"
    assert parsed.device == "keyboard"
    assert parsed.text == "test"
    assert parsed.journal_root == Path("journals/mission-v2")
    assert parsed.open_existing is False
    assert parsed.fault_kind == "none"
    assert parsed.fault_command_ordinal is None
    assert parsed.camera_fault_kind == "none"
    assert parsed.camera_fault_contact_ordinal is None
    assert parsed.require_pass is False
    assert parsed.json is False
    assert not hasattr(parsed, "port")


@pytest.mark.parametrize(
    ("fault_arguments", "expected_code"),
    (
        (
            ("--fault-command-ordinal", "0"),
            "INTEGRATED_V2_FAULT_KIND_REQUIRED",
        ),
        (
            ("--fault-kind", "stall"),
            "INTEGRATED_V2_FAULT_ORDINAL_REQUIRED",
        ),
        (
            ("--camera-fault-contact-ordinal", "0"),
            "INTEGRATED_V2_CAMERA_FAULT_KIND_REQUIRED",
        ),
        (
            ("--camera-fault-kind", "stale-frame"),
            "INTEGRATED_V2_CAMERA_FAULT_ORDINAL_REQUIRED",
        ),
    ),
)
def test_integrated_v2_fault_kind_and_ordinal_must_be_paired(
    tmp_path: Path,
    fault_arguments: tuple[str, ...],
    expected_code: str,
) -> None:
    journal_root = tmp_path / expected_code.lower()
    result = _invoke(
        "simulate-integrated-v2",
        "--device",
        "keyboard",
        "--text",
        "test",
        "--journal-root",
        str(journal_root),
        *fault_arguments,
    )

    assert result.exit_code == int(ExitCode.USAGE_ERROR)
    error = result.stderr_json()["error"]
    assert error["code"] == expected_code
    assert not journal_root.exists()


@pytest.fixture(scope="module")
def successful_keyboard_cli(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, _CliResult]:
    journal_root = tmp_path_factory.mktemp("integrated-v2-cli") / "keyboard"
    result = _invoke(
        "simulate-integrated-v2",
        "--device",
        "keyboard",
        "--text",
        "test",
        "--journal-root",
        str(journal_root),
        "--require-pass",
    )
    return journal_root, result


def test_integrated_v2_keyboard_json_runs_complete_zero_authority_mission(
    successful_keyboard_cli: tuple[Path, _CliResult],
) -> None:
    journal_root, result = successful_keyboard_cli
    assert result.exit_code == int(ExitCode.OK)
    document = result.stdout_json()

    assert document["schema"] == "rocell.integrated_zero_hardware_mission_cli.v1"
    assert document["completed"] is True
    assert document["status"] == (
        "ZERO_HARDWARE_MISSION_V2_COMPLETE_WITH_PHYSICAL_HOLDS"
    )
    assert document["opened_existing_journals"] is False
    assert document["journal_root"] == str(journal_root.resolve())
    assert document["fault_injection"] == {
        "controller": {"kind": "none", "command_ordinal": None},
        "camera": {
            "kind": "none",
            "contact_occurrence_ordinal": None,
        },
    }
    assert document["assembly"] == {
        "assembly_sha256": document["assembly"]["assembly_sha256"],
        "source_action_plan_sha256": document["assembly"][
            "source_action_plan_sha256"
        ],
        "semantic_step_count": 4,
        "observation_only_step_count": 0,
        "contact_count": 4,
        "route_waypoint_count": 48,
        "command_count": 47,
        "physical_clearance_established": False,
    }

    report = document["report"]
    assert report["completed"] is True
    assert report["fault_detail"] is None
    assert report["execution"]["command_count"] == 47
    assert report["execution"]["camera_observation_count"] == 4
    assert report["execution"]["state_observation_count"] == 0
    assert report["execution"]["contact_count"] == 4
    assert report["outcome"]["matches"] is True
    assert report["outcome"]["expected_length"] == 4
    assert report["outcome"]["observed_length"] == 4
    assert report["controller_final_state"]["terminal"] is True
    assert report["controller_final_state"]["completed_command_count"] == 47
    assert all(item["current_state"] == "PARKED" for item in report["journals"])
    assert (journal_root / INTEGRATED_JOURNAL_SET_FILENAME).is_file()
    _assert_zero_authority(document)


@pytest.fixture(scope="module")
def faulted_keyboard_cli(
    tmp_path_factory: pytest.TempPathFactory,
) -> tuple[Path, _CliResult]:
    journal_root = tmp_path_factory.mktemp("integrated-v2-cli-fault") / "keyboard"
    result = _invoke(
        "simulate-integrated-v2",
        "--device",
        "keyboard",
        "--text",
        "test",
        "--journal-root",
        str(journal_root),
        "--fault-kind",
        "stall",
        "--fault-command-ordinal",
        "0",
        "--require-pass",
    )
    return journal_root, result


def test_integrated_v2_require_pass_returns_nonzero_for_runtime_fault(
    faulted_keyboard_cli: tuple[Path, _CliResult],
) -> None:
    journal_root, result = faulted_keyboard_cli
    assert result.exit_code == int(ExitCode.CONFIGURATION_ERROR)
    document = result.stdout_json()

    assert document["completed"] is False
    assert document["status"] == "ZERO_HARDWARE_MISSION_V2_FAULTED_CLOSED"
    assert document["fault_injection"] == {
        "controller": {"kind": "stall", "command_ordinal": 0},
        "camera": {
            "kind": "none",
            "contact_occurrence_ordinal": None,
        },
    }
    report = document["report"]
    assert report["fault_detail"] is not None
    assert "STALL" in report["fault_detail"]
    assert report["execution"]["command_count"] == 1
    assert report["execution"]["camera_observation_count"] == 0
    assert report["execution"]["contact_count"] == 0
    assert report["outcome"]["matches"] is False
    assert report["controller_final_state"]["fault_latched"] == "STALL"
    assert report["controller_final_state"]["attempted_command_count"] == 1
    assert report["controller_final_state"]["completed_command_count"] == 0
    assert all(item["current_state"] == "FAULTED" for item in report["journals"])
    assert (journal_root / INTEGRATED_JOURNAL_SET_FILENAME).is_file()
    _assert_zero_authority(document)


def test_integrated_v2_camera_fault_is_structured_and_stops_before_approach(
    tmp_path: Path,
) -> None:
    journal_root = tmp_path / "camera-fault"
    result = _invoke(
        "simulate-integrated-v2",
        "--device",
        "keyboard",
        "--text",
        "test",
        "--journal-root",
        str(journal_root),
        "--camera-fault-kind",
        "stale-frame",
        "--camera-fault-contact-ordinal",
        "0",
        "--require-pass",
    )

    assert result.exit_code == int(ExitCode.CONFIGURATION_ERROR)
    document = result.stdout_json()
    assert document["fault_injection"] == {
        "controller": {"kind": "none", "command_ordinal": None},
        "camera": {
            "kind": "stale-frame",
            "contact_occurrence_ordinal": 0,
        },
    }
    report = document["report"]
    assert report["completed"] is False
    assert report["execution"]["camera_observation_count"] == 0
    assert report["execution"]["contact_count"] == 0
    assert report["execution"]["command_receipts"][-1]["phase"] == "HOVER"
    assert (
        report["fault_receipt"]["source_class"]
        == "SettledHoverObservationBoundary"
    )
    assert report["fault_receipt"]["stage"] == "SETTLED_HOVER_OBSERVATION"
    assert (
        report["fault_receipt"]["fault_kind"]
        == "OBSERVATION_BOUNDARY_FAILURE"
    )
    assert (
        report["fault_receipt"]["camera_fault_receipt_is_causal_evidence"]
        is False
    )
    assert report["fault_receipt"]["camera_fault_receipt"][
        "fault_kind"
    ] == "STALE_FRAME"
    assert report["fault_receipt"]["camera_fault_receipt"][
        "observation_yielded"
    ] is False
    assert report["fault_detail_is_descriptive_only"] is True
    _assert_zero_authority(document)


def test_integrated_v2_open_existing_refuses_automatic_completed_mission_retry(
    successful_keyboard_cli: tuple[Path, _CliResult],
) -> None:
    journal_root, initial_result = successful_keyboard_cli
    assert initial_result.exit_code == int(ExitCode.OK)
    files_before = {
        path.relative_to(journal_root).as_posix(): path.read_bytes()
        for path in journal_root.rglob("*")
        if path.is_file()
    }

    reopened = _invoke(
        "simulate-integrated-v2",
        "--device",
        "keyboard",
        "--text",
        "test",
        "--journal-root",
        str(journal_root),
        "--open-existing",
        "--require-pass",
    )

    assert reopened.exit_code == int(ExitCode.CONFIGURATION_ERROR)
    error = reopened.stderr_json()["error"]
    assert error["code"] == "INTEGRATED_V2_REHEARSAL_INVALID"
    assert "automatic integrated restart is refused" in error["message"]
    assert error["details"]["journal_root"] == str(journal_root.resolve())
    assert error["details"]["open_existing"] is True
    files_after = {
        path.relative_to(journal_root).as_posix(): path.read_bytes()
        for path in journal_root.rglob("*")
        if path.is_file()
    }
    assert files_after == files_before
