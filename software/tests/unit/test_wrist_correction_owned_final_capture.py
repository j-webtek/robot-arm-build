import json
import pytest
from test_wrist_correction_serial_connection import owner,select
from rocell.arm.protocol import encode_line
from rocell.application.wrist_correction_owned_final_capture import retain_owned_final_capture


@pytest.mark.parametrize('fault',[None,'cancel','empty','budget'])
def test_owned_capture_once_no_dispatch_and_cumulative_reads(tmp_path,monkeypatch,fault):
    connection,kernel,permit,request,reader,clock=owner(tmp_path,monkeypatch)
    connection.open();select(connection,permit,request,reader,clock)
    joints=reader._originals[0][0].to_dict()['draft']['expected_start_joints_rad']
    kernel.input=b'' if fault=='empty' else encode_line(dict(T=1051,x=0,y=0,z=0,tit=0,**joints))
    original=kernel.ReadFile
    def read(*args):
        clock[0]+=20_000_000
        return original(*args)
    monkeypatch.setattr(kernel,'ReadFile',read)
    if fault=='cancel': permit._binding._cancel.set()
    if fault=='budget': connection._read_calls['baseline']=request.runtime_body()['limits']['maximum_baseline_reads']
    before=connection.snapshot()['read_calls']['baseline']
    try:
        result=retain_owned_final_capture(connection,permit,
            idle_wait=lambda seconds:clock.__setitem__(0,clock[0]+round(seconds*1e9)))
        assert result['status']==('FINAL_CAPTURE_RETAINED_NOT_ADMITTED' if fault is None else 'HELD_FINAL_CAPTURE')
        retained=json.loads((tmp_path/result['retention']['file']).read_bytes())
        assert retained['capture']==result['capture'] and not retained['motion_authorized']
        if fault=='budget':
            assert result['capture']['read_calls']==1  # refused by connection before IO
            assert connection.snapshot()['read_calls']['baseline']==before
        else:
            assert connection.snapshot()['read_calls']['baseline']-before==result['capture']['read_calls']
        assert not kernel.writes and permit._binding._state=='HELD'
        with pytest.raises(ValueError): retain_owned_final_capture(connection,permit)
        with pytest.raises(ValueError): permit.selected_payload()
    finally:
        assert connection.close(2000).all_handles_closed
    assert kernel.closed==[202,201,101]


def test_changed_selection_refused_before_read_and_held(tmp_path,monkeypatch):
    connection,kernel,permit,request,reader,clock=owner(tmp_path,monkeypatch)
    connection.open();select(connection,permit,request,reader,clock)
    path=tmp_path/permit._binding._records[-1][0]
    path.write_bytes(b'{}')
    try:
        with pytest.raises(ValueError,match='selection changed'):
            retain_owned_final_capture(connection,permit)
        assert connection.snapshot()['read_calls']['baseline']==0
        assert permit._binding._state=='HELD' and not kernel.writes
    finally: connection.close(2000)


@pytest.mark.parametrize('stage',['claim','result'])
def test_retention_failure_never_leaves_dispatch_available(tmp_path,monkeypatch,stage):
    from rocell.application import wrist_correction_owned_final_capture as module
    connection,kernel,permit,request,reader,clock=owner(tmp_path,monkeypatch)
    connection.open();select(connection,permit,request,reader,clock)
    publish=module.publish_reservation_bytes
    def fail(root,name,raw,**kwargs):
        if (stage=='claim' and name.endswith('capture-claim.json')) or (stage=='result' and name.endswith('capture.original.json')):
            raise OSError('synthetic storage failure')
        return publish(root,name,raw,**kwargs)
    monkeypatch.setattr(module,'publish_reservation_bytes',fail)
    kernel.input=b''
    try:
        with pytest.raises(OSError):
            module.retain_owned_final_capture(connection,permit,
                idle_wait=lambda seconds:clock.__setitem__(0,clock[0]+round(seconds*1e9)))
        assert permit._binding._state=='HELD' and not kernel.writes
        if stage=='claim': assert connection.snapshot()['read_calls']['baseline']==0
        with pytest.raises(ValueError): permit.selected_payload()
    finally: connection.close(2000)
