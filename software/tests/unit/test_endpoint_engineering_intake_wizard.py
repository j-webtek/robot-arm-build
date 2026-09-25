"""Public intake/export flow with synthetic draft and self-reported decisions."""

import json
from pathlib import Path
import pytest

from rocell.application.endpoint_trial_draft import EndpointTrialDraft
from rocell.application.wizard_actions import WizardError
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import make_service, _run, _ticket
from test_endpoint_trial_contract import request


def values(decision='UNKNOWN'):
    return {'draft_json':EndpointTrialDraft.from_request(request()).canonical_bytes.decode(),
        'reviewer_id':'synthetic-reviewer', 'check':'noncontact_route_review',
        'decision':decision, 'detail':'Synthetic test only; not hardware approval.'}


@pytest.mark.parametrize('decision',['UNKNOWN','DENIED','APPROVED'])
def test_public_record_and_verified_export(make_service,decision):
    service,runner,_ = make_service(mode='physical')
    preview = _ticket(service,'record_endpoint_engineering_review',values(decision))
    assert 'self-reported' in ' '.join(preview['effects'])
    completed = _run(service,'record_endpoint_engineering_review',values(decision))
    assert completed['status'] == 'SUCCEEDED',completed
    report = completed['result']['steps'][0]['report']
    assert report['status'] == 'ENGINEERING_DECISION_RECORDED_NOT_AUTHORIZED'
    assert report['review']['decision'] == decision
    assert report['review']['recorded_ns'] > 1
    assert report['reviewer_identity_independently_verified'] is False
    assert report['physical_authority'] is False
    assert not runner.calls
    assert service._endpoint_binding is None
    export = _run(service,'export_logs')
    assert export['status'] == 'SUCCEEDED'
    folder = Path(export['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    saved = json.loads((folder/f"attachment-result-{completed['operation_id'].removeprefix('operation-')}.json").read_bytes())
    assert saved['steps'][0]['report'] == report


@pytest.mark.parametrize('change', [
    {'reviewer_id':'../bad'}, {'draft_json':'{}'}, {'check':'operator_present'},
    {'decision':True}, {'detail':''},
])
def test_invalid_input_rejected_before_recording(make_service,change):
    service,runner,_ = make_service(mode='physical')
    given = values()
    given.update(change)
    with pytest.raises(WizardError): _ticket(service,'record_endpoint_engineering_review',given)
    assert not runner.calls


def test_action_does_not_default_to_approval(make_service):
    service,_,_ = make_service(mode='physical')
    action = next(a for a in service.view()['actions'] if a['action_id']=='record_endpoint_engineering_review')
    assert next(f for f in action['fields'] if f['name']=='decision')['default'] == 'UNKNOWN'


def test_draft_from_other_source_does_not_publish_review(make_service):
    from rocell.application.endpoint_trial_contract import EndpointTrialRequest, _canonical
    service,runner,_ = make_service(mode='physical')
    body = request().to_dict()
    body['references']['source_sha256'] = 'b'*64
    body['campaign']['evidence']['source_sha256'] = 'b'*64
    given = values()
    given['draft_json'] = EndpointTrialDraft.from_request(EndpointTrialRequest(_canonical(body))).canonical_bytes.decode()
    completed = _run(service,'record_endpoint_engineering_review',given)
    assert completed['status'] == 'FAILED'
    assert not list(service._log.root.glob('*-engineering-review-original.json'))
    assert not runner.calls
