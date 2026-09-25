"""Real journal/wire reconstruction with synthetic bytes and process receipts."""
import base64
from dataclasses import replace
import hashlib

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.powered_feedback_attempt_store import _publish, attempt_path
from rocell.application.wizard_powered_feedback_native_coordinator import PoweredFeedbackOutcome, TELEMETRY_ACTION
from rocell.application.absolute_wrist_telemetry_source import choices_from_retained_telemetry
from rocell.providers.windows.owned_worker_process import OwnedWorkerResult
from test_powered_telemetry_wire import captured, result
from test_observational_capture_preview import observation


def fixture(tmp_path, captured):
    wire, value = result(captured)
    body = wire['payload']['intent']
    attempt = body['attempt_id']
    prepared = _publish(tmp_path, attempt, 'prepared', dict(intent=body,
        originals_base64=dict(runtime_sha256=base64.b64encode(canonical(wire['payload']['registration'])).decode())))
    consumed = _publish(tmp_path, attempt, 'consumed', dict(prepared_sha256=prepared,
        request_sha256=wire['operation_sha256']))
    claimed = _publish(tmp_path, attempt, 'claimed', dict(consumption_sha256=consumed,
        request_sha256=wire['operation_sha256']))
    wire['payload'].update(root=str(tmp_path), consumption_sha256=consumed)
    wire['request_sha256'] = hashlib.sha256(canonical({k:v for k,v in wire.items() if k != 'request_sha256'})).hexdigest()
    value['request_sha256'] = wire['request_sha256']
    value['child_result']['claim_sha256'] = claimed
    obs = value['child_result']['observation']
    historical = observation()
    for key in ('capture', 'read_windows', 'started_monotonic_ns', 'observation_finished_monotonic_ns'):
        obs[key] = historical[key]
    obs['finished_monotonic_ns'] = 7_000_000_001
    obs['acquisition_started_monotonic_ns'] = historical['started_monotonic_ns']
    obs['read_calls'] = len(obs['read_windows'])
    obs['stop_reason'] = 'OBSERVATION_WINDOW_COMPLETE'
    stdout = canonical(value)
    digest = _publish(tmp_path, attempt, 'outcome', dict(consumption_sha256=consumed,
        process_status='SUCCEEDED', stdout_base64=base64.b64encode(stdout).decode(), stderr_base64=''))
    process = OwnedWorkerResult('SUCCEEDED', None, (), wire['request_sha256'], attempt,
        True, True, True, 0, 0, 0, 0, 0, stdout, b'', parsed_result=value,
        owned_process_id=1234, finished_monotonic_ns=8_000_000_000)
    outcome = PoweredFeedbackOutcome(process, digest, None, TELEMETRY_ACTION)
    context = dict(session_id=wire['session_id'], source_sha256=wire['source_sha256'],
                   native_identity_sha256=wire['selected_identity_sha256'])
    return outcome, context


def test_original_bound_choices_preserve_capture_identity(tmp_path, captured):
    outcome, context = fixture(tmp_path, captured)
    choices = choices_from_retained_telemetry(tmp_path, outcome, **context)
    assert [c['draft']['target_deg'] for c in choices['choices']] == [0, 4]
    assert choices['source_attempt_id'] == outcome.process.attempt_id
    assert choices['outcome_sha256'] == outcome.outcome_sha256
    assert choices['historical_only'] and not choices['motion_authorized']


@pytest.mark.parametrize('fault', ['session', 'source', 'identity', 'process', 'stdout', 'parsed',
    'outcome_hash', 'prepared', 'consumed', 'claimed', 'outcome'])
def test_changed_associations_do_not_supply_drafts(tmp_path, captured, fault):
    outcome, context = fixture(tmp_path, captured)
    if fault == 'session': context['session_id'] = 'wizard-'+'f'*32
    if fault == 'source': context['source_sha256'] = 'f'*64
    if fault == 'identity': context['native_identity_sha256'] = 'f'*64
    if fault == 'process': outcome = replace(outcome, process=replace(outcome.process, tree_exit_confirmed=False))
    if fault == 'stdout': outcome = replace(outcome, process=replace(outcome.process, stdout=b'{}'))
    if fault == 'parsed': outcome = replace(outcome, process=replace(outcome.process, parsed_result={}))
    if fault == 'outcome_hash': outcome = replace(outcome, outcome_sha256='f'*64)
    if fault in ('prepared', 'consumed', 'claimed', 'outcome'):
        attempt_path(tmp_path, outcome.process.attempt_id, fault).write_bytes(b'{}')
    with pytest.raises(ValueError): choices_from_retained_telemetry(tmp_path, outcome, **context)
