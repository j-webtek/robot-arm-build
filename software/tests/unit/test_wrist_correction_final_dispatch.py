import pytest
from test_wrist_correction_serial_connection import owner,select
from rocell.arm.protocol import encode_line
from rocell.application.wrist_correction_owned_final_capture import retain_owned_final_capture


def prepared(tmp_path,monkeypatch):
    connection,kernel,permit,request,reader,clock=owner(tmp_path,monkeypatch)
    connection.open();select(connection,permit,request,reader,clock)
    joints=reader._originals[0][0].to_dict()['draft']['expected_start_joints_rad']
    kernel.input=encode_line(dict(T=1051,x=0,y=0,z=0,tit=0,**joints))
    read=kernel.ReadFile
    def timed(*args):
        clock[0]+=20_000_000
        return read(*args)
    monkeypatch.setattr(kernel,'ReadFile',timed)
    retain_owned_final_capture(connection,permit,
        idle_wait=lambda s:clock.__setitem__(0,clock[0]+round(s*1e9)))
    return connection,kernel,permit,request,reader,clock


def test_one_native_fake_write_consumes_final_evidence_not_old_timestamp(tmp_path,monkeypatch):
    c,k,p,r,reader,clock=prepared(tmp_path,monkeypatch)
    old=p._binding._acquired
    assert clock[0]-old>100_000_000
    try:
        p.prepare_final_dispatch(c)
        payload=p.selected_payload()
        assert c.write_once(payload)==len(payload)
        assert k.writes==[payload] and p._binding._acquired==old
        assert (tmp_path/(r.to_dict()['attempt_id']+'-wrist-correction-final-consumed.json')).is_file()
        assert not (tmp_path/(r.to_dict()['attempt_id']+'-wrist-correction-consumed.json')).exists()
        with pytest.raises(ValueError): c.write_once(payload)
        with pytest.raises(ValueError): p.prepare_final_dispatch(c)
    finally: c.close(2000)


@pytest.mark.parametrize('fault',['stale','capture','revoke','cancel','wrong_connection'])
def test_preparation_faults_never_write(tmp_path,monkeypatch,fault):
    c,k,p,r,_,clock=prepared(tmp_path,monkeypatch)
    if fault=='stale': clock[0]+=101_000_000
    elif fault=='capture': (tmp_path/(r.to_dict()['attempt_id']+'-wrist-correction-final-capture.original.json')).write_bytes(b'{}')
    elif fault=='revoke': p.revoke()
    elif fault=='cancel': p._binding._cancel.set()
    elif fault=='wrong_connection': c._request=None
    try:
        with pytest.raises(ValueError): p.prepare_final_dispatch(c)
        assert not k.writes
    finally: c.close(2000)


@pytest.mark.parametrize('fault',['age','cancel','record'])
def test_final_dispatch_rechecks_after_preparation(tmp_path,monkeypatch,fault):
    c,k,p,r,_,clock=prepared(tmp_path,monkeypatch)
    try:
        p.prepare_final_dispatch(c);payload=p.selected_payload()
        if fault=='age': clock[0]+=101_000_000
        elif fault=='cancel': p._binding._cancel.set()
        else: (tmp_path/(r.to_dict()['attempt_id']+'-wrist-correction-final-reservation.json')).write_bytes(b'{}')
        with pytest.raises(ValueError): c.write_once(payload)
        assert not k.writes
    finally: c.close(2000)
