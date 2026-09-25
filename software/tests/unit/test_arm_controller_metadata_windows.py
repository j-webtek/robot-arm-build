"""Real CM ABI/parser code with injected C functions; no Windows API execution."""

import ctypes
from dataclasses import replace
from threading import Event

import pytest

from rocell.application import arm_controller_resolution as resolution
from rocell.application.physical_device_inventory import InventorySource
from rocell.providers.windows import controller_metadata as metadata
from test_arm_controller_resolution import batch, native, request, PATH
from test_arm_feedback_worker import Clock


def u32(ref):
    return ctypes.cast(ref, ctypes.POINTER(ctypes.c_uint32)).contents


def property_name(ref):
    value = ctypes.cast(ref, ctypes.POINTER(metadata._PropertyKey)).contents
    return next(
        name for name, (key, _) in metadata._KEYS.items() if bytes(value) == bytes(key)
    )


class Function:
    def __init__(self, call):
        self.call = call

    def __call__(self, *args):
        return self.call(*args)


class CmDll:
    """Only the five permitted metadata calls exist on this fake library."""

    def __init__(self):
        self.paths = [PATH]
        self.trace = []
        self.values = native().to_dict()
        self.read_override = {}
        self.size_override = {}
        self.list_error = 0
        self.size_error = 0
        self.node_error = 0
        self.after_call = lambda: None
        self.list_wire = None
        self.list_size = None
        for name, function in (
            ("CM_Get_Device_Interface_List_SizeW", self.list_size_call),
            ("CM_Get_Device_Interface_ListW", self.list_call),
            ("CM_Get_Device_Interface_PropertyW", self.interface_call),
            ("CM_Locate_DevNodeW", self.node_call),
            ("CM_Get_DevNode_PropertyW", self.node_property_call),
        ):
            setattr(self, name, Function(function))

    def record(self, name, *args):
        self.trace.append((name, *args))
        self.after_call()

    def wire(self):
        if self.list_wire is not None:
            return self.list_wire
        return (("\0".join(self.paths) + "\0\0") if self.paths else "\0").encode(
            "utf-16-le"
        )

    def list_size_call(self, size, guid, device_id, flags):
        assert bytes(
            ctypes.cast(guid, ctypes.POINTER(metadata._Guid)).contents
        ) == bytes(metadata._COM_GUID)
        assert device_id is None and flags == 0
        u32(size).value = (
            len(self.wire()) // 2 if self.list_size is None else self.list_size
        )
        self.record("list_size")
        return self.size_error

    def list_call(self, guid, device_id, buffer, length, flags):
        assert device_id is None and flags == 0
        raw = self.wire()
        ctypes.memmove(buffer, raw, min(len(raw), length * 2))
        self.record("list")
        return self.list_error

    def property_call(self, target, key, kind, buffer, size, flags, *, node):
        assert flags == 0
        name = property_name(key)
        assert (
            (name.startswith("driver_") and target == 123)
            if node
            else (not name.startswith("driver_") and target in self.paths)
        )
        value = self.values[name]
        raw_type = metadata._KEYS[name][1]
        if name in ("vid", "pid"):
            raw = b"" if value is None else int(value, 16).to_bytes(2, "little")
        else:
            raw = b"" if value is None else (value + "\0").encode("utf-16-le")
        if buffer is None:
            status, amount, reported_type = self.size_override.get(
                name,
                (
                    metadata._MISSING if value is None else metadata._BUFFER_SMALL,
                    len(raw),
                    raw_type,
                ),
            )
            u32(size).value, u32(kind).value = amount, reported_type
            self.record("property_size", name)
            return status
        status, raw, reported_type, amount = self.read_override.get(
            name, (0, raw, raw_type, len(raw))
        )
        capacity = u32(size).value
        ctypes.memmove(buffer, raw, min(capacity, len(raw)))
        u32(size).value, u32(kind).value = amount, reported_type
        self.record("property", name)
        return status

    def interface_call(self, *args):
        return self.property_call(*args, node=False)

    def node_property_call(self, *args):
        return self.property_call(*args, node=True)

    def node_call(self, result, instance, flags):
        assert instance == self.values["persistent_instance_id"] and flags == 0
        u32(result).value = 123
        self.record("node")
        return self.node_error


@pytest.fixture(autouse=True)
def no_native_or_os_enumeration(monkeypatch):
    def forbidden(*args, **kwargs):
        pytest.fail("No native DLL or actual serial metadata enumeration allowed")

    monkeypatch.setattr(ctypes, "WinDLL", forbidden, raising=False)
    monkeypatch.setattr(metadata, "inventory_serial_ports_with_pyserial", forbidden)


def setup(*, dll=None, generic=None, clock=None, cancel=None, maximum_acquisitions=2):
    dll = CmDll() if dll is None else dll
    clock = Clock() if clock is None else clock
    cancel = Event() if cancel is None else cancel
    generic = batch if generic is None else generic
    acquirer = metadata.WindowsControllerMetadataAcquirer(
        deadline_ns=clock.value + 10_000_000_000,
        cancellation=cancel,
        monotonic_ns=clock,
        inventory=generic,
        api=metadata._CmApi(_library=dll),
        maximum_acquisitions=maximum_acquisitions,
    )
    return acquirer, dll, clock, cancel


@pytest.mark.parametrize('limit', [2, 5, 7, 8, 32])
def test_explicit_snapshot_allowance_is_finite_and_keeps_native_limits(limit):
    acquirer, dll, _, _ = setup(maximum_acquisitions=limit)
    for _ in range(limit):
        acquirer()
    before = list(dll.trace)
    with pytest.raises(resolution.ControllerResolutionError) as error:
        acquirer()
    assert error.value.code == 'CONTROLLER_RESOLUTION_CALL_LIMIT'
    assert dll.trace == before
    assert acquirer.status()['acquisition_attempts'] == limit
    assert acquirer.status()['metadata_api_calls'] <= metadata.MAX_NATIVE_CALLS
    assert acquirer.status()['metadata_buffer_bytes_reserved'] <= metadata.MAX_QUERY_BYTES


@pytest.mark.parametrize('limit', [True, 0, 9, 31, 33, 2.0])
def test_invalid_snapshot_allowance_rejected_before_native_access(limit):
    with pytest.raises(resolution.ControllerResolutionError):
        setup(maximum_acquisitions=limit)


def test_constructor_status_and_default_unregistered_native_do_no_io():
    acquirer, dll, clock, _ = setup()
    before = clock.value
    assert acquirer.status()["metadata_api_calls"] == 0
    assert dll.trace == [] and clock.value == before
    physical = metadata.WindowsControllerMetadataAcquirer(
        deadline_ns=5, cancellation=Event()
    )
    assert physical.status()["native_source"] == "WINDOWS_CM_METADATA"
    assert physical.status()["metadata_api_calls"] == 0
    assert physical._api._dll is None


def test_actual_cm_parser_and_resolver_callback_join_without_native_calls():
    acquirer, dll, clock, cancel = setup()
    resolver = resolution.ExplicitArmControllerResolver(
        request(clock).controller,
        acquirer,
        deadline_ns=clock.value + 10_000_000_000,
        cancellation=cancel,
        monotonic_ns=clock,
    )
    for _ in range(2):
        assert (
            resolver(request(clock).controller.identity)
            == request(clock).controller.identity
        )
    status = acquirer.status()
    assert status["acquisition_attempts"] == 2
    assert status["metadata_api_calls"] == len(dll.trace)
    assert status["physical_authority"] is False
    assert resolver.status()["latest"]["native_source"] == "INJECTED_CM_METADATA"
    assert {row[0] for row in dll.trace} == {
        "list_size",
        "list",
        "property_size",
        "property",
        "node",
    }
    assert sum(row[0] == "list" for row in dll.trace) == 4


def test_cm_acquisition_callback_and_actual_nonpurging_worker_compose_end_to_end():
    from rocell.providers.windows.arm_feedback_worker import (
        ArmFeedbackOutcome,
        ArmFeedbackWorker,
    )
    from rocell.providers.windows.arm_nonpurging_adapter import (
        NonPurgingArmFeedbackBackend,
    )
    from rocell.providers.windows.nonpurging_serial_api import IncapableWin32SerialApi

    acquirer, dll, clock, cancel = setup()
    exact = request(clock)
    api = IncapableWin32SerialApi()
    backend = NonPurgingArmFeedbackBackend(exact.controller, api=api)
    resolver = resolution.ExplicitArmControllerResolver(
        exact.controller,
        acquirer,
        deadline_ns=exact.expires_monotonic_ns,
        cancellation=cancel,
        monotonic_ns=clock,
    )
    worker = ArmFeedbackWorker(
        authorizer=lambda _: None,
        identity_resolver=resolver,
        backend=backend,
        monotonic_ns=clock,
        wait=clock.wait,
    )
    result = worker.run(exact, cancellation=cancel)
    assert result.outcome is ArmFeedbackOutcome.SUCCEEDED_DIAGNOSTIC
    assert (
        result.api_counts.identity_checks
        == acquirer.status()["acquisition_attempts"]
        == 2
    )
    assert result.api_counts.writes_confirmed == result.api_counts.closes_confirmed == 1
    assert api.open_handles == () and dll.trace
    assert backend.retain_evidence(exact, result).view()["physical_authority"] is False


def test_default_native_loader_is_lazy_fixed_system32_and_metadata_only(monkeypatch):
    """The Windows DLL boundary itself is a fake; no real DLL is loaded."""
    dll, loads = CmDll(), []
    clock = Clock()
    generic = batch()
    physical = replace(
        generic,
        source=InventorySource.PYSERIAL_LIST_PORTS,
        candidates=tuple(
            replace(v, source=InventorySource.PYSERIAL_LIST_PORTS)
            for v in generic.candidates
        ),
    )

    def load(name, **kwargs):
        loads.append((name, kwargs))
        return dll

    # _CmApi checks the platform and Windows wchar ABI before its lazy load.
    # This test is therefore Windows-only, unlike the injected buffer tests.
    if metadata.os.name != "nt":
        pytest.skip("Default loader ABI check requires Windows; no DLL is executed")
    monkeypatch.setattr(ctypes, "WinDLL", load)
    acquirer = metadata.WindowsControllerMetadataAcquirer(
        deadline_ns=clock.value + 10_000_000_000,
        cancellation=Event(),
        monotonic_ns=clock,
        inventory=lambda: physical,
    )
    assert acquirer.status()["metadata_api_calls"] == 0 and loads == []
    snap = acquirer()
    assert loads == [("cfgmgr32.dll", {"winmode": 0x800})]
    assert snap.native_source == "WINDOWS_CM_METADATA"
    assert all(
        not name.startswith(("Set", "Create", "Open", "Write"))
        for name in vars(dll)
        if name.startswith("CM_")
    )


@pytest.mark.parametrize("field", list(metadata._KEYS))
def test_missing_properties_stay_unknown_and_never_fill_from_review(field):
    dll = CmDll()
    dll.values[field] = None
    acquirer, _, _, _ = setup(dll=dll)
    snap = acquirer()
    assert getattr(snap.native_observations[0], field) is None
    assert (
        resolution.resolve_controller_metadata(request().controller, snap).identity
        is None
    )
    if field == "persistent_instance_id":
        assert not any(row[0] == "node" for row in dll.trace)


def test_generic_and_native_observed_boundary_drift_is_retained_as_collection_hold():
    calls = 0
    original = batch()

    def inventory():
        nonlocal calls
        calls += 1
        if calls == 1:
            return original
        return replace(
            original,
            candidates=(replace(original.candidates[0], ephemeral_locator="COM405"),),
        )

    acquirer, dll, _, _ = setup(generic=inventory)
    dll.after_call = lambda: (
        dll.paths.clear() if dll.trace[-1] == ("property", "driver_inf") else None
    )
    snap = acquirer()
    assert set(snap.collection_blockers) == {
        "NATIVE_INTERFACE_LIST_CHANGED_DURING_ACQUISITION",
        "GENERIC_INVENTORY_CHANGED_DURING_ACQUISITION",
    }
    assert (
        resolution.resolve_controller_metadata(request().controller, snap).identity
        is None
    )


@pytest.mark.parametrize("mode", ["size_error", "list_error", "node_error"])
def test_native_errors_do_not_silently_make_a_complete_snapshot(mode):
    dll = CmDll()
    setattr(dll, mode, 0x0D)
    acquirer, _, _, _ = setup(dll=dll)
    with pytest.raises(resolution.ControllerResolutionError) as error:
        acquirer()
    assert "0000000D" in error.value.code


@pytest.mark.parametrize("count", [0, metadata.MAX_LIST_BYTES // 2 + 1, 0xFFFFFFFF])
def test_list_allocation_is_bounded_before_second_native_call(count):
    dll = CmDll()
    dll.list_size = count
    acquirer, _, _, _ = setup(dll=dll)
    with pytest.raises(resolution.ControllerResolutionError):
        acquirer()
    assert dll.trace == [("list_size",)]


def test_list_growth_has_only_one_retry_and_no_properties_or_port_fallback():
    dll = CmDll()
    dll.list_error = metadata._BUFFER_SMALL
    acquirer, _, _, _ = setup(dll=dll)
    with pytest.raises(resolution.ControllerResolutionError) as error:
        acquirer()
    assert error.value.code == "CM_LIST_CHANGED"
    assert dll.trace == [("list_size",), ("list",)] * 2


@pytest.mark.parametrize(
    "raw",
    [
        (PATH + "\0").encode("utf-16-le"),
        ("COM404\0\0").encode("utf-16-le"),
        (PATH + "\0" + PATH + "\0\0").encode("utf-16-le"),
        b"\x00\xd8\x00\x00\x00\x00",
    ],
)
def test_malformed_or_duplicate_interface_list_is_rejected(raw):
    dll = CmDll()
    dll.list_wire = raw
    acquirer, _, _, _ = setup(dll=dll)
    with pytest.raises(resolution.ControllerResolutionError):
        acquirer()
    assert len(dll.trace) == 2


def test_candidate_count_is_bounded_without_property_reads():
    dll = CmDll()
    dll.paths = [PATH + str(i) for i in range(129)]
    acquirer, _, _, _ = setup(dll=dll)
    with pytest.raises(resolution.ControllerResolutionError):
        acquirer()
    assert dll.trace == [("list_size",), ("list",)]


@pytest.mark.parametrize(
    "override",
    [
        (0, b"\x01\x00", metadata._STRING, 2),
        (0, b"\x01\x00\x00", metadata._UINT16, 3),
        (0, b"\x01\x00", metadata._UINT16, 3000),
        (metadata._BUFFER_SMALL, b"", metadata._UINT16, 4),
    ],
)
def test_native_uint_property_type_size_or_hotplug_drift_is_held(override):
    dll = CmDll()
    dll.read_override["vid"] = override
    acquirer, _, _, _ = setup(dll=dll)
    with pytest.raises(resolution.ControllerResolutionError):
        acquirer()


@pytest.mark.parametrize(
    "raw",
    [b"x", b"x\x00", b"\x00\xd8\x00\x00", "a\0b\0".encode("utf-16-le"), b"\x00\x00"],
)
def test_invalid_native_string_property_never_becomes_an_identifier(raw):
    dll = CmDll()
    dll.read_override["port_name"] = (0, raw, metadata._STRING, len(raw))
    acquirer, _, _, _ = setup(dll=dll)
    with pytest.raises(resolution.ControllerResolutionError):
        acquirer()


def test_property_allocation_limit_is_checked_before_content_read():
    dll = CmDll()
    dll.size_override["vid"] = (
        metadata._BUFFER_SMALL,
        metadata.MAX_PROPERTY_BYTES + 1,
        metadata._UINT16,
    )
    acquirer, _, _, _ = setup(dll=dll)
    with pytest.raises(resolution.ControllerResolutionError) as error:
        acquirer()
    assert error.value.code == "CM_BUFFER_LIMIT"
    assert ("property", "vid") not in dll.trace


def test_cumulative_buffer_and_call_limits_precede_native_content_io(monkeypatch):
    monkeypatch.setattr(metadata, "MAX_QUERY_BYTES", 4)
    acquirer, dll, _, _ = setup()
    with pytest.raises(resolution.ControllerResolutionError) as error:
        acquirer()
    assert error.value.code == "CM_TOTAL_BUFFER_LIMIT"
    assert dll.trace == [("list_size",)]
    monkeypatch.setattr(metadata, "MAX_QUERY_BYTES", 1024 * 1024)
    monkeypatch.setattr(metadata, "MAX_NATIVE_CALLS", 1)
    acquirer, dll, _, _ = setup()
    with pytest.raises(resolution.ControllerResolutionError) as error:
        acquirer()
    assert error.value.code == "CM_CALL_LIMIT"
    assert dll.trace == [("list_size",)]


def test_cancel_and_expiry_checked_before_any_query_and_after_each_native_call():
    acquirer, dll, clock, cancel = setup()
    cancel.set()
    with pytest.raises(resolution.ControllerResolutionError):
        acquirer()
    assert dll.trace == []
    acquirer, dll, clock, cancel = setup()
    dll.after_call = cancel.set
    with pytest.raises(resolution.ControllerResolutionError):
        acquirer()
    assert dll.trace == [("list_size",)]
    acquirer, dll, clock, cancel = setup()
    dll.after_call = lambda: setattr(clock, "value", clock.value + 11_000_000_000)
    with pytest.raises(resolution.ControllerResolutionError):
        acquirer()
    assert dll.trace == [("list_size",)]


def test_generic_provider_error_never_starts_native_acquisition():
    def fail():
        raise RuntimeError("injected inventory failed")

    acquirer, dll, _, _ = setup(generic=fail)
    with pytest.raises(RuntimeError):
        acquirer()
    assert dll.trace == []


def test_incapable_native_calls_cannot_implicitly_use_physical_generic_enumerator():
    with pytest.raises(resolution.ControllerResolutionError):
        metadata.WindowsControllerMetadataAcquirer(
            deadline_ns=100, cancellation=Event(), api=metadata._CmApi(_library=CmDll())
        )


def test_mixed_generic_origin_is_refused_before_native_metadata_calls():
    generic = batch()
    physical = replace(
        generic,
        source=InventorySource.PYSERIAL_LIST_PORTS,
        candidates=tuple(
            replace(v, source=InventorySource.PYSERIAL_LIST_PORTS)
            for v in generic.candidates
        ),
    )
    acquirer, dll, _, _ = setup(generic=lambda: physical)
    with pytest.raises(resolution.ControllerResolutionError) as error:
        acquirer()
    assert error.value.code == "CONTROLLER_METADATA_PROVENANCE_MISMATCH"
    assert dll.trace == []
