from __future__ import annotations

import hashlib
import importlib.util
import json
from pathlib import Path

import numpy as np
import pytest
from PIL import Image, ImageDraw


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
    assert len(flattened) == len(set(flattened)) == 45
    assert set(module.REFERENCE_POSES) == {"ready", "hover_t", "hover_e"}
    assert set(module.SCHEDULE_POSE_SEQUENCES) == set(flattened) - set(module.REFERENCE_POSES)
    assert set(module.SCHEDULE_POSE_SEQUENCES.values()) == {
        2, 4, 6, 8, 10, 13, 17, 20, 26, 34, 35, 44, 52, 60, 63, 64, 72,
        11, 15, 19, 23, 27, 31, 84, 96, 103, 104, 112, 113, 114, 115,
        117, 118, 119, 120, 121, 122, 123, 124, 126, 128, 130,
    }
    assert set(groups["development"]) == {
        "targetaware_dev_outbound_11", "targetaware_dev_outbound_15",
        "targetaware_dev_outbound_19", "targetaware_dev_return_113",
        "targetaware_dev_return_117", "targetaware_dev_return_121",
    }
    assert set(groups["evaluation"]) == {
        "targetaware_eval_outbound_23", "targetaware_eval_outbound_27",
        "targetaware_eval_outbound_31", "targetaware_eval_return_115",
        "targetaware_eval_return_119", "targetaware_eval_return_123",
    }
    assert not (set(groups["development"]) & set(groups["evaluation"]))


def test_mask_perturbation_poses_are_fresh_development_only() -> None:
    module = _renderer()
    groups = module.PERTURBATION_POSE_GROUPS
    sequences = module.PERTURBATION_SCHEDULE_POSE_SEQUENCES

    assert set(groups) == {"training", "development", "evaluation"}
    assert groups["training"] == groups["evaluation"] == ()
    assert set(groups["development"]) == set(sequences)
    assert len(sequences) == len(set(sequences.values())) == 6
    assert not (set(sequences.values()) & set(module.SCHEDULE_POSE_SEQUENCES.values()))


def test_policy_evaluation_poses_are_fresh_evaluation_only() -> None:
    module = _renderer()
    groups = module.POLICY_EVALUATION_POSE_GROUPS
    sequences = module.POLICY_EVALUATION_SCHEDULE_POSE_SEQUENCES

    assert set(groups) == {"training", "development", "evaluation"}
    assert groups["training"] == groups["development"] == ()
    assert groups["evaluation"] == tuple(sequences)
    assert set(sequences.values()) == {40, 48, 56, 76, 88, 100}
    prior = set(module.SCHEDULE_POSE_SEQUENCES.values()) | set(
        module.PERTURBATION_SCHEDULE_POSE_SEQUENCES.values()
    )
    assert not (set(sequences.values()) & prior)


def test_hard_negative_poses_are_fresh_development_only() -> None:
    module = _renderer()
    groups = module.HARD_NEGATIVE_POSE_GROUPS
    sequences = module.HARD_NEGATIVE_SCHEDULE_POSE_SEQUENCES

    assert set(groups) == {"training", "development", "evaluation"}
    assert groups["training"] == groups["evaluation"] == ()
    assert groups["development"] == tuple(sequences)
    assert set(sequences.values()) == {42, 50, 58, 78, 90, 98}
    prior = (
        set(module.SCHEDULE_POSE_SEQUENCES.values())
        | set(module.PERTURBATION_SCHEDULE_POSE_SEQUENCES.values())
        | set(module.POLICY_EVALUATION_SCHEDULE_POSE_SEQUENCES.values())
    )
    assert not (set(sequences.values()) & prior)


def test_target_identity_training_poses_are_fresh_training_only() -> None:
    module = _renderer()
    groups = module.TARGET_IDENTITY_TRAINING_POSE_GROUPS
    sequences = module.TARGET_IDENTITY_TRAINING_SCHEDULE_POSE_SEQUENCES

    assert set(groups) == {"training", "development", "evaluation"}
    assert groups["development"] == groups["evaluation"] == ()
    assert groups["training"] == tuple(sequences)
    assert set(sequences.values()) == {
        41, 43, 45, 47, 49, 51, 77, 79, 81, 83, 85, 87,
    }
    prior = (
        set(module.SCHEDULE_POSE_SEQUENCES.values())
        | set(module.PERTURBATION_SCHEDULE_POSE_SEQUENCES.values())
        | set(module.POLICY_EVALUATION_SCHEDULE_POSE_SEQUENCES.values())
        | set(module.HARD_NEGATIVE_SCHEDULE_POSE_SEQUENCES.values())
    )
    assert not (set(sequences.values()) & prior)


def test_fusion_evaluation_poses_are_fresh_evaluation_only() -> None:
    module = _renderer()
    groups = module.FUSION_EVALUATION_POSE_GROUPS
    sequences = module.FUSION_EVALUATION_SCHEDULE_POSE_SEQUENCES

    assert set(groups) == {"training", "development", "evaluation"}
    assert groups["training"] == groups["development"] == ()
    assert groups["evaluation"] == tuple(sequences)
    assert set(sequences.values()) == {46, 54, 62, 80, 92, 102}
    prior = (
        set(module.SCHEDULE_POSE_SEQUENCES.values())
        | set(module.PERTURBATION_SCHEDULE_POSE_SEQUENCES.values())
        | set(module.POLICY_EVALUATION_SCHEDULE_POSE_SEQUENCES.values())
        | set(module.HARD_NEGATIVE_SCHEDULE_POSE_SEQUENCES.values())
        | set(module.TARGET_IDENTITY_TRAINING_SCHEDULE_POSE_SEQUENCES.values())
    )
    assert not (set(sequences.values()) & prior)


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


def test_specificity_dataset_policy_uses_fresh_disjoint_lighting() -> None:
    builder = _builder()
    renderer = _renderer()
    source = {
        "schema": "tactevra.isaac_fixed_overview_mesh_render.v4",
        "pose_groups": {name: list(poses) for name, poses in renderer.POSE_GROUPS.items()},
        "pose_results": [
            {"pose_id": pose_id, "pose_group": group}
            for group, pose_ids in renderer.POSE_GROUPS.items()
            for pose_id in pose_ids
        ],
    }

    schema, policy = builder._split_policy(source)

    assert schema == "rocell.ai_official_mesh_occlusion_data.v4"
    assert policy["development"]["lighting"] == (
        "soft_neutral", "gamma_mid", "left_shadow",
    )
    assert policy["evaluation"]["lighting"] == (
        "cool_flat", "top_shadow", "vertical_motion_blur",
    )
    pose_groups = [set(split["poses"]) for split in policy.values()]
    lighting_groups = [set(split["lighting"]) for split in policy.values()]
    assert all(
        not (left & right)
        for groups in (pose_groups, lighting_groups)
        for index, left in enumerate(groups)
        for right in groups[index + 1:]
    )


def test_specificity_lighting_families_are_deterministic_and_distinct() -> None:
    module = _builder()
    pixels = np.arange(48 * 48 * 3, dtype=np.uint8).reshape(48, 48, 3)
    source = Image.fromarray(pixels, mode="RGB")
    variants = (
        *module.SPECIFICITY_LIGHTING["development"],
        *module.SPECIFICITY_LIGHTING["evaluation"],
    )

    first = [np.asarray(module._lighting(source, name)) for name in variants]
    second = [np.asarray(module._lighting(source, name)) for name in variants]

    assert all(np.array_equal(left, right) for left, right in zip(first, second, strict=True))
    assert len({_sha256(value.tobytes()) for value in first}) == len(variants)


def test_target_aware_dataset_policy_uses_fresh_disjoint_lighting() -> None:
    builder = _builder()
    renderer = _renderer()
    source = {
        "schema": "tactevra.isaac_fixed_overview_mesh_render.v5",
        "pose_groups": {name: list(poses) for name, poses in renderer.POSE_GROUPS.items()},
        "pose_results": [
            {"pose_id": pose_id, "pose_group": group}
            for group, pose_ids in renderer.POSE_GROUPS.items()
            for pose_id in pose_ids
        ],
    }

    schema, policy = builder._split_policy(source)

    assert schema == "rocell.ai_official_mesh_occlusion_data.v5"
    assert policy["development"]["lighting"] == (
        "neutral_low", "bottom_shadow", "diagonal_motion_blur",
    )
    assert policy["evaluation"]["lighting"] == (
        "green_cast", "corner_glare", "horizontal_motion_blur",
    )
    assert set(builder.SPECIFICITY_LIGHTING["development"]) <= set(
        policy["train"]["lighting"]
    )
    assert set(builder.SPECIFICITY_LIGHTING["evaluation"]) <= set(
        policy["train"]["lighting"]
    )
    groups = [set(split["lighting"]) for split in policy.values()]
    assert all(
        not (left & right)
        for index, left in enumerate(groups)
        for right in groups[index + 1:]
    )


def test_mask_perturbation_policy_has_no_evaluation_group() -> None:
    builder = _builder()
    renderer = _renderer()
    source = {
        "schema": "tactevra.isaac_fixed_overview_mesh_render.v6",
        "pose_groups": {
            name: list(poses)
            for name, poses in renderer.PERTURBATION_POSE_GROUPS.items()
        },
        "pose_results": [
            {"pose_id": pose_id, "pose_group": group}
            for group, pose_ids in renderer.PERTURBATION_POSE_GROUPS.items()
            for pose_id in pose_ids
        ],
    }

    schema, policy = builder._split_policy(source)

    assert schema == "rocell.ai_official_mesh_occlusion_data.v6"
    assert policy["train"]["poses"] == policy["evaluation"]["poses"] == ()
    assert policy["development"]["poses"] == tuple(
        renderer.PERTURBATION_POSE_GROUPS["development"]
    )
    assert policy["development"]["lighting"] == (
        "neutral_low", "bottom_shadow", "diagonal_motion_blur",
    )


def test_policy_evaluation_dataset_policy_is_evaluation_only() -> None:
    builder = _builder()
    renderer = _renderer()
    source = {
        "schema": "tactevra.isaac_fixed_overview_mesh_render.v7",
        "pose_groups": {
            name: list(poses)
            for name, poses in renderer.POLICY_EVALUATION_POSE_GROUPS.items()
        },
        "pose_results": [
            {"pose_id": pose_id, "pose_group": group}
            for group, pose_ids in renderer.POLICY_EVALUATION_POSE_GROUPS.items()
            for pose_id in pose_ids
        ],
    }

    schema, policy = builder._split_policy(source)

    assert schema == "rocell.ai_official_mesh_occlusion_data.v7"
    assert policy["train"]["poses"] == policy["development"]["poses"] == ()
    assert policy["evaluation"]["poses"] == tuple(
        renderer.POLICY_EVALUATION_POSE_GROUPS["evaluation"]
    )
    assert policy["evaluation"]["lighting"] == (
        "amber_cast", "center_glare", "anti_diagonal_motion_blur",
    )


def test_policy_evaluation_lighting_is_deterministic_and_fresh() -> None:
    module = _builder()
    pixels = np.arange(48 * 48 * 3, dtype=np.uint8).reshape(48, 48, 3)
    source = Image.fromarray(pixels, mode="RGB")
    variants = module.POLICY_EVALUATION_LIGHTING["evaluation"]

    first = [np.asarray(module._lighting(source, name)) for name in variants]
    second = [np.asarray(module._lighting(source, name)) for name in variants]

    assert all(np.array_equal(left, right) for left, right in zip(first, second, strict=True))
    assert len({_sha256(value.tobytes()) for value in first}) == len(variants)
    prior = {
        name
        for policy in (
            module.LEGACY_SPLITS, module.EXPANDED_LIGHTING, module.TRANSIT_LIGHTING,
            module.SPECIFICITY_LIGHTING, module.TARGET_AWARE_LIGHTING,
            module.PERTURBATION_LIGHTING,
        )
        for split in policy.values()
        for name in (split["lighting"] if isinstance(split, dict) else split)
    }
    assert not (set(variants) & prior)


def test_hard_negative_dataset_policy_is_development_only() -> None:
    builder = _builder()
    renderer = _renderer()
    source = {
        "schema": "tactevra.isaac_fixed_overview_mesh_render.v8",
        "pose_groups": {
            name: list(poses)
            for name, poses in renderer.HARD_NEGATIVE_POSE_GROUPS.items()
        },
        "pose_results": [
            {"pose_id": pose_id, "pose_group": group}
            for group, pose_ids in renderer.HARD_NEGATIVE_POSE_GROUPS.items()
            for pose_id in pose_ids
        ],
    }

    schema, policy = builder._split_policy(source)

    assert schema == "rocell.ai_official_mesh_occlusion_data.v8"
    assert policy["train"]["poses"] == policy["evaluation"]["poses"] == ()
    assert policy["development"]["poses"] == tuple(
        renderer.HARD_NEGATIVE_POSE_GROUPS["development"]
    )
    assert policy["development"]["lighting"] == (
        "amber_low_contrast", "right_center_glare", "offset_anti_diagonal_blur",
    )


def test_hard_negative_lighting_is_deterministic_and_distinct() -> None:
    module = _builder()
    pixels = np.arange(48 * 48 * 3, dtype=np.uint8).reshape(48, 48, 3)
    source = Image.fromarray(pixels, mode="RGB")
    variants = module.HARD_NEGATIVE_LIGHTING["development"]

    first = [np.asarray(module._lighting(source, name)) for name in variants]
    second = [np.asarray(module._lighting(source, name)) for name in variants]

    assert all(np.array_equal(left, right) for left, right in zip(first, second, strict=True))
    assert len({_sha256(value.tobytes()) for value in first}) == len(variants)
    prior = {
        name
        for policy in (
            module.LEGACY_SPLITS, module.EXPANDED_LIGHTING, module.TRANSIT_LIGHTING,
            module.SPECIFICITY_LIGHTING, module.TARGET_AWARE_LIGHTING,
            module.PERTURBATION_LIGHTING, module.POLICY_EVALUATION_LIGHTING,
        )
        for split in policy.values()
        for name in (split["lighting"] if isinstance(split, dict) else split)
    }
    assert not (set(variants) & prior)


def test_target_identity_training_policy_has_no_selection_or_evaluation_group() -> None:
    builder = _builder()
    renderer = _renderer()
    source = {
        "schema": "tactevra.isaac_fixed_overview_mesh_render.v9",
        "pose_groups": {
            name: list(poses)
            for name, poses in renderer.TARGET_IDENTITY_TRAINING_POSE_GROUPS.items()
        },
        "pose_results": [
            {"pose_id": pose_id, "pose_group": group}
            for group, pose_ids in renderer.TARGET_IDENTITY_TRAINING_POSE_GROUPS.items()
            for pose_id in pose_ids
        ],
    }

    schema, policy = builder._split_policy(source)

    assert schema == "rocell.ai_official_mesh_occlusion_data.v9"
    assert policy["development"]["poses"] == policy["evaluation"]["poses"] == ()
    assert policy["train"]["poses"] == tuple(
        renderer.TARGET_IDENTITY_TRAINING_POSE_GROUPS["training"]
    )
    assert policy["train"]["lighting"] == (
        "amber_edge_boost", "right_glare_dim", "anti_diagonal_blur_contrast",
    )


def test_target_identity_training_lighting_is_deterministic_and_fresh() -> None:
    module = _builder()
    pixels = np.arange(48 * 48 * 3, dtype=np.uint8).reshape(48, 48, 3)
    source = Image.fromarray(pixels, mode="RGB")
    variants = module.TARGET_IDENTITY_TRAINING_LIGHTING["train"]

    first = [np.asarray(module._lighting(source, name)) for name in variants]
    second = [np.asarray(module._lighting(source, name)) for name in variants]

    assert all(np.array_equal(left, right) for left, right in zip(first, second, strict=True))
    assert len({_sha256(value.tobytes()) for value in first}) == len(variants)
    prior = {
        name
        for policy in (
            module.LEGACY_SPLITS, module.EXPANDED_LIGHTING, module.TRANSIT_LIGHTING,
            module.SPECIFICITY_LIGHTING, module.TARGET_AWARE_LIGHTING,
            module.PERTURBATION_LIGHTING, module.POLICY_EVALUATION_LIGHTING,
            module.HARD_NEGATIVE_LIGHTING,
        )
        for split in policy.values()
        for name in (split["lighting"] if isinstance(split, dict) else split)
    }
    assert not (set(variants) & prior)


def test_fusion_evaluation_policy_and_lighting_are_fresh() -> None:
    builder = _builder()
    renderer = _renderer()
    source = {
        "schema": "tactevra.isaac_fixed_overview_mesh_render.v10",
        "pose_groups": {
            name: list(poses)
            for name, poses in renderer.FUSION_EVALUATION_POSE_GROUPS.items()
        },
        "pose_results": [
            {"pose_id": pose_id, "pose_group": group}
            for group, pose_ids in renderer.FUSION_EVALUATION_POSE_GROUPS.items()
            for pose_id in pose_ids
        ],
    }

    schema, policy = builder._split_policy(source)
    variants = builder.FUSION_EVALUATION_LIGHTING["evaluation"]
    pixels = np.arange(48 * 48 * 3, dtype=np.uint8).reshape(48, 48, 3)
    image = Image.fromarray(pixels, mode="RGB")
    first = [np.asarray(builder._lighting(image, name)) for name in variants]
    second = [np.asarray(builder._lighting(image, name)) for name in variants]
    prior = {
        name
        for lighting in (
            builder.LEGACY_SPLITS, builder.EXPANDED_LIGHTING,
            builder.TRANSIT_LIGHTING, builder.SPECIFICITY_LIGHTING,
            builder.TARGET_AWARE_LIGHTING, builder.PERTURBATION_LIGHTING,
            builder.POLICY_EVALUATION_LIGHTING, builder.HARD_NEGATIVE_LIGHTING,
            builder.TARGET_IDENTITY_TRAINING_LIGHTING,
        )
        for split in lighting.values()
        for name in (split["lighting"] if isinstance(split, dict) else split)
    }

    assert schema == "rocell.ai_official_mesh_occlusion_data.v10"
    assert policy["train"]["poses"] == policy["development"]["poses"] == ()
    assert policy["evaluation"]["poses"] == tuple(
        renderer.FUSION_EVALUATION_POSE_GROUPS["evaluation"]
    )
    assert policy["evaluation"]["lighting"] == variants
    assert all(
        np.array_equal(left, right)
        for left, right in zip(first, second, strict=True)
    )
    assert len({_sha256(value.tobytes()) for value in first}) == len(variants)
    assert not (set(variants) & prior)


def test_target_aware_lighting_families_are_deterministic_and_distinct() -> None:
    module = _builder()
    pixels = np.arange(48 * 48 * 3, dtype=np.uint8).reshape(48, 48, 3)
    source = Image.fromarray(pixels, mode="RGB")
    variants = (
        *module.TARGET_AWARE_LIGHTING["development"],
        *module.TARGET_AWARE_LIGHTING["evaluation"],
    )

    first = [np.asarray(module._lighting(source, name)) for name in variants]
    second = [np.asarray(module._lighting(source, name)) for name in variants]

    assert all(np.array_equal(left, right) for left, right in zip(first, second, strict=True))
    assert len({_sha256(value.tobytes()) for value in first}) == len(variants)


def test_progression_video_encoder_is_deterministic(tmp_path: Path) -> None:
    pytest.importorskip("av")
    module = _builder()
    first_path = tmp_path / "first.mp4"
    second_path = tmp_path / "second.mp4"
    frames = [
        Image.new("RGB", (960, 540), color=(index * 40, 20, 80))
        for index in range(3)
    ]

    module._encode_mp4(first_path, frames)
    module._encode_mp4(second_path, frames)

    assert first_path.read_bytes() == second_path.read_bytes()
    assert first_path.stat().st_size > 0


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


def test_target_aware_crops_add_only_known_safe_region_mask(tmp_path: Path) -> None:
    module = _builder()
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    pixels = np.arange(64 * 64 * 3, dtype=np.uint8).reshape(64, 64, 3)
    image_path = image_dir / "sample.png"
    Image.fromarray(pixels, mode="RGB").save(image_path)
    row = {
        "image_path": "images/sample.png",
        "image_sha256": _sha256(image_path.read_bytes()),
        "safe_polygon_px": [[24, 26], [40, 26], [40, 38], [24, 38]],
        "decision": "abstain",
    }

    spatial, labels = module._spatial_crops(tmp_path, [row])
    first, first_labels = module._target_aware_crops(tmp_path, [row])
    second, second_labels = module._target_aware_crops(tmp_path, [row])

    assert first.shape == (1, 4, 32, 32)
    assert np.array_equal(first[:, :3], spatial)
    assert set(np.unique(first[:, 3])).issubset({0.0, 1.0})
    assert 0 < int(first[:, 3].sum()) < 32 * 32
    assert np.array_equal(first, second)
    assert np.array_equal(labels, first_labels)
    assert np.array_equal(first_labels, second_labels)


def test_target_aware_crops_translate_rgb_and_mask_together(tmp_path: Path) -> None:
    module = _builder()
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    x = np.arange(128, dtype=np.uint8)[None, :]
    pixels = np.repeat(x, 128, axis=0)
    rgb = np.stack((pixels, np.flip(pixels, axis=1), pixels), axis=2)
    image_path = image_dir / "gradient.png"
    Image.fromarray(rgb, mode="RGB").save(image_path)
    row = {
        "image_path": "images/gradient.png",
        "image_sha256": _sha256(image_path.read_bytes()),
        "safe_polygon_px": [[56, 58], [72, 58], [72, 70], [56, 70]],
        "decision": "abstain",
    }

    nominal, labels = module._target_aware_crops(tmp_path, [row])
    shifted, shifted_labels = module._target_aware_crops(tmp_path, [row], (8.0, -4.0))
    repeated, _ = module._target_aware_crops(tmp_path, [row], (8.0, -4.0))

    assert nominal.shape == shifted.shape == (1, 4, 32, 32)
    assert not np.array_equal(nominal[:, :3], shifted[:, :3])
    assert np.array_equal(nominal[:, 3], shifted[:, 3])
    assert np.array_equal(shifted, repeated)
    assert np.array_equal(labels, shifted_labels)
    assert len(module._declared_mask_offsets()) == 33
    assert len(module._training_augmentation_offsets()) == 17


def test_target_identity_descriptor_binds_identity_and_nominal_geometry(
    tmp_path: Path,
) -> None:
    module = _builder()
    image_dir = tmp_path / "images"
    image_dir.mkdir()
    image_path = image_dir / "sample.png"
    Image.new("RGB", (100, 50), (200, 200, 200)).save(image_path)
    rows = [
        {
            "device": "keyboard", "target_id": target,
            "image_path": "images/sample.png", "center_px": [50, 25],
            "safe_polygon_px": [[40, 20], [60, 20], [60, 30], [40, 30]],
        }
        for target in ("ENTER", "EQUAL")
    ]
    catalog = module._target_identity_catalog(rows)

    first = module._target_identity_descriptors(tmp_path, rows, catalog)
    second = module._target_identity_descriptors(tmp_path, rows, catalog)

    assert catalog == ("keyboard:ENTER", "keyboard:EQUAL")
    assert first.shape == (2, 6)
    assert np.array_equal(first, second)
    assert first[0, :2].tolist() == [1.0, 0.0]
    assert first[1, :2].tolist() == [0.0, 1.0]
    assert np.allclose(first[:, 2:], [[0.5, 0.5, 0.2, 0.2]] * 2)


def test_localization_policy_selects_largest_supported_development_bound() -> None:
    module = _builder()
    rows = [
        {"id": "visible"},
        {"id": "blocked"},
    ]
    labels = np.asarray([0.0, 1.0])
    probabilities = np.asarray([0.01, 0.99])
    by_offset = [
        (offset, probabilities.copy())
        for offset in module._declared_mask_offsets()
    ]

    threshold, bound, gate_met, measurements = module._select_localization_policy(
        rows, labels, by_offset,
    )

    assert threshold == 0.05
    assert bound == 4.0
    assert gate_met is True
    assert len(measurements) == 33
    assert all(
        item["metrics"]["confusion"] == {
            "true_abstain": 1,
            "true_visible": 1,
            "false_abstain": 0,
            "missed_abstain": 0,
        }
        for item in measurements
    )


def test_localization_policy_resolves_feasible_sub_centithreshold_interval() -> None:
    module = _builder()
    rows = [{"id": f"row-{index}"} for index in range(40)]
    labels = np.asarray([0.0] * 20 + [1.0] * 20)
    probabilities = np.asarray(
        [0.01] * 18 + [0.0945, 0.0945] + [0.094, 0.096] + [0.99] * 18,
        dtype=np.float64,
    )
    by_offset = [
        (offset, probabilities.copy())
        for offset in module._declared_mask_offsets()
    ]

    threshold, bound, gate_met, measurements = module._select_localization_policy(
        rows, labels, by_offset,
    )

    assert threshold == 0.095
    assert bound == 4.0
    assert gate_met is True
    assert len(measurements) == 33
    assert all(
        item["metrics"]["confusion"]["missed_abstain"] == 1
        and item["metrics"]["confusion"]["false_abstain"] == 0
        for item in measurements
    )


def test_target_aware_candidate_is_deterministic_and_has_no_robot_mask_input(
    tmp_path: Path,
) -> None:
    module = _builder()
    dataset = tmp_path / "dataset"
    image_dir = dataset / "images"
    image_dir.mkdir(parents=True)
    splits = {}
    for split_index, split in enumerate(("train", "development", "evaluation")):
        rows = []
        for index in range(8):
            expected_abstain = index % 2 == 0
            image = Image.new("RGB", (64, 64), (205, 205, 205))
            draw = ImageDraw.Draw(image)
            if expected_abstain:
                draw.rectangle((26, 20, 38, 44), fill=(20, 20, 20))
            else:
                draw.rectangle((4, 4, 14, 14), fill=(20, 20, 20))
            image_path = image_dir / f"{split}-{index}.png"
            image.save(image_path)
            rows.append({
                "id": f"{split}-{index}",
                "image_path": f"images/{image_path.name}",
                "image_sha256": _sha256(image_path.read_bytes()),
                "pose_id": f"pose-{split_index}-{index}",
                "lighting_variant": f"light-{split_index}",
                "device": "keyboard",
                "target_id": "H",
                "center_px": [32, 32],
                "safe_polygon_px": [[24, 24], [40, 24], [40, 40], [24, 40]],
                "center_occluded": expected_abstain,
                "safe_region_overlap_fraction": 0.5 if expected_abstain else 0.0,
                "decision": "abstain" if expected_abstain else "target_visible",
                "reason": "robot_occlusion" if expected_abstain else None,
                "synthetic_only": True,
            })
        payload = b"".join(module._canonical(row) + b"\n" for row in rows)
        path = dataset / f"{split}.jsonl"
        path.write_bytes(payload)
        splits[split] = {
            "path": path.name,
            "sha256": _sha256(payload),
            "count": len(rows),
            "abstain_count": 4,
            "visible_count": 4,
        }
    manifest = {
        "schema": "rocell.ai_official_mesh_occlusion_data.v5",
        "scope": "SYNTHETIC_ONLY_NO_DEPLOYMENT_QUALIFICATION",
        "splits": splits,
        "limitations": ["unit-test synthetic fixture"],
    }
    manifest["dataset_sha256"] = _sha256(module._canonical(manifest))
    (dataset / "manifest.json").write_bytes(module._canonical(manifest) + b"\n")

    first = module.train_target_aware_candidate(dataset, tmp_path / "first")
    second = module.train_target_aware_candidate(dataset, tmp_path / "second")
    checkpoint = json.loads((tmp_path / "first" / "model.json").read_text())

    assert first == second
    assert (tmp_path / "first" / "model.json").read_bytes() == (
        tmp_path / "second" / "model.json"
    ).read_bytes()
    assert checkpoint["architecture"]["input"] == [4, 32, 32]
    assert checkpoint["architecture"]["simulator_robot_mask_input"] is False
    assert checkpoint["architecture"]["parameter_count"] == 1721
    loaded_checkpoint, loaded_model = module._load_spatial_checkpoint(tmp_path / "first")
    crops, _ = module._target_aware_crops(dataset, [
        json.loads((dataset / "evaluation.jsonl").read_text().splitlines()[0])
    ])
    torch = pytest.importorskip("torch")
    with torch.no_grad():
        probability = torch.sigmoid(loaded_model(torch.from_numpy(crops))).item()
    assert loaded_checkpoint["schema"] == "rocell.ai_target_crop_safe_region_spatial.v1"
    assert loaded_model.features[0].in_channels == 4
    assert 0.0 <= probability <= 1.0
    assert first["promotion_status"] == "BLOCKED_SYNTHETIC_ONLY"
    assert first["hardware_writes"] == 0
    assert first["physical_movements"] == 0


def test_target_identity_candidate_is_deterministic_and_keeps_evaluation_closed(
    tmp_path: Path,
) -> None:
    module = _builder()

    def make_dataset(name: str, schema: str, populated_split: str) -> Path:
        dataset = tmp_path / name
        image_dir = dataset / "images"
        image_dir.mkdir(parents=True)
        rows = []
        for index in range(16):
            expected_abstain = index % 2 == 0
            target_id = "ENTER" if index % 4 < 2 else "EQUAL"
            image = Image.new("RGB", (64, 64), (205, 205, 205))
            draw = ImageDraw.Draw(image)
            if expected_abstain:
                draw.rectangle((26, 20, 38, 44), fill=(20, 20, 20))
            else:
                draw.rectangle((4, 4, 14, 14), fill=(20, 20, 20))
            image_path = image_dir / f"{populated_split}-{index}.png"
            image.save(image_path)
            rows.append({
                "id": f"{populated_split}-{index}",
                "image_path": f"images/{image_path.name}",
                "image_sha256": _sha256(image_path.read_bytes()),
                "pose_id": f"pose-{index}",
                "lighting_variant": "unit-light",
                "device": "keyboard",
                "target_id": target_id,
                "center_px": [32, 32],
                "safe_polygon_px": [[24, 24], [40, 24], [40, 40], [24, 40]],
                "center_occluded": expected_abstain,
                "safe_region_overlap_fraction": 0.5 if expected_abstain else 0.0,
                "decision": "abstain" if expected_abstain else "target_visible",
                "reason": "robot_occlusion" if expected_abstain else None,
                "synthetic_only": True,
            })
        splits = {}
        for split in ("train", "development", "evaluation"):
            split_rows = rows if split == populated_split else []
            payload = b"".join(module._canonical(row) + b"\n" for row in split_rows)
            path = dataset / f"{split}.jsonl"
            path.write_bytes(payload)
            splits[split] = {
                "path": path.name,
                "sha256": _sha256(payload),
                "count": len(split_rows),
                "abstain_count": sum(row["decision"] == "abstain" for row in split_rows),
                "visible_count": sum(
                    row["decision"] == "target_visible" for row in split_rows
                ),
            }
        manifest = {
            "schema": schema,
            "scope": "SYNTHETIC_ONLY_NO_DEPLOYMENT_QUALIFICATION",
            "target_catalog_sha256": "a" * 64,
            "splits": splits,
            "limitations": ["unit-test synthetic fixture"],
        }
        manifest["dataset_sha256"] = _sha256(module._canonical(manifest))
        (dataset / "manifest.json").write_bytes(module._canonical(manifest) + b"\n")
        return dataset

    training = make_dataset(
        "training", "rocell.ai_official_mesh_occlusion_data.v9", "train",
    )
    development = make_dataset(
        "development", "rocell.ai_official_mesh_occlusion_data.v8", "development",
    )

    first = module.train_target_identity_candidate(training, development, tmp_path / "first")
    second = module.train_target_identity_candidate(training, development, tmp_path / "second")
    checkpoint = json.loads((tmp_path / "first" / "model.json").read_text())

    assert first == second
    assert (tmp_path / "first" / "model.json").read_bytes() == (
        tmp_path / "second" / "model.json"
    ).read_bytes()
    assert checkpoint["schema"] == "rocell.ai_target_identity_geometry_spatial.v1"
    assert checkpoint["architecture"]["target_catalog"] == [
        "keyboard:ENTER", "keyboard:EQUAL",
    ]
    assert checkpoint["architecture"]["descriptor_size"] == 6
    assert checkpoint["evaluation_opened"] is False
    assert first["evaluation_group_present"] is False
    assert first["hardware_writes"] == 0
    assert first["physical_movements"] == 0
    assert first["physical_authority"] is False



def test_target_conditioned_fusion_is_deterministic_and_freezes_seed(
    tmp_path: Path,
) -> None:
    module = _builder()
    torch = pytest.importorskip("torch")

    def make_dataset(name: str, schema: str, populated_split: str) -> Path:
        dataset = tmp_path / name
        image_dir = dataset / "images"
        image_dir.mkdir(parents=True)
        rows = []
        for index in range(12):
            expected_abstain = index % 3 == 0
            target_id = "ENTER" if index % 2 == 0 else "EQUAL"
            image = Image.new("RGB", (64, 64), (205, 205, 205))
            draw = ImageDraw.Draw(image)
            if expected_abstain:
                draw.rectangle((26, 20, 38, 44), fill=(20, 20, 20))
            else:
                draw.rectangle((4, 4, 14, 14), fill=(20, 20, 20))
            image_path = image_dir / f"{populated_split}-{index}.png"
            image.save(image_path)
            rows.append({
                "id": f"{populated_split}-{index}",
                "image_path": f"images/{image_path.name}",
                "image_sha256": _sha256(image_path.read_bytes()),
                "pose_id": f"pose-{index}",
                "lighting_variant": "unit-light",
                "device": "keyboard",
                "target_id": target_id,
                "center_px": [32, 32],
                "safe_polygon_px": [[24, 24], [40, 24], [40, 40], [24, 40]],
                "center_occluded": expected_abstain,
                "safe_region_overlap_fraction": 0.5 if expected_abstain else 0.0,
                "decision": "abstain" if expected_abstain else "target_visible",
                "reason": "robot_occlusion" if expected_abstain else None,
                "synthetic_only": True,
            })
        splits = {}
        for split in ("train", "development", "evaluation"):
            split_rows = rows if split == populated_split else []
            payload = b"".join(module._canonical(row) + b"\n" for row in split_rows)
            path = dataset / f"{split}.jsonl"
            path.write_bytes(payload)
            splits[split] = {
                "path": path.name, "sha256": _sha256(payload),
                "count": len(split_rows),
                "abstain_count": sum(row["decision"] == "abstain" for row in split_rows),
                "visible_count": sum(
                    row["decision"] == "target_visible" for row in split_rows
                ),
            }
        manifest = {
            "schema": schema,
            "scope": "SYNTHETIC_ONLY_NO_DEPLOYMENT_QUALIFICATION",
            "target_catalog_sha256": "a" * 64,
            "splits": splits,
            "limitations": ["unit-test synthetic fixture"],
        }
        manifest["dataset_sha256"] = _sha256(module._canonical(manifest))
        (dataset / "manifest.json").write_bytes(module._canonical(manifest) + b"\n")
        return dataset

    seed_dir = tmp_path / "seed"
    seed_dir.mkdir()
    generator = torch.Generator().manual_seed(190)
    shapes = {
        "features.0.weight": (8, 4, 3, 3), "features.0.bias": (8,),
        "features.3.weight": (16, 8, 3, 3), "features.3.bias": (16,),
        "classifier.weight": (1, 256), "classifier.bias": (1,),
    }
    state = {
        name: {
            "shape": list(shape),
            "values": (
                torch.randn(shape, generator=generator) * 0.02
            ).reshape(-1).tolist(),
        }
        for name, shape in shapes.items()
    }
    seed_checkpoint = {
        "schema": "rocell.ai_target_crop_localization_robust_spatial.v1",
        "architecture": {"input": [4, 32, 32]},
        "threshold": 0.1,
        "localization_uncertainty_policy": {
            "maximum_supported_planar_error_mm": 1.0,
            "development_gate_met": True,
        },
        "evaluation_opened": False,
        "state_dict": state,
    }
    seed_model_path = seed_dir / "model.json"
    seed_model_path.write_bytes(module._canonical(seed_checkpoint) + b"\n")
    seed_scorecard = {
        "schema": "rocell.ai_localization_policy_refreeze.v1",
        "model_sha256": _sha256(seed_model_path.read_bytes()),
        "maximum_supported_planar_error_mm": 1.0,
        "development_gate_met": True,
        "hardware_writes": 0,
        "physical_movements": 0,
    }
    seed_scorecard["scorecard_sha256"] = _sha256(module._canonical(seed_scorecard))
    (seed_dir / "scorecard.json").write_bytes(module._canonical(seed_scorecard) + b"\n")
    training = make_dataset(
        "fusion-training", "rocell.ai_official_mesh_occlusion_data.v9", "train",
    )
    development = make_dataset(
        "fusion-development", "rocell.ai_official_mesh_occlusion_data.v8", "development",
    )

    first = module.train_target_conditioned_fusion_candidate(
        training, development, seed_dir, tmp_path / "fusion-first",
    )
    second = module.train_target_conditioned_fusion_candidate(
        training, development, seed_dir, tmp_path / "fusion-second",
    )
    checkpoint = json.loads((tmp_path / "fusion-first" / "model.json").read_text())

    assert first == second
    assert (tmp_path / "fusion-first" / "model.json").read_bytes() == (
        tmp_path / "fusion-second" / "model.json"
    ).read_bytes()
    assert checkpoint["schema"] == "rocell.ai_target_conditioned_spatial_fusion.v1"
    assert checkpoint["architecture"]["fusion"].endswith("before_spatial_pooling")
    assert checkpoint["architecture"]["frozen_visual_backbone"] is True
    assert checkpoint["architecture"]["frozen_classifier"] is True
    assert checkpoint["architecture"]["trainable_parameter_count"] == 224
    assert checkpoint["state_dict"]["conv1.weight"] == state["features.0.weight"]
    assert checkpoint["state_dict"]["conv2.weight"] == state["features.3.weight"]
    assert checkpoint["state_dict"]["classifier.weight"] == state["classifier.weight"]
    assert checkpoint["evaluation_opened"] is False
    assert first["evaluation_group_present"] is False
    assert first["hardware_writes"] == 0
    assert first["physical_movements"] == 0
    assert first["physical_authority"] is False

    evaluation = make_dataset(
        "fusion-evaluation", "rocell.ai_official_mesh_occlusion_data.v10", "evaluation",
    )
    candidate_dir = tmp_path / "fusion-first"
    checkpoint["localization_uncertainty_policy"].update({
        "maximum_supported_planar_error_mm": 1.0,
        "development_gate_met": True,
        "above_bound_decision": "abstain_localization_uncertain",
    })
    model_path = candidate_dir / "model.json"
    model_path.write_bytes(module._canonical(checkpoint) + b"\n")
    scorecard_path = candidate_dir / "scorecard.json"
    scorecard = json.loads(scorecard_path.read_text())
    scorecard.pop("scorecard_sha256")
    scorecard.update({
        "model_sha256": _sha256(model_path.read_bytes()),
        "maximum_supported_planar_error_mm": 1.0,
        "development_gate_met": True,
        "evaluation_group_present": False,
    })
    scorecard["scorecard_sha256"] = _sha256(module._canonical(scorecard))
    scorecard_path.write_bytes(module._canonical(scorecard) + b"\n")

    evaluation_first = module.evaluate_target_conditioned_fusion(
        evaluation, candidate_dir, tmp_path / "evaluation-first",
    )
    evaluation_second = module.evaluate_target_conditioned_fusion(
        evaluation, candidate_dir, tmp_path / "evaluation-second",
    )

    assert evaluation_first == evaluation_second
    assert (tmp_path / "evaluation-first" / "report.json").read_bytes() == (
        tmp_path / "evaluation-second" / "report.json"
    ).read_bytes()
    assert evaluation_first["schema"] \
        == "rocell.ai_target_conditioned_fusion_evaluation.v1"
    assert evaluation_first["evaluation_opened"] is True
    assert evaluation_first["evaluation_row_count"] == 12
    assert evaluation_first["hardware_writes"] == 0
    assert evaluation_first["physical_movements"] == 0
    assert evaluation_first["physical_authority"] is False

    manifest_path = evaluation / "manifest.json"
    tampered = json.loads(manifest_path.read_text())
    tampered["dataset_sha256"] = "0" * 64
    manifest_path.write_bytes(module._canonical(tampered) + b"\n")
    with pytest.raises(ValueError, match="manifest hash mismatch"):
        module.evaluate_target_conditioned_fusion(
            evaluation, candidate_dir, tmp_path / "tampered-evaluation",
        )
