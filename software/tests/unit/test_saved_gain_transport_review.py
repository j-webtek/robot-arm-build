import base64
import importlib.util
from pathlib import Path
import pytest
from rocell.application.first_motion_contract import canonical


def load_review():
    path=Path(__file__).resolve().parents[2]/'scripts/review_gain_transport.py'
    spec=importlib.util.spec_from_file_location('saved_gain_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    return module.review


@pytest.mark.parametrize('retained',[False,True])
def test_complete_post_not_confused_with_complete_workflow(retained):
    document=dict(schema='rocell.elbow_gain.v1',boot_id='11'*16,capture_id='elbow-gain-1',
        profile_id='roarm-m3-gain-reference-e8d5fc95a60f',byte_order='little',
        complete=True,reason='GAIN_CAPTURED',reads=[
            [14,21+i,1,[i,100+10*i,101+10*i,1,0,True,value]]
            for i,value in enumerate(('20','20','00'))])
    raw=base64.b64encode(canonical(document)).decode()
    report=dict(schema='rocell.gain_capture_transport.v1',
        subject=dict(expected_boot='11'*16,expected_capture='elbow-gain-1'),
        responses=[dict(method='POST',raw_base64=raw)],category='INCONCLUSIVE',error_type='TimeoutError')
    if retained:
        report['responses'].append(dict(method='GET',raw_base64=raw))
        report['category']='CONTROLLER_REPORTED_GAINS';report.pop('error_type')
    actual=load_review()(report)
    assert actual['post_assessment']['gains_raw']==dict(P=32,D=32,I=0)
    assert actual['capture_workflow_complete'] is retained
    assert actual['retained_copy_verified'] is retained
    assert actual['hardware_access'] is actual['gain_changes_authorized'] is False
    report['responses'][0]['method']='GET'
    with pytest.raises(ValueError):load_review()(report)
