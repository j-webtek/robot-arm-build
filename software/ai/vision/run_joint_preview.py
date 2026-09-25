"""Synthetic pixels + trained pose model + grounded text to key coordinates."""

from __future__ import annotations

import argparse
import hashlib
from io import BytesIO
import json
import math
from pathlib import Path
import sys

import numpy as np
import torch


AI_DIR = Path(__file__).resolve().parents[1]
ROOT = AI_DIR.parents[1]
sys.path.insert(0, str(AI_DIR.parent / "src"))
sys.path.insert(0, str(AI_DIR))

from rocell_ai.coordinate_preview import preview  # noqa: E402
from rocell_ai.visual_observation import MODEL_SCHEMA  # noqa: E402
from vision.pose_model import KeyboardPoseNet  # noqa: E402
from vision.synthetic_keyboard import (  # noqa: E402
    PHOTO_STUDY_CENTER_MM, catalog_for_workspace, load_photo_texture, render, transform_target,
)


def _hash(value: dict) -> str:
    payload = json.dumps(value, sort_keys=True, separators=(",", ":"), allow_nan=False).encode()
    return hashlib.sha256(payload).hexdigest()


def run(*, request: str, checkpoint: Path, seed: int, frame_id: str, image_output: Path | None = None,
        photo_path: Path | None = None, domain: str = "standard") -> dict:
    catalog = catalog_for_workspace(ROOT)
    photo_sha256 = json.loads((AI_DIR / "data" / "real_photo_seed_v0.manifest.json").read_text())["photos"][4]["sha256"]
    texture = None if photo_path is None else load_photo_texture(photo_path, photo_sha256)
    image, truth = render(seed, catalog, domain=domain, photo_texture=texture)
    stream = BytesIO()
    image.save(stream, format="PNG")
    image_bytes = stream.getvalue()
    if image_output is not None:
        image_output.parent.mkdir(parents=True, exist_ok=True)
        image_output.write_bytes(image_bytes)
    checkpoint_bytes = checkpoint.read_bytes()
    model = KeyboardPoseNet()
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True))
    model.eval()
    pixels = np.asarray(image.resize((128, 96)), dtype=np.uint8).transpose(2, 0, 1).copy()
    with torch.no_grad():
        row = model(torch.from_numpy(pixels).unsqueeze(0).float().div_(255))[0]
    estimated_pose = (
        PHOTO_STUDY_CENTER_MM[0] + float(row[0]) * 30,
        PHOTO_STUDY_CENTER_MM[1] + float(row[1]) * 24,
        math.pi + float(row[2]) * .2,
    )
    targets = {}
    for target_id, region in sorted(catalog.keyboard_targets.items()):
        x, y = transform_target(region.center.x, region.center.y, estimated_pose[:2], estimated_pose[2])
        targets[target_id] = {"center_board_mm": [x, y, region.center.z]}
    core = {
        "schema": MODEL_SCHEMA,
        "frame_id": frame_id,
        "device": "keyboard",
        "coordinate_frame": "board",
        "coordinate_unit": "mm",
        "source": "SYNTHETIC_IMAGE_MODEL_PREDICTION",
        "target_catalog_sha256": catalog.content_sha256,
        "image_sha256": hashlib.sha256(image_bytes).hexdigest(),
        "model_sha256": hashlib.sha256(checkpoint_bytes).hexdigest(),
        "targets": targets,
    }
    visual = {**core, "observation_sha256": _hash(core)}
    result = preview(request, {"ref": frame_id, "fresh": True, "phone_state": "UNKNOWN"},
                     request_id=f"synthetic-{seed}", workspace=ROOT, visual_observation=visual)
    return {
        "schema": "rocell.ai_joint_synthetic_preview.v0",
        "seed": seed,
        "synthetic_domain": domain,
        "image_sha256": core["image_sha256"],
        "model_sha256": core["model_sha256"],
        "simulator_truth_keyboard_pose_board": [*truth],
        "predicted_keyboard_pose_board": [*estimated_pose],
        "center_error_mm": math.dist(truth[:2], estimated_pose[:2]),
        "yaw_error_deg": abs(math.degrees(truth[2] - estimated_pose[2])),
        "coordinate_preview": result,
        "physical_execution_authorized": False,
        "hardware_commands": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Synthetic image and text joint preview; no hardware access")
    parser.add_argument("--request", required=True)
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--seed", type=int, default=1_000_001)
    parser.add_argument("--frame-id", default="synthetic-camera-frame-001")
    parser.add_argument("--image-output", type=Path)
    parser.add_argument("--photo-path", type=Path)
    parser.add_argument("--domain", choices=("standard", "appearance_shift"), default="standard")
    args = parser.parse_args()
    print(json.dumps(run(request=args.request, checkpoint=args.checkpoint, seed=args.seed,
                         frame_id=args.frame_id, image_output=args.image_output,
                         photo_path=args.photo_path, domain=args.domain), indent=2))


if __name__ == "__main__":
    main()
