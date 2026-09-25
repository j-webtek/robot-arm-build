#!/usr/bin/env python3
"""Synchronize bounded RC03 manual blocks with layout and measurement data.

Only content between explicit AUTO-GENERATED markers is changed after the
first migration. ``--check`` is read-only and fails if markers are missing or
their content is stale.
"""
from __future__ import annotations

import argparse
import hashlib
import json
import re
from pathlib import Path

from generate_drawings import (
    EXPECTED_REVISION,
    board_feature_rows,
    direct_tag_rows,
    direct_tag_spec,
    layout_sha256,
    load_layout,
    release_revision,
)
from generate_fiducials import build_tag_map


ROOT = Path(__file__).resolve().parents[1]
MANUAL_PATH = ROOT / "ASSEMBLY_MANUAL.md"
SYNC_RECORD_PATH = ROOT / "drawings" / "documentation_sync.json"
TAG_MAP_PATH = ROOT / "fiducials" / "apriltag_map.json"

BLOCK_NAMES = (
    "RC03_BOARD_FEATURES",
    "RC03_DIRECT_TAG_INSTALLATION",
    "RC03_RUNTIME_TAG_COORDINATES",
)


def begin_marker(name: str) -> str:
    return f"<!-- BEGIN AUTO-GENERATED: {name} -->"


def end_marker(name: str) -> str:
    return f"<!-- END AUTO-GENERATED: {name} -->"


def generated_block(name: str, content: str) -> str:
    return f"{begin_marker(name)}\n{content.rstrip()}\n{end_marker(name)}"


def _number(value: object, places: int = 2) -> str:
    if value in (None, ""):
        return "-"
    rendered = f"{float(value):.{places}f}"
    return rendered.rstrip("0").rstrip(".")


def render_board_features(layout: dict) -> str:
    rows = board_feature_rows(layout)
    lines = [
        "Coordinates are measured from the front-left corner of the **finished sealed board top**. "
        "The named rows below come directly from `config/workcell_layout.json`; do not transfer "
        "coordinates from an earlier release.",
        "",
        "| ID | Station | Feature | X mm | Y mm | Diameter mm | Depth mm | Instruction |",
        "|---|---|---|---:|---:|---:|---:|---|",
    ]
    for row in rows:
        lines.append(
            f"| {row['id']} | {row['station'] or '-'} | {row['type'].replace('_', ' ')} | "
            f"{_number(row['x'])} | {_number(row['y'])} | {_number(row['diameter'])} | "
            f"{_number(row['depth_mm'])} | {row['instruction']} |"
        )
    lines += [
        "",
        "On the 1:1 board drill guide, blue double-ring symbols are the four 6.0 mm x 15.0 mm "
        "blind locator-bore centers. Orange dashed-square symbols are the nine anchor centers only; "
        "select each final wood-bore size from the completed `FASTENER_MAP.csv`. Green and cyan "
        "AprilTag geometry is placement guidance marked NO DRILL.",
    ]
    return "\n".join(lines)


def render_direct_tag_installation(layout: dict) -> str:
    spec = direct_tag_spec(layout)
    rows = direct_tag_rows(layout)
    lines = [
        "All six AprilTags attach **directly to the fully cured, finished board**. RC02 printed tag "
        "frames and their twelve mounting holes are obsolete. Print "
        "`fiducials/apriltag36h11_ID0-5_40mm_detection_edge.pdf` at Actual Size, verify the "
        "100 mm bar and a 40.0 mm detection edge, then cut each 55.0 mm tile square.",
        "",
        "Re-register the scale-verified 1:1 board template after all drilling, proof loading, arm "
        "clamping, and final board-flatness checks. Transfer each tag center and its +Y/page-top "
        "edge witness to the finished board with a fine pencil, then remove the paper and clean the "
        "six board regions. Never adhere a tag to or through the paper template.",
        "",
        "Align job 03C2's application frame to the transferred center/edge witnesses, with "
        "`+Y / REAR` toward board rear. Confirm the actual square 55 mm tile drops into and releases "
        "from the square opening without corner contact. Apply one controlled thin layer of matte "
        "full-surface adhesive and burnish through clean release paper with a flat block. Lift the "
        "frame vertically. Reject bubbles, lifted corners, skew, gloss over the marker, or adhesive "
        "extending beyond the paper.",
        "",
        "| Name | Printed ID | Role | 55 mm tile origin X,Y mm | Detection center X,Y mm | Yaw |",
        "|---|---:|---|---:|---:|---:|",
    ]
    for row in rows:
        lines.append(
            f"| {row['name']} | {row['id']} | {row['role'].replace('_', ' ')} | "
            f"{_number(row['tile_origin_x_mm'])}, {_number(row['tile_origin_y_mm'])} | "
            f"{_number(row['detection_center_x_mm'])}, {_number(row['detection_center_y_mm'])} | "
            f"{_number(row['expected_yaw_deg'])}° |"
        )
    nominal_plane = spec["direct_tag_plane_nominal_z_mm"]
    if nominal_plane is None:
        plane_sentence = (
            "No nominal optical Z is asserted: the installed tag plane depends on the compressed "
            "tape and actual stock."
        )
    else:
        plane_sentence = f"The layout's provisional direct-tag plane is Z={nominal_plane:.3f} mm."
    lines += [
        "",
        f"{plane_sentence} Measure every installed detection center and plane relative to the "
        "finished sealed board top, then record exact X, Y, Z and yaw under "
        "`tag_plane_placement_measured`. The runtime map remains nominal and board-pose solving "
        "remains blocked until that gate is PASS. After it is PASS, run "
        "`python scripts/generate_fiducials.py --map-only` from the project root and require the "
        "summary to report `coordinate_source` as `measured_installation` and `direct_tags` as 6 "
        "before handing the map to Step 13.",
    ]
    return "\n".join(lines)


def render_runtime_tag_coordinates(layout: dict) -> str:
    tag_map = build_tag_map(layout)
    nominal_rows = direct_tag_rows(layout)
    world = [row for row in nominal_rows if row["role"] == "world"]
    centers = ", ".join(
        f"`({_number(row['detection_center_x_mm'])},{_number(row['detection_center_y_mm'])})`"
        for row in world
    )
    source = tag_map["coordinate_source"]
    measurement_status = tag_map["measurement"]["status"]
    if source == "measured_installation":
        plane_values = [
            tag_map["tags"][name]["detection_center_xyz_mm"][2]
            for name in ("T0", "T1", "T2", "T3", "K0", "P0")
        ]
        plane_note = (
            "The generated runtime map uses the measured installation. Recorded tag-plane Z values "
            f"span {_number(min(plane_values), 3)} to {_number(max(plane_values), 3)} mm."
        )
    else:
        plane_note = (
            "The generated runtime map is nominal only and contains no asserted optical Z. "
            "`detect_apriltags.py` will report camera-frame tag poses but will not solve a board "
            "transform until the placement gate passes."
        )
    return (
        "Confirm IDs 0-5, stable axes, matte flat tiles, and a configured 0.040 m detection edge. "
        f"The frozen nominal T0-T3 detection centers are {centers} mm. T0-T3 define the primary "
        "board transform; K0/P0 are held out as station-area residual checks. "
        f"Current map coordinate source: **{source}**; placement gate: **{measurement_status}**. "
        f"{plane_note}"
    )


def render_blocks(layout: dict) -> dict[str, str]:
    return {
        "RC03_BOARD_FEATURES": render_board_features(layout),
        "RC03_DIRECT_TAG_INSTALLATION": render_direct_tag_installation(layout),
        "RC03_RUNTIME_TAG_COORDINATES": render_runtime_tag_coordinates(layout),
    }


def migrate_legacy_sections(text: str, blocks: dict[str, str]) -> str:
    replacements: list[tuple[str, str, str]] = [
        (
            "RC03_BOARD_FEATURES",
            r"(?s)(## 7\.3 Hole coordinate fallback\s*\n)(.*?)(?=\n# 8\.)",
            r"\1" + generated_block("RC03_BOARD_FEATURES", blocks["RC03_BOARD_FEATURES"]) + "\n",
        ),
        (
            "RC03_DIRECT_TAG_INSTALLATION",
            r"(?s)(# 10\. Install the AprilTag frames\s*\n)(.*?)(?=\n# 11\.)",
            "# 10. Apply the direct-board AprilTags\n\n" + generated_block(
                "RC03_DIRECT_TAG_INSTALLATION", blocks["RC03_DIRECT_TAG_INSTALLATION"]
            ) + "\n",
        ),
        (
            "RC03_RUNTIME_TAG_COORDINATES",
            r"(?s)Confirm IDs 0-5 are correct, tag axes are stable,.*?(?=\n\n# 14\.)",
            generated_block(
                "RC03_RUNTIME_TAG_COORDINATES", blocks["RC03_RUNTIME_TAG_COORDINATES"]
            ),
        ),
    ]
    migrated = text
    for name, pattern, replacement in replacements:
        if begin_marker(name) in migrated:
            continue
        migrated, count = re.subn(pattern, replacement, migrated, count=1)
        if count != 1:
            raise ValueError(f"Could not locate the legacy manual section for {name}")
    return migrated


def replace_marked_block(text: str, name: str, content: str) -> str:
    pattern = re.compile(
        re.escape(begin_marker(name)) + r".*?" + re.escape(end_marker(name)),
        flags=re.DOTALL,
    )
    replacement = generated_block(name, content)
    updated, count = pattern.subn(lambda _: replacement, text)
    if count != 1:
        raise ValueError(f"Expected exactly one marked {name} block; found {count}")
    return updated


def expected_manual(text: str, blocks: dict[str, str]) -> str:
    updated = migrate_legacy_sections(text, blocks)
    for name in BLOCK_NAMES:
        updated = replace_marked_block(updated, name, blocks[name])
    return updated


def sha256_text(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


def sha256_file(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def read_json(path: Path) -> dict | None:
    if not path.exists():
        return None
    try:
        value = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    return value if isinstance(value, dict) else None


def sync_record(layout: dict, manual_text: str, tag_map: dict) -> dict:
    return {
        "schema_version": 2,
        "design_revision": release_revision(layout),
        "expected_revision": EXPECTED_REVISION,
        "layout_sha256": layout_sha256(),
        "apriltag_map_sha256": sha256_file(TAG_MAP_PATH),
        "coordinate_source": tag_map["coordinate_source"],
        "tag_measurement_gate_status": tag_map["measurement"]["status"],
        "manual_sha256": sha256_text(manual_text),
        "controlled_blocks": list(BLOCK_NAMES),
        "status": "SYNCED",
    }


def main() -> int:
    parser = argparse.ArgumentParser()
    parser.add_argument(
        "--check", action="store_true",
        help="Fail without writing if the controlled manual blocks are stale",
    )
    args = parser.parse_args()
    layout = load_layout()
    original = MANUAL_PATH.read_text(encoding="utf-8")
    blocks = render_blocks(layout)
    expected = expected_manual(original, blocks)
    expected_map = build_tag_map(layout)
    actual_map = read_json(TAG_MAP_PATH)
    map_current = actual_map == expected_map
    if args.check:
        reasons: list[str] = []
        if original != expected:
            reasons.append("manual_blocks")
        if not map_current:
            reasons.append("apriltag_map")
        expected_record = sync_record(layout, expected, expected_map) if map_current else None
        if expected_record is None or read_json(SYNC_RECORD_PATH) != expected_record:
            reasons.append("documentation_sync_record")
        if reasons:
            print(json.dumps({
                "status": "STALE",
                "manual": str(MANUAL_PATH),
                "revision": release_revision(layout),
                "controlled_blocks": list(BLOCK_NAMES),
                "stale_artifacts": reasons,
            }, indent=2))
            return 1
        print(json.dumps({
            "status": "PASS",
            "manual": str(MANUAL_PATH),
            "manual_sha256": sha256_text(original),
            "layout_sha256": layout_sha256(),
            "controlled_blocks": list(BLOCK_NAMES),
        }, indent=2))
        return 0
    if not map_current:
        print(json.dumps({
            "status": "STALE_MAP",
            "map": str(TAG_MAP_PATH),
            "layout_sha256": layout_sha256(),
            "instruction": "Run scripts/generate_fiducials.py --map-only before syncing documentation.",
        }, indent=2))
        return 1
    MANUAL_PATH.write_text(expected, encoding="utf-8")
    record = sync_record(layout, expected, expected_map)
    SYNC_RECORD_PATH.parent.mkdir(parents=True, exist_ok=True)
    SYNC_RECORD_PATH.write_text(json.dumps(record, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(record, indent=2))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
