"""Synthetic native-domain codec fixtures, not evidence of a physical trial.

Only the process-claim verifier is replaced for successful reconstruction here;
its real PID/claim validation is independently tested in coordinator tests.
"""
import base64
from dataclasses import replace
import hashlib

import pytest

from rocell.application import observational_functional_assessment as module
from rocell.application.first_motion_contract import canonical
from rocell.application.observational_operator_report import record_operator_report
from rocell.application.wizard_observational_coordinator import ObservationalRunOutcome
from rocell.providers.windows.observational_native_result import encode_result
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from rocell.safety.observational_review_authority import ObservationalIntent
from test_observational_native_result import fixture


@pytest.mark.parametrize('fault', [None, 'no_movement', 'partial', 'bytes', 'cleanup', 'claim', 'early'])
def test_original_reconstruction_and_observation_agreement(tmp_path, monkeypatch, fault):
    wire, child = fixture(tmp_path, monkeypatch)
    request = ObservationalIntent(canonical(wire['payload']['observational_intent']))
    attempt = request.to_dict()['attempt_id']
    stdout = encode_result(child, wire=wire)
    export = tmp_path/'exports'
    export.mkdir()
    originals = {}
    for name, raw in (('request', canonical(wire)), ('stdout', stdout), ('stderr', b'')):
        filename = attempt+'-observational-'+name+'.original.json'
        (export/filename).write_bytes(canonical(dict(bytes=len(raw), base64=base64.b64encode(raw).decode('ascii'))))
        originals[name] = dict(file=filename, bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
    report = dict(schema='rocell.observational_retained_result.v1', attempt_id=attempt,
        request_sha256=request.request_sha256, status='RESULT_RETAINED', claim_receipt_verified=True,
        originals=originals)
    report_raw = canonical(report)
    path = export/(attempt+'-observational-report.json')
    path.write_bytes(report_raw)
    finished = child['trial']['cleanup']['finished_ns']
    owned = OwnedWorkerResult('SUCCEEDED', None, (), wire['request_sha256'], attempt,
        True, True, True, 0, 1, 1, 1, 1, stdout, b'', owned_process_id=123,
        finished_monotonic_ns=finished)
    if fault == 'cleanup': owned = replace(owned, cleanup_errors=('SYNTHETIC_ERROR',))
    outcome = ObservationalRunOutcome('RETAINED', owned, path, report, None)
    values = dict(observer_id='synthetic', outcome='NO_MOVEMENT' if fault == 'no_movement' else 'EXPECTED_MOVEMENT',
        covered_trial=fault != 'partial', detail='Synthetic codec data, not hardware evidence')
    receipt = record_operator_report(request, report_raw, values, root=tmp_path,
        operation_id='operation-'+'f'*32, recorded_ns=finished-1 if fault == 'early' else finished+1)
    calls = []

    def claim_check(*args, **kwargs):
        calls.append(kwargs)
        assert kwargs['owned_process_id'] == 123
        if fault == 'claim': raise ValueError('Synthetic claim rejection')

    monkeypatch.setattr(module, 'verify_observational_worker_receipt', claim_check)
    if fault == 'bytes': (export/originals['stdout']['file']).write_bytes(b'{}')
    result = module.assess_retained_observational_trial(request, outcome, receipt,
        review_root=tmp_path, export_root=export)
    assert result['status'] == ('OBSERVED_FUNCTIONAL_PASS' if fault is None else 'HELD'), result
    if fault in (None, 'no_movement', 'partial'):
        assert len(calls) == 1
        assert result['analysis']['post_sample_count'] > 1
    assert result['physical_accuracy_verified'] is False
    assert result['campaign_advance_allowed'] is False
    assert result['motion_authorized'] is False
