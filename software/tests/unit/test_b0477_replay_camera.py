"""Focused contracts for the strictly stateful B0477 replay camera port."""

from __future__ import annotations

import copy
from dataclasses import replace
from pathlib import Path

import pytest

from rocell.application.b0477_mission_observations import (
    B0477MissionObservation,
    B0477MissionObservationSet,
)
from rocell.application.integrated_zero_hardware_mission import (
    assemble_default_zero_hardware_mission_v2,
)
from rocell.simulation.b0477_replay_camera import (
    B0477ReplayCameraError,
    B0477ReplayCameraPort,
    B0477ReplayCaptureError,
    B0477ReplayFaultInjection,
    B0477ReplayFaultKind,
)


WORKSPACE = Path(__file__).resolve().parents[3]


@pytest.fixture(scope="module")
def observation_set() -> B0477MissionObservationSet:
    pytest.importorskip("PIL")
    assembly = assemble_default_zero_hardware_mission_v2(
        WORKSPACE,
        "keyboard",
        "ab",
        mission_id="b0477-replay-camera-test",
        controller_session_id="b0477-replay-camera-test-t104",
        camera_starting_sequence=81_000,
    )
    assert assembly.camera_observations.observation_count == 2
    return assembly.camera_observations


def _capture(
    port: B0477ReplayCameraPort,
    observation: B0477MissionObservation,
    **overrides: object,
) -> B0477MissionObservation:
    arguments: dict[str, object] = {
        "semantic_step_ordinal": observation.semantic_step_ordinal,
        "contact_occurrence_ordinal": observation.contact_occurrence_ordinal,
        "target_id": observation.target_id,
        "final_hover_route_waypoint_ordinal": observation.route_waypoint_ordinal,
        "authorization_command_ordinal": observation.authorization_command_ordinal,
        "just_settled_controller_pose_sha256": (
            observation.expected_settled_controller_pose_sha256
        ),
    }
    arguments.update(overrides)
    return port.capture_after_settle(**arguments)  # type: ignore[arg-type]


def test_consumes_each_observation_once_in_exact_order(
    observation_set: B0477MissionObservationSet,
) -> None:
    port = B0477ReplayCameraPort(observation_set)
    first, second = observation_set.observations

    assert port.authority == "ZERO"
    assert not port.hardware_accessed
    assert port.consumed == 0
    assert port.remaining == 2
    assert not port.complete
    assert port.fault_latched is None

    assert _capture(port, first) is first
    assert port.consumed == 1
    assert port.remaining == 1
    assert not port.complete

    # A reused contact cannot advance or reveal another observation.
    with pytest.raises(B0477ReplayCameraError, match="reused"):
        _capture(port, first)
    assert port.consumed == 1
    assert port.remaining == 1

    assert _capture(port, second) is second
    assert port.consumed == 2
    assert port.remaining == 0
    assert port.complete

    with pytest.raises(B0477ReplayCameraError, match="already completely consumed"):
        _capture(port, second)


def test_out_of_order_preconsumption_is_refused_without_advancing(
    observation_set: B0477MissionObservationSet,
) -> None:
    port = B0477ReplayCameraPort(observation_set)
    with pytest.raises(B0477ReplayCameraError, match="skipped"):
        _capture(port, observation_set.observations[1])
    assert port.consumed == 0
    assert port.remaining == 2
    assert not port.complete


@pytest.mark.parametrize(
    ("field", "wrong_value", "message"),
    (
        ("semantic_step_ordinal", 511, "exact next observation binding"),
        ("target_id", "keyboard.wrong", "exact next observation binding"),
        (
            "final_hover_route_waypoint_ordinal",
            65_535,
            "exact next observation binding",
        ),
        (
            "authorization_command_ordinal",
            65_535,
            "exact next observation binding",
        ),
        (
            "just_settled_controller_pose_sha256",
            "0" * 64,
            "exact settled final-hover pose",
        ),
    ),
)
def test_wrong_binding_or_pose_is_refused_without_consumption(
    observation_set: B0477MissionObservationSet,
    field: str,
    wrong_value: object,
    message: str,
) -> None:
    port = B0477ReplayCameraPort(observation_set)
    with pytest.raises(B0477ReplayCameraError, match=message):
        _capture(port, observation_set.observations[0], **{field: wrong_value})
    assert port.consumed == 0
    assert port.remaining == 2
    assert not port.complete


@pytest.mark.parametrize("fault_kind", tuple(B0477ReplayFaultKind))
def test_camera_faults_latch_closed_without_yielding_an_observation(
    observation_set: B0477MissionObservationSet,
    fault_kind: B0477ReplayFaultKind,
) -> None:
    port = B0477ReplayCameraPort(
        observation_set,
        fault_injection=B0477ReplayFaultInjection(
            contact_occurrence_ordinal=1,
            fault_kind=fault_kind,
        ),
    )
    first, second = observation_set.observations
    assert _capture(port, first) is first

    with pytest.raises(B0477ReplayCaptureError) as raised:
        _capture(port, second)
    assert raised.value.contact_occurrence_ordinal == 1
    assert raised.value.fault_kind is fault_kind
    assert "no observation was yielded" in str(raised.value)
    receipt = raised.value.receipt
    assert port.fault_receipt is receipt
    assert receipt.fault_kind is fault_kind
    assert receipt.semantic_step_ordinal == second.semantic_step_ordinal
    assert receipt.contact_occurrence_ordinal == 1
    assert receipt.target_id == second.target_id
    assert receipt.route_waypoint_ordinal == second.route_waypoint_ordinal
    assert receipt.authorization_command_ordinal == (
        second.authorization_command_ordinal
    )
    assert receipt.expected_observation_sha256 == second.observation_sha256
    assert receipt.observation_set_sha256 == observation_set.canonical_sha256
    assert receipt.fault_injection_sha256
    assert receipt.to_dict()["observation_yielded"] is False
    assert port.fault_latched is fault_kind
    assert port.consumed == 1
    assert port.remaining == 1
    assert not port.complete

    # A fault cannot be retried into success and cannot be bypassed.
    with pytest.raises(B0477ReplayCameraError, match="fault-latched"):
        _capture(port, second)
    assert port.consumed == 1
    assert port.remaining == 1

    object.__setattr__(receipt, "target_id", "forged.target")
    with pytest.raises(B0477ReplayCameraError, match="changed after construction"):
        receipt.validate()


def test_fault_receipt_rejects_route_rebinding(
    observation_set: B0477MissionObservationSet,
) -> None:
    port = B0477ReplayCameraPort(
        observation_set,
        fault_injection=B0477ReplayFaultInjection(
            contact_occurrence_ordinal=0,
            fault_kind=B0477ReplayFaultKind.CAPTURE_FAILURE,
        ),
    )
    with pytest.raises(B0477ReplayCaptureError) as raised:
        _capture(port, observation_set.observations[0])
    with pytest.raises(B0477ReplayCameraError, match="ordinals differ"):
        replace(
            raised.value.receipt,
            authorization_command_ordinal=(
                raised.value.receipt.authorization_command_ordinal + 1
            ),
        )


def test_fault_request_requires_the_exact_contact_before_it_can_latch(
    observation_set: B0477MissionObservationSet,
) -> None:
    port = B0477ReplayCameraPort(
        observation_set,
        fault_injection=B0477ReplayFaultInjection(
            contact_occurrence_ordinal=0,
            fault_kind=B0477ReplayFaultKind.TIMEOUT,
        ),
    )
    first = observation_set.observations[0]
    with pytest.raises(B0477ReplayCameraError, match="exact settled"):
        _capture(
            port,
            first,
            just_settled_controller_pose_sha256="f" * 64,
        )
    assert port.fault_latched is None
    assert port.consumed == 0

    with pytest.raises(B0477ReplayCaptureError):
        _capture(port, first)
    assert port.fault_latched is B0477ReplayFaultKind.TIMEOUT


def test_port_snapshots_and_seals_the_fault_schedule(
    observation_set: B0477MissionObservationSet,
) -> None:
    injection = B0477ReplayFaultInjection(
        contact_occurrence_ordinal=1,
        fault_kind=B0477ReplayFaultKind.STALE_FRAME,
    )
    injection_sha256 = injection.canonical_sha256
    port = B0477ReplayCameraPort(observation_set, fault_injection=injection)

    # Even privileged mutation of the caller-owned object cannot move the
    # schedule retained by the already-created port.
    object.__setattr__(injection, "contact_occurrence_ordinal", 0)
    with pytest.raises(B0477ReplayCameraError, match="changed after construction"):
        injection.validate()
    assert _capture(port, observation_set.observations[0]) is (
        observation_set.observations[0]
    )
    with pytest.raises(B0477ReplayCaptureError) as raised:
        _capture(port, observation_set.observations[1])
    assert raised.value.receipt.fault_injection_sha256 == injection_sha256


def test_port_is_noncopyable_and_fault_must_be_in_range(
    observation_set: B0477MissionObservationSet,
) -> None:
    port = B0477ReplayCameraPort(observation_set)
    with pytest.raises(B0477ReplayCameraError, match="cannot be copied"):
        copy.copy(port)
    with pytest.raises(B0477ReplayCameraError, match="cannot be copied"):
        copy.deepcopy(port)

    with pytest.raises(B0477ReplayCameraError, match="outside"):
        B0477ReplayCameraPort(
            observation_set,
            fault_injection=B0477ReplayFaultInjection(
                contact_occurrence_ordinal=2,
                fault_kind=B0477ReplayFaultKind.CAPTURE_FAILURE,
            ),
        )
