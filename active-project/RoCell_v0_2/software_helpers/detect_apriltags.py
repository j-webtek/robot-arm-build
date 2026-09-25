#!/usr/bin/env python3
"""Detect RoCell AprilTags and estimate each tag pose.

Example image mode:
  python detect_apriltags.py --image frame.png --calibration camera_intrinsics.json \
      --tag-map ../fiducials/apriltag_map.json --annotated annotated.png --output poses.json

Example live camera mode:
  python detect_apriltags.py --camera 0 --calibration camera_intrinsics.json \
      --tag-map ../fiducials/apriltag_map.json --annotated annotated.png --output poses.json
"""
from __future__ import annotations

import argparse
import json
from pathlib import Path
from typing import Any

import cv2
import numpy as np


def load_frame(image_path: Path | None, camera_index: int | None) -> np.ndarray:
    if image_path is not None:
        image = cv2.imread(str(image_path), cv2.IMREAD_COLOR)
        if image is None:
            raise SystemExit(f"Could not read {image_path}")
        return image
    cap = cv2.VideoCapture(int(camera_index))
    ok, frame = cap.read()
    cap.release()
    if not ok or frame is None:
        raise SystemExit(f"Could not capture camera {camera_index}")
    return frame


def main() -> int:
    ap = argparse.ArgumentParser()
    src = ap.add_mutually_exclusive_group(required=True)
    src.add_argument("--image", type=Path)
    src.add_argument("--camera", type=int)
    ap.add_argument("--calibration", required=True, type=Path)
    ap.add_argument("--tag-map", required=True, type=Path)
    ap.add_argument("--output", required=True, type=Path)
    ap.add_argument("--annotated", type=Path, default=None)
    args = ap.parse_args()

    calib: dict[str, Any] = json.loads(args.calibration.read_text(encoding="utf-8"))
    tag_map: dict[str, Any] = json.loads(args.tag_map.read_text(encoding="utf-8"))
    camera_matrix = np.asarray(calib["camera_matrix"], dtype=np.float64)
    dist = np.asarray(calib["distortion_coefficients"], dtype=np.float64)
    tag_size_m = float(tag_map["detection_edge_mm"]) / 1000.0

    frame = load_frame(args.image, args.camera)
    h, w = frame.shape[:2]
    expected = (int(calib["image_width"]), int(calib["image_height"]))
    if (w, h) != expected:
        raise SystemExit(f"Frame resolution {(w,h)} does not match calibration {expected}")

    dictionary = cv2.aruco.getPredefinedDictionary(cv2.aruco.DICT_APRILTAG_36h11)
    params = cv2.aruco.DetectorParameters()
    params.cornerRefinementMethod = cv2.aruco.CORNER_REFINE_SUBPIX
    detector = cv2.aruco.ArucoDetector(dictionary, params)
    corners, ids, rejected = detector.detectMarkers(frame)

    reverse_names = {int(v): k for k, v in tag_map["ids"].items()}
    half = tag_size_m / 2.0
    # Order required by SOLVEPNP_IPPE_SQUARE: TL, TR, BR, BL.
    object_corners = np.array([
        [-half, +half, 0.0],
        [+half, +half, 0.0],
        [+half, -half, 0.0],
        [-half, -half, 0.0],
    ], dtype=np.float64)

    detections: list[dict[str, Any]] = []
    annotated = frame.copy()
    if ids is not None:
        cv2.aruco.drawDetectedMarkers(annotated, corners, ids)
        for marker_corners, marker_id_arr in zip(corners, ids):
            marker_id = int(marker_id_arr[0])
            image_corners = np.asarray(marker_corners, dtype=np.float64).reshape(4, 2)
            ok, rvec, tvec = cv2.solvePnP(
                object_corners,
                image_corners,
                camera_matrix,
                dist,
                flags=cv2.SOLVEPNP_IPPE_SQUARE,
            )
            if not ok:
                continue
            projected, _ = cv2.projectPoints(object_corners, rvec, tvec, camera_matrix, dist)
            error = float(np.sqrt(np.mean(np.sum((projected.reshape(4,2)-image_corners)**2, axis=1))))
            cv2.drawFrameAxes(annotated, camera_matrix, dist, rvec, tvec, tag_size_m * 0.6, 2)
            detections.append({
                "id": marker_id,
                "name": reverse_names.get(marker_id, f"UNKNOWN_{marker_id}"),
                "rvec": rvec.reshape(-1).tolist(),
                "translation_m_camera_frame": tvec.reshape(-1).tolist(),
                "reprojection_error_px": error,
                "image_corners_px": image_corners.tolist(),
            })

    result = {
        "schema": "rocell.apriltag_detections.v1",
        "family": tag_map["family"],
        "configured_tag_detection_edge_m": tag_size_m,
        "frame_size": [w, h],
        "detections": detections,
        "rejected_candidate_count": len(rejected),
        "opencv_version": cv2.__version__,
    }
    args.output.write_text(json.dumps(result, indent=2), encoding="utf-8")
    if args.annotated:
        cv2.imwrite(str(args.annotated), annotated)
    print(json.dumps({"output": str(args.output), "detected": len(detections)}, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
