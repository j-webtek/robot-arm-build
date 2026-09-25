"""Closed extension of the existing isolated arm archive for passive rehearsal."""

import hashlib
from pathlib import Path

from .owned_arm_feedback_package import (
    _WORKSPACE,
    _sources,
    _archive,
    _read,
    MAX_FILE_BYTES,
    MAX_PACKAGE_BYTES,
)
from rocell.application.physical_onboarding_durability import (
    publish_bytes,
    PublicationMode,
)

CHILD = Path(__file__).with_name("_passive_arm_lifecycle_child.py")
SCENARIOS = frozenset(
    {"lifecycle-nominal", "lifecycle-open-failed", "lifecycle-cleanup-unknown"}
)
EXTRA = (
    "application/arm_bench_qualification_contract.py",
    "application/arm_bench_qualification_result.py",
    "providers/windows/passive_serial_observation.py",
)


def expected_archive():
    # Reuse the exact existing dependency roster and namespace isolation. Never
    # add a caller-supplied module, import root, glob or mutable package override.
    _, entries = _sources(_WORKSPACE)
    for name in EXTRA:
        entries["rocell/" + name] = _read(
            _WORKSPACE / "software/src/rocell" / name, MAX_FILE_BYTES
        )
    return _archive(entries)


def prepare(directory):
    raw = expected_archive()
    return publish_bytes(
        directory,
        "passive-lifecycle.zip",
        raw,
        mode=PublicationMode.IMMUTABLE,
        maximum_bytes=MAX_PACKAGE_BYTES,
    )


def validate_registration(registration, scenario):
    files = registration.package_files
    if (
        scenario not in SCENARIOS
        or len(files) != 2
        or files[0].path != CHILD
        or files[1].path != registration.working_directory / "passive-lifecycle.zip"
        or registration.argv
        != ("-I", "-S", str(CHILD), str(files[1].path), files[1].sha256, scenario)
    ):
        raise ValueError("PASSIVE_LIFECYCLE_FIXED_PACKAGE_REQUIRED")
    # A hash supplied by a caller alone is insufficient. Require the archive
    # derived from this checked-out, closed source roster. The process owner
    # subsequently pins both files for the child lifetime.
    if hashlib.sha256(expected_archive()).hexdigest() != files[1].sha256:
        raise ValueError("PASSIVE_LIFECYCLE_SOURCE_MISMATCH")
