"""Render pinned official per-link meshes from the fixed overview in Isaac.

The probe uses the seven visual meshes bound by the upstream Xacro and places
them with the governed URDF forward kinematics.  It exports RGB, semantic link
masks, robot-only metric depth, and mask comparison against the lightweight
capsule corpus.  Visual meshes are never promoted to collision geometry.
"""

from __future__ import annotations

import argparse
from io import BytesIO
import hashlib
import json
from pathlib import Path
import subprocess
import sys
from typing import Any


UPSTREAM_COMMIT = "40dbd84b553695212fab713e8465f817ba95454d"
EXPECTED_URDF_SHA256 = "a565718e7d74b07702802cf41eb9549a6e38e50b5e80aa9b887ab1ae3d0d8190"
LINKS = ("base_link", "link1", "link2", "link3", "link4", "link5", "gripper_link")
REFERENCE_POSES = {
    "ready": None,
    "hover_t": (-0.23228866404719983, 0.63981053780154, 1.9887938075201332,
                -1.0578043436893252, 4.987262088921639e-10),
    "hover_e": (-0.31131621748840294, 0.6841707277884785, 1.8469265148292362,
                -0.9602972424740397, 4.2194931944696405e-10),
}
SCHEDULE_POSE_SEQUENCES = {
    "hover_h": 34,
    "contact_h": 35,
    "hover_1": 63,
    "contact_1": 64,
    "hover_period": 103,
    "contact_period": 104,
    "transit_outbound_08": 8,
    "transit_outbound_17": 17,
    "transit_outbound_26": 26,
    "transit_return_112": 112,
    "transit_return_120": 120,
    "transit_return_128": 128,
    "transit_h_to_1_44": 44,
    "transit_h_to_1_52": 52,
    "transit_h_to_1_60": 60,
    "transit_1_to_period_72": 72,
    "transit_1_to_period_84": 84,
    "transit_1_to_period_96": 96,
}
POSE_GROUPS = {
    "training": (
        "ready", "hover_t", "hover_e", "hover_h", "contact_h", "hover_1",
        "contact_1", "hover_period", "contact_period",
    ),
    "development": (
        "transit_outbound_08", "transit_outbound_17", "transit_outbound_26",
        "transit_return_112", "transit_return_120", "transit_return_128",
    ),
    "evaluation": (
        "transit_h_to_1_44", "transit_h_to_1_52", "transit_h_to_1_60",
        "transit_1_to_period_72", "transit_1_to_period_84",
        "transit_1_to_period_96",
    ),
}
EXPECTED_SCHEDULE_FILE_SHA256 = "6a59ce143f5527c7a9ced09b08d5515644ea4fb859dd69691e08483eb020ee42"
WIDTH = 1920
HEIGHT = 1080


def _sha256(payload: bytes) -> str:
    return hashlib.sha256(payload).hexdigest()


def _canonical(value: object) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":"),
                      ensure_ascii=True, allow_nan=False).encode("utf-8")


def _git(repo: Path, *args: str, binary: bool = False) -> bytes | str:
    result = subprocess.run(
        ["git", "-C", str(repo), *args], check=True, capture_output=True,
        text=not binary,
    )
    return result.stdout


def _load(path: Path) -> dict[str, Any]:
    value = json.loads(path.read_text(encoding="utf-8"))
    if not isinstance(value, dict):
        raise ValueError(f"{path} must contain a JSON object")
    return value


def _joint_positions(context: Any, order: tuple[str, ...], values: tuple[float, ...] | None) -> dict[str, Any]:
    from rocell.geometry import JointPosition

    if values is None:
        result = dict(context.scenario.ready_arm_joint_positions_rad)
    else:
        result = {name: JointPosition.radians(value) for name, value in zip(order[:-1], values)}
    result[order[-1]] = context.scenario.fixed_gripper_position
    return result


def _matrix_points(vertices: Any, transform: Any, np: Any) -> Any:
    rotation = np.asarray(transform.rotation.matrix, dtype=float).reshape(3, 3)
    translation = np.asarray([
        transform.translation_mm.x,
        transform.translation_mm.y,
        transform.translation_mm.z,
    ])
    return (np.asarray(vertices, dtype=float) @ rotation.T + translation) / 1000.0


def _cube(stage: Any, path: str, minimum_mm: tuple[float, float, float], maximum_mm: tuple[float, float, float], color: tuple[float, float, float], Gf: Any, UsdGeom: Any) -> None:
    cube = UsdGeom.Cube.Define(stage, path)
    cube.GetSizeAttr().Set(1.0)
    center = tuple((low + high) / 2000.0 for low, high in zip(minimum_mm, maximum_mm))
    size = tuple((high - low) / 1000.0 for low, high in zip(minimum_mm, maximum_mm))
    xform = UsdGeom.Xformable(cube)
    xform.AddTranslateOp().Set(Gf.Vec3d(*center))
    xform.AddScaleOp().Set(Gf.Vec3d(*size))
    cube.GetDisplayColorAttr().Set([Gf.Vec3f(*color)])


def _semantic_array(value: Any, np: Any) -> tuple[Any, dict[str, Any]]:
    if isinstance(value, dict) and "data" in value:
        data = np.asarray(value["data"])
        info = value.get("info", {})
    else:
        data = np.asarray(value)
        info = {}
    if data.ndim == 3 and data.shape[-1] == 1:
        data = data[..., 0]
    if data.shape != (HEIGHT, WIDTH):
        raise RuntimeError(f"unexpected semantic shape {data.shape}")
    return data.astype(np.uint32), json.loads(json.dumps(info, default=str))


def _depth_array(value: Any, np: Any) -> Any:
    data = np.asarray(value["data"] if isinstance(value, dict) and "data" in value else value)
    if data.ndim == 3 and data.shape[-1] == 1:
        data = data[..., 0]
    if data.shape != (HEIGHT, WIDTH):
        raise RuntimeError(f"unexpected depth shape {data.shape}")
    return data.astype(np.float32)


def _robot_semantic_ids(info: dict[str, Any]) -> set[int]:
    id_to_labels = info.get("idToLabels")
    if not isinstance(id_to_labels, dict):
        raise RuntimeError("semantic output omitted idToLabels")
    robot_ids = {
        int(raw_id)
        for raw_id, labels in id_to_labels.items()
        if isinstance(labels, dict) and labels.get("class") in LINKS
    }
    if not robot_ids:
        raise RuntimeError("semantic output resolved no visible robot link IDs")
    return robot_ids


def _project_targets(context: Any, Point3Mm: Any) -> list[dict[str, object]]:
    camera = context.scenario.overview.camera
    camera_T_board = context.scenario.overview.camera_T_board
    targets = [*context.targets.keyboard_targets.values(), *context.targets.phone_targets.values()]
    result = []
    for target in sorted(targets, key=lambda value: (value.device, value.target_id)):
        left, front, right, rear = target.safe_rectangle_board_mm
        polygon = []
        for x, y in ((left, rear), (right, rear), (right, front), (left, front)):
            pixel = camera.project(camera_T_board.transform_point(
                Point3Mm("board", x, y, target.center.z)
            ))
            polygon.append([pixel.u_px, pixel.v_px])
        center = camera.project(camera_T_board.transform_point(target.center))
        result.append({
            "device": target.device,
            "target_id": target.target_id,
            "center_board_mm": [target.center.x, target.center.y, target.center.z],
            "safe_rectangle_board_mm": [left, front, right, rear],
            "center_px": [center.u_px, center.v_px],
            "safe_polygon_px": polygon,
            "depth_mm": center.depth_mm,
            "in_frame": center.in_bounds,
        })
    return result


def _target_occlusion(target: dict[str, object], robot_mask: Any, Image: Any,
                      ImageDraw: Any, np: Any) -> tuple[bool, float]:
    polygon = [(round(x), round(y)) for x, y in target["safe_polygon_px"]]  # type: ignore[index]
    region = Image.new("1", (WIDTH, HEIGHT), 0)
    ImageDraw.Draw(region).polygon(polygon, fill=1)
    region_mask = np.asarray(region, dtype=bool)
    area = int(np.count_nonzero(region_mask))
    overlap = int(np.count_nonzero(region_mask & robot_mask))
    center = tuple(round(value) for value in target["center_px"])  # type: ignore[arg-type]
    center_occluded = (
        0 <= center[0] < WIDTH and 0 <= center[1] < HEIGHT
        and bool(robot_mask[center[1], center[0]])
    )
    return center_occluded, 0.0 if area == 0 else overlap / area


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--workspace", type=Path, required=True)
    parser.add_argument("--upstream-repo", type=Path, required=True)
    parser.add_argument("--mesh-receipt", type=Path, required=True)
    parser.add_argument("--capsule-manifest", type=Path, required=True)
    parser.add_argument("--schedule-bundle", type=Path, required=True)
    parser.add_argument("--output-dir", type=Path, required=True)
    parser.add_argument("--receipt", type=Path, required=True)
    parser.add_argument("--status-output", type=Path, required=True)
    args = parser.parse_args()
    args.receipt.parent.mkdir(parents=True, exist_ok=True)
    args.status_output.parent.mkdir(parents=True, exist_ok=True)
    app = None
    try:
        workspace = args.workspace.resolve(strict=True)
        upstream = args.upstream_repo.resolve(strict=True)
        mesh_receipt_path = args.mesh_receipt.resolve(strict=True)
        capsule_manifest_path = args.capsule_manifest.resolve(strict=True)
        schedule_bundle_path = args.schedule_bundle.resolve(strict=True)
        output_dir = args.output_dir.resolve()
        if output_dir.exists() and any(output_dir.iterdir()):
            raise ValueError("output directory must be empty")
        output_dir.mkdir(parents=True, exist_ok=True)

        if str(_git(upstream, "rev-parse", "HEAD")).strip() != UPSTREAM_COMMIT:
            raise ValueError("upstream checkout identity mismatch")
        mesh_receipt = _load(mesh_receipt_path)
        capsule_manifest = _load(capsule_manifest_path)
        if _sha256(schedule_bundle_path.read_bytes()) != EXPECTED_SCHEDULE_FILE_SHA256:
            raise ValueError("schedule bundle identity mismatch")
        schedule_bundle = _load(schedule_bundle_path)
        if (schedule_bundle.get("physical_authority") is not False
                or schedule_bundle.get("hardware_access") is not False
                or schedule_bundle.get("hardware_writes") != 0
                or schedule_bundle.get("physical_movements") != 0):
            raise ValueError("schedule bundle claims authority")
        if mesh_receipt["evidence_class"] != "UPSTREAM_LINK_MESH_GROUPING_ONLY":
            raise ValueError("mesh receipt has wrong evidence class")
        if capsule_manifest["schema"] != "rocell.fixed_overview_segmentation_corpus.v1":
            raise ValueError("capsule manifest schema mismatch")

        sys.path.insert(0, str(workspace / "software/src"))
        from rocell.application.arm_camera_pose import ARM_CAMERA_JOINT_ORDER
        from rocell.application.bootstrap import bootstrap_virtual_workcell
        from rocell.geometry import Point3Mm, UrdfModel

        bootstrap = bootstrap_virtual_workcell(workspace)
        context = bootstrap.context
        schedule_by_sequence = {row["sequence"]: row for row in schedule_bundle["samples"]}
        poses = dict(REFERENCE_POSES)
        for pose_id, sequence in SCHEDULE_POSE_SEQUENCES.items():
            sample = schedule_by_sequence[sequence]
            poses[pose_id] = tuple(
                sample["joint_positions_rad"][name]
                for name in ARM_CAMERA_JOINT_ORDER[:-1]
            )
        declared_pose_ids = {pose_id for group in POSE_GROUPS.values() for pose_id in group}
        if declared_pose_ids != set(poses) or sum(map(len, POSE_GROUPS.values())) != len(poses):
            raise ValueError("pose groups must partition every rendered pose exactly once")
        model_path = context.scenario.model_path
        if _sha256(model_path.read_bytes()) != EXPECTED_URDF_SHA256:
            raise ValueError("governed URDF identity mismatch")
        if mesh_receipt["home_pose_step_envelope_comparison"]["pass"] is not True:
            raise ValueError("official link-mesh envelope comparison did not pass")
        inventory = {row["link_name"]: row for row in mesh_receipt["mesh_inventory"]}
        if set(inventory) != set(LINKS):
            raise ValueError("mesh receipt link set mismatch")

        from isaacsim import SimulationApp
        app = SimulationApp({"headless": True, "multi_gpu": False})
        import carb.settings
        import numpy as np
        import omni.replicator.core as rep
        import omni.usd
        import trimesh
        from isaacsim.core.experimental.utils.semantics import add_labels
        from PIL import Image, ImageDraw
        from pxr import Gf, UsdGeom, UsdLux

        rep.orchestrator.set_capture_on_play(False)
        carb.settings.get_settings().set("rtx/post/dlss/execMode", 2)
        omni.usd.get_context().new_stage()
        stage = omni.usd.get_context().get_stage()
        UsdGeom.SetStageMetersPerUnit(stage, 1.0)
        UsdGeom.SetStageUpAxis(stage, UsdGeom.Tokens.z)
        root = UsdGeom.Xform.Define(stage, "/World").GetPrim()
        stage.SetDefaultPrim(root)

        board = context.scene.board
        _cube(stage, "/World/Board", (board.minimum.x, board.minimum.y, board.minimum.z - 4.0),
              (board.maximum.x, board.maximum.y, board.minimum.z), (0.72, 0.72, 0.72), Gf, UsdGeom)
        for name, device in sorted(context.scene.devices.items()):
            if name == "tcp_target":
                continue
            envelope = device.envelope
            _cube(stage, f"/World/Devices/{name}",
                  (envelope.minimum.x, envelope.minimum.y, envelope.minimum.z),
                  (envelope.maximum.x, envelope.maximum.y, envelope.maximum.z),
                  (0.18, 0.2, 0.24) if name == "keyboard" else (0.1, 0.11, 0.13), Gf, UsdGeom)
        all_targets = [*context.targets.keyboard_targets.values(), *context.targets.phone_targets.values()]
        for index, target in enumerate(sorted(all_targets, key=lambda item: (item.device, item.target_id))):
            left, front, right, rear = target.safe_rectangle_board_mm
            _cube(stage, f"/World/Targets/T{index:03d}", (left, front, target.center.z),
                  (right, rear, target.center.z + 0.6), (0.35, 0.38, 0.44), Gf, UsdGeom)

        model = UrdfModel.from_file(model_path)
        mesh_bytes_by_link: dict[str, bytes] = {}
        for link in LINKS:
            git_path = inventory[link]["git_path"]
            payload = _git(upstream, "show", f"{UPSTREAM_COMMIT}:{git_path}", binary=True)
            assert isinstance(payload, bytes)
            if _sha256(payload) != inventory[link]["sha256"]:
                raise ValueError(f"mesh bytes changed for {link}")
            mesh_bytes_by_link[link] = payload

        pose_prim_paths: dict[str, list[str]] = {}
        pose_joint_positions: dict[str, dict[str, float]] = {}
        for pose_id, values in poses.items():
            joints = _joint_positions(context, ARM_CAMERA_JOINT_ORDER, values)
            pose_joint_positions[pose_id] = {
                name: value.value for name, value in sorted(joints.items())
            }
            transforms = model.forward_kinematics(joints)
            paths = []
            for link_index, link in enumerate(LINKS):
                loaded = trimesh.load_mesh(BytesIO(mesh_bytes_by_link[link]), file_type="stl", process=True)
                board_T_link = context.scenario.board_T_world.compose(transforms[link])
                vertices = _matrix_points(loaded.vertices, board_T_link, np)
                path = f"/World/Robot_{pose_id}/{link}"
                usd_mesh = UsdGeom.Mesh.Define(stage, path)
                usd_mesh.CreatePointsAttr([Gf.Vec3f(*map(float, point)) for point in vertices])
                usd_mesh.CreateFaceVertexCountsAttr([3] * len(loaded.faces))
                usd_mesh.CreateFaceVertexIndicesAttr(np.asarray(loaded.faces, dtype=np.int32).reshape(-1).tolist())
                color = ((35 + link_index * 31) / 255.0, (45 + link_index * 23) / 255.0,
                         (55 + link_index * 17) / 255.0)
                usd_mesh.GetDisplayColorAttr().Set([Gf.Vec3f(*color)])
                add_labels(usd_mesh.GetPrim(), labels=[link], taxonomy="class")
                paths.append(path)
            pose_prim_paths[pose_id] = paths
            for path in paths:
                UsdGeom.Imageable(stage.GetPrimAtPath(path)).MakeInvisible()

        dome = UsdLux.DomeLight.Define(stage, "/World/Dome")
        dome.CreateIntensityAttr(900.0)
        distant = UsdLux.DistantLight.Define(stage, "/World/KeyLight")
        distant.CreateIntensityAttr(1800.0)
        distant.CreateAngleAttr(1.0)

        camera = rep.functional.create.camera(
            position=(0.305, 0.2285, 0.5),
            look_at=(0.305, 0.2285, 0.0),
            look_at_up_axis=(0.0, 1.0, 0.0),
            focal_length=24.0,
            horizontal_aperture=46.08,
            clipping_range=(0.01, 5.0),
            name="FixedOverviewCamera",
        )
        render_product = rep.create.render_product(camera, (WIDTH, HEIGHT), name="fixed_overview")
        rgb_annotator = rep.AnnotatorRegistry.get_annotator("rgb")
        semantic_annotator = rep.AnnotatorRegistry.get_annotator(
            "semantic_segmentation", init_params={"colorize": False}
        )
        depth_annotator = rep.AnnotatorRegistry.get_annotator("distance_to_image_plane")
        for annotator in (rgb_annotator, semantic_annotator, depth_annotator):
            annotator.attach(render_product)

        capsule_layers = {layer["pose_id"]: layer for layer in capsule_manifest["pose_layers"]}
        targets = _project_targets(context, Point3Mm)
        pose_results = []
        mask_hashes: set[str] = set()
        try:
            for pose_id in poses:
                for other in poses:
                    for path in pose_prim_paths[other]:
                        imageable = UsdGeom.Imageable(stage.GetPrimAtPath(path))
                        imageable.MakeVisible() if other == pose_id else imageable.MakeInvisible()
                app.update()
                app.update()
                rep.orchestrator.step(delta_time=0.0, rt_subframes=4)
                rgb = np.asarray(rgb_annotator.get_data())
                semantic, semantic_info = _semantic_array(semantic_annotator.get_data(), np)
                depth_m = _depth_array(depth_annotator.get_data(), np)
                robot_mask = np.isin(semantic, tuple(sorted(_robot_semantic_ids(semantic_info))))
                if not robot_mask.any():
                    raise RuntimeError(f"Isaac semantic mask is empty for {pose_id}")
                robot_depth_mm = np.where(robot_mask & np.isfinite(depth_m),
                                          np.clip(np.rint(depth_m * 1000.0), 1, 65535), 0).astype(np.uint16)
                label_path = output_dir / f"{pose_id}__isaac_robot_mask.png"
                depth_path = output_dir / f"{pose_id}__isaac_robot_depth_mm.png"
                rgb_path = output_dir / f"{pose_id}__isaac_rgb.jpg"
                Image.fromarray((robot_mask.astype(np.uint8) * 255), mode="L").save(label_path, "PNG")
                Image.fromarray(robot_depth_mm).save(depth_path, "PNG")
                Image.fromarray(rgb[..., :3].astype(np.uint8), mode="RGB").save(
                    rgb_path, "JPEG", quality=92, optimize=False, progressive=False, subsampling=0)

                cad_pixels = int(np.count_nonzero(robot_mask))
                comparison: dict[str, object] = {"capsule_comparison_available": False}
                if pose_id in capsule_layers:
                    capsule_path = capsule_manifest_path.parent / capsule_layers[pose_id]["robot_label_path"]
                    capsule_mask = np.asarray(Image.open(capsule_path).convert("L")) != 0
                    intersection = int(np.count_nonzero(robot_mask & capsule_mask))
                    union = int(np.count_nonzero(robot_mask | capsule_mask))
                    comparison = {
                        "capsule_comparison_available": True,
                        "capsule_pixels": int(np.count_nonzero(capsule_mask)),
                        "intersection_pixels": intersection,
                        "union_pixels": union,
                        "mask_iou": intersection / union,
                        "official_mesh_outside_capsule_pixels": int(np.count_nonzero(robot_mask & ~capsule_mask)),
                        "capsule_outside_official_mesh_pixels": int(np.count_nonzero(capsule_mask & ~robot_mask)),
                    }
                mask_hash = _sha256(label_path.read_bytes())
                mask_hashes.add(mask_hash)
                labeled_targets = []
                for target in targets:
                    center_occluded, overlap = _target_occlusion(
                        target, robot_mask, Image, ImageDraw, np
                    )
                    labeled_targets.append({
                        **target,
                        "center_occluded_by_official_mesh": center_occluded,
                        "safe_region_official_mesh_overlap_fraction": overlap,
                    })
                pose_results.append({
                    "pose_id": pose_id,
                    "pose_group": next(
                        group for group, pose_ids in POSE_GROUPS.items() if pose_id in pose_ids
                    ),
                    "joint_positions_rad": pose_joint_positions[pose_id],
                    "rgb_path": rgb_path.name,
                    "rgb_sha256": _sha256(rgb_path.read_bytes()),
                    "robot_mask_path": label_path.name,
                    "robot_mask_sha256": mask_hash,
                    "robot_depth_path": depth_path.name,
                    "robot_depth_sha256": _sha256(depth_path.read_bytes()),
                    "semantic_info": semantic_info,
                    "official_mesh_pixels": cad_pixels,
                    **comparison,
                    "robot_depth_min_mm": int(robot_depth_mm[robot_depth_mm > 0].min()),
                    "robot_depth_max_mm": int(robot_depth_mm.max()),
                    "targets": labeled_targets,
                })
            if len(mask_hashes) != len(poses):
                raise RuntimeError("official mesh semantic masks are not pose-distinct")
        finally:
            for annotator in (rgb_annotator, semantic_annotator, depth_annotator):
                annotator.detach()
            render_product.destroy()
            rep.orchestrator.wait_until_complete()

        rgb_atlas_path = output_dir / "official_mesh_rgb_atlas.jpg"
        mask_atlas_path = output_dir / "official_mesh_mask_atlas.png"
        depth_atlas_path = output_dir / "official_mesh_depth_mm_atlas.png"
        rgb_atlas = np.concatenate([
            np.asarray(Image.open(output_dir / row["rgb_path"]).convert("RGB"))
            for row in pose_results
        ], axis=0)
        mask_atlas = np.concatenate([
            np.asarray(Image.open(output_dir / row["robot_mask_path"]).convert("L"))
            for row in pose_results
        ], axis=0)
        depth_atlas = np.concatenate([
            np.asarray(Image.open(output_dir / row["robot_depth_path"]), dtype=np.uint16)
            for row in pose_results
        ], axis=0)
        Image.fromarray(rgb_atlas).save(
            rgb_atlas_path, "JPEG", quality=92, optimize=False, progressive=False, subsampling=0
        )
        Image.fromarray(mask_atlas).save(mask_atlas_path, "PNG")
        Image.fromarray(depth_atlas).save(depth_atlas_path, "PNG")
        decoded_rgb_atlas = np.asarray(Image.open(rgb_atlas_path).convert("RGB"))
        decoded_depth_atlas = np.asarray(Image.open(depth_atlas_path), dtype=np.uint16)
        for index, row in enumerate(pose_results):
            top = index * HEIGHT
            bottom = top + HEIGHT
            for field in ("rgb_path", "rgb_sha256", "robot_mask_path", "robot_mask_sha256",
                          "robot_depth_path", "robot_depth_sha256"):
                del row[field]
            row["atlas_crop_px"] = [0, top, WIDTH, bottom]
            row["rgb_crop_pixel_sha256"] = _sha256(decoded_rgb_atlas[top:bottom].tobytes())
            row["robot_mask_crop_pixel_sha256"] = _sha256(mask_atlas[top:bottom].tobytes())
            row["robot_depth_crop_pixel_sha256"] = _sha256(
                decoded_depth_atlas[top:bottom].tobytes()
            )
        for path in output_dir.iterdir():
            if path not in (rgb_atlas_path, mask_atlas_path, depth_atlas_path):
                path.unlink()

        receipt: dict[str, object] = {
            "schema": "tactevra.isaac_fixed_overview_mesh_render.v3",
            "evidence_class": "OFFICIAL_VISUAL_MESH_PERCEPTION_COMPARISON_ONLY",
            "upstream_commit": UPSTREAM_COMMIT,
            "governed_urdf_sha256": EXPECTED_URDF_SHA256,
            "mesh_receipt_file_sha256": _sha256(mesh_receipt_path.read_bytes()),
            "mesh_receipt_sha256": mesh_receipt["receipt_sha256"],
            "capsule_manifest_file_sha256": _sha256(capsule_manifest_path.read_bytes()),
            "capsule_corpus_sha256": capsule_manifest["corpus_sha256"],
            "schedule_bundle_file_sha256": EXPECTED_SCHEDULE_FILE_SHA256,
            "schedule_bundle_sha256": schedule_bundle["bundle_sha256"],
            "pose_groups": {name: list(pose_ids) for name, pose_ids in POSE_GROUPS.items()},
            "target_catalog_sha256": context.targets.content_sha256,
            "camera": {
                "resolution_px": [WIDTH, HEIGHT],
                "position_board_m": [0.305, 0.2285, 0.5],
                "look_at_board_m": [0.305, 0.2285, 0.0],
                "focal_length_mm": 24.0,
                "horizontal_aperture_mm": 46.08,
                "nominal_fx_px": 1000.0,
                "fixed_across_poses": True,
            },
            "artifact_atlases": {
                "rgb": {"path": rgb_atlas_path.name, "sha256": _sha256(rgb_atlas_path.read_bytes())},
                "robot_mask": {"path": mask_atlas_path.name, "sha256": _sha256(mask_atlas_path.read_bytes())},
                "robot_depth_mm": {"path": depth_atlas_path.name, "sha256": _sha256(depth_atlas_path.read_bytes())},
            },
            "pose_results": pose_results,
            "result_status": "PASS_WITH_BLOCKERS",
            "result_summary": {
                "minimum_mask_iou": min(
                    row["mask_iou"] for row in pose_results
                    if row["capsule_comparison_available"]
                ),
                "maximum_official_mesh_outside_capsule_pixels": max(
                    row["official_mesh_outside_capsule_pixels"] for row in pose_results
                    if row["capsule_comparison_available"]
                ),
            },
            "visual_meshes_used_for_collision": False,
            "physics_steps": 0,
            "hardware_access": False,
            "hardware_writes": 0,
            "physical_movements": 0,
            "physical_authority": False,
            "limitations": [
                "official upstream visual meshes are perception geometry only",
                "render materials and lighting are synthetic",
                "camera and robot placement are nominal and unmeasured",
                "Isaac semantic rasterization does not establish collision clearance",
                "no tool or camera-support geometry is present",
            ],
        }
        receipt["receipt_sha256"] = _sha256(_canonical(receipt))
        args.receipt.write_bytes(_canonical(receipt) + b"\n")
        args.status_output.write_text(json.dumps({
            "status": "PASS_WITH_BLOCKERS",
            "receipt_sha256": receipt["receipt_sha256"],
            "minimum_mask_iou": min(
                row["mask_iou"] for row in pose_results
                if row["capsule_comparison_available"]
            ),
            "maximum_official_mesh_outside_capsule_pixels": max(
                row["official_mesh_outside_capsule_pixels"] for row in pose_results
                if row["capsule_comparison_available"]),
            "hardware_writes": 0,
            "physical_movements": 0,
        }, sort_keys=True) + "\n", encoding="utf-8")
    except BaseException as exc:
        args.status_output.write_text(json.dumps({
            "status": "ERROR", "type": type(exc).__name__, "message": str(exc),
            "hardware_writes": 0, "physical_movements": 0,
        }, sort_keys=True) + "\n", encoding="utf-8")
        raise
    finally:
        if app is not None:
            app.close()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
