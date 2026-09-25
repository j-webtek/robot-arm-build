import ctypes
import ipaddress
import pytest
from rocell.providers.windows.ipv4_neighbor import Row,Table,parse_neighbor,lookup_neighbor,MAX_TABLE_BYTES

ADDRESS='192.168.0.225'


def row(address=ADDRESS,kind=3,length=6,mac=b'\xfc\xe8\xc0\xf8\xd5\x38'):
    value=Row();value.index=7;value.kind=kind;value.length=length
    value.physical[:len(mac)]=mac
    raw=bytearray(bytes(value))
    raw[Row.address.offset:Row.address.offset+4]=ipaddress.IPv4Address(address).packed
    return bytes(raw)


def table(*rows):
    return len(rows).to_bytes(4,'little')+b'\0'*(Table.rows.offset-4)+b''.join(rows)


def test_abi_and_matching():
    assert ctypes.sizeof(Row)==24 and Table.rows.offset==4
    assert parse_neighbor(table(row('192.168.0.1'),row()),ADDRESS)=='FC-E8-C0-F8-D5-38'
    assert parse_neighbor(table(),ADDRESS) is None
    assert parse_neighbor(table(row('192.168.0.25')),ADDRESS) is None


@pytest.mark.parametrize('data',[table(row(),row()),table(row(kind=2)),table(row(length=8)),
    table(row(mac=b'\0'*6)),table(row(mac=b'\xff'*6)),table(row(kind=1))])
def test_ambiguous_or_invalid_fails_closed(data):
    assert parse_neighbor(data,ADDRESS) is None


@pytest.mark.parametrize('data',[b'',b'\xff'*4,table(row())[:-1],b'\0'*(MAX_TABLE_BYTES+1)],ids=['empty','bad-count','truncated','oversized'])
def test_bounds(data):
    with pytest.raises(ValueError):parse_neighbor(data,ADDRESS)


@pytest.mark.parametrize('code',[0,232,122,87])
def test_native_wrapper_single_call(code):
    calls=[]
    def fake(buffer,size,order):
        calls.append(1)
        raw=table(row())
        ctypes.memmove(buffer,raw,len(raw))
        ctypes.cast(size,ctypes.POINTER(ctypes.c_uint32)).contents.value=len(raw)
        return code
    if code in (0,232):
        assert lookup_neighbor(ADDRESS,get_table=fake)==('FC-E8-C0-F8-D5-38' if code==0 else None)
    else:
        with pytest.raises(OSError):lookup_neighbor(ADDRESS,get_table=fake)
    assert len(calls)==1
