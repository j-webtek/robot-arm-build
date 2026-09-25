"""Lossless parsing for installed-firmware RoArm feedback snapshots."""

from __future__ import annotations

from copy import deepcopy
from dataclasses import dataclass
import math
from typing import Any, Mapping

from .protocol import FEEDBACK_RESPONSE_TYPE, ProtocolError, decode_line, validate_message


class FeedbackError(ProtocolError):
    """A reply is not a valid T=1051 feedback snapshot."""


# This set documents the fields currently known from the public command family.
# Every source field, including these and future firmware additions, also remains
# available unchanged in ``raw_fields``.
KNOWN_1051_FIELDS = frozenset(
    {
        "T",
        "x",
        "y",
        "z",
        "tit",
        "b",
        "s",
        "e",
        "t",
        "r",
        "g",
        "tB",
        "tS",
        "tE",
        "tT",
        "tR",
        "tG",
        "torswitchB",
        "torswitchS",
        "torswitchE",
        "torswitchT",
        "torswitchR",
        "torswitchG",
        "v",
    }
)

LOAD_FIELDS = {
    "base": "tB",
    "shoulder": "tS",
    "elbow": "tE",
    "wrist_pitch": "tT",
    "wrist_roll": "tR",
    "gripper": "tG",
}

TORQUE_SWITCH_FIELDS = {
    "base": "torswitchB",
    "shoulder": "torswitchS",
    "elbow": "torswitchE",
    "wrist_pitch": "torswitchT",
    "wrist_roll": "torswitchR",
    "gripper": "torswitchG",
}


def _optional_finite_number(message: Mapping[str, Any], key: str) -> float | None:
    if key not in message:
        return None
    value = message[key]
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise FeedbackError(f"Feedback field {key!r} must be numeric when present")
    result = float(value)
    if not math.isfinite(result):
        raise FeedbackError(f"Feedback field {key!r} must be finite")
    return result


@dataclass(frozen=True, slots=True)
class Feedback1051:
    """Typed core pose fields plus a lossless snapshot of the complete reply."""

    x_mm: float | None
    y_mm: float | None
    z_mm: float | None
    endpoint_pitch_rad: float | None
    base_rad: float | None
    shoulder_rad: float | None
    elbow_rad: float | None
    wrist_pitch_rad: float | None
    wrist_roll_rad: float | None
    gripper_rad: float | None
    loads_raw: dict[str, float]
    torque_switches: dict[str, bool]
    voltage_raw_0p01_v: float | None
    raw_fields: dict[str, Any]
    unknown_fields: dict[str, Any]

    def field(self, name: str, default: Any = None) -> Any:
        """Read any retained installed-firmware field without schema loss."""

        return self.raw_fields.get(name, default)

    @property
    def voltage_v(self) -> float | None:
        """Return voltage in volts while retaining the firmware's raw field."""

        if self.voltage_raw_0p01_v is None:
            return None
        return self.voltage_raw_0p01_v * 0.01


def parse_feedback_1051(message: Mapping[str, Any]) -> Feedback1051:
    """Parse T=1051 while retaining all recognized and unrecognized fields."""

    try:
        validate_message(message)
    except ProtocolError as exc:
        raise FeedbackError(str(exc)) from exc
    if message.get("T") != FEEDBACK_RESPONSE_TYPE:
        raise FeedbackError(
            f"Expected T={FEEDBACK_RESPONSE_TYPE} feedback, received T={message.get('T')!r}"
        )

    # deepcopy prevents later mutation of the decoder/caller's object from
    # silently changing the evidence retained by this feedback value.
    snapshot = deepcopy(dict(message))
    unknown = {
        key: deepcopy(value)
        for key, value in snapshot.items()
        if key not in KNOWN_1051_FIELDS
    }
    loads_raw = {
        name: value
        for name, key in LOAD_FIELDS.items()
        if (value := _optional_finite_number(snapshot, key)) is not None
    }
    torque_switches: dict[str, bool] = {}
    for name, key in TORQUE_SWITCH_FIELDS.items():
        if key not in snapshot:
            continue
        value = snapshot[key]
        if value not in (0, 1) or isinstance(value, bool):
            raise FeedbackError(f"Feedback field {key!r} must be integer 0 or 1")
        torque_switches[name] = bool(value)
    return Feedback1051(
        x_mm=_optional_finite_number(snapshot, "x"),
        y_mm=_optional_finite_number(snapshot, "y"),
        z_mm=_optional_finite_number(snapshot, "z"),
        endpoint_pitch_rad=_optional_finite_number(snapshot, "tit"),
        base_rad=_optional_finite_number(snapshot, "b"),
        shoulder_rad=_optional_finite_number(snapshot, "s"),
        elbow_rad=_optional_finite_number(snapshot, "e"),
        wrist_pitch_rad=_optional_finite_number(snapshot, "t"),
        wrist_roll_rad=_optional_finite_number(snapshot, "r"),
        gripper_rad=_optional_finite_number(snapshot, "g"),
        loads_raw=loads_raw,
        torque_switches=torque_switches,
        voltage_raw_0p01_v=_optional_finite_number(snapshot, "v"),
        raw_fields=snapshot,
        unknown_fields=unknown,
    )


def parse_feedback_line(line: bytes | str) -> Feedback1051:
    return parse_feedback_1051(decode_line(line))
