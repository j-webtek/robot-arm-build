from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass, replace
import hashlib
import json
from pathlib import Path
import shutil
from typing import Any, Mapping

import pytest

from rocell.application.first_power_on_onboarding import (
    FIRST_POWER_ON_CHECKPOINT_SCHEMA,
    FIRST_POWER_ON_PURPOSE,
    FIRST_POWER_ON_SCHEMA,
    MAX_CHECKPOINT_BYTES,
    STAGE_DEFINITIONS,
    STAGE_ORDER,
    DeterministicOnboardingProvider,
    FirstPowerOnCheckpoint,
    FirstPowerOnError,
    FirstPowerOnReport,
    OnboardingRecordStatus,
    OnboardingProbeResult,
    OnboardingScenario,
    OnboardingStage,
    load_first_power_on_checkpoint,
    parse_first_power_on_checkpoint,
    run_first_power_on_rehearsal,
    save_first_power_on_checkpoint,
)


WORKSPACE = Path(__file__).resolve().parents[3]


@dataclass(frozen=True)
class FaultExpectation:
    """Exact externally visible signature of one deliberate fail-stop."""

    stage: OnboardingStage
    detail_code: str
    failed_check_ids: tuple[str, ...]
    record_count: int
    stage_camera_frames: int = 0
    stage_feedback_queries: int = 0
    total_camera_frames: int = 0
    total_feedback_queries: int = 0
    stage_virtual_waypoints: int = 0
    stage_virtual_contact_attempts: int = 0
    stage_virtual_contacts_accepted: int = 0
    stage_virtual_observations: int = 0
    total_virtual_waypoints: int = 0
    total_virtual_contact_attempts: int = 0
    total_virtual_contacts_accepted: int = 0
    total_virtual_observations: int = 0
    cleanup_result: str = "NOT_APPLICABLE_NO_RESOURCE_OPENED"
    cleanup_satisfied: bool = True


FAULT_EXPECTATIONS: Mapping[OnboardingScenario, FaultExpectation] = {
    OnboardingScenario.CAMERA_RECEIPT_MISMATCH: FaultExpectation(
        OnboardingStage.CAMERA_RECEIPT,
        "CAMERA_RECEIPT_MISMATCH",
        ("model_matches",),
        3,
        total_camera_frames=2,
    ),
    OnboardingScenario.CAMERA_MISSING: FaultExpectation(
        OnboardingStage.CAMERA_IDENTITY,
        "CAMERA_IDENTITY_BLOCKED",
        ("identity_policy", "persistent_selector", "profile_product", "reconnect_identity"),
        4,
        total_camera_frames=2,
    ),
    OnboardingScenario.CAMERA_WRONG_IDENTITY: FaultExpectation(
        OnboardingStage.CAMERA_IDENTITY,
        "CAMERA_IDENTITY_BLOCKED",
        ("profile_product",),
        4,
        total_camera_frames=2,
    ),
    OnboardingScenario.CAMERA_USB2: FaultExpectation(
        OnboardingStage.CAMERA_MODE_CONTROLS,
        "CAMERA_MODE_CONTROLS_BLOCKED",
        ("native_mode_selected", "usb3_negotiated"),
        5,
        total_camera_frames=2,
    ),
    OnboardingScenario.CAMERA_SETTINGS_DRIFT: FaultExpectation(
        OnboardingStage.CAMERA_MODE_CONTROLS,
        "CAMERA_MODE_CONTROLS_BLOCKED",
        ("settings_stability",),
        5,
        total_camera_frames=2,
    ),
    OnboardingScenario.CAMERA_FRAME_STALE: FaultExpectation(
        OnboardingStage.CAMERA_FRAME_FRESHNESS,
        "CAMERA_FRAME_STALE",
        ("capture_sequence_advanced", "raw_frame_bytes_advanced"),
        6,
        stage_camera_frames=2,
        total_camera_frames=4,
    ),
    OnboardingScenario.CAMERA_FRAME_REWRAPPED: FaultExpectation(
        OnboardingStage.CAMERA_FRAME_FRESHNESS,
        "CAMERA_FRAME_REWRAPPED",
        ("raw_frame_bytes_advanced",),
        6,
        stage_camera_frames=2,
        total_camera_frames=4,
    ),
    OnboardingScenario.INTRINSICS_TAMPERED: FaultExpectation(
        OnboardingStage.OPTICS_INTRINSICS,
        "INTRINSICS_TAMPERED_BLOCKED",
        ("intrinsics_source_trusted",),
        7,
        total_camera_frames=4,
    ),
    OnboardingScenario.CAMERA_TAG_LOSS: FaultExpectation(
        OnboardingStage.STATIC_REGISTRATION,
        "CAMERA_TAG_LOSS_BLOCKED",
        ("held_out_station_validation", "startup_registration"),
        8,
        stage_camera_frames=1,
        total_camera_frames=5,
    ),
    OnboardingScenario.ARM_IDENTITY_MISMATCH: FaultExpectation(
        OnboardingStage.ARM_IDENTITY,
        "ARM_IDENTITY_MISMATCH",
        ("arm_model",),
        9,
        total_camera_frames=6,
    ),
    OnboardingScenario.STARTUP_SAFETY_BLOCKED: FaultExpectation(
        OnboardingStage.POWER_SAFETY,
        "POWER_SAFETY_BLOCKED",
        ("estop_gravity", "startup_sweep"),
        10,
        total_camera_frames=6,
    ),
    OnboardingScenario.STARTUP_MOTION_UNOBSERVED: FaultExpectation(
        OnboardingStage.POWER_ON_OBSERVATION,
        "STARTUP_MOTION_UNOBSERVED",
        ("startup_motion_observed",),
        11,
        total_camera_frames=6,
    ),
    OnboardingScenario.ARM_TIMEOUT: FaultExpectation(
        OnboardingStage.FEEDBACK_ONLY_CONNECTION,
        "ARM_FEEDBACK_TIMEOUT_BLOCKED",
        ("feedback_complete", "serial_exchange"),
        12,
        stage_feedback_queries=1,
        total_camera_frames=6,
        total_feedback_queries=1,
        cleanup_result="SYNTHETIC_SERIAL_TRANSPORT_CLOSED",
    ),
    OnboardingScenario.ARM_MALFORMED_FEEDBACK: FaultExpectation(
        OnboardingStage.FEEDBACK_ONLY_CONNECTION,
        "ARM_FEEDBACK_MALFORMED_BLOCKED",
        ("feedback_complete", "serial_exchange"),
        12,
        stage_feedback_queries=1,
        total_camera_frames=6,
        total_feedback_queries=1,
        cleanup_result="SYNTHETIC_SERIAL_TRANSPORT_CLOSED",
    ),
    OnboardingScenario.ARM_DISCONNECT: FaultExpectation(
        OnboardingStage.FEEDBACK_ONLY_CONNECTION,
        "ARM_FEEDBACK_DISCONNECT_BLOCKED",
        ("feedback_complete", "serial_exchange"),
        12,
        stage_feedback_queries=1,
        total_camera_frames=6,
        total_feedback_queries=1,
        cleanup_result="SYNTHETIC_SERIAL_TRANSPORT_CLOSED",
    ),
    OnboardingScenario.ARM_RESET_BANNER: FaultExpectation(
        OnboardingStage.FEEDBACK_ONLY_CONNECTION,
        "ARM_RESET_BANNER_BLOCKED",
        ("feedback_complete", "serial_exchange"),
        12,
        stage_feedback_queries=1,
        total_camera_frames=6,
        total_feedback_queries=1,
        cleanup_result="SYNTHETIC_SERIAL_TRANSPORT_CLOSED",
    ),
    OnboardingScenario.ARM_INCOMPLETE_FEEDBACK: FaultExpectation(
        OnboardingStage.FEEDBACK_ONLY_CONNECTION,
        "ARM_FEEDBACK_INCOMPLETE_BLOCKED",
        ("feedback_complete",),
        12,
        stage_feedback_queries=1,
        total_camera_frames=6,
        total_feedback_queries=1,
        cleanup_result="SYNTHETIC_SERIAL_TRANSPORT_CLOSED",
    ),
    OnboardingScenario.ARM_STALE_FEEDBACK: FaultExpectation(
        OnboardingStage.FEEDBACK_ONLY_CONNECTION,
        "ARM_STALE_BUFFERED_FEEDBACK_BLOCKED",
        (
            "feedback_complete",
            "receive_buffer_quiescent",
            "serial_exchange",
        ),
        12,
        stage_feedback_queries=1,
        total_camera_frames=6,
        total_feedback_queries=1,
        cleanup_result="SYNTHETIC_SERIAL_TRANSPORT_CLOSED",
    ),
    OnboardingScenario.CALIBRATION_STALE: FaultExpectation(
        OnboardingStage.REFERENCE_FRAME_CALIBRATION,
        "CALIBRATION_STALE_BLOCKED",
        ("calibration_chain_current",),
        13,
        total_camera_frames=6,
        total_feedback_queries=2,
    ),
    OnboardingScenario.NONCONTACT_PATH_BLOCKED: FaultExpectation(
        OnboardingStage.NONCONTACT_ACCEPTANCE,
        "NONCONTACT_VIRTUAL_ROUTE_FAULT_BLOCKED",
        ("noncontact_route_clear",),
        14,
        total_camera_frames=6,
        total_feedback_queries=2,
        cleanup_result="VIRTUAL_ARM_CLOSED_AFTER_FAIL_STOP",
    ),
}


@pytest.fixture(scope="module")
def nominal_report() -> FirstPowerOnReport:
    return run_first_power_on_rehearsal(WORKSPACE)


@pytest.fixture(scope="module")
def fault_reports() -> Mapping[OnboardingScenario, FirstPowerOnReport]:
    return {
        scenario: run_first_power_on_rehearsal(WORKSPACE, scenario=scenario)
        for scenario in FAULT_EXPECTATIONS
    }


def _canonical_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


def _checkpoint_payload(document: dict[str, Any]) -> bytes:
    return json.dumps(
        document,
        sort_keys=True,
        ensure_ascii=True,
        allow_nan=False,
    ).encode("utf-8")


def _refresh_checkpoint_hash(document: dict[str, Any]) -> None:
    without_hash = {
        key: value for key, value in document.items() if key != "checkpoint_sha256"
    }
    document["checkpoint_sha256"] = _canonical_hash(without_hash)


def _assert_zero_physical_authority(report: FirstPowerOnReport) -> None:
    payload = report.to_dict()
    assert payload["authority"] == {
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
    assert payload["physical_state"] == {
        "physical_onboarding_started": False,
        "camera_received_verified": False,
        "camera_connected": False,
        "camera_physically_calibrated": False,
        "arm_connected": False,
        "arm_identity_commissioned": False,
        "power_on_behavior_qualified": False,
        "reference_qualified": False,
        "frame_chain_calibrated": False,
        "noncontact_routes_qualified": False,
        "safe_to_power_robot": False,
        "motion_authorized": False,
        "contact_authorized": False,
    }
    simulated = payload["simulated_operations"]
    assert simulated["motion_commands"] == 0  # type: ignore[index]
    assert simulated["contact_commands"] == 0  # type: ignore[index]

    expected_record_authority = {
        "hardware_accessed": False,
        "camera_enumerations": 0,
        "live_camera_frames": 0,
        "arm_port_opens": 0,
        "arm_feedback_commands": 0,
        "arm_motion_commands": 0,
        "contact_commands": 0,
        "physical_release_effect": "NONE",
    }
    for record in payload["records"]:  # type: ignore[union-attr]
        assert record["authority"] == expected_record_authority
        assert record["evidence"]["origin"] == "SYNTHETIC_REHEARSAL"
        assert record["evidence"]["hardware_accessed"] is False
        assert record["evidence"]["physical_evidence_satisfied"] is False


def test_nominal_rehearsal_runs_all_fifteen_stages_in_order_and_stays_safe(
    nominal_report: FirstPowerOnReport,
) -> None:
    assert len(STAGE_ORDER) == 15
    assert tuple(record.stage for record in nominal_report.records) == STAGE_ORDER
    assert tuple(record.ordinal for record in nominal_report.records) == tuple(range(15))
    assert all(
        record.status is OnboardingRecordStatus.PASS
        for record in nominal_report.records
    )
    assert nominal_report.schema == FIRST_POWER_ON_SCHEMA
    assert nominal_report.purpose == FIRST_POWER_ON_PURPOSE
    assert nominal_report.status == (
        "SIMULATION_WORKFLOW_COMPLETE_PHYSICAL_ONBOARDING_NOT_STARTED"
    )
    assert nominal_report.complete is True
    assert nominal_report.expected_outcome_observed is True
    assert nominal_report.first_blocked_stage is None
    assert nominal_report.next_stage is None
    assert nominal_report.stopped_after is None
    assert nominal_report.emulated_camera_frames == 15
    assert nominal_report.emulated_feedback_queries == 2
    assert nominal_report.virtual_waypoints_executed == 109
    assert nominal_report.virtual_contact_attempts == 9
    assert nominal_report.virtual_contacts_accepted == 9
    assert nominal_report.virtual_observations == 9

    previous: str | None = None
    for record in nominal_report.records:
        assert record.previous_record_sha256 == previous
        assert len(record.record_sha256) == 64
        previous = record.record_sha256

    _assert_zero_physical_authority(nominal_report)


def test_source_binding_covers_commissioning_runtime_and_implementation(
    nominal_report: FirstPowerOnReport,
) -> None:
    bindings = dict(nominal_report.source_bindings)
    required = {
        "software/tests/fixtures/camera/b0477_nominal_rehearsal.json",
        "software/tests/fixtures/camera/b0477_synthetic_intrinsics_rehearsal.json",
        "software/config/runtime.json",
        "software/src/rocell/application/first_power_on_onboarding.py",
        "software/src/rocell/application/virtual_session.py",
        "software/src/rocell/arm/serial_transport.py",
        "software/src/rocell/vision/camera_commissioning.py",
    }

    assert required <= bindings.keys()
    assert tuple(path for path, _digest in nominal_report.source_bindings) == tuple(
        sorted(bindings)
    )
    assert len(bindings) == len(nominal_report.source_bindings)
    for relative in required:
        assert bindings[relative] == hashlib.sha256(
            (WORKSPACE / relative).read_bytes()
        ).hexdigest()


def test_nominal_freshness_uses_distinct_raw_jpegs_not_only_new_wrappers(
    nominal_report: FirstPowerOnReport,
) -> None:
    record = nominal_report.records[
        STAGE_ORDER.index(OnboardingStage.CAMERA_FRAME_FRESHNESS)
    ]
    evidence = dict(record.evidence_hashes)

    assert evidence["capture_first_raw"] != evidence["capture_second_raw_observed"]
    assert evidence["capture_first_report"] != evidence["capture_second_report"]
    assert {
        check.check_id: check.passed for check in record.checks
    }["raw_frame_bytes_advanced"] is True


@pytest.mark.parametrize("scenario", tuple(FAULT_EXPECTATIONS), ids=lambda item: item.value)
def test_all_twenty_faults_have_their_exact_fail_stop_signature(
    scenario: OnboardingScenario,
    fault_reports: Mapping[OnboardingScenario, FirstPowerOnReport],
    nominal_report: FirstPowerOnReport,
) -> None:
    expected = FAULT_EXPECTATIONS[scenario]
    report = fault_reports[scenario]
    final_ordinal = STAGE_ORDER.index(expected.stage)
    expected_prefix = STAGE_ORDER[: final_ordinal + 1]
    assert tuple(record.stage for record in report.records) == expected_prefix
    assert len(report.records) == expected.record_count
    assert all(
        record.status is OnboardingRecordStatus.PASS
        for record in report.records[:-1]
    )
    assert report.records[:-1] == nominal_report.records[:final_ordinal]
    observed = report.records[-1]
    assert observed.status is OnboardingRecordStatus.BLOCKED
    assert observed.stage is expected.stage
    assert observed.detail_code == expected.detail_code
    assert tuple(
        sorted(check.check_id for check in observed.checks if not check.passed)
    ) == expected.failed_check_ids
    assert observed.emulated_camera_frames == expected.stage_camera_frames
    assert observed.emulated_feedback_queries == expected.stage_feedback_queries
    assert observed.virtual_waypoints_executed == expected.stage_virtual_waypoints
    assert observed.virtual_contact_attempts == expected.stage_virtual_contact_attempts
    assert observed.virtual_contacts_accepted == expected.stage_virtual_contacts_accepted
    assert observed.virtual_observations == expected.stage_virtual_observations
    assert report.first_blocked_stage is expected.stage
    assert report.next_stage is expected.stage
    assert report.status == "SYNTHETIC_REHEARSAL_BLOCKED"
    assert report.complete is False
    assert report.expected_outcome_observed is True
    assert report.emulated_camera_frames == expected.total_camera_frames
    assert report.emulated_feedback_queries == expected.total_feedback_queries
    assert report.virtual_waypoints_executed == expected.total_virtual_waypoints
    assert report.virtual_contact_attempts == expected.total_virtual_contact_attempts
    assert report.virtual_contacts_accepted == expected.total_virtual_contacts_accepted
    assert report.virtual_observations == expected.total_virtual_observations

    document = report.to_dict()
    assert document["expected_block_stage"] == expected.stage.value
    assert document["expected_fault_detail_code"] == expected.detail_code
    assert document["simulated_operations"] == {
        "camera_frames": expected.total_camera_frames,
        "feedback_queries": expected.total_feedback_queries,
        "virtual_waypoints_executed": expected.total_virtual_waypoints,
        "virtual_contact_attempts": expected.total_virtual_contact_attempts,
        "virtual_contacts_accepted": expected.total_virtual_contacts_accepted,
        "virtual_observations": expected.total_virtual_observations,
        "motion_commands": 0,
        "contact_commands": 0,
    }
    assert document["fault_diagnostics"] == {
        "observed_detail_code": expected.detail_code,
        "expected_failed_check_ids": list(expected.failed_check_ids),
        "observed_failed_check_ids": list(expected.failed_check_ids),
        "expected_stage_operations": {
            "emulated_camera_frames": expected.stage_camera_frames,
            "emulated_feedback_queries": expected.stage_feedback_queries,
            "virtual_waypoints_executed": expected.stage_virtual_waypoints,
            "virtual_contact_attempts": expected.stage_virtual_contact_attempts,
            "virtual_contacts_accepted": expected.stage_virtual_contacts_accepted,
            "virtual_observations": expected.stage_virtual_observations,
        },
        "observed_stage_operations": {
            "emulated_camera_frames": expected.stage_camera_frames,
            "emulated_feedback_queries": expected.stage_feedback_queries,
            "virtual_waypoints_executed": expected.stage_virtual_waypoints,
            "virtual_contact_attempts": expected.stage_virtual_contact_attempts,
            "virtual_contacts_accepted": expected.stage_virtual_contacts_accepted,
            "virtual_observations": expected.stage_virtual_observations,
        },
        "stages_not_run": [stage.value for stage in STAGE_ORDER[expected.record_count :]],
        "cleanup_result": expected.cleanup_result,
        "cleanup_satisfied": expected.cleanup_satisfied,
        "next_safe_action": document["next_safe_action"],
    }
    _assert_zero_physical_authority(report)


def test_scenario_inventory_is_exactly_one_nominal_plus_twenty_faults() -> None:
    assert len(tuple(OnboardingScenario)) == 21
    assert set(OnboardingScenario) == {
        OnboardingScenario.NOMINAL,
        *FAULT_EXPECTATIONS,
    }


def test_rewrapped_frame_fault_has_new_metadata_but_duplicate_raw_bytes(
    fault_reports: Mapping[OnboardingScenario, FirstPowerOnReport],
) -> None:
    report = fault_reports[OnboardingScenario.CAMERA_FRAME_REWRAPPED]
    evidence = dict(report.records[-1].evidence_hashes)

    assert evidence["capture_first_raw"] == evidence["capture_second_raw_observed"]
    assert evidence["capture_first_report"] != evidence["capture_second_report"]
    assert report.expected_outcome_observed is True


def test_receipt_mismatch_hashes_the_observed_wrong_article(
    nominal_report: FirstPowerOnReport,
    fault_reports: Mapping[OnboardingScenario, FirstPowerOnReport],
) -> None:
    ordinal = STAGE_ORDER.index(OnboardingStage.CAMERA_RECEIPT)
    nominal = dict(nominal_report.records[ordinal].evidence_hashes)
    mismatch = dict(
        fault_reports[OnboardingScenario.CAMERA_RECEIPT_MISMATCH]
        .records[-1]
        .evidence_hashes
    )

    assert nominal["synthetic_receipt"] != mismatch["synthetic_receipt"]
    assert nominal["receipt_assessment"] != mismatch["receipt_assessment"]
    nominal_checks = {
        check.check_id: check.passed
        for check in nominal_report.records[ordinal].checks
    }
    assert nominal_checks["receipt_assessment_check_contract"] is True


def test_fault_acceptance_rejects_a_changed_nominal_prefix_signature(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    """A correct terminal fault cannot hide drift in an earlier pass record."""

    original_probe = DeterministicOnboardingProvider.probe

    def changed_prefix_probe(
        self: DeterministicOnboardingProvider, stage: OnboardingStage
    ) -> OnboardingProbeResult:
        result = original_probe(self, stage)
        if (
            self.scenario is OnboardingScenario.CAMERA_RECEIPT_MISMATCH
            and stage is OnboardingStage.WORKSPACE_SOURCES
        ):
            return replace(result, detail_code="WORKSPACE_SOURCES_UNEXPECTED_VARIANT")
        return result

    monkeypatch.setattr(
        DeterministicOnboardingProvider,
        "probe",
        changed_prefix_probe,
    )
    report = run_first_power_on_rehearsal(
        WORKSPACE,
        scenario=OnboardingScenario.CAMERA_RECEIPT_MISMATCH,
    )

    assert report.first_blocked_stage is OnboardingStage.CAMERA_RECEIPT
    assert report.records[-1].detail_code == "CAMERA_RECEIPT_MISMATCH"
    assert report.expected_outcome_observed is False


def test_static_phase1_calibration_stage_exercises_the_complete_selected_graph(
    nominal_report: FirstPowerOnReport,
) -> None:
    record = nominal_report.records[
        STAGE_ORDER.index(OnboardingStage.REFERENCE_FRAME_CALIBRATION)
    ]
    checks = {check.check_id: check.passed for check in record.checks}

    assert checks["static_phase1_graph_complete"] is True
    assert checks["dependency_invalidation_exercised"] is True
    assert checks["physical_registry_blocked"] is True
    assert "static_phase1_calibration_graph" in dict(record.evidence_hashes)


def test_rehearsal_encodes_distinct_power_and_calibration_campaign_boundaries(
    nominal_report: FirstPowerOnReport,
) -> None:
    """Procedure guidance must not turn one reviewed effect into standing authority."""

    by_stage = {record.stage: record for record in nominal_report.records}

    stage8 = STAGE_DEFINITIONS[OnboardingStage.STATIC_REGISTRATION]
    assert "actuator 12 V physically disconnected" in stage8.procedure

    stage11 = by_stage[OnboardingStage.POWER_ON_OBSERVATION]
    stage11_checks = {check.check_id: check.passed for check in stage11.checks}
    assert stage11_checks["unique_energization_envelope_required"] is True
    assert stage11_checks["final_deenergized_state_required"] is True
    assert "then manually de-energize" in STAGE_DEFINITIONS[
        OnboardingStage.POWER_ON_OBSERVATION
    ].procedure

    stage12 = by_stage[OnboardingStage.FEEDBACK_ONLY_CONNECTION]
    stage12_checks = {check.check_id: check.passed for check in stage12.checks}
    assert stage12_checks["fresh_stage12_envelope_required"] is True
    assert stage12_checks["permit_precedes_serial_open"] is True
    assert stage12_checks["serial_open_possible_motion_effect"] is True
    assert stage12_checks["final_deenergized_state_required"] is True
    assert "T=105 is not a motion command" in STAGE_DEFINITIONS[
        OnboardingStage.FEEDBACK_ONLY_CONNECTION
    ].procedure

    stage13 = by_stage[OnboardingStage.REFERENCE_FRAME_CALIBRATION]
    stage13_checks = {check.check_id: check.passed for check in stage13.checks}
    assert stage13_checks["precalibration_bootstrap_separate"] is True
    assert stage13_checks["reference_campaign_separate"] is True
    assert stage13_checks["calibration_dependency_manifest_complete"] is True
    assert "calibration_dependency_manifest" in dict(stage13.evidence_hashes)


def test_stage15_rehearses_the_top_level_39_component_contract_without_release(
    nominal_report: FirstPowerOnReport,
) -> None:
    record = nominal_report.records[
        STAGE_ORDER.index(OnboardingStage.PHYSICAL_HANDOFF)
    ]
    checks = {check.check_id: check.passed for check in record.checks}

    assert checks == {
        "bundle_component_contract_complete": True,
        "commissioning_bundle_withheld": True,
        "separate_release_review": True,
        "no_automatic_arm": True,
    }
    assert tuple(name for name, _digest in record.evidence_hashes) == (
        "commissioning_bundle_component_contract",
        "handoff_contract",
    )
    assert "39-component top-level CommissioningBundle contract" in record.summary
    assert "real bundle explicitly incomplete" in STAGE_DEFINITIONS[
        OnboardingStage.PHYSICAL_HANDOFF
    ].procedure
    assert "COMPLETE_DIAGNOSTIC disposition remain withheld" in record.summary
    assert record.to_dict()["authority"]["physical_release_effect"] == "NONE"  # type: ignore[index]


def test_nominal_noncontact_stage_exposes_exact_virtual_work_and_b0477_binding(
    nominal_report: FirstPowerOnReport,
) -> None:
    record = nominal_report.records[
        STAGE_ORDER.index(OnboardingStage.NONCONTACT_ACCEPTANCE)
    ]
    checks = {check.check_id: check.passed for check in record.checks}

    assert record.virtual_waypoints_executed == 109
    assert record.virtual_contact_attempts == 9
    assert record.virtual_contacts_accepted == 9
    assert record.virtual_observations == 9
    assert checks["b0477_action_bindings_complete"] is True
    assert checks["latest_static_registration_bound"] is True
    assert checks["b0477_imagery_claim_bounded"] is True
    assert checks["virtual_operation_counts_exact"] is True
    assert "b0477_virtual_acceptance" in dict(record.evidence_hashes)


def test_first_waypoint_fault_proves_no_later_virtual_contact_or_observation(
    fault_reports: Mapping[OnboardingScenario, FirstPowerOnReport],
) -> None:
    record = fault_reports[OnboardingScenario.NONCONTACT_PATH_BLOCKED].records[-1]
    checks = {check.check_id: check.passed for check in record.checks}

    assert checks["no_waypoint_executed_after_fault"] is True
    assert checks["no_contact_or_observation_after_fault"] is True
    assert checks["virtual_output_unchanged_after_fault"] is True
    assert record.virtual_waypoints_executed == 0
    assert record.virtual_contact_attempts == 0
    assert record.virtual_contacts_accepted == 0
    assert record.virtual_observations == 0


def test_runner_rejects_external_provider_injection() -> None:
    with pytest.raises(TypeError, match="unexpected keyword argument 'provider'"):
        run_first_power_on_rehearsal(  # type: ignore[call-arg]
            WORKSPACE,
            provider=DeterministicOnboardingProvider(
                WORKSPACE, OnboardingScenario.NOMINAL
            ),
        )


def test_feedback_rehearsal_cannot_mint_or_use_a_live_feedback_permit(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rocell.arm.serial_transport import SerialTransport
    from rocell.safety.permit import FeedbackPermit

    def forbidden_live_capability(*args: Any, **kwargs: Any) -> Any:
        raise AssertionError(
            "zero-authority onboarding attempted to mint or use a live capability"
        )

    # Patch both sides of the live capability boundary.  The onboarding probe
    # must stay wholly inside DeterministicFeedbackSession: it may neither mint
    # a SafetySupervisor capability nor pass one into SerialTransport.
    monkeypatch.setattr(FeedbackPermit, "_issue", forbidden_live_capability)
    monkeypatch.setattr(
        SerialTransport, "request_feedback", forbidden_live_capability
    )

    result = DeterministicOnboardingProvider(
        WORKSPACE, OnboardingScenario.NOMINAL
    ).probe(OnboardingStage.FEEDBACK_ONLY_CONNECTION)

    assert result.passed is True
    assert result.detail_code == "FEEDBACK_ONLY_CONNECTION_REHEARSED"
    assert result.emulated_feedback_queries == 2
    assert {check.check_id: check.passed for check in result.checks}[
        "transport_cleanup_closed"
    ] is True


def test_feedback_fault_detail_comes_from_observed_failure_not_scenario(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rocell.arm.protocol_emulator import (
        DeterministicFeedbackSession,
        ProtocolEmulatorFault,
        ProtocolEmulatorStep,
    )

    original_init = DeterministicFeedbackSession.__init__

    def swap_timeout_step_for_disconnect(
        self: DeterministicFeedbackSession,
        steps: Any = (),
        *,
        max_line_bytes: int = 4096,
    ) -> None:
        swapped = tuple(
            ProtocolEmulatorStep(ProtocolEmulatorFault.DISCONNECT)
            if step.fault is ProtocolEmulatorFault.TIMEOUT
            else step
            for step in steps
        )
        original_init(self, swapped, max_line_bytes=max_line_bytes)

    # Keep failed checks and bounded operation counts identical to the timeout
    # scenario while changing only what the fake wire actually does.  A
    # scenario-selected detail code would falsely report the expected timeout.
    monkeypatch.setattr(
        DeterministicFeedbackSession, "__init__", swap_timeout_step_for_disconnect
    )
    report = run_first_power_on_rehearsal(
        WORKSPACE, scenario=OnboardingScenario.ARM_TIMEOUT
    )
    observed = report.records[-1]

    assert observed.stage is OnboardingStage.FEEDBACK_ONLY_CONNECTION
    assert observed.detail_code == "ARM_FEEDBACK_DISCONNECT_BLOCKED"
    assert tuple(
        sorted(check.check_id for check in observed.checks if not check.passed)
    ) == ("feedback_complete", "serial_exchange")
    assert observed.emulated_feedback_queries == 1
    assert report.expected_outcome_observed is False
    diagnostics = report.to_dict()["fault_diagnostics"]
    assert isinstance(diagnostics, dict)
    assert report.to_dict()["expected_fault_detail_code"] == (
        "ARM_FEEDBACK_TIMEOUT_BLOCKED"
    )
    assert diagnostics["observed_detail_code"] == "ARM_FEEDBACK_DISCONNECT_BLOCKED"


def test_intrinsics_fault_is_not_mistaken_for_expected_if_parser_regresses(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rocell.calibration import static_camera_intrinsics

    original_parser = static_camera_intrinsics.parse_static_camera_intrinsics_json

    def parser_with_artifact_id_regression(
        payload: bytes, *args: Any, **kwargs: Any
    ) -> Any:
        # Preserve every normal parse used by earlier onboarding stages, but
        # model a parser regression that wrongly accepts the injected ID edit.
        if b'tampered-intrinsics-artifact' in payload:
            return object()
        return original_parser(payload, *args, **kwargs)

    monkeypatch.setattr(
        static_camera_intrinsics,
        "parse_static_camera_intrinsics_json",
        parser_with_artifact_id_regression,
    )
    report = run_first_power_on_rehearsal(
        WORKSPACE, scenario=OnboardingScenario.INTRINSICS_TAMPERED
    )
    observed = report.records[-1]

    assert observed.stage is OnboardingStage.OPTICS_INTRINSICS
    assert observed.detail_code == "INTRINSICS_TAMPERED_BLOCKED"
    assert tuple(
        sorted(check.check_id for check in observed.checks if not check.passed)
    ) == ("intrinsics_source_trusted", "intrinsics_tamper_rejected")
    assert report.expected_outcome_observed is False
    _assert_zero_physical_authority(report)


@pytest.mark.parametrize(
    "scenario, expected_calls",
    (
        (
            OnboardingScenario.NOMINAL,
            (("keyboard", "test"), ("phone", "test.")),
        ),
        (
            OnboardingScenario.NONCONTACT_PATH_BLOCKED,
            (("keyboard", "test"),),
        ),
    ),
    ids=("nominal", "fault-cleanup"),
)
def test_noncontact_stage_executes_actual_virtual_paths_and_closes_plants(
    scenario: OnboardingScenario,
    expected_calls: tuple[tuple[str, str], ...],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rocell.application import b0477_virtual_acceptance, virtual_session

    original_runner = virtual_session.run_default_virtual_session
    observed: list[tuple[str, str, Any]] = []

    def tracking_runner(
        workspace: Path,
        target: str,
        text: str,
        **kwargs: Any,
    ) -> Any:
        session = original_runner(workspace, target, text, **kwargs)
        observed.append((target, text, session))
        return session

    monkeypatch.setattr(
        virtual_session, "run_default_virtual_session", tracking_runner
    )
    monkeypatch.setattr(
        b0477_virtual_acceptance,
        "run_default_virtual_session",
        tracking_runner,
    )
    result = DeterministicOnboardingProvider(WORKSPACE, scenario).probe(
        OnboardingStage.NONCONTACT_ACCEPTANCE
    )

    assert tuple((target, text) for target, text, _ in observed) == expected_calls
    assert all(
        session.arm_document.get("lifecycle") == "CLOSED"
        for _target, _text, session in observed
    )
    assert all(
        session.to_dict()["authority"]["hardware_accessed"] is False
        and session.to_dict()["authority"]["hardware_commands_generated"] == 0
        for _target, _text, session in observed
    )
    checks = {check.check_id: check.passed for check in result.checks}
    if scenario is OnboardingScenario.NOMINAL:
        assert result.passed is True
        assert (
            result.detail_code
            == "NONCONTACT_ACCEPTANCE_REHEARSED_PHYSICAL_COLLISION_BLOCKED"
        )
        assert all(
            session.pipeline_completed
            and session.outcome_verified
            and session.ended_at_park
            for _target, _text, session in observed
        )
        assert checks["final_park_and_cleanup"] is True
    else:
        assert result.passed is False
        assert result.detail_code == "NONCONTACT_VIRTUAL_ROUTE_FAULT_BLOCKED"
        session = observed[0][2]
        assert session.pipeline_completed is False
        assert session.fault_reason == "ARM_STALL"
        assert (
            "onboarding-blocked-first-virtual-waypoint"
            in session.final_fault_script.consumed_trigger_ids
        )
        assert checks["fault_injection_consumed"] is True
        assert checks["fault_cleanup_closed"] is True


def test_explicit_stop_is_a_successful_checkpoint_not_an_unexpected_outcome() -> None:
    report = run_first_power_on_rehearsal(
        WORKSPACE,
        stop_after=OnboardingStage.CAMERA_RECEIPT,
    )

    assert tuple(record.stage for record in report.records) == STAGE_ORDER[:3]
    assert report.stopped_after is OnboardingStage.CAMERA_RECEIPT
    assert report.next_stage is OnboardingStage.CAMERA_IDENTITY
    assert report.status == "SYNTHETIC_REHEARSAL_CHECKPOINT_READY"
    assert report.complete is False
    assert report.expected_outcome_observed is True
    _assert_zero_physical_authority(report)


def test_fault_scenario_stopped_before_its_gate_is_not_an_expected_outcome() -> None:
    report = run_first_power_on_rehearsal(
        WORKSPACE,
        scenario=OnboardingScenario.ARM_TIMEOUT,
        stop_after=OnboardingStage.CAMERA_RECEIPT,
    )

    assert report.stopped_after is OnboardingStage.CAMERA_RECEIPT
    assert report.first_blocked_stage is None
    assert report.expected_outcome_observed is False
    assert report.to_dict()["expected_block_stage"] == "feedback_only_connection"
    assert report.to_dict()["fault_diagnostics"]["observed_detail_code"] is None  # type: ignore[index]
    _assert_zero_physical_authority(report)


def test_stop_checkpoint_save_load_and_resume_matches_uninterrupted_records(
    tmp_path: Path,
    nominal_report: FirstPowerOnReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    stop_stage = OnboardingStage.STATIC_REGISTRATION
    stopped = run_first_power_on_rehearsal(WORKSPACE, stop_after=stop_stage)
    checkpoint_path = save_first_power_on_checkpoint(
        tmp_path,
        Path("nested/first-power-on.json"),
        stopped,
    )
    checkpoint = load_first_power_on_checkpoint(tmp_path, checkpoint_path)
    calls: list[OnboardingStage] = []
    original_probe = DeterministicOnboardingProvider.probe

    def tracking_probe(
        self: DeterministicOnboardingProvider, stage: OnboardingStage
    ):  # type: ignore[no-untyped-def]
        calls.append(stage)
        return original_probe(self, stage)

    monkeypatch.setattr(DeterministicOnboardingProvider, "probe", tracking_probe)

    resumed = run_first_power_on_rehearsal(
        WORKSPACE,
        checkpoint=checkpoint,
    )

    assert checkpoint.schema == FIRST_POWER_ON_CHECKPOINT_SCHEMA
    assert checkpoint.records == stopped.records
    assert resumed.resumed_from_checkpoint_sha256 == checkpoint.checkpoint_sha256
    # Resume does not trust or skip the stored prefix: every built-in probe is
    # replayed and compared byte-for-byte before later stages are accepted.
    assert tuple(calls) == STAGE_ORDER
    assert resumed.records == nominal_report.records
    assert resumed.run_binding_sha256 == nominal_report.run_binding_sha256
    assert resumed.status == nominal_report.status
    assert resumed.complete is True
    assert resumed.expected_outcome_observed is True
    _assert_zero_physical_authority(resumed)


def test_resume_replays_the_prefix_and_repeats_a_blocked_stage(
    fault_reports: Mapping[OnboardingScenario, FirstPowerOnReport],
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    scenario = OnboardingScenario.CAMERA_RECEIPT_MISMATCH
    blocked = fault_reports[scenario]
    checkpoint = FirstPowerOnCheckpoint.from_report(blocked)
    calls: list[OnboardingStage] = []
    original_probe = DeterministicOnboardingProvider.probe

    def tracking_probe(
        self: DeterministicOnboardingProvider, stage: OnboardingStage
    ):  # type: ignore[no-untyped-def]
        calls.append(stage)
        return original_probe(self, stage)

    monkeypatch.setattr(DeterministicOnboardingProvider, "probe", tracking_probe)

    resumed = run_first_power_on_rehearsal(
        WORKSPACE,
        scenario=scenario,
        checkpoint=checkpoint,
    )

    assert tuple(calls) == STAGE_ORDER[:3]
    assert resumed.records == blocked.records
    assert resumed.first_blocked_stage is OnboardingStage.CAMERA_RECEIPT
    assert resumed.resumed_from_checkpoint_sha256 == checkpoint.checkpoint_sha256


def test_parser_rejects_checkpoint_digest_tampering(
    nominal_report: FirstPowerOnReport,
) -> None:
    document = FirstPowerOnCheckpoint.from_report(nominal_report).to_dict()
    document["checkpoint_sha256"] = "0" * 64

    with pytest.raises(FirstPowerOnError, match="canonical digest mismatch"):
        parse_first_power_on_checkpoint(_checkpoint_payload(document))


def test_self_consistent_source_tamper_is_rejected_when_resuming_workspace(
    nominal_report: FirstPowerOnReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    document = deepcopy(FirstPowerOnCheckpoint.from_report(nominal_report).to_dict())
    bindings = document["source_bindings"]
    assert isinstance(bindings, list)
    original_digest = bindings[0]["sha256"]
    bindings[0]["sha256"] = (
        ("0" if original_digest[0] != "0" else "1") + original_digest[1:]
    )

    report_payload = nominal_report.to_dict()
    changed_run_binding = _canonical_hash(
        {
            "workflow_schema": FIRST_POWER_ON_SCHEMA,
            "workflow_definition_sha256": report_payload[
                "workflow_definition_sha256"
            ],
            "source_bindings": bindings,
        }
    )
    document["run_binding_sha256"] = changed_run_binding
    changed_source_bindings = tuple(
        (binding["path"], binding["sha256"]) for binding in bindings
    )
    changed_report = FirstPowerOnReport(
        scenario=nominal_report.scenario,
        source_bindings=changed_source_bindings,
        run_binding_sha256=changed_run_binding,
        records=nominal_report.records,
        stopped_after=nominal_report.stopped_after,
        resumed_from_checkpoint_sha256=(
            nominal_report.resumed_from_checkpoint_sha256
        ),
    )
    source_report = document["source_report"]
    assert isinstance(source_report, dict)
    source_report["report_sha256"] = changed_report.report_sha256
    _refresh_checkpoint_hash(document)
    tampered = parse_first_power_on_checkpoint(_checkpoint_payload(document))
    calls: list[OnboardingStage] = []
    original_probe = DeterministicOnboardingProvider.probe

    def tracking_probe(
        self: DeterministicOnboardingProvider, stage: OnboardingStage
    ):  # type: ignore[no-untyped-def]
        calls.append(stage)
        return original_probe(self, stage)

    monkeypatch.setattr(DeterministicOnboardingProvider, "probe", tracking_probe)

    with pytest.raises(FirstPowerOnError, match="source hashes are stale"):
        run_first_power_on_rehearsal(
            WORKSPACE,
            checkpoint=tampered,
        )
    assert calls == []


def test_checkpoint_binds_the_exact_originating_report(
    nominal_report: FirstPowerOnReport,
) -> None:
    checkpoint = FirstPowerOnCheckpoint.from_report(nominal_report)
    document = checkpoint.to_dict()

    assert document["source_report"] == {
        "report_sha256": nominal_report.report_sha256,
        "stopped_after": None,
        "resumed_from_checkpoint_sha256": None,
    }
    assert parse_first_power_on_checkpoint(_checkpoint_payload(document)) == checkpoint


@pytest.mark.parametrize(
    "mutate_source_report",
    (
        lambda report: report.__setitem__("report_sha256", "0" * 64),
        lambda report: report.__setitem__("stopped_after", "physical_handoff"),
        lambda report: report.__setitem__(
            "resumed_from_checkpoint_sha256", "1" * 64
        ),
    ),
    ids=("report-digest", "stop-context", "resume-context"),
)
def test_parser_rejects_source_report_tampering_with_a_refreshed_outer_hash(
    nominal_report: FirstPowerOnReport,
    mutate_source_report: Any,
) -> None:
    document = deepcopy(FirstPowerOnCheckpoint.from_report(nominal_report).to_dict())
    source_report = document["source_report"]
    assert isinstance(source_report, dict)
    mutate_source_report(source_report)
    _refresh_checkpoint_hash(document)

    with pytest.raises(FirstPowerOnError, match="source report"):
        parse_first_power_on_checkpoint(_checkpoint_payload(document))


@pytest.mark.parametrize(
    "mutation, message",
    (
        (lambda value: value.__setitem__("workflow_schema", "rocell.changed.v9"), "schema"),
        (lambda value: value.__setitem__("run_binding_sha256", "0" * 64), "run binding"),
    ),
    ids=("workflow-schema", "workflow-binding"),
)
def test_parser_rejects_workflow_tampering_even_with_refreshed_outer_hash(
    nominal_report: FirstPowerOnReport,
    mutation: Any,
    message: str,
) -> None:
    document = deepcopy(FirstPowerOnCheckpoint.from_report(nominal_report).to_dict())
    mutation(document)
    _refresh_checkpoint_hash(document)

    with pytest.raises(FirstPowerOnError, match=message):
        parse_first_power_on_checkpoint(_checkpoint_payload(document))


def test_parser_rejects_record_tampering_even_with_refreshed_outer_hash(
    nominal_report: FirstPowerOnReport,
) -> None:
    document = deepcopy(FirstPowerOnCheckpoint.from_report(nominal_report).to_dict())
    document["records"][0]["summary"] = "tampered summary"
    _refresh_checkpoint_hash(document)

    with pytest.raises(FirstPowerOnError, match="canonical record"):
        parse_first_power_on_checkpoint(_checkpoint_payload(document))


@pytest.mark.parametrize(
    "payload, message",
    (
        (b"", "non-empty bytes"),
        (b"{", "strict UTF-8 JSON"),
        (b"\xff", "strict UTF-8 JSON"),
        (b'{"schema": "one", "schema": "two"}', "duplicate key"),
        (b'{"value": NaN}', "invalid JSON constant"),
    ),
    ids=("empty", "malformed", "invalid-utf8", "duplicate", "nan"),
)
def test_parser_rejects_malformed_or_ambiguous_json(
    payload: bytes,
    message: str,
) -> None:
    with pytest.raises(FirstPowerOnError, match=message):
        parse_first_power_on_checkpoint(payload)


def test_parser_rejects_unknown_fields(
    nominal_report: FirstPowerOnReport,
) -> None:
    document = deepcopy(FirstPowerOnCheckpoint.from_report(nominal_report).to_dict())
    document["unexpected"] = "must fail closed"
    _refresh_checkpoint_hash(document)

    with pytest.raises(FirstPowerOnError, match="unknown=.*unexpected"):
        parse_first_power_on_checkpoint(_checkpoint_payload(document))


def test_parser_rejects_oversized_payload() -> None:
    with pytest.raises(FirstPowerOnError, match="byte limit"):
        parse_first_power_on_checkpoint(b" " * (MAX_CHECKPOINT_BYTES + 1))


def test_checkpoint_write_is_no_overwrite_and_preserves_original_bytes(
    tmp_path: Path,
    nominal_report: FirstPowerOnReport,
) -> None:
    destination = save_first_power_on_checkpoint(
        tmp_path,
        Path("first-power-on.json"),
        nominal_report,
    )
    original = destination.read_bytes()

    with pytest.raises(FirstPowerOnError, match="overwrite is forbidden"):
        save_first_power_on_checkpoint(tmp_path, destination, nominal_report)

    assert destination.read_bytes() == original
    assert not destination.with_name(destination.name + ".partial").exists()


def test_checkpoint_publish_loses_destination_race_without_overwriting(
    tmp_path: Path,
    nominal_report: FirstPowerOnReport,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from rocell.application import first_power_on_onboarding as onboarding

    destination = tmp_path / "raced.json"
    racer_bytes = b"independent-writer-won-the-race"
    original_link = onboarding.os.link

    def racing_link(source: str | Path, target: str | Path) -> None:
        Path(target).write_bytes(racer_bytes)
        original_link(source, target)

    monkeypatch.setattr(onboarding.os, "link", racing_link)

    with pytest.raises(FirstPowerOnError, match="appeared during write"):
        save_first_power_on_checkpoint(tmp_path, destination, nominal_report)

    assert destination.read_bytes() == racer_bytes
    assert not destination.with_name(destination.name + ".partial").exists()


def _symlink_or_skip(
    link: Path, target: Path | str, *, target_is_directory: bool
) -> None:
    try:
        link.symlink_to(target, target_is_directory=target_is_directory)
    except (NotImplementedError, OSError) as exc:
        pytest.skip(f"symlink creation is unavailable on this Windows host: {exc}")


def test_checkpoint_load_rejects_a_symlink_file(
    tmp_path: Path,
    nominal_report: FirstPowerOnReport,
) -> None:
    destination = save_first_power_on_checkpoint(
        tmp_path,
        Path("real.json"),
        nominal_report,
    )
    link = tmp_path / "linked.json"
    _symlink_or_skip(link, destination.name, target_is_directory=False)

    with pytest.raises(FirstPowerOnError, match="symlink"):
        load_first_power_on_checkpoint(tmp_path, link)


def test_rehearsal_rejects_a_bound_source_symlink(
    tmp_path: Path,
    nominal_report: FirstPowerOnReport,
) -> None:
    workspace = tmp_path / "workspace"
    for relative, _digest in nominal_report.source_bindings:
        if relative.startswith("@runtime/"):
            continue
        destination = workspace / relative
        destination.parent.mkdir(parents=True, exist_ok=True)
        shutil.copyfile(WORKSPACE / relative, destination)
    linked_source = workspace / "software/config/arm_connection.json"
    real_source = linked_source.with_name("arm_connection.real.json")
    linked_source.replace(real_source)
    _symlink_or_skip(linked_source, real_source.name, target_is_directory=False)

    with pytest.raises(FirstPowerOnError, match="onboarding source.*symlink"):
        run_first_power_on_rehearsal(workspace)


def test_checkpoint_save_rejects_a_symlink_parent(
    tmp_path: Path,
    nominal_report: FirstPowerOnReport,
) -> None:
    real_parent = tmp_path / "real-parent"
    real_parent.mkdir()
    linked_parent = tmp_path / "linked-parent"
    _symlink_or_skip(linked_parent, real_parent, target_is_directory=True)

    with pytest.raises(FirstPowerOnError, match="symlink"):
        save_first_power_on_checkpoint(
            tmp_path,
            linked_parent / "checkpoint.json",
            nominal_report,
        )
    assert not (real_parent / "checkpoint.json").exists()
