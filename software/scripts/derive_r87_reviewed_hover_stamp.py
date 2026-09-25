"""Print the r87 source-derived release stamp; never writes files or contacts hardware."""
from __future__ import annotations

import hashlib
import json
from pathlib import Path

from rocell.application.reviewed_hover_manifest import ghost_key_manifest, validate_manifest
from rocell.application.reviewed_hover_release_identity import (
    derive_release_identity, render_release_stamp,
)


def derive(root: Path, target: str = "configured-diagnostic-candidate-r87") -> dict:
    root = Path(root).resolve()
    staged = root / ".firmware-tools" / target / "RoArm-M3_example"
    diagnostics = root / "firmware/diagnostics"
    inputs = {
        str(path.relative_to(root)).replace("\\", "/"):
            hashlib.sha256(path.read_bytes()).hexdigest()
        for folder in (staged, diagnostics)
        for path in folder.iterdir()
        if path.suffix in (".ino", ".h", ".cpp") and
           path.name != "reviewed_hover_release_stamp.h"
    }
    recipe = validate_manifest(ghost_key_manifest())["manifest_sha256"]
    lock = hashlib.sha256((root / "firmware/toolchain.lock.json").read_bytes()).hexdigest()
    release = derive_release_identity(source_hashes=inputs,
        toolchain_lock_sha256=lock, recipe_sha256=recipe,
        build_profile="default-4mb-no-psram")
    return dict(release_sha256=release, recipe_sha256=recipe,
                source_count=len(inputs), stamp=render_release_stamp(release).decode("ascii"))


if __name__ == "__main__":
    print(json.dumps(derive(Path(__file__).resolve().parents[1])))
