import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.pose_observation_capture import pose_exchange,capture_pose,PoseHTTPStatus
from test_servo_diagnostic_start_http import once_server
from test_servo_diagnostic_http import response


def test_loopback_exact_capture_and_record():
    body=canonical(dict(boot_id='11'*16,scan_id='pose-1'))
    for method,path,payload,status in [('POST','/rocell/pose/capture',body,b'202 Accepted'),
            ('GET','/rocell/pose/record?index=0',b'',b'200 OK')]:
        with once_server(response(b'{}',status=status)) as (port,requests):
            assert pose_exchange('127.0.0.1',method,path,payload,port=port)==b'{}'
        assert len(requests)==1 and requests[0][2]==payload
        assert requests[0][0][0]==f'{method} {path} HTTP/1.1'.encode()


@pytest.mark.parametrize('failure',range(5))
def test_acquisition_failure_stops_without_retry(tmp_path,failure):
    calls=[]
    def exchange(*args):
        index=len(calls);calls.append(args)
        if index==failure:raise OSError('private detail')
        return canonical(dict(status='POSE_QUEUED',retry_allowed=False)) if index==0 else b'{}'
    result=capture_pose(tmp_path,address='127.0.0.1',expected_boot='11'*16,scan_id='pose-1',
        authorized=True,exchange=exchange,pause=lambda seconds:None)
    assert len(calls)==failure+1
    assert result['report']['category']=='INCONCLUSIVE'
    assert 'private detail' not in str(result)
    before=list(calls)
    with pytest.raises(Exception):
        capture_pose(tmp_path,address='127.0.0.1',expected_boot='11'*16,scan_id='pose-2',
            authorized=True,exchange=exchange,pause=lambda seconds:None)
    assert calls==before


def test_no_approval_no_io(tmp_path):
    with pytest.raises(ValueError,match='approval'):
        capture_pose(tmp_path,address='127.0.0.1',expected_boot='11'*16,scan_id='pose-1')
    assert not list(tmp_path.iterdir())


def test_non_success_capture_retains_status_only_and_no_retry(tmp_path):
    with once_server(response(b'private controller detail',status=b'409 Conflict')) as (port, requests):
        with pytest.raises(PoseHTTPStatus) as exc:
            pose_exchange('127.0.0.1','POST','/rocell/pose/capture',
                canonical(dict(boot_id='11'*16,scan_id='pose-1')),port=port)
    assert exc.value.status == 409
    assert 'private controller detail' not in str(exc.value)
    assert len(requests) == 1
    calls=[]
    def rejected(*args):
        calls.append(args)
        raise PoseHTTPStatus(409)
    result=capture_pose(tmp_path,address='127.0.0.1',expected_boot='11'*16,
        scan_id='pose-1',authorized=True,exchange=rejected)
    assert result['report']['http_status']==409
    assert result['report']['responses']==[]
    assert len(calls)==1
