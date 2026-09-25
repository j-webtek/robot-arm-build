"""Explicit read-only COM interface metadata acquisition, never a port open.

CM interface-list/property and device-node/property functions are used, with a
read-only exact-instance registry PortName fallback for legacy USB drivers.
Construction/status do not load a DLL, enumerate, read files or consult clocks.
The native library is resolved from System32 on explicit acquisition only.
Native call injection is for incapable tests and is labeled synthetic.
"""

from __future__ import annotations

import ctypes
import os
from threading import Event, RLock
import time
from typing import Any, Callable
from uuid import UUID

from rocell.application.arm_controller_resolution import (
    ControllerMetadataSnapshot,
    ControllerNativeMetadata,
    ControllerResolutionError,
    MAX_CANDIDATES,
    _require,
    _text,
    _validate_batch,
)
from rocell.application.physical_connection_contracts import EvidenceOrigin
from rocell.application.physical_device_inventory import (
    DeviceInventoryBatch,
    InventorySource,
    inventory_serial_ports_with_pyserial,
)


MAX_LIST_BYTES = 128 * 1024
MAX_PROPERTY_BYTES = 2048
MAX_QUERY_BYTES = 1024 * 1024
MAX_NATIVE_CALLS = 4096
_U32 = ctypes.c_uint32
_U16 = ctypes.c_uint16
_PU32 = ctypes.POINTER(_U32)
_SUCCESS, _BUFFER_SMALL, _MISSING = 0, 0x1A, 0x25
_STRING, _UINT16 = 0x12, 0x05


class _Guid(ctypes.Structure):
    _fields_ = [("data", ctypes.c_ubyte * 16)]


class _PropertyKey(ctypes.Structure):
    _fields_ = [("fmtid", _Guid), ("pid", _U32)]


def _guid(value: str) -> _Guid:
    return _Guid.from_buffer_copy(UUID(value).bytes_le)


_COM_GUID = _guid("86e0d1e0-8089-11d0-9ce4-08003e301f73")
_SERIAL_FMT = "4c6bf15c-4c03-4aac-91f5-64c0f852bcf4"
_DRIVER_FMT = "a8b865dd-2e3d-4094-ad97-e593a70c75d6"
_KEYS = {
    "port_name": (_PropertyKey(_guid(_SERIAL_FMT), 4), _STRING),
    "vid": (_PropertyKey(_guid(_SERIAL_FMT), 2), _UINT16),
    "pid": (_PropertyKey(_guid(_SERIAL_FMT), 3), _UINT16),
    "persistent_instance_id": (
        _PropertyKey(_guid("78c34fc8-104a-4aca-9ea4-524d52996e57"), 256),
        _STRING,
    ),
    "driver_provider": (_PropertyKey(_guid(_DRIVER_FMT), 9), _STRING),
    "driver_version": (_PropertyKey(_guid(_DRIVER_FMT), 3), _STRING),
    "driver_inf": (_PropertyKey(_guid(_DRIVER_FMT), 5), _STRING),
    "driver_service": (
        _PropertyKey(_guid("a45c254e-df1c-4efd-8020-67d146a850e0"), 6),
        _STRING,
    ),
}


def _decode_string(raw: bytes) -> str:
    _require(
        2 <= len(raw) <= MAX_PROPERTY_BYTES and len(raw) % 2 == 0,
        "CM_PROPERTY_STRING_INVALID",
    )
    try:
        value = raw.decode("utf-16-le", errors="strict")
    except UnicodeError as error:
        raise ControllerResolutionError(
            "CM_PROPERTY_STRING_INVALID", "invalid UTF-16 metadata"
        ) from error
    _require(
        value.endswith("\0") and "\0" not in value[:-1], "CM_PROPERTY_STRING_INVALID"
    )
    value = value[:-1]
    _text(value)
    return value


class _CmApi:
    """Fixed ABI only; a private injected library avoids all OS calls in tests."""

    def __init__(self, *, _library: Any = None, _registry_library: Any = None) -> None:
        self._dll = _library
        _require(
            _registry_library is None or _library is not None,
            "INJECTED_CM_LIBRARY_REQUIRED",
        )
        self._registry_library = _registry_library
        self.injected = _library is not None
        self._bound = False
        self.calls = self.bytes_reserved = 0

    def _library(self) -> Any:
        if self._dll is None:
            _require(
                os.name == "nt" and ctypes.sizeof(ctypes.c_wchar) == 2,
                "WINDOWS_CM_METADATA_UNAVAILABLE",
            )
            self._dll = ctypes.WinDLL("cfgmgr32.dll", winmode=0x800)
        if not self._bound:
            ptr = ctypes.c_void_p
            prototypes = {
                "CM_Get_Device_Interface_List_SizeW": [
                    _PU32,
                    ptr,
                    ctypes.c_wchar_p,
                    _U32,
                ],
                "CM_Get_Device_Interface_ListW": [
                    ptr,
                    ctypes.c_wchar_p,
                    ptr,
                    _U32,
                    _U32,
                ],
                "CM_Get_Device_Interface_PropertyW": [
                    ctypes.c_wchar_p,
                    ptr,
                    _PU32,
                    ptr,
                    _PU32,
                    _U32,
                ],
                "CM_Locate_DevNodeW": [_PU32, ctypes.c_wchar_p, _U32],
                "CM_Get_DevNode_PropertyW": [_U32, ptr, _PU32, ptr, _PU32, _U32],
            }
            for name, args in prototypes.items():
                function = getattr(self._dll, name)
                function.argtypes, function.restype = args, _U32
            self._bound = True
        return self._dll

    def _call(self, check: Callable[[], Any], name: str, *args: Any) -> int:
        check()
        _require(self.calls < MAX_NATIVE_CALLS, "CM_CALL_LIMIT")
        function = getattr(self._library(), name)
        # DLL load and symbol resolution may take time; check again before the
        # first actual metadata call, without extending the caller's deadline.
        check()
        self.calls += 1
        result = function(*args)
        check()
        _require(type(result) is int and 0 <= result <= 0xFFFFFFFF, "CM_STATUS_INVALID")
        return result

    def _reserve(self, count: int, maximum: int) -> None:
        _require(type(count) is int and 0 < count <= maximum, "CM_BUFFER_LIMIT")
        _require(
            self.bytes_reserved + count <= MAX_QUERY_BYTES, "CM_TOTAL_BUFFER_LIMIT"
        )
        self.bytes_reserved += count

    def interfaces(self, check: Callable[[], Any]) -> tuple[str, ...]:
        # A hot-plug size race gets one bounded retry, never an unbounded loop.
        for _ in range(2):
            size = _U32()
            status = self._call(
                check,
                "CM_Get_Device_Interface_List_SizeW",
                ctypes.byref(size),
                ctypes.byref(_COM_GUID),
                None,
                0,
            )
            _require(status == _SUCCESS, f"CM_LIST_SIZE_ERROR_{status:08X}")
            self._reserve(size.value * 2, MAX_LIST_BYTES)
            buffer = (_U16 * size.value)()
            status = self._call(
                check,
                "CM_Get_Device_Interface_ListW",
                ctypes.byref(_COM_GUID),
                None,
                buffer,
                size.value,
                0,
            )
            if status == _BUFFER_SMALL:
                continue
            _require(status == _SUCCESS, f"CM_LIST_ERROR_{status:08X}")
            try:
                text = bytes(buffer).decode("utf-16-le", errors="strict")
            except UnicodeError as error:
                raise ControllerResolutionError(
                    "CM_LIST_INVALID", "invalid UTF-16 metadata list"
                ) from error
            if text in ("\0", "\0\0"):
                return ()
            _require(text.endswith("\0\0"), "CM_LIST_INVALID")
            values = tuple(text[:-2].split("\0"))
            _require(
                len(values) <= MAX_CANDIDATES and len(set(values)) == len(values),
                "CM_LIST_AMBIGUOUS_OR_OVER_LIMIT",
            )
            for value in values:
                _text(value)
                _require(value.startswith("\\\\?\\"), "CM_LIST_INVALID")
            return tuple(sorted(values))
        raise ControllerResolutionError(
            "CM_LIST_CHANGED", "bounded interface enumeration changed"
        )

    def property(
        self,
        target: str | int,
        field: str,
        check: Callable[[], Any],
        *,
        node: bool = False,
    ) -> str | None:
        key, expected_type = _KEYS[field]
        function = (
            "CM_Get_DevNode_PropertyW" if node else "CM_Get_Device_Interface_PropertyW"
        )
        size, kind = _U32(), _U32()
        status = self._call(
            check,
            function,
            target,
            ctypes.byref(key),
            ctypes.byref(kind),
            None,
            ctypes.byref(size),
            0,
        )
        if status == _MISSING:
            return None
        _require(status == _BUFFER_SMALL, f"CM_PROPERTY_SIZE_ERROR_{status:08X}")
        self._reserve(size.value, MAX_PROPERTY_BYTES)
        capacity = size.value
        buffer = (ctypes.c_ubyte * capacity)()
        status = self._call(
            check,
            function,
            target,
            ctypes.byref(key),
            ctypes.byref(kind),
            buffer,
            ctypes.byref(size),
            0,
        )
        _require(status == _SUCCESS, f"CM_PROPERTY_ERROR_{status:08X}")
        _require(
            kind.value == expected_type and 0 < size.value <= capacity,
            "CM_PROPERTY_TYPE_OR_SIZE_INVALID",
        )
        raw = bytes(buffer[: size.value])
        if expected_type == _UINT16:
            _require(len(raw) == 2, "CM_PROPERTY_TYPE_OR_SIZE_INVALID")
            return f"{int.from_bytes(raw, 'little'):04x}"
        return _decode_string(raw)

    def node(self, instance: str, check: Callable[[], Any]) -> int:
        _text(instance)
        value = _U32()
        # NORMAL only: no phantom lookup, remove cancellation, restart or scan.
        status = self._call(
            check, "CM_Locate_DevNodeW", ctypes.byref(value), instance, 0
        )
        _require(status == _SUCCESS, f"CM_NODE_ERROR_{status:08X}")
        return value.value

    def legacy_usb(self, instance: str, check: Callable[[], Any]):
        # An incapable CM fixture must never fall through to the real registry.
        if self.injected and self._registry_library is None:
            return None
        # The sealed incapable child has no registry backend and must not need
        # the native fallback module merely to import this metadata codec.
        # A future physically capable runtime must package this dependency.
        from .legacy_usb_metadata import read_legacy_usb_metadata

        check()
        _require(self.calls + 3 <= MAX_NATIVE_CALLS, "CM_CALL_LIMIT")
        self.calls += 3  # Conservative allowance: registry open, query, close.
        self._reserve(MAX_PROPERTY_BYTES, MAX_PROPERTY_BYTES)
        return read_legacy_usb_metadata(instance, check, library=self._registry_library)


class WindowsControllerMetadataAcquirer:
    """Explicit snapshot function for ExplicitArmControllerResolver.

    Uses generic serial inventory and independent native CM/registry metadata.
    Both generic inventory and interface-list boundaries are compared before
    returning. This catches observed changes, not an atomic snapshot/handle bind.
    A process supervisor must still contain potentially stalled native calls.
    """

    def __init__(
        self,
        *,
        deadline_ns: int,
        cancellation: Event,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
        inventory: Callable[[], DeviceInventoryBatch] | None = None,
        api: _CmApi | None = None,
        maximum_acquisitions: int = 2,
    ) -> None:
        _require(type(deadline_ns) is int and 0 < deadline_ns <= 2**63 - 1)
        _require(type(cancellation) is Event and callable(monotonic_ns))
        # Single trials use up to eight checks; the finite two-leg campaign
        # explicitly requests 32 across its durable claims. This is metadata
        # only: cumulative native-call/byte budgets and the deadline are unchanged.
        _require(type(maximum_acquisitions) is int
                 and (1 <= maximum_acquisitions <= 8 or maximum_acquisitions == 32),
                 'INVALID_CONTROLLER_ACQUISITION_LIMIT')
        self._maximum_acquisitions = maximum_acquisitions
        _require(api is None or type(api) is _CmApi, "EXACT_CM_METADATA_API_REQUIRED")
        self._api = _CmApi() if api is None else api
        _require(
            not self._api.injected or callable(inventory), "INJECTED_INVENTORY_REQUIRED"
        )
        _require(inventory is None or callable(inventory))
        self._inventory = (
            inventory_serial_ports_with_pyserial if inventory is None else inventory
        )
        self._deadline, self._cancel, self._clock = (
            deadline_ns,
            cancellation,
            monotonic_ns,
        )
        self._last_now, self._acquisitions = 0, 0
        self._lock = RLock()

    def status(self) -> dict[str, Any]:
        with self._lock:
            return {
                "native_source": (
                    "INJECTED_CM_METADATA"
                    if self._api.injected
                    else "WINDOWS_CM_METADATA"
                ),
                "acquisition_attempts": self._acquisitions,
                "metadata_api_calls": self._api.calls,
                "metadata_buffer_bytes_reserved": self._api.bytes_reserved,
                "hardware_accessed_by_status": False,
                "device_ports_opened": False,
                "physical_authority": False,
            }

    def _check(self) -> int:
        _require(not self._cancel.is_set(), "CONTROLLER_RESOLUTION_CANCELLED")
        now = self._clock()
        _require(
            type(now) is int and 0 < now < self._deadline and now >= self._last_now,
            "CONTROLLER_RESOLUTION_DEADLINE_OR_CLOCK",
        )
        self._last_now = now
        return now

    def __call__(self) -> ControllerMetadataSnapshot:
        with self._lock:
            _require(self._acquisitions < self._maximum_acquisitions, "CONTROLLER_RESOLUTION_CALL_LIMIT")
            self._acquisitions += 1
            start = self._check()
            generic = self._inventory()
            self._check()
            _validate_batch(generic)
            _require(
                generic.source
                is (
                    InventorySource.INJECTED_SERIAL_ENUMERATOR
                    if self._api.injected
                    else InventorySource.PYSERIAL_LIST_PORTS
                ),
                "CONTROLLER_METADATA_PROVENANCE_MISMATCH",
            )
            generic_hash = generic.batch_sha256
            paths = self._api.interfaces(self._check)
            observations = []
            for path in paths:
                values: dict[str, str | None] = {}
                blockers: list[str] = []

                def read(target: str | int, field: str, *, node: bool = False) -> None:
                    # Unknown properties remain None. Cancellation/deadline and
                    # resource exhaustion escape immediately, never continuing
                    # to query the remaining fields under a swallowed hold.
                    values[field] = self._api.property(
                        target, field, self._check, node=node
                    )
                    if values[field] is None:
                        blockers.append("NATIVE_UNOBSERVED_" + field.upper())

                for field in ("persistent_instance_id", "port_name", "vid", "pid"):
                    read(path, field)
                instance = values["persistent_instance_id"]
                if instance is not None:
                    node_id = self._api.node(instance, self._check)
                    if any(
                        values[field] is None for field in ("port_name", "vid", "pid")
                    ):
                        fallback = self._api.legacy_usb(instance, self._check)
                        if fallback is not None:
                            for field, observed in zip(
                                ("port_name", "vid", "pid"), fallback
                            ):
                                _require(
                                    values[field] in (None, observed),
                                    "NATIVE_USB_METADATA_CONFLICT",
                                )
                                if values[field] is None:
                                    values[field] = observed
                                    blockers.remove(
                                        "NATIVE_UNOBSERVED_" + field.upper()
                                    )
                    for field in (
                        "driver_provider",
                        "driver_service",
                        "driver_version",
                        "driver_inf",
                    ):
                        read(node_id, field, node=True)
                else:
                    for field in (
                        "driver_provider",
                        "driver_service",
                        "driver_version",
                        "driver_inf",
                    ):
                        values[field] = None
                observations.append(
                    ControllerNativeMetadata(
                        persistent_port_path=path, blockers=tuple(blockers), **values
                    )
                )
            after_paths = self._api.interfaces(self._check)
            self._check()
            after_generic = self._inventory()
            finish = self._check()
            _validate_batch(after_generic)
            collection = []
            if after_paths != paths:
                collection.append("NATIVE_INTERFACE_LIST_CHANGED_DURING_ACQUISITION")
            if after_generic.batch_sha256 != generic_hash:
                collection.append("GENERIC_INVENTORY_CHANGED_DURING_ACQUISITION")
            injected = self._api.injected
            return ControllerMetadataSnapshot(
                generic,
                tuple(observations),
                (
                    EvidenceOrigin.SYNTHETIC_REHEARSAL
                    if injected
                    else EvidenceOrigin.PHYSICAL_OBSERVATION
                ),
                "INJECTED_CM_METADATA" if injected else "WINDOWS_CM_METADATA",
                start,
                finish,
                tuple(collection),
            )
