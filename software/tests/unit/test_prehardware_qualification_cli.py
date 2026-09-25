from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rocell.cli import build_parser, main


def _fake_report(*, campaign_passed: bool) -> SimpleNamespace:
    """Minimal public report surface consumed by the CLI adapter.

    Qualification execution is tested independently.  Keeping this CLI double
    tiny makes it explicit that the CLI must not inspect private runner state or
    rerun any case to decide its exit status.
    """

    status = (
        "PREHARDWARE_QUALIFICATION_PASSED_WITH_PHYSICAL_HOLDS"
        if campaign_passed
        else "PREHARDWARE_QUALIFICATION_FAILED"
    )
    document: dict[str, Any] = {
        "schema": "rocell.prehardware_qualification.v1",
        "status": status,
        "profile": "quick",
        "campaign_passed": campaign_passed,
        # Deliberately exercise the three independent readiness dimensions.
        "coverage_state": "NOT_RUN",
        "all_mission_routes_accepted": False,
        "physical_ready": False,
        "case_summary": {"total": 4, "passed": 4 if campaign_passed else 3},
        "authority": {
            "simulation_only": True,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "execution_authorized": False,
            "physical_release_effect": "NONE",
        },
        "report_sha256": "a" * 64,
    }
    return SimpleNamespace(
        status=status,
        profile="quick",
        campaign_passed=campaign_passed,
        all_mission_routes_accepted=False,
        physical_ready=False,
        report_hash="a" * 64,
        case_results=(object(), object(), object(), object()),
        to_dict=lambda: dict(document),
    )


def _patch_runner(
    monkeypatch: pytest.MonkeyPatch,
    *,
    campaign_passed: bool,
) -> tuple[list[tuple[Path, Path | None, str]], list[dict[str, Any]]]:
    import rocell.application as application
    import rocell.cli as cli

    calls: list[tuple[Path, Path | None, str]] = []
    emitted: list[dict[str, Any]] = []

    class FakePolicy:
        def __init__(self, *, profile: str) -> None:
            self.profile = profile

    def run(
        workspace: Path,
        *,
        runtime_path: Path | None = None,
        policy: object | None = None,
    ) -> SimpleNamespace:
        assert isinstance(policy, FakePolicy)
        calls.append((workspace, runtime_path, policy.profile))
        return _fake_report(campaign_passed=campaign_passed)

    monkeypatch.setattr(application, "PrehardwareQualificationPolicy", FakePolicy)
    monkeypatch.setattr(application, "run_prehardware_qualification", run)
    monkeypatch.setattr(
        cli,
        "_json_dump",
        lambda document, stream=None: emitted.append(dict(document)),
    )
    return calls, emitted


def test_qualify_prehardware_parser_uses_locked_standard_campaign_by_default() -> None:
    """The v1 CLI deliberately exposes no arbitrary case/offset controls."""

    parsed = build_parser().parse_args(("qualify-prehardware",))

    assert parsed.command == "qualify-prehardware"
    assert parsed.profile == "standard"
    assert parsed.runtime is None
    assert parsed.require_pass is False
    assert parsed.json is False
    assert not hasattr(parsed, "device")
    assert not hasattr(parsed, "text")
    assert not hasattr(parsed, "truth_offset_x_mm")
    assert not hasattr(parsed, "port")


def test_qualify_prehardware_parser_accepts_only_bounded_campaign_controls() -> None:
    parsed = build_parser().parse_args(
        (
            "qualify-prehardware",
            "--profile",
            "quick",
            "--runtime",
            "software/config/runtime.json",
            "--require-pass",
            "--json",
        )
    )

    assert parsed.command == "qualify-prehardware"
    assert parsed.profile == "quick"
    assert parsed.runtime == Path("software/config/runtime.json")
    assert parsed.require_pass is True
    assert parsed.json is True


@pytest.mark.parametrize("profile", ("", "full", "custom", "STANDARD", "../quick"))
def test_qualify_prehardware_parser_rejects_unknown_profiles(profile: str) -> None:
    with pytest.raises(SystemExit) as raised:
        build_parser().parse_args(
            ("qualify-prehardware", "--profile", profile)
        )

    assert raised.value.code == 2


def test_qualify_prehardware_json_keeps_diagnostic_route_and_physical_states_distinct(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, emitted = _patch_runner(monkeypatch, campaign_passed=True)

    exit_code = main(
        (
            "--workspace",
            str(tmp_path),
            "qualify-prehardware",
            "--profile",
            "quick",
            "--runtime",
            "software/config/runtime.json",
            "--require-pass",
            "--json",
        )
    )

    assert exit_code == 0
    assert calls == [
        (
            tmp_path.resolve(),
            Path("software/config/runtime.json"),
            "quick",
        )
    ]
    assert len(emitted) == 1
    document = emitted[0]
    assert document["schema"] == "rocell.qualify_prehardware_cli.v1"
    assert document["campaign_passed"] is True
    assert document["coverage_state"] == "NOT_RUN"
    assert document["all_mission_routes_accepted"] is False
    assert document["physical_ready"] is False
    assert document["qualification_report_hash"] == "a" * 64
    assert document["prehardware_qualification"]["profile"] == "quick"
    assert document["authority"] == {
        "simulation_only": True,
        "hardware_accessed": False,
        "hardware_commands_generated": 0,
        "live_motion_authorized": False,
        "physical_contact_authorized": False,
        "physical_release_effect": "NONE",
    }
    assert len(document["report_hash"]) == 64


def test_qualify_prehardware_require_pass_uses_campaign_result_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    _calls, emitted = _patch_runner(monkeypatch, campaign_passed=False)

    strict = main(
        (
            "--workspace",
            str(tmp_path),
            "qualify-prehardware",
            "--profile",
            "quick",
            "--require-pass",
            "--json",
        )
    )
    advisory = main(
        (
            "--workspace",
            str(tmp_path),
            "qualify-prehardware",
            "--profile",
            "quick",
            "--json",
        )
    )

    assert strict == 3
    assert advisory == 0
    assert len(emitted) == 2
    assert all(document["campaign_passed"] is False for document in emitted)
    assert all(document["physical_ready"] is False for document in emitted)


def test_qualify_prehardware_human_output_names_holds_and_zero_authority(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    _patch_runner(monkeypatch, campaign_passed=True)

    exit_code = main(
        (
            "--workspace",
            str(tmp_path),
            "qualify-prehardware",
            "--profile",
            "quick",
        )
    )

    output = capsys.readouterr().out.lower()
    assert exit_code == 0
    assert "campaign passed: true" in output
    assert "all mission routes accepted: false" in output
    assert "physical ready: false" in output
    assert "hardware commands generated: 0" in output
