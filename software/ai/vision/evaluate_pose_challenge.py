"""One fixed synthetic appearance challenge for the selected pose checkpoint."""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import random
import sys

import numpy as np
from PIL import Image, ImageDraw, ImageEnhance, ImageFilter
import torch


AI_DIR = Path(__file__).resolve().parents[1]
ROOT = AI_DIR.parents[1]
sys.path.insert(0, str(AI_DIR.parent / "src"))
sys.path.insert(0, str(AI_DIR))

from vision.pose_model import KeyboardPoseNet  # noqa: E402
from vision.synthetic_keyboard import catalog_for_workspace, load_photo_texture, render  # noqa: E402
from vision.train_pose import _metrics  # noqa: E402


CHALLENGE_START = 3_000_000
CHALLENGE_COUNT = 300


def _alter(image: Image.Image, seed: int) -> Image.Image:
    rng = random.Random(seed ^ 0x5A17)
    image = ImageEnhance.Brightness(image).enhance(rng.uniform(0.55, 1.35))
    image = ImageEnhance.Contrast(image).enhance(rng.uniform(0.65, 1.3))
    image = ImageEnhance.Color(image).enhance(rng.uniform(0.4, 1.5))
    overlay = Image.new("RGBA", image.size, (0, 0, 0, 0))
    draw = ImageDraw.Draw(overlay)
    if seed % 3 == 0:
        x = rng.randint(45, 190)
        draw.line((x, -10, x + rng.randint(-20, 20), 95), fill=(12, 18, 23, 170), width=rng.randint(3, 8))
    if seed % 4 == 0:
        y = rng.randint(30, 150)
        draw.line((20, y, 230, y - rng.randint(0, 12)), fill=(250, 250, 250, 95), width=rng.randint(2, 5))
    image = Image.alpha_composite(image.convert("RGBA"), overlay).convert("RGB")
    if seed % 5 == 0:
        image = image.filter(ImageFilter.GaussianBlur(0.8))
    return image


def evaluate(checkpoint: Path, photo_path: Path) -> dict:
    manifest = json.loads((AI_DIR / "data" / "real_photo_seed_v0.manifest.json").read_text())
    texture = load_photo_texture(photo_path, manifest["photos"][4]["sha256"])
    catalog = catalog_for_workspace(ROOT)
    model = KeyboardPoseNet()
    model.load_state_dict(torch.load(checkpoint, map_location="cpu", weights_only=True))
    model.eval()
    images, poses = [], []
    for seed in range(CHALLENGE_START, CHALLENGE_START + CHALLENGE_COUNT):
        image, pose = render(seed, catalog, photo_texture=texture)
        images.append(np.asarray(_alter(image, seed).resize((128, 96)), dtype=np.uint8).transpose(2, 0, 1))
        poses.append(pose)
    tensor = torch.from_numpy(np.stack(images)).float().div_(255)
    with torch.no_grad():
        prediction = torch.cat([model(batch) for batch in tensor.split(64)])
    return {
        "schema": "rocell.ai_synthetic_keyboard_pose_challenge.v0",
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "challenge_source_sha256": hashlib.sha256(Path(__file__).read_bytes()).hexdigest(),
        "photo_texture_sha256": manifest["photos"][4]["sha256"],
        "seed_range": [CHALLENGE_START, CHALLENGE_START + CHALLENGE_COUNT - 1],
        "case_count": CHALLENGE_COUNT,
        "metrics": _metrics(prediction, poses, catalog),
        "real_camera_evaluation": False,
        "physical_execution_authorized": False,
        "hardware_commands": 0,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Evaluate fixed synthetic pose challenge")
    parser.add_argument("--checkpoint", type=Path, required=True)
    parser.add_argument("--photo-path", type=Path, required=True)
    parser.add_argument("--output", type=Path)
    args = parser.parse_args()
    result = evaluate(args.checkpoint, args.photo_path)
    if args.output:
        args.output.write_bytes((json.dumps(result, indent=2) + "\n").encode())
    print(json.dumps(result, indent=2))


if __name__ == "__main__":
    main()
