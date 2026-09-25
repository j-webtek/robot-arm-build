"""Deterministic, simulation-only model of selected RoArm-M3 firmware math.

The controller's Cartesian frame, ``R_ctrl``, is deliberately distinct from
the Waveshare URDF ``world``/``base_link`` frames.  This module models only
published/audited equations and the T=104 easing loop; it cannot encode,
transmit, or authorize a hardware command.
"""

from __future__ import annotations

from dataclasses import dataclass, field
import math
from typing import Any

from rocell.models.units import finite_real


CONTROLLER_FRAME = "R_ctrl"
MAX_SIMULATION_SPD_COEFFICIENT = 1000.0
MAX_TRACE_SAMPLES = 100_000
MODEL_GRIPPER_CLOSED_RAD = 0.0
MODEL_GRIPPER_OPEN_RAD = 1.5
PROVISIONAL_SIMULATION_JOINT_INTERSECTION_RAD: dict[str, tuple[float, float]] = {
    "base_rad": (-math.pi, math.pi),
    "shoulder_rad": (-math.pi / 2.0, math.pi / 2.0),
    "elbow_rad": (0.0, 2.95),
    "wrist_pitch_rad": (-math.pi / 2.0, math.pi / 2.0),
    "wrist_roll_rad": (-math.pi, math.pi),
    "gripper_raw_rad": (math.pi - MODEL_GRIPPER_OPEN_RAD, math.pi),
}


class ControllerSimulationError(ValueError):
    """A controller-model input is invalid or unsafe to simulate."""


def _finite(value: object, name: str) -> float:
    try:
        return finite_real(value, name=name)
    except (TypeError, ValueError) as exc:
        raise ControllerSimulationError(str(exc)) from exc


@dataclass(frozen=True, slots=True)
class ControllerJointState:
    """Logical controller joint state, all angles in radians."""

    base_rad: float
    shoulder_rad: float
    elbow_rad: float
    wrist_pitch_rad: float
    wrist_roll_rad: float
    gripper_raw_rad: float

    def __post_init__(self) -> None:
        for name in (
            "base_rad",
            "shoulder_rad",
            "elbow_rad",
            "wrist_pitch_rad",
            "wrist_roll_rad",
            "gripper_raw_rad",
        ):
            object.__setattr__(self, name, _finite(getattr(self, name), name))

    def to_dict(self) -> dict[str, float]:
        return {
            "base_rad": self.base_rad,
            "shoulder_rad": self.shoulder_rad,
            "elbow_rad": self.elbow_rad,
            "wrist_pitch_rad": self.wrist_pitch_rad,
            "wrist_roll_rad": self.wrist_roll_rad,
            "gripper_raw_rad": self.gripper_raw_rad,
        }


@dataclass(frozen=True, slots=True)
class ControllerPose:
    """One Cartesian pose in the firmware-specific ``R_ctrl`` frame."""

    x_mm: float
    y_mm: float
    z_mm: float
    pitch_rad: float
    roll_rad: float
    gripper_raw_rad: float
    frame: str = field(default=CONTROLLER_FRAME, init=False)

    def __post_init__(self) -> None:
        for name in (
            "x_mm",
            "y_mm",
            "z_mm",
            "pitch_rad",
            "roll_rad",
            "gripper_raw_rad",
        ):
            object.__setattr__(self, name, _finite(getattr(self, name), name))

    def to_dict(self) -> dict[str, Any]:
        return {
            "frame": self.frame,
            "x_mm": self.x_mm,
            "y_mm": self.y_mm,
            "z_mm": self.z_mm,
            "pitch_rad": self.pitch_rad,
            "roll_rad": self.roll_rad,
            "gripper_raw_rad": self.gripper_raw_rad,
        }


def model_gripper_to_controller_raw(model_position_rad: object) -> float:
    """Convert URDF gripper position (0 closed, 1.5 open) to raw controller g."""

    position = _finite(model_position_rad, "model_position_rad")
    if not MODEL_GRIPPER_CLOSED_RAD <= position <= MODEL_GRIPPER_OPEN_RAD:
        raise ControllerSimulationError("model gripper position must be within [0, 1.5] rad")
    return math.pi - position


def controller_raw_to_model_gripper(controller_raw_rad: object) -> float:
    """Convert the model-corresponding raw controller g range to URDF position."""

    raw = _finite(controller_raw_rad, "controller_raw_rad")
    model = math.pi - raw
    if not MODEL_GRIPPER_CLOSED_RAD <= model <= MODEL_GRIPPER_OPEN_RAD:
        raise ControllerSimulationError(
            "controller raw gripper value is outside the model-equivalent range"
        )
    return model


def controller_forward_kinematics(state: ControllerJointState) -> ControllerPose:
    """Evaluate the audited firmware FK without relating ``R_ctrl`` to URDF frames."""

    if not isinstance(state, ControllerJointState):
        raise TypeError("state must be a ControllerJointState")
    l2_mm = math.hypot(236.82, 30.00)
    a2_rad = math.atan2(30.00, 236.82)
    l3_mm = 144.49
    le_mm = math.hypot(171.67, 13.69)
    ae_rad = math.atan2(13.69, 171.67)

    shoulder_elbow = state.elbow_rad + state.shoulder_rad
    terminal_angle = shoulder_elbow + state.wrist_pitch_rad
    rho_mm = (
        l2_mm * math.sin(state.shoulder_rad + a2_rad)
        + l3_mm * math.sin(shoulder_elbow)
        + le_mm * math.sin(terminal_angle + ae_rad)
    )
    return ControllerPose(
        x_mm=rho_mm * math.cos(state.base_rad),
        y_mm=rho_mm * math.sin(state.base_rad),
        z_mm=(
            l2_mm * math.cos(state.shoulder_rad + a2_rad)
            + l3_mm * math.cos(shoulder_elbow)
            + le_mm * math.cos(terminal_angle + ae_rad)
        ),
        pitch_rad=terminal_angle - math.pi / 2.0,
        roll_rad=state.wrist_roll_rad,
        gripper_raw_rad=state.gripper_raw_rad,
    )


def validate_provisional_simulation_intersection(
    state: ControllerJointState,
) -> ControllerJointState:
    """Reject states outside the documented URDF/controller intersection.

    This check is useful for simulation triage only. Passing it does not make a
    state physically safe, because received-arm hard stops, zero offsets, and
    self-interference limits remain uncharacterized.
    """

    if not isinstance(state, ControllerJointState):
        raise TypeError("state must be a ControllerJointState")
    for name, (lower, upper) in PROVISIONAL_SIMULATION_JOINT_INTERSECTION_RAD.items():
        value = getattr(state, name)
        if value < lower or value > upper:
            raise ControllerSimulationError(
                f"{name}={value} is outside provisional simulation intersection "
                f"[{lower}, {upper}]"
            )
    return state


@dataclass(frozen=True, slots=True)
class T104TraceSample:
    sample_index: int
    interpolation_parameter: float
    cosine_eased_fraction: float
    pose: ControllerPose

    def __post_init__(self) -> None:
        if isinstance(self.sample_index, bool) or not isinstance(self.sample_index, int):
            raise TypeError("sample_index must be an integer")
        if self.sample_index < 0:
            raise ControllerSimulationError("sample_index must be non-negative")
        for name in ("interpolation_parameter", "cosine_eased_fraction"):
            value = _finite(getattr(self, name), name)
            if not 0.0 <= value <= 1.0:
                raise ControllerSimulationError(f"{name} must be within [0, 1]")
            object.__setattr__(self, name, value)
        if not isinstance(self.pose, ControllerPose):
            raise TypeError("pose must be a ControllerPose")

    def to_dict(self) -> dict[str, Any]:
        return {
            "sample_index": self.sample_index,
            "interpolation_parameter": self.interpolation_parameter,
            "cosine_eased_fraction": self.cosine_eased_fraction,
            "pose": self.pose.to_dict(),
        }


@dataclass(frozen=True, slots=True)
class T104SimulationTrace:
    start: ControllerPose
    target: ControllerPose
    spd_coefficient: float
    delta_mixed_units: float
    samples: tuple[T104TraceSample, ...]
    zero_motion_delta: bool

    def __post_init__(self) -> None:
        if not isinstance(self.start, ControllerPose) or not isinstance(self.target, ControllerPose):
            raise TypeError("start and target must be ControllerPose values")
        spd = _finite(self.spd_coefficient, "spd_coefficient")
        if spd <= 0.0 or spd > MAX_SIMULATION_SPD_COEFFICIENT:
            raise ControllerSimulationError("trace spd_coefficient is outside simulation bounds")
        delta = _finite(self.delta_mixed_units, "delta_mixed_units")
        if delta < 0.0:
            raise ControllerSimulationError("delta_mixed_units must be non-negative")
        if not isinstance(self.zero_motion_delta, bool):
            raise TypeError("zero_motion_delta must be boolean")
        if self.zero_motion_delta != (delta == 0.0):
            raise ControllerSimulationError("zero_motion_delta disagrees with delta_mixed_units")
        object.__setattr__(self, "spd_coefficient", spd)
        object.__setattr__(self, "delta_mixed_units", delta)
        object.__setattr__(self, "samples", tuple(self.samples))
        if not self.samples:
            raise ControllerSimulationError("trace must contain at least one sample")

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.simulation.controller_t104.v1",
            "simulation_only": True,
            "live_motion_authorized": False,
            "hardware_accessed": False,
            "hardware_commands_generated": 0,
            "commands_transmitted": 0,
            "controller_frame": CONTROLLER_FRAME,
            "urdf_frame_equivalence_assumed": False,
            "spd_units": "OPAQUE_FIRMWARE_COEFFICIENT",
            "delta_semantics": "max absolute x/y/z/t/r delta with mixed millimetre/radian units",
            "start": self.start.to_dict(),
            "target": self.target.to_dict(),
            "spd_coefficient": self.spd_coefficient,
            "delta_mixed_units": self.delta_mixed_units,
            "zero_motion_delta": self.zero_motion_delta,
            "samples": [sample.to_dict() for sample in self.samples],
        }


def simulate_t104_trace(
    start: ControllerPose,
    target: ControllerPose,
    *,
    spd_coefficient: object,
    maximum_samples: int = MAX_TRACE_SAMPLES,
) -> T104SimulationTrace:
    """Reproduce the T=104 cosine interpolation trace without controller I/O.

    The real firmware mixes millimetres and radians when computing ``delta``.
    That behavior is preserved as a diagnostic fact, not endorsed as a
    physical motion-rate model.  A zero Cartesian delta produces one explicit
    terminal sample so gripper-only behavior is deterministic in simulation.
    """

    if not isinstance(start, ControllerPose) or not isinstance(target, ControllerPose):
        raise TypeError("start and target must be ControllerPose values")
    if isinstance(maximum_samples, bool) or not isinstance(maximum_samples, int):
        raise TypeError("maximum_samples must be an integer")
    if maximum_samples < 2:
        raise ControllerSimulationError("maximum_samples must be at least two")
    spd = _finite(spd_coefficient, "spd_coefficient")
    if spd <= 0.0:
        raise ControllerSimulationError("spd_coefficient must be positive")
    if spd > MAX_SIMULATION_SPD_COEFFICIENT:
        raise ControllerSimulationError(
            f"spd_coefficient exceeds simulation bound {MAX_SIMULATION_SPD_COEFFICIENT:g}"
        )

    start_values = (
        start.x_mm,
        start.y_mm,
        start.z_mm,
        start.pitch_rad,
        start.roll_rad,
    )
    target_values = (
        target.x_mm,
        target.y_mm,
        target.z_mm,
        target.pitch_rad,
        target.roll_rad,
    )
    delta = max(abs(end - begin) for begin, end in zip(start_values, target_values))
    if delta == 0.0:
        terminal = ControllerPose(
            start.x_mm,
            start.y_mm,
            start.z_mm,
            start.pitch_rad,
            start.roll_rad,
            target.gripper_raw_rad,
        )
        samples = (T104TraceSample(0, 1.0, 1.0, terminal),)
        return T104SimulationTrace(start, target, spd, delta, samples, True)

    increment = spd / delta
    if increment <= 0.0 or not math.isfinite(increment):
        raise ControllerSimulationError("computed interpolation increment is invalid")
    intervals = max(1, math.ceil(1.0 / increment))
    if intervals + 1 > maximum_samples:
        raise ControllerSimulationError(
            f"T=104 trace would exceed maximum_samples={maximum_samples}"
        )

    samples_list: list[T104TraceSample] = []
    for index in range(intervals + 1):
        parameter = min(index * increment, 1.0)
        if index == intervals:
            parameter = 1.0
        eased = (1.0 - math.cos(math.pi * parameter)) / 2.0
        values = tuple(
            begin + (end - begin) * eased
            for begin, end in zip(start_values, target_values)
        )
        pose = ControllerPose(
            x_mm=values[0],
            y_mm=values[1],
            z_mm=values[2],
            pitch_rad=values[3],
            roll_rad=values[4],
            gripper_raw_rad=target.gripper_raw_rad,
        )
        samples_list.append(T104TraceSample(index, parameter, eased, pose))

    return T104SimulationTrace(start, target, spd, delta, tuple(samples_list), False)
