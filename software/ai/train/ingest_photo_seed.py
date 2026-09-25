"""Inventory user-supplied JPEGs as an ignored real-photo vision seed.

Copies original bytes for local analysis and writes a reproducible, metadata-
minimal manifest. It performs no calibration, annotation, or model training.
"""

from __future__ import annotations

import argparse
import hashlib
import json
from pathlib import Path
import re
import shutil

from PIL import Image


AI_DIR = Path(__file__).resolve().parents[1]
DEFAULT_DESTINATION = AI_DIR / "data" / "raw" / "real_photo_seed_v0"


def ingest(source: Path, destination: Path) -> dict:
    source = source.resolve(strict=True)
    destination = destination.resolve()
    if source == destination or destination.is_relative_to(source):
        raise ValueError("destination must be separate from source")
    files = sorted(source.glob("*-Photo-*.jpg"), key=lambda path: int(path.name.split("-")[0]))
    if len(files) != 10 or [int(path.name.split("-")[0]) for path in files] != list(range(1, 11)):
        raise ValueError("expected exactly Photo 1 through Photo 10")
    destination.mkdir(parents=True, exist_ok=True)
    records = []
    for index, path in enumerate(files, start=1):
        if not path.is_file() or not re.fullmatch(fr"{index}-Photo-{index}\.jpg", path.name):
            raise ValueError("unexpected photo filename")
        payload = path.read_bytes()
        if len(payload) > 20_000_000:
            raise ValueError("photo exceeds 20 MB")
        with Image.open(path) as image:
            if image.format != "JPEG":
                raise ValueError("photo is not a JPEG")
            width, height = image.size
            if width * height > 20_000_000:
                raise ValueError("photo resolution exceeds bound")
        output_name = f"photo_{index:02d}.jpg"
        target = destination / output_name
        if target.exists() and target.read_bytes() != payload:
            raise ValueError(f"existing {output_name} has different bytes")
        if not target.exists():
            shutil.copyfile(path, target)
        records.append({
            "id": f"photo_{index:02d}",
            "file": output_name,
            "sha256": hashlib.sha256(payload).hexdigest(),
            "bytes": len(payload),
            "width_px": width,
            "height_px": height,
        })
    return {
        "schema": "rocell.ai_real_photo_seed_manifest.v0",
        "capture_group": "user_supplied_handheld_keyboard_setup_2026_09_25",
        "storage": "ignored_local_raw_photos_original_bytes",
        "exif_retained_locally": True,
        "human_reviewed": False,
        "physical_calibration": False,
        "photos": records,
    }


def main() -> None:
    parser = argparse.ArgumentParser(description="Inventory ten real setup photos without publishing raw captures")
    parser.add_argument("--source", type=Path, required=True)
    parser.add_argument("--destination", type=Path, default=DEFAULT_DESTINATION)
    parser.add_argument("--manifest", type=Path, default=AI_DIR / "data" / "real_photo_seed_v0.manifest.json")
    args = parser.parse_args()
    manifest = ingest(args.source, args.destination)
    args.manifest.parent.mkdir(parents=True, exist_ok=True)
    args.manifest.write_bytes((json.dumps(manifest, indent=2) + "\n").encode("utf-8"))
    print(f"Inventoried {len(manifest['photos'])} photos in {args.destination}")


if __name__ == "__main__":
    main()
