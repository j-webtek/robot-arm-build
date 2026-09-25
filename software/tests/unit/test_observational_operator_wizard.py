"""Exercise public preview/run/export with host-injected synthetic trial evidence."""
import base64
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_observational_coordinator import ObservationalRunOutcome
from rocell.safety.observational_review_authority import ObservationalIntent
from test_observational_review_authority import intent
from test_arrival_wizard_service import make_service, _run


@pytest.mark.parametrize('fault', [None, 'changed_result', 'session', 'selection'])
def test_simple_observation_and_export(make_service, fault):
    service, runner, _ = make_service(mode='physical')
    body = intent()
    if fault != 'session': body['session_id'] = service.session_id
    request = ObservationalIntent(canonical(body))
    attempt = body['attempt_id']
    report = dict(schema='rocell.observational_retained_result.v1', attempt_id=attempt,
        request_sha256=request.request_sha256, status='RESULT_REJECTED',
        physical_movement_verified=False, campaign_advance_allowed=False)
    raw = canonical(report)
    service._append_event('synthetic_observational_fixture', {'physical_authority':False})
    service.export_directory.mkdir(parents=True, exist_ok=True)
    path = service.export_directory/(attempt+'-observational-report.json')
    path.write_bytes(raw)
    service._observational_request = request
    service._observational_outcome = ObservationalRunOutcome('RETAINED', None, path, report, None)
    values = dict(trial=attempt+'@'+hashlib.sha256(raw).hexdigest(), observer_id='Jack',
        outcome='EXPECTED_MOVEMENT', covered_trial=True, detail='')
    if fault == 'changed_result': path.write_bytes(b'{}')
    if fault == 'selection': values['trial'] = 'wrong-selection'
    if fault == 'selection':
        with pytest.raises(Exception): _run(service, 'record_observational_movement', values)
    else:
        operation = _run(service, 'record_observational_movement', values)
        if fault:
            assert operation['status'] == 'FAILED'
        else:
            assert operation['status'] == 'SUCCEEDED', operation
            saved = operation['result']['steps'][0]['report']
            assert saved['observation']['reported']['detail'] == ''
            assert saved['functional_assessment_pending'] is False
            assert saved['assessment']['status'] == 'HELD'  # Fixture has no owned process evidence.
            assert operation['result']['motion_command_count'] == 0
            exported = _run(service, 'export_logs')
            assert exported['status'] == 'SUCCEEDED', exported
            folder = Path(exported['result']['receipt']['path'])
            from rocell.application.wizard_diagnostic_export import verify_export
            assert verify_export(folder)['valid']
            bundle = json.loads((folder/'attachment-observational-operator-reports.json').read_bytes())
            for digest, original in bundle['originals'].items():
                data = b''.join(base64.b64decode(chunk, validate=True) for chunk in original['base64_chunks'])
                assert hashlib.sha256(data).hexdigest() == digest
                assert len(data) == original['bytes']
            assert bundle['associations'][0]['report_sha256'] == saved['observation_sha256']
            assert bundle['associations'][0]['assessment_sha256'] == saved['assessment_sha256']
    assert not runner.calls
