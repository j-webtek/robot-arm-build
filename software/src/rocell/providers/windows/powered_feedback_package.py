"""Deterministic isolated powered-feedback worker dependencies, not admission.

The child currently exposes import and memory-rehearsal modes only. Packaging
the claim/journal code tests its deployment dependencies without enabling I/O.
"""

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
    PublicationMode,
    publish_bytes,
)

CHILD = Path(__file__).with_name("_powered_feedback_child.py")
EXTRA = (
    "application/arm_bench_qualification_contract.py",
    "application/passive_arm_identity.py",
    "application/physical_onboarding_durability.py",
    "application/wizard_diagnostic_coordinator.py",
    "application/wizard_actions.py",
    "application/wizard_native_arm_metadata.py",
    "application/wizard_device_selection.py",
    "application/wizard_inventory_fixture.py",
    "application/powered_arm_feedback_contract.py",
    "application/powered_arm_feedback_preparation.py",
    "application/powered_feedback_firmware_review.py",
    "application/powered_feedback_attempt_store.py",
    "application/powered_feedback_child_claim.py",
    "application/wizard_powered_feedback_rehearsal.py",
    "providers/windows/passive_serial_binding.py",
    "providers/windows/powered_feedback_binding.py",
    "providers/windows/powered_feedback_observation.py",
    "providers/windows/powered_feedback_serial_api.py",
    "providers/windows/powered_feedback_process_codec.py",
)


def expected_archive():
    _, entries = _sources(_WORKSPACE)
    for name in EXTRA:
        entries["rocell/" + name] = _read(
            _WORKSPACE / "software/src/rocell" / name, MAX_FILE_BYTES
        )
    return _archive(entries)


def prepare(directory):
    return publish_bytes(
        directory,
        "powered-feedback.zip",
        expected_archive(),
        mode=PublicationMode.IMMUTABLE,
        maximum_bytes=MAX_PACKAGE_BYTES,
    )
