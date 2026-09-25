"""Ordered calibration/qualification dependency graph for contact missions."""

from __future__ import annotations

from dataclasses import dataclass
from types import MappingProxyType
from typing import Mapping


@dataclass(frozen=True, slots=True)
class CalibrationRequirement:
    artifact_id: str
    prerequisites: tuple[str, ...]
    purpose: str
    acceptance_evidence: str


REQUIREMENTS: Mapping[str, CalibrationRequirement] = MappingProxyType(
    {
        item.artifact_id: item
        for item in (
            CalibrationRequirement(
                "camera_intrinsics",
                (),
                "Calibrate the locked IMX335-B resolution/lens model.",
                "ChArUco dataset, train/held-out residuals, image size, and camera identity hash.",
            ),
            CalibrationRequirement(
                "measured_tag_map",
                (),
                "Replace nominal tag centres/Z with measured board-frame geometry.",
                "Measured tag corners/plane, method/tool IDs, residuals, and RC03 layout hash.",
            ),
            CalibrationRequirement(
                "robot_reference",
                (),
                "Bind installed joint signs, zeros, ranges, and reference procedure.",
                "Arm/controller/firmware identity, repeated reference trials, joint error bounds.",
            ),
            CalibrationRequirement(
                "eye_on_arm_extrinsic",
                ("camera_intrinsics", "measured_tag_map", "robot_reference"),
                "Solve link2/E/holder to C_arm at the locked rail position.",
                "Diverse-pose hand-eye dataset, transform, condition metrics, held-out residuals.",
            ),
            CalibrationRequirement(
                "arm_board",
                ("eye_on_arm_extrinsic", "measured_tag_map", "robot_reference"),
                "Solve and validate B_T_Wv for the installed clamp/board state.",
                "Transform, observability/rank report, held-out translational/angular residuals.",
            ),
            CalibrationRequirement(
                "controller_correlation",
                ("arm_board", "robot_reference"),
                "Correlate separate firmware R_ctrl with the vendor kinematic model.",
                "Configuration-dependent residual model and bounded T=104/T=1051 validation.",
            ),
            CalibrationRequirement(
                "keyboard_pose",
                ("measured_tag_map",),
                "Measure keyboard pose, key polygons, Z, normals, and press travel.",
                "Exact keyboard identity/layout plus per-key safe regions and held-out targeting error.",
            ),
            CalibrationRequirement(
                "keyboard_tcp",
                ("arm_board", "controller_correlation", "keyboard_pose"),
                "Calibrate keyboard tool TCP, compliance, travel, and free/contact states.",
                "Route/tool identity, TCP trials, force/travel limits, and recovery behavior.",
            ),
            CalibrationRequirement(
                "keyboard_outcome_observer",
                ("keyboard_pose",),
                "Verify that each physical press produced the expected host key outcome.",
                "Qualified acceptance app/OS layout and observed-vs-expected text test set.",
            ),
            CalibrationRequirement(
                "phone_screen",
                ("camera_intrinsics", "measured_tag_map"),
                "Measure phone pose, active-screen homography, insets, and UI target polygons.",
                "Phone/Gboard/version/orientation identity, screenshots, safe polygons, residuals.",
            ),
            CalibrationRequirement(
                "phone_tcp",
                ("arm_board", "controller_correlation", "phone_screen"),
                "Calibrate stylus TCP, compliance, travel, and touchscreen activation.",
                "Route/tool identity, TCP trials, safe travel/force proxy, and repeatability evidence.",
            ),
            CalibrationRequirement(
                "phone_ui_observer",
                ("phone_screen",),
                "Verify Android keyboard state and tap outcome before/after actions.",
                "Qualified Gboard state classifier, dialog/rotation detection, held-out screenshots.",
            ),
        )
    }
)


def ordered_requirement_closure(artifact_ids: tuple[str, ...]) -> tuple[str, ...]:
    """Return deterministic prerequisite-first closure, rejecting unknown/cycles."""

    ordered: list[str] = []
    complete: set[str] = set()
    active: set[str] = set()

    def visit(artifact_id: str) -> None:
        if artifact_id in complete:
            return
        if artifact_id in active:
            raise ValueError(f"Calibration dependency cycle at {artifact_id}")
        try:
            requirement = REQUIREMENTS[artifact_id]
        except KeyError as exc:
            raise ValueError(f"Unknown calibration requirement {artifact_id!r}") from exc
        active.add(artifact_id)
        for prerequisite in requirement.prerequisites:
            visit(prerequisite)
        active.remove(artifact_id)
        complete.add(artifact_id)
        ordered.append(artifact_id)

    for requested in artifact_ids:
        visit(requested)
    return tuple(ordered)

