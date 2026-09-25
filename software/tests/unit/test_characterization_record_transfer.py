import hashlib
import pytest
from rocell.application.characterization_record_transfer import RecordTransfer


def make(data):
    return RecordTransfer(boot='11'*16,campaign='22'*32,leg=0,size=len(data),sha256=hashlib.sha256(data).hexdigest())


def append(owner,data,offset=0,**changes):
    args=dict(boot='11'*16,campaign='22'*32,leg=0,offset=offset,data=data)
    args.update(changes);owner.append(**args)


def test_maximum_record():
    raw=b'x'*11000;owner=make(raw)
    for offset in range(0,len(raw),1024):append(owner,raw[offset:offset+1024],offset)
    assert owner.finish()==raw
    with pytest.raises(ValueError):owner.finish()


@pytest.mark.parametrize('case',['boot','campaign','offset','oversize','digest','partial','replay'])
def test_transfer_fault_latches(case):
    owner=make(b'abc')
    with pytest.raises(ValueError):
        if case=='digest':append(owner,b'xyz');owner.finish()
        elif case=='partial':append(owner,b'a');owner.finish()
        elif case=='replay':append(owner,b'a');append(owner,b'a')
        elif case=='oversize':append(owner,b'x'*1025)
        else:append(owner,b'abc',**{'boot':{'boot':'33'*16},'campaign':{'campaign':'33'*32},
                                  'offset':{'offset':1}}[case])
    with pytest.raises(ValueError):owner.finish()
