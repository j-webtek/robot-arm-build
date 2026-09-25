#!/usr/bin/env python3
"""Validate and summarize the zero-authority overhead-camera support design.

This operator-facing wrapper deliberately performs no hardware discovery and
cannot promote the design.  It exposes the same strict loader used by tests so
CAD, documentation, and simulation reviews can detect source or geometry drift
with one command.
"""

from __future__ import annotations

import argparse
import json
from pathlib import Path
import sys
from typing import Sequence


WORKSPACE = Path(__file__).resolve().parents[2]
SOURCE_ROOT = WORKSPACE / "software" / "src"


def _parser() -> argparse.ArgumentParser:
    parser = argparse.ArgumentParser(
        description="Validate the static overhead camera support candidate."
    )
    parser.add_argument(
        "--json",
        action="store_true",
        help="emit the complete canonical summary as JSON",
    )
    return parser


def main(argv: Sequence[str] | None = None) -> int:
    args = _parser().parse_args(argv)
    if str(SOURCE_ROOT) not in sys.path:
        sys.path.insert(0, str(SOURCE_ROOT))

    # Import after inserting the repository source root so this script also
    # works in a clean checkout without an editable installation.
    from rocell.workcell import (  # pylint: disable=import-outside-toplevel
        StaticCameraSupportError,
        load_static_camera_support_design,
    )

    try:
        design = load_static_camera_support_design(WORKSPACE)
    except (OSError, StaticCameraSupportError) as exc:
        print(f"STATIC_CAMERA_SUPPORT_INVALID: {exc}", file=sys.stderr)
        return 2

    metrics = design.metrics
    summary = {
        "schema": "rocell.static_camera_support_validation.v1",
        "result": "VALID_SCREENING_CANDIDATE_PHYSICAL_QUALIFICATION_OPEN",
        "design_id": design.design_id,
        "design_sha256": design.content_sha256,
        "physical_authority": False,
        "camera": {
            "model": design.camera_model,
            "sensor": design.sensor,
            "native_mode": {
                "width_px": design.native_mode[0],
                "height_px": design.native_mode[1],
                "fps": design.native_mode[2],
                "pixel_format": design.native_mode[3],
            },
        },
        "geometry_mm": {
            "board": list(design.board_size_mm),
            "required_view": list(design.required_view_mm),
            "camera_axis_xy": list(design.camera_axis_xy_mm),
            "nominal_entrance_pupil_z": design.nominal_entrance_pupil_z_mm,
            "qualification_z": list(design.qualification_adjustment_z_mm),
            "lowest_overhead_hardware_z": design.lowest_static_hardware_z_mm,
            "post_axes_xy": [list(point) for point in design.post_axis_xy_mm],
        },
        "screening_metrics": {
            "conservative_vertical_fov_deg": (
                metrics.aspect_conservative_vertical_fov_deg
            ),
            "nominal_coverage_mm": [
                metrics.nominal_coverage_width_mm,
                metrics.nominal_coverage_depth_mm,
            ],
            "minimum_height_coverage_mm": [
                metrics.minimum_height_coverage_width_mm,
                metrics.minimum_height_coverage_depth_mm,
            ],
            # The model stores total excess coverage.  Divide by two here to
            # report the intuitive centered margin on each opposing edge.
            "nominal_margin_each_edge_mm": [
                metrics.nominal_view_margin_width_mm / 2.0,
                metrics.nominal_view_margin_depth_mm / 2.0,
            ],
            "conservative_pixels_per_mm": (
                metrics.nominal_conservative_pixels_per_mm
            ),
            "pixels_across_40mm_tag": metrics.nominal_tag_width_pixels,
            "post_radial_screen_clearance_mm": (
                metrics.minimum_post_radial_clearance_mm
            ),
            "overhead_vertical_screen_clearance_mm": (
                metrics.minimum_overhead_vertical_clearance_mm
            ),
        },
        "open_blockers": list(design.open_blockers),
    }

    if args.json:
        print(json.dumps(summary, indent=2, sort_keys=True))
    else:
        coverage = summary["screening_metrics"]["nominal_coverage_mm"]
        print("STATIC_CAMERA_SUPPORT_VALID_SCREENING_ONLY")
        print(f"design: {design.design_id}")
        print(f"camera: {design.camera_model} / {design.sensor}")
        print(
            "camera axis: "
            f"B=({design.camera_axis_xy_mm[0]:.1f}, "
            f"{design.camera_axis_xy_mm[1]:.1f}, "
            f"{design.nominal_entrance_pupil_z_mm:.1f}) mm"
        )
        print(f"conservative nominal view: {coverage[0]:.2f} x {coverage[1]:.2f} mm")
        print(
            "screen clearances: "
            f"post={metrics.minimum_post_radial_clearance_mm:.2f} mm, "
            f"overhead={metrics.minimum_overhead_vertical_clearance_mm:.2f} mm"
        )
        print(f"physical authority: false; open blockers: {len(design.open_blockers)}")
    return 0


if __name__ == "__main__":
    raise SystemExit(main())

