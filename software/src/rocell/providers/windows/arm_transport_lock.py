"""Cooperative cross-process exclusion for participating bench transports.

Not a physical stop. External programs, other computers and legacy entry points
do not honor this mutex. Abandoned ownership is refused, never treated as clean.
"""
import ctypes
from contextlib import contextmanager

NAME = 'Global\\RoCell-Arm-FCE8C0F8D538-Transport-v1'


@contextmanager
def arm_transport_lock():
    api=ctypes.WinDLL('kernel32.dll',winmode=0x800,use_last_error=True)
    api.CreateMutexW.argtypes=(ctypes.c_void_p,ctypes.c_int,ctypes.c_wchar_p)
    api.CreateMutexW.restype=ctypes.c_void_p
    api.WaitForSingleObject.argtypes=(ctypes.c_void_p,ctypes.c_uint32)
    api.WaitForSingleObject.restype=ctypes.c_uint32
    api.ReleaseMutex.argtypes=(ctypes.c_void_p,)
    api.ReleaseMutex.restype=ctypes.c_int
    api.CloseHandle.argtypes=(ctypes.c_void_p,)
    api.CloseHandle.restype=ctypes.c_int
    handle=api.CreateMutexW(None,False,NAME)
    if not handle:
        raise RuntimeError('ARM_TRANSPORT_LOCK_UNAVAILABLE')
    acquired=False
    try:
        status=api.WaitForSingleObject(handle,0)
        acquired=status in (0,0x80)
        if status!=0:
            raise RuntimeError('ARM_TRANSPORT_ABANDONED' if status==0x80 else 'ARM_TRANSPORT_BUSY_OR_UNAVAILABLE')
        yield
    finally:
        released=not acquired or bool(api.ReleaseMutex(handle))
        closed=bool(api.CloseHandle(handle))
        if not released or not closed:
            raise RuntimeError('ARM_TRANSPORT_LOCK_CLEANUP_FAILED')
