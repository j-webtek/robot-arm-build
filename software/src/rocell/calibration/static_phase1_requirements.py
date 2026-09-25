"""Versioned calibration requirements for the static-overhead Phase-1 cell.

This module is intentionally additive.  The original ``REQUIREMENTS`` map in
``requirements.py`` describes the historical eye-on-arm architecture retained
by Freeze 009.  Reinterpreting those artifact IDs would make old evidence
ambiguous, so the selected B0477/static-overhead architecture uses a new,
namespaced graph instead.

The graph specifies *what physical artifacts will eventually be required* and
which artifact/source hashes each one must bind.  It grants no power, motion,
or contact authority.  Pre-hardware code may use nominal artifacts to rehearse
the graph, but those artifacts must remain ``NOMINAL_ONLY``.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
import re
from types import MappingProxyType
from typing import Any, Mapping


STATIC_OVERHEAD_PHASE1_GRAPH_SCHEMA = (
    "rocell.static_overhead_phase1_calibration_graph.v1"
)
STATIC_OVERHEAD_PHASE1_GRAPH_ID = "static-overhead-b0477-phase1.v1"
STATIC_OVERHEAD_PHASE1_AUTHORITY = "SIMULATION_ONLY_ZERO_PHYSICAL_AUTHORITY"

_IDENTIFIER = re.compile(r"^[A-Za-z0-9_.-]+$")
_SUPPORTED_DEVICES = ("keyboard", "phone")


class StaticPhase1RequirementError(ValueError):
    """The static Phase-1 requirement graph is malformed or incomplete."""


def _identifier(value: object, name: str) -> str:
    if not isinstance(value, str) or _IDENTIFIER.fullmatch(value) is None:
        raise StaticPhase1RequirementError(
            f"{name} must match {_IDENTIFIER.pattern}"
        )
    return value


def _text(value: object, name: str) -> str:
    if not isinstance(value, str) or not value.strip():
        raise StaticPhase1RequirementError(f"{name} must be non-empty")
    return value.strip()


@dataclass(frozen=True, slots=True)
class StaticPhase1CalibrationRequirement:
    """One versioned, physical calibration requirement.

    ``context_dependencies`` names immutable non-calibration sources (for
    example the purchased-camera profile or workcell layout).  ``prerequisites``
    names calibration artifacts and becomes the required parent-hash set.
    Keeping those two edge types explicit lets the rehearsal prove staleness at
    every edge instead of relying on an undocumented transitive assumption.
    """

    artifact_id: str
    artifact_schema: str
    prerequisites: tuple[str, ...]
    context_dependencies: tuple[str, ...]
    purpose: str
    acceptance_evidence: str

    def __post_init__(self) -> None:
        object.__setattr__(
            self, "artifact_id", _identifier(self.artifact_id, "artifact_id")
        )
        object.__setattr__(
            self,
            "artifact_schema",
            _identifier(self.artifact_schema, "artifact_schema"),
        )
        prerequisites = tuple(
            _identifier(item, "prerequisite") for item in self.prerequisites
        )
        if len(prerequisites) != len(set(prerequisites)):
            raise StaticPhase1RequirementError(
                f"{self.artifact_id} contains duplicate prerequisites"
            )
        if self.artifact_id in prerequisites:
            raise StaticPhase1RequirementError(
                f"{self.artifact_id} cannot depend on itself"
            )
        object.__setattr__(self, "prerequisites", prerequisites)

        context_dependencies = tuple(
            _identifier(item, "context dependency")
            for item in self.context_dependencies
        )
        if len(context_dependencies) != len(set(context_dependencies)):
            raise StaticPhase1RequirementError(
                f"{self.artifact_id} contains duplicate context dependencies"
            )
        object.__setattr__(self, "context_dependencies", context_dependencies)
        object.__setattr__(self, "purpose", _text(self.purpose, "purpose"))
        object.__setattr__(
            self,
            "acceptance_evidence",
            _text(self.acceptance_evidence, "acceptance_evidence"),
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "artifact_schema": self.artifact_schema,
            "prerequisites": list(self.prerequisites),
            "context_dependencies": list(self.context_dependencies),
            "purpose": self.purpose,
            "acceptance_evidence": self.acceptance_evidence,
        }


@dataclass(frozen=True, slots=True)
class StaticPhase1CalibrationGraph:
    """Immutable graph and device terminal definitions."""

    requirements: Mapping[str, StaticPhase1CalibrationRequirement]
    device_terminals: Mapping[str, tuple[str, ...]]
    graph_id: str = STATIC_OVERHEAD_PHASE1_GRAPH_ID
    schema: str = STATIC_OVERHEAD_PHASE1_GRAPH_SCHEMA

    def __post_init__(self) -> None:
        if self.schema != STATIC_OVERHEAD_PHASE1_GRAPH_SCHEMA:
            raise StaticPhase1RequirementError("Unsupported static Phase-1 graph schema")
        object.__setattr__(self, "graph_id", _identifier(self.graph_id, "graph_id"))

        requirements = dict(self.requirements)
        if not requirements:
            raise StaticPhase1RequirementError("requirements cannot be empty")
        for key, requirement in requirements.items():
            if not isinstance(requirement, StaticPhase1CalibrationRequirement):
                raise TypeError(
                    "requirements must contain StaticPhase1CalibrationRequirement values"
                )
            if key != requirement.artifact_id:
                raise StaticPhase1RequirementError(
                    f"Requirement key {key!r} differs from its artifact_id"
                )
            for prerequisite in requirement.prerequisites:
                if prerequisite not in requirements:
                    raise StaticPhase1RequirementError(
                        f"{key} has unknown prerequisite {prerequisite}"
                    )

        terminals: dict[str, tuple[str, ...]] = {}
        if set(self.device_terminals) != set(_SUPPORTED_DEVICES):
            raise StaticPhase1RequirementError(
                "device_terminals must define exactly keyboard and phone"
            )
        for device in _SUPPORTED_DEVICES:
            requested = tuple(
                _identifier(item, f"{device} terminal")
                for item in self.device_terminals[device]
            )
            if not requested or len(requested) != len(set(requested)):
                raise StaticPhase1RequirementError(
                    f"{device} terminals must be non-empty and unique"
                )
            unknown = tuple(item for item in requested if item not in requirements)
            if unknown:
                raise StaticPhase1RequirementError(
                    f"{device} has unknown terminal requirements {unknown}"
                )
            terminals[device] = requested

        object.__setattr__(
            self, "requirements", MappingProxyType(requirements)
        )
        object.__setattr__(
            self, "device_terminals", MappingProxyType(terminals)
        )

        # Traversing every node catches cycles, including nodes that are not a
        # terminal due to a future graph-editing mistake.
        self.ordered_closure(tuple(requirements))

    def ordered_closure(self, artifact_ids: tuple[str, ...]) -> tuple[str, ...]:
        """Return a deterministic prerequisite-first closure."""

        ordered: list[str] = []
        complete: set[str] = set()
        active: set[str] = set()

        def visit(artifact_id: str) -> None:
            if artifact_id in complete:
                return
            if artifact_id in active:
                raise StaticPhase1RequirementError(
                    f"Static Phase-1 dependency cycle at {artifact_id}"
                )
            try:
                requirement = self.requirements[artifact_id]
            except KeyError as exc:
                raise StaticPhase1RequirementError(
                    f"Unknown static Phase-1 requirement {artifact_id!r}"
                ) from exc
            active.add(artifact_id)
            for prerequisite in requirement.prerequisites:
                visit(prerequisite)
            active.remove(artifact_id)
            complete.add(artifact_id)
            ordered.append(artifact_id)

        for artifact_id in artifact_ids:
            visit(_identifier(artifact_id, "requested artifact_id"))
        return tuple(ordered)

    def device_closure(self, device: str) -> tuple[str, ...]:
        """Return the complete closure for one Phase-1 typing surface."""

        try:
            terminals = self.device_terminals[device]
        except KeyError as exc:
            raise StaticPhase1RequirementError(
                f"Unsupported static Phase-1 device {device!r}"
            ) from exc
        return self.ordered_closure(terminals)

    @property
    def ordered_requirements(self) -> tuple[str, ...]:
        return self.ordered_closure(tuple(self.requirements))

    @property
    def parent_edges(self) -> tuple[tuple[str, str], ...]:
        """Return ``(parent, child)`` edges in stable child/parent order."""

        return tuple(
            (parent, child)
            for child in self.ordered_requirements
            for parent in self.requirements[child].prerequisites
        )

    @property
    def required_context_hash_ids(self) -> tuple[str, ...]:
        return tuple(
            sorted(
                {
                    dependency
                    for requirement in self.requirements.values()
                    for dependency in requirement.context_dependencies
                }
            )
        )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": self.schema,
            "graph_id": self.graph_id,
            "architecture": "RIGID_STATIC_OVERHEAD_EYE_TO_HAND",
            "camera_catalog_configuration": "ARDUCAM_B0477_IMX283_16MM",
            "phase": 1,
            "authority": STATIC_OVERHEAD_PHASE1_AUTHORITY,
            "historical_eye_on_arm_graph_reinterpreted": False,
            "device_terminals": {
                device: list(self.device_terminals[device])
                for device in _SUPPORTED_DEVICES
            },
            "requirements": [
                self.requirements[artifact_id].to_dict()
                for artifact_id in self.ordered_requirements
            ],
        }

    @property
    def graph_hash(self) -> str:
        payload = json.dumps(
            self.to_dict(),
            sort_keys=True,
            separators=(",", ":"),
            allow_nan=False,
        ).encode("utf-8")
        return hashlib.sha256(payload).hexdigest()


def _requirement(
    artifact_id: str,
    prerequisites: tuple[str, ...],
    context_dependencies: tuple[str, ...],
    purpose: str,
    acceptance_evidence: str,
) -> StaticPhase1CalibrationRequirement:
    return StaticPhase1CalibrationRequirement(
        artifact_id=artifact_id,
        artifact_schema=f"rocell.{artifact_id}.v1",
        prerequisites=prerequisites,
        context_dependencies=context_dependencies,
        purpose=purpose,
        acceptance_evidence=acceptance_evidence,
    )


_REQUIREMENT_ROWS = (
    _requirement(
        "phase1_b0477_identity",
        (),
        ("camera_architecture_plan", "b0477_catalog_profile"),
        "Bind the received camera, IMX283 sensor, included 16 mm lens, enclosure, cable, and stable USB identity.",
        "Receipt photographs, label/serial records, measured mechanical identity, VID/PID, serial descriptor, persistent OS path, and reconnect/reboot identity trials.",
    ),
    _requirement(
        "phase1_b0477_mode",
        ("phase1_b0477_identity",),
        ("b0477_catalog_profile",),
        "Bind the exact UVC bus, width, height, frame rate, and pixel format used by calibration and runtime.",
        "Enumerated mode inventory plus close/reopen, reconnect, and reboot trials proving the selected native mode without camera-index assumptions.",
    ),
    _requirement(
        "phase1_b0477_settings",
        ("phase1_b0477_mode",),
        (
            "b0477_catalog_profile",
            "camera_architecture_plan",
            "static_camera_support",
        ),
        "Bind the retained installed optical stack and lock focus, aperture, exposure, gain, white balance, and every available automatic/manual control.",
        "Installed camera, mount, lighting, cable/strain-relief, and support identities; control snapshots before and after reopen/reboot; one-metre focus evidence; physical lock witness marks; and disturbance/drift/illumination checks.",
    ),
    _requirement(
        "phase1_static_intrinsics",
        (
            "phase1_b0477_identity",
            "phase1_b0477_mode",
            "phase1_b0477_settings",
        ),
        (
            "b0477_catalog_profile",
            "camera_architecture_plan",
            "static_camera_support",
        ),
        "Calibrate the received B0477/lens in the retained installed optical stack at the exact locked mode and settings, including distortion and undistortion geometry.",
        "Scale-verified ChArUco images captured after retained camera/mount/light/cable installation, immutable source hashes, precommitted fit/held-out split, selected distortion model, residuals by image region, ROI/crop, and undistortion-map hash.",
    ),
    _requirement(
        "phase1_measured_tag_map",
        (),
        ("workcell_layout", "apriltag_map"),
        "Replace nominal RC03 tag centers and plane assumptions with surveyed board-frame tag geometry.",
        "Measured corners, optical-plane Z, yaw, uncertainty, method/tool identities, installation photographs, layout hash, and held-out survey residuals.",
    ),
    _requirement(
        "phase1_static_extrinsic",
        (
            "phase1_static_intrinsics",
            "phase1_measured_tag_map",
            "phase1_b0477_settings",
        ),
        ("camera_architecture_plan", "static_camera_support"),
        "Solve the rigid camera-to-board transform and qualify reseating, warm-up, cable-load, and time drift.",
        "Static eye-to-hand transform, inlier/residual/covariance evidence, frame witness references, independent held-out station tags, and repeated-installation drift trials.",
    ),
    _requirement(
        "phase1_robot_reference",
        (),
        ("system_manifest", "kinematic_model"),
        "Bind the installed RoArm-M3 Pro, controller/firmware identity, joint order/sign/zero/range, and repeatable reference procedure.",
        "Received arm/servo/controller identities, firmware readback, bounded T=1051 records, repeated references, and joint/reference uncertainty bounds.",
    ),
    _requirement(
        "phase1_controller_correlation",
        ("phase1_robot_reference",),
        ("kinematic_model",),
        "Correlate controller feedback and T=104 command behavior with the pinned vendor kinematic model and host timestamps.",
        "Configuration-diverse feedback/command trials, frame and unit correlation, settling/overshoot/latency bounds, residual model, and reset/reconnect behavior.",
    ),
    _requirement(
        "phase1_arm_board",
        (
            "phase1_static_extrinsic",
            "phase1_measured_tag_map",
            "phase1_robot_reference",
            "phase1_controller_correlation",
        ),
        ("workcell_layout", "static_camera_support"),
        "Solve the installed robot-base-to-board transform independently of the static camera-to-board transform.",
        "Installed clamp/base identity, diverse robot-to-board correspondences, rank/observability evidence, held-out position/orientation residuals, and reseat checks.",
    ),
    _requirement(
        "phase1_keyboard_target_map",
        (
            "phase1_static_intrinsics",
            "phase1_measured_tag_map",
            "phase1_static_extrinsic",
        ),
        ("target_catalog", "keyboard_semantic_profile"),
        "Measure the exact keyboard installation, all supported key polygons/safe insets, surface Z/normals, and press travel.",
        "Keyboard identity/layout, 46-key coverage, board transform, per-key polygons and safe regions, tool-footprint uncertainty budget, measurements/images, and held-out targeting residuals.",
    ),
    _requirement(
        "phase1_keyboard_tcp",
        (
            "phase1_arm_board",
            "phase1_controller_correlation",
            "phase1_keyboard_target_map",
        ),
        ("kinematic_model",),
        "Calibrate the selected keyboard tool TCP, compliance, hover/contact/retract travel, and free/contact telemetry.",
        "Tool/route identity, TCP pivot and contact trials, travel/load limits, repeatability, recovery behavior, and collision-cleared route evidence.",
    ),
    _requirement(
        "phase1_keyboard_outcome_observer",
        ("phase1_keyboard_target_map",),
        ("keyboard_semantic_profile",),
        "Independently verify each expected host-key effect without treating commanded contact as success.",
        "Qualified acceptance application, host OS/layout identity, baseline/expected/observed transitions, repeated-key tests, negative controls, and held-out text trials.",
    ),
    _requirement(
        "phase1_phone_target_map",
        (
            "phase1_static_intrinsics",
            "phase1_measured_tag_map",
            "phase1_static_extrinsic",
        ),
        ("target_catalog", "phone_semantic_profile"),
        "Measure the exact phone installation, screen homography/insets, Android/IME state, and conservative tap regions.",
        "Phone/display/OS/Gboard identities, orientation/density, 29-target coverage, screenshots, screen/board transforms, safe polygons, uncertainty budget, and held-out residuals.",
    ),
    _requirement(
        "phase1_phone_tcp",
        (
            "phase1_arm_board",
            "phase1_controller_correlation",
            "phase1_phone_target_map",
        ),
        ("kinematic_model",),
        "Calibrate the selected touchscreen stylus TCP, compliance, hover/contact/retract travel, and activation behavior.",
        "Tool/route identity, TCP and activation trials, safe travel/load proxy, repeatability, recovery behavior, and collision-cleared route evidence.",
    ),
    _requirement(
        "phase1_phone_outcome_observer",
        ("phase1_phone_target_map",),
        ("phone_semantic_profile",),
        "Independently verify Android keyboard state and each expected tap effect after retraction.",
        "Qualified app/field/Gboard state observer, lock/dialog/rotation detection, baseline/expected/observed transitions, negative controls, and held-out screenshot trials.",
    ),
)


STATIC_OVERHEAD_PHASE1_REQUIREMENTS: Mapping[
    str, StaticPhase1CalibrationRequirement
] = MappingProxyType({row.artifact_id: row for row in _REQUIREMENT_ROWS})

STATIC_OVERHEAD_PHASE1_DEVICE_TERMINALS: Mapping[str, tuple[str, ...]] = (
    MappingProxyType(
        {
            "keyboard": (
                "phase1_keyboard_tcp",
                "phase1_keyboard_outcome_observer",
            ),
            "phone": (
                "phase1_phone_tcp",
                "phase1_phone_outcome_observer",
            ),
        }
    )
)

STATIC_OVERHEAD_PHASE1_GRAPH = StaticPhase1CalibrationGraph(
    requirements=STATIC_OVERHEAD_PHASE1_REQUIREMENTS,
    device_terminals=STATIC_OVERHEAD_PHASE1_DEVICE_TERMINALS,
)


def ordered_static_phase1_requirement_closure(
    artifact_ids: tuple[str, ...],
) -> tuple[str, ...]:
    """Convenience integration point for the selected static graph."""

    return STATIC_OVERHEAD_PHASE1_GRAPH.ordered_closure(artifact_ids)


__all__ = [
    "STATIC_OVERHEAD_PHASE1_AUTHORITY",
    "STATIC_OVERHEAD_PHASE1_DEVICE_TERMINALS",
    "STATIC_OVERHEAD_PHASE1_GRAPH",
    "STATIC_OVERHEAD_PHASE1_GRAPH_ID",
    "STATIC_OVERHEAD_PHASE1_GRAPH_SCHEMA",
    "STATIC_OVERHEAD_PHASE1_REQUIREMENTS",
    "StaticPhase1CalibrationGraph",
    "StaticPhase1CalibrationRequirement",
    "StaticPhase1RequirementError",
    "ordered_static_phase1_requirement_closure",
]
