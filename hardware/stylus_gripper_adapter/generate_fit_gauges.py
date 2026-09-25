"""Generate open-sided stylus barrel gauges in mm, with no hidden allowance."""
from pathlib import Path
import hashlib
import json

import cadquery as cq
from cadquery import exporters
import numpy as np
import trimesh
import matplotlib
matplotlib.use("Agg")
import matplotlib.pyplot as plt
from matplotlib.collections import PolyCollection

ROOT = Path(__file__).resolve().parent
OUT = ROOT / "fit_gauges"
THICKNESS = 4.0
DEPTH = 36.0
WEB = 3.0
SLOT_CENTER_Y = 12.0
GROUPS = {"A": [8.0 + i * 0.25 for i in range(9)],
          "B": [10.25 + i * 0.25 for i in range(8)]}


def box(x, y, z, origin):
    return cq.Workplane("XY").box(x, y, z, centered=False).translate(origin)


def engrave(part, label, x, y, size):
    letters = (cq.Workplane("XY").workplane(offset=THICKNESS - 0.6)
               .center(x, y).text(label, size, 0.7, kind="bold", combine=False))
    return part.cut(letters)


def build(group, widths):
    length = sum(widths) + WEB * (len(widths) + 1)
    part = box(length, DEPTH, THICKNESS, (0, 0, 0))
    cursor = WEB
    slots = []
    for width in widths:
        center_x = cursor + width / 2
        # Open mouth and round end: constant width through the straight throat.
        cutter = box(width, SLOT_CENTER_Y + 1, THICKNESS + 2,
                     (cursor, -1, -1))
        rounded_end = (cq.Workplane("XY").center(center_x, SLOT_CENTER_Y)
                       .circle(width / 2).extrude(THICKNESS + 2)
                       .translate((0, 0, -1)))
        part = part.cut(cutter.union(rounded_end))
        part = engrave(part, f"{width:.2f}", center_x, 23, 2.8)
        slots.append({"nominal_gap_mm": width, "center_x_mm": center_x})
        cursor += width + WEB
    part = engrave(part, f"{group}  BARREL GAP mm", length / 2, 31, 3.0)
    if not part.val().isValid() or len(part.solids().vals()) != 1:
        raise ValueError("Gauge must be one valid solid")
    # Check the real solid, including labels, at each intended measuring throat.
    for slot in slots:
        x, gap = slot["center_x_mm"], slot["nominal_gap_mm"]
        empty = box(gap - 0.04, 6, 2, (x - gap / 2 + 0.02, 3, 1))
        if part.intersect(empty).val().Volume() > 1e-6:
            raise ValueError("Nominal throat obstructed")
        for side in (-1, 1):
            wall = box(0.2, 6, 2, (x + side * (gap / 2 + 0.2) - 0.1, 3, 1))
            if part.intersect(wall).val().Volume() < 2.39:
                raise ValueError("Measuring wall missing")
    return part, {"group": group, "nominal_size_mm": [length, DEPTH, THICKNESS],
                  "slots": slots}


def main():
    OUT.mkdir(parents=True, exist_ok=True)
    report = {"units": "mm", "revision": "barrel-gauge-v1",
              "purpose": "Barrel fitting coupons only; not a stylus holder",
              "hidden_clearance_mm": 0,
              "product_asin": "B08Q7L85X2", "parts": []}
    fig, axes = plt.subplots(2, 1, figsize=(12, 8))
    for ax, (group, widths) in zip(axes, GROUPS.items()):
        part, details = build(group, widths)
        name = f"barrel_gap_gauge_{group}"
        step, stl = OUT / f"{name}.step", OUT / f"{name}.stl"
        exporters.export(part, str(step))
        exporters.export(part, str(stl), tolerance=0.03, angularTolerance=0.1)
        mesh = trimesh.load_mesh(stl, process=True)
        if not mesh.is_watertight or not mesh.is_volume or len(mesh.split()) != 1:
            raise ValueError("STL must be one closed solid")
        if not np.allclose(mesh.extents, details["nominal_size_mm"], atol=0.002):
            raise ValueError("STL scale differs")
        # Independently inspect STEP reimport, not only the in-memory solid.
        imported = cq.importers.importStep(str(step))
        if not imported.val().isValid() or len(imported.solids().vals()) != 1:
            raise ValueError("STEP reimport failed")
        details.update(stl_watertight=True, stl_single_solid=True,
                       step_reimport_valid=True, throat_checks_passed=True,
                       volume_mm3=float(mesh.volume), files={})
        for file in (step, stl):
            details["files"][file.name] = hashlib.sha256(file.read_bytes()).hexdigest()
        report["parts"].append(details)
        # Top projection of the actual STL: engraved floors are darker.
        triangles = mesh.triangles
        levels = triangles[:, :, 2].mean(axis=1)
        order = np.argsort(levels)
        colors = ["#207e99" if level > 3.95 else "#153642" for level in levels[order]]
        ax.add_collection(PolyCollection(triangles[order, :, :2], facecolors=colors,
                                         edgecolors="none", antialiaseds=False))
        ax.set_xlim(-2, details["nominal_size_mm"][0] + 2)
        ax.set_ylim(-2, DEPTH + 2)
        ax.set_aspect("equal")
        ax.set_title(f"Gauge {group}: {widths[0]:.2f}–{widths[-1]:.2f} mm, 0.25 mm steps")
        ax.set_xlabel("mm — slot mouths open at bottom")
        ax.set_ylabel("mm")
    fig.suptitle("OASO barrel fitting gauges — top view of exported STL meshes")
    fig.tight_layout()
    fig.savefig(OUT / "gauge_preview.png", dpi=160)
    plt.close(fig)
    (OUT / "verification.json").write_text(json.dumps(report, indent=2) + "\n")
    print(json.dumps(report, indent=2), flush=True)


if __name__ == "__main__":
    main()
