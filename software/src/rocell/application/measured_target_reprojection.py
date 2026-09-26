"""Reproject a model target through measured device placement without motion.

The model is allowed to name a device target and propose a point.  This module
keeps that point in device coordinates long enough to validate it against the
named key/region, then applies the commissioned ``B_T_device`` transform.  The
result is Cartesian planning input only: it performs no IK, route screening,
transport access, or controller encoding.
"""

from __future__ import annotations

import hashlib
import json
import math
import re
from typing import Any

from rocell.calibration import PlannerCalibrationSnapshot
from rocell.geometry import Point3Mm
from rocell.models import Interaction, ModelMotionProposal
from rocell.targets import NominalTargetCatalog


SCHEMA = "rocell.measured_target_reprojection.v1"
_SHA256 = re.compile(r"^[0-9a-f]{64}$")
_DEVICE_FRAMES = {
    "keyboard": ("keyboard_local", "keyboard"),
    "phone": ("phone_screen_local", "phone_screen"),
}


class MeasuredTargetReprojectionError(ValueError):
    """The proposal cannot be safely expressed through measured placement."""


def _canonical(value: object) -> bytes:
    return json.dumps(
        value, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")


def _point(point: Point3Mm) -> dict[str, float | str]:
    return {"frame": point.frame, "x": point.x, "y": point.y, "z": point.z}


def _finite_nonnegative(value: object, label: str) -> float:
    if isinstance(value, bool) or not isinstance(value, (int, float)):
        raise TypeError(f"{label} must be numeric")
    result = float(value)
    if not math.isfinite(result) or result < 0.0:
        raise ValueError(f"{label} must be finite and non-negative")
    return result


def _device_geometry(
    catalog: NominalTargetCatalog, device: str
) -> tuple[tuple[float, float], float, str, str]:
    local_frame, measured_frame = _DEVICE_FRAMES[device]
    if device == "keyboard":
        return (
            catalog.keyboard_origin_board_xy_mm,
            catalog.keyboard_target_plane_z_board_mm,
            local_frame,
            measured_frame,
        )
    return (
        catalog.phone_origin_board_xy_mm,
        catalog.phone_target_plane_z_board_mm,
        local_frame,
        measured_frame,
    )


def reproject_measured_target(
    proposal: ModelMotionProposal,
    catalog: NominalTargetCatalog,
    snapshot: PlannerCalibrationSnapshot,
    *,
    model_motion_candidate_sha256: str,
    plane_tolerance_mm: float = 1e-6,
) -> dict[str, Any]:
    """Produce measured board-frame waypoints with zero execution authority."""

    if not isinstance(proposal, ModelMotionProposal):
        raise TypeError("proposal must be a ModelMotionProposal")
    if not isinstance(catalog, NominalTargetCatalog):
        raise TypeError("catalog must be a NominalTargetCatalog")
    if not isinstance(snapshot, PlannerCalibrationSnapshot):
        raise TypeError("snapshot must be a PlannerCalibrationSnapshot")
    if (
        not isinstance(model_motion_candidate_sha256, str)
        or _SHA256.fullmatch(model_motion_candidate_sha256) is None
    ):
        raise MeasuredTargetReprojectionError(
            "model_motion_candidate_sha256 must be a lowercase SHA-256 digest"
        )
    tolerance = _finite_nonnegative(plane_tolerance_mm, "plane_tolerance_mm")
    device = proposal.device.value
    if snapshot.device != device:
        raise MeasuredTargetReprojectionError(
            "proposal and calibration snapshot devices differ"
        )
    if snapshot.target_map_sha256 != catalog.content_sha256:
        raise MeasuredTargetReprojectionError(
            "calibration snapshot target map does not match the loaded catalog"
        )

    origin, nominal_plane_z, proposal_local_frame, measured_frame = _device_geometry(
        catalog, device
    )
    board_T_device = snapshot.board_T_device
    if (
        board_T_device.parent_frame != "B"
        or board_T_device.child_frame != measured_frame
    ):
        raise MeasuredTargetReprojectionError(
            f"snapshot must provide B_T_{measured_frame}"
        )

    nominal = catalog.resolve(device, proposal.target_id)
    center_local_x = nominal.center.x - origin[0]
    center_local_y = nominal.center.y - origin[1]
    surface_local_z = nominal.center.z - nominal_plane_z

    if proposal.target.frame == proposal_local_frame:
        local = Point3Mm(
            measured_frame, proposal.target.x, proposal.target.y, proposal.target.z
        )
        input_binding = {
            "mode": "EXPLICIT_EQUIVALENT_DEVICE_FRAME_RELABEL",
            "source_frame": proposal_local_frame,
            "measured_transform_child_frame": measured_frame,
        }
    elif proposal.target.frame == "board":
        board_input = Point3Mm(
            "B", proposal.target.x, proposal.target.y, proposal.target.z
        )
        local = board_T_device.inverse().transform_point(board_input)
        input_binding = {
            "mode": "INVERSE_MEASURED_DEVICE_TRANSFORM",
            "source_frame": "board",
            "measured_transform_parent_frame": "B",
        }
    else:  # ModelMotionProposal already rejects this, retained as a fail-closed seam.
        raise MeasuredTargetReprojectionError(
            "proposal coordinate frame is unsupported"
        )

    left = center_local_x - nominal.half_extent_x_mm
    front = center_local_y - nominal.half_extent_y_mm
    right = center_local_x + nominal.half_extent_x_mm
    rear = center_local_y + nominal.half_extent_y_mm
    if not (left <= local.x <= right and front <= local.y <= rear):
        raise MeasuredTargetReprojectionError(
            "measured device-local coordinate is outside the named target safe rectangle"
        )
    if abs(local.z - surface_local_z) > tolerance:
        raise MeasuredTargetReprojectionError(
            "measured device-local coordinate is outside the named target surface plane"
        )

    surface_board = board_T_device.transform_point(local)
    hover_local = Point3Mm(
        measured_frame,
        local.x,
        local.y,
        local.z + proposal.approach_clearance_mm,
    )
    hover_board = board_T_device.transform_point(hover_local)
    if proposal.interaction is Interaction.HOVER:
        waypoints = [{"phase": "HOVER_DESTINATION", "point_mm": _point(hover_board)}]
    else:
        waypoints = [
            {"phase": "APPROACH", "point_mm": _point(hover_board)},
            {"phase": "CONTACT_CANDIDATE", "point_mm": _point(surface_board)},
            {"phase": "RETRACT", "point_mm": _point(hover_board)},
        ]

    corners_local = (
        Point3Mm(measured_frame, left, front, surface_local_z),
        Point3Mm(measured_frame, right, front, surface_local_z),
        Point3Mm(measured_frame, right, rear, surface_local_z),
        Point3Mm(measured_frame, left, rear, surface_local_z),
    )
    report: dict[str, Any] = {
        "schema": SCHEMA,
        "status": "READY_FOR_DETERMINISTIC_IK_AND_ROUTE_SCREENING",
        "proposal_id": proposal.proposal_id,
        "proposal_sha256": proposal.proposal_sha256,
        "model_motion_candidate_sha256": model_motion_candidate_sha256,
        "calibration_snapshot_sha256": snapshot.snapshot_sha256,
        "target_catalog_sha256": catalog.content_sha256,
        "source": proposal.source.to_dict(),
        "device": device,
        "target_id": proposal.target_id,
        "interaction": proposal.interaction.value,
        "speed_class": proposal.speed_class.value,
        "input_target_mm": _point(proposal.target),
        "input_frame_binding": input_binding,
        "named_target_safe_rectangle_device_mm": [left, front, right, rear],
        "surface_plane_z_device_mm": surface_local_z,
        "validated_target_device_mm": _point(local),
        "measured_surface_target_board_mm": _point(surface_board),
        "measured_safe_polygon_board_mm": [
            _point(board_T_device.transform_point(corner)) for corner in corners_local
        ],
        "requested_waypoints": waypoints,
        "clearance_definition": "MEASURED_DEVICE_LOCAL_POSITIVE_Z",
        "controller_commands": [],
        "hardware_commands_generated": 0,
        "hardware_access": False,
        "physical_authority": False,
        "limitations": [
            "No inverse kinematics or joint-limit screening performed",
            "No full-route collision, cable, timing, or smoothness screening performed",
            "No controller command encoding or transport access performed",
        ],
    }
    return {
        **report,
        "reprojection_sha256": hashlib.sha256(_canonical(report)).hexdigest(),
    }
