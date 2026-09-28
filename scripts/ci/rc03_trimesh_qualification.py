"""Qualify the released RC03 STL inventory with the declared Trimesh range."""

from __future__ import annotations

import argparse
import csv
import hashlib
import importlib.metadata
import json
from pathlib import Path, PureWindowsPath
import re


RUNTIME_PACKAGES = ("trimesh", "numpy", "networkx")
ALLOWED_REFERENCE_STLS = {Path("stl/BOARD_REFERENCE_DO_NOT_PRINT.stl")}


def requirement_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    if match is None:
        raise ValueError(f"Invalid requirement line: {requirement!r}")
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def select_requirements(source: Path) -> list[str]:
    selected: dict[str, str] = {}
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        name = requirement_name(line)
        if name not in RUNTIME_PACKAGES:
            continue
        if name in selected:
            raise ValueError(f"Duplicate RC03 mesh requirement: {name}")
        selected[name] = line
    missing = [name for name in RUNTIME_PACKAGES if name not in selected]
    if missing:
        raise ValueError(f"Missing RC03 mesh requirements: {', '.join(missing)}")
    return [selected[name] for name in RUNTIME_PACKAGES]


def write_requirements(source: Path, output: Path) -> None:
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(select_requirements(source)) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def qualify(root: Path, manifest: Path) -> dict[str, object]:
    import numpy as np
    import trimesh

    rows = list(csv.DictReader(manifest.open(newline="", encoding="utf-8")))
    if not rows:
        raise ValueError("PART_VALIDATION.csv contains no released meshes")

    results: list[dict[str, object]] = []
    seen: set[Path] = set()
    for row in rows:
        relative = Path(*PureWindowsPath(row["stl"]).parts)
        mesh_path = root / relative
        if relative in seen:
            raise ValueError(f"Duplicate mesh manifest row: {relative.as_posix()}")
        seen.add(relative)
        if not mesh_path.is_file():
            raise ValueError(f"Missing released mesh: {relative.as_posix()}")

        mesh = trimesh.load_mesh(mesh_path, force="mesh")
        components = len(mesh.split(only_watertight=False))
        expected_extents = np.asarray(
            [float(row[f"extent_{axis}_mm"]) for axis in "xyz"], dtype=float
        )
        actual_extents = np.asarray(mesh.extents, dtype=float)
        if not bool(mesh.is_watertight):
            raise ValueError(f"Mesh is not watertight: {relative.as_posix()}")
        if not bool(mesh.is_winding_consistent):
            raise ValueError(f"Mesh winding is inconsistent: {relative.as_posix()}")
        if components != 1:
            raise ValueError(f"Mesh has {components} connected components: {relative.as_posix()}")
        if float(mesh.volume) <= 0:
            raise ValueError(f"Mesh has non-positive volume: {relative.as_posix()}")
        if not np.allclose(actual_extents, expected_extents, atol=0.05):
            raise ValueError(
                f"Mesh extents drifted for {relative.as_posix()}: "
                f"{actual_extents.tolist()} != {expected_extents.tolist()}"
            )
        results.append(
            {
                "part": row["part"],
                "stl": relative.as_posix(),
                "sha256": sha256(mesh_path),
                "vertices": int(len(mesh.vertices)),
                "faces": int(len(mesh.faces)),
                "extents_mm": [round(float(value), 3) for value in actual_extents],
                "volume_cm3": round(float(mesh.volume) / 1000.0, 3),
                "watertight": True,
                "winding_consistent": True,
                "connected_components": 1,
            }
        )

    tracked = {path.relative_to(root) for path in (root / "stl").glob("*.stl")}
    unlisted = sorted(path.as_posix() for path in tracked - seen - ALLOWED_REFERENCE_STLS)
    if unlisted:
        raise ValueError(f"Released STL files lack manifest rows: {', '.join(unlisted)}")

    references = []
    for relative in sorted(tracked & ALLOWED_REFERENCE_STLS):
        path = root / relative
        mesh = trimesh.load_mesh(path, force="mesh")
        if len(mesh.vertices) == 0 or len(mesh.faces) == 0:
            raise ValueError(f"Reference STL is empty: {relative.as_posix()}")
        references.append(
            {
                "stl": relative.as_posix(),
                "sha256": sha256(path),
                "vertices": int(len(mesh.vertices)),
                "faces": int(len(mesh.faces)),
                "disposition": "reference_only_do_not_print",
            }
        )

    inventory_digest = hashlib.sha256(
        "\n".join(f"{row['sha256']}  {row['stl']}" for row in results).encode("utf-8")
    ).hexdigest()
    return {
        "schema": "tactevra.rc03_trimesh_qualification.v1",
        "root": root.as_posix(),
        "manifest": manifest.as_posix(),
        "manifest_sha256": sha256(manifest),
        "inventory_sha256": inventory_digest,
        "mesh_count": len(results),
        "resolved_versions": {
            package: importlib.metadata.version(package) for package in RUNTIME_PACKAGES
        },
        "checks": {
            "manifest_covers_released_stls": "pass",
            "load_as_mesh": "pass",
            "watertight": "pass",
            "winding_consistent": "pass",
            "single_connected_component": "pass",
            "positive_volume": "pass",
            "recorded_extents_within_0_05_mm": "pass",
        },
        "meshes": results,
        "reference_meshes": references,
        "scope": "released_stl_readback_and_manifest_geometry_validation",
        "limitations": [
            "This check does not regenerate CAD or prove physical fit.",
            "Slicer behavior, print quality, and installed hardware remain separately qualified.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    requirements = subparsers.add_parser("requirements")
    requirements.add_argument("--source", type=Path, required=True)
    requirements.add_argument("--output", type=Path, required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--root", type=Path, required=True)
    validate.add_argument("--manifest", type=Path, required=True)
    validate.add_argument("--summary", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "requirements":
        write_requirements(args.source, args.output)
        return

    summary = qualify(args.root, args.manifest)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps({key: value for key, value in summary.items() if key != "meshes"}, indent=2))


if __name__ == "__main__":
    main()
