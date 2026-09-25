"""Contract and fault-matrix tests for the physical-shaped fake onboarding."""

from __future__ import annotations

from dataclasses import FrozenInstanceError, replace
import hashlib

import pytest

import rocell.application as application
from rocell.application.physical_shaped_onboarding import (
    ORDERED_ONBOARDING_STAGES,
    ArmIdentityObservation,
    CameraConfigurationReceipt,
    CleanupReceipt,
    DeterministicFakeOnboardingProvider,
    FakeBoundary,
    FakeProviderAccounting,
    FakeProviderDescriptor,
    InputBufferEmptyObservation,
    OnboardingErrorPhase,
    OnboardingStage,
    ParsedT1051Feedback,
    PhysicalShapedFakeProviders,
    PhysicalShapedOnboardingError,
    PowerEventObservation,
    StageStatus,
    SyntheticZeroReleaseAuthority,
    SyntheticControllerSessionIdentity,
    T105FeedbackReceipt,
    UntrustedSyntheticSequenceStamp,
    WorkflowStatus,
    build_deterministic_fake_providers,
    default_physical_shaped_onboarding_request,
    run_physical_shaped_fake_onboarding,
)


def test_physical_shaped_runner_is_intentionally_exported() -> None:
    assert application.run_physical_shaped_fake_onboarding is (
        run_physical_shaped_fake_onboarding
    )
    assert application.PHYSICAL_SHAPED_ONBOARDING_STAGES == (
        ORDERED_ONBOARDING_STAGES
    )
    assert (
        application.PhysicalShapedUntrustedSequenceStamp
        is UntrustedSyntheticSequenceStamp
    )
    assert (
        application.PhysicalShapedPowerEventObservation is PowerEventObservation
    )
    assert (
        application.PhysicalShapedControllerSessionIdentity
        is SyntheticControllerSessionIdentity
    )
    assert (
        application.PhysicalShapedInputBufferEmptyObservation
        is InputBufferEmptyObservation
    )
    assert application.PhysicalShapedT105FeedbackReceipt is T105FeedbackReceipt
    for public_name in (
        "PhysicalShapedUntrustedSequenceStamp",
        "PhysicalShapedPowerEventObservation",
        "PhysicalShapedControllerSessionIdentity",
        "PhysicalShapedInputBufferEmptyObservation",
        "PhysicalShapedT105FeedbackReceipt",
    ):
        assert public_name in application.__all__


def test_nominal_workflow_exercises_all_physical_shaped_boundaries_without_authority() -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(request)

    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.COMPLETE
    assert tuple(item.stage for item in result.stages) == ORDERED_ONBOARDING_STAGES
    assert all(item.status is StageStatus.PASSED for item in result.stages)
    assert result.cleanup is not None
    assert result.cleanup.cleanup_ordinal == 1
    assert result.cleanup.open_sessions_remaining == 0
    assert result.cleanup.pending_operations_remaining == 0
    assert result.accounting.synthetic_camera_captures == request.freshness_frame_count
    assert result.accounting.synthetic_feedback_requests == 1
    assert result.accounting.synthetic_t104_motion_requests == 0
    assert result.accounting.cleanup_attempts == 1
    assert result.accounting.operation_trace == (
        FakeBoundary.CAMERA_RECEIPT.value,
        FakeBoundary.CAMERA_INVENTORY.value,
        FakeBoundary.CAMERA_OPEN.value,
        FakeBoundary.CAMERA_APPLY_CONFIGURATION.value,
        FakeBoundary.CAMERA_READBACK.value,
        FakeBoundary.CAMERA_FLUSH.value,
        FakeBoundary.CAMERA_CAPTURE.value,
        FakeBoundary.CAMERA_CAPTURE.value,
        FakeBoundary.CAMERA_CAPTURE.value,
        FakeBoundary.CAMERA_REOPEN.value,
        FakeBoundary.CALIBRATION_ACQUISITION.value,
        FakeBoundary.ARM_IDENTITY_OFF.value,
            FakeBoundary.SAFETY_EVIDENCE.value,
            FakeBoundary.POWER_EVENT.value,
            FakeBoundary.CONTROLLER_SESSION.value,
            FakeBoundary.INPUT_BUFFER_EMPTY.value,
            FakeBoundary.T105_FEEDBACK.value,
        FakeBoundary.ACCOUNTING.value,
        FakeBoundary.CLEANUP.value,
        FakeBoundary.ACCOUNTING.value,
    )
    assert result.zero_physical_authority
    assert not result.physical_onboarding_completed
    assert not result.physical_calibration_valid
    assert result.physical_release_effect == "NONE"
    assert provider.descriptor.provider_kind == "EXPLICIT_FAKE"


def test_nominal_workflow_is_deterministic_and_configuration_is_b0477_bound() -> None:
    request = default_physical_shaped_onboarding_request()
    first_providers, _ = build_deterministic_fake_providers(request)
    second_providers, _ = build_deterministic_fake_providers(request)

    first = run_physical_shaped_fake_onboarding(request, first_providers)
    second = run_physical_shaped_fake_onboarding(request, second_providers)

    assert first == second
    assert request.expected_camera.manufacturer == "Arducam"
    assert request.expected_camera.model == "B0477"
    assert request.expected_camera.sensor == "Sony IMX283"
    assert request.exact_camera_configuration.mode.width_px == 5472
    assert request.exact_camera_configuration.mode.height_px == 3648
    assert request.exact_camera_configuration.mode.fps_numerator == 9
    assert request.exact_camera_configuration.mode.fps_denominator == 1
    assert request.exact_camera_configuration.mode.pixel_format == "YUY2"
    assert request.calibration_frame_count == 32
    assert request.calibration_training_frame_count == 24
    assert request.calibration_held_out_frame_count == 8
    assert tuple(
        setting.name for setting in request.exact_camera_configuration.controls
    ) == (
        "analog_gain_x100",
        "auto_exposure",
        "auto_white_balance",
        "exposure_time_us",
        "white_balance_temperature_k",
    )


def test_fake_authority_and_provider_kind_are_constructor_fixed_and_frozen() -> None:
    authority = SyntheticZeroReleaseAuthority()
    descriptor = FakeProviderDescriptor("run-001", "provider-001")

    with pytest.raises(TypeError):
        SyntheticZeroReleaseAuthority(robot_motion_authority=True)  # type: ignore[call-arg]
    with pytest.raises(ValueError):
        replace(authority, hardware_accessed=True)
    with pytest.raises(ValueError):
        replace(descriptor, provider_kind="PHYSICAL")
    with pytest.raises(FrozenInstanceError):
        authority.contact_authority = True  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        descriptor.provider_kind = "PHYSICAL"  # type: ignore[misc]


def test_fake_arm_surface_has_feedback_only_and_no_motion_or_raw_write_capability() -> None:
    request = default_physical_shaped_onboarding_request()
    _, provider = build_deterministic_fake_providers(request)

    assert callable(provider.inspect_arm_identity_while_off)
    assert callable(provider.open_synthetic_feedback_session)
    assert callable(provider.observe_t105_input_buffer_empty)
    assert callable(provider.acquire_single_t105_feedback)
    for forbidden_name in (
        "execute",
        "move",
        "move_joint",
        "move_pose",
        "contact",
        "send_command",
        "send_t104",
        "write",
        "write_serial",
    ):
        assert not hasattr(provider, forbidden_name)


def test_fake_provider_must_be_created_by_factory_and_have_exact_runtime_type() -> None:
    request = default_physical_shaped_onboarding_request()

    with pytest.raises(PhysicalShapedOnboardingError, match="issued by"):
        DeterministicFakeOnboardingProvider(request)

    providers, provider = build_deterministic_fake_providers(request)
    forged_type = type(
        "ForgedDeterministicFakeOnboardingProvider",
        (DeterministicFakeOnboardingProvider,),
        {},
    )
    forged = object.__new__(forged_type)
    forged.__dict__.update(provider.__dict__)

    with pytest.raises(PhysicalShapedOnboardingError, match="exact deterministic"):
        PhysicalShapedFakeProviders(
            camera=forged,
            calibration=forged,
            arm=forged,
            safety=forged,
            lifecycle=forged,
        )

    # Even separately issued exact fakes cannot split state/accounting roles.
    other_providers, other_provider = build_deterministic_fake_providers(request)
    assert other_providers.camera is other_provider
    with pytest.raises(PhysicalShapedOnboardingError, match="one issued"):
        PhysicalShapedFakeProviders(
            camera=provider,
            calibration=other_provider,
            arm=provider,
            safety=provider,
            lifecycle=provider,
        )


_FAULT_STAGE = {
    FakeBoundary.CAMERA_RECEIPT: OnboardingStage.CAMERA_RECEIPT,
    FakeBoundary.CAMERA_INVENTORY: OnboardingStage.CAMERA_INVENTORY_SELECTION,
    FakeBoundary.CAMERA_OPEN: OnboardingStage.CAMERA_INVENTORY_SELECTION,
    FakeBoundary.CAMERA_APPLY_CONFIGURATION: OnboardingStage.CAMERA_MODE_CONTROL,
    FakeBoundary.CAMERA_READBACK: OnboardingStage.CAMERA_MODE_CONTROL,
    FakeBoundary.CAMERA_FLUSH: OnboardingStage.CAMERA_BUFFER_FRESHNESS,
    FakeBoundary.CAMERA_CAPTURE: OnboardingStage.CAMERA_BUFFER_FRESHNESS,
    FakeBoundary.CAMERA_REOPEN: OnboardingStage.CAMERA_RECONNECT_IDENTITY,
    FakeBoundary.CALIBRATION_ACQUISITION: (
        OnboardingStage.RETAINED_INSTALL_CALIBRATION_ACQUISITION
    ),
    FakeBoundary.ARM_IDENTITY_OFF: OnboardingStage.ARM_IDENTITY_WHILE_OFF,
    FakeBoundary.SAFETY_EVIDENCE: OnboardingStage.SAFETY_EVIDENCE,
    FakeBoundary.POWER_EVENT: OnboardingStage.POWER_EVENT_OBSERVATION,
    FakeBoundary.CONTROLLER_SESSION: OnboardingStage.SINGLE_T105_FEEDBACK,
    FakeBoundary.INPUT_BUFFER_EMPTY: OnboardingStage.SINGLE_T105_FEEDBACK,
    FakeBoundary.T105_FEEDBACK: OnboardingStage.SINGLE_T105_FEEDBACK,
    FakeBoundary.ACCOUNTING: OnboardingStage.SINGLE_T105_FEEDBACK,
}


@pytest.mark.parametrize("fault_at", tuple(_FAULT_STAGE))
def test_every_diagnostic_provider_boundary_fails_closed_and_cleans_up(
    fault_at: FakeBoundary,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, _ = build_deterministic_fake_providers(request, fault_at=fault_at)

    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.FAILED
    assert result.stages[-1].stage is _FAULT_STAGE[fault_at]
    assert result.stages[-1].status is StageStatus.FAILED_CLOSED
    assert result.stages[-1].detail_code == f"FAKE_BOUNDARY_{fault_at.value}_FAILED"
    assert sum(item.status is StageStatus.FAILED_CLOSED for item in result.stages) == 1
    assert result.cleanup is not None
    assert result.cleanup.cleanup_ordinal == 1
    assert result.cleanup.open_sessions_remaining == 0
    assert result.accounting.cleanup_attempts == 1
    assert result.accounting.synthetic_t104_motion_requests == 0
    if fault_at is not FakeBoundary.ACCOUNTING:
        assert result.accounting.synthetic_feedback_requests == 0
    assert result.zero_physical_authority


def test_cleanup_boundary_is_reported_without_converting_simulation_to_authority() -> None:
    request = default_physical_shaped_onboarding_request()
    providers, _ = build_deterministic_fake_providers(
        request, fault_at=FakeBoundary.CLEANUP
    )

    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.CLEANUP_UNCONFIRMED
    assert tuple(item.stage for item in result.stages) == ORDERED_ONBOARDING_STAGES
    assert all(item.status is StageStatus.PASSED for item in result.stages)
    assert result.cleanup is None
    assert result.cleanup_error_code == "FAKE_BOUNDARY_CLEANUP_FAILED"
    assert result.accounting.cleanup_attempts == 1
    assert result.accounting.synthetic_feedback_requests == 1
    assert result.accounting.synthetic_t104_motion_requests == 0
    assert result.zero_physical_authority


def test_fault_stops_before_later_diagnostic_boundaries() -> None:
    request = default_physical_shaped_onboarding_request()
    providers, _ = build_deterministic_fake_providers(
        request, fault_at=FakeBoundary.CAMERA_READBACK
    )

    result = run_physical_shaped_fake_onboarding(request, providers)

    trace = result.accounting.operation_trace
    assert FakeBoundary.CAMERA_READBACK.value in trace
    assert FakeBoundary.CAMERA_FLUSH.value not in trace
    assert FakeBoundary.CAMERA_REOPEN.value not in trace
    assert FakeBoundary.ARM_IDENTITY_OFF.value not in trace
    assert FakeBoundary.T105_FEEDBACK.value not in trace
    assert FakeBoundary.CLEANUP.value in trace


def test_wrong_configuration_readback_is_rejected_before_capture_and_cleanup_runs(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(request)
    original = provider.read_configuration

    def wrong_readback(request_value: object) -> CameraConfigurationReceipt:
        observation = original(request_value)  # type: ignore[arg-type]
        return replace(observation, fallback_negotiated=True)

    monkeypatch.setattr(provider, "read_configuration", wrong_readback)
    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.FAILED
    assert result.stages[-1].stage is OnboardingStage.CAMERA_MODE_CONTROL
    assert result.stages[-1].detail_code == "PROVIDER_RESULT_INVARIANT_FAILED"
    assert result.accounting.synthetic_camera_captures == 0
    assert result.accounting.synthetic_feedback_requests == 0
    assert result.cleanup is not None


@pytest.mark.parametrize(
    "corruption",
    (
        "reopened_session_run_id",
        "configuration_readback_run_id",
        "requested_configuration_digest",
    ),
)
def test_reopen_nested_records_are_bound_to_active_run_and_configuration(
    corruption: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(request)
    original = provider.reopen_selected_camera

    def corrupt_reconnect(request_value: object) -> object:
        receipt = original(request_value)  # type: ignore[arg-type]
        if corruption == "reopened_session_run_id":
            return replace(
                receipt,
                reopened_session=replace(
                    receipt.reopened_session, run_id="foreign-run"
                ),
            )
        if corruption == "configuration_readback_run_id":
            return replace(
                receipt,
                configuration_readback=replace(
                    receipt.configuration_readback, run_id="foreign-run"
                ),
            )
        return replace(
            receipt,
            configuration_readback=replace(
                receipt.configuration_readback,
                requested_configuration_sha256="f" * 64,
            ),
        )

    monkeypatch.setattr(provider, "reopen_selected_camera", corrupt_reconnect)
    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.FAILED
    assert result.stages[-1].stage is OnboardingStage.CAMERA_RECONNECT_IDENTITY
    assert result.stages[-1].detail_code == "PROVIDER_RESULT_INVARIANT_FAILED"
    assert result.primary_error is not None
    assert result.primary_error.stage is OnboardingStage.CAMERA_RECONNECT_IDENTITY
    assert result.cleanup is not None


def test_arm_identity_must_be_observed_while_power_is_off(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(request)
    original = provider.inspect_arm_identity_while_off

    def powered_identity(request_value: object) -> ArmIdentityObservation:
        observation = original(request_value)  # type: ignore[arg-type]
        return replace(observation, arm_power_observed_off=False)

    monkeypatch.setattr(provider, "inspect_arm_identity_while_off", powered_identity)
    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.FAILED
    assert result.stages[-1].stage is OnboardingStage.ARM_IDENTITY_WHILE_OFF
    assert result.accounting.synthetic_feedback_requests == 0
    assert result.cleanup is not None


def test_safety_sequence_stamp_is_recomputed_before_power_event(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(request)
    original = provider.collect_safety_evidence

    def corrupt_safety(request_value: object) -> object:
        observation = original(request_value)  # type: ignore[arg-type]
        object.__setattr__(
            observation.sequence_stamp, "purpose", "POWER_EVENT_REQUEST"
        )
        return observation

    monkeypatch.setattr(provider, "collect_safety_evidence", corrupt_safety)
    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.FAILED
    assert result.stages[-1].stage is OnboardingStage.SAFETY_EVIDENCE
    assert result.stages[-1].detail_code == "PROVIDER_RESULT_INVARIANT_FAILED"
    assert FakeBoundary.POWER_EVENT.value not in result.accounting.operation_trace
    assert result.cleanup is not None


@pytest.mark.parametrize(
    "corruption",
    (
        "safety_binding",
        "request_binding",
        "event_identifier",
        "sequence_stamp",
    ),
)
def test_power_event_is_bound_to_exact_safety_observation_and_request(
    corruption: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(request)
    original = provider.observe_power_event

    def corrupt_power(request_value: object) -> object:
        observation = original(request_value)  # type: ignore[arg-type]
        if corruption == "safety_binding":
            object.__setattr__(
                observation,
                "safety_observation_sha256",
                observation.power_event_request_sha256,
            )
        elif corruption == "request_binding":
            object.__setattr__(
                observation,
                "power_event_request_sha256",
                observation.safety_observation_sha256,
            )
        elif corruption == "event_identifier":
            object.__setattr__(observation, "event_id", "substituted-power-event")
        else:
            object.__setattr__(observation.sequence_stamp, "chain_ordinal", 9)
        return observation

    monkeypatch.setattr(provider, "observe_power_event", corrupt_power)
    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.FAILED
    assert result.stages[-1].stage is OnboardingStage.POWER_EVENT_OBSERVATION
    assert result.stages[-1].detail_code == "PROVIDER_RESULT_INVARIANT_FAILED"
    assert FakeBoundary.CONTROLLER_SESSION.value not in result.accounting.operation_trace
    assert result.cleanup is not None


@pytest.mark.parametrize(
    "corruption",
    (
        "cross_run",
        "power_binding",
        "request_binding",
        "substituted_session",
        "sequence_stamp",
    ),
)
def test_controller_session_identity_rejects_cross_run_stage_and_substitution(
    corruption: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(request)
    original = provider.open_synthetic_feedback_session

    def corrupt_session(request_value: object) -> object:
        session = original(request_value)  # type: ignore[arg-type]
        if corruption == "cross_run":
            object.__setattr__(session, "run_id", "foreign-run")
        elif corruption == "power_binding":
            object.__setattr__(
                session,
                "power_event_observation_sha256",
                session.controller_session_request_sha256,
            )
        elif corruption == "request_binding":
            object.__setattr__(
                session,
                "controller_session_request_sha256",
                session.power_event_observation_sha256,
            )
        elif corruption == "substituted_session":
            object.__setattr__(session, "session_id", "substituted-session")
        else:
            object.__setattr__(session.sequence_stamp, "purpose", "T105_FEEDBACK")
        return session

    monkeypatch.setattr(provider, "open_synthetic_feedback_session", corrupt_session)
    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.FAILED
    assert result.stages[-1].stage is OnboardingStage.SINGLE_T105_FEEDBACK
    assert result.stages[-1].detail_code == "PROVIDER_RESULT_INVARIANT_FAILED"
    assert FakeBoundary.INPUT_BUFFER_EMPTY.value not in result.accounting.operation_trace
    assert result.accounting.synthetic_feedback_requests == 0
    assert result.cleanup is not None


@pytest.mark.parametrize(
    "corruption",
    (
        "cross_run",
        "power_binding",
        "cross_session",
        "controller_identity_binding",
        "request_binding",
        "nonempty_buffer",
        "sequence_stamp",
    ),
)
def test_pre_query_input_buffer_observation_is_exactly_session_bound_and_empty(
    corruption: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(request)
    original = provider.observe_t105_input_buffer_empty

    def corrupt_buffer(request_value: object) -> object:
        observation = original(request_value)  # type: ignore[arg-type]
        if corruption == "cross_run":
            object.__setattr__(observation, "run_id", "foreign-run")
        elif corruption == "power_binding":
            object.__setattr__(
                observation,
                "power_event_observation_sha256",
                observation.controller_session_identity_sha256,
            )
        elif corruption == "cross_session":
            object.__setattr__(
                observation, "controller_session_id", "foreign-session"
            )
        elif corruption == "controller_identity_binding":
            object.__setattr__(
                observation,
                "controller_session_identity_sha256",
                observation.input_buffer_request_sha256,
            )
        elif corruption == "request_binding":
            object.__setattr__(
                observation,
                "input_buffer_request_sha256",
                observation.power_event_observation_sha256,
            )
        elif corruption == "nonempty_buffer":
            object.__setattr__(observation, "bytes_waiting", 1)
        else:
            object.__setattr__(observation.sequence_stamp, "chain_ordinal", 9)
        return observation

    monkeypatch.setattr(
        provider, "observe_t105_input_buffer_empty", corrupt_buffer
    )
    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.FAILED
    assert result.stages[-1].stage is OnboardingStage.SINGLE_T105_FEEDBACK
    assert result.stages[-1].detail_code == "PROVIDER_RESULT_INVARIANT_FAILED"
    assert FakeBoundary.T105_FEEDBACK.value not in result.accounting.operation_trace
    assert result.accounting.synthetic_feedback_requests == 0
    assert result.cleanup is not None


def test_feedback_must_be_identity_bound_t1051_and_first_query(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(request)
    original = provider.acquire_single_t105_feedback

    def wrong_feedback(request_value: object) -> T105FeedbackReceipt:
        observation = original(request_value)  # type: ignore[arg-type]
        return replace(observation, response_type="T=1041")

    monkeypatch.setattr(provider, "acquire_single_t105_feedback", wrong_feedback)
    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.FAILED
    assert result.stages[-1].stage is OnboardingStage.SINGLE_T105_FEEDBACK
    assert result.accounting.synthetic_feedback_requests == 1
    assert result.accounting.synthetic_t104_motion_requests == 0
    assert result.cleanup is not None


@pytest.mark.parametrize(
    "corruption",
    (
        "request_bytes",
        "response_bytes",
        "typed_feedback",
        "typed_feedback_digest",
        "cross_stage_power_binding",
        "cross_session",
        "controller_identity_binding",
        "input_buffer_binding",
        "request_context_binding",
        "sequence_stamp",
    ),
)
def test_t105_hashes_are_revalidated_against_retained_bytes_and_parsed_content(
    corruption: str,
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(request)
    original = provider.acquire_single_t105_feedback

    def corrupt_feedback(request_value: object) -> T105FeedbackReceipt:
        receipt = original(request_value)  # type: ignore[arg-type]
        if corruption == "request_bytes":
            # Keep the digest self-consistent: the runner must still reject a
            # retained T=104 request masquerading as feedback-only evidence.
            bad_request = b'{"T":104}\n'
            object.__setattr__(receipt, "request_bytes", bad_request)
            object.__setattr__(
                receipt,
                "request_bytes_sha256",
                hashlib.sha256(bad_request).hexdigest(),
            )
        elif corruption == "response_bytes":
            object.__setattr__(
                receipt,
                "response_bytes",
                receipt.response_bytes.replace(b'"x":0.0', b'"x":1.0'),
            )
        elif corruption == "typed_feedback":
            object.__setattr__(
                receipt,
                "typed_feedback",
                replace(receipt.typed_feedback, x=1.0),
            )
        elif corruption == "typed_feedback_digest":
            object.__setattr__(receipt, "typed_feedback_sha256", "f" * 64)
        elif corruption == "cross_stage_power_binding":
            object.__setattr__(
                receipt,
                "power_event_observation_sha256",
                receipt.input_buffer_observation_sha256,
            )
        elif corruption == "cross_session":
            object.__setattr__(
                receipt, "controller_session_id", "foreign-session"
            )
        elif corruption == "controller_identity_binding":
            object.__setattr__(
                receipt,
                "controller_session_identity_sha256",
                receipt.power_event_observation_sha256,
            )
        elif corruption == "input_buffer_binding":
            object.__setattr__(
                receipt,
                "input_buffer_observation_sha256",
                receipt.controller_session_identity_sha256,
            )
        elif corruption == "request_context_binding":
            object.__setattr__(
                receipt,
                "feedback_request_context_sha256",
                receipt.input_buffer_observation_sha256,
            )
        else:
            object.__setattr__(receipt.sequence_stamp, "chain_ordinal", 1)
        return receipt

    monkeypatch.setattr(provider, "acquire_single_t105_feedback", corrupt_feedback)
    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.FAILED
    assert result.stages[-1].stage is OnboardingStage.SINGLE_T105_FEEDBACK
    assert result.stages[-1].detail_code == "PROVIDER_RESULT_INVARIANT_FAILED"
    assert result.primary_error is not None
    assert result.accounting.synthetic_feedback_requests == 1
    assert result.accounting.synthetic_t104_motion_requests == 0
    assert result.cleanup is not None


def test_primary_cleanup_and_repeated_accounting_failures_are_all_preserved(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(
        request, fault_at=FakeBoundary.ACCOUNTING
    )

    def fail_cleanup(request_value: object) -> CleanupReceipt:
        del request_value
        provider._cleanup_attempts += 1
        raise RuntimeError("second cleanup failure")

    monkeypatch.setattr(provider, "cleanup", fail_cleanup)
    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.CLEANUP_UNCONFIRMED
    assert result.primary_error is not None
    assert result.primary_error.phase is OnboardingErrorPhase.WORKFLOW
    assert result.primary_error.detail_code == "FAKE_BOUNDARY_ACCOUNTING_FAILED"
    assert len(result.cleanup_errors) == 1
    assert result.cleanup_errors[0].phase is OnboardingErrorPhase.CLEANUP
    assert result.cleanup_errors[0].message == "second cleanup failure"
    assert len(result.post_run_accounting_errors) == 1
    assert (
        result.post_run_accounting_errors[0].phase
        is OnboardingErrorPhase.POST_RUN_ACCOUNTING
    )
    assert (
        result.post_run_accounting_errors[0].detail_code
        == "FAKE_BOUNDARY_ACCOUNTING_FAILED"
    )
    assert result.accounting.cleanup_attempts == 1
    assert result.cleanup is None


def test_every_invalid_cleanup_receipt_field_is_reported(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(request)

    def invalid_cleanup(request_value: object) -> CleanupReceipt:
        del request_value
        provider._cleanup_attempts += 1
        provider._open_sessions.clear()
        provider._configured_sessions.clear()
        return CleanupReceipt("foreign-run", 2, 3, 4)

    monkeypatch.setattr(provider, "cleanup", invalid_cleanup)
    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.CLEANUP_UNCONFIRMED
    assert result.primary_error is None
    assert result.cleanup is None
    assert len(result.cleanup_errors) == 4
    assert all(
        item.phase is OnboardingErrorPhase.CLEANUP
        for item in result.cleanup_errors
    )
    assert {item.message for item in result.cleanup_errors} == {
        "cleanup run_id mismatch",
        "cleanup must occur once",
        "cleanup left an open camera session",
        "cleanup left a pending operation",
    }


def test_every_post_run_accounting_violation_is_reported_without_escaping(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    request = default_physical_shaped_onboarding_request()
    providers, provider = build_deterministic_fake_providers(request)
    original = provider.snapshot_accounting
    call_count = 0

    def invalid_second_accounting() -> FakeProviderAccounting:
        nonlocal call_count
        call_count += 1
        accounting = original()
        if call_count == 1:
            return accounting
        return replace(
            accounting,
            run_id="foreign-run",
            synthetic_feedback_requests=2,
            synthetic_t104_motion_requests=1,
            cleanup_attempts=2,
        )

    monkeypatch.setattr(provider, "snapshot_accounting", invalid_second_accounting)
    result = run_physical_shaped_fake_onboarding(request, providers)

    assert result.status is WorkflowStatus.FAILED
    assert result.primary_error is None
    assert result.cleanup_errors == ()
    assert len(result.post_run_accounting_errors) == 4
    assert {item.message for item in result.post_run_accounting_errors} == {
        "post-run accounting run_id mismatch",
        "post-run accounting reported a T=104 motion request",
        "post-run accounting must report exactly one cleanup attempt",
        "post-run accounting must retain exactly one T=105 request",
    }
    assert result.accounting.run_id == request.run_id
    assert result.accounting.synthetic_t104_motion_requests == 1
    assert not result.zero_physical_authority
    assert result.cleanup is not None


def test_records_reject_implicit_coercion_and_invalid_digest() -> None:
    request = default_physical_shaped_onboarding_request()

    with pytest.raises(PhysicalShapedOnboardingError, match="must sum"):
        replace(request, calibration_training_frame_count=23)
    with pytest.raises(PhysicalShapedOnboardingError, match="fps_numerator"):
        replace(request.exact_camera_configuration.mode, fps_numerator=True)
    with pytest.raises(PhysicalShapedOnboardingError, match="controls must be sorted"):
        replace(
            request.exact_camera_configuration,
            controls=tuple(reversed(request.exact_camera_configuration.controls)),
        )
    with pytest.raises(PhysicalShapedOnboardingError, match="lowercase SHA-256"):
        ParsedT1051Feedback(
            "X" * 64,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0.0,
            0,
            0,
            0,
            0,
        )


def test_result_and_stage_records_are_immutable() -> None:
    request = default_physical_shaped_onboarding_request()
    providers, _ = build_deterministic_fake_providers(request)
    result = run_physical_shaped_fake_onboarding(request, providers)

    with pytest.raises(FrozenInstanceError):
        result.physical_onboarding_completed = True  # type: ignore[misc]
    with pytest.raises(FrozenInstanceError):
        result.stages[0].status = StageStatus.FAILED_CLOSED  # type: ignore[misc]
