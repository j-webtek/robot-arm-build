#!/usr/bin/env python3
"""Calibrate a fixed workcell camera from ChArUco images.

Example:
  python calibrate_camera_charuco.py \
      --images 'captures/*.png' \
      --definition ../fiducials/charuco_board_definition.json \
      --output camera_intrinsics.json

Capture at least 20 sharp images at the exact runtime resolution. Tilt and move the
board so it covers the center, edges, and corners of the image. This script uses the
modern OpenCV CharucoDetector + Board.matchImagePoints path.
"""
from __future__ import annotations

import argparse
import glob
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def dictionary_from_name(name: str):
    if not hasattr(cv2.aruco, name):
        raise ValueError(f"OpenCV does not provide aruco dictionary {name!r}")
    return cv2.aruco.getPredefinedDictionary(getattr(cv2.aruco, name))


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--images", required=True, help="Glob for calibration images")
    ap.add_argument("--definition", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--min-corners", type=int, default=8)
    ap.add_argument("--preview-dir", type=Path, default=None)
    args = ap.parse_args()

    definition: dict[str, Any] = json.loads(args.definition.read_text(encoding="utf-8"))
    dictionary = dictionary_from_name(definition["dictionary"])
    square_m = float(definition["square_length_mm"]) / 1000.0
    marker_m = float(definition["marker_length_mm"]) / 1000.0
    board = cv2.aruco.CharucoBoard(
        (int(definition["squares_x"]), int(definition["squares_y"])),
        square_m,
        marker_m,
        dictionary,
    )
    detector = cv2.aruco.CharucoDetector(board)

    paths = sorted(glob.glob(args.images))
    if not paths:
        raise SystemExit(f"No images matched: {args.images}")
    if args.preview_dir:
        args.preview_dir.mkdir(parents=True, exist_ok=True)

    object_points: list[np.ndarray] = []
    image_points: list[np.ndarray] = []
    image_size = None
    used: list[str] = []
    rejected: list[dict[str, Any]] = []

    for path_str in paths:
        image = cv2.imread(path_str, cv2.IMREAD_COLOR)
        if image is None:
            rejected.append({"file": path_str, "reason": "unreadable"})
            continue
        h, w = image.shape[:2]
        if image_size is None:
            image_size = (w, h)
        elif image_size != (w, h):
            rejected.append({"file": path_str, "reason": f"resolution {(w,h)} != {image_size}"})
            continue

        corners, ids, marker_corners, marker_ids = detector.detectBoard(image)
        count = 0 if ids is None else int(len(ids))
        if ids is None or count < args.min_corners:
            rejected.append({"file": path_str, "reason": f"only {count} ChArUco corners"})
            continue

        obj, img = board.matchImagePoints(corners, ids)
        if obj is None or img is None or len(obj) < args.min_corners:
            rejected.append({"file": path_str, "reason": "point matching failed"})
            continue
        object_points.append(np.asarray(obj, dtype=np.float32))
        image_points.append(np.asarray(img, dtype=np.float32))
        used.append(path_str)

        if args.preview_dir:
            preview = image.copy()
            cv2.aruco.drawDetectedCornersCharuco(preview, corners, ids)
            cv2.imwrite(str(args.preview_dir / Path(path_str).name), preview)

    if image_size is None or len(used) < 10:
        raise SystemExit(
            f"Only {len(used)} valid views. Capture at least 10; 20-30 varied views are recommended."
        )

    flags = 0
    rms, camera_matrix, dist_coeffs, rvecs, tvecs = cv2.calibrateCamera(
        object_points,
        image_points,
        image_size,
        None,
        None,
        flags=flags,
    )

    per_view_errors: list[float] = []
    for obj, img, rvec, tvec in zip(object_points, image_points, rvecs, tvecs):
        projected, _ = cv2.projectPoints(obj, rvec, tvec, camera_matrix, dist_coeffs)
        projected = projected.reshape(-1, 2)
        observed = img.reshape(-1, 2)
        per_view_errors.append(float(np.sqrt(np.mean(np.sum((projected - observed) ** 2, axis=1)))))

    result = {
        "schema": "rocell.camera_intrinsics.v1",
        "image_width": image_size[0],
        "image_height": image_size[1],
        "camera_matrix": camera_matrix.tolist(),
        "distortion_coefficients": dist_coeffs.reshape(-1).tolist(),
        "rms_reprojection_error_px": float(rms),
        "mean_view_reprojection_error_px": float(np.mean(per_view_errors)),
        "max_view_reprojection_error_px": float(np.max(per_view_errors)),
        "views_used": used,
        "views_rejected": rejected,
        "board_definition": definition,
        "opencv_version": cv2.__version__,
    }
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    print(json.dumps({
        "output": str(args.output),
        "views_used": len(used),
        "rms_px": result["rms_reprojection_error_px"],
        "mean_view_error_px": result["mean_view_reprojection_error_px"],
        "max_view_error_px": result["max_view_reprojection_error_px"],
    }, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
