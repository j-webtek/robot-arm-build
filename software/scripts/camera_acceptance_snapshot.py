"""File-only camera acceptance snapshots; never a hardware/UI action.

The developer may keep editing the shared checkout. Acceptance runs import from
one separately copied input tree, with no prior runs, virtualenv or cached build
of the Python package. Source-before, copied bytes and source-after must agree.
This is reproducibility bookkeeping, not a physical qualification or a sandbox.
"""

from __future__ import annotations

import argparse
from datetime import datetime, timezone
import hashlib
import json
import os
from pathlib import Path
import stat
import sys
import xml.etree.ElementTree as ET


INPUT_TREES = (
    "active-project",
    "archives",
    "hardware",
    "software/src",
    "software/config",
    "software/tests",
    "software/models",
    "software/native",
    "software/freezes",
    "software/calibrations",
    "software/scripts",
    "software/tools",
    "software/docs",
)
INPUT_FILES = (
    "rocell.ps1",
    "setup-rocell.ps1",
    "start-rocell-wizard.ps1",
    "start-rocell-onboarding.ps1",
    "software/pyproject.toml",
    "software/README.md",
    "README.md",
    "BUILD_ALIGNMENT_FREEZE.md",
    "ROBOT_TYPING_SYSTEM_MASTER_PLAN.md",
    "STATIC_OVERHEAD_CAMERA_ARCHITECTURE_PLAN.md",
)
EXCLUDED_DIRS = {
    "tmp",
    "node_modules",
    "runs",
    "__pycache__",
    ".pytest_cache",
    ".mypy_cache",
    ".ruff_cache",
    ".git",
    ".venv",
    ".codex-preserved",
}
MAX_FILES = 30_000
MAX_BYTES = 2 * 1024**3
SCHEMA = "rocell.camera_acceptance_snapshot.v1"
MANIFEST = "camera-input-manifest.json"
FULL_TEST = "test_full_original_history_reopen_prepare_probe_settings_capture_export"


def verify_test_outcome(junit: Path, *, lane: str) -> dict:
    """Require executed passing cases, not just pytest's successful exit code.

    Pytest also exits zero when every selected case is skipped. These developer
    lanes require genuine Windows execution; a skipped lane is not acceptance.
    This verifies a local test report, not original hardware evidence.
    """
    if lane not in {"smoke", "full"}:
        raise ValueError("Unknown camera acceptance lane")
    info = _regular(junit, directory=False)
    if not 0 < info.st_size <= 4 * 1024 * 1024:
        raise ValueError("Camera JUnit report exceeds its byte bound")
    raw = junit.read_bytes()
    if b"<!DOCTYPE" in raw or b"<!ENTITY" in raw:
        raise ValueError("Camera JUnit declarations are unsupported")
    root = ET.fromstring(raw)
    cases = root.findall(".//testcase")
    expected_count = 1 if lane == "full" else 23
    names = [(case.get("classname"), case.get("name")) for case in cases]
    if len(cases) != expected_count or len(set(names)) != expected_count:
        raise ValueError("Camera test selection count or identity differs")
    if any(
        case.find(tag) is not None
        for case in cases
        for tag in ("failure", "error", "skipped")
    ):
        raise ValueError(
            "Camera acceptance requires executed passing tests, not failures or skips"
        )
    if any(not module or not name for module, name in names):
        raise ValueError("Camera JUnit test identity is missing")
    if lane == "full" and (
        names[0][1] != FULL_TEST
        or not names[0][0].endswith(".test_arrival_camera_full_history_ntfs")
    ):
        raise ValueError("Camera full-history case was not executed")
    return dict(
        lane=lane,
        passed=len(cases),
        skipped=0,
        junit_sha256=hashlib.sha256(raw).hexdigest(),
    )


def _regular(path: Path, *, directory: bool) -> os.stat_result:
    info = path.lstat()
    if stat.S_ISLNK(info.st_mode) or getattr(info, "st_file_attributes", 0) & 0x400:
        raise ValueError(f"Snapshot input is a link/reparse point: {path}")
    expected = stat.S_ISDIR if directory else stat.S_ISREG
    if not expected(info.st_mode):
        raise ValueError(f"Wrong snapshot input type: {path}")
    return info


def _root(path: Path) -> Path:
    candidate = Path(os.path.abspath(path))
    for component in (*reversed(candidate.parents), candidate):
        _regular(component, directory=True)
    return candidate


def _digest(path: Path) -> dict[str, str | int]:
    before = _regular(path, directory=False)
    digest = hashlib.sha256()
    length = 0
    with path.open("rb") as stream:
        while chunk := stream.read(1024 * 1024):
            length += len(chunk)
            if length > MAX_BYTES:
                raise ValueError("Snapshot file exceeds byte budget")
            digest.update(chunk)
    after = _regular(path, directory=False)
    if (before.st_ino, before.st_size, before.st_mtime_ns) != (
        after.st_ino,
        after.st_size,
        after.st_mtime_ns,
    ) or length != after.st_size:
        raise ValueError(f"Snapshot input changed while reading: {path}")
    return {"bytes": length, "sha256": digest.hexdigest()}


def inventory(root: Path) -> dict[str, dict[str, str | int]]:
    """Closed input trees only: never enumerate another run or its evidence."""
    root = _root(root)
    paths = [root / name for name in INPUT_FILES]
    for relative in INPUT_TREES:
        base = root / relative
        _regular(base, directory=True)
        for current, directories, files in os.walk(base, followlinks=False):
            directories[:] = sorted(n for n in directories if n not in EXCLUDED_DIRS)
            for name in directories:
                _regular(Path(current) / name, directory=True)
            paths.extend(
                Path(current) / n
                for n in sorted(files)
                if not n.endswith((".pyc", ".pyo"))
            )
            if len(paths) > MAX_FILES:
                raise ValueError("Snapshot inventory exceeds file budget")
    result = {}
    total = 0
    for path in sorted(paths):
        value = _digest(path)
        total += int(value["bytes"])
        if total > MAX_BYTES:
            raise ValueError("Snapshot inventory exceeds total byte budget")
        result[path.relative_to(root).as_posix()] = value
    return result


def _canonical(value: object) -> bytes:
    return (
        json.dumps(value, sort_keys=True, separators=(",", ":"), ensure_ascii=True)
        + "\n"
    ).encode("ascii")


def _roster_digest(rows: dict) -> str:
    return hashlib.sha256(_canonical(rows)).hexdigest()


def _copy_input(source: Path, target: Path, expected_bytes: int) -> None:
    """Copy exactly the observed length; concurrent growth cannot fill the disk."""
    _regular(source, directory=False)
    remaining = expected_bytes
    with target.open("xb") as output, source.open("rb") as input_stream:
        while remaining:
            chunk = input_stream.read(min(remaining, 1024 * 1024))
            if not chunk:
                raise ValueError("Snapshot input shrank during copy")
            output.write(chunk)
            remaining -= len(chunk)
        if input_stream.read(1):
            raise ValueError("Snapshot input grew during copy")


def create_snapshot(source: Path, destination: Path) -> dict:
    source = _root(source)
    destination = Path(os.path.abspath(destination))
    _root(destination.parent)
    if destination.exists() or destination.is_symlink():
        raise ValueError(
            "Snapshot destination must be absent; existing data is preserved"
        )
    if source.is_relative_to(destination) or any(
        destination.is_relative_to(source / tree) for tree in INPUT_TREES
    ):
        raise ValueError("Snapshot destination overlaps the input trees")
    before = inventory(source)
    destination.mkdir()
    # Preserve partial copies on failure. No deletion, merge, overwrite or retry.
    for tree in INPUT_TREES:
        (destination / tree).mkdir(parents=True, exist_ok=True)
    for relative in before:
        target = destination / relative
        target.parent.mkdir(parents=True, exist_ok=True)
        _copy_input(source / relative, target, int(before[relative]["bytes"]))
    copied = inventory(destination)
    after = inventory(source)
    if copied != before or after != before:
        raise ValueError(
            "Inputs changed during snapshot; partial copy is retained but not accepted"
        )
    manifest = dict(
        schema=SCHEMA,
        source_directory=str(source),
        created_utc=datetime.now(timezone.utc).isoformat(),
        input_trees=list(INPUT_TREES),
        input_files=list(INPUT_FILES),
        excluded_directories=sorted(EXCLUDED_DIRS),
        files=before,
        input_sha256=_roster_digest(before),
        file_count=len(before),
        total_bytes=sum(int(row["bytes"]) for row in before.values()),
        physical_authority=False,
    )
    with (destination / MANIFEST).open("xb") as output:
        output.write(_canonical(manifest))
    return manifest


def verify_snapshot(root: Path) -> dict:
    root = _root(root)
    _regular(root / MANIFEST, directory=False)
    manifest = json.loads((root / MANIFEST).read_bytes())
    if (
        manifest["schema"] != SCHEMA
        or manifest["input_trees"] != list(INPUT_TREES)
        or manifest["input_files"] != list(INPUT_FILES)
        or manifest["excluded_directories"] != sorted(EXCLUDED_DIRS)
        or manifest["physical_authority"] is not False
    ):
        raise ValueError("Snapshot manifest policy differs")
    actual = inventory(root)
    if (
        actual != manifest["files"]
        or _roster_digest(actual) != manifest["input_sha256"]
        or manifest["file_count"] != len(actual)
        or manifest["total_bytes"] != sum(int(row["bytes"]) for row in actual.values())
    ):
        raise ValueError("Snapshot input bytes/roster changed")
    return manifest


def run_acceptance(snapshot: Path, result_directory: Path, *, lane: str) -> int:
    """Run a closed no-device test selection from the copied import root.

    The interpreter/dependencies are shared and reported, not installed here.
    New result directories sit outside all input trees. Manifest verification
    after pytest runs even on a failed assertion, without repairing any input.
    """
    snapshot = _root(snapshot)
    if (
        Path(__file__).resolve()
        != snapshot / "software/scripts/camera_acceptance_snapshot.py"
    ):
        raise ValueError(
            "Run the snapshot's copied acceptance script, not the shared script"
        )
    expected = verify_snapshot(snapshot)
    result_directory = Path(os.path.abspath(result_directory))
    _root(result_directory.parent)
    if result_directory.exists() or result_directory.is_relative_to(snapshot):
        raise ValueError("Results require a new directory outside snapshot inputs")
    if result_directory in snapshot.parents:
        raise ValueError("Results cannot contain snapshot inputs")
    if lane not in {"smoke", "full"}:
        raise ValueError("Unknown camera acceptance lane")
    result_directory.mkdir()
    os.chdir(snapshot)
    sys.path.insert(0, str(snapshot / "software/src"))
    os.environ["PYTEST_DISABLE_PLUGIN_AUTOLOAD"] = "1"
    sys.dont_write_bytecode = True
    import rocell
    import pytest
    from rocell.application.wizard_diagnostic_coordinator import source_fingerprint

    if not Path(rocell.__file__).resolve().is_relative_to(snapshot / "software/src"):
        raise ValueError("Acceptance imported rocell from the shared editable checkout")
    source_before = source_fingerprint(snapshot)
    args = [
        "software/tests/unit/test_arrival_camera_full_history_ntfs.py",
        "-m",
        "slow" if lane == "full" else "not slow",
        "-v",
        "--tb=short",
        "--capture=tee-sys",
        "-p",
        "no:cacheprovider",
        "--basetemp=" + str(result_directory / "pytest"),
        "--junitxml=" + str(result_directory / "junit.xml"),
    ]
    if lane == "smoke":
        args.insert(0, "software/tests/unit/test_camera_full_history_source_fixture.py")
    pytest_code = None
    audit_error = None
    outcome_error = None
    outcome = None
    ending_source = None
    try:
        pytest_code = int(pytest.main(args))
    finally:
        try:
            observed = verify_snapshot(snapshot)
            ending_source = source_fingerprint(snapshot)
            if observed != expected or ending_source != source_before:
                raise ValueError("Acceptance input/source binding changed")
        except Exception as error:
            audit_error = f"{type(error).__name__}: {error}"
        try:
            outcome = verify_test_outcome(result_directory / "junit.xml", lane=lane)
        except Exception as error:
            outcome_error = f"{type(error).__name__}: {error}"
        audit = dict(
            schema="rocell.camera_acceptance_execution.v1",
            lane=lane,
            input_sha256=expected["input_sha256"],
            source_before=source_before,
            source_after=ending_source,
            pytest_exit_code=pytest_code,
            input_audit_error=audit_error,
            test_outcome=outcome,
            test_outcome_error=outcome_error,
            interpreter=sys.executable,
            python_version=sys.version,
            rocell_import=str(rocell.__file__),
            pytest_version=pytest.__version__,
            physical_authority=False,
            accepted=pytest_code == 0 and audit_error is None and outcome_error is None,
        )
        with (result_directory / "execution-audit.json").open("xb") as output:
            output.write(_canonical(audit))
        print(json.dumps(audit, indent=2), flush=True)
    return (
        1 if audit_error is not None or outcome_error is not None else int(pytest_code)
    )


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    sub = parser.add_subparsers(dest="command", required=True)
    create = sub.add_parser("create")
    create.add_argument("--source", type=Path, required=True)
    create.add_argument("--snapshot", type=Path, required=True)
    verify = sub.add_parser("verify")
    verify.add_argument("--snapshot", type=Path, required=True)
    outcome = sub.add_parser("check-junit")
    outcome.add_argument("--junit", type=Path, required=True)
    outcome.add_argument("--lane", choices=("smoke", "full"), required=True)
    run = sub.add_parser("run")
    run.add_argument("--snapshot", type=Path, required=True)
    run.add_argument("--results", type=Path, required=True)
    run.add_argument("--lane", choices=("smoke", "full"), required=True)
    options = parser.parse_args()
    if options.command == "check-junit":
        print(
            json.dumps(verify_test_outcome(options.junit, lane=options.lane), indent=2)
        )
        return 0
    if options.command == "run":
        return run_acceptance(options.snapshot, options.results, lane=options.lane)
    manifest = (
        create_snapshot(options.source, options.snapshot)
        if options.command == "create"
        else verify_snapshot(options.snapshot)
    )
    print(
        json.dumps(
            {key: value for key, value in manifest.items() if key != "files"}, indent=2
        )
    )
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
