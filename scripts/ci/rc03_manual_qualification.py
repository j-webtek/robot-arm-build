"""Prepare and validate the bounded RC03 assembly-manual CI render."""

from __future__ import annotations

import argparse
import hashlib
import importlib.metadata
import json
from pathlib import Path
import re


REQUIRED_RUNTIME_PACKAGES = ("mistune", "beautifulsoup4", "weasyprint")
VALIDATION_REQUIREMENT = "pypdf>=6,<7"
MINIMUM_PDF_BYTES = 100_000
MINIMUM_PAGE_COUNT = 20


def requirement_name(requirement: str) -> str:
    match = re.match(r"\s*([A-Za-z0-9_.-]+)", requirement)
    if match is None:
        raise ValueError(f"Invalid requirement line: {requirement!r}")
    return re.sub(r"[-_.]+", "-", match.group(1)).lower()


def select_requirements(source: Path) -> list[str]:
    selected: dict[str, str] = {}
    wanted = {requirement_name(name): name for name in REQUIRED_RUNTIME_PACKAGES}
    for raw_line in source.read_text(encoding="utf-8").splitlines():
        line = raw_line.split("#", 1)[0].strip()
        if not line:
            continue
        name = requirement_name(line)
        if name not in wanted:
            continue
        if name in selected:
            raise ValueError(f"Duplicate RC03 manual requirement: {wanted[name]}")
        selected[name] = line
    missing = [name for name in wanted if name not in selected]
    if missing:
        raise ValueError(f"Missing RC03 manual requirements: {', '.join(missing)}")
    return [selected[requirement_name(name)] for name in REQUIRED_RUNTIME_PACKAGES]


def write_requirements(source: Path, output: Path) -> None:
    lines = [*select_requirements(source), VALIDATION_REQUIREMENT]
    output.parent.mkdir(parents=True, exist_ok=True)
    output.write_text("\n".join(lines) + "\n", encoding="utf-8")


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for chunk in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(chunk)
    return digest.hexdigest()


def validate_pdf(pdf: Path, source: Path) -> dict[str, object]:
    from pypdf import PdfReader

    data = pdf.read_bytes()
    if len(data) < MINIMUM_PDF_BYTES:
        raise ValueError(
            f"Rendered PDF is unexpectedly small: {len(data)} < {MINIMUM_PDF_BYTES} bytes"
        )
    if not data.startswith(b"%PDF-") or b"%%EOF" not in data[-2048:]:
        raise ValueError("Rendered output lacks a valid PDF header or terminal marker")

    reader = PdfReader(pdf)
    page_count = len(reader.pages)
    if page_count < MINIMUM_PAGE_COUNT:
        raise ValueError(
            f"Rendered PDF has too few pages: {page_count} < {MINIMUM_PAGE_COUNT}"
        )
    for index, page in enumerate(reader.pages):
        box = page.mediabox
        if float(box.width) <= 0 or float(box.height) <= 0:
            raise ValueError(f"Rendered PDF page {index + 1} has invalid dimensions")

    versions = {
        package: importlib.metadata.version(package)
        for package in (*REQUIRED_RUNTIME_PACKAGES, "pypdf")
    }
    return {
        "schema": "tactevra.rc03_manual_qualification.v1",
        "source": source.as_posix(),
        "source_sha256": sha256(source),
        "pdf": pdf.as_posix(),
        "pdf_sha256": sha256(pdf),
        "pdf_bytes": len(data),
        "page_count": page_count,
        "resolved_versions": versions,
        "scope": "render_and_structural_validation_only",
        "limitations": [
            "Representative pages still require human visual review.",
            "This check does not qualify CAD, hardware, firmware, or physical operation.",
        ],
    }


def main() -> None:
    parser = argparse.ArgumentParser()
    subparsers = parser.add_subparsers(dest="command", required=True)

    requirements = subparsers.add_parser("requirements")
    requirements.add_argument("--source", type=Path, required=True)
    requirements.add_argument("--output", type=Path, required=True)

    validate = subparsers.add_parser("validate")
    validate.add_argument("--pdf", type=Path, required=True)
    validate.add_argument("--source", type=Path, required=True)
    validate.add_argument("--summary", type=Path, required=True)

    args = parser.parse_args()
    if args.command == "requirements":
        write_requirements(args.source, args.output)
        return

    summary = validate_pdf(args.pdf, args.source)
    args.summary.parent.mkdir(parents=True, exist_ok=True)
    args.summary.write_text(json.dumps(summary, indent=2) + "\n", encoding="utf-8")
    print(json.dumps(summary, indent=2))


if __name__ == "__main__":
    main()
