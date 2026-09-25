"""Imported capture tampering cannot manufacture clean evidence."""
from threading import Event

import pytest

from rocell.application.first_motion_capture import capture_first_motion_window
from rocell.application.first_motion_capture_validation import validate_clean_first_motion_capture
from test_first_motion_measurement_binding import setup


def fixture(tmp_path,phase='baseline'):
    _,request=setup(tmp_path)
    tick=[2_000_000_000]
    def read(n,timeout):
        tick[0]+=timeout*1_000_000
        return b'raw-invalid-pose\n'
    capture=capture_first_motion_window(request,phase,read_once=read,cancellation=Event(),
        clock_ns=lambda:tick[0],command_completed_ns=2_000_000_000 if phase=='post' else None)
    return request,capture


@pytest.mark.parametrize('phase',['baseline','post'])
def test_actual_collector_envelope_validates_without_qualifying_pose(tmp_path,phase):
    request,capture=fixture(tmp_path,phase)
    raw=validate_clean_first_motion_capture(request,capture,phase=phase,
        command_completed_ns=2_000_000_000 if phase=='post' else None)
    assert raw.startswith(b'raw-invalid-pose\n')
    # Capture integrity and completion are not valid pose/physical evidence.
    assert capture['coverage']['counts']['POSE_TELEMETRY']==0


@pytest.mark.parametrize('field,value',[
    ('request_sha256','f'*64),('status','CANCELLED'),('errors',['failure']),
    ('physical_movement_verified',True),('sample_freshness_verified',True),
    ('read_calls',True),('within_deadline_bytes',0),('late_completion_bytes',True),
    ('window_deadline_ns',2_999_999_999),('started_ns',True),('coverage',{}),
    ('extra','unexpected'),('baseline_framing',{}),
])
def test_changed_envelope_refused(tmp_path,field,value):
    request,capture=fixture(tmp_path)
    capture[field]=value
    with pytest.raises(ValueError): validate_clean_first_motion_capture(request,capture,phase='baseline')


@pytest.mark.parametrize('fault',['digest','chunks','read-gap','read-time','size'])
def test_original_bytes_and_windows_are_checked(tmp_path,fault):
    request,capture=fixture(tmp_path)
    if fault=='digest': capture['raw']['sha256']='f'*64
    if fault=='chunks': capture['raw']['base64_chunks']=['x'*1025]
    if fault=='read-gap': capture['read_windows'][0][0]=1
    if fault=='read-time': capture['read_windows'][0][2]=1
    if fault=='size': capture['raw']['bytes']=True
    with pytest.raises(ValueError): validate_clean_first_motion_capture(request,capture,phase='baseline')
