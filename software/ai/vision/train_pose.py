"""Train and score a keyboard-pose CNN on rendered images only."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
import random
import sys

import numpy as np
import torch
from torch import nn
from torch.utils.data import DataLoader, TensorDataset


AI_DIR = Path(__file__).resolve().parents[1]
ROOT = AI_DIR.parents[1]
sys.path.insert(0, str(AI_DIR.parent / "src"))
sys.path.insert(0, str(AI_DIR))

from vision.pose_model import KeyboardPoseNet  # noqa: E402
from vision.synthetic_keyboard import (  # noqa: E402
    PHOTO_STUDY_CENTER_MM,
    catalog_for_workspace, load_photo_texture, render, transform_target,
)


def _samples(seeds: range, catalog, *, domain: str = "standard", photo_texture=None) -> tuple[torch.Tensor, torch.Tensor, list[tuple[float, float, float]]]:
    images, labels, poses = [], [], []
    for seed in seeds:
        selected_domain = ("appearance_shift" if seed % 2 else "standard") if domain == "mixed" else domain
        image, pose = render(seed, catalog, domain=selected_domain, photo_texture=photo_texture)
        images.append(np.asarray(image.resize((128, 96)), dtype=np.uint8).transpose(2, 0, 1))
        labels.append(((pose[0] - PHOTO_STUDY_CENTER_MM[0]) / 30.0,
                       (pose[1] - PHOTO_STUDY_CENTER_MM[1]) / 24.0,
                       (pose[2] - math.pi) / 0.2))
        poses.append(pose)
    return (torch.from_numpy(np.stack(images)).float().div_(255),
            torch.tensor(labels, dtype=torch.float32), poses)


def _pose_from_prediction(row: torch.Tensor) -> tuple[float, float, float]:
    return (PHOTO_STUDY_CENTER_MM[0] + float(row[0]) * 30,
            PHOTO_STUDY_CENTER_MM[1] + float(row[1]) * 24,
            math.pi + float(row[2]) * 0.2)


def _percentile(values: list[float], percentile: float) -> float:
    return round(float(np.percentile(values, percentile)), 3)


def _metrics(prediction: torch.Tensor, poses: list[tuple[float, float, float]], catalog) -> dict:
    center_errors, yaw_errors, target_errors = [], [], []
    target_ids = ("1", "A", "B", "PERIOD", "SPACE")
    for row, true_pose in zip(prediction, poses):
        predicted_pose = _pose_from_prediction(row)
        center_errors.append(math.dist(predicted_pose[:2], true_pose[:2]))
        yaw_errors.append(abs(math.degrees(predicted_pose[2] - true_pose[2])))
        for target_id in target_ids:
            target = catalog.resolve("keyboard", target_id)
            actual = transform_target(target.center.x, target.center.y, true_pose[:2], true_pose[2])
            estimated = transform_target(target.center.x, target.center.y, predicted_pose[:2], predicted_pose[2])
            target_errors.append(math.dist(actual, estimated))
    return {
        "center_error_mm_mean": round(float(np.mean(center_errors)), 3),
        "center_error_mm_p95": _percentile(center_errors, 95),
        "yaw_error_deg_mean": round(float(np.mean(yaw_errors)), 3),
        "yaw_error_deg_p95": _percentile(yaw_errors, 95),
        "selected_key_error_mm_mean": round(float(np.mean(target_errors)), 3),
        "selected_key_error_mm_p95": _percentile(target_errors, 95),
    }


def train(*, output: Path, train_count: int, validation_count: int, epochs: int, seed: int,
          photo_path: Path | None = None, train_domain: str = "standard") -> dict:
    if output.exists():
        raise ValueError("output directory exists; use a new run directory")
    if not (100 <= train_count <= 10000 and 50 <= validation_count <= 3000 and 1 <= epochs <= 100):
        raise ValueError("training counts or epochs outside bounds")
    if train_domain not in {"standard", "mixed"}:
        raise ValueError("training domain must be standard or mixed")
    torch.manual_seed(seed)
    random.seed(seed)
    np.random.seed(seed)
    torch.set_num_threads(4)
    catalog = catalog_for_workspace(ROOT)
    photo_sha256 = json.loads((AI_DIR / "data" / "real_photo_seed_v0.manifest.json").read_text())["photos"][4]["sha256"]
    texture = None if photo_path is None else load_photo_texture(photo_path, photo_sha256)
    train_images, train_labels, _ = _samples(range(0, train_count), catalog,
                                             domain=train_domain, photo_texture=texture)
    validation_images, validation_labels, validation_poses = _samples(
        range(1_000_000, 1_000_000 + validation_count), catalog, photo_texture=texture
    )
    device = torch.device("cuda" if torch.cuda.is_available() else "cpu")
    model = KeyboardPoseNet().to(device)
    optimizer = torch.optim.AdamW(model.parameters(), lr=0.001, weight_decay=0.0001)
    loader = DataLoader(TensorDataset(train_images, train_labels), batch_size=64,
                        shuffle=True, generator=torch.Generator().manual_seed(seed))
    history = []
    for epoch in range(epochs):
        model.train()
        total = 0.0
        for images, labels in loader:
            images, labels = images.to(device), labels.to(device)
            prediction = model(images)
            loss = nn.functional.mse_loss(prediction, labels)
            optimizer.zero_grad(set_to_none=True)
            loss.backward()
            optimizer.step()
            total += float(loss) * len(images)
        model.eval()
        with torch.no_grad():
            prediction = torch.cat([
                model(batch.to(device)).cpu() for batch in validation_images.split(64)
            ])
            validation_loss = float(nn.functional.mse_loss(prediction, validation_labels))
        history.append({"epoch": epoch + 1, "train_mse": round(total / train_count, 6),
                        "validation_mse": round(validation_loss, 6)})
        print(f"epoch {epoch + 1}/{epochs}: train={history[-1]['train_mse']:.5f} valid={validation_loss:.5f}", flush=True)
    shifted_images, _, shifted_poses = _samples(
        range(2_000_000, 2_000_000 + validation_count), catalog,
        domain="appearance_shift", photo_texture=texture
    )
    with torch.no_grad():
        shifted_prediction = torch.cat([model(batch.to(device)).cpu() for batch in shifted_images.split(64)])
    output.mkdir(parents=True)
    checkpoint = output / "pose_model.pt"
    torch.save(model.cpu().state_dict(), checkpoint)
    result = {
        "schema": "rocell.ai_synthetic_keyboard_pose_result.v0",
        "training_source": "procedurally_rendered_images_with_nominal_key_geometry",
        "photo_use": "one_agent_rectified_photo_05_crop_mixed_with_procedural_keyboard" if texture is not None else "appearance_cues_and_repo_photo_estimate_as_broad_priors_only",
        "photo_texture_sha256": photo_sha256 if texture is not None else None,
        "model": "KeyboardPoseNet",
        "device": str(device),
        "seed": seed,
        "train_domain": train_domain,
        "train_count": train_count,
        "validation_count": validation_count,
        "validation_seed_range": [1_000_000, 1_000_000 + validation_count - 1],
        "epochs": epochs,
        "target_catalog_sha256": catalog.content_sha256,
        "renderer_sha256": hashlib.sha256((AI_DIR / "vision" / "synthetic_keyboard.py").read_bytes()).hexdigest(),
        "model_source_sha256": hashlib.sha256((AI_DIR / "vision" / "pose_model.py").read_bytes()).hexdigest(),
        "photo_study_config_sha256": hashlib.sha256((ROOT / "software" / "config" / "photo_keyboard_registration_20260925.json").read_bytes()).hexdigest(),
        "new_photo_10_sha256": json.loads((AI_DIR / "data" / "real_photo_seed_v0.manifest.json").read_text())["photos"][9]["sha256"],
        "checkpoint_sha256": hashlib.sha256(checkpoint.read_bytes()).hexdigest(),
        "history": history,
        "validation": _metrics(prediction, validation_poses, catalog),
        "appearance_shift_validation": _metrics(shifted_prediction, shifted_poses, catalog),
        "evaluated_on_real_photos": False,
        "physical_execution_authorized": False,
        "hardware_commands": 0,
    }
    (output / "result.json").write_bytes((json.dumps(result, indent=2) + "\n").encode())
    return result


def main() -> None:
    parser = argparse.ArgumentParser(description="Train synthetic keyboard-pose vision model offline")
    parser.add_argument("--output", type=Path, required=True)
    parser.add_argument("--train-count", type=int, default=1800)
    parser.add_argument("--validation-count", type=int, default=300)
    parser.add_argument("--epochs", type=int, default=16)
    parser.add_argument("--seed", type=int, default=260925)
    parser.add_argument("--photo-path", type=Path, help="Ignored local photo_05.jpg matching the seed manifest")
    parser.add_argument("--train-domain", choices=("standard", "mixed"), default="standard")
    args = parser.parse_args()
    result = train(output=args.output, train_count=args.train_count,
                   validation_count=args.validation_count, epochs=args.epochs, seed=args.seed,
                   photo_path=args.photo_path, train_domain=args.train_domain)
    print(json.dumps(result["validation"], indent=2))


if __name__ == "__main__":
    main()
