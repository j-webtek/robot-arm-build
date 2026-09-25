"""Read a legacy USB serial driver's PortName; never open the COM endpoint.

Some drivers omit serial interface properties. The fallback uses the exact
present CM device instance, its USB ID components, and its read-only registry
PortName. Neither a friendly name nor pyserial metadata supplies native fields.
This remains a point-in-time observation, not an atomic device-handle binding.
"""

import ctypes
import re

from rocell.application.arm_controller_resolution import _require


_INSTANCE = re.compile(
    r"USB\\VID_([0-9A-F]{4})&PID_([0-9A-F]{4})(?:&MI_[0-9A-F]{2})?"
    r"\\[A-Z0-9&_.+\-]{1,200}",
    re.IGNORECASE,
)
_CAPACITY = 2048


def read_legacy_usb_metadata(instance, check, *, library=None):
    """Return independently observed (port, vid, pid), or None if absent.

    Fixed-size RegQueryValueExW refuses oversized/wrong-type values. Registry
    handles are closed even on cancellation; there are no writes or retries.
    An injected library is solely an incapable ABI test seam.
    """
    match = _INSTANCE.fullmatch(instance) if type(instance) is str else None
    if match is None:
        return None
    check()
    dll = ctypes.WinDLL("advapi32.dll", winmode=0x800) if library is None else library
    ptr, u32 = ctypes.c_void_p, ctypes.c_uint32
    dll.RegOpenKeyExW.argtypes = [ptr, ctypes.c_wchar_p, u32, u32, ctypes.POINTER(ptr)]
    dll.RegOpenKeyExW.restype = ctypes.c_long
    dll.RegQueryValueExW.argtypes = [
        ptr,
        ctypes.c_wchar_p,
        ptr,
        ctypes.POINTER(u32),
        ptr,
        ctypes.POINTER(u32),
    ]
    dll.RegQueryValueExW.restype = ctypes.c_long
    dll.RegCloseKey.argtypes = [ptr]
    dll.RegCloseKey.restype = ctypes.c_long
    check()
    handle = ptr()
    path = "SYSTEM\\CurrentControlSet\\Enum\\" + instance + "\\Device Parameters"
    # HKEY_LOCAL_MACHINE is a sign-extended predefined handle; KEY_QUERY_VALUE
    # cannot create keys or change driver/device configuration.
    status = dll.RegOpenKeyExW(ptr(-2147483646), path, 0, 1, ctypes.byref(handle))
    if status != 0:
        check()
        _require(status in (2, 3), "USB_REGISTRY_OPEN_FAILED")
        return None
    try:
        check()
        kind, size = u32(), u32(_CAPACITY)
        buffer = (ctypes.c_ubyte * _CAPACITY)()
        status = dll.RegQueryValueExW(
            handle, "PortName", None, ctypes.byref(kind), buffer, ctypes.byref(size)
        )
        check()
        if status == 2:
            return None
        _require(
            status == 0
            and kind.value == 1
            and 2 <= size.value <= _CAPACITY
            and size.value % 2 == 0,
            "USB_REGISTRY_VALUE_INVALID",
        )
        try:
            value = bytes(buffer[: size.value]).decode("utf-16-le", errors="strict")
        except UnicodeError:
            _require(False, "USB_REGISTRY_VALUE_INVALID")
        _require(
            re.fullmatch(r"COM[1-9][0-9]{0,3}\x00", value) is not None,
            "USB_REGISTRY_PORT_INVALID",
        )
        port = value[:-1]
        _require(int(port[3:]) <= 4096, "USB_REGISTRY_PORT_INVALID")
        return port, match[1].lower(), match[2].lower()
    finally:
        # Cleanup is not prevented by an expired deadline or cancellation.
        _require(dll.RegCloseKey(handle) == 0, "USB_REGISTRY_CLOSE_FAILED")
