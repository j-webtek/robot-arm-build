from __future__ import annotations

import hashlib
import json
from pathlib import Path

import numpy as np
from PIL import Image


WORKSPACE = Path(__file__).resolve().parents[3]
EVIDENCE = (
    WORKSPACE / "software" / "integrations" / "isaac_sim" / "evidence"
    / "fixed_overview_official_mesh_v1"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def test_official_mesh_render_receipt_is_bound_and_zero_authority() -> None:
    manifest_path = EVIDENCE / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))
    status = json.loads((EVIDENCE / "status.json").read_text(encoding="utf-8"))

    claimed_receipt_sha = manifest.pop("receipt_sha256")
    canonical = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    assert _sha256(canonical) == claimed_receipt_sha == status["receipt_sha256"]
    assert manifest["schema"] == "tactevra.isaac_fixed_overview_mesh_render.v1"
    assert manifest["evidence_class"] == "OFFICIAL_VISUAL_MESH_PERCEPTION_COMPARISON_ONLY"
    assert manifest["visual_meshes_used_for_collision"] is False
    assert manifest["physics_steps"] == 0
    assert manifest["hardware_access"] is False
    assert manifest["hardware_writes"] == 0
    assert manifest["physical_movements"] == 0
    assert manifest["physical_authority"] is False
    assert status["status"] == "PASS_WITH_BLOCKERS"

    arrays = {}
    for name, artifact in manifest["artifact_atlases"].items():
        path = EVIDENCE / artifact["path"]
        assert _sha256(path.read_bytes()) == artifact["sha256"]
        dtype = np.uint16 if name == "robot_depth_mm" else None
        arrays[name] = np.asarray(Image.open(path), dtype=dtype)
        assert arrays[name].shape[:2] == (3240, 1920)

    results = manifest["pose_results"]
    assert [row["pose_id"] for row in results] == ["ready", "hover_t", "hover_e"]
    assert len({row["robot_mask_crop_pixel_sha256"] for row in results}) == 3
    for row in results:
        left, top, right, bottom = row["atlas_crop_px"]
        assert [left, right - left, bottom - top] == [0, 1920, 1080]
        slices = {
            "rgb": arrays["rgb"][top:bottom, left:right],
            "robot_mask": arrays["robot_mask"][top:bottom, left:right],
            "robot_depth": arrays["robot_depth_mm"][top:bottom, left:right],
        }
        assert _sha256(slices["rgb"].tobytes()) == row["rgb_crop_pixel_sha256"]
        assert _sha256(slices["robot_mask"].tobytes()) == row["robot_mask_crop_pixel_sha256"]
        assert _sha256(slices["robot_depth"].tobytes()) == row["robot_depth_crop_pixel_sha256"]
        assert 0.0 < row["mask_iou"] < 1.0
        assert row["official_mesh_outside_capsule_pixels"] > 0
        assert row["capsule_outside_official_mesh_pixels"] > 0
