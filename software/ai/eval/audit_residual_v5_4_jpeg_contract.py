"""Audit the frozen v5.4 JPEG contract without rendering or training."""

from __future__ import annotations

import argparse
import hashlib
import json
import math
from pathlib import Path
from typing import Any

import numpy as np
from PIL import Image


def sha256(path: Path) -> str:
    return hashlib.sha256(path.read_bytes()).hexdigest()


def canonical(value: Any) -> bytes:
    return json.dumps(value, sort_keys=True, separators=(",", ":")).encode()


def error_metrics(first: np.ndarray, second: np.ndarray) -> dict[str, float | int]:
    error = first.astype(np.int16) - second.astype(np.int16)
    mse = float(np.mean(error.astype(np.float64) ** 2))
    return {
        "mse": mse,
        "psnr_db": math.inf if mse == 0 else 10.0 * math.log10(255.0**2 / mse),
        "mean_absolute_error": float(np.mean(np.abs(error))),
        "maximum_absolute_error": int(np.max(np.abs(error))),
    }


def summary(rows: list[dict[str, float | int]]) -> dict[str, float | int | None]:
    finite_psnr = [
        float(row["psnr_db"]) for row in rows if math.isfinite(float(row["psnr_db"]))
    ]
    return {
        "count": len(rows),
        "minimum_finite_psnr_db": min(finite_psnr) if finite_psnr else None,
        "median_finite_psnr_db": float(np.median(finite_psnr)) if finite_psnr else None,
        "maximum_mean_absolute_error": max(
            float(row["mean_absolute_error"]) for row in rows
        ),
        "maximum_absolute_error": max(int(row["maximum_absolute_error"]) for row in rows),
        "zero_mse_count": sum(float(row["mse"]) == 0.0 for row in rows),
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    parser.add_argument("--source-commit", required=True)
    parser.add_argument("--fixture", type=Path, required=True)
    parser.add_argument("--v5", type=Path, required=True)
    parser.add_argument("--renderer", type=Path, required=True)
    parser.add_argument("--shard", type=Path, required=True)
    parser.add_argument("--output", type=Path, required=True)
    args = parser.parse_args()

    fixture = json.loads(args.fixture.read_text(encoding="utf-8"))
    v5 = json.loads(args.v5.read_text(encoding="utf-8"))
    renderer = args.renderer.read_text(encoding="utf-8")
    manifest_path = args.shard / "manifest.json"
    manifest = json.loads(manifest_path.read_text(encoding="utf-8"))

    if "quality: int = 92" not in renderer or "subsampling=0" not in renderer:
        raise ValueError("renderer JPEG contract no longer matches the audited implementation")
    if any("jpeg" in key.lower() for key in fixture) or any(
        "jpeg" in key.lower() for key in v5["render_contract"]
    ):
        raise ValueError("fixture now declares JPEG fields; this gap audit is obsolete")

    dark_rows = [
        row
        for row in manifest["observations"]
        if row["variant_id"] in {"dark_cable_30", "dark_cable_60"}
    ]
    second_encode: list[dict[str, float | int]] = []
    signal_mae: list[float] = []
    added_to_signal: list[float] = []
    for row in dark_rows:
        local = np.asarray(Image.open(args.shard / row["rgb_path"]).convert("RGB"))
        context = np.asarray(
            Image.open(args.shard / row["context_rgb_path"]).convert("RGB")
        )[48:144, 48:144]
        reference = np.asarray(
            Image.open(args.shard / row["reference_rgb_path"]).convert("RGB")
        )
        metrics = error_metrics(local, context)
        second_encode.append(metrics)
        signal = float(
            np.mean(np.abs(local.astype(np.int16) - reference.astype(np.int16)))
        )
        signal_mae.append(signal)
        added_to_signal.append(float(metrics["mean_absolute_error"]) / max(signal, 1e-12))

    reference_paths = {
        (row["reference_rgb_path"], row["reference_context_rgb_path"])
        for row in manifest["observations"]
    }
    reference_encode = []
    for local_path, context_path in sorted(reference_paths):
        local = np.asarray(Image.open(args.shard / local_path).convert("RGB"))
        context = np.asarray(Image.open(args.shard / context_path).convert("RGB"))[
            48:144, 48:144
        ]
        reference_encode.append(error_metrics(local, context))

    report = {
        "schema": "tactevra.residual_v5_4_jpeg_contract_audit.v1",
        "status": "PASS_AUDIT_WITH_KNOWN_LIMITATION",
        "source_commit": args.source_commit,
        "inputs": {
            "fixture_sha256": sha256(args.fixture),
            "v5_sha256": sha256(args.v5),
            "renderer_sha256": sha256(args.renderer),
            "sample_manifest_sha256": sha256(manifest_path),
            "sample_dataset_sha256": manifest["dataset_sha256"],
        },
        "encoding_contract": {
            "declared_in_frozen_fixture": False,
            "renderer_default_format": "JPEG",
            "renderer_default_quality": 92,
            "renderer_optimize": False,
            "renderer_progressive": False,
            "renderer_chroma_subsampling": 0,
            "current_training_development_consistency": "SAME_RENDERER_IMPLEMENTATION",
            "evaluation_consistency": "MUST_BIND_THIS_RENDERER_OR_FREEZE_AN_EXPLICIT_PRE_RENDER_AMENDMENT",
            "runtime_camera_format": "YUY2_4_2_2_UNCOMPRESSED",
        },
        "sample": {
            "shard": args.shard.name,
            "dark_cable_rows": len(dark_rows),
            "reference_pairs": len(reference_paths),
            "dark_cable_second_encode": summary(second_encode),
            "dark_cable_reference_to_observation_signal_mae": {
                "minimum": min(signal_mae),
                "median": float(np.median(signal_mae)),
            },
            "second_encode_to_signal_ratio": {
                "median": float(np.median(added_to_signal)),
                "maximum": max(added_to_signal),
            },
            "aligned_reference_encode_comparison": summary(reference_encode),
        },
        "result": {
            "extra_local_reencode_material_at_sample_scale": False,
            "raw_to_first_jpeg_loss_measured": False,
            "lossless_same_scene_comparison": "BLOCKED_RAW_RGB_NOT_RETAINED",
            "training_authorized_by_this_audit": False,
            "physical_or_deployment_qualification": False,
        },
        "limitations": [
            "The sample measures the additional local JPEG encode, not loss from the original raw Isaac RGB to the first JPEG.",
            "The frozen fixture does not declare codec, quality, or chroma-subsampling semantics.",
            "JPEG 4:4:4 synthetic inputs do not reproduce the commissioned camera's YUY2 4:2:2 signal path.",
            "A separate deterministic same-scene lossless rerender is required after the active campaign and before training.",
            "No evaluation pixels were rendered or opened.",
        ],
        "hardware_writes": 0,
        "physical_movements": 0,
        "physical_authority": False,
        "evaluation_images_opened": 0,
    }
    report["report_sha256"] = hashlib.sha256(canonical(report)).hexdigest()
    args.output.parent.mkdir(parents=True, exist_ok=True)
    args.output.write_bytes(canonical(report) + b"\n")


if __name__ == "__main__":
    main()
