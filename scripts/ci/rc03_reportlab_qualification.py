"""Render and qualify the bounded RC03 ReportLab drill-guide outputs."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import importlib.util
import json
import math
from pathlib import Path
import re


REPORTLAB_PACKAGE = "reportlab"
VALIDATION_REQUIREMENTS = ("pypdf>=6,<7", "pdfplumber>=0.11,<1")
MM_PT = 72.0 / 25.4
FEATURE_IDS = (
    "KBL-LOC-ROUND", "KBL-LOC-RADIAL", "KBL-HOLD-F", "KBL-HOLD-R",
    "KBL-CLAMP", "KBR-HOLD-F", "KBR-HOLD-R", "KBR-CLAMP",
    "PT-LOC-ROUND", "PT-LOC-RADIAL", "PT-HOLD-TCP", "PT-HOLD-R1",
    "PT-HOLD-R2",
)
TILE_IDS = ("A1", "A2", "A3", "B1", "B2", "B3", "C1", "C2", "C3")


def requirement_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    if match is None:
        raise ValueError(f"Invalid requirement line: {requirement!r}")
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def select_reportlab_requirement(source: Path) -> str:
    matches: list[str] = []
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if line and requirement_name(line) == REPORTLAB_PACKAGE:
            matches.append(line)
    if len(matches) != 1:
        raise ValueError(
            f"Expected one ReportLab requirement, found {len(matches)}"
        )
    return matches[0]


def write_requirements(source: Path, output: Path) -> None:
    lines = [select_reportlab_requirement(source), *VALIDATION_REQUIREMENTS]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def load_generator(source: Path):
    spec = importlib.util.spec_from_file_location("rc03_generate_drawings", source)
    if spec is None or spec.loader is None:
        raise ValueError(f"Cannot load drawing generator: {source}")
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def render(source: Path, output_dir: Path) -> tuple[Path, Path]:
    module = load_generator(source)
    output_dir.mkdir(parents=True, exist_ok=True)
    letter = output_dir / "RC03_BOARD_DRILL_GUIDE_LETTER_1TO1.pdf"
    full_size = output_dir / "RC03_BOARD_DRILL_GUIDE_24X36_FULL_SIZE_1TO1.pdf"
    module.LETTER_DRILL_GUIDE = letter
    module.FULL_SIZE_DRILL_GUIDE = full_size
    module.LEGACY_LETTER_TEMPLATE = output_dir / "legacy-letter-alias.pdf"
    layout = module.load_layout()
    module.generate_tiled_pdf(layout)
    module.generate_full_size_pdf(layout)
    return letter, full_size


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def _assert_scale_bars(page) -> None:
    target = 100.0 * MM_PT
    horizontal = [
        line for line in page.lines
        if math.isclose(abs(float(line["x1"]) - float(line["x0"])), target, abs_tol=0.02)
        and math.isclose(float(line["y1"]), float(line["y0"]), abs_tol=0.02)
    ]
    vertical = [
        line for line in page.lines
        if math.isclose(abs(float(line["y1"]) - float(line["y0"])), target, abs_tol=0.02)
        and math.isclose(float(line["x1"]), float(line["x0"]), abs_tol=0.02)
    ]
    if not horizontal or not vertical:
        raise ValueError("Rendered page lacks exact 100 mm X/Y scale-control vectors")


def validate(letter: Path, full_size: Path, source: Path) -> dict[str, object]:
    import pdfplumber
    from pypdf import PdfReader

    letter_reader = PdfReader(letter)
    if len(letter_reader.pages) != 12:
        raise ValueError(f"Letter guide has {len(letter_reader.pages)} pages, expected 12")
    for page in letter_reader.pages:
        if not math.isclose(float(page.mediabox.width), 11.0 * 72.0, abs_tol=0.001):
            raise ValueError("Letter guide page width changed")
        if not math.isclose(float(page.mediabox.height), 8.5 * 72.0, abs_tol=0.001):
            raise ValueError("Letter guide page height changed")

    cover = letter_reader.pages[0].extract_text()
    if "OVERVIEW ONLY" not in cover or "DO NOT MARK OR DRILL" not in cover:
        raise ValueError("Letter guide safety text is missing")
    schedule = letter_reader.pages[1].extract_text()
    missing_features = [feature for feature in FEATURE_IDS if feature not in schedule]
    if missing_features:
        raise ValueError(f"Letter guide schedule is missing: {', '.join(missing_features)}")

    with pdfplumber.open(letter) as pdf:
        for page_index, tile_id in enumerate(TILE_IDS, start=3):
            text = letter_reader.pages[page_index].extract_text()
            required = (
                f"DRILL TILE {tile_id} - 1:1",
                f"X SCALE - 100.0 mm - TILE {tile_id}",
                f"Y SCALE - 100.0 mm - TILE {tile_id}",
                "CENTER-PUNCH ONLY",
                "ACTUAL SIZE / 100% ONLY",
            )
            missing = [label for label in required if label not in text]
            if missing:
                raise ValueError(f"Tile {tile_id} is missing text: {', '.join(missing)}")
            _assert_scale_bars(pdf.pages[page_index])

    full_reader = PdfReader(full_size)
    if len(full_reader.pages) != 1:
        raise ValueError("Full-size guide must contain exactly one page")
    full_page = full_reader.pages[0]
    if not math.isclose(float(full_page.mediabox.width), 36.0 * 72.0, abs_tol=0.001):
        raise ValueError("Full-size guide page width changed")
    if not math.isclose(float(full_page.mediabox.height), 24.0 * 72.0, abs_tol=0.001):
        raise ValueError("Full-size guide page height changed")
    full_text = full_page.extract_text()
    for label in (
        "FULL-SIZE Board Drill Guide",
        "ANCHOR SQUARES ARE CENTER TARGETS ONLY",
        "X SCALE - 100.0 mm",
        "Y SCALE - 100.0 mm",
    ):
        if label not in full_text:
            raise ValueError(f"Full-size guide is missing text: {label}")
    with pdfplumber.open(full_size) as pdf:
        _assert_scale_bars(pdf.pages[0])

    return {
        "schema": "tactevra.rc03_reportlab_qualification.v1",
        "generator": source.as_posix(),
        "generator_sha256": sha256(source),
        "outputs": {
            "letter": {
                "path": letter.as_posix(),
                "sha256": sha256(letter),
                "bytes": letter.stat().st_size,
                "pages": 12,
            },
            "full_size": {
                "path": full_size.as_posix(),
                "sha256": sha256(full_size),
                "bytes": full_size.stat().st_size,
                "pages": 1,
            },
        },
        "resolved_versions": {
            package: importlib.metadata.version(package)
            for package in ("reportlab", "pypdf", "pdfplumber")
        },
        "checks": {
            "page_geometry": "pass",
            "required_safety_text": "pass",
            "feature_schedule": "pass",
            "tile_identity": "pass",
            "physical_100_mm_scale_vectors": "pass",
        },
        "scope": "fresh_render_and_geometric_content_validation",
        "limitations": [
            "The retained PDFs still require representative-page human visual review.",
            "This check does not qualify printing, drilling, CAD, or physical hardware.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    requirements = subparsers.add_parser("requirements")
    requirements.add_argument("--source", type=Path, required=True)
    requirements.add_argument("--output", type=Path, required=True)

    render_parser = subparsers.add_parser("render")
    render_parser.add_argument("--source", type=Path, required=True)
    render_parser.add_argument("--output-dir", type=Path, required=True)

    validate_parser = subparsers.add_parser("validate")
    validate_parser.add_argument("--source", type=Path, required=True)
    validate_parser.add_argument("--letter", type=Path, required=True)
    validate_parser.add_argument("--full-size", type=Path, required=True)
    validate_parser.add_argument("--summary", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "requirements":
        write_requirements(args.source, args.output)
        return
    if args.command == "render":
        letter, full_size = render(args.source, args.output_dir)
        print(json.dumps({"letter": str(letter), "full_size": str(full_size)}, indent=2))
        return

    summary = validate(args.letter, args.full_size, args.source)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
