"""Legacy registry ABI and CM integration with incapable libraries only."""

import ctypes

import pytest

from rocell.application.arm_controller_resolution import ControllerResolutionError
from rocell.providers.windows import controller_metadata as cm
from rocell.providers.windows.legacy_usb_metadata import read_legacy_usb_metadata
from test_arm_controller_metadata_windows import CmDll, Function, setup, u32


INSTANCE = r"USB\VID_10C4&PID_EA60\SYNTHETIC-UNIT"


class Registry:
    def __init__(self):
        self.trace = []
        self.raw = "COM6\0".encode("utf-16-le")
        self.kind = 1
        self.open_status = self.query_status = 0
        for name, call in (
            ("RegOpenKeyExW", self.open),
            ("RegQueryValueExW", self.query),
            ("RegCloseKey", self.close),
        ):
            setattr(self, name, Function(call))

    def open(self, root, path, options, access, output):
        assert root.value == ctypes.c_void_p(-2147483646).value
        assert options == 0 and access == 1
        assert (
            path
            == "SYSTEM\\CurrentControlSet\\Enum\\" + INSTANCE + "\\Device Parameters"
        )
        self.trace.append("open")
        ctypes.cast(output, ctypes.POINTER(ctypes.c_void_p)).contents.value = 123
        return self.open_status

    def query(self, handle, name, reserved, kind, buffer, size):
        assert handle.value == 123 and name == "PortName" and reserved is None
        self.trace.append("query")
        capacity = u32(size).value
        ctypes.memmove(buffer, self.raw, min(capacity, len(self.raw)))
        u32(size).value, u32(kind).value = len(self.raw), self.kind
        return self.query_status

    def close(self, handle):
        assert handle.value == 123
        self.trace.append("close")
        return 0


@pytest.fixture(autouse=True)
def no_real_dll(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No actual registry or device access")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)


def test_read_only_exact_instance_and_closure():
    registry = Registry()
    assert read_legacy_usb_metadata(INSTANCE, lambda: None, library=registry) == (
        "COM6",
        "10c4",
        "ea60",
    )
    assert registry.trace == ["open", "query", "close"]


@pytest.mark.parametrize(
    "instance",
    [None, "", r"BTHENUM\anything", "COM6", r"USB\VID_10C4&PID_EA60\..\other"],
)
def test_not_a_native_usb_instance_performs_no_query(instance):
    registry = Registry()
    assert read_legacy_usb_metadata(instance, lambda: None, library=registry) is None
    assert registry.trace == []


@pytest.mark.parametrize(
    "value",
    [
        "COM0\0",
        "COM4097\0",
        "COM6",
        "COM6\0extra",
        "com6\0",
        "COM06\0",
        "COM6\0\0",
        "x" * 2000,
    ],
)
def test_invalid_port_fails_and_closes(value):
    registry = Registry()
    registry.raw = value.encode("utf-16-le")
    with pytest.raises(ControllerResolutionError):
        read_legacy_usb_metadata(INSTANCE, lambda: None, library=registry)
    assert registry.trace[-1] == "close"


@pytest.mark.parametrize(
    "fault", ["missing_key", "missing_value", "denied", "more_data", "wrong_type"]
)
def test_registry_faults_never_become_a_match(fault):
    registry = Registry()
    if fault == "missing_key":
        registry.open_status = 2
    elif fault == "missing_value":
        registry.query_status = 2
    elif fault == "denied":
        registry.open_status = 5
    elif fault == "more_data":
        registry.query_status = 234
    else:
        registry.kind = 2
    if fault.startswith("missing"):
        assert (
            read_legacy_usb_metadata(INSTANCE, lambda: None, library=registry) is None
        )
    else:
        with pytest.raises(ControllerResolutionError):
            read_legacy_usb_metadata(INSTANCE, lambda: None, library=registry)
    assert ("close" in registry.trace) == (registry.open_status == 0)


def test_cancel_after_open_still_closes():
    registry = Registry()

    def check():
        if "open" in registry.trace:
            raise RuntimeError("cancel")

    with pytest.raises(RuntimeError, match="cancel"):
        read_legacy_usb_metadata(INSTANCE, check, library=registry)
    assert registry.trace == ["open", "close"]


def test_cm_fallback_uses_registry_and_instance_not_generic_inventory():
    dll, registry = CmDll(), Registry()
    dll.values.update(
        persistent_instance_id=INSTANCE, port_name=None, vid=None, pid=None
    )
    acquirer, _, _, _ = setup(dll=dll)
    acquirer._api = cm._CmApi(_library=dll, _registry_library=registry)
    observation = acquirer().native_observations[0]
    assert (observation.port_name, observation.vid, observation.pid) == (
        "COM6",
        "10c4",
        "ea60",
    )
    assert observation.blockers == ()
    assert acquirer.status()["native_source"] == "INJECTED_CM_METADATA"


def test_cm_conflicting_interface_and_registry_values_fail():
    dll, registry = CmDll(), Registry()
    dll.values.update(
        persistent_instance_id=INSTANCE, port_name="COM7", vid=None, pid=None
    )
    acquirer, _, _, _ = setup(dll=dll)
    acquirer._api = cm._CmApi(_library=dll, _registry_library=registry)
    with pytest.raises(ControllerResolutionError, match="NATIVE_USB_METADATA_CONFLICT"):
        acquirer()
    assert registry.trace[-1] == "close"
