"""Prepare the official RoArm-M3 surface asset for the local Blender render.

The Waveshare archive and derived STL remain under /tmp and are never added to
source control. The download is accepted only when its SHA-256 matches the pin
in dimension_manifest.json. CadQuery is used only as a STEP tessellator.
"""

from __future__ import annotations

import hashlib
import json
import urllib.request
import zipfile
from pathlib import Path

import cadquery as cq


SCRIPT = Path(__file__).resolve()
ROOT = SCRIPT.parents[2]
MANIFEST = json.loads(SCRIPT.with_name("dimension_manifest.json").read_text(encoding="utf-8"))
CONTRACT = MANIFEST["arm"]["surface_geometry"]
VENDOR_DIR = ROOT / "tmp" / "vendor" / "roarm_m3"
ARCHIVE_PATH = VENDOR_DIR / "RoArm-M3_STEP_260310.zip"
SOURCE_DIR = VENDOR_DIR / "source"
OUTPUT_PATH = ROOT / CONTRACT["presentation_mesh_path"]


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def main() -> None:
    VENDOR_DIR.mkdir(parents=True, exist_ok=True)
    if not ARCHIVE_PATH.is_file():
        print(f"Downloading pinned official arm archive to {ARCHIVE_PATH}")
        urllib.request.urlretrieve(CONTRACT["source_archive_url"], ARCHIVE_PATH)
    actual_hash = sha256(ARCHIVE_PATH)
    if actual_hash.lower() != CONTRACT["source_archive_sha256"].lower():
        raise RuntimeError(f"Official arm archive SHA-256 mismatch: {actual_hash}")

    with zipfile.ZipFile(ARCHIVE_PATH) as archive:
        member = CONTRACT["source_step_member"]
        if member not in archive.namelist():
            raise RuntimeError(f"Pinned STEP member missing from official archive: {member}")
        archive.extract(member, SOURCE_DIR)
    step_path = SOURCE_DIR / member
    shape = cq.importers.importStep(str(step_path))
    bounds = shape.val().BoundingBox()
    actual_envelope = [bounds.xlen, bounds.ylen, bounds.zlen]
    expected_envelope = CONTRACT["default_step_envelope_mm"]
    if any(abs(actual - expected) > 1e-4 for actual, expected in zip(actual_envelope, expected_envelope)):
        raise RuntimeError(f"Official arm STEP envelope drift: {actual_envelope}")

    cq.exporters.export(shape, str(OUTPUT_PATH), tolerance=0.35, angularTolerance=0.2)
    print(f"Official RoArm asset ready: {OUTPUT_PATH}")
    print(f"  archive SHA-256: {actual_hash}")
    print(f"  STEP envelope mm: {actual_envelope}")
    print(f"  solids: {len(shape.solids().vals())}")


if __name__ == "__main__":
    main()
