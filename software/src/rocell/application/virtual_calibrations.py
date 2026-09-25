"""Resolve explicit simulation surrogates for physical calibration dependencies.

The physical dependency graph remains authoritative and blocked until measured
artifacts exist.  A virtual session still needs deterministic substitutes in
order to exercise the software around that graph.  This module makes those
substitutions visible and hash-bound instead of silently treating nominal
geometry as calibration evidence.
"""

from __future__ import annotations

from dataclasses import dataclass
import hashlib
import json
from typing import Any, Mapping

from rocell.calibration import ordered_requirement_closure
from rocell.models.actions import ActionPlan

from .context import SimulationContext, revalidate_simulation_context
from .reach_optimizer import ReachStudyInput


class VirtualCalibrationError(ValueError):
    """A virtual calibration closure cannot be built unambiguously."""


def _stable_hash(value: object) -> str:
    return hashlib.sha256(
        json.dumps(
            value,
            sort_keys=True,
            separators=(",", ":"),
            ensure_ascii=True,
            allow_nan=False,
        ).encode("utf-8")
    ).hexdigest()


@dataclass(frozen=True, slots=True)
class VirtualCalibrationSurrogate:
    """One non-physical replacement used only by the virtual executor."""

    artifact_id: str
    model: str
    source_bindings: tuple[tuple[str, str], ...]
    limitations: tuple[str, ...]

    def __post_init__(self) -> None:
        if not self.artifact_id or not self.artifact_id.strip():
            raise VirtualCalibrationError("artifact_id must be non-empty")
        if not self.model or not self.model.strip():
            raise VirtualCalibrationError("surrogate model must be non-empty")
        bindings = tuple(sorted(self.source_bindings))
        if not bindings or len({key for key, _ in bindings}) != len(bindings):
            raise VirtualCalibrationError(
                f"{self.artifact_id} source bindings must be non-empty and unique"
            )
        if any(not key or not value for key, value in bindings):
            raise VirtualCalibrationError(
                f"{self.artifact_id} source bindings cannot be empty"
            )
        object.__setattr__(self, "source_bindings", bindings)
        limitations = tuple(self.limitations)
        if not limitations:
            raise VirtualCalibrationError(
                f"{self.artifact_id} must state its physical limitation"
            )
        object.__setattr__(self, "limitations", limitations)

    def to_dict(self) -> dict[str, Any]:
        return {
            "artifact_id": self.artifact_id,
            "resolution": "VIRTUAL_SURROGATE",
            "model": self.model,
            "source_bindings": dict(self.source_bindings),
            "limitations": list(self.limitations),
            "physical_artifact_valid": False,
            "physical_release_effect": "NONE",
        }

    @property
    def surrogate_hash(self) -> str:
        return _stable_hash(self.to_dict())


@dataclass(frozen=True, slots=True)
class VirtualCalibrationClosure:
    """Prerequisite-first virtual closure plus permanent physical holds."""

    requested: tuple[str, ...]
    ordered: tuple[str, ...]
    surrogates: tuple[VirtualCalibrationSurrogate, ...]

    def __post_init__(self) -> None:
        if tuple(row.artifact_id for row in self.surrogates) != self.ordered:
            raise VirtualCalibrationError(
                "virtual calibration rows must follow the dependency closure exactly"
            )

    def to_dict(self) -> dict[str, Any]:
        return {
            "schema": "rocell.virtual_calibration_closure.v1",
            "status": "VIRTUAL_SURROGATES_COMPLETE_PHYSICAL_ARTIFACTS_REQUIRED",
            "requested": list(self.requested),
            "ordered_requirement_closure": list(self.ordered),
            "surrogates": [
                {**row.to_dict(), "surrogate_hash": row.surrogate_hash}
                for row in self.surrogates
            ],
            "all_virtual_requirements_resolved": len(self.surrogates) == len(self.ordered),
            "physical_calibration_ready": False,
            "physical_blockers": list(self.ordered),
            "physical_release_effect": "NONE",
        }

    @property
    def closure_hash(self) -> str:
        return _stable_hash(self.to_dict())


def resolve_virtual_calibrations(
    context: SimulationContext,
    plan: ActionPlan,
    study_input: ReachStudyInput,
) -> VirtualCalibrationClosure:
    """Resolve every required artifact to an explicit idealized substitute.

    The function intentionally does not inspect, write, or promote the physical
    calibration registry.  The returned rows are useful for dependency and
    orchestration testing only.
    """

    if not isinstance(plan, ActionPlan):
        raise TypeError("plan must be an ActionPlan")
    if not isinstance(study_input, ReachStudyInput):
        raise TypeError("study_input must be a ReachStudyInput")
    revalidate_simulation_context(context)

    ordered = ordered_requirement_closure(plan.required_calibrations)
    scene_hashes: Mapping[str, str] = context.scene.source_hashes
    scene_binding = _stable_hash(dict(sorted(scene_hashes.items())))
    common = {
        "simulation_bundle": context.bundle_lock.source_lock_sha256,
        "snapshot": context.snapshot.snapshot_hash,
    }
    model_by_id: dict[str, tuple[str, dict[str, str]]] = {
        "camera_intrinsics": (
            "PINNED_SYNTHETIC_OVERVIEW_PINHOLE_MODEL",
            {
                "scenario": context.scenario.overview.scenario_id,
                "simulation_profile": context.scenario.source_profile_sha256,
            },
        ),
        "measured_tag_map": (
            "NOMINAL_RC03_TAG_MAP_TRUTH_ORACLE",
            {"scene_sources": scene_binding},
        ),
        "robot_reference": (
            "PINNED_URDF_JOINT_STATE_TRUTH",
            {"kinematic_model": context.scenario.model_sha256},
        ),
        "eye_on_arm_extrinsic": (
            "IDEALIZED_FRAME_TRUTH_WITHOUT_PHYSICAL_CAMERA_MOUNT",
            {
                "simulation_profile": context.scenario.source_profile_sha256,
                "kinematic_model": context.scenario.model_sha256,
            },
        ),
        "arm_board": (
            "UNMEASURED_SENSITIVITY_OVERLAY_TRANSFORM",
            {"study_input": study_input.study_input_id},
        ),
        "controller_correlation": (
            "DIRECT_VIRTUAL_JOINT_PLANT_BYPASS",
            {
                "kinematic_model": context.scenario.model_sha256,
                "simulation_profile": context.scenario.source_profile_sha256,
            },
        ),
        "keyboard_pose": (
            "NOMINAL_TARGET_CATALOG_GEOMETRY",
            {"target_catalog": context.targets.content_sha256},
        ),
        "keyboard_tcp": (
            "VIRTUAL_TOOL_LENGTH",
            {
                "study_input": study_input.study_input_id,
                "tool_length_mm": f"{study_input.keyboard_tool_length_mm:.17g}",
            },
        ),
        "keyboard_outcome_observer": (
            "DETERMINISTIC_VIRTUAL_KEYBOARD_STATE",
            {"semantic_profile": plan.profile_id},
        ),
        "phone_screen": (
            "NOMINAL_TARGET_CATALOG_AND_UI_STATE",
            {"target_catalog": context.targets.content_sha256},
        ),
        "phone_tcp": (
            "VIRTUAL_TOOL_LENGTH",
            {
                "study_input": study_input.study_input_id,
                "tool_length_mm": f"{study_input.phone_tool_length_mm:.17g}",
            },
        ),
        "phone_ui_observer": (
            "DETERMINISTIC_VIRTUAL_ANDROID_STATE",
            {"semantic_profile": plan.profile_id},
        ),
    }

    rows: list[VirtualCalibrationSurrogate] = []
    for artifact_id in ordered:
        try:
            model, specific = model_by_id[artifact_id]
        except KeyError as exc:
            raise VirtualCalibrationError(
                f"No virtual surrogate is defined for {artifact_id!r}"
            ) from exc
        rows.append(
            VirtualCalibrationSurrogate(
                artifact_id=artifact_id,
                model=model,
                source_bindings=tuple({**common, **specific}.items()),
                limitations=(
                    "Idealized deterministic software surrogate; it is not measured calibration evidence.",
                    "It cannot satisfy or modify a physical capability gate.",
                ),
            )
        )

    return VirtualCalibrationClosure(
        requested=tuple(plan.required_calibrations),
        ordered=ordered,
        surrogates=tuple(rows),
    )


__all__ = [
    "VirtualCalibrationClosure",
    "VirtualCalibrationError",
    "VirtualCalibrationSurrogate",
    "resolve_virtual_calibrations",
]
