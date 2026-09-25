from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib
import json
from pathlib import Path
from types import SimpleNamespace
from types import MappingProxyType
from typing import Any, Mapping, cast

import pytest

from rocell.application.prehardware_qualification import (
    MAX_QUALIFICATION_CAMERA_CAPTURES,
    MAX_QUALIFICATION_CASES,
    MAX_QUALIFICATION_LEGACY_EVENTS,
    MAX_QUALIFICATION_SESSION_RUNS,
    MAX_QUALIFICATION_VIRTUAL_COMMANDS,
    PREHARDWARE_QUALIFICATION_CATALOG,
    PREHARDWARE_QUALIFICATION_SCHEMA,
    PrehardwareQualificationError,
    PrehardwareQualificationPolicy,
    QualificationCaseResult,
    QualificationCaseSpec,
    default_qualification_case_specs,
)
from rocell.simulation import VirtualFaultKind


EXPECTED_QUICK_CASE_IDS = (
    "startup.integrity",
    "adaptive.keyboard.offset_x_plus_12mm",
    "adaptive.phone.offset_x_plus_8mm",
    "fault.camera_tag_loss.keyboard",
    "determinism.keyboard.offset_x_plus_12mm",
)

EXPECTED_STANDARD_CASE_IDS = (
    "startup.integrity",
    "adaptive.keyboard.nominal",
    "adaptive.phone.nominal",
    "adaptive.keyboard.offset_x_plus_12mm",
    "adaptive.phone.offset_x_plus_8mm",
    "adaptive.keyboard.offset_x_plus_16mm_rejected",
    "fault.arm_connect.keyboard",
    "fault.arm_reference.keyboard",
    "fault.arm_stall.keyboard",
    "fault.camera_unavailable.keyboard",
    "fault.camera_tag_loss.keyboard",
    "fault.contact_missed.keyboard",
    "fault.keyboard_double",
    "fault.phone_wrong_ui",
    "fault.focus_lost.phone",
    "determinism.keyboard.offset_x_plus_12mm",
    "coverage.locked_catalog",
)

EXPECTED_FAULT_KINDS = {
    "ARM_CONNECT_FAILURE",
    "ARM_REFERENCE_FAILURE",
    "ARM_STALL",
    "CAMERA_UNAVAILABLE",
    "CAMERA_TAG_LOSS",
    "KEYBOARD_MISSED_CONTACT",
    "KEYBOARD_DOUBLE_CONTACT",
    "ANDROID_WRONG_UI_STATE",
    "DEVICE_FOCUS_LOST",
}


def _sha256(value: str) -> str:
    return hashlib.sha256(value.encode("utf-8")).hexdigest()


def _mapping_nodes(value: object) -> list[Mapping[str, Any]]:
    found: list[Mapping[str, Any]] = []
    if isinstance(value, Mapping):
        found.append(value)
        for child in value.values():
            found.extend(_mapping_nodes(child))
    elif isinstance(value, (tuple, list)):
        for child in value:
            found.extend(_mapping_nodes(child))
    return found


def _assert_zero_authority(value: object) -> None:
    """Reject an authority escalation at any retained evidence depth."""

    for node in _mapping_nodes(value):
        if "simulation_only" in node:
            assert node["simulation_only"] is True
        for key in (
            "execution_authorized",
            "hardware_accessed",
            "live_motion_authorized",
            "physical_contact_authorized",
            "contact_authorized",
            "can_release_physical_gates",
        ):
            if key in node:
                assert node[key] is False
        if "hardware_commands_generated" in node:
            assert node["hardware_commands_generated"] == 0
        if "physical_release_effect" in node:
            assert node["physical_release_effect"] == "NONE"


def _case(profile: str, case_id: str) -> QualificationCaseSpec:
    return next(
        case
        for case in default_qualification_case_specs(profile)
        if case.case_id == case_id
    )


class _AdaptiveReportDouble:
    """Structural test double for the aggregate orchestration boundary."""

    def __init__(
        self,
        identity: str,
        *,
        pipeline_completed: bool = True,
        fault_reason: str | None = None,
        correction_count: int = 1,
        contact_count: int = 1,
        document_variant: str = "stable",
        nested_authority_escalation: bool = False,
        forced_hash: str | None = None,
    ) -> None:
        self.identity = identity
        self.pipeline_completed = pipeline_completed
        self.fault_reason = fault_reason
        self.status = (
            "ADAPTIVE_VIRTUAL_SESSION_COMPLETE_WITH_PHYSICAL_HOLDS"
            if pipeline_completed
            else "ADAPTIVE_VIRTUAL_SESSION_FAULTED"
        )
        self.outcome_verified = pipeline_completed
        self.ended_at_park = pipeline_completed
        self.arm_document = {"lifecycle": "CLOSED"}
        self.correction_installations = tuple(object() for _ in range(correction_count))
        self.contact_attempts = tuple(object() for _ in range(contact_count))
        self.executions = (object(), object())
        decision_statuses: tuple[str, ...]
        if not pipeline_completed and fault_reason and "CORRECTION_REJECTED" in fault_reason:
            decision_statuses = ("REJECT",)
        elif correction_count == 0:
            decision_statuses = ("NO_CHANGE",)
        else:
            decision_statuses = ("APPLY", "NO_CHANGE")
        self.vision_attempts = tuple(
            SimpleNamespace(
                decision=SimpleNamespace(status=SimpleNamespace(value=status))
            )
            for status in decision_statuses
        )
        self.phone_verifications: tuple[object, ...] = ()
        self.document_variant = document_variant
        self.nested_authority_escalation = nested_authority_escalation
        self.report_hash = forced_hash or _sha256(
            "|".join(
                (
                    identity,
                    str(pipeline_completed),
                    str(fault_reason),
                    str(correction_count),
                    str(contact_count),
                    document_variant,
                )
            )
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "test.adaptive_report.v1",
            "simulation_only": True,
            "identity": self.identity,
            "document_variant": self.document_variant,
            "nested": {
                "execution_authorized": self.nested_authority_escalation,
                "hardware_commands_generated": 0,
            },
            "authority": {
                "simulation_only": True,
                "execution_authorized": False,
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
                "physical_release_effect": "NONE",
            },
            "report_sha256": self.report_hash,
        }


class _LegacyReportDouble:
    def __init__(
        self,
        kind: VirtualFaultKind,
        *,
        trigger_id: str,
        closed: bool = True,
        consume_trigger: bool = True,
        fault_reason: str | None = None,
        nested_authority_escalation: bool = False,
    ) -> None:
        self.status = "VIRTUAL_SESSION_FAULTED"
        self.pipeline_completed = False
        self.fault_reason = fault_reason or (
            "ANDROID_UI_STATE_REJECTED"
            if kind is VirtualFaultKind.ANDROID_WRONG_UI_STATE
            else kind.value
        )
        self.outcome_verified = False
        self.ended_at_park = False
        self.final_fault_script = SimpleNamespace(
            consumed_trigger_ids=(
                frozenset({trigger_id}) if consume_trigger else frozenset()
            ),
            unconsumed_trigger_ids=() if consume_trigger else (trigger_id,),
        )
        self.lifecycle_history = (
            SimpleNamespace(value="FAULTED"),
            SimpleNamespace(value="CLOSED" if closed else "FAULTED"),
        )
        self.arm_document = {"lifecycle": "CLOSED" if closed else "FAULT"}
        self.ledger = SimpleNamespace(
            virtual_commands_executed=2,
            events=(object(), object()),
        )
        self.nested_authority_escalation = nested_authority_escalation
        self.report_hash = _sha256(
            f"legacy|{kind.value}|{closed}|{consume_trigger}|{self.fault_reason}"
        )

    def to_dict(self) -> dict[str, object]:
        return {
            "schema": "test.legacy_report.v1",
            "simulation_only": True,
            "arm": {
                "execution_authorized": self.nested_authority_escalation,
                "hardware_commands_generated": 0,
            },
            "authority": {
                "simulation_only": True,
                "execution_authorized": False,
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
                "physical_release_effect": "NONE",
            },
            "report_sha256": self.report_hash,
        }


class _CoverageReportDouble:
    def __init__(
        self,
        *,
        complete: bool = True,
        accepted_count: int = 75,
    ) -> None:
        self.complete_catalog_evidence = complete
        self.routes = tuple(
            SimpleNamespace(accepted=index < accepted_count) for index in range(75)
        )
        self.all_routes_accepted = complete and accepted_count == 75
        self.status = (
            "MISSION_ROUTE_COVERAGE_DIAGNOSTIC_PASS_WITH_UNSUPPORTED_CHECKS"
            if self.all_routes_accepted
            else "MISSION_ROUTE_COVERAGE_DIAGNOSTIC_GAPS_REPORTED"
        )
        self.total_waypoint_records = 750
        self.total_ik_solves = 750
        self.total_task_jacobian_fk_evaluations = 1_500
        self.report_hash = _sha256(f"coverage|{complete}|{accepted_count}")

    def to_dict(self) -> dict[str, object]:
        accepted_count = sum(route.accepted for route in self.routes)
        return {
            "schema": "test.coverage_report.v1",
            "simulation_only": True,
            "execution_authorized": False,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "physical_release_effect": "NONE",
            "device_summary": {
                "keyboard": {
                    "route_count": 46,
                    "accepted_route_count": min(46, accepted_count),
                },
                "phone": {
                    "route_count": 29,
                    "accepted_route_count": max(0, accepted_count - 46),
                },
            },
        }


def _bootstrap_double() -> SimpleNamespace:
    snapshot = SimpleNamespace(
        manifest_id="TEST-FREEZE-008",
        manifest_sha256="1" * 64,
        snapshot_hash="2" * 64,
        design_revision="RC03-INT-R1",
        active_build_id="TEST-BUILD-001",
        hard_blockers=("PHYSICAL_RELEASE_UNRELEASED",),
    )
    bundle = SimpleNamespace(
        bundle_id="TEST-SIMULATION-BUNDLE",
        source_lock_sha256="3" * 64,
    )
    alignment = SimpleNamespace(
        status="PASS_NOMINAL_ALIGNMENT_WITH_PHYSICAL_HOLDS",
        report_hash="4" * 64,
    )
    context = SimpleNamespace(
        snapshot=snapshot,
        bundle_lock=bundle,
        alignment=alignment,
    )
    return SimpleNamespace(
        context=context,
        simulation_ready=True,
        status="VIRTUAL_WORKCELL_READY_WITH_DECLARED_GAPS",
        bootstrap_hash="5" * 64,
        checks=(
            SimpleNamespace(status="PASS"),
            SimpleNamespace(status="DECLARED_GAP"),
        ),
        collision_readiness=SimpleNamespace(
            geometry_audit=SimpleNamespace(diagnostic_ready=False)
        ),
        calibration_inventory=SimpleNamespace(
            missing_requirement_ids=("camera_intrinsics",)
        ),
        to_dict=lambda: {
            "schema": "test.bootstrap.v1",
            "simulation_only": True,
            "authority": {
                "simulation_only": True,
                "execution_authorized": False,
                "hardware_accessed": False,
                "hardware_commands_generated": 0,
                "physical_release_effect": "NONE",
            },
        },
    )


def _profile_double() -> SimpleNamespace:
    return SimpleNamespace(
        profile_id="test-virtual-profile",
        source_sha256="6" * 64,
        status="UNMEASURED_SENSITIVITY_OVERLAY",
        simulation_only=True,
        physical_release_effect="NONE",
        study_input=SimpleNamespace(study_input_id="test-study-input"),
        park_point_board=SimpleNamespace(x=290.0, y=10.0, z=70.0),
        park_probe_id="test-park-probe",
        source_layout_report_hash="7" * 64,
        source_mission_route_coverage_hash="8" * 64,
    )


class _QualificationHarness:
    def __init__(
        self,
        *,
        profile: str,
        coverage_accepted_count: int = 75,
        legacy_closed: bool = True,
        legacy_consume_trigger: bool = True,
        legacy_reason_override: Mapping[VirtualFaultKind, str] | None = None,
        adaptive_nested_authority_escalation_at: int | None = None,
        replay_document_mismatch: bool = False,
    ) -> None:
        self.profile = profile
        self.bootstrap = _bootstrap_double()
        self.virtual_profile = _profile_double()
        self.coverage_accepted_count = coverage_accepted_count
        self.legacy_closed = legacy_closed
        self.legacy_consume_trigger = legacy_consume_trigger
        self.legacy_reason_override = legacy_reason_override or {}
        self.adaptive_nested_authority_escalation_at = (
            adaptive_nested_authority_escalation_at
        )
        self.replay_document_mismatch = replay_document_mismatch
        self.bootstrap_calls: list[tuple[Path, Path | None]] = []
        self.profile_calls: list[object] = []
        self.adaptive_calls = 0
        self.virtual_calls: list[VirtualFaultKind] = []
        self.route_calls = 0
        self.revalidation_calls = 0

    def bootstrap_runner(
        self, workspace: Path, runtime_path: Path | None
    ) -> SimpleNamespace:
        self.bootstrap_calls.append((workspace, runtime_path))
        return self.bootstrap

    def profile_loader(self, context: object) -> SimpleNamespace:
        self.profile_calls.append(context)
        return self.virtual_profile

    def _standard_adaptive_report(self, index: int) -> _AdaptiveReportDouble:
        definitions = (
            ("keyboard-nominal", True, None, 0, 1),
            ("phone-nominal", True, None, 0, 1),
            ("keyboard-x12", True, None, 1, 1),
            ("phone-x8", True, None, 1, 1),
            (
                "keyboard-x16-reject",
                False,
                "BOARD_POSE_CORRECTION_REJECTED:TRANSLATION_DELTA_LIMIT_EXCEEDED",
                0,
                0,
            ),
            # Determinism operand B must be identical to operand A at index 2.
            ("keyboard-x12", True, None, 1, 1),
        )
        identity, completed, reason, corrections, contacts = definitions[index]
        variant = "stable"
        forced_hash = None
        if index == len(definitions) - 1 and self.replay_document_mismatch:
            variant = "changed-document"
            # Force a hash collision-like test condition: full-document
            # equality must still be checked independently.
            forced_hash = _sha256("keyboard-x12|True|None|1|1|stable")
        return _AdaptiveReportDouble(
            identity,
            pipeline_completed=completed,
            fault_reason=reason,
            correction_count=corrections,
            contact_count=contacts,
            document_variant=variant,
            forced_hash=forced_hash,
            nested_authority_escalation=(
                self.adaptive_nested_authority_escalation_at == index
            ),
        )

    def _quick_adaptive_report(self, index: int) -> _AdaptiveReportDouble:
        definitions = (
            ("keyboard-x12", 1),
            ("phone-x8", 1),
            ("keyboard-x12", 1),
        )
        identity, corrections = definitions[index]
        variant = (
            "changed-document"
            if index == 2 and self.replay_document_mismatch
            else "stable"
        )
        forced_hash = (
            _sha256("keyboard-x12|True|None|1|1|stable")
            if index == 2 and self.replay_document_mismatch
            else None
        )
        return _AdaptiveReportDouble(
            identity,
            correction_count=corrections,
            document_variant=variant,
            forced_hash=forced_hash,
            nested_authority_escalation=(
                self.adaptive_nested_authority_escalation_at == index
            ),
        )

    def adaptive_runner(self, *_args: object, **_kwargs: object) -> _AdaptiveReportDouble:
        index = self.adaptive_calls
        self.adaptive_calls += 1
        if self.profile == "quick":
            return self._quick_adaptive_report(index)
        return self._standard_adaptive_report(index)

    def virtual_runner(self, *_args: object, **kwargs: object) -> _LegacyReportDouble:
        script = cast(Any, kwargs["fault_script"])
        trigger = script.triggers[0]
        kind = trigger.kind
        self.virtual_calls.append(kind)
        return _LegacyReportDouble(
            kind,
            trigger_id=trigger.trigger_id,
            closed=self.legacy_closed,
            consume_trigger=self.legacy_consume_trigger,
            fault_reason=self.legacy_reason_override.get(kind),
        )

    def route_runner(self, *_args: object, **_kwargs: object) -> _CoverageReportDouble:
        self.route_calls += 1
        return _CoverageReportDouble(accepted_count=self.coverage_accepted_count)

    def revalidator(self, bootstrap: object) -> None:
        assert bootstrap is self.bootstrap
        self.revalidation_calls += 1


def _run_harness(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    harness: _QualificationHarness,
    *,
    policy: PrehardwareQualificationPolicy | None = None,
) -> Any:
    import rocell.application.prehardware_qualification as qualification

    monkeypatch.setattr(
        qualification,
        "make_hidden_virtual_board_truth",
        lambda *_args, **_kwargs: object(),
    )
    selected_policy = policy or PrehardwareQualificationPolicy(profile=harness.profile)
    return qualification._run_prehardware_qualification_with_runners(
        tmp_path,
        policy=selected_policy,
        runtime_path=Path("software/config/runtime.json"),
        bootstrap_runner=cast(Any, harness.bootstrap_runner),
        profile_loader=cast(Any, harness.profile_loader),
        adaptive_runner=cast(Any, harness.adaptive_runner),
        virtual_runner=cast(Any, harness.virtual_runner),
        route_runner=cast(Any, harness.route_runner),
        revalidator=harness.revalidator,
    )


def test_locked_case_catalog_has_exact_order_and_profile_membership() -> None:
    quick = default_qualification_case_specs("quick")
    standard = default_qualification_case_specs("standard")

    assert tuple(case.case_id for case in quick) == EXPECTED_QUICK_CASE_IDS
    assert tuple(case.case_id for case in standard) == EXPECTED_STANDARD_CASE_IDS
    assert len(set(EXPECTED_STANDARD_CASE_IDS)) == len(EXPECTED_STANDARD_CASE_IDS)
    assert set(EXPECTED_QUICK_CASE_IDS).issubset(EXPECTED_STANDARD_CASE_IDS)
    assert all("quick" in case.profiles for case in quick)
    assert all("standard" in case.profiles for case in standard)

    # Every bounded CLI fault profile is rehearsed exactly once on a compatible
    # device in the standard campaign. Camera faults here intentionally use the
    # legacy fixed-overview service; moving-camera capture faults remain a
    # separately disclosed gap until that adaptive injection surface exists.
    fault_cases = tuple(
        case for case in standard if case.category == "LEGACY_FAULT_SESSION"
    )
    assert {case.fault_kind.value for case in fault_cases if case.fault_kind} == (
        EXPECTED_FAULT_KINDS
    )
    assert len(fault_cases) == len(EXPECTED_FAULT_KINDS)
    assert all(
        case.device == "keyboard"
        for case in fault_cases
        if case.fault_component == "keyboard"
    )
    assert all(
        case.device == "phone"
        for case in fault_cases
        if case.fault_component == "android"
    )


def test_adaptive_matrix_has_deterministic_nominal_correction_and_reject_cases() -> None:
    adaptive = tuple(
        case
        for case in default_qualification_case_specs("standard")
        if case.category == "ADAPTIVE_SESSION"
    )

    assert tuple(
        (
            case.device,
            case.truth_translation_Wv_mm,
            case.truth_yaw_board_deg,
            case.expected_outcome,
            case.expected_correction_count,
            case.maximum_contact_attempts,
        )
        for case in adaptive
    ) == (
        ("keyboard", (0.0, 0.0, 0.0), 0.0, "COMPLETE", 0, None),
        ("phone", (0.0, 0.0, 0.0), 0.0, "COMPLETE", 0, None),
        ("keyboard", (12.0, 0.0, 0.0), 0.0, "COMPLETE", 1, None),
        ("phone", (8.0, 0.0, 0.0), 0.0, "COMPLETE", 1, None),
        ("keyboard", (16.0, 0.0, 0.0), 0.0, "FAIL_STOP", 0, 0),
    )
    rejected = adaptive[4]
    assert rejected.expected_fault_reason == (
        "BOARD_POSE_CORRECTION_REJECTED:TRANSLATION_DELTA_LIMIT_EXCEEDED"
    )


def test_phone_wrong_ui_names_observed_fault_separately_from_trigger_kind() -> None:
    spec = _case("standard", "fault.phone_wrong_ui")

    assert spec.fault_kind is not None
    assert spec.fault_kind.value == "ANDROID_WRONG_UI_STATE"
    assert spec.expected_fault_reason == "ANDROID_UI_STATE_REJECTED"
    assert spec.fault_component == "android"
    assert spec.fault_operation == "verify_state"


def test_policy_is_deterministic_hash_bound_and_explicit_about_quick_coverage() -> None:
    quick = PrehardwareQualificationPolicy(profile="quick")
    replay = PrehardwareQualificationPolicy(profile="quick")
    standard = PrehardwareQualificationPolicy(profile="standard")
    document = quick.to_dict()

    assert quick.policy_hash == replay.policy_hash
    assert quick.to_dict() == replay.to_dict()
    assert document["schema"] == "rocell.prehardware_qualification_policy.v1"
    assert document["catalog_id"] == PREHARDWARE_QUALIFICATION_CATALOG
    assert document["profile"] == "quick"
    assert document["selected_case_count"] == len(EXPECTED_QUICK_CASE_IDS)
    assert document["includes_full_catalog_coverage"] is False
    assert standard.includes_full_catalog_coverage is True
    assert standard.policy_hash != quick.policy_hash
    assert len(quick.policy_hash) == 64
    assert document["wall_clock_time_is_evidence"] is False


@pytest.mark.parametrize(
    ("field_name", "invalid"),
    (
        ("maximum_cases", 0),
        ("maximum_cases", True),
        ("maximum_cases", MAX_QUALIFICATION_CASES + 1),
        ("maximum_session_runs", 0),
        ("maximum_session_runs", True),
        ("maximum_session_runs", MAX_QUALIFICATION_SESSION_RUNS + 1),
        ("maximum_total_virtual_commands", 0),
        ("maximum_total_virtual_commands", True),
        (
            "maximum_total_virtual_commands",
            MAX_QUALIFICATION_VIRTUAL_COMMANDS + 1,
        ),
        ("maximum_total_camera_captures", 0),
        ("maximum_total_camera_captures", True),
        (
            "maximum_total_camera_captures",
            MAX_QUALIFICATION_CAMERA_CAPTURES + 1,
        ),
        ("maximum_total_legacy_events", 0),
        ("maximum_total_legacy_events", True),
        (
            "maximum_total_legacy_events",
            MAX_QUALIFICATION_LEGACY_EVENTS + 1,
        ),
    ),
)
def test_policy_rejects_non_integer_underflow_and_hard_cap_bypass(
    field_name: str,
    invalid: object,
) -> None:
    with pytest.raises(PrehardwareQualificationError):
        cast(Any, PrehardwareQualificationPolicy)(**{field_name: invalid})


@pytest.mark.parametrize("profile", ("", "full", "STANDARD", True, None))
def test_policy_rejects_unknown_profile(profile: object) -> None:
    with pytest.raises(PrehardwareQualificationError):
        PrehardwareQualificationPolicy(profile=profile)  # type: ignore[arg-type]


def test_policy_rejects_limits_below_its_fixed_selected_catalog() -> None:
    with pytest.raises(
        PrehardwareQualificationError,
        match="selected qualification profile exceeds maximum_cases",
    ):
        PrehardwareQualificationPolicy(
            profile="quick",
            maximum_cases=len(EXPECTED_QUICK_CASE_IDS) - 1,
        )

    # Quick executes three adaptive sessions: two declared cases and one fresh
    # determinism operand. Counting cases rather than invocations would let a
    # campaign silently exceed this bound.
    with pytest.raises(
        PrehardwareQualificationError,
        match="maximum_session_runs",
    ):
        PrehardwareQualificationPolicy(
            profile="quick",
            maximum_session_runs=2,
        )


@pytest.mark.parametrize(
    ("field_name", "invalid"),
    (
        ("truth_translation_Wv_mm", (0.0, 0.0)),
        ("truth_translation_Wv_mm", (float("nan"), 0.0, 0.0)),
        ("truth_translation_Wv_mm", (True, 0.0, 0.0)),
        ("truth_translation_Wv_mm", (100.001, 0.0, 0.0)),
        ("truth_yaw_board_deg", float("inf")),
        ("truth_yaw_board_deg", True),
        ("truth_yaw_board_deg", 30.001),
        ("expected_correction_count", True),
        ("expected_correction_count", 2),
        ("maximum_contact_attempts", True),
        ("maximum_contact_attempts", 5),
    ),
)
def test_case_spec_rejects_nonfinite_or_out_of_bounds_controls(
    field_name: str,
    invalid: object,
) -> None:
    valid = _case("standard", "adaptive.keyboard.offset_x_plus_12mm")

    with pytest.raises(PrehardwareQualificationError):
        replace(valid, **cast(Any, {field_name: invalid}))


def test_case_spec_redacts_text_and_hidden_truth_but_hashes_private_input() -> None:
    offset = _case("quick", "adaptive.keyboard.offset_x_plus_12mm")
    nominal = _case("standard", "adaptive.keyboard.nominal")
    document = offset.to_dict()

    assert document["requested_text"] == {
        "sha256": _sha256("a"),
        "normalized_codepoint_length": 1,
        "plaintext_serialized": False,
    }
    assert document["synthetic_truth_injection"] == {
        "scope": "HIDDEN_VIRTUAL_PLANT_SIMULATION_ONLY",
        "transform_serialized": False,
        "processor_received_transform": False,
    }
    assert "truth_translation_Wv_mm" not in document
    assert "truth_yaw_board_deg" not in document
    assert offset.spec_hash == document["case_spec_sha256"]
    assert offset.spec_hash != nominal.spec_hash
    assert offset.to_dict() == replace(offset).to_dict()


def test_case_result_is_recursively_immutable_detached_and_hash_bound() -> None:
    spec = _case("quick", "startup.integrity")
    mutable_metrics: dict[str, object] = {
        "nested": {"values": [1, 2]},
        "hardware_commands_generated": 0,
    }
    result = QualificationCaseResult(
        spec=spec,
        observed_status="READY",
        passed=True,
        source_report_sha256="a" * 64,
        authority_verified=True,
        metrics=mutable_metrics,
    )
    original_hash = result.result_hash

    mutable_metrics["nested"] = {"values": [999]}
    public = result.to_dict()
    public_metrics = public["metrics"]
    assert isinstance(public_metrics, dict)
    public_metrics["nested"] = {"values": [888]}
    assert result.result_hash == original_hash
    assert result.to_dict()["metrics"] == {
        "nested": {"values": [1, 2]},
        "hardware_commands_generated": 0,
    }
    assert isinstance(result.metrics, MappingProxyType)
    with pytest.raises(TypeError):
        result.metrics["mutated"] = True  # type: ignore[index]
    with pytest.raises(FrozenInstanceError):
        result.passed = False  # type: ignore[misc]

    changed = replace(
        result,
        metrics={"nested": {"values": [1, 3]}, "hardware_commands_generated": 0},
    )
    assert changed.result_hash != original_hash


def test_case_result_rejects_invalid_hash_and_authority_escalation() -> None:
    spec = _case("quick", "startup.integrity")

    with pytest.raises(PrehardwareQualificationError, match="SHA-256"):
        QualificationCaseResult(
            spec,
            "READY",
            False,
            "A" * 64,
            True,
            {},
        )
    with pytest.raises(PrehardwareQualificationError, match="zero authority"):
        QualificationCaseResult(
            spec,
            "READY",
            True,
            "a" * 64,
            False,
            {},
        )


def test_schema_name_is_stable_and_json_safe() -> None:
    assert PREHARDWARE_QUALIFICATION_SCHEMA == "rocell.prehardware_qualification.v1"
    policy_document = PrehardwareQualificationPolicy(profile="quick").to_dict()
    encoded = json.dumps(
        policy_document,
        sort_keys=True,
        separators=(",", ":"),
        allow_nan=False,
    )
    assert "NaN" not in encoded
    _assert_zero_authority(policy_document)


def test_quick_campaign_runs_locked_smoke_matrix_and_marks_coverage_not_run(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _QualificationHarness(profile="quick")

    report = _run_harness(tmp_path, monkeypatch, harness)
    document = report.to_dict()

    assert report.profile == "quick"
    assert report.campaign_passed is True
    assert report.diagnostic_pass is True
    assert report.coverage_state == "NOT_RUN"
    assert report.coverage_evaluated is False
    assert report.all_mission_routes_accepted is False
    assert report.physical_ready is False
    assert report.status == (
        "PREHARDWARE_QUALIFICATION_PASS_WITH_UNEVALUATED_"
        "CATALOG_AND_PHYSICAL_HOLDS"
    )
    assert tuple(case.spec.case_id for case in report.case_results) == (
        EXPECTED_QUICK_CASE_IDS
    )
    assert all(case.passed for case in report.case_results)
    assert harness.bootstrap_calls == [
        (tmp_path.resolve(), Path("software/config/runtime.json"))
    ]
    assert harness.profile_calls == [harness.bootstrap.context]
    assert harness.adaptive_calls == 3
    assert harness.virtual_calls == [VirtualFaultKind.CAMERA_TAG_LOSS]
    assert harness.route_calls == 0
    assert harness.revalidation_calls == 1

    by_id = {case.spec.case_id: case for case in report.case_results}
    camera_fault = by_id["fault.camera_tag_loss.keyboard"]
    assert camera_fault.passed
    assert camera_fault.metrics["pipeline_completed"] is False
    assert camera_fault.metrics["fault_trigger_consumed"] is True
    assert camera_fault.metrics["closed_after_fail_stop"] is True
    assert camera_fault.metrics["camera_path"] == (
        "LEGACY_FIXED_OVERVIEW_PIXEL_SERVICE"
    )
    determinism = by_id["determinism.keyboard.offset_x_plus_12mm"]
    assert determinism.metrics["byte_canonical_report_hash_identical"] is True
    assert determinism.metrics["full_child_document_identical"] is True
    assert determinism.metrics["reference_report_sha256"] == (
        determinism.metrics["replay_report_sha256"]
    )
    assert document["case_summary"] == {
        "selected": 5,
        "passed": 5,
        "failed": 0,
        "expected_fail_stop_cases": 1,
    }
    assert document["coverage_summary"]["state"] == "NOT_RUN"
    assert document["coverage_summary"]["reason"] == (
        "QUICK_PROFILE_DOES_NOT_RECOMPUTE_MULTI_MINUTE_75_ROUTE_SCREEN"
    )
    assert document["resource_usage"]["session_run_count"] == 4
    assert document["resource_usage"]["hardware_commands_generated"] == 0
    assert document["final_source_revalidation_passed"] is True
    assert document["physical_holds"]
    assert document["evidence_recording"] == {
        "recorded": False,
        "replay_supported": False,
        "reason": "QUALIFICATION_EVIDENCE_PACKAGE_SCHEMA_NOT_IMPLEMENTED",
    }
    _assert_zero_authority(document)


def test_standard_campaign_runs_all_faults_and_fresh_75_route_coverage(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _QualificationHarness(profile="standard")

    report = _run_harness(tmp_path, monkeypatch, harness)
    document = report.to_dict()

    assert report.profile == "standard"
    assert report.campaign_passed is True
    assert report.coverage_evaluated is True
    assert report.coverage_state == "ALL_ROUTES_ACCEPTED"
    assert report.all_mission_routes_accepted is True
    assert report.physical_ready is False
    assert report.status == "PREHARDWARE_QUALIFICATION_PASS_WITH_PHYSICAL_HOLDS"
    assert tuple(case.spec.case_id for case in report.case_results) == (
        EXPECTED_STANDARD_CASE_IDS
    )
    assert all(case.passed for case in report.case_results)
    assert harness.adaptive_calls == 6
    assert set(harness.virtual_calls) == {
        VirtualFaultKind(value) for value in EXPECTED_FAULT_KINDS
    }
    assert len(harness.virtual_calls) == 9
    assert harness.route_calls == 1
    assert harness.revalidation_calls == 1

    coverage = document["coverage_summary"]
    assert coverage["complete_catalog_evidence"] is True
    assert coverage["route_count"] == 75
    assert coverage["accepted_route_count"] == 75
    assert coverage["rejected_route_count"] == 0
    assert coverage["keyboard"]["route_count"] == 46
    assert coverage["phone"]["route_count"] == 29
    assert coverage["all_routes_accepted"] is True
    assert coverage["coverage_report_sha256"] == _sha256("coverage|True|75")
    assert coverage["selected_profile_source_coverage_sha256"] == "8" * 64
    assert document["source"]["virtual_profile_sha256"] == "6" * 64
    assert document["source"]["historical_mission_coverage_sha256"] == "8" * 64
    assert document["source"]["virtual_profile_classification"] == (
        "UNMEASURED_SENSITIVITY_OVERLAY"
    )
    assert document["resource_usage"]["mission_route_count"] == 75
    assert document["case_summary"]["expected_fail_stop_cases"] == 10
    _assert_zero_authority(document)


def test_expected_fail_stop_is_a_passing_case_not_a_completed_child_session(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _run_harness(
        tmp_path,
        monkeypatch,
        _QualificationHarness(profile="standard"),
    )
    fail_stop_cases = tuple(
        case
        for case in report.case_results
        if case.spec.expected_outcome == "FAIL_STOP"
    )

    assert len(fail_stop_cases) == 10
    assert all(case.passed for case in fail_stop_cases)
    assert all(case.metrics["pipeline_completed"] is False for case in fail_stop_cases)
    assert all(case.metrics["fault_reason"] for case in fail_stop_cases)


def test_one_rejected_route_fails_standard_campaign_but_preserves_coverage_state(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _QualificationHarness(
        profile="standard",
        coverage_accepted_count=74,
    )

    report = _run_harness(tmp_path, monkeypatch, harness)
    coverage_case = next(
        case
        for case in report.case_results
        if case.spec.category == "MISSION_ROUTE_COVERAGE"
    )

    assert coverage_case.passed is False
    assert coverage_case.metrics["complete_catalog_evidence"] is True
    assert coverage_case.metrics["all_routes_accepted"] is False
    assert report.campaign_passed is False
    assert report.coverage_evaluated is True
    assert report.coverage_state == "ROUTE_GAPS_REPORTED"
    assert report.all_mission_routes_accepted is False
    assert report.physical_ready is False
    assert report.status == "PREHARDWARE_QUALIFICATION_FAILED"


@pytest.mark.parametrize(
    ("closed", "consumed"),
    ((False, True), (True, False)),
)
def test_legacy_fault_pass_requires_closed_arm_and_exact_trigger_consumption(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    closed: bool,
    consumed: bool,
) -> None:
    harness = _QualificationHarness(
        profile="quick",
        legacy_closed=closed,
        legacy_consume_trigger=consumed,
    )

    report = _run_harness(tmp_path, monkeypatch, harness)
    fault_case = next(
        case
        for case in report.case_results
        if case.spec.category == "LEGACY_FAULT_SESSION"
    )

    assert fault_case.passed is False
    assert fault_case.metrics["closed_after_fail_stop"] is closed
    assert fault_case.metrics["fault_trigger_consumed"] is consumed
    assert report.campaign_passed is False


def test_wrong_fault_reason_fails_case_even_when_child_faulted_and_closed(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _QualificationHarness(
        profile="quick",
        legacy_reason_override={
            VirtualFaultKind.CAMERA_TAG_LOSS: "CAMERA_UNAVAILABLE"
        },
    )

    report = _run_harness(tmp_path, monkeypatch, harness)
    fault_case = next(
        case
        for case in report.case_results
        if case.spec.category == "LEGACY_FAULT_SESSION"
    )

    assert fault_case.metrics["fault_reason"] == "CAMERA_UNAVAILABLE"
    assert fault_case.passed is False
    assert report.campaign_passed is False


def test_nested_child_authority_escalation_is_detected_recursively(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _QualificationHarness(
        profile="quick",
        adaptive_nested_authority_escalation_at=0,
    )

    report = _run_harness(tmp_path, monkeypatch, harness)
    shifted_keyboard = report.case_results[1]

    assert shifted_keyboard.spec.case_id == (
        "adaptive.keyboard.offset_x_plus_12mm"
    )
    assert shifted_keyboard.authority_verified is False
    assert shifted_keyboard.passed is False
    assert report.campaign_passed is False
    assert report.physical_ready is False


def test_determinism_requires_full_child_document_not_only_same_hash(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    harness = _QualificationHarness(
        profile="quick",
        replay_document_mismatch=True,
    )

    report = _run_harness(tmp_path, monkeypatch, harness)
    determinism = next(
        case
        for case in report.case_results
        if case.spec.category == "DETERMINISM_REPLAY"
    )

    assert determinism.metrics["reference_report_sha256"] == (
        determinism.metrics["replay_report_sha256"]
    )
    assert determinism.metrics["full_child_document_identical"] is False
    assert determinism.passed is False
    assert report.campaign_passed is False


@pytest.mark.parametrize(
    ("policy_field", "expected_resource"),
    (
        ("maximum_total_virtual_commands", "virtual_commands_executed"),
        ("maximum_total_camera_captures", "camera_capture_count"),
        ("maximum_total_legacy_events", "legacy_event_count"),
    ),
)
def test_actual_resource_usage_cannot_exceed_policy(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
    policy_field: str,
    expected_resource: str,
) -> None:
    harness = _QualificationHarness(profile="quick")
    policy = cast(Any, PrehardwareQualificationPolicy)(
        profile="quick",
        **{policy_field: 1},
    )

    with pytest.raises(
        PrehardwareQualificationError,
        match=f"qualification resource {expected_resource} exceeded",
    ):
        _run_harness(
            tmp_path,
            monkeypatch,
            harness,
            policy=policy,
        )


def test_unexpected_dependency_error_aborts_instead_of_returning_partial_pass(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.prehardware_qualification as qualification

    harness = _QualificationHarness(profile="quick")

    def explode(*_args: object, **_kwargs: object) -> object:
        raise RuntimeError("injected dependency failure")

    monkeypatch.setattr(
        qualification,
        "make_hidden_virtual_board_truth",
        lambda *_args, **_kwargs: object(),
    )
    with pytest.raises(RuntimeError, match="injected dependency failure"):
        qualification._run_prehardware_qualification_with_runners(
            tmp_path,
            policy=PrehardwareQualificationPolicy(profile="quick"),
            bootstrap_runner=cast(Any, harness.bootstrap_runner),
            profile_loader=cast(Any, harness.profile_loader),
            adaptive_runner=cast(Any, explode),
            virtual_runner=cast(Any, harness.virtual_runner),
            route_runner=cast(Any, harness.route_runner),
            revalidator=harness.revalidator,
        )
    assert harness.revalidation_calls == 0


def test_final_source_revalidation_error_aborts_completed_case_set(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    import rocell.application.prehardware_qualification as qualification

    harness = _QualificationHarness(profile="quick")

    def source_drift(_bootstrap: object) -> None:
        raise PrehardwareQualificationError("source changed during campaign")

    monkeypatch.setattr(
        qualification,
        "make_hidden_virtual_board_truth",
        lambda *_args, **_kwargs: object(),
    )
    with pytest.raises(
        PrehardwareQualificationError,
        match="source changed during campaign",
    ):
        qualification._run_prehardware_qualification_with_runners(
            tmp_path,
            policy=PrehardwareQualificationPolicy(profile="quick"),
            bootstrap_runner=cast(Any, harness.bootstrap_runner),
            profile_loader=cast(Any, harness.profile_loader),
            adaptive_runner=cast(Any, harness.adaptive_runner),
            virtual_runner=cast(Any, harness.virtual_runner),
            route_runner=cast(Any, harness.route_runner),
            revalidator=source_drift,
        )


def test_report_is_deterministic_hash_bound_redacted_and_detached(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _run_harness(
        tmp_path,
        monkeypatch,
        _QualificationHarness(profile="quick"),
    )
    second = _run_harness(
        tmp_path,
        monkeypatch,
        _QualificationHarness(profile="quick"),
    )
    document = first.to_dict()

    assert first.report_hash == second.report_hash
    assert document == second.to_dict()
    assert document["schema"] == PREHARDWARE_QUALIFICATION_SCHEMA
    assert document["report_sha256"] == first.report_hash
    without_hash = dict(document)
    without_hash.pop("report_sha256")
    assert hashlib.sha256(
        json.dumps(
            without_hash,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest() == first.report_hash

    serialized = json.dumps(document, sort_keys=True, allow_nan=False)
    assert '"plaintext_serialized": false' in serialized
    assert '"transform_serialized": false' in serialized
    assert "jpeg_bytes" not in serialized
    assert not any(isinstance(value, bytes) for value in _walk_values(document))
    _assert_zero_authority(document)

    original_hash = first.report_hash
    source = document["source"]
    assert isinstance(source, dict)
    source["manifest_sha256"] = "0" * 64
    cases = document["cases"]
    assert isinstance(cases, list)
    cases[0]["passed"] = False
    assert first.report_hash == original_hash
    assert first.to_dict()["source"]["manifest_sha256"] == "1" * 64
    with pytest.raises(TypeError):
        first.source["mutated"] = True  # type: ignore[index]


def _walk_values(value: object) -> list[object]:
    values = [value]
    if isinstance(value, Mapping):
        for child in value.values():
            values.extend(_walk_values(child))
    elif isinstance(value, (list, tuple)):
        for child in value:
            values.extend(_walk_values(child))
    return values


def test_report_hash_changes_with_case_evidence(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    first = _run_harness(
        tmp_path,
        monkeypatch,
        _QualificationHarness(profile="quick"),
    )
    changed_harness = _QualificationHarness(
        profile="quick",
        legacy_reason_override={
            VirtualFaultKind.CAMERA_TAG_LOSS: "CAMERA_UNAVAILABLE"
        },
    )
    changed = _run_harness(tmp_path, monkeypatch, changed_harness)

    assert first.report_hash != changed.report_hash
    assert first.campaign_passed is True
    assert changed.campaign_passed is False


def test_report_constructor_rejects_tampered_source_digest(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _run_harness(
        tmp_path,
        monkeypatch,
        _QualificationHarness(profile="quick"),
    )
    source = dict(report.to_dict()["source"])
    source["manifest_sha256"] = "not-a-digest"

    with pytest.raises(PrehardwareQualificationError, match="manifest_sha256"):
        replace(report, source=source)


def test_report_constructor_rejects_same_id_with_altered_case_spec(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _run_harness(
        tmp_path,
        monkeypatch,
        _QualificationHarness(profile="quick"),
    )
    original = report.case_results[0]
    # Keeping the identifier while changing membership used to evade a check
    # that compared case IDs only. The aggregate must bind the complete spec.
    forged_spec = replace(original.spec, profiles=("quick",))
    forged_result = replace(original, spec=forged_spec)

    with pytest.raises(
        PrehardwareQualificationError,
        match="selected ordered catalog",
    ):
        replace(report, cases=(forged_result, *report.case_results[1:]))


def test_case_result_rejects_hardware_command_metric_despite_claimed_authority() -> None:
    spec = _case("quick", "startup.integrity")

    with pytest.raises(PrehardwareQualificationError, match="zero authority"):
        QualificationCaseResult(
            spec=spec,
            observed_status="READY",
            passed=True,
            source_report_sha256="a" * 64,
            authority_verified=True,
            metrics={"hardware_commands_generated": 1},
        )


def test_report_constructor_rejects_resource_authority_or_coverage_forgery(
    tmp_path: Path,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    report = _run_harness(
        tmp_path,
        monkeypatch,
        _QualificationHarness(profile="quick"),
    )
    resources = dict(report.to_dict()["resource_usage"])
    resources["hardware_commands_generated"] = 1

    with pytest.raises(PrehardwareQualificationError, match="resource usage"):
        replace(report, resource_usage=resources)

    forged_coverage = dict(report.to_dict()["coverage_summary"])
    forged_coverage.update(
        {
            "evaluated": True,
            "state": "ALL_ROUTES_ACCEPTED",
            "complete_catalog_evidence": True,
            "route_count": 75,
            "accepted_route_count": 75,
            "rejected_route_count": 0,
            "all_routes_accepted": True,
        }
    )
    with pytest.raises(PrehardwareQualificationError, match="coverage summary"):
        replace(report, coverage_summary=forged_coverage)
