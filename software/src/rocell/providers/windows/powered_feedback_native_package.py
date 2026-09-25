"""Closed physical feedback dependencies, separate from the rehearsal archive."""

from pathlib import Path
from .owned_arm_feedback_package import (
    _WORKSPACE,
    _sources,
    _archive,
    _read,
    MAX_FILE_BYTES,
    MAX_PACKAGE_BYTES,
)
from .powered_feedback_package import EXTRA
from .passive_native_package import SERIAL
from rocell.application.physical_onboarding_durability import (
    PublicationMode,
    publish_bytes,
    read_bounded_regular_file,
)

CHILD = Path(__file__).with_name("_powered_feedback_native_child.py")


def expected_archive():
    _, entries = _sources(_WORKSPACE)
    for name in EXTRA + (
        "providers/windows/legacy_usb_metadata.py",
        "providers/windows/powered_feedback_native_registration.py",
        "providers/windows/powered_feedback_native_wire.py",
        "providers/windows/powered_telemetry_observation.py",
        "providers/windows/powered_telemetry_wire.py",
        "arm/telemetry_stream.py",
    ):
        entries["rocell/" + name] = _read(
            _WORKSPACE / "software/src/rocell" / name, MAX_FILE_BYTES
        )
    for name in SERIAL:
        path = _WORKSPACE / ".venv/Lib/site-packages/serial" / name
        entries["serial/" + name] = (
            read_bounded_regular_file(path, maximum_bytes=MAX_FILE_BYTES)
            if name == "tools/__init__.py"
            else _read(path, MAX_FILE_BYTES)
        )
    return _archive(entries)


def prepare(directory):
    return publish_bytes(
        directory,
        "powered-feedback-native.zip",
        expected_archive(),
        mode=PublicationMode.IMMUTABLE,
        maximum_bytes=MAX_PACKAGE_BYTES,
    )
