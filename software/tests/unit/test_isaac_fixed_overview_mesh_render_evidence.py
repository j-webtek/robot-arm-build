from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
from PIL import Image


WORKSPACE = Path(__file__).resolve().parents[3]
EVIDENCE = (
    WORKSPACE / "software" / "integrations" / "isaac_sim" / "evidence"
    / "fixed_overview_official_mesh_v1"
)
BUILDER_PATH = (
    WORKSPACE / "software" / "ai" / "train" / "build_official_mesh_occlusion_data.py"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _builder():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("build_official_mesh_occlusion_data", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def test_official_mesh_render_receipt_is_bound_and_zero_authority() -> None:
    manifest_path = EVIDENCE / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    claimed_receipt_sha = manifest.pop("receipt_sha256")
    canonical = json.dumps(
        manifest, sort_keys=True, separators=(",", ":"), ensure_ascii=True, allow_nan=False
    ).encode("utf-8")
    assert _sha256(canonical) == claimed_receipt_sha
    assert manifest["schema"] == "tactevra.isaac_fixed_overview_mesh_render.v1"
    assert manifest["evidence_class"] == "OFFICIAL_VISUAL_MESH_PERCEPTION_COMPARISON_ONLY"
    assert manifest["visual_meshes_used_for_collision"] is False
    assert manifest["physics_steps"] == 0
    assert manifest["hardware_access"] is False
    assert manifest["hardware_writes"] == 0
    assert manifest["physical_movements"] == 0
    assert manifest["physical_authority"] is False
    assert manifest["result_status"] == "PASS_WITH_BLOCKERS"
    assert manifest["result_summary"]["minimum_mask_iou"] == min(
        row["mask_iou"] for row in manifest["pose_results"]
    )

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
    expected_occlusion_counts = {
        "ready": (1, 5),
        "hover_t": (14, 17),
        "hover_e": (14, 18),
    }
    target_order = None
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
        targets = row["targets"]
        assert len(targets) == 75
        current_order = [(target["device"], target["target_id"]) for target in targets]
        target_order = current_order if target_order is None else target_order
        assert current_order == target_order
        assert all(target["in_frame"] is True for target in targets)
        center_count = sum(target["center_occluded_by_official_mesh"] for target in targets)
        overlap_count = sum(
            target["safe_region_official_mesh_overlap_fraction"] > 0.0
            for target in targets
        )
        assert (center_count, overlap_count) == expected_occlusion_counts[row["pose_id"]]


def test_official_mesh_occlusion_builder_has_disjoint_groups_and_zero_authority(
    tmp_path: Path,
) -> None:
    module = _builder()
    first = module.build(EVIDENCE / "manifest.json", tmp_path / "first")
    second = module.build(EVIDENCE / "manifest.json", tmp_path / "second")

    assert first == second
    assert first["scope"] == "SYNTHETIC_ONLY_NO_DEPLOYMENT_QUALIFICATION"
    assert first["pose_groups_disjoint"] is True
    assert first["lighting_groups_disjoint"] is True
    assert first["splits"]["train"] == {
        "path": "train.jsonl",
        "sha256": "140636df91e1884ca28d5f8cb9fb3662946a0ab8633f452098de4e87c3f8f107",
        "count": 450,
        "abstain_count": 51,
        "visible_count": 399,
    }
    assert first["splits"]["evaluation"] == {
        "path": "evaluation.jsonl",
        "sha256": "c00b3c3ded761af0c57e4211441d253bfa9848623b658be02dd114a2b40d70ca",
        "count": 225,
        "abstain_count": 45,
        "visible_count": 180,
    }
    assert first["authority"] == {
        "hardware_accessed": False,
        "hardware_write_count": 0,
        "physical_movement_count": 0,
        "can_release_physical_gates": False,
    }
    assert len(first["images"]) == 9
    assert len({record["sha256"] for record in first["images"]}) == 9
    assert all(
        (tmp_path / "first" / record["path"]).is_file()
        for record in first["images"]
    )
    first_score = module.train_baseline(tmp_path / "first", tmp_path / "run-first")
    second_score = module.train_baseline(tmp_path / "second", tmp_path / "run-second")
    assert first_score == second_score
    assert first_score["promotion_status"] == "BLOCKED_SYNTHETIC_ONLY"
    assert first_score["train"]["confusion"] == {
        "true_abstain": 49,
        "true_visible": 398,
        "false_abstain": 1,
        "missed_abstain": 2,
    }
    assert first_score["evaluation"]["confusion"] == {
        "true_abstain": 32,
        "true_visible": 118,
        "false_abstain": 62,
        "missed_abstain": 13,
    }
    assert first_score["evaluation"]["balanced_accuracy"] < 0.70
    assert first_score["evaluation"]["expected_calibration_error_10_bin"] > 0.30
    assert first_score["hardware_writes"] == 0
    assert first_score["physical_movements"] == 0


def test_official_mesh_occlusion_builder_rejects_altered_source(tmp_path: Path) -> None:
    module = _builder()
    altered_dir = tmp_path / "altered"
    altered_dir.mkdir()
    source = json.loads((EVIDENCE / "manifest.json").read_text(encoding="utf-8"))
    source["target_catalog_sha256"] = "0" * 64
    (altered_dir / "manifest.json").write_text(json.dumps(source), encoding="utf-8")
    try:
        module.build(altered_dir / "manifest.json", tmp_path / "output")
    except ValueError as exc:
        assert "receipt hash mismatch" in str(exc)
    else:
        raise AssertionError("altered source was accepted")


def test_expanded_occlusion_policy_preserves_reserved_evaluation_groups() -> None:
    module = _builder()
    pose_groups = {
        "training": ["ready", "hover_t", "hover_e"],
        "development": ["hover_h", "contact_h"],
        "evaluation": ["hover_1", "contact_1", "hover_period", "contact_period"],
    }
    source = {
        "schema": "tactevra.isaac_fixed_overview_mesh_render.v2",
        "pose_groups": pose_groups,
        "pose_results": [
            {"pose_id": pose_id, "pose_group": group}
            for group, pose_ids in pose_groups.items()
            for pose_id in pose_ids
        ],
    }

    schema, policy = module._split_policy(source)

    assert schema == "rocell.ai_official_mesh_occlusion_data.v2"
    assert policy == {
        "train": {
            "poses": ("ready", "hover_t", "hover_e"),
            "lighting": ("nominal", "dim", "bright"),
        },
        "development": {
            "poses": ("hover_h", "contact_h"),
            "lighting": ("warm", "glare", "blur"),
        },
        "evaluation": {
            "poses": ("hover_1", "contact_1", "hover_period", "contact_period"),
            "lighting": ("cool", "side_shadow", "defocus"),
        },
    }
    assert not (set(policy["train"]["poses"]) & set(policy["development"]["poses"]))
    assert not (set(policy["train"]["lighting"]) & set(policy["evaluation"]["lighting"]))


def test_expanded_lighting_families_are_deterministic_and_distinct() -> None:
    module = _builder()
    pixels = np.arange(32 * 32 * 3, dtype=np.uint8).reshape(32, 32, 3)
    source = Image.fromarray(pixels, mode="RGB")

    first = [np.asarray(module._lighting(source, name)) for name in module.EXPANDED_LIGHTING["evaluation"]]
    second = [np.asarray(module._lighting(source, name)) for name in module.EXPANDED_LIGHTING["evaluation"]]

    assert all(np.array_equal(left, right) for left, right in zip(first, second, strict=True))
    assert len({_sha256(value.tobytes()) for value in first}) == 3
