"""Validate endpoint child results and rebuild observations from original bytes.

Envelope/byte consistency is not authentication of a physical arm. The parent
must additionally verify its owned process, durable child claim and persistence.
"""

import base64
import hashlib

from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.endpoint_capture import analyze_endpoint_capture
from rocell.arm.protocol import encode_line
from rocell.arm.telemetry_coverage import analyze_window_coverage, complete_frame_interval
from .endpoint_native_registration import RESULT_SCHEMA, validate_payload, _require
from .endpoint_native_wire import decode_request
from .owned_worker_process import decode_owned_json

MAX_RESULT_BYTES = 256*1024
STATUSES = frozenset({'NOT_OPENED','CANCELLED_BEFORE_OPEN','NATIVE_TRIAL_FAILED',
    'NOT_SENT','CANCELLED_BEFORE_WRITE','HELD_BEFORE_WRITE','WRITE_UNCERTAIN_NO_RETRY',
    'BYTES_WRITTEN_NOT_MOVEMENT_VERIFIED','TRIAL_FAILED_AFTER_WRITE',
    'INSUFFICIENT_ENDPOINT_EVIDENCE','OBSERVED_ENDPOINT_DWELL',
    'CLEANUP_UNCERTAIN','CLEANUP_UNCONFIRMED'})


def _integer(value, low, high):
    return type(value) is int and low <= value <= high


def _capture(value, request, phase):
    _require(type(value) is dict and value.get('schema')=='rocell.endpoint_capture_window.v1'
             and value.get('request_sha256')==request.request_sha256 and value.get('phase')==phase,
             'ENDPOINT_CAPTURE_ASSOCIATION')
    limits = request.to_dict()['limits']
    maximum = limits[f'maximum_{phase}_bytes']
    original = value.get('raw')
    _require(type(original) is dict and set(original)=={'bytes','sha256','base64_chunks'},'ENDPOINT_CAPTURE_ORIGINAL')
    chunks = original['base64_chunks']
    _require(type(chunks) is list and len(chunks)<=(maximum+767)//768
             and all(type(c) is str and len(c)<=1024 for c in chunks),'ENDPOINT_CAPTURE_CHUNKS')
    raw = b''.join(base64.b64decode(c,validate=True) for c in chunks)
    _require(_integer(original['bytes'],0,maximum) and len(raw)==original['bytes']
             and hashlib.sha256(raw).hexdigest()==original['sha256'],'ENDPOINT_CAPTURE_BYTES_CHANGED')
    _require(_integer(value.get('read_calls'),0,limits[f'maximum_{phase}_reads'])
             and type(value.get('read_windows')) is list and len(value['read_windows'])<=value['read_calls'],
             'ENDPOINT_CAPTURE_READ_BUDGET')
    coverage = analyze_window_coverage(raw,value['read_windows'],display_limit=0)
    _require(_canonical(value.get('coverage'))==_canonical(coverage),'ENDPOINT_CACHED_COVERAGE_CHANGED')
    if 'baseline_frame_interval' in value:
        _require(phase=='baseline' and _canonical(value['baseline_frame_interval'])==
                 _canonical(complete_frame_interval(raw,value['read_windows'])[2]),
                 'ENDPOINT_FRAME_INTERVAL_CHANGED')
    started,finished,deadline = (value.get(k) for k in ('started_ns','finished_ns','window_deadline_ns'))
    _require(all(_integer(t,1,2**63-1) for t in (started,finished,deadline))
             and request.to_dict()['issued_monotonic_ns']<=started<=finished
             and started<deadline,'ENDPOINT_CAPTURE_TIME_ORDER')
    windows = value['read_windows']
    _require(not windows or (windows[0][2]>=started and windows[-1][3]<=finished),'ENDPOINT_CAPTURE_WINDOW_ORDER')
    within = sum(row[1]-row[0] for row in windows if row[3]<=deadline)
    _require(type(value.get('within_deadline_bytes')) is int and value['within_deadline_bytes']==within
             and type(value.get('late_completion_bytes')) is int and value['late_completion_bytes']==len(raw)-within,
             'ENDPOINT_CAPTURE_TIME_ACCOUNTING')
    _require(value.get('physical_movement_verified') is False and value.get('physical_stop_verified') is False
             and value.get('sample_freshness_verified') is False,'ENDPOINT_CAPTURE_AUTHORITY_CLAIM')
    if value.get('status')=='WINDOW_COMPLETE':
        _require(finished>=deadline and value.get('errors')==[]
                 and value.get('abnormal_completion') is None and value.get('untimed_completion') is None,
                 'ENDPOINT_CAPTURE_COMPLETION_CONTRADICTION')


def validate_result(value, *, wire):
    wire = decode_request(_canonical(wire))
    request = validate_payload(wire['payload'])
    _require(type(value) is dict and set(value)=={'schema','attempt_id','request_sha256','child_result',
             'physical_authority','connected'},'ENDPOINT_RESULT_FIELDS')
    _require(value['schema']==RESULT_SCHEMA and value['attempt_id']==wire['attempt_id']
             and value['request_sha256']==wire['request_sha256'] and value['physical_authority'] is False
             and value['connected'] is False,'ENDPOINT_RESULT_CONTEXT')
    child = value['child_result']
    _require(type(child) is dict and set(child)=={'schema','claim_sha256','execution','physical_authority'}
             and child['schema']=='rocell.endpoint_native_child_result.v1'
             and child['physical_authority'] is False,'ENDPOINT_CHILD_FIELDS')
    from .owned_worker_process import _hash
    _hash(child['claim_sha256'])
    execution = child['execution']
    _require(type(execution) is dict and execution.get('schema')=='rocell.native_endpoint_execution.v1'
             and execution.get('request_sha256')==request.request_sha256 and execution.get('status') in STATUSES
             and execution.get('physical_movement_verified') is False
             and execution.get('physical_stop_verified') is False and execution.get('replay_allowed') is False,
             'ENDPOINT_EXECUTION_CONTEXT')
    life = execution.get('lifecycle')
    command_size = len(encode_line(request.goal().to_message()))
    _require(type(life) is dict and life.get('schema')=='rocell.endpoint_connection_lifecycle.v1'
             and life.get('request_sha256')==request.request_sha256
             and type(life.get('connection_id')) is str and 1<=len(life['connection_id'])<=80
             and _integer(life.get('owned_handle_count'),0,3) and _integer(life.get('pending_io_count'),0,1)
             and _integer(life.get('confirmed_write_bytes'),0,command_size)
             and life.get('physical_stop_verified') is False,'ENDPOINT_LIFECYCLE_CONTEXT')
    for phase in ('baseline','post'):
        for category in ('reads','bytes'):
            counts = life.get('read_calls' if category=='reads' else 'read_bytes')
            _require(type(counts) is dict and set(counts)=={'baseline','post'}
                     and _integer(counts[phase],0,request.to_dict()['limits'][f'maximum_{phase}_{category}']),
                     'ENDPOINT_LIFECYCLE_BUDGET')
    late = life.get('late_cleanup_read_base64')
    _require(type(late) is str and len(late)<=344 and len(base64.b64decode(late,validate=True))<=256,
             'ENDPOINT_LATE_READ_BUDGET')
    cleanup = life.get('phase')=='CLOSED' and life['owned_handle_count']==life['pending_io_count']==0
    rebuilt = None
    trial = execution.get('trial')
    if trial is not None:
        _require(type(trial) is dict and trial.get('schema')=='rocell.owned_endpoint_trial.v1'
                 and trial.get('request_sha256')==request.request_sha256
                 and trial.get('basis')=='RETAINED_PHYSICAL_CAPTURE'
                 and trial.get('status') in STATUSES and trial.get('replay_allowed') is False
                 and trial.get('physical_movement_verified') is False and trial.get('physical_stop_verified') is False,
                 'ENDPOINT_TRIAL_CONTEXT')
        for phase in ('baseline','post'):
            if trial.get(phase) is not None: _capture(trial[phase],request,phase)
        write = trial.get('write')
        if write is not None:
            _require(type(write) is dict and write.get('schema')=='rocell.endpoint_write_attempt.v1'
                     and write.get('request_sha256')==request.request_sha256
                     and type(write.get('write_attempted')) is bool
                     and type(write.get('write_completion_uncertain')) is bool
                     and _integer(write.get('confirmed_write_bytes'),0,command_size)
                     and write.get('physical_movement_verified') is False and write.get('physical_stop_verified') is False,
                     'ENDPOINT_WRITE_CONTEXT')
        if trial.get('post') is not None:
            _require(write is not None and write['write_attempted'],'ENDPOINT_POST_WITHOUT_WRITE')
            rebuilt = analyze_endpoint_capture(request,trial['post'],
                command_completed_ns=write.get('write_finished_ns'),basis='RETAINED_PHYSICAL_CAPTURE')
            if trial.get('analysis') is not None:
                _require(_canonical(trial['analysis'])==_canonical(rebuilt),'ENDPOINT_CACHED_ANALYSIS_CHANGED')
    observed = execution['status']=='OBSERVED_ENDPOINT_DWELL'
    if observed:
        _require(cleanup and rebuilt is not None and rebuilt['status']=='OBSERVED_ENDPOINT_DWELL'
                 and execution.get('errors')==[] and trial.get('errors')==[]
                 and trial['status']=='OBSERVED_ENDPOINT_DWELL'
                 and trial['baseline'] is not None and trial['baseline']['status']=='WINDOW_COMPLETE'
                 and write['status']=='BYTES_WRITTEN_NOT_MOVEMENT_VERIFIED'
                 and write['confirmed_write_bytes']==command_size and write['write_completion_uncertain'] is False
                 and life['confirmed_write_bytes']==command_size
                 and trial.get('cleanup',{}).get('status')=='HANDLES_CLOSED',
                 'ENDPOINT_OBSERVATION_NOT_SUPPORTED')
    return {'status':'RESULT_BYTES_VALIDATED_NOT_PHYSICAL_QUALIFICATION','endpoint_observed':observed,
            'cleanup_reported':cleanup,'analysis':rebuilt,'claim_sha256':child['claim_sha256'],
            'physical_movement_verified':False,'physical_stop_verified':False}


def encode_result(child, wire):
    value = {'schema':RESULT_SCHEMA,'attempt_id':wire['attempt_id'],'request_sha256':wire['request_sha256'],
             'child_result':child,'physical_authority':False,'connected':False}
    raw = _canonical(value)
    _require(len(raw)<=MAX_RESULT_BYTES,'ENDPOINT_RESULT_BYTE_BUDGET')
    validate_result(value,wire=wire)
    return raw


def decode_result(raw, *, wire):
    value = decode_owned_json(raw,maximum=MAX_RESULT_BYTES)
    validate_result(value,wire=wire)
    return value
