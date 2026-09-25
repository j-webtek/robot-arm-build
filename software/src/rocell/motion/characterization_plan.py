"""Canonical finite Cartesian characterization plans, with no device authority.

Every return/repetition is an explicit trial. Construction validates numeric
budgets and continuity, not robot IK or swept-link clearance. Bounds are caller-
supplied planning constraints, never claims about the installed robot's limits.
T104 speed is a coefficient; acceleration is not invented for this command.
"""

from dataclasses import dataclass
import hashlib
import json
import math
import re

AXES = ("x_mm", "y_mm", "z_mm", "pitch_rad", "roll_rad", "gripper_rad")
SCHEMA = "rocell.characterization_plan.v1"


def _keys(value, expected, label):
    if type(value) is not dict or set(value) != set(expected):
        raise ValueError(f"{label}: unexpected or missing fields")


def _number(value, label, *, positive=False):
    # The absolute ceiling is a software numeric-work limit, not a robot limit.
    if type(value) not in (int, float):
        raise ValueError(f"{label}: expected a finite number")
    try:
        number = float(value)
    except OverflowError as error:
        raise ValueError(f"{label}: numeric range exceeded") from error
    if not math.isfinite(number) or abs(number) > 1e6 or (positive and number <= 0):
        raise ValueError(f"{label}: numeric range exceeded")
    return 0.0 if number == 0 else number


def _id(value, label):
    if type(value) is not str or re.fullmatch(r"[a-zA-Z0-9_-]{1,80}", value) is None:
        raise ValueError(f"{label}: expected a bounded identifier")
    return value


def _pose(value):
    _keys(value, AXES, "pose")
    return {axis: _number(value[axis], axis) for axis in AXES}


@dataclass(frozen=True, slots=True)
class FrozenCampaign:
    """Detached canonical plan bytes; a hash identifies content, not approval."""

    canonical_bytes: bytes

    def __post_init__(self):
        # Do not allow direct construction to bypass the same validation path.
        if type(self.canonical_bytes) is not bytes or len(self.canonical_bytes) > 256*1024:
            raise ValueError("Invalid plan bytes")
        normalized = _normalize(json.loads(self.canonical_bytes))
        if _canonical(normalized) != self.canonical_bytes:
            raise ValueError("Plan is not canonical")

    @property
    def sha256(self):
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def to_dict(self):
        return json.loads(self.canonical_bytes)

    def preview(self):
        plan = self.to_dict()
        return {
            "plan_sha256": self.sha256, "trial_count": len(plan["trials"]),
            "maximum_duration_s": sum(t["timeout_s"] for t in plan["trials"]),
            "frame": plan["frame"], "speed_units": "FIRMWARE_COEFFICIENT",
            "acceleration": "NOT_EXPOSED_BY_T104",
            "geometry_status": "UNQUALIFIED", "motion_authorized": False,
            "physical_ready": False, "trials": plan["trials"],
        }


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()


def _normalize(value):
    _keys(value, {"schema", "campaign_id", "frame", "evidence", "limits", "trials"}, "plan")
    if value["schema"] != SCHEMA or value["frame"] not in {"robot_base", "R_ctrl"}:
        raise ValueError("Unsupported schema or coordinate frame")
    evidence = value["evidence"]
    _keys(evidence, {"source_sha256", "configuration_sha256", "firmware_review_sha256",
                     "geometry_sha256", "usb_identity", "tool_payload_id"}, "evidence")
    for key in ("source_sha256", "configuration_sha256", "firmware_review_sha256", "geometry_sha256"):
        if type(evidence[key]) is not str or re.fullmatch(r"[0-9a-f]{64}", evidence[key]) is None:
            raise ValueError(f"Invalid {key}")
    for key in ("usb_identity", "tool_payload_id"):
        _id(evidence[key], key)
    limits = value["limits"]
    _keys(limits, {"minimum_pose", "maximum_pose", "max_translation_mm", "max_rotation_rad",
                   "min_spd", "max_spd", "max_trials", "max_duration_s"}, "limits")
    low, high = _pose(limits["minimum_pose"]), _pose(limits["maximum_pose"])
    if any(low[axis] > high[axis] for axis in AXES):
        raise ValueError("Inverted pose envelope")
    normalized_limits = {"minimum_pose": low, "maximum_pose": high}
    for key in ("max_translation_mm", "max_rotation_rad", "min_spd", "max_spd", "max_duration_s"):
        normalized_limits[key] = _number(limits[key], key, positive=True)
    if normalized_limits["min_spd"] > normalized_limits["max_spd"]:
        raise ValueError("Inverted speed bounds")
    count = limits["max_trials"]
    if type(count) is not int or not 1 <= count <= 128:
        raise ValueError("Trial count must be from 1 through 128")
    normalized_limits["max_trials"] = count
    trials = value["trials"]
    if type(trials) is not list or not 1 <= len(trials) <= count:
        raise ValueError("Empty or oversized campaign")
    result, identifiers, previous = [], set(), None
    for trial in trials:
        _keys(trial, {"trial_id", "command_family", "start", "target", "spd",
                     "dwell_s", "timeout_s", "stop"}, "trial")
        identifier = _id(trial["trial_id"], "trial_id")
        if identifier in identifiers:
            raise ValueError("Duplicate trial ID")
        identifiers.add(identifier)
        if trial["command_family"] != "T104":
            raise ValueError("Only typed Cartesian T104 candidates are represented")
        start, target = _pose(trial["start"]), _pose(trial["target"])
        if previous is not None and previous != start:
            raise ValueError("Discontinuous trial: return or reposition must be explicit")
        for pose in (start, target):
            if any(not low[axis] <= pose[axis] <= high[axis] for axis in AXES):
                raise ValueError("Pose outside planning envelope")
        distance = math.dist([start[a] for a in AXES[:3]], [target[a] for a in AXES[:3]])
        rotation = max(abs(target[a]-start[a]) for a in AXES[3:])
        # No shortest-angle wrapping: winding and joint limits are unqualified.
        if distance == 0 and rotation == 0:
            raise ValueError("A motion trial must contain an explicit nonzero change")
        if distance > normalized_limits["max_translation_mm"] or rotation > normalized_limits["max_rotation_rad"]:
            raise ValueError("Move exceeds per-trial displacement bound")
        spd = _number(trial["spd"], "spd", positive=True)
        if not normalized_limits["min_spd"] <= spd <= normalized_limits["max_spd"]:
            raise ValueError("Speed outside planning bounds")
        dwell, timeout = (_number(trial[k], k, positive=True) for k in ("dwell_s", "timeout_s"))
        if dwell >= timeout:
            raise ValueError("Timeout must include movement and dwell")
        stop = trial["stop"]
        _keys(stop, {"max_read_gap_s", "position_tolerance_mm", "angle_tolerance_rad",
                     "max_endpoint_error_mm"}, "stop")
        stop = {key: _number(v, key, positive=True) for key,v in stop.items()}
        if stop["max_read_gap_s"] > dwell or stop["position_tolerance_mm"] > stop["max_endpoint_error_mm"]:
            raise ValueError("Inconsistent stop/tolerance policy")
        result.append({"trial_id": identifier, "command_family": "T104", "start": start,
                       "target": target, "spd": spd, "dwell_s": dwell, "timeout_s": timeout, "stop": stop})
        previous = target
    if sum(t["timeout_s"] for t in result) > normalized_limits["max_duration_s"]:
        raise ValueError("Campaign exceeds duration budget")
    return {"schema": SCHEMA, "campaign_id": _id(value["campaign_id"], "campaign_id"),
            "frame": value["frame"], "evidence": dict(evidence), "limits": normalized_limits, "trials": result}


def freeze_campaign(value: dict) -> FrozenCampaign:
    """Validate/detach a candidate, without opening a device or granting a permit."""
    return FrozenCampaign(_canonical(_normalize(value)))
