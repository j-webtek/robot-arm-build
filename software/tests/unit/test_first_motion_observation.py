"""Synthetic correlation evidence only; no actual observer or physical motion."""
import hashlib
import pytest

from rocell.application.first_motion_contract import FirstMotionRequest, canonical
from rocell.application.first_motion_observation import observation_original, record_observation, load_observation
from test_first_motion_contract import request


def values(outcome='EXPECTED_MOVEMENT'):
    return dict(observer_id='synthetic-observer', method='LIVE_VISUAL', outcome=outcome,
        coverage='ENTIRE_TRIAL', detail='Synthetic fixture only.', limitations='No actual observation or calibrated accuracy.')


def result(req):
    return canonical(dict(schema='rocell.first_motion_retained_result.v1',
        request_sha256=req.request_sha256, status='RESULT_REJECTED'))


@pytest.mark.parametrize('outcome', ['EXPECTED_MOVEMENT', 'NO_MOVEMENT', 'WRONG_MOVEMENT', 'UNKNOWN'])
def test_all_outcomes_retained_without_qualification(tmp_path, outcome):
    req = request()
    op = 'operation-'+'1'*32
    report = record_observation(req, result(req), values(outcome), root=tmp_path, operation_id=op, recorded_ns=100)
    loaded = load_observation(req, root=tmp_path, operation_id=op,
        expected_observation_sha256=report['observation_sha256'], expected_result_sha256=report['result_sha256'])
    assert loaded['reported']['outcome'] == outcome
    assert loaded['recorded_monotonic_ns'] == 100
    assert loaded['observed_monotonic_ns'] is None
    assert not loaded['physical_movement_verified']
    assert not loaded['physical_stop_verified']
    assert not loaded['campaign_advance_allowed']
    with pytest.raises(Exception):
        record_observation(req, result(req), values(outcome), root=tmp_path, operation_id=op, recorded_ns=101)


@pytest.mark.parametrize('fault', ['other_attempt', 'result', 'observation', 'forged_flag', 'path'])
def test_mismatched_or_changed_evidence_rejected(tmp_path, fault):
    req = request()
    op = 'operation-'+'2'*32
    report = record_observation(req, result(req), values(), root=tmp_path, operation_id=op, recorded_ns=100)
    if fault == 'other_attempt':
        body = req.to_dict()
        body['attempt_id'] = 'operation-'+'3'*32
        req = FirstMotionRequest(canonical(body))
    if fault == 'result': (tmp_path/(op+'-first-motion-observation-result.json')).write_bytes(b'{}')
    if fault == 'observation': (tmp_path/(op+'-first-motion-observation-original.json')).write_bytes(b'{}')
    if fault == 'forged_flag':
        path = tmp_path/(op+'-first-motion-observation-original.json')
        raw = path.read_bytes().replace(b'"campaign_advance_allowed":false', b'"campaign_advance_allowed":true')
        path.write_bytes(raw)
        report['observation_sha256'] = hashlib.sha256(raw).hexdigest()
    if fault == 'path': op = '../other'
    with pytest.raises(ValueError):
        load_observation(req, root=tmp_path, operation_id=op,
            expected_observation_sha256=report['observation_sha256'], expected_result_sha256=report['result_sha256'])


@pytest.mark.parametrize('field,value', [('observer_id','../x'), ('outcome',True), ('coverage',''),
    ('method','CALIBRATED_ACCURACY'), ('detail',''), ('limitations','x'*1025), ('extra','yes')])
def test_invalid_reports_rejected(field, value):
    req = request()
    inputs = values()
    inputs[field] = value
    with pytest.raises(ValueError): observation_original(req, result(req), inputs, recorded_ns=100)


def test_different_result_request_rejected_before_files(tmp_path):
    req = request()
    raw = result(req).replace(req.request_sha256.encode(), b'f'*64)
    with pytest.raises(ValueError):
        record_observation(req, raw, values(), root=tmp_path, operation_id='operation-'+'4'*32, recorded_ns=100)
    assert not list(tmp_path.iterdir())


def test_export_preserves_maximum_result_and_deduplicates(tmp_path):
    import base64
    import json
    from rocell.application.first_motion_observation import export_observations, MAX_RESULT_BYTES
    req = request()
    raw = result(req)
    raw += b' '*(MAX_RESULT_BYTES-len(raw))
    records = []
    for i in range(2):
        receipt = record_observation(req, raw, values(), root=tmp_path,
            operation_id='operation-'+format(i, '032x'), recorded_ns=100+i)
        records.append((req, receipt))
    bundle = json.loads(export_observations(root=tmp_path, records=tuple(records)))
    assert len(bundle['originals']) == 4  # One request/result, two observations.
    item = bundle['originals'][hashlib.sha256(raw).hexdigest()]
    assert b''.join(base64.b64decode(chunk, validate=True) for chunk in item['base64_chunks']) == raw
    assert not bundle['campaign_advance_allowed']
    (tmp_path/(records[0][1]['operation_id']+'-first-motion-observation-original.json')).write_bytes(b'{}')
    with pytest.raises(ValueError): export_observations(root=tmp_path, records=tuple(records))
