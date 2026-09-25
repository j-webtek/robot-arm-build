import base64
import hashlib
import json
import pytest
from rocell.application.coordinated_trace_review import review_servo_packets


def report():
    rows=[]
    for load in (45,46,45):
        raw=json.dumps(dict(T=1051,e=1.67,tE=load)).encode()
        rows.append(dict(status='SUCCEEDED',response_base64=base64.b64encode(raw).decode(),
                         response_sha256=hashlib.sha256(raw).hexdigest()))
    return dict(run=dict(feedback_originals=rows))


def test_varying_load_does_not_prove_position_freshness_or_health():
    r=review_servo_packets(report())
    assert r['retained_packet_count']==3 and r['whole_packet_unique_count']==2
    assert r['fields']['e']['unique_values']==[1.67]
    assert r['fields']['tE']['unique_values']==[45,46]
    assert r['fields']['torswitchE']['missing_samples']==3
    assert r['fields']['v']['minimum'] is None
    assert not r['per_servo_acquisition_freshness_verified']
    assert not r['actuator_health_verified']


def test_changed_original_packet_rejected():
    r=report();r['run']['feedback_originals'][0]['response_sha256']='bad'
    with pytest.raises(ValueError,match='hash mismatch'):review_servo_packets(r)
