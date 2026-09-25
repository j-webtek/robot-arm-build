from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace
from typing import Any

import pytest

from rocell.cli import build_parser, main


def _qualification_report() -> SimpleNamespace:
    document = {
        "schema": "rocell.prehardware_qualification.v1",
        "status": "PREHARDWARE_QUALIFICATION_PASS_WITH_PHYSICAL_HOLDS",
        "profile": "quick",
        "campaign_passed": True,
        "coverage_state": "NOT_RUN",
        "all_mission_routes_accepted": False,
        "physical_ready": False,
        "case_summary": {"selected": 5, "passed": 5, "failed": 0},
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
        status=document["status"],
        profile="quick",
        campaign_passed=True,
        all_mission_routes_accepted=False,
        physical_ready=False,
        report_hash="a" * 64,
        to_dict=lambda: dict(document),
    )


def _runtime(workspace: Path, evidence_root: Path) -> SimpleNamespace:
    return SimpleNamespace(
        workspace=workspace.resolve(),
        evidence_root_path=evidence_root.resolve(),
        source_path=(workspace / "software/config/runtime.json").resolve(),
    )


def test_qualification_parser_adds_only_explicit_record_control() -> None:
    default = build_parser().parse_args(("qualify-prehardware",))
    selected = build_parser().parse_args(
        ("qualify-prehardware", "--profile", "quick", "--record", "--json")
    )

    assert default.record is False
    assert selected.record is True
    assert selected.profile == "quick"
    assert not hasattr(selected, "evidence_root")
    assert not hasattr(selected, "output")


def test_replay_qualification_parser_requires_manifest_and_is_bounded() -> None:
    parsed = build_parser().parse_args(
        (
            "replay-prehardware-qualification",
            "--manifest",
            "software/runs/qualification-test/manifest.json",
            "--runtime",
            "software/config/runtime.json",
            "--require-identical",
            "--json",
        )
    )

    assert parsed.qualification_manifest == Path(
        "software/runs/qualification-test/manifest.json"
    )
    assert parsed.runtime == Path("software/config/runtime.json")
    assert parsed.require_identical is True
    assert parsed.json is True
    assert not hasattr(parsed, "profile")
    assert not hasattr(parsed, "device")
    with pytest.raises(SystemExit):
        build_parser().parse_args(("replay-prehardware-qualification",))


def test_qualify_record_uses_runtime_evidence_root_and_reports_manifest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application as application
    import rocell.cli as cli
    import rocell.evidence as evidence

    evidence_root = tmp_path / "software/runs"
    evidence_root.mkdir(parents=True)
    report = _qualification_report()
    calls: dict[str, Any] = {}
    emitted: list[dict[str, Any]] = []

    class FakePolicy:
        def __init__(self, *, profile: str) -> None:
            self.profile = profile

    def run(
        workspace: Path,
        *,
        runtime_path: Path | None,
        policy: object,
    ) -> SimpleNamespace:
        calls["run"] = (workspace, runtime_path, policy)
        return report

    def load_runtime(
        workspace: Path,
        runtime_path: Path | None,
    ) -> SimpleNamespace:
        calls["runtime"] = (workspace, runtime_path)
        return _runtime(workspace, evidence_root)

    def record(value: object, root: Path) -> SimpleNamespace:
        calls["record"] = (value, root)
        return SimpleNamespace(
            to_dict=lambda: {
                "manifest": str(evidence_root / "qualification-a/manifest.json"),
                "recorded": True,
                "replay_supported": True,
            }
        )

    monkeypatch.setattr(application, "PrehardwareQualificationPolicy", FakePolicy)
    monkeypatch.setattr(application, "run_prehardware_qualification", run)
    monkeypatch.setattr(application, "load_runtime_policy", load_runtime)
    monkeypatch.setattr(evidence, "record_prehardware_qualification", record)
    monkeypatch.setattr(
        cli,
        "_json_dump",
        lambda document, stream=None: emitted.append(dict(document)),
    )

    exit_code = main(
        (
            "--workspace",
            str(tmp_path),
            "qualify-prehardware",
            "--profile",
            "quick",
            "--runtime",
            "software/config/runtime.json",
            "--record",
            "--require-pass",
            "--json",
        )
    )

    assert exit_code == 0
    assert calls["runtime"] == (
        tmp_path.resolve(),
        Path("software/config/runtime.json"),
    )
    assert calls["record"] == (report, evidence_root.resolve())
    assert emitted[0]["record_requested"] is True
    assert emitted[0]["evidence_record"]["recorded"] is True
    assert emitted[0]["authority"]["hardware_commands_generated"] == 0


@pytest.mark.parametrize(
    ("identical", "strict", "expected_exit"),
    ((True, True, 0), (False, True, 3), (False, False, 0)),
)
def test_replay_qualification_cli_strictness_uses_recomputed_identity_only(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    identical: bool,
    strict: bool,
    expected_exit: int,
) -> None:
    import rocell.application as application
    import rocell.cli as cli
    import rocell.evidence as evidence

    evidence_root = tmp_path / "software/runs"
    record_dir = evidence_root / "qualification-aaaaaaaaaaaaaaaaaaaaaaaa"
    record_dir.mkdir(parents=True)
    manifest = record_dir / "manifest.json"
    manifest.write_text("{}", encoding="utf-8")
    emitted: list[dict[str, Any]] = []
    calls: list[tuple[Path, Path, Path | None]] = []

    monkeypatch.setattr(
        application,
        "load_runtime_policy",
        lambda workspace, runtime_path: _runtime(workspace, evidence_root),
    )

    def replay(
        workspace: Path,
        manifest_path: Path,
        *,
        runtime_path: Path | None,
    ) -> SimpleNamespace:
        calls.append((workspace, manifest_path, runtime_path))
        return SimpleNamespace(
            status=(
                "QUALIFICATION_REPLAY_IDENTICAL"
                if identical
                else "QUALIFICATION_REPLAY_DIVERGED"
            ),
            profile="quick",
            identical=identical,
            recorded_report_sha256="a" * 64,
            recomputed_report_sha256=("a" if identical else "b") * 64,
            to_dict=lambda: {
                "schema": "rocell.prehardware_qualification_replay.v1",
                "identical": identical,
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
            },
        )

    monkeypatch.setattr(evidence, "replay_prehardware_qualification", replay)
    monkeypatch.setattr(
        cli,
        "_json_dump",
        lambda document, stream=None: emitted.append(dict(document)),
    )
    arguments = [
        "--workspace",
        str(tmp_path),
        "replay-prehardware-qualification",
        "--manifest",
        str(manifest),
        "--json",
    ]
    if strict:
        arguments.append("--require-identical")

    exit_code = main(tuple(arguments))

    assert exit_code == expected_exit
    assert calls == [
        (
            tmp_path.resolve(),
            manifest.resolve(),
            (tmp_path / "software/config/runtime.json").resolve(),
        )
    ]
    assert emitted[0]["identical"] is identical
    assert emitted[0]["authority"]["execution_authorized"] is False
    assert emitted[0]["authority"]["hardware_commands_generated"] == 0


def test_replay_qualification_manifest_must_stay_under_evidence_root(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application as application

    evidence_root = tmp_path / "software/runs"
    evidence_root.mkdir(parents=True)
    outside = tmp_path / "outside/manifest.json"
    outside.parent.mkdir()
    outside.write_text("{}", encoding="utf-8")
    monkeypatch.setattr(
        application,
        "load_runtime_policy",
        lambda workspace, runtime_path: _runtime(workspace, evidence_root),
    )

    exit_code = main(
        (
            "--workspace",
            str(tmp_path),
            "replay-prehardware-qualification",
            "--manifest",
            str(outside),
            "--json",
        )
    )

    assert exit_code == 2
