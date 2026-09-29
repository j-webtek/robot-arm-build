"""Fail-closed, simulator-neutral request and receipt contracts for Isaac Sim.

This module imports no NVIDIA package and exposes no transport or controller
capability.  It is safe to use in ordinary hardware-free CI.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import math
import re
from typing import Any, Mapping, Sequence

REQUEST_SCHEMA = "rocell.isaac_sim_run_request.v1"
RECEIPT_SCHEMA = "rocell.isaac_sim_run_receipt.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_IDENTIFIER = re.compile(r"^[A-Za-z0-9][A-Za-z0-9._:-]{0,127}$")


class IsaacSimContractError(ValueError):
    """An Isaac simulation envelope is incomplete, inconsistent, or unsafe."""


def canonical_bytes(value: object) -> bytes:
    try:
        return json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    except (TypeError, ValueError) as exc:
        raise IsaacSimContractError(
            "document must contain only finite canonical JSON values"
        ) from exc


def canonical_sha256(value: object) -> str:
    return hashlib.sha256(canonical_bytes(value)).hexdigest()


def _mapping(value: object, label: str) -> Mapping[str, Any]:
    if not isinstance(value, Mapping):
        raise IsaacSimContractError(f"{label} must be an object")
    return value


def _exact_keys(
    value: Mapping[str, Any], required: set[str], label: str
) -> None:
    missing = sorted(required.difference(value))
    extra = sorted(set(value).difference(required))
    if missing:
        raise IsaacSimContractError(f"{label} missing fields: {', '.join(missing)}")
    if extra:
        raise IsaacSimContractError(f"{label} has unknown fields: {', '.join(extra)}")


def _digest(value: object, label: str) -> str:
    if not isinstance(value, str) or _SHA256.fullmatch(value) is None:
        raise IsaacSimContractError(f"{label} must be a lowercase SHA-256 digest")
    return value


def _identifier(value: object, label: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise IsaacSimContractError(f"{label} is not a valid identifier")
    return value


def _text(value: object, label: str, *, allow_empty: bool = False) -> str:
    if not isinstance(value, str) or (not allow_empty and not value):
        raise IsaacSimContractError(f"{label} must be a nonempty string")
    return value


def _integer(value: object, label: str, *, minimum: int = 0) -> int:
    if isinstance(value, bool) or not isinstance(value, int) or value < minimum:
        raise IsaacSimContractError(f"{label} must be an integer >= {minimum}")
    return value


def _finite(value: object, label: str, *, positive: bool = False) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise IsaacSimContractError(f"{label} must be a finite number")
    result = float(value)
    if not math.isfinite(result) or (positive and result <= 0.0):
        qualifier = "positive finite" if positive else "finite"
        raise IsaacSimContractError(f"{label} must be a {qualifier} number")
    return result


def _string_tuple(
    value: object, label: str, *, nonempty: bool = False, unique: bool = False
) -> tuple[str, ...]:
    if not isinstance(value, Sequence) or isinstance(value, (str, bytes)):
        raise IsaacSimContractError(f"{label} must be an array")
    result = tuple(_text(item, f"{label} item") for item in value)
    if nonempty and not result:
        raise IsaacSimContractError(f"{label} must not be empty")
    if unique and len(set(result)) != len(result):
        raise IsaacSimContractError(f"{label} must contain unique values")
    return result


def _zero_authority(document: Mapping[str, Any], label: str) -> None:
    if document.get("hardware_access") is not False:
        raise IsaacSimContractError(f"{label}.hardware_access must be false")
    if document.get("physical_authority") is not False:
        raise IsaacSimContractError(f"{label}.physical_authority must be false")
    if document.get("wire_commands") != []:
        raise IsaacSimContractError(f"{label}.wire_commands must be empty")


@dataclass(frozen=True, slots=True)
class IsaacSimRunRequest:
    """Validated canonical simulation job with an embedded content digest."""

    _document: Mapping[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IsaacSimRunRequest":
        document = dict(_mapping(value, "request"))
        fields = {
            "schema", "request_id", "created_by", "toolchain", "system",
            "scene", "frames", "articulation", "trajectory", "observation",
            "wire_commands", "hardware_access", "physical_authority",
            "request_sha256",
        }
        _exact_keys(document, fields, "request")
        if document["schema"] != REQUEST_SCHEMA:
            raise IsaacSimContractError("unsupported request schema")
        _identifier(document["request_id"], "request_id")
        _identifier(document["created_by"], "created_by")
        _zero_authority(document, "request")
        cls._validate_toolchain(document["toolchain"])
        cls._validate_system(document["system"])
        cls._validate_scene(document["scene"])
        cls._validate_frames(document["frames"])
        joints = cls._validate_articulation(document["articulation"])
        cls._validate_trajectory(document["trajectory"], joints)
        cls._validate_observation(document["observation"])
        claimed = _digest(document["request_sha256"], "request_sha256")
        unsigned = {k: v for k, v in document.items() if k != "request_sha256"}
        if canonical_sha256(unsigned) != claimed:
            raise IsaacSimContractError("request_sha256 does not match request content")
        # Canonical round-trip makes the retained mapping detached and JSON-only.
        retained = json.loads(canonical_bytes(document).decode("ascii"))
        return cls(retained)

    @classmethod
    def seal(cls, unsigned: Mapping[str, Any]) -> "IsaacSimRunRequest":
        if "request_sha256" in unsigned:
            raise IsaacSimContractError("unsigned request must omit request_sha256")
        document = dict(unsigned)
        document["request_sha256"] = canonical_sha256(document)
        return cls.from_dict(document)

    @staticmethod
    def _validate_toolchain(value: object) -> None:
        item = _mapping(value, "toolchain")
        _exact_keys(item, {
            "isaac_sim_version", "installation_sha256",
            "extension_lock_sha256", "settings_profile_sha256",
        }, "toolchain")
        _text(item["isaac_sim_version"], "toolchain.isaac_sim_version")
        for name in (
            "installation_sha256", "extension_lock_sha256",
            "settings_profile_sha256",
        ):
            _digest(item[name], f"toolchain.{name}")

    @staticmethod
    def _validate_system(value: object) -> None:
        item = _mapping(value, "system")
        _exact_keys(item, {
            "system_manifest_id", "system_manifest_sha256", "source_revision",
        }, "system")
        _identifier(item["system_manifest_id"], "system.system_manifest_id")
        _digest(item["system_manifest_sha256"], "system.system_manifest_sha256")
        _text(item["source_revision"], "system.source_revision")

    @staticmethod
    def _validate_scene(value: object) -> None:
        item = _mapping(value, "scene")
        _exact_keys(item, {
            "scene_usd_sha256", "arm_asset_sha256", "meters_per_unit",
            "up_axis", "physics", "random_seed",
        }, "scene")
        _digest(item["scene_usd_sha256"], "scene.scene_usd_sha256")
        _digest(item["arm_asset_sha256"], "scene.arm_asset_sha256")
        _finite(item["meters_per_unit"], "scene.meters_per_unit", positive=True)
        if item["up_axis"] not in ("Y", "Z"):
            raise IsaacSimContractError("scene.up_axis must be Y or Z")
        _integer(item["random_seed"], "scene.random_seed")
        physics = _mapping(item["physics"], "scene.physics")
        _exact_keys(physics, {
            "time_step_s", "substeps", "solver", "gravity_m_s2",
        }, "scene.physics")
        _finite(physics["time_step_s"], "scene.physics.time_step_s", positive=True)
        _integer(physics["substeps"], "scene.physics.substeps", minimum=1)
        _text(physics["solver"], "scene.physics.solver")
        gravity = physics["gravity_m_s2"]
        if not isinstance(gravity, Sequence) or isinstance(gravity, (str, bytes)) or len(gravity) != 3:
            raise IsaacSimContractError("scene.physics.gravity_m_s2 must contain three numbers")
        for index, component in enumerate(gravity):
            _finite(component, f"scene.physics.gravity_m_s2[{index}]")

    @staticmethod
    def _validate_frames(value: object) -> None:
        item = _mapping(value, "frames")
        _exact_keys(item, {"frame_graph_sha256", "world_frame", "robot_base_frame"}, "frames")
        _digest(item["frame_graph_sha256"], "frames.frame_graph_sha256")
        _identifier(item["world_frame"], "frames.world_frame")
        _identifier(item["robot_base_frame"], "frames.robot_base_frame")
        if item["world_frame"] == item["robot_base_frame"]:
            raise IsaacSimContractError("world and robot-base frames must differ")

    @staticmethod
    def _validate_articulation(value: object) -> tuple[str, ...]:
        item = _mapping(value, "articulation")
        _exact_keys(item, {
            "joint_names", "initial_positions_rad", "drive_configuration_sha256",
            "joint_limits",
        }, "articulation")
        joints = _string_tuple(item["joint_names"], "articulation.joint_names", nonempty=True, unique=True)
        positions = item["initial_positions_rad"]
        if not isinstance(positions, Sequence) or isinstance(positions, (str, bytes)) or len(positions) != len(joints):
            raise IsaacSimContractError("initial_positions_rad must match joint_names")
        for index, position in enumerate(positions):
            _finite(position, f"articulation.initial_positions_rad[{index}]")
        _digest(item["drive_configuration_sha256"], "articulation.drive_configuration_sha256")
        limits = _mapping(item["joint_limits"], "articulation.joint_limits")
        if set(limits) != set(joints):
            raise IsaacSimContractError("joint_limits must exactly match joint_names")
        for joint, raw_limit in limits.items():
            limit = _mapping(raw_limit, f"joint_limits.{joint}")
            _exact_keys(limit, {"lower_rad", "upper_rad", "maximum_velocity_rad_s", "maximum_effort"}, f"joint_limits.{joint}")
            lower = _finite(limit["lower_rad"], f"joint_limits.{joint}.lower_rad")
            upper = _finite(limit["upper_rad"], f"joint_limits.{joint}.upper_rad")
            if lower >= upper:
                raise IsaacSimContractError(f"joint_limits.{joint} lower must be below upper")
            _finite(limit["maximum_velocity_rad_s"], f"joint_limits.{joint}.maximum_velocity_rad_s", positive=True)
            _finite(limit["maximum_effort"], f"joint_limits.{joint}.maximum_effort", positive=True)
        return joints

    @staticmethod
    def _validate_trajectory(value: object, joints: tuple[str, ...]) -> None:
        item = _mapping(value, "trajectory")
        _exact_keys(item, {"trajectory_sha256", "samples"}, "trajectory")
        _digest(item["trajectory_sha256"], "trajectory.trajectory_sha256")
        samples = item["samples"]
        if not isinstance(samples, Sequence) or isinstance(samples, (str, bytes)) or len(samples) < 2:
            raise IsaacSimContractError("trajectory.samples must contain at least two samples")
        prior = -1
        unsigned_samples: list[dict[str, Any]] = []
        for index, raw_sample in enumerate(samples):
            sample = _mapping(raw_sample, f"trajectory.samples[{index}]")
            _exact_keys(sample, {"time_from_start_ns", "joint_positions_rad"}, f"trajectory.samples[{index}]")
            time_ns = _integer(sample["time_from_start_ns"], f"trajectory.samples[{index}].time_from_start_ns")
            if time_ns <= prior:
                raise IsaacSimContractError("trajectory sample times must increase strictly")
            prior = time_ns
            positions = sample["joint_positions_rad"]
            if not isinstance(positions, Sequence) or isinstance(positions, (str, bytes)) or len(positions) != len(joints):
                raise IsaacSimContractError("trajectory sample positions must match joint_names")
            checked = [_finite(position, f"trajectory.samples[{index}].joint_positions_rad") for position in positions]
            unsigned_samples.append({"time_from_start_ns": time_ns, "joint_positions_rad": checked})
        if canonical_sha256(unsigned_samples) != item["trajectory_sha256"]:
            raise IsaacSimContractError("trajectory_sha256 does not match samples")

    @staticmethod
    def _validate_observation(value: object) -> None:
        item = _mapping(value, "observation")
        _exact_keys(item, {
            "required_link_transforms", "clearance_pairs", "camera_ids",
            "capture_collisions", "capture_contacts", "capture_joint_tracking",
        }, "observation")
        _string_tuple(item["required_link_transforms"], "observation.required_link_transforms", unique=True)
        _string_tuple(item["clearance_pairs"], "observation.clearance_pairs", unique=True)
        _string_tuple(item["camera_ids"], "observation.camera_ids", unique=True)
        for name in ("capture_collisions", "capture_contacts", "capture_joint_tracking"):
            if not isinstance(item[name], bool):
                raise IsaacSimContractError(f"observation.{name} must be boolean")

    @property
    def request_id(self) -> str:
        return str(self._document["request_id"])

    @property
    def request_sha256(self) -> str:
        return str(self._document["request_sha256"])

    def to_dict(self) -> dict[str, Any]:
        return json.loads(canonical_bytes(self._document).decode("ascii"))


@dataclass(frozen=True, slots=True)
class IsaacSimRunReceipt:
    """Validated zero-authority simulation result bound to one request."""

    _document: Mapping[str, Any]

    @classmethod
    def from_dict(cls, value: Mapping[str, Any]) -> "IsaacSimRunReceipt":
        document = dict(_mapping(value, "receipt"))
        fields = {
            "schema", "request_id", "request_sha256", "evidence_class",
            "toolchain", "execution", "import_parity", "tracking", "geometry",
            "contact", "vision", "differential", "reproducibility", "status",
            "reason_codes", "limitations", "wire_commands", "hardware_access",
            "physical_authority", "gate_promotions", "receipt_sha256",
        }
        _exact_keys(document, fields, "receipt")
        if document["schema"] != RECEIPT_SCHEMA:
            raise IsaacSimContractError("unsupported receipt schema")
        _identifier(document["request_id"], "request_id")
        _digest(document["request_sha256"], "request_sha256")
        if document["evidence_class"] not in ("CONTRACT_TEST_ONLY", "ISAAC_SIM_ADVISORY"):
            raise IsaacSimContractError("unsupported receipt evidence_class")
        _zero_authority(document, "receipt")
        if document["gate_promotions"] != []:
            raise IsaacSimContractError("receipt.gate_promotions must be empty")
        if document["status"] not in ("PASS", "REJECT", "ERROR"):
            raise IsaacSimContractError("receipt.status is invalid")
        reasons = _string_tuple(document["reason_codes"], "receipt.reason_codes", unique=True)
        _string_tuple(document["limitations"], "receipt.limitations", nonempty=True, unique=True)
        if document["status"] != "PASS" and not reasons:
            raise IsaacSimContractError("non-PASS receipt requires a reason code")
        cls._validate_sections(document)
        claimed = _digest(document["receipt_sha256"], "receipt_sha256")
        unsigned = {k: v for k, v in document.items() if k != "receipt_sha256"}
        if canonical_sha256(unsigned) != claimed:
            raise IsaacSimContractError("receipt_sha256 does not match receipt content")
        retained = json.loads(canonical_bytes(document).decode("ascii"))
        return cls(retained)

    @classmethod
    def seal(cls, unsigned: Mapping[str, Any]) -> "IsaacSimRunReceipt":
        if "receipt_sha256" in unsigned:
            raise IsaacSimContractError("unsigned receipt must omit receipt_sha256")
        document = dict(unsigned)
        document["receipt_sha256"] = canonical_sha256(document)
        return cls.from_dict(document)

    @staticmethod
    def _validate_sections(document: Mapping[str, Any]) -> None:
        toolchain = _mapping(document["toolchain"], "receipt.toolchain")
        _exact_keys(toolchain, {"isaac_sim_version", "installation_sha256", "backend"}, "receipt.toolchain")
        _text(toolchain["isaac_sim_version"], "receipt.toolchain.isaac_sim_version")
        _digest(toolchain["installation_sha256"], "receipt.toolchain.installation_sha256")
        if toolchain["backend"] not in ("FAKE", "ISAAC_SIM"):
            raise IsaacSimContractError("receipt.toolchain.backend is invalid")
        execution = _mapping(document["execution"], "receipt.execution")
        _exact_keys(execution, {"step_count", "time_step_s", "substeps", "random_seed", "gpu", "driver", "renderer", "physics_backend"}, "receipt.execution")
        _integer(execution["step_count"], "receipt.execution.step_count")
        _finite(execution["time_step_s"], "receipt.execution.time_step_s", positive=True)
        _integer(execution["substeps"], "receipt.execution.substeps", minimum=1)
        _integer(execution["random_seed"], "receipt.execution.random_seed")
        for name in ("gpu", "driver", "renderer", "physics_backend"):
            _text(execution[name], f"receipt.execution.{name}")
        for name in ("import_parity", "tracking", "geometry", "contact", "vision", "differential", "reproducibility"):
            _mapping(document[name], f"receipt.{name}")
        signature = _mapping(document["reproducibility"], "receipt.reproducibility")
        _exact_keys(signature, {"result_signature_sha256", "repeat_index"}, "receipt.reproducibility")
        _digest(signature["result_signature_sha256"], "receipt.reproducibility.result_signature_sha256")
        _integer(signature["repeat_index"], "receipt.reproducibility.repeat_index")

    @property
    def receipt_sha256(self) -> str:
        return str(self._document["receipt_sha256"])

    def to_dict(self) -> dict[str, Any]:
        return json.loads(canonical_bytes(self._document).decode("ascii"))

