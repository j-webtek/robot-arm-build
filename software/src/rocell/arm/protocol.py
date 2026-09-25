"""Typed, side-effect-free encoding for the RoArm-M3 JSON wire protocol.

Only the deliberately small Phase-3 command surface is represented here.  All
lengths exposed to callers are millimetres and all angles are radians.  The
firmware's ``spd`` value is intentionally kept as an opaque coefficient.
"""

from __future__ import annotations

from dataclasses import dataclass
import json
import math
from typing import Any, Mapping, Sequence


FEEDBACK_REQUEST_TYPE = 105
FEEDBACK_RESPONSE_TYPE = 1051
CARTESIAN_TARGET_TYPE = 104
PROHIBITED_DIRECT_TARGET_TYPE = 1041


class ProtocolError(ValueError):
    """A message does not satisfy the controlled RoArm protocol boundary."""


class UnsupportedCommandError(ProtocolError):
    """A command is intentionally unavailable through this boundary."""


def _finite_number(name: str, value: object) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise ProtocolError(f"{name} must be a real number")
    parsed = float(value)
    if not math.isfinite(parsed):
        raise ProtocolError(f"{name} must be finite")
    return parsed


def _validate_json_value(value: object, path: str = "$") -> None:
    if value is None or isinstance(value, (str, bool)):
        return
    if isinstance(value, int):
        return
    if isinstance(value, float):
        if not math.isfinite(value):
            raise ProtocolError(f"{path} contains a nonfinite number")
        return
    if isinstance(value, list):
        for index, item in enumerate(value):
            _validate_json_value(item, f"{path}[{index}]")
        return
    if isinstance(value, dict):
        for key, item in value.items():
            if not isinstance(key, str):
                raise ProtocolError(f"{path} contains a non-string object key")
            _validate_json_value(item, f"{path}.{key}")
        return
    raise ProtocolError(f"{path} contains unsupported JSON value {type(value).__name__}")


def validate_message(message: Mapping[str, Any]) -> None:
    """Validate a complete inbound or outbound protocol object.

    T=1041 is denied in both directions so it cannot be accidentally replayed
    through a generic message path.
    """

    if not isinstance(message, Mapping):
        raise ProtocolError("RoArm message must be a JSON object")
    if "T" not in message:
        raise ProtocolError("RoArm message is missing command field T")
    command_type = message["T"]
    if isinstance(command_type, bool) or not isinstance(command_type, int):
        raise ProtocolError("RoArm command field T must be an integer")
    if command_type == PROHIBITED_DIRECT_TARGET_TYPE:
        raise UnsupportedCommandError("T=1041 is prohibited by the contact-motion boundary")
    _validate_json_value(dict(message))


def _reject_json_constant(value: str) -> None:
    raise ProtocolError(f"Nonfinite JSON constant {value!r} is prohibited")


def _object_without_duplicates(pairs: Sequence[tuple[str, Any]]) -> dict[str, Any]:
    result: dict[str, Any] = {}
    for key, value in pairs:
        if key in result:
            raise ProtocolError(f"Duplicate JSON field {key!r} is prohibited")
        result[key] = value
    return result


def encode_line(message: Mapping[str, Any]) -> bytes:
    """Encode one compact UTF-8 JSON object followed by exactly one LF."""

    validate_message(message)
    try:
        payload = json.dumps(
            dict(message),
            ensure_ascii=True,
            allow_nan=False,
            separators=(",", ":"),
        )
    except (TypeError, ValueError) as exc:
        raise ProtocolError(f"Could not encode RoArm message: {exc}") from exc
    return payload.encode("utf-8") + b"\n"


def decode_line(line: bytes | str) -> dict[str, Any]:
    """Decode exactly one LF- or CRLF-terminated JSON protocol object."""

    if isinstance(line, bytes):
        try:
            text = line.decode("utf-8")
        except UnicodeDecodeError as exc:
            raise ProtocolError("RoArm line is not valid UTF-8") from exc
    elif isinstance(line, str):
        text = line
    else:
        raise ProtocolError("RoArm line must be bytes or text")

    if not text.endswith("\n"):
        raise ProtocolError("RoArm message is not newline terminated")
    payload = text[:-1]
    if payload.endswith("\r"):
        payload = payload[:-1]
    if not payload:
        raise ProtocolError("RoArm message is empty")
    if "\n" in payload or "\r" in payload:
        raise ProtocolError("RoArm input contains more than one line")

    try:
        decoded = json.loads(
            payload,
            parse_constant=_reject_json_constant,
            object_pairs_hook=_object_without_duplicates,
        )
    except json.JSONDecodeError as exc:
        raise ProtocolError(f"Invalid RoArm JSON: {exc.msg}") from exc
    if not isinstance(decoded, dict):
        raise ProtocolError("RoArm message must decode to a JSON object")
    validate_message(decoded)
    return decoded


def feedback_request() -> dict[str, int]:
    """Return the documented T=105 raw-feedback request."""

    return {"T": FEEDBACK_REQUEST_TYPE}


@dataclass(frozen=True, slots=True)
class CartesianGoal:
    """A complete typed T=104 target in millimetres and radians.

    Waveshare names the endpoint axes ``x``, ``y``, ``z``, ``t``, ``r``, and
    ``g``.  The first three are millimetres; pitch, roll, and gripper are
    radians.  ``spd`` remains an opaque firmware curve coefficient.
    """

    x_mm: float
    y_mm: float
    z_mm: float
    pitch_rad: float
    roll_rad: float
    gripper_rad: float
    spd: float

    def __post_init__(self) -> None:
        object.__setattr__(self, "x_mm", _finite_number("x_mm", self.x_mm))
        object.__setattr__(self, "y_mm", _finite_number("y_mm", self.y_mm))
        object.__setattr__(self, "z_mm", _finite_number("z_mm", self.z_mm))
        object.__setattr__(
            self,
            "pitch_rad",
            _finite_number("pitch_rad", self.pitch_rad),
        )
        object.__setattr__(self, "roll_rad", _finite_number("roll_rad", self.roll_rad))
        object.__setattr__(
            self,
            "gripper_rad",
            _finite_number("gripper_rad", self.gripper_rad),
        )
        object.__setattr__(self, "spd", _finite_number("spd", self.spd))

    @property
    def spd_coefficient(self) -> float:
        """Expose the firmware value without assigning physical speed units."""

        return self.spd

    def to_message(self) -> dict[str, int | float]:
        return {
            "T": CARTESIAN_TARGET_TYPE,
            "x": self.x_mm,
            "y": self.y_mm,
            "z": self.z_mm,
            "t": self.pitch_rad,
            "r": self.roll_rad,
            "g": self.gripper_rad,
            "spd": self.spd,
        }
