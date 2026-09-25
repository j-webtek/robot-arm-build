"""Bounded saved-byte reanalysis and the public wizard/export path."""

import base64
import hashlib
import json
from pathlib import Path

import pytest

from rocell.application.wizard_movement_capture import reanalyze_logs, validate_export_name
from rocell.application.wizard_worker import run
from rocell.application.wizard_diagnostic_export import verify_export
from test_arrival_wizard_service import make_service, _run, _ticket, WORKSPACE
from test_movement_campaign_ui import render

NAME = 'wizard-20260912T232404247125Z-19c8b63e3aa54dcb9ff472dc0d9c23d1'


def fixture_logs():
    raw = b'{"T":1051,"x":1,"y":0,"z":0,"tit":0,"r":0,"g":0,"b":0,"s":0,"e":0,"t":0}\n'
    observation = {'schema':'rocell.powered_telemetry_observation.v2','request_sha256':'b'*64,
                   'physical_authority':False,'origin':'SYNTHETIC_REHEARSAL','status':'CAPTURED_CLOSED',
                   'capture':{'raw':{'bytes':len(raw),'sha256':hashlib.sha256(raw).hexdigest(),
                                     'base64':base64.b64encode(raw).decode()}},
                   'read_windows':[[0,len(raw),100,101]]}
    result = {'schema':'rocell.owned_powered_feedback_native_result.v1','attempt_id':'operation-'+'a'*32,
              'request_sha256':'a'*64,'physical_authority':False,
              'child_result':{'schema':'rocell.powered_feedback_native_child_result.v1','observation':observation}}
    stdout = json.dumps(result).encode()
    logs = {'schema':'rocell.powered_feedback_native_logs.v1','physical_authority':False,
            'process':{'attempt_id':result['attempt_id'],'request_sha256':'a'*64,
                       'stdout_bytes':len(stdout),'stdout_sha256':hashlib.sha256(stdout).hexdigest()},
            'stdout_base64_chunks':[base64.b64encode(stdout[:17]).decode(),base64.b64encode(stdout[17:]).decode()]}
    return logs


def test_chunked_stdout_is_checked_and_all_bytes_reanalyzed():
    result = reanalyze_logs(json.dumps(fixture_logs()).encode())
    assert result['coverage']['counts']['POSE_TELEMETRY'] == 1
    assert result['coverage']['unprocessed_range'] is None
    assert result['request_sha256'] != result['observation_intent_sha256']
    assert not result['sample_freshness_verified']
    reconstructed = b''.join(base64.b64decode(chunk,validate=True) for chunk in result['retained_original']['base64_chunks'])
    assert hashlib.sha256(reconstructed).hexdigest() == result['coverage']['raw_sha256']


def test_changed_original_and_paths_rejected():
    logs = fixture_logs()
    logs['process']['stdout_sha256'] = 'f'*64
    with pytest.raises(ValueError, match='original mismatch'):
        reanalyze_logs(json.dumps(logs).encode())
    for name in ('../'+NAME, NAME+'/child', 'C:\\temp', NAME+'..', 'arbitrary'):
        with pytest.raises(ValueError):
            validate_export_name(name)


@pytest.mark.skipif(not (WORKSPACE/'software/runs/wizard-exports'/NAME).is_dir(), reason='Local retained hardware export not present')
@pytest.mark.parametrize('mode', ['rehearsal', 'physical'])
def test_public_saved_capture_and_reexport_preserve_actual_original(make_service, mode):
    service, runner, _ = make_service(mode=mode)
    runner.run = lambda action, values, **kw: run(WORKSPACE, action, values, kw['cell_id'])
    ticket = _ticket(service, 'movement_saved_capture_review')
    assert ticket['input']['export_name'] == NAME
    operation = _run(service, 'movement_saved_capture_review')
    assert operation['status'] == 'SUCCEEDED', json.dumps(operation.get('result', {}))
    report = operation['result']['steps'][0]['report']
    assert report['coverage']['counts']['POSE_TELEMETRY'] == 270
    assert report['coverage']['unprocessed_range'] == [56271,56384]
    assert report['coverage']['raw_sha256'] == '279f7a7827440ab97dfd374b79cdc705c909b20538c9781769245463210993d1'
    page = render(operation)
    assert 'Saved arm telemetry review' in page and '270' in page
    assert 'NOT ESTABLISHED' in page
    exported = _run(service, 'export_logs')
    folder = Path(exported['result']['receipt']['path'])
    assert verify_export(folder)['valid']
    retained = json.loads((folder/f"attachment-result-{operation['operation_id'].removeprefix('operation-')}.json").read_bytes())
    assert retained['steps'][0]['report'] == report
    raw = b''.join(base64.b64decode(chunk,validate=True) for chunk in report['retained_original']['base64_chunks'])
    assert len(raw) == 56384
    assert hashlib.sha256(raw).hexdigest() == report['coverage']['raw_sha256']
