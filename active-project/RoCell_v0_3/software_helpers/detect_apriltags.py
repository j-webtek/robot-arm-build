#!/usr/bin/env python3
"""Detect RC03 AprilTags and, when measured map data exists, solve board pose.

Independent per-tag camera poses are always reported. A board-coordinate pose
is reported only when the map was generated from a PASS
``tag_plane_placement_measured`` record and enough world tags are visible.
T0-T3 define the board transform; K0/P0 are held out as station-area residual
checks so they cannot silently bias the primary world solution.
"""
from __future__ import annotations

import argparse
import contextlib
import hashlib
import io
import json
import math
from pathlib import Path
from typing import Any


EXPECTED_FAMILY = "tag36h11"
WORLD_NAMES = {"T0", "T1", "T2", "T3"}
EXPECTED_TAG_IDS = {"T0": 0, "T1": 1, "T2": 2, "T3": 3, "K0": 4, "P0": 5}
EXPECTED_TAG_ROLES = {
    "T0": "world", "T1": "world", "T2": "world", "T3": "world",
    "K0": "station_check", "P0": "station_check",
}
cv2: Any = None
np: Any = None


def load_vision_dependencies() -> None:
    """Load the optional native vision stack after CLI arguments are parsed."""
    global cv2, np
    errors = io.StringIO()
    try:
        with contextlib.redirect_stderr(errors):
            import cv2 as cv2_module
            import numpy as numpy_module
    except Exception as exc:
        raise SystemExit(
            "OpenCV is unavailable or binary-incompatible with NumPy. Install a "
            "matching opencv-contrib-python build (the aruco module is required) "
            f"before detection. Original error: {exc}"
        ) from None
    if not hasattr(cv2_module, "aruco"):
        raise SystemExit(
            "The installed OpenCV build has no aruco module; install "
            "opencv-contrib-python rather than the base opencv-python package."
        )
    cv2, np = cv2_module, numpy_module


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def load_frame(image_path: Path | None, camera_index: int | None) -> np.ndarray:
    if image_path is not None:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise SystemExit(f"Could not read {image_path}")
        return image
    capture = cv2.VideoCapture(int(camera_index))
    ok, frame = capture.read()
    capture.release()
    if not ok or frame is None:
        raise SystemExit(f"Could not capture camera {camera_index}")
    return frame


def local_tag_corners(edge_m: float) -> np.ndarray:
    half = edge_m / 2.0
    # OpenCV detector order is TL, TR, BR, BL. With the printed top edge at
    # board +Y, those corners have the following tag-local coordinates.
    return np.array([
        [-half, +half, 0.0],
        [+half, +half, 0.0],
        [+half, -half, 0.0],
        [-half, -half, 0.0],
    ], dtype=np.float64)


def _finite_xyz(value: Any) -> tuple[float, float, float] | None:
    if not isinstance(value, (list, tuple)) or len(value) != 3:
        return None
    if any(item is None for item in value):
        return None
    xyz = tuple(float(item) for item in value)
    return xyz if all(math.isfinite(item) for item in xyz) else None


def validate_tag_map(tag_map: dict[str, Any]) -> None:
    if tag_map.get("schema") != "rocell.apriltag_map.v2":
        raise SystemExit("Use the RC03 rocell.apriltag_map.v2 map")
    if tag_map.get("design_revision") != "RC03-INT-R1":
        raise SystemExit(f"Tag map revision is {tag_map.get('design_revision')!r}, not RC03-INT-R1")
    if tag_map.get("family") != EXPECTED_FAMILY:
        raise SystemExit(f"Unsupported tag family {tag_map.get('family')!r}; expected {EXPECTED_FAMILY}")
    if not math.isclose(float(tag_map.get("detection_edge_mm", 0)), 40.0, abs_tol=1e-9):
        raise SystemExit("RC03 detection edge must be 40.0 mm")
    if not math.isclose(float(tag_map.get("tile_size_mm", 0)), 55.0, abs_tol=1e-9):
        raise SystemExit("RC03 paper tile must be 55.0 mm")
    if tag_map.get("mounting") != "direct_adhesive":
        raise SystemExit("RC03 tag map must use direct_adhesive mounting")
    if tag_map.get("ids") != EXPECTED_TAG_IDS:
        raise SystemExit("RC03 tag names and printed IDs must remain T0-T3=0-3, K0=4, P0=5")
    tags = tag_map.get("tags")
    if not isinstance(tags, dict) or set(tags) != set(EXPECTED_TAG_IDS):
        raise SystemExit("RC03 tag map must contain exactly T0, T1, T2, T3, K0 and P0")
    coordinate_source = tag_map.get("coordinate_source")
    measurement = tag_map.get("measurement") or {}
    if coordinate_source not in {"nominal_layout", "measured_installation"}:
        raise SystemExit(f"Unsupported tag coordinate source {coordinate_source!r}")
    if coordinate_source == "measured_installation" and measurement.get("status") != "PASS":
        raise SystemExit("Measured installation coordinates require a PASS placement gate")
    if coordinate_source == "nominal_layout" and measurement.get("status") == "PASS":
        raise SystemExit("A PASS placement gate requires a regenerated measured-installation map")
    for name, expected_id in EXPECTED_TAG_IDS.items():
        tag = tags[name]
        if not isinstance(tag, dict):
            raise SystemExit(f"Tag {name} map entry must be an object")
        if tag.get("id") != expected_id or tag.get("role") != EXPECTED_TAG_ROLES[name]:
            raise SystemExit(f"Tag {name} ID/role does not match the RC03 contract")
        if tag.get("mounting") != "direct_adhesive" or tag.get("coordinate_source") != coordinate_source:
            raise SystemExit(f"Tag {name} mounting/source does not match the map")
        tile_origin = tag.get("tile_origin_xy_mm")
        if not isinstance(tile_origin, list) or len(tile_origin) != 2 or not all(
            math.isfinite(float(value)) for value in tile_origin
        ):
            raise SystemExit(f"Tag {name} has an invalid tile origin")
        xyz = tag.get("detection_center_xyz_mm")
        if not isinstance(xyz, list) or len(xyz) != 3 or any(
            value is not None and not math.isfinite(float(value)) for value in xyz
        ):
            raise SystemExit(f"Tag {name} has an invalid detection center")
        if any(value is None for value in xyz[:2]):
            raise SystemExit(f"Tag {name} requires finite detection-center X and Y")
        try:
            yaw = float(tag["expected_yaw_deg_in_board_frame"])
        except (KeyError, TypeError, ValueError):
            raise SystemExit(f"Tag {name} has an invalid expected yaw") from None
        if not math.isfinite(yaw):
            raise SystemExit(f"Tag {name} has an invalid expected yaw")
        if coordinate_source == "measured_installation" and _finite_xyz(xyz) is None:
            raise SystemExit(f"Measured tag {name} requires finite X, Y and optical-plane Z")


def board_tag_corners(tag: dict[str, Any], edge_mm: float) -> np.ndarray | None:
    center = _finite_xyz(tag.get("detection_center_xyz_mm"))
    if center is None:
        return None
    yaw_deg = float(tag.get("expected_yaw_deg_in_board_frame", 0.0))
    if not math.isfinite(yaw_deg):
        return None
    local_mm = local_tag_corners(edge_mm / 1000.0) * 1000.0
    yaw = math.radians(yaw_deg)
    rotation = np.array([
        [math.cos(yaw), -math.sin(yaw)],
        [math.sin(yaw), math.cos(yaw)],
    ], dtype=np.float64)
    xy = local_mm[:, :2] @ rotation.T
    points_mm = np.column_stack((
        xy[:, 0] + center[0],
        xy[:, 1] + center[1],
        np.full(4, center[2], dtype=np.float64),
    ))
    return points_mm / 1000.0


def homogeneous_transform(rvec: np.ndarray, tvec: np.ndarray) -> tuple[list[list[float]], list[list[float]]]:
    rotation, _ = cv2.Rodrigues(rvec)
    translation = tvec.reshape(3, 1)
    board_to_camera = np.eye(4, dtype=np.float64)
    board_to_camera[:3, :3] = rotation
    board_to_camera[:3, 3:4] = translation
    camera_to_board = np.eye(4, dtype=np.float64)
    camera_to_board[:3, :3] = rotation.T
    camera_to_board[:3, 3:4] = -rotation.T @ translation
    return board_to_camera.tolist(), camera_to_board.tolist()


def solve_board_pose(
    detections_by_name: dict[str, dict[str, Any]],
    tag_map: dict[str, Any],
    camera_matrix: np.ndarray,
    distortion: np.ndarray,
    min_world_tags: int,
) -> tuple[dict[str, Any], dict[str, Any]]:
    coordinate_source = str(tag_map.get("coordinate_source", "nominal_layout"))
    measurement = tag_map.get("measurement") or {}
    if coordinate_source != "measured_installation" or measurement.get("status") != "PASS":
        return ({
            "status": "BLOCKED_MAP_UNMEASURED",
            "reason": "Run and PASS tag_plane_placement_measured, then regenerate apriltag_map.json.",
            "world_tags_visible": sorted(WORLD_NAMES & set(detections_by_name)),
        }, {})

    edge_mm = float(tag_map["detection_edge_mm"])
    tags = tag_map.get("tags") or {}
    object_groups: list[np.ndarray] = []
    image_groups: list[np.ndarray] = []
    used_names: list[str] = []
    for name in sorted(WORLD_NAMES):
        detection = detections_by_name.get(name)
        tag = tags.get(name)
        if detection is None or not isinstance(tag, dict):
            continue
        corners_3d = board_tag_corners(tag, edge_mm)
        if corners_3d is None:
            continue
        object_groups.append(corners_3d)
        image_groups.append(np.asarray(detection["image_corners_px"], dtype=np.float64))
        used_names.append(name)
    if len(used_names) < min_world_tags:
        return ({
            "status": "INSUFFICIENT_WORLD_TAGS",
            "required_world_tags": min_world_tags,
            "usable_world_tags": used_names,
            "reason": "Board pose intentionally excludes K0/P0 from the primary solve.",
        }, {})

    object_points = np.concatenate(object_groups, axis=0)
    image_points = np.concatenate(image_groups, axis=0)
    ok, rvec, tvec = cv2.solvePnP(
        object_points, image_points, camera_matrix, distortion,
        flags=cv2.SOLVEPNP_ITERATIVE,
    )
    if not ok:
        return ({
            "status": "SOLVE_FAILED",
            "usable_world_tags": used_names,
        }, {})
    projected, _ = cv2.projectPoints(object_points, rvec, tvec, camera_matrix, distortion)
    residual_vectors = projected.reshape(-1, 2) - image_points
    all_rms = float(np.sqrt(np.mean(np.sum(residual_vectors ** 2, axis=1))))
    per_tag_rms: dict[str, float] = {}
    offset = 0
    for name in used_names:
        residual = residual_vectors[offset:offset + 4]
        per_tag_rms[name] = float(np.sqrt(np.mean(np.sum(residual ** 2, axis=1))))
        offset += 4
    board_to_camera, camera_to_board = homogeneous_transform(rvec, tvec)
    pose = {
        "status": "SOLVED",
        "coordinate_source": coordinate_source,
        "world_tags_used": used_names,
        "board_to_camera_rvec": rvec.reshape(-1).tolist(),
        "board_to_camera_translation_m": tvec.reshape(-1).tolist(),
        "board_to_camera_matrix": board_to_camera,
        "camera_to_board_matrix": camera_to_board,
        "reprojection_rms_px": all_rms,
        "world_tag_reprojection_rms_px": per_tag_rms,
    }

    checks: dict[str, Any] = {}
    for name, detection in detections_by_name.items():
        tag = tags.get(name)
        if not isinstance(tag, dict) or tag.get("role") != "station_check":
            continue
        object_corners = board_tag_corners(tag, edge_mm)
        if object_corners is None:
            checks[name] = {"status": "MAP_COORDINATE_MISSING"}
            continue
        expected_pixels, _ = cv2.projectPoints(
            object_corners, rvec, tvec, camera_matrix, distortion,
        )
        observed_pixels = np.asarray(detection["image_corners_px"], dtype=np.float64)
        residual = expected_pixels.reshape(-1, 2) - observed_pixels
        checks[name] = {
            "status": "CHECKED",
            "reprojection_rms_px": float(np.sqrt(np.mean(np.sum(residual ** 2, axis=1)))),
            "corner_residuals_px": residual.tolist(),
        }
    return pose, checks


def main() -> int:
    parser = argparse.ArgumentParser()
    source = parser.add_mutually_exclusive_group(required=True)
    source.add_argument("--image", type=Path)
    source.add_argument("--camera", type=int)
    parser.add_argument("--calibration", required=True, type=Path)
    parser.add_argument("--tag-map", required=True, type=Path)
    parser.add_argument("--output", required=True, type=Path)
    parser.add_argument("--annotated", type=Path, default=None)
    parser.add_argument(
        "--min-world-tags", type=int, default=3, choices=(2, 3, 4),
        help="Minimum visible measured T0-T3 tags required for a board solve",
    )
    parser.add_argument(
        "--require-board-pose", action="store_true",
        help="Return a nonzero exit code unless the measured-map board pose is solved",
    )
    parser.add_argument(
        "--require-tag",
        action="append",
        choices=sorted(EXPECTED_TAG_IDS),
        default=[],
        help=(
            "Require this named RC03 tag in the frame; repeat for multiple tags. "
            "The report is still written when a required tag is missing."
        ),
    )
    args = parser.parse_args()
    load_vision_dependencies()

    calibration: dict[str, Any] = json.loads(args.calibration.read_text(encoding="utf-8"))
    tag_map: dict[str, Any] = json.loads(args.tag_map.read_text(encoding="utf-8"))
    validate_tag_map(tag_map)
    camera_matrix = np.asarray(calibration["camera_matrix"], dtype=np.float64)
    distortion = np.asarray(calibration["distortion_coefficients"], dtype=np.float64)
    tag_size_m = float(tag_map["detection_edge_mm"]) / 1000.0

    frame = load_frame(args.image, args.camera)
    height, width = frame.shape[:2]
    expected_resolution = (int(calibration["image_width"]), int(calibration["image_height"]))
    if (width, height) != expected_resolution:
        raise SystemExit(f"Frame resolution {(width, height)} does not match calibration {expected_resolution}")

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    parameters = cv2.aruco.DetectorParameters()
    parameters.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(dictionary, parameters)
    corners, ids, rejected = detector.detectMarkers(frame)

    reverse_names = {int(value): key for key, value in tag_map["ids"].items()}
    tag_local_corners = local_tag_corners(tag_size_m)
    detections: list[dict[str, Any]] = []
    detections_by_name: dict[str, dict[str, Any]] = {}
    annotated = frame.copy()
    if ids is not None:
        cv2.aruco.drawDetectedMarkers(annotated, corners, ids)
        for marker_corners, marker_id_array in zip(corners, ids):
            marker_id = int(marker_id_array[0])
            name = reverse_names.get(marker_id, f"UNKNOWN_{marker_id}")
            image_corners = np.asarray(marker_corners, dtype=np.float64).reshape(4, 2)
            ok, rvec, tvec = cv2.solvePnP(
                tag_local_corners, image_corners, camera_matrix, distortion,
                flags=cv2.SOLVEPNP_IPPE_SQUARE,
            )
            if not ok:
                continue
            projected, _ = cv2.projectPoints(
                tag_local_corners, rvec, tvec, camera_matrix, distortion,
            )
            error = float(np.sqrt(np.mean(np.sum(
                (projected.reshape(4, 2) - image_corners) ** 2, axis=1,
            ))))
            cv2.drawFrameAxes(
                annotated, camera_matrix, distortion, rvec, tvec,
                tag_size_m * 0.6, 2,
            )
            detection = {
                "id": marker_id,
                "name": name,
                "known_to_map": marker_id in reverse_names,
                "rvec_tag_to_camera": rvec.reshape(-1).tolist(),
                "translation_m_camera_frame": tvec.reshape(-1).tolist(),
                "reprojection_error_px": error,
                "image_corners_px": image_corners.tolist(),
            }
            detections.append(detection)
            if marker_id in reverse_names:
                detections_by_name[name] = detection

    board_pose, station_checks = solve_board_pose(
        detections_by_name, tag_map, camera_matrix, distortion,
        args.min_world_tags,
    )
    required_tags = sorted(set(args.require_tag))
    missing_required_tags = sorted(set(required_tags) - set(detections_by_name))
    result = {
        "schema": "rocell.apriltag_detections.v2",
        "design_revision": tag_map.get("design_revision"),
        "family": tag_map["family"],
        "configured_tag_detection_edge_m": tag_size_m,
        "tag_map_sha256": sha256_file(args.tag_map),
        "tag_map_layout_sha256": tag_map.get("layout_sha256"),
        "tag_map_coordinate_source": tag_map.get("coordinate_source"),
        "frame_size": [width, height],
        "detections": detections,
        "required_tags": required_tags,
        "missing_required_tags": missing_required_tags,
        "board_pose": board_pose,
        "station_tag_checks": station_checks,
        "rejected_candidate_count": len(rejected),
        "opencv_version": cv2.__version__,
    }
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_text(json.dumps(result, indent=2) + "\n", encoding="utf-8")
    if args.annotated:
        args.annotated.parent.mkdir(parents=True, exist_ok=True)
        cv2.imwrite(str(args.annotated), annotated)
    summary = {
        "output": str(args.output),
        "detected": len(detections),
        "known_tags": len(detections_by_name),
        "missing_required_tags": missing_required_tags,
        "board_pose_status": board_pose["status"],
        "station_checks": sorted(station_checks),
    }
    print(json.dumps(summary, indent=2))
    if args.require_board_pose and board_pose["status"] != "SOLVED":
        return 2
    if missing_required_tags:
        return 3
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
