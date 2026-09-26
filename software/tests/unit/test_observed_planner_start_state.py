from __future__ import annotations

import hashlib

import pytest

from rocell.application.observed_planner_start_state import (
    ObservedPlannerStartStateError,
    build_observed_planner_start_state,
)
from rocell.application.physical_connection_contracts import (
    SingleT105FeedbackReceipt,
    SingleT105FeedbackRequest,
    T105TransactionTiming,
    canonical_sha256,
)
from rocell.arm import validate_feedback_response_line
from rocell.calibration import PlannerCalibrationSnapshot, required_planner_artifact_ids
from rocell.geometry import RigidTransform, Rotation3, Vec3


ARM_IDENTITY = "1" * 64
RESPONSE = (
    b'{"T":1051,"x":120,"y":0,"z":180,"b":0.1,"s":0.2,'
    b'"e":0.3,"t":0.4,"r":0.5,"g":0.6}\n'
)


def snapshot(arm_identity: str = ARM_IDENTITY) -> PlannerCalibrationSnapshot:
    return PlannerCalibrationSnapshot(
        device="keyboard",
        manifest_id="manifest",
        active_build_id="build",
        artifact_hashes={
            item: "a" * 64 for item in required_planner_artifact_ids("keyboard")
        },
        board_T_vendor_world=RigidTransform("B", "Wv", Rotation3.identity(), Vec3.zero()),
        board_T_device=RigidTransform("B", "keyboard", Rotation3.identity(), Vec3.zero()),
        hand_T_tool=RigidTransform("G", "T", Rotation3.identity(), Vec3.zero()),
        robot_reference_identity={
            "arm_identity_hash": arm_identity,
            "controller_identity_hash": "2" * 64,
            "firmware_identity_hash": "3" * 64,
        },
        joint_zero_offsets_rad=(0.01, 0.02, 0.03, 0.04, 0.05, 0.06),
        joint_lower_rad=(-2.0,) * 6,
        joint_upper_rad=(2.0,) * 6,
        joint_signs=(1, -1, 1, -1, 1, -1),
        controller_correlation={"model": "test"},
        target_map_sha256="b" * 64,
    )


def request() -> SingleT105FeedbackRequest:
    return SingleT105FeedbackRequest(
        run_id="run-1",
        arm_identity_receipt_sha256="4" * 64,
        arm_identity_sha256=ARM_IDENTITY,
        power_event_observation_sha256="5" * 64,
        safety_permit_sha256="6" * 64,
        controller_session_id="session-1",
        requested_monotonic_ns=90,
    )


def receipt(response: bytes = RESPONSE) -> SingleT105FeedbackReceipt:
    request_value = request()
    parsed = validate_feedback_response_line(response, max_line_bytes=2048)
    request_bytes = b'{"T":105}\n'
    return SingleT105FeedbackReceipt(
        run_id=request_value.run_id,
        provider_descriptor_sha256="7" * 64,
        request_context_sha256=request_value.request_context_sha256,
        arm_identity_sha256=request_value.arm_identity_sha256,
        controller_session_id=request_value.controller_session_id,
        timing=T105TransactionTiming(91, 92, 93, 94, 95, 100, 101),
        pre_request_bytes_waiting=0,
        post_response_bytes_waiting=0,
        request_bytes=request_bytes,
        response_bytes=response,
        request_bytes_sha256=hashlib.sha256(request_bytes).hexdigest(),
        response_bytes_sha256=hashlib.sha256(response).hexdigest(),
        parsed_response_sha256=canonical_sha256(parsed),
        write_attempts=1,
        feedback_query_count=1,
        retry_count=0,
        t104_motion_count=0,
        connection_closed=True,
    )


def test_projects_complete_fresh_feedback_into_model_joint_state() -> None:
    measured = snapshot()
    state = build_observed_planner_start_state(
        request(), receipt(), measured, observed_monotonic_ns=110, maximum_age_ns=100
    )
    assert dict(state.controller_joint_positions_rad) == {
        "b": 0.1, "s": 0.2, "e": 0.3, "t": 0.4, "r": 0.5, "g": 0.6
    }
    assert dict(state.model_joint_positions_rad) == pytest.approx({
        "b_base": 0.11, "s_shoulder": -0.18, "e_elbow": 0.33,
        "t_wrist_pitch": -0.36, "r_wrist_roll": 0.55, "g_gripper": -0.54,
    })
    assert set(state.require_fresh_for(measured, 150)) == {
        "base_link_to_link1", "link1_to_link2", "link2_to_link3",
        "link3_to_link4", "link4_to_link5",
    }
    document = state.to_dict()
    assert document["controller_commands"] == []
    assert document["hardware_access"] is False
    assert document["physical_authority"] is False


def test_rejects_stale_incomplete_and_wrong_arm_feedback() -> None:
    with pytest.raises(ObservedPlannerStartStateError, match="already stale"):
        build_observed_planner_start_state(
            request(), receipt(), snapshot(), observed_monotonic_ns=201, maximum_age_ns=100
        )
    incomplete = b'{"T":1051,"b":0.1,"s":0.2,"e":0.3,"t":0.4,"g":0.6}\n'
    with pytest.raises(ObservedPlannerStartStateError, match="lacks complete.*r"):
        build_observed_planner_start_state(
            request(), receipt(incomplete), snapshot(),
            observed_monotonic_ns=110, maximum_age_ns=100,
        )
    with pytest.raises(ObservedPlannerStartStateError, match="calibrated robot"):
        build_observed_planner_start_state(
            request(), receipt(), snapshot("9" * 64),
            observed_monotonic_ns=110, maximum_age_ns=100,
        )


def test_state_cannot_be_reused_after_freshness_window() -> None:
    measured = snapshot()
    state = build_observed_planner_start_state(
        request(), receipt(), measured, observed_monotonic_ns=110, maximum_age_ns=100
    )
    with pytest.raises(ObservedPlannerStartStateError, match="stale"):
        state.require_fresh_for(measured, 201)
