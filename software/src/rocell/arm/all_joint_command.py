"""Offline T102 construction; encoding is not motion admission or path approval.

Reference: RoArm-M3_example_20260701.zip, uart_ctrl.h:23-33 and
RoArm-M3_module.h:825-840. Settings are firmware units, not rad/s or rad/s².
This module deliberately owns no transport and makes no installed-version claim.
"""
from collections.abc import Mapping, Sequence

from .protocol import ProtocolError, _finite_number

JOINT_FIELDS = ("base", "shoulder", "elbow", "wrist", "roll", "hand")


def all_joint_command(joints_rad: Sequence[float], *, speed: int,
                      acceleration: int) -> dict[str, int | float]:
    """Encode six absolute targets with explicit, nonzero firmware settings.

    Integer limits are reference C++ argument widths, NOT safe operating limits.
    A separate trial policy must restrict rates, joint limits and swept geometry.
    Zero is deliberately excluded to avoid firmware special/default semantics.
    """
    if len(joints_rad) != 6:
        raise ProtocolError("Exactly six joint targets are required")
    for name, value, limit in (("speed", speed, 65535),
                               ("acceleration", acceleration, 255)):
        if type(value) is not int or not 1 <= value <= limit:
            raise ProtocolError(f"{name} must be an explicit integer in 1..{limit}")
    return {"T": 102,
            **{name: _finite_number(name, value)
               for name, value in zip(JOINT_FIELDS, joints_rad)},
            "spd": speed, "acc": acceleration}


def identification_command(baseline_rad: Sequence[float],
                           target_overrides: Mapping[str, float], *,
                           speed: int, acceleration: int) -> dict[str, int | float]:
    """Preserve every non-test target numerically from the supplied baseline.

    Caller must establish feedback freshness. Re-commanding a reported position
    can still move a servo; unchanged fields are not a physical no-motion promise.
    """
    if not target_overrides or set(target_overrides) - set(JOINT_FIELDS):
        raise ProtocolError("Explicit named joint overrides are required")
    command = all_joint_command(baseline_rad, speed=speed, acceleration=acceleration)
    for name, value in target_overrides.items():
        command[name] = _finite_number(name, value)
    return command
