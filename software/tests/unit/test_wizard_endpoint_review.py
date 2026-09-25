"""Public request-review action is inspection only, including expired requests."""

import json
from pathlib import Path
import pytest
from rocell.application.wizard_worker import run
from rocell.application.wizard_endpoint_review import review_endpoint_request
from rocell.application.wizard_actions import ACTION_BY_ID,validate_action_input
from test_endpoint_trial_contract import request


def test_public_review_shows_exact_target_and_no_authority():
    req = request()
    result = run(Path(__file__).resolve().parents[3],'movement_endpoint_review',
                 {'request_json':req.canonical_bytes.decode()},'cell')
    report = result['steps'][0]['report']
    assert report['request_sha256']==req.request_sha256
    assert report['axes'][0]=={'axis':'x_mm','unit':'mm','start':0,'target':1,'delta':1}
    assert len(report['axes'])==6
    assert report['spd']==.05 and 'not mm/s' in report['speed_meaning']
    assert len(report['operator_checks'])+len(report['engineering_checks'])==12
    assert report['physical_authority'] is report['motion_approved'] is False
    assert result['device_open_count']==result['serial_write_count']==0


@pytest.mark.parametrize('raw',['{}','{"T":104}', '{"x":1,"x":2}'])
def test_invalid_json_cannot_become_request_review(raw):
    with pytest.raises(ValueError):
        validate_action_input(ACTION_BY_ID['movement_endpoint_review'],{'request_json':raw})


def test_authority_claim_is_not_accepted_for_display():
    data = request().to_dict()
    data['physical_authority']=True
    with pytest.raises(ValueError): review_endpoint_request(json.dumps(data))
