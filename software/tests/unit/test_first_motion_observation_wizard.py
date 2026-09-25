"""Synthetic completed-result association; no process or hardware is created."""
import hashlib
import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_first_motion_coordinator import FirstMotionRunOutcome
from rocell.application.first_motion_observation import load_observation
from test_arrival_wizard_service import make_service, _run
from test_first_motion_contract import request
from test_first_motion_observation import values, result


@pytest.mark.parametrize('fault', [None, 'changed_result', 'changed_request', 'different_selection'])
@pytest.mark.parametrize('large_result', [False, True])
def test_wizard_records_only_selected_retained_outcome(make_service, fault, large_result):
    service, runner, _ = make_service(mode='physical')
    req = request()
    attempt = req.to_dict()['attempt_id']
    raw = result(req)
    import json
    report = json.loads(raw)
    if large_result:
        report['synthetic_diagnostic_fragments'] = ['x'*16384 for _ in range(15)]
        raw = canonical(report)
    service._append_event('synthetic_observation_fixture', {'physical_authority': False})
    service.export_directory.mkdir(parents=True, exist_ok=True)
    path = service.export_directory/(attempt+'-first_motion-report.json')
    path.write_bytes(raw)
    click_path = service._log.root/(attempt+'-first-motion-final-click.json')
    click_path.write_bytes(canonical(dict(request=req.to_dict())))
    service._first_motion_attempt_id = attempt
    service._first_motion_outcome = FirstMotionRunOutcome('RETAINED', None, path, report, None)
    inputs = dict(values(), trial=attempt+'@'+hashlib.sha256(raw).hexdigest())
    if fault == 'changed_result': path.write_bytes(b'{}')
    if fault == 'changed_request':
        changed = req.to_dict()
        changed['attempt_id'] = 'operation-'+'f'*32
        click_path.write_bytes(canonical(dict(request=changed)))
    if fault == 'different_selection': inputs['trial'] = 'operation-'+'f'*32+'@'+hashlib.sha256(raw).hexdigest()
    if fault == 'different_selection':
        with pytest.raises(Exception): _run(service, 'record_first_motion_observation', inputs)
    else:
        operation = _run(service, 'record_first_motion_observation', inputs)
        if fault:
            assert operation['status'] == 'FAILED'
        else:
            assert operation['status'] == 'SUCCEEDED'
            saved = operation['result']['steps'][0]['report']
            original = load_observation(req, root=service._log.root, operation_id=operation['operation_id'],
                expected_observation_sha256=saved['observation_sha256'], expected_result_sha256=saved['result_sha256'])
            assert original['reported'] == values()
            assert not saved['physical_movement_verified']
            assert not saved['campaign_advance_allowed']
            assert operation['result']['device_open_count'] == 0
            from pathlib import Path
            import base64
            from rocell.application.wizard_diagnostic_export import verify_export
            exported = _run(service, 'export_logs')
            assert exported['status'] == 'SUCCEEDED'
            folder = Path(exported['result']['receipt']['path'])
            assert verify_export(folder)['valid']
            bundle = json.loads((folder/'attachment-first-motion-observations.json').read_bytes())
            for digest, item in bundle['originals'].items():
                decoded = b''.join(base64.b64decode(chunk, validate=True) for chunk in item['base64_chunks'])
                assert hashlib.sha256(decoded).hexdigest() == digest
                assert len(decoded) == item['bytes']
            association = bundle['associations'][0]
            assert association['observation_sha256'] == saved['observation_sha256']
            assert association['request_sha256'] == req.request_sha256
            assert association['result_sha256'] == hashlib.sha256(raw).hexdigest()
    assert service._first_motion_attempt_id == attempt
    assert service._first_motion_attachment is None
    assert not runner.calls
