"""Wizard observation-to-assessment flow over synthetic native originals."""
import hashlib
import os
import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_first_motion_coordinator import FirstMotionRunOutcome
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from rocell.providers.windows.first_motion_native_protocol import decode_request, validate_payload
from rocell.providers.windows.first_motion_result_publication import publish_first_motion_result
from test_first_motion_result_publication import fixture
from test_first_motion_observation import values
from test_arrival_wizard_service import make_service, _run


@pytest.mark.parametrize('fault', [None, 'no_movement', 'missing_owner', 'changed_stream'])
def test_ticketed_assessment_never_grants_motion(make_service, tmp_path, fault):
    service, runner, _ = make_service(mode='physical')
    native = tmp_path/'native'; native.mkdir()
    request_raw, stdout = fixture(native)
    wire = decode_request(request_raw)
    req = validate_payload(wire['payload'])
    service.export_directory.mkdir(parents=True, exist_ok=True)
    path, report = publish_first_motion_result(service.export_directory, request_raw=request_raw, stdout=stdout,
        stderr=b'', owned_process_id=os.getpid(), returncode=0, process_tree_closed=True, finished_ns=40_000_000_000)
    owned = OwnedWorkerResult(status='SUCCEEDED', primary_error=None, cleanup_errors=(),
        request_sha256=wire['request_sha256'], attempt_id=wire['attempt_id'], process_created=True,
        initial_thread_resumed=True, tree_exit_confirmed=True, returncode=0, elapsed_ns=1,
        stdin_bytes_written=len(request_raw), peak_observed_handles=1, peak_active_processes=1,
        stdout=stdout, stderr=b'', owned_process_id=os.getpid(), finished_monotonic_ns=40_000_000_000)
    service._first_motion_attempt_id = wire['attempt_id']
    service._first_motion_outcome = FirstMotionRunOutcome('RETAINED', None if fault == 'missing_owner' else owned, path, report, None)
    service._append_event('synthetic_fixture', {'physical_authority': False})
    (service._log.root/(wire['attempt_id']+'-first-motion-final-click.json')).write_bytes(canonical(dict(request=req.to_dict())))
    inputs = dict(values('NO_MOVEMENT' if fault == 'no_movement' else 'EXPECTED_MOVEMENT'),
        trial=wire['attempt_id']+'@'+hashlib.sha256(path.read_bytes()).hexdigest())
    observation = _run(service, 'record_first_motion_observation', inputs)
    assert observation['status'] == 'SUCCEEDED'
    if fault == 'changed_stream':
        (service.export_directory/report['originals']['stdout.bin']['file']).write_bytes(b'{}')
    operation = _run(service, 'assess_first_motion_qualification', dict(observation_operation_id=observation['operation_id']))
    if fault == 'changed_stream':
        assert operation['status'] == 'FAILED'
    else:
        assert operation['status'] == 'SUCCEEDED'
        result = operation['result']['steps'][0]['report']
        assessment = result['assessment']
        assert assessment['status'] == ('READY_FOR_EXPLICIT_QUALIFICATION_REVIEW' if fault is None else 'HELD')
        assert not assessment['campaign_advance_allowed']
        raw = (service._log.root/(operation['operation_id']+'-first-motion-assessment.json')).read_bytes()
        assert hashlib.sha256(raw).hexdigest() == result['assessment_sha256']
        from rocell.application.first_motion_qualification_decision import REVIEW_CHECKS
        inputs = dict.fromkeys(REVIEW_CHECKS, True) | dict(
            assessment_operation_id=operation['operation_id'], reviewer_id='synthetic-reviewer',
            decision='ACCEPT_FUNCTIONAL_RESPONSE', rationale='Synthetic review; no actual physical claim.')
        review = _run(service, 'review_first_motion_qualification', inputs)
        assert review['status'] == ('SUCCEEDED' if fault is None else 'FAILED')
        if fault is None:
            decision = review['result']['steps'][0]['report']
            assert not decision['motion_authorized'] and not decision['campaign_advance_allowed']
            retained = (service._log.root/(review['operation_id']+'-first-motion-qualification-decision.json')).read_bytes()
            assert hashlib.sha256(retained).hexdigest() == decision['decision_sha256']
            import base64
            import json
            from pathlib import Path
            from rocell.application.wizard_diagnostic_export import verify_export
            exported = _run(service, 'export_logs')
            assert exported['status'] == 'SUCCEEDED'
            folder = Path(exported['result']['receipt']['path'])
            assert verify_export(folder)['valid']
            bundle = json.loads((folder/'attachment-first-motion-qualification.json').read_bytes())
            originals = {digest:b''.join(base64.b64decode(chunk, validate=True) for chunk in item['base64_chunks'])
                         for digest,item in bundle['originals'].items()}
            assert originals[decision['decision_sha256']] == retained
            assert originals[decision['assessment_sha256']] == raw
            assert all(hashlib.sha256(value).hexdigest() == digest for digest,value in originals.items())
            # The original assessment cannot be silently changed for a later review.
            (service._log.root/(operation['operation_id']+'-first-motion-assessment.json')).write_bytes(b'{}')
            assert _run(service, 'review_first_motion_qualification', inputs)['status'] == 'FAILED'
    assert service._first_motion_attempt_id == wire['attempt_id']
    assert service._first_motion_attachment is None
    assert not runner.calls
