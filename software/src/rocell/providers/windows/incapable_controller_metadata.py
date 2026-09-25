"""Sealed in-memory CM ABI and serial inventory for the contained arm child.

No DLL loader, endpoint opener or host inventory is reachable here. Modeled
values go through the real Windows metadata acquirer's UTF-16/property parser;
they are not an expected-identity callback and confer no physical authority.
"""

from __future__ import annotations

import ctypes
from dataclasses import replace
import hashlib
from threading import Event
import time
from typing import Any, Callable

from rocell.application.arm_controller_resolution import _binding, _require
from rocell.application.physical_connection_contracts import (
    EvidenceOrigin,
    RoArmUsbSerialIdentity,
)
from rocell.application.physical_device_inventory import (
    DeviceInventoryBatch,
    InventoryDeviceClass,
    InventorySource,
    NormalizedDeviceCandidate,
)
from rocell.providers.windows.arm_feedback_worker import ReviewedControllerBinding
from rocell.providers.windows import controller_metadata as cm

SCENARIOS = frozenset(
    {"nominal", "identity-change-preopen", "identity-change", "malformed-metadata"}
)
_COM_GUID_TEXT = "86e0d1e0-8089-11d0-9ce4-08003e301f73"


def synthetic_native_identity(
    reviewed: ReviewedControllerBinding,
) -> RoArmUsbSerialIdentity:
    """Explicit modeled native identity, separate from a generic review hash."""
    binding = _binding(reviewed)
    _require(
        binding.origin is EvidenceOrigin.SYNTHETIC_REHEARSAL,
        "INCAPABLE_CONTROLLER_REQUIRED",
    )
    value = binding.identity
    suffix = (
        "INCAPABLE-CM-"
        + hashlib.sha256(value.unit_serial.encode("utf-8")).hexdigest()[:16]
    )
    return replace(
        value,
        persistent_instance_id=f"USB\\VID_{value.vid.upper()}&PID_{value.pid.upper()}\\{suffix}",
        persistent_port_path=f"\\\\?\\usb#vid_{value.vid}&pid_{value.pid}#{suffix}#{{{_COM_GUID_TEXT}}}",
    )


class _Function:
    __slots__ = ("_call", "argtypes", "restype")

    def __init__(self, call: Callable[..., int]) -> None:
        self._call = call
        self.argtypes: Any = None
        self.restype: Any = None

    def __call__(self, *args: Any) -> int:
        return self._call(*args)


def _u32(pointer: Any) -> Any:
    return ctypes.cast(pointer, ctypes.POINTER(ctypes.c_uint32)).contents


class _SealedCmLibrary:
    __slots__ = (
        "_producer",
        "CM_Get_Device_Interface_List_SizeW",
        "CM_Get_Device_Interface_ListW",
        "CM_Get_Device_Interface_PropertyW",
        "CM_Locate_DevNodeW",
        "CM_Get_DevNode_PropertyW",
    )

    def __init__(self, producer: IncapableControllerMetadataProducer) -> None:
        self._producer = producer
        self.CM_Get_Device_Interface_List_SizeW = _Function(self._list_size)
        self.CM_Get_Device_Interface_ListW = _Function(self._list)
        self.CM_Get_Device_Interface_PropertyW = _Function(self._interface)
        self.CM_Locate_DevNodeW = _Function(self._node)
        self.CM_Get_DevNode_PropertyW = _Function(self._node_property)

    def _wire(self) -> bytes:
        return (self._producer._identity.persistent_port_path + "\0\0").encode(
            "utf-16-le"
        )

    def _list_size(self, size: Any, guid: Any, device: Any, flags: int) -> int:
        _require(
            bytes(ctypes.cast(guid, ctypes.POINTER(cm._Guid)).contents)
            == bytes(cm._COM_GUID)
        )
        _require(device is None and flags == 0)
        _u32(size).value = len(self._wire()) // 2
        return cm._SUCCESS

    def _list(
        self, guid: Any, device: Any, buffer: Any, length: int, flags: int
    ) -> int:
        _require(device is None and flags == 0 and length * 2 == len(self._wire()))
        ctypes.memmove(buffer, self._wire(), len(self._wire()))
        return cm._SUCCESS

    def _node(self, result: Any, instance: str, flags: int) -> int:
        _require(
            flags == 0 and instance == self._producer._identity.persistent_instance_id
        )
        _u32(result).value = 1
        return cm._SUCCESS

    def _property(
        self,
        target: Any,
        key: Any,
        kind: Any,
        buffer: Any,
        size: Any,
        flags: int,
        *,
        node: bool,
    ) -> int:
        _require(flags == 0)
        raw_key = bytes(ctypes.cast(key, ctypes.POINTER(cm._PropertyKey)).contents)
        name = next(
            (name for name, (item, _) in cm._KEYS.items() if bytes(item) == raw_key),
            None,
        )
        _require(name is not None)
        assert name is not None
        _require(
            (name.startswith("driver_") and target == 1)
            if node
            else (
                not name.startswith("driver_")
                and target == self._producer._identity.persistent_port_path
            )
        )
        identity = self._producer._identity
        values = {
            "persistent_instance_id": identity.persistent_instance_id,
            "port_name": identity.port_name,
            "vid": identity.vid,
            "pid": identity.pid,
            "driver_provider": identity.driver.provider,
            "driver_service": identity.driver.service,
            "driver_version": identity.driver.version,
            "driver_inf": identity.driver.package_or_inf_path,
        }
        value = values[name]
        if name == "driver_version" and self._producer._drift():
            value = "INCAPABLE-CHANGED-DRIVER"
        raw = (
            int(value, 16).to_bytes(2, "little")
            if name in {"vid", "pid"}
            else (value + "\0").encode("utf-16-le")
        )
        if name == "port_name" and self._producer._scenario == "malformed-metadata":
            raw = (
                b"\x00\xd8\x00\x00"  # Unpaired surrogate rejected by actual CM decoder.
            )
        _u32(kind).value = cm._KEYS[name][1]
        if buffer is None:
            _u32(size).value = len(raw)
            return cm._BUFFER_SMALL
        _require(_u32(size).value == len(raw))
        ctypes.memmove(buffer, raw, len(raw))
        _u32(size).value = len(raw)
        return cm._SUCCESS

    def _interface(self, *args: Any) -> int:
        return self._property(*args, node=False)

    def _node_property(self, *args: Any) -> int:
        return self._property(*args, node=True)


class IncapableControllerMetadataProducer:
    """One acquirer, two bounded acquisitions; no caller-provided function hooks."""

    __slots__ = ("_identity", "_scenario", "_inventory_calls", "_issued", "_batch")

    def __init__(
        self, reviewed: ReviewedControllerBinding, *, scenario: str = "nominal"
    ) -> None:
        binding = _binding(reviewed)
        _require(
            binding.origin is EvidenceOrigin.SYNTHETIC_REHEARSAL,
            "INCAPABLE_CONTROLLER_REQUIRED",
        )
        _require(
            type(scenario) is str and scenario in SCENARIOS,
            "INCAPABLE_CONTROLLER_SCENARIO_INVALID",
        )
        _require(
            binding.identity.persistent_port_path.startswith("\\\\?\\"),
            "NATIVE_INTERFACE_PATH_REQUIRED",
        )
        self._identity, self._scenario = binding.identity, scenario
        self._inventory_calls, self._issued = 0, False
        value = self._identity
        candidate = NormalizedDeviceCandidate(
            InventoryDeviceClass.SERIAL,
            InventorySource.INJECTED_SERIAL_ENUMERATOR,
            "Incapable arm controller metadata",
            value.vid,
            value.pid,
            value.unit_serial,
            f"USB VID:PID={value.vid}:{value.pid} SER={value.unit_serial}",
            (f"usb-unit:{value.vid}:{value.pid}:{value.unit_serial}",),
            value.port_name,
            "INCAPABLE_FIXTURE",
            "INCAPABLE_FIXTURE",
            None,
            (),
        )
        self._batch = DeviceInventoryBatch(
            InventoryDeviceClass.SERIAL,
            InventorySource.INJECTED_SERIAL_ENUMERATOR,
            (candidate,),
            (),
            True,
        )

    def _drift(self) -> bool:
        return self._scenario == "identity-change-preopen" or (
            self._scenario == "identity-change" and self._inventory_calls >= 3
        )

    def _inventory(self) -> DeviceInventoryBatch:
        _require(self._inventory_calls < 4, "CONTROLLER_RESOLUTION_CALL_LIMIT")
        self._inventory_calls += 1
        return self._batch

    def acquirer(
        self,
        *,
        deadline_ns: int,
        cancellation: Event,
        monotonic_ns: Callable[[], int] = time.monotonic_ns,
    ) -> cm.WindowsControllerMetadataAcquirer:
        _require(not self._issued, "CONTROLLER_RESOLUTION_CALL_LIMIT")
        self._issued = True
        return cm.WindowsControllerMetadataAcquirer(
            deadline_ns=deadline_ns,
            cancellation=cancellation,
            monotonic_ns=monotonic_ns,
            api=cm._CmApi(_library=_SealedCmLibrary(self)),
            inventory=self._inventory,
        )
