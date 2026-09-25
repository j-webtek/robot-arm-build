"""Bounded read-only Windows IPv4 neighbor lookup; no ARP writes or resolution.

Uses the documented GetIpNetTable ABI. DLL loading is lazy and restricted to
System32. Cached neighbor records are consistency evidence, not authentication.
"""
import ctypes
import ipaddress
import os

MAX_TABLE_BYTES = 65536


class Row(ctypes.Structure):
    _fields_ = [('index',ctypes.c_uint32), ('length',ctypes.c_uint32),
                ('physical',ctypes.c_ubyte*8), ('address',ctypes.c_uint32),
                ('kind',ctypes.c_uint32)]


class Table(ctypes.Structure):
    _fields_ = [('count',ctypes.c_uint32), ('rows',Row*1)]


def parse_neighbor(raw, address):
    """Reject ambiguous, invalid or truncated target records; disclose one MAC."""
    packed=ipaddress.IPv4Address(address).packed
    offset=Table.rows.offset
    if not offset <= len(raw) <= MAX_TABLE_BYTES:
        raise ValueError('Invalid neighbor table size')
    count=ctypes.c_uint32.from_buffer_copy(raw).value
    stride=ctypes.sizeof(Row)
    if offset+count*stride > len(raw):
        raise ValueError('Truncated neighbor table')
    matches=[]
    for i in range(count):
        begin=offset+i*stride
        # dwAddr is network-order data in DWORD storage: compare its raw bytes.
        if raw[begin+Row.address.offset:begin+Row.address.offset+4] != packed:
            continue
        row=Row.from_buffer_copy(raw,begin)
        if row.kind not in (3,4) or row.length != 6 or not row.index:
            return None
        mac=bytes(row.physical[:6])
        if mac==b'\x00'*6 or mac[0]&1:
            return None
        matches.append('-'.join(f'{v:02X}' for v in mac))
    return matches[0] if len(matches)==1 else None


def lookup_neighbor(address, *, get_table=None):
    """One bounded OS query. Overflow/errors fail closed without allocation retry."""
    ipaddress.IPv4Address(address)
    if get_table is None:
        if os.name!='nt':
            raise OSError('Windows neighbor API required')
        library=ctypes.WinDLL('iphlpapi.dll',winmode=0x00000800)
        get_table=library.GetIpNetTable
        get_table.argtypes=(ctypes.c_void_p,ctypes.POINTER(ctypes.c_uint32),ctypes.c_int)
        get_table.restype=ctypes.c_uint32
    buffer=ctypes.create_string_buffer(MAX_TABLE_BYTES)
    size=ctypes.c_uint32(MAX_TABLE_BYTES)
    code=get_table(buffer,ctypes.byref(size),False)
    if code==232:  # ERROR_NO_DATA
        return None
    if code!=0 or not Table.rows.offset <= size.value <= MAX_TABLE_BYTES:
        raise OSError('Neighbor table query unavailable or exceeds budget')
    return parse_neighbor(buffer.raw[:size.value],address)
