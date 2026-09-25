from __future__ import annotations

import json
from pathlib import Path
from typing import Any

import pytest

import rocell.application as application
import rocell.cli as cli
from rocell.cli import build_parser, main


WORKSPACE = Path(__file__).resolve().parents[3]


class _CoverageReport:
    status = "ADAPTIVE_MISSION_COVERAGE_PASS_WITH_PHYSICAL_HOLDS"
    all_routes_accepted = True
    report_hash = "a" * 64

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.adaptive_mission_coverage.v1",
            "status": self.status,
            "summary": {
                "route_count": 75,
                "accepted_route_count": 75,
                "execution_count": 2_400,
                "capture_count": 75,
                "contact_count": 75,
                "all_routes_accepted": self.all_routes_accepted,
                "physical_ready": False,
            },
            "authority": {
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
            },
            "report_sha256": self.report_hash,
        }


class _PerturbationReport:
    status = "ADAPTIVE_PERTURBATION_CAMPAIGN_PASS_WITH_PHYSICAL_HOLDS"
    campaign_passed = True
    report_hash = "b" * 64

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "rocell.adaptive_perturbation_campaign.v1",
            "status": self.status,
            "summary": {
                "case_count": 15,
                "passed_count": 15,
                "failed_count": 0,
                "expected_rejection_count": 4,
                "total_executions": 480,
                "total_captures": 26,
                "campaign_passed": self.campaign_passed,
                "physical_ready": False,
            },
            "authority": {
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
            },
            "report_sha256": self.report_hash,
        }


def test_adaptive_diagnostic_commands_are_registered() -> None:
    parser = build_parser()
    coverage = parser.parse_args(("screen-adaptive-mission-routes",))
    stress = parser.parse_args(("stress-adaptive-session",))

    assert coverage.chunk_size == 5
    assert not coverage.require_all
    assert stress.seed == 20_260_903
    assert stress.generated_cases == 8
    assert not stress.require_pass


def test_adaptive_coverage_cli_emits_bounded_zero_authority_summary(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    emitted: list[dict[str, Any]] = []

    def fake_runner(workspace: Path, **kwargs: Any) -> _CoverageReport:
        captured["workspace"] = workspace
        captured.update(kwargs)
        return _CoverageReport()

    monkeypatch.setattr(application, "run_adaptive_mission_coverage", fake_runner)
    monkeypatch.setattr(cli, "_json_dump", lambda document: emitted.append(dict(document)))

    status = main(
        (
            "--workspace",
            str(WORKSPACE),
            "screen-adaptive-mission-routes",
            "--chunk-size",
            "7",
            "--require-all",
            "--json",
        )
    )
    document = emitted[0]

    assert status == 0
    assert captured["workspace"] == WORKSPACE.resolve()
    assert captured["policy"].orchestration_chunk_size == 7
    assert document["all_routes_accepted"] is True
    assert document["adaptive_mission_coverage"]["summary"]["route_count"] == 75
    assert document["authority"] == {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "execution_authorized": False,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "physical_release_effect": "NONE",
    }


def test_adaptive_stress_cli_binds_seed_and_expected_safe_rejections(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    emitted: list[dict[str, Any]] = []

    def fake_runner(workspace: Path, **kwargs: Any) -> _PerturbationReport:
        captured["workspace"] = workspace
        captured.update(kwargs)
        return _PerturbationReport()

    monkeypatch.setattr(application, "run_adaptive_perturbation_campaign", fake_runner)
    monkeypatch.setattr(cli, "_json_dump", lambda document: emitted.append(dict(document)))

    status = main(
        (
            "--workspace",
            str(WORKSPACE),
            "stress-adaptive-session",
            "--seed",
            "-44",
            "--generated-cases",
            "3",
            "--require-pass",
            "--json",
        )
    )
    document = emitted[0]

    assert status == 0
    assert captured["workspace"] == WORKSPACE.resolve()
    assert captured["policy"].seed == -44
    assert captured["policy"].generated_case_count == 3
    assert document["seed"] == -44
    assert document["campaign_passed"] is True
    assert (
        document["adaptive_perturbation_campaign"]["summary"]
        ["expected_rejection_count"]
        == 4
    )
    serialized = json.dumps(document, sort_keys=True)
    assert "translation_Wv_mm" not in serialized
    assert "yaw_board_rad" not in serialized


@pytest.mark.parametrize(
    ("command", "flag", "attribute"),
    (
        ("screen-adaptive-mission-routes", "--require-all", "all_routes_accepted"),
        ("stress-adaptive-session", "--require-pass", "campaign_passed"),
    ),
)
def test_adaptive_cli_require_flags_fail_closed(
    command: str,
    flag: str,
    attribute: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report: Any = _CoverageReport() if "routes" in command else _PerturbationReport()
    setattr(report, attribute, False)
    if "routes" in command:
        monkeypatch.setattr(
            application, "run_adaptive_mission_coverage", lambda *_args, **_kwargs: report
        )
    else:
        monkeypatch.setattr(
            application,
            "run_adaptive_perturbation_campaign",
            lambda *_args, **_kwargs: report,
        )
    monkeypatch.setattr(cli, "_json_dump", lambda _document: None)

    status = main(
        ("--workspace", str(WORKSPACE), command, flag, "--json")
    )
    assert status != 0
