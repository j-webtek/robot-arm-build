"""Closed source roster for the passive native child; not a release permit."""

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
    read_bounded_regular_file,
)

CHILD = Path(__file__).with_name("_passive_native_child.py")
EXTRA = (
    "application/arm_bench_qualification_contract.py",
    "application/arm_bench_qualification_result.py",
    "application/passive_arm_entry_policy.py",
    "application/passive_arm_identity.py",
    "application/passive_arm_attempt_store.py",
    "application/passive_arm_child_claim.py",
    "application/physical_onboarding_durability.py",
    "application/wizard_diagnostic_coordinator.py",
    "application/wizard_actions.py",
    "application/wizard_native_arm_metadata.py",
    "application/wizard_device_selection.py",
    "providers/windows/passive_serial_binding.py",
    "providers/windows/passive_serial_api.py",
    "providers/windows/passive_serial_observation.py",
    "providers/windows/legacy_usb_metadata.py",
    "providers/windows/passive_native_registration.py",
    "providers/windows/passive_native_wire.py",
)
SERIAL = (
    "__init__.py",
    "serialutil.py",
    "serialwin32.py",
    "win32.py",
    "tools/__init__.py",
    "tools/list_ports.py",
    "tools/list_ports_common.py",
    "tools/list_ports_windows.py",
)


def expected_archive():
    _, entries = _sources(_WORKSPACE)
    for name in EXTRA:
        entries["rocell/" + name] = _read(
            _WORKSPACE / "software/src/rocell" / name, MAX_FILE_BYTES
        )
    for name in SERIAL:
        path = _WORKSPACE / ".venv/Lib/site-packages/serial" / name
        # pySerial's tools namespace is legitimately a zero-byte __init__.
        # Retain it exactly through the regular-file reader; do not broaden the
        # older arm packager's nonempty module policy or synthesize its content.
        entries["serial/" + name] = (
            read_bounded_regular_file(path, maximum_bytes=MAX_FILE_BYTES)
            if name == "tools/__init__.py"
            else _read(path, MAX_FILE_BYTES)
        )
    return _archive(entries)


def prepare(directory):
    return publish_bytes(
        directory,
        "passive-native.zip",
        expected_archive(),
        mode=PublicationMode.IMMUTABLE,
        maximum_bytes=MAX_PACKAGE_BYTES,
    )
