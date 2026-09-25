"""Route checks with a substituted exchange: no network access."""
import pytest
from rocell.application.held_pair_transport import HeldPairHTTPReader, STATUS, RECORD


@pytest.mark.parametrize('path,maximum,timeout', [('/js',1024,3),
    (RECORD+'34',9216,3),(STATUS,1025,3),(RECORD+'0',9217,3),
    (STATUS,1024,4),(STATUS,1024,float('nan')),([],1024,3)])
def test_reader_rejects_and_latches(path,maximum,timeout):
    reader=HeldPairHTTPReader('127.0.0.1');calls=[]
    reader._get=lambda *a,**k: calls.append(a)
    with pytest.raises(ValueError):
        reader(path,maximum_bytes=maximum,timeout_seconds=timeout)
    with pytest.raises(ValueError):
        reader(STATUS,maximum_bytes=1024,timeout_seconds=3)
    assert reader.failed and not calls


def test_reader_allows_only_bounded_gets():
    reader=HeldPairHTTPReader('127.0.0.1');calls=[]
    def exchange(path,**kwargs):
        calls.append((path,kwargs));return b'{}'
    reader._get=exchange
    for path,maximum in [(STATUS,1024),(RECORD+'0',9216),(RECORD+'33',9216)]:
        assert reader(path,maximum_bytes=maximum,timeout_seconds=3)==b'{}'
    assert len(calls)==3 and not reader.failed
