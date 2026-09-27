"""Bound generated evidence added by a single repository change.

This is a repository-operability check, not scientific validation. It keeps
large generated reports from entering source history without an explicit,
content-addressed review exception.
"""
from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path, PurePosixPath
import subprocess


ROOT = Path(__file__).resolve().parents[2]
REGISTRY = ROOT / ".github" / "evidence-retention-exceptions.json"
EVIDENCE_ROOTS = ("evidence/", "software/ai/eval/")
DATA_SUFFIXES = {".csv", ".json", ".jsonl", ".ndjson", ".npz", ".parquet", ".tsv"}

MAX_CHANGED_FILES = 25
MAX_ADDED_LINES_PER_FILE = 20_000
MAX_ADDED_LINES_TOTAL = 50_000
MAX_FILE_BYTES = 1_048_576


def is_evidence_data(path: str) -> bool:
    normalized = PurePosixPath(path.replace("\\", "/")).as_posix()
    return normalized.startswith(EVIDENCE_ROOTS) and Path(normalized).suffix.lower() in DATA_SUFFIXES


def load_exceptions(path: Path = REGISTRY) -> dict[str, dict[str, str]]:
    raw = json.loads(path.read_text(encoding="utf-8"))
    if raw.get("version") != 1 or not isinstance(raw.get("exceptions"), list):
        raise ValueError("exception registry must use version 1 and an exceptions list")
    result: dict[str, dict[str, str]] = {}
    for index, item in enumerate(raw["exceptions"]):
        required = {"path", "sha256", "issue", "rationale"}
        if not isinstance(item, dict) or set(item) != required:
            raise ValueError(f"exception {index} must contain exactly {sorted(required)}")
        if item["path"] in result:
            raise ValueError(f"duplicate exception path: {item['path']}")
        if not is_evidence_data(item["path"]):
            raise ValueError(f"exception path is outside generated evidence scope: {item['path']}")
        digest = item["sha256"].lower()
        if len(digest) != 64 or any(char not in "0123456789abcdef" for char in digest):
            raise ValueError(f"invalid SHA-256 for {item['path']}")
        if not item["issue"].startswith("https://github.com/j-webtek/tactevra/issues/"):
            raise ValueError(f"exception must link a Tactevra review issue: {item['path']}")
        if not item["rationale"].strip():
            raise ValueError(f"exception rationale is empty: {item['path']}")
        result[item["path"]] = item
    return result


def parse_numstat(output: str) -> list[tuple[int | None, int | None, str]]:
    entries = []
    for line in output.splitlines():
        if not line.strip():
            continue
        added, deleted, path = line.split("\t", 2)
        entries.append((None if added == "-" else int(added),
                        None if deleted == "-" else int(deleted), path))
    return entries


def sha256(path: Path) -> str:
    digest = hashlib.sha256()
    with path.open("rb") as stream:
        for block in iter(lambda: stream.read(1024 * 1024), b""):
            digest.update(block)
    return digest.hexdigest()


def registry_errors(root: Path, exceptions: dict[str, dict[str, str]]) -> list[str]:
    errors = []
    for path, exception in exceptions.items():
        disk_path = root / Path(path)
        if not disk_path.is_file():
            errors.append(f"evidence exception path is missing: {path}")
        elif sha256(disk_path) != exception["sha256"].lower():
            errors.append(f"stale evidence exception (digest mismatch): {path}")
    return errors


def evaluate(entries: list[tuple[int | None, int | None, str]], root: Path,
             exceptions: dict[str, dict[str, str]]) -> list[str]:
    errors = []
    counted: list[tuple[int, str]] = []
    for added, _deleted, raw_path in entries:
        path = PurePosixPath(raw_path.replace("\\", "/")).as_posix()
        if not is_evidence_data(path):
            continue
        disk_path = root / Path(path)
        if not disk_path.is_file():
            continue  # Deleting evidence reduces repository cost.
        exception = exceptions.get(path)
        if exception and sha256(disk_path) == exception["sha256"].lower():
            continue
        if exception:
            errors.append(f"stale evidence exception (digest mismatch): {path}")
        file_added = added or 0
        counted.append((file_added, path))
        if file_added > MAX_ADDED_LINES_PER_FILE:
            errors.append(
                f"evidence file adds {file_added} lines (limit {MAX_ADDED_LINES_PER_FILE}): {path}")
        size = disk_path.stat().st_size
        if size > MAX_FILE_BYTES:
            errors.append(f"evidence file is {size} bytes (limit {MAX_FILE_BYTES}): {path}")

    if len(counted) > MAX_CHANGED_FILES:
        errors.append(
            f"change touches {len(counted)} evidence data files (limit {MAX_CHANGED_FILES})")
    total_added = sum(added for added, _path in counted)
    if total_added > MAX_ADDED_LINES_TOTAL:
        errors.append(
            f"change adds {total_added} evidence lines (limit {MAX_ADDED_LINES_TOTAL})")
    return errors


def diff_entries(base: str) -> list[tuple[int | None, int | None, str]]:
    result = subprocess.run(
        ["git", "diff", "--numstat", "--no-renames", f"{base}..HEAD"],
        cwd=ROOT, check=True, text=True, capture_output=True,
    )
    return parse_numstat(result.stdout)


def main() -> None:
    base = os.environ.get("EVIDENCE_BASE", "HEAD^1")
    try:
        exceptions = load_exceptions()
        errors = registry_errors(ROOT, exceptions)
        errors.extend(evaluate(diff_entries(base), ROOT, exceptions))
    except (ValueError, OSError, subprocess.CalledProcessError) as exc:
        raise SystemExit(f"evidence-scope check could not run: {exc}") from exc
    if errors:
        message = "\n".join(f"- {error}" for error in errors)
        raise SystemExit(
            "Generated evidence exceeds the ordinary review budget:\n"
            f"{message}\n"
            "See docs/EVIDENCE_RETENTION.md for reduction and exception procedures."
        )
    print("PASS: changed generated evidence stays within the ordinary review budget")


if __name__ == "__main__":
    main()
