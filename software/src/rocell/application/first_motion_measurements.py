"""Retain operator-reported independent measurements without approving motion."""
import hashlib
import math
import re
import time
from pathlib import Path

from .first_motion_contract import FirstMotionRequest, canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .physical_onboarding_durability import (
    publish_reservation_bytes, safe_root, contained_path, read_bounded_regular_file,
)

FIELDS = frozenset(('operator_id','unit_serial','method','angle_deg',
    'angle_uncertainty_deg','distal_radius_mm','radius_uncertainty_mm',
    'observation_notes','acknowledge_measured'))
METHODS = ('NONCONTACT_ANGLE_REFERENCE', 'CALIBRATED_SIDE_VIEW')
MAX_RECORD_AGE_NS = 300_000_000_000


def validate_measurements(values):
    if type(values) is not dict or set(values)!=FIELDS:
        raise ValueError('Exact independent measurement fields required')
    if (type(values['operator_id']) is not str
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',values['operator_id'])
            or type(values['unit_serial']) is not str
            or not re.fullmatch(r'[A-F0-9]{32}',values['unit_serial'])):
        raise ValueError('Identified operator and reported USB serial required')
    if values['method'] not in METHODS or type(values['method']) is not str:
        raise ValueError('Independent noncontact measurement method required')
    if values['acknowledge_measured'] is not True:
        raise ValueError('Explicit actual-measurement acknowledgment required')
    notes=values['observation_notes']
    if (type(notes) is not str or not 1<=len(notes.strip())<=1024
            or any(ord(c)<32 and c not in '\n\t' for c in notes)):
        raise ValueError('Describe the angle reference, uncertainty and radius measurement')
    bounds={'angle_deg':(-180,180),'angle_uncertainty_deg':(.1,30),
            'distal_radius_mm':(1,1000),'radius_uncertainty_mm':(0,100)}
    for name,(low,high) in bounds.items():
        number=values[name]
        if type(number) not in (int,float) or not low<=number<=high or not math.isfinite(number):
            raise ValueError('Invalid measurement: '+name)
    angle,uncertainty=values['angle_deg'],values['angle_uncertainty_deg']
    interval=[angle-uncertainty,angle+uncertainty]
    radius=values['distal_radius_mm']+values['radius_uncertainty_mm']
    # Out-of-proposal observations are retained, not silently clamped or lost.
    return {'reported_wrist_interval_deg':interval,
            'reported_distal_radius_upper_bound_mm':radius,
            'within_proposal_numeric_bounds':interval[0]>=-5 and interval[1]<=5 and radius<=200}


def _original(values, *, session_id, operation_id, source_sha256, now_ns):
    derived=validate_measurements(values)
    if (type(operation_id) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}',operation_id)
            or type(session_id) is not str or not re.fullmatch(r'wizard-[a-f0-9]{32}',session_id)
            or type(source_sha256) is not str or not re.fullmatch(r'[a-f0-9]{64}',source_sha256)
            or type(now_ns) is not int or not 0<now_ns<2**63):
        raise ValueError('Host-owned recording context required')
    return {'schema':'rocell.first_motion_measurement_original.v1',
        'operation_id':operation_id,'session_id':session_id,'source_sha256':source_sha256,
        'recorded_monotonic_ns':now_ns,'measured_monotonic_ns':None,
        'evidence_kind':'OPERATOR_REPORTED_INDEPENDENT_MEASUREMENT',
        'angle_reference':'WRIST_PITCH_ZERO_RELATIVE_TO_FOREARM_NOT_WORLD_HORIZONTAL',
        'reported':dict(values),'derived':derived,
        'measurement_time_independently_verified':False,
        'measurement_accuracy_independently_verified':False,
        'unit_association_independently_verified':False,
        'physical_authority':False,'motion_authorized':False}


def record_measurements(values, *, root, session_id, operation_id, source_sha256, now_ns):
    original = _original(values,session_id=session_id,operation_id=operation_id,
                         source_sha256=source_sha256,now_ns=now_ns)
    raw=canonical(original)
    name=operation_id+'-first-motion-measurement-original.json'
    publish_reservation_bytes(root,name,raw,maximum_bytes=8192)
    return {'status':'MEASUREMENTS_RECORDED_REVIEW_REQUIRED','original':original,
            'original_sha256':hashlib.sha256(raw).hexdigest(),'filename':name,
            'physical_authority':False,'motion_authorized':False}


def validate_original_for_request(raw, request, *, session_id, operation_id, now_ns):
    """Bind exact original bytes and geometry, not physical truth or approval.

    Record recency is only a prerequisite; measurement time is still unverified.
    Never regenerate this original with a new timestamp to extend its validity.
    """
    if type(request) is not FirstMotionRequest or type(raw) is not bytes:
        raise ValueError('Typed commissioning request and original bytes required')
    request.require_start_time(now_ns)
    body = request.to_dict()
    if hashlib.sha256(raw).hexdigest()!=body['references']['independent_posture_review_sha256']:
        raise ValueError('Measurement original hash differs from selected request')
    value = decode_diagnostic_json(raw,maximum=8192)
    if type(value) is not dict:
        raise ValueError('Structured original required')
    try:
        # Recompute derived geometry and all fixed claims using the old recording
        # time. Exact canonical equality rejects added fields or changed flags.
        reconstructed = _original(value['reported'],session_id=session_id,
            operation_id=operation_id,source_sha256=body['references']['source_sha256'],
            now_ns=value['recorded_monotonic_ns'])
    except (KeyError, TypeError) as error:
        raise ValueError('Incomplete retained measurement original') from error
    if canonical(reconstructed)!=raw:
        raise ValueError('Measurement fields, source, session or operation mismatch')
    recorded=value['recorded_monotonic_ns']
    if not recorded<=now_ns<recorded+MAX_RECORD_AGE_NS:
        raise ValueError('Measurement recording is future-dated or expired')
    if value['reported']['unit_serial']!=body['usb_identity']['serial_number']:
        raise ValueError('Measurement belongs to a different reported USB unit')
    geometry=value['derived']
    if (not geometry['within_proposal_numeric_bounds']
            or canonical(geometry['reported_wrist_interval_deg'])!=canonical(body['independent_start_interval_deg'])
            or canonical(geometry['reported_distal_radius_upper_bound_mm'])!=canonical(body['distal_radius_mm'])):
        raise ValueError('Request geometry differs from the complete measurement uncertainty bounds')
    return {'status':'ORIGINAL_MATCHES_REQUEST_NOT_APPROVED',
        'request_sha256':request.request_sha256,
        'original_sha256':hashlib.sha256(raw).hexdigest(),
        'original_recorded_monotonic_ns':recorded,
        'record_age_ns':now_ns-recorded,
        'record_valid_until_ns':min(recorded+MAX_RECORD_AGE_NS,body['deadline_monotonic_ns']),
        'measurement_time_independently_verified':False,
        'measurement_accuracy_independently_verified':False,
        'physical_authority':False,'motion_authorized':False}


def load_measurement_for_request(request, *, root, session_id, operation_id,
                                 check_current, clock_ns=time.monotonic_ns):
    """Read only the explicit host-selected original from its assigned root.

    No latest-record discovery, browser path, signing, retry or device access.
    The host must own session/operation selection and current-source checks.
    """
    if (type(operation_id) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}',operation_id)
            or type(request) is not FirstMotionRequest or not callable(check_current)
            or not callable(clock_ns)):
        raise ValueError('Exact retained operation and current host context required')
    def current():
        if check_current() is not None:
            raise ValueError('Measurement selection context changed')
    current()
    request.require_start_time(clock_ns())
    filename=operation_id+'-first-motion-measurement-original.json'
    raw=read_bounded_regular_file(contained_path(safe_root(Path(root)),filename,
        label='first-motion measurement original'),maximum_bytes=8192)
    current()
    result=validate_original_for_request(raw,request,session_id=session_id,
        operation_id=operation_id,now_ns=clock_ns())
    current()
    # A slow/cancelled source check must not allow a stale result to escape.
    result=validate_original_for_request(raw,request,session_id=session_id,
        operation_id=operation_id,now_ns=clock_ns())
    return raw,result
