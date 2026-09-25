"""Independent raw-record assessment for the fixed A_HOVER recovery recipe."""
from __future__ import annotations

from .reviewed_hover_manifest import POSES
from .reviewed_hover_record import _assess_bound_leg
from .reviewed_hover_recovery_admission import (
    recovery_manifest, validate_recovery_manifest,
)


SOURCE_POSITIONS = (2041, 2094, 2020, 2620, 2199, 2041, 2047)


def assess_recovery_leg(raw: bytes, *, boot: str, leg: int,
                        previous: dict | None = None) -> dict:
    manifest = recovery_manifest()
    return _assess_bound_leg(raw, pose_ids=manifest["pose_ids"],
        manifest_sha256=validate_recovery_manifest(manifest),
        source_goals=POSES["A_HOVER"], source_positions=SOURCE_POSITIONS,
        source_tolerance=6, boot=boot, leg=leg, previous=previous)
