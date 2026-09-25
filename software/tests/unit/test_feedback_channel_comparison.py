import base64
import hashlib
import json
import pytest
from rocell.application.feedback_channel_comparison import compare_feedback_channels


def packet(channel,elbow=1.6,started=100,finished=200):
    raw=json.dumps(dict(T=1051,b=0,s=0,e=elbow,t=0,r=0,g=3.14)).encode()
    if channel=='SERIAL':raw+=b'\n'
    return dict(channel=channel,started_ns=started,finished_ns=finished,
        response_base64=base64.b64encode(raw).decode(),response_sha256=hashlib.sha256(raw).hexdigest())


def test_agreement_is_not_freshness_or_motion_authority():
    r=compare_feedback_channels(packet('HTTP'),packet('SERIAL'))
    assert r['status']=='PACKETS_AGREE'
    assert not r['encoder_freshness_verified'] and not r['motion_authorized']


def test_disagreement_retains_signed_difference():
    r=compare_feedback_channels(packet('HTTP'),packet('SERIAL',1.61))
    assert r['status']=='PACKETS_DIFFER'
    assert r['serial_minus_http_rad']['e']==pytest.approx(.01)


def test_old_capture_does_not_qualify_agreement():
    r=compare_feedback_channels(packet('HTTP'),packet('SERIAL',started=2_000_000_000,finished=2_000_000_100))
    assert r['status']=='CAPTURES_TOO_FAR_APART'


@pytest.mark.parametrize('fault',['hash','channel','time','nan'])
def test_bad_capture_rejected(fault):
    s=packet('SERIAL',float('nan') if fault=='nan' else 1.6)
    if fault=='hash':s['response_sha256']='bad'
    if fault=='channel':s['channel']='HTTP'
    if fault=='time':s['finished_ns']=1
    with pytest.raises(ValueError):compare_feedback_channels(packet('HTTP'),s)
