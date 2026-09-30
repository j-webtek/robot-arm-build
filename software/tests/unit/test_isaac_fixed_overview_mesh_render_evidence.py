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
RENDERER_PATH = (
    WORKSPACE / "software" / "integrations" / "isaac_sim"
    / "isaac_fixed_overview_mesh_render_probe.py"
)


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _builder():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("build_official_mesh_occlusion_data", BUILDER_PATH)
    assert spec is not None and spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _renderer():  # type: ignore[no-untyped-def]
    spec = importlib.util.spec_from_file_location("isaac_fixed_overview_mesh_render_probe", RENDERER_PATH)
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


def test_candidate_threshold_selection_prioritizes_missed_abstention_bound() -> None:
    module = _builder()
    labels = np.asarray([1.0] * 20 + [0.0] * 20)
    probabilities = np.asarray(
        [0.90] * 18 + [0.20, 0.10] + [0.40] * 5 + [0.15] * 15
    )

    threshold = module._select_threshold(labels, probabilities)

    predicted = probabilities >= threshold
    missed = int(np.count_nonzero(~predicted & labels.astype(bool)))
    assert threshold == 0.2
    assert missed / int(labels.sum()) <= 0.05


def test_chromatic_edge_features_are_deterministic_and_brightness_stable(tmp_path: Path) -> None:
    module = _builder()
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    base = np.tile(np.arange(64, 192, 8, dtype=np.uint8), (16, 1))
    rgb = np.stack((base, np.flip(base, axis=1), base), axis=2)
    bright = np.clip(rgb.astype(np.int16) + 40, 0, 255).astype(np.uint8)
    Image.fromarray(rgb).save(image_dir / "base.png")
    Image.fromarray(bright).save(image_dir / "bright.png")
    rows = [
        {
            "image_path": f"images/{name}.png",
            "image_sha256": _sha256((image_dir / f"{name}.png").read_bytes()),
            "safe_polygon_px": [[0, 0], [15, 0], [15, 15], [0, 15]],
            "decision": "target_visible",
        }
        for name in ("base", "bright")
    ]

    first, _ = module._features(tmp_path, rows, "chromatic_gray_edges")
    second, _ = module._features(tmp_path, rows, "chromatic_gray_edges")

    assert np.array_equal(first, second)
    assert first.shape == (2, 1536)
    assert np.mean(np.abs(first[0] - first[1])) < 0.08


def test_transit_pose_groups_are_predeclared_disjoint_and_schedule_bound() -> None:
    module = _renderer()
    groups = module.POSE_GROUPS
    flattened = [pose for poses in groups.values() for pose in poses]

    assert set(groups) == {"training", "development", "evaluation"}
    assert len(flattened) == len(set(flattened)) == 21
    assert set(module.REFERENCE_POSES) == {"ready", "hover_t", "hover_e"}
    assert set(module.SCHEDULE_POSE_SEQUENCES) == set(flattened) - set(module.REFERENCE_POSES)
    assert set(module.SCHEDULE_POSE_SEQUENCES.values()) == {
        8, 17, 26, 34, 35, 44, 52, 60, 63, 64, 72, 84, 96, 103, 104, 112, 120, 128,
    }
    assert not (set(groups["development"]) & set(groups["evaluation"]))


def test_transit_dataset_policy_uses_fresh_disjoint_lighting() -> None:
    builder = _builder()
    renderer = _renderer()
    source = {
        "schema": "tactevra.isaac_fixed_overview_mesh_render.v3",
        "pose_groups": {name: list(poses) for name, poses in renderer.POSE_GROUPS.items()},
        "pose_results": [
            {"pose_id": pose_id, "pose_group": group}
            for group, pose_ids in renderer.POSE_GROUPS.items()
            for pose_id in pose_ids
        ],
    }

    schema, policy = builder._split_policy(source)

    assert schema == "rocell.ai_official_mesh_occlusion_data.v3"
    assert policy["train"]["lighting"] == (
        "nominal", "dim", "bright", "warm", "glare", "blur",
        "cool", "side_shadow", "defocus",
    )
    assert policy["development"]["lighting"] == (
        "desaturated", "gamma_dark", "vignette",
    )
    assert policy["evaluation"]["lighting"] == (
        "low_contrast", "right_shadow", "motion_blur",
    )
    lighting = [set(split["lighting"]) for split in policy.values()]
    assert all(
        not (left & right)
        for index, left in enumerate(lighting)
        for right in lighting[index + 1:]
    )


def test_transit_lighting_families_are_deterministic_and_distinct() -> None:
    module = _builder()
    pixels = np.arange(48 * 48 * 3, dtype=np.uint8).reshape(48, 48, 3)
    source = Image.fromarray(pixels, mode="RGB")
    variants = (*module.TRANSIT_LIGHTING["development"], *module.TRANSIT_LIGHTING["evaluation"])

    first = [np.asarray(module._lighting(source, name)) for name in variants]
    second = [np.asarray(module._lighting(source, name)) for name in variants]

    assert all(np.array_equal(left, right) for left, right in zip(first, second, strict=True))
    assert len({_sha256(value.tobytes()) for value in first}) == len(variants)


def test_spatial_crops_are_deterministic_channel_first_and_labeled(tmp_path: Path) -> None:
    module = _builder()
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    pixels = np.arange(64 * 64 * 3, dtype=np.uint8).reshape(64, 64, 3)
    image_path = image_dir / "sample.png"
    Image.fromarray(pixels, mode="RGB").save(image_path)
    row = {
        "image_path": "images/sample.png",
        "image_sha256": _sha256(image_path.read_bytes()),
        "safe_polygon_px": [[20, 20], [44, 20], [44, 44], [20, 44]],
        "decision": "abstain",
    }

    first_x, first_y = module._spatial_crops(tmp_path, [row])
    second_x, second_y = module._spatial_crops(tmp_path, [row])

    assert first_x.shape == (1, 3, 32, 32)
    assert first_x.dtype == np.float32
    assert np.array_equal(first_x, second_x)
    assert np.array_equal(first_y, second_y)
    assert first_y.tolist() == [1.0]
    assert 0.0 <= float(first_x.min()) <= float(first_x.max()) <= 1.0
