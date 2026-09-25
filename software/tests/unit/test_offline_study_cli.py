from __future__ import annotations

import argparse
from pathlib import Path
from types import SimpleNamespace

import pytest

from rocell.cli import build_parser, main


WORKSPACE_ROOT = Path(__file__).resolve().parents[3]


FREEZE005_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-005"
FREEZE006_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-006"
FREEZE007_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-007"
FREEZE008_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-008"
FREEZE009_ID = "ROCELL-PHASE0-RC03-INT-R1-FREEZE-009"
FREEZE_ID = FREEZE009_ID
DOCUMENTED_STUDY_ID = "reach-00ed8c5820df03c7"
DOCUMENTED_REPORT_HASH = (
    "335275e2a68aa2cda82163fedfe93c17daccdd65d87e07ab03359fafc738fc00"
)


def _fake_trajectory(*, passed: bool = False) -> SimpleNamespace:
    final_round = SimpleNamespace(
        all_waypoints_accepted=passed,
        joint_results=(object(),),
        waypoints=(object(), object()),
    )
    return SimpleNamespace(
        status="DISCRETE_SEQUENTIAL_IK_WAYPOINT_DIAGNOSTIC_GAPS_REPORTED",
        report_hash="a" * 64,
        final_round=final_round,
        total_ik_solves=1,
        termination_reason="UNIT_TEST_STOP",
        to_dict=lambda: {
            "schema": "rocell.discrete_sequential_ik_waypoint_simulation.v1",
            "simulation_only": True,
        },
    )


def _patch_trajectory_dependencies(
    monkeypatch: pytest.MonkeyPatch,
    *,
    refresh_report: object | None = None,
    passed: bool = False,
    manifest_id: str = FREEZE_ID,
) -> tuple[dict[str, int], list[dict[str, object]]]:
    import rocell.application as application
    import rocell.cli as cli

    calls = {"default_inputs": 0, "refresh": 0, "trajectory": 0}
    emitted: list[dict[str, object]] = []
    context = SimpleNamespace(snapshot=SimpleNamespace(manifest_id=manifest_id))
    study = SimpleNamespace(study_input_id=DOCUMENTED_STUDY_ID)

    def default_inputs(_context: object) -> tuple[object, ...]:
        calls["default_inputs"] += 1
        return (study,)

    def refresh(_context: object) -> object:
        calls["refresh"] += 1
        if refresh_report is None:
            raise AssertionError("reach optimizer was not expected")
        return refresh_report

    def trajectory(*_args: object, **_kwargs: object) -> SimpleNamespace:
        calls["trajectory"] += 1
        return _fake_trajectory(passed=passed)

    monkeypatch.setattr(application, "load_simulation_context", lambda *_: context)
    monkeypatch.setattr(application, "default_reach_study_inputs", default_inputs)
    monkeypatch.setattr(application, "run_reach_optimization", refresh)
    monkeypatch.setattr(
        application,
        "run_park_optimization",
        lambda _context: (_ for _ in ()).throw(
            AssertionError("park optimizer was not expected")
        ),
    )
    monkeypatch.setattr(application, "run_trajectory_simulation", trajectory)
    monkeypatch.setattr(
        cli,
        "_json_dump",
        lambda document, stream=None: emitted.append(dict(document)),
    )
    return calls, emitted


def test_reach_layout_cli_is_explicitly_bounded_and_optional_strict() -> None:
    parser = build_parser()
    parsed = parser.parse_args(("optimize-layout", "--require-complete", "--json"))

    assert isinstance(parsed, argparse.Namespace)
    assert parsed.command == "optimize-layout"
    assert parsed.require_complete is True
    assert parsed.json is True


def test_reach_layout_cli_help_states_contact_and_park_scope(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(("optimize-layout", "--help"))

    captured = capsys.readouterr()
    assert raised.value.code == 0
    assert "contact-and-park" in captured.out
    assert "--require-complete" in captured.out


def test_park_cli_is_bounded_and_optionally_strict() -> None:
    parser = build_parser()
    parsed = parser.parse_args(
        ("optimize-park", "--require-both-routes", "--json")
    )

    assert parsed.command == "optimize-park"
    assert parsed.require_both_routes is True
    assert parsed.json is True


def test_park_cli_help_states_independent_pose_scope_and_zero_authority(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(("optimize-park", "--help"))

    captured = capsys.readouterr()
    normalized_help = " ".join(captured.out.split())
    assert raised.value.code == 0
    assert "independent pose IK only" in normalized_help
    assert "never authorizes motion" in normalized_help


def test_broader_layout_and_mission_coverage_cli_contracts_are_explicit() -> None:
    parser = build_parser()
    layout = parser.parse_args(
        ("study-layout-hypotheses", "--require-promotable", "--json")
    )
    mission = parser.parse_args(
        (
            "screen-mission-routes",
            "--from-layout-study-rank",
            "2",
            "--require-all",
            "--json",
        )
    )
    collision = parser.parse_args(
        ("collision-status", "--require-diagnostic-ready", "--json")
    )

    assert layout.command == "study-layout-hypotheses"
    assert layout.require_promotable is True
    assert mission.command == "screen-mission-routes"
    assert mission.from_layout_study_rank == 2
    assert mission.require_all is True
    assert collision.command == "collision-status"
    assert collision.require_diagnostic_ready is True


def test_mission_coverage_cli_defaults_to_bound_documented_placement_and_park(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application as application
    import rocell.cli as cli

    study = SimpleNamespace(study_input_id=DOCUMENTED_STUDY_ID)
    context = SimpleNamespace(snapshot=SimpleNamespace(manifest_id=FREEZE_ID))
    point = SimpleNamespace(x=290.0, y=10.0, z=70.0)
    best_park = SimpleNamespace(
        all_routes_accepted=True,
        geometry=SimpleNamespace(candidate_id="park-test", point_board=point),
    )
    park_report = SimpleNamespace(
        best_candidate=best_park,
        selected_study_input=study,
        report_hash="b" * 64,
    )
    routes = (SimpleNamespace(accepted=True), SimpleNamespace(accepted=False))
    coverage = SimpleNamespace(
        status="MISSION_ROUTE_COVERAGE_DIAGNOSTIC_GAPS_REPORTED",
        report_hash="c" * 64,
        study_input=study,
        park_xy_board_mm=(290.0, 10.0),
        routes=routes,
        all_routes_accepted=False,
        total_ik_solves=22,
        total_task_jacobian_fk_evaluations=220,
        to_dict=lambda: {
            "schema": "rocell.independent_mission_route_coverage.v1",
            "device_summary": {
                "keyboard": {"accepted_route_count": 1},
                "phone": {"accepted_route_count": 0},
            },
        },
    )
    observed: dict[str, object] = {}
    emitted: dict[str, object] = {}
    monkeypatch.setattr(application, "load_simulation_context", lambda *_: context)
    monkeypatch.setattr(
        application, "default_reach_study_inputs", lambda _: (study,)
    )
    monkeypatch.setattr(application, "run_park_optimization", lambda _: park_report)
    monkeypatch.setattr(
        application,
        "run_prehardware_layout_study",
        lambda _: (_ for _ in ()).throw(
            AssertionError("broader layout study was not requested")
        ),
    )

    def run_coverage(
        candidate_context: object,
        candidate_study: object,
        park_xy: tuple[float, float],
    ) -> object:
        observed.update(
            context=candidate_context,
            study=candidate_study,
            park_xy=park_xy,
        )
        return coverage

    monkeypatch.setattr(application, "run_mission_route_coverage", run_coverage)
    monkeypatch.setattr(
        cli,
        "_json_dump",
        lambda document, stream=None: emitted.update(document),
    )

    exit_code = main(
        (
            "--workspace",
            str(tmp_path),
            "screen-mission-routes",
            "--require-all",
            "--json",
        )
    )

    assert exit_code == 3
    assert emitted["schema"] == "rocell.mission_route_coverage_cli.v1"
    assert emitted["execution_authorized"] is False
    assert emitted["contact_authorized"] is False
    assert emitted["selection"]["source"] == (
        "DOCUMENTED_FREEZE_PLACEMENT_AND_BOUNDED_PARK"
    )
    assert emitted["selection"]["park_xy_board_mm"] == [290.0, 10.0]
    assert observed == {
        "context": context,
        "study": study,
        "park_xy": (290.0, 10.0),
    }


def test_mission_coverage_cli_consumes_only_a_promoted_layout_candidate(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application as application
    import rocell.cli as cli

    context = SimpleNamespace(snapshot=SimpleNamespace(manifest_id=FREEZE_ID))
    study = SimpleNamespace(study_input_id="broader-study-test")
    point = SimpleNamespace(x=111.0, y=22.0, z=70.0)
    park = SimpleNamespace(park_id="park-probe-test", point_board=point)
    promotion = SimpleNamespace(
        rank=1,
        study_input=study,
        full_catalog_screen=SimpleNamespace(selected_park_probe=park),
    )
    layout_report = SimpleNamespace(
        promoted_candidates=(promotion,),
        report_hash="d" * 64,
    )
    coverage = SimpleNamespace(
        status="MISSION_ROUTE_COVERAGE_DIAGNOSTIC_PASS_WITH_UNSUPPORTED_CHECKS",
        report_hash="e" * 64,
        study_input=study,
        park_xy_board_mm=(111.0, 22.0),
        routes=(SimpleNamespace(accepted=True),),
        all_routes_accepted=True,
        total_ik_solves=10,
        total_task_jacobian_fk_evaluations=100,
        to_dict=lambda: {
            "device_summary": {
                "keyboard": {"accepted_route_count": 46},
                "phone": {"accepted_route_count": 29},
            }
        },
    )
    emitted: dict[str, object] = {}
    monkeypatch.setattr(application, "load_simulation_context", lambda *_: context)
    monkeypatch.setattr(
        application, "run_prehardware_layout_study", lambda _: layout_report
    )
    monkeypatch.setattr(
        application,
        "run_park_optimization",
        lambda _: (_ for _ in ()).throw(
            AssertionError("frozen park path should not run for a promotion")
        ),
    )
    monkeypatch.setattr(
        application,
        "run_mission_route_coverage",
        lambda candidate_context, candidate_study, park_xy: coverage,
    )
    monkeypatch.setattr(
        cli,
        "_json_dump",
        lambda document, stream=None: emitted.update(document),
    )

    exit_code = main(
        (
            "--workspace",
            str(tmp_path),
            "screen-mission-routes",
            "--from-layout-study-rank",
            "1",
            "--require-all",
            "--json",
        )
    )

    assert exit_code == 0
    selection = emitted["selection"]
    assert selection["source"] == "PROMOTED_PREHARDWARE_LAYOUT_STUDY"
    assert selection["study_input_id"] == "broader-study-test"
    assert selection["park_probe_id"] == "park-probe-test"
    assert selection["park_xy_board_mm"] == [111.0, 22.0]


def test_mission_coverage_cli_rejects_selection_coverage_drift(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    import rocell.application as application

    study = SimpleNamespace(study_input_id=DOCUMENTED_STUDY_ID)
    context = SimpleNamespace(snapshot=SimpleNamespace(manifest_id=FREEZE_ID))
    point = SimpleNamespace(x=290.0, y=10.0, z=70.0)
    park_report = SimpleNamespace(
        best_candidate=SimpleNamespace(
            all_routes_accepted=True,
            geometry=SimpleNamespace(candidate_id="park-test", point_board=point),
        ),
        selected_study_input=study,
        report_hash="b" * 64,
    )
    drifted_coverage = SimpleNamespace(
        study_input=SimpleNamespace(study_input_id="different-study"),
        park_xy_board_mm=(290.0, 10.0),
    )
    monkeypatch.setattr(application, "load_simulation_context", lambda *_: context)
    monkeypatch.setattr(
        application, "default_reach_study_inputs", lambda _: (study,)
    )
    monkeypatch.setattr(application, "run_park_optimization", lambda _: park_report)
    monkeypatch.setattr(
        application,
        "run_mission_route_coverage",
        lambda candidate_context, candidate_study, park_xy: drifted_coverage,
    )

    exit_code = main(
        (
            "--workspace",
            str(tmp_path),
            "screen-mission-routes",
        )
    )

    assert exit_code == 3
    assert "MISSION_ROUTE_COVERAGE_FAILED" in capsys.readouterr().err


def test_collision_status_cli_reports_blockers_and_optional_strict_failure(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application as application
    import rocell.cli as cli

    context = object()
    audit = SimpleNamespace(
        required_body_count=19,
        bound_body_count=19,
        diagnostic_ready=False,
    )
    report = SimpleNamespace(
        status="COLLISION_DIAGNOSTIC_BLOCKED_REQUIRED_GEOMETRY_INCOMPLETE",
        report_hash="f" * 64,
        geometry_audit=audit,
        missing_required_body_ids=tuple(f"missing-{index}" for index in range(7)),
        unknown_required_body_ids=tuple(f"unknown-{index}" for index in range(6)),
        to_dict=lambda: {
            "schema": "rocell.current_collision_readiness.v1",
            "authority": {
                "hardware_commands_generated": 0,
                "can_release_physical_gates": False,
            },
        },
    )
    emitted: dict[str, object] = {}
    monkeypatch.setattr(application, "load_simulation_context", lambda *_: context)
    monkeypatch.setattr(
        application, "assess_current_collision_readiness", lambda _: report
    )
    monkeypatch.setattr(
        cli,
        "_json_dump",
        lambda document, stream=None: emitted.update(document),
    )

    exit_code = main(
        (
            "--workspace",
            str(tmp_path),
            "collision-status",
            "--require-diagnostic-ready",
            "--json",
        )
    )

    assert exit_code == 3
    assert emitted["schema"] == "rocell.current_collision_readiness.v1"
    assert emitted["report_hash"] == "f" * 64
    assert emitted["authority"]["can_release_physical_gates"] is False


def test_trajectory_cli_exposes_bounded_route_and_strict_exit_policy() -> None:
    parser = build_parser()
    parsed = parser.parse_args(
        (
            "simulate-trajectory",
            "--device",
            "keyboard",
            "--text",
            "ab",
            "--placement-rank",
            "2",
            "--refresh-placement-ranking",
            "--maximum-route-targets",
            "4",
            "--require-pass",
            "--json",
        )
    )

    assert parsed.command == "simulate-trajectory"
    assert parsed.placement_rank == 2
    assert parsed.refresh_placement_ranking is True
    assert parsed.maximum_route_targets == 4
    assert parsed.require_pass is True


def test_trajectory_cli_help_states_phases_and_zero_hardware_authority(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(("simulate-trajectory", "--help"))

    captured = capsys.readouterr()
    normalized_help = " ".join(captured.out.split())
    assert raised.value.code == 0
    assert "park/transit/hover/approach/contact/retract" in captured.out
    assert "deltas between sampled IK waypoints" in normalized_help
    assert "joint continuity" not in captured.out.lower()
    assert "never authorizes hardware" in captured.out.lower()


@pytest.mark.parametrize(
    "manifest_id",
    (FREEZE005_ID, FREEZE006_ID, FREEZE007_ID, FREEZE008_ID, FREEZE009_ID),
)
def test_trajectory_cli_fast_replays_freeze_bound_selection_without_reranking(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    manifest_id: str,
) -> None:
    calls, emitted = _patch_trajectory_dependencies(
        monkeypatch,
        manifest_id=manifest_id,
    )

    exit_code = main(
        (
            "--workspace",
            str(tmp_path),
            "simulate-trajectory",
            "--device",
            "keyboard",
            "--text",
            "a",
            "--json",
        )
    )
    document = emitted[0]

    assert exit_code == 0
    assert calls == {"default_inputs": 1, "refresh": 0, "trajectory": 1}
    selection = document["placement_selection"]
    assert selection["source"] == "DOCUMENTED_FREEZE_BOUND_REACH_RESULT"
    assert selection["study_input_id"] == DOCUMENTED_STUDY_ID
    assert selection["reach_report_hash"] == DOCUMENTED_REPORT_HASH
    assert selection["reach_mission_complete"] is False


def test_trajectory_cli_rejects_undocumented_future_freeze(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    calls, emitted = _patch_trajectory_dependencies(
        monkeypatch,
        manifest_id="ROCELL-PHASE0-RC03-INT-R1-FREEZE-999",
    )

    exit_code = main(
        (
            "--workspace",
            str(tmp_path),
            "simulate-trajectory",
            "--device",
            "keyboard",
            "--text",
            "a",
            "--json",
        )
    )

    assert exit_code == 2
    assert calls == {"default_inputs": 0, "refresh": 0, "trajectory": 0}
    assert emitted == [
        {
            "schema": "rocell.error.v1",
            "error": {
                "code": "PLACEMENT_SELECTION_REQUIRED",
                "message": (
                    "No documented placement exists for this freeze; provide "
                    "--study-input-id or --refresh-placement-ranking"
                ),
            },
        }
    ]


def test_trajectory_cli_refresh_uses_fresh_rank_and_not_default_grid(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = SimpleNamespace(
        rank=1,
        study_input_id="reach-first",
        mission_complete=False,
        park_id="park-00",
    )
    second = SimpleNamespace(
        rank=2,
        study_input_id=DOCUMENTED_STUDY_ID,
        mission_complete=False,
        park_id="park-00",
    )
    study = SimpleNamespace(study_input_id=DOCUMENTED_STUDY_ID)
    refresh_report = SimpleNamespace(
        ranked_candidates=(first, second),
        full_evaluations=(SimpleNamespace(study_input=study),),
        report_hash="b" * 64,
        status="CONTACT_AND_PARK_DIAGNOSTIC_NO_COMPLETE_FINALIST",
    )
    calls, emitted = _patch_trajectory_dependencies(
        monkeypatch,
        refresh_report=refresh_report,
    )

    exit_code = main(
        (
            "--workspace",
            str(tmp_path),
            "simulate-trajectory",
            "--device",
            "phone",
            "--text",
            "a",
            "--placement-rank",
            "2",
            "--refresh-placement-ranking",
            "--json",
        )
    )
    document = emitted[0]

    assert exit_code == 0
    assert calls == {"default_inputs": 0, "refresh": 1, "trajectory": 1}
    selection = document["placement_selection"]
    assert selection["source"] == "FRESH_BOUNDED_REACH_OPTIMIZATION"
    assert selection["rank"] == 2
    assert selection["reach_report_hash"] == "b" * 64


def test_trajectory_cli_can_use_verified_optimized_park_overlay(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application as application

    calls, emitted = _patch_trajectory_dependencies(monkeypatch)
    point = SimpleNamespace(x=123.0, y=45.0, z=210.0)
    best = SimpleNamespace(
        geometry=SimpleNamespace(candidate_id="park-test", point_board=point),
        accepted_route_count=2,
        all_routes_accepted=True,
        minimum_normalized_arm_joint_margin=0.2,
    )
    report = SimpleNamespace(
        best_candidate=best,
        selected_study_input=SimpleNamespace(study_input_id=DOCUMENTED_STUDY_ID),
        report_hash="f" * 64,
        status="PARK_POSE_DIAGNOSTIC_COMPLETE_CANDIDATE_FOUND",
    )
    monkeypatch.setattr(application, "run_park_optimization", lambda _: report)

    exit_code = main(
        (
            "--workspace",
            str(tmp_path),
            "simulate-trajectory",
            "--device",
            "keyboard",
            "--text",
            "a",
            "--use-optimized-park",
            "--json",
        )
    )

    assert exit_code == 0
    assert calls["trajectory"] == 1
    selection = emitted[0]["park_selection"]
    assert selection["source"] == "FREEZE_BOUND_BOUNDED_PARK_OPTIMIZATION"
    assert selection["point_board_mm"] == [123.0, 45.0, 210.0]
    assert selection["park_report_hash"] == "f" * 64
    assert selection["canonical_context_modified"] is False


def test_trajectory_cli_usage_and_optional_strict_exit_codes(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    capsys: pytest.CaptureFixture[str],
) -> None:
    calls, _ = _patch_trajectory_dependencies(monkeypatch)
    base = (
        "--workspace",
        str(tmp_path),
        "simulate-trajectory",
        "--device",
        "keyboard",
        "--text",
        "a",
    )

    assert main((*base, "--placement-rank", "2")) == 2
    assert "PLACEMENT_RANK_REQUIRES_REFRESH" in capsys.readouterr().err
    assert calls["trajectory"] == 0

    assert main((*base, "--park-x-mm", "10")) == 2
    assert "TRAJECTORY_PARK_PAIR_REQUIRED" in capsys.readouterr().err
    assert calls["trajectory"] == 0

    assert (
        main(
            (
                *base,
                "--park-x-mm",
                "10",
                "--park-y-mm",
                "20",
                "--use-optimized-park",
            )
        )
        == 2
    )
    assert "TRAJECTORY_PARK_SOURCE_CONFLICT" in capsys.readouterr().err
    assert calls["trajectory"] == 0

    assert main((*base, "--require-pass")) == 3
    capsys.readouterr()
    assert calls["trajectory"] == 1


def test_eye_on_arm_fk_cli_requires_exact_dataset_and_evidence_hashes() -> None:
    parser = build_parser()
    parsed = parser.parse_args(
        (
            "verify-eye-on-arm-fk-offline",
            "--dataset",
            "capture.json",
            "--dataset-sha256",
            "a" * 64,
            "--evidence",
            "raw-feedback.json",
            "--evidence-sha256",
            "b" * 64,
            "--require-pass",
            "--json",
        )
    )

    assert parsed.command == "verify-eye-on-arm-fk-offline"
    assert parsed.dataset_sha256 == "a" * 64
    assert parsed.evidence_sha256 == "b" * 64
    assert parsed.require_pass is True


def test_eye_on_arm_fk_cli_help_states_raw_feedback_and_zero_hardware(
    capsys: pytest.CaptureFixture[str],
) -> None:
    with pytest.raises(SystemExit) as raised:
        main(("verify-eye-on-arm-fk-offline", "--help"))

    captured = capsys.readouterr()
    assert raised.value.code == 0
    normalized_help = " ".join(captured.out.split())
    assert "raw T=1051 evidence" in normalized_help
    assert "no hardware or artifact writes" in normalized_help.lower()


def test_eye_on_arm_fk_cli_binds_verified_context_and_remains_zero_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application as application
    import rocell.calibration as calibration
    import rocell.cli as cli

    model_hash = "c" * 64
    context = SimpleNamespace(
        snapshot=SimpleNamespace(
            manifest_id="TEST-FREEZE-005",
            active_build_id="TEST-BUILD-A",
            snapshot_hash="d" * 64,
        ),
        bundle_lock=SimpleNamespace(bundle_id="TEST-BUNDLE-005"),
        scenario=SimpleNamespace(
            model_sha256=model_hash,
            model_path=WORKSPACE_ROOT / "software" / "models" / "test.urdf",
        ),
    )
    dataset = object()
    evidence = SimpleNamespace(
        manifest_id="TEST-FREEZE-005",
        active_build_id="TEST-BUILD-A",
        kinematic_model_sha256=model_hash,
    )
    report = SimpleNamespace(
        status="PASS",
        dataset_id="dataset-001",
        evidence_id="evidence-001",
        samples=(object(), object()),
        kinematic_model_sha256=model_hash,
        report_hash="e" * 64,
        all_passed=True,
        to_dict=lambda: {
            "schema": "rocell.eye_on_arm_fk_verification.v1",
            "status": "PASS",
            "physical_release_effect": "NONE",
        },
    )
    observed: dict[str, object] = {}
    emitted: dict[str, object] = {}

    monkeypatch.setattr(
        application,
        "load_simulation_context",
        lambda workspace, manifest: context,
    )
    monkeypatch.setattr(
        calibration,
        "load_eye_on_arm_dataset",
        lambda path, *, expected_file_sha256: (
            observed.update(dataset_hash=expected_file_sha256) or dataset
        ),
    )
    monkeypatch.setattr(
        calibration,
        "load_eye_on_arm_capture_evidence",
        lambda path, *, expected_file_sha256: (
            observed.update(evidence_hash=expected_file_sha256) or evidence
        ),
    )

    def fake_verify(
        candidate_dataset: object,
        candidate_evidence: object,
        model_path: Path,
    ) -> object:
        observed["dataset"] = candidate_dataset
        observed["evidence"] = candidate_evidence
        observed["model_path"] = model_path
        return report

    monkeypatch.setattr(calibration, "verify_eye_on_arm_fk", fake_verify)
    monkeypatch.setattr(
        cli,
        "_json_dump",
        lambda document, stream=None: emitted.update(document),
    )

    exit_code = main(
        (
            "--workspace",
            str(WORKSPACE_ROOT),
            "verify-eye-on-arm-fk-offline",
            "--dataset",
            "capture.json",
            "--dataset-sha256",
            "a" * 64,
            "--evidence",
            "raw-feedback.json",
            "--evidence-sha256",
            "b" * 64,
            "--require-pass",
            "--json",
        )
    )

    document = emitted
    assert exit_code == 0
    assert document["schema"] == "rocell.eye_on_arm_fk_offline_cli.v1"
    assert document["verified_context"]["identity_match_checked"] is True
    assert document["verified_context"]["manifest_id"] == "TEST-FREEZE-005"
    assert document["verified_input_file_sha256"] == {
        "dataset": "a" * 64,
        "evidence": "b" * 64,
    }
    assert document["fk_verification"]["report_hash"] == "e" * 64
    assert document["hardware_access"] is False
    assert document["arm_commands_generated"] == 0
    assert document["artifact_installed"] is False
    assert document["commissioning_assessment_performed"] is False
    assert observed == {
        "dataset_hash": "a" * 64,
        "evidence_hash": "b" * 64,
        "dataset": dataset,
        "evidence": evidence,
        "model_path": context.scenario.model_path,
    }


def test_eye_on_arm_capture_bundle_cli_requires_three_exact_hashes() -> None:
    parsed = build_parser().parse_args(
        (
            "verify-eye-on-arm-capture-bundle-offline",
            "--dataset",
            "capture.json",
            "--dataset-sha256",
            "a" * 64,
            "--evidence",
            "feedback.json",
            "--evidence-sha256",
            "b" * 64,
            "--bundle",
            "raw-bundle.json",
            "--bundle-sha256",
            "c" * 64,
            "--require-pass",
            "--json",
        )
    )

    assert parsed.command == "verify-eye-on-arm-capture-bundle-offline"
    assert parsed.dataset_sha256 == "a" * 64
    assert parsed.evidence_sha256 == "b" * 64
    assert parsed.bundle_sha256 == "c" * 64
    assert parsed.require_pass is True


def test_eye_on_arm_capture_bundle_cli_remains_structural_and_zero_authority(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application as application
    import rocell.calibration as calibration
    import rocell.cli as cli

    model_hash = "c" * 64
    context = SimpleNamespace(
        snapshot=SimpleNamespace(
            manifest_id="TEST-FREEZE-005",
            active_build_id="TEST-BUILD-A",
            snapshot_hash="d" * 64,
        ),
        bundle_lock=SimpleNamespace(bundle_id="TEST-BUNDLE-005"),
        scenario=SimpleNamespace(model_sha256=model_hash),
    )
    dataset = object()
    evidence = SimpleNamespace(
        manifest_id="TEST-FREEZE-005",
        active_build_id="TEST-BUILD-A",
        kinematic_model_sha256=model_hash,
    )
    bundle = object()
    report = SimpleNamespace(
        status="STRUCTURAL_PASS_NO_PHYSICAL_AUTHORITY",
        bundle_id="bundle-001",
        samples=(object(), object()),
        report_hash="e" * 64,
        structural_passed=True,
        to_dict=lambda: {
            "schema": "rocell.eye_on_arm_capture_bundle_verification.v1",
            "status": "STRUCTURAL_PASS_NO_PHYSICAL_AUTHORITY",
            "physical_release_effect": "NONE",
        },
    )
    emitted: dict[str, object] = {}
    observed: dict[str, object] = {}
    monkeypatch.setattr(application, "load_simulation_context", lambda *_: context)
    monkeypatch.setattr(
        calibration,
        "load_eye_on_arm_dataset",
        lambda path, *, expected_file_sha256: dataset,
    )
    monkeypatch.setattr(
        calibration,
        "load_eye_on_arm_capture_evidence",
        lambda path, *, expected_file_sha256: evidence,
    )
    monkeypatch.setattr(
        calibration,
        "load_eye_on_arm_capture_bundle",
        lambda path, *, expected_file_sha256: (
            observed.update(bundle_hash=expected_file_sha256) or bundle
        ),
    )
    monkeypatch.setattr(
        calibration,
        "verify_eye_on_arm_capture_bundle",
        lambda candidate_dataset, candidate_evidence, candidate_bundle: (
            observed.update(
                dataset=candidate_dataset,
                evidence=candidate_evidence,
                bundle=candidate_bundle,
            )
            or report
        ),
    )
    monkeypatch.setattr(
        cli,
        "_json_dump",
        lambda document, stream=None: emitted.update(document),
    )

    exit_code = main(
        (
            "--workspace",
            str(WORKSPACE_ROOT),
            "verify-eye-on-arm-capture-bundle-offline",
            "--dataset",
            "capture.json",
            "--dataset-sha256",
            "a" * 64,
            "--evidence",
            "feedback.json",
            "--evidence-sha256",
            "b" * 64,
            "--bundle",
            "raw-bundle.json",
            "--bundle-sha256",
            "c" * 64,
            "--require-pass",
            "--json",
        )
    )

    assert exit_code == 0
    assert emitted["schema"] == "rocell.eye_on_arm_capture_bundle_offline_cli.v1"
    assert emitted["hardware_access"] is False
    assert emitted["camera_frames_requested"] == 0
    assert emitted["commissioning_assessment_performed"] is False
    assert emitted["physical_timing_qualified"] is False
    assert emitted["verified_input_file_sha256"] == {
        "dataset": "a" * 64,
        "evidence": "b" * 64,
        "capture_bundle": "c" * 64,
    }
    assert observed == {
        "bundle_hash": "c" * 64,
        "dataset": dataset,
        "evidence": evidence,
        "bundle": bundle,
    }
