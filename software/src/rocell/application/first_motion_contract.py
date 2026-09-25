"""Separate immutable commissioning request data, never a live capability.

One fixed absolute wrist test is represented. Its independent measurement
references must later be authenticated by a separate admission boundary; digest
syntax and numeric intervals do not prove that an observation occurred.
"""
from dataclasses import dataclass
import hashlib
import json
import math
import re

from .wizard_diagnostic_coordinator import decode_diagnostic_json

SCHEMA = 'rocell.first_motion_request.v1'
REFERENCES = frozenset(('source_sha256', 'build_snapshot_sha256',
    'received_unit_review_sha256', 'native_controller_review_sha256',
    'installed_unit_compatibility_sha256', 'independent_posture_review_sha256',
    'swept_clearance_review_sha256', 'power_and_shutdown_review_sha256',
    'independent_observation_method_sha256', 'serial_profile_review_sha256'))


def fixed_command():
    return {'T':101, 'joint':4, 'rad':math.radians(1), 'spd':20, 'acc':1}


def fixed_limits():
    # Match the established bounded endpoint observation/resource budgets.
    return {'maximum_open_attempts':1, 'maximum_motion_write_attempts':1,
        'maximum_retry_count':0, 'maximum_command_bytes':512,
        'maximum_open_ms':2000, 'maximum_baseline_ms':1000,
        'maximum_write_ms':1000, 'maximum_post_observation_ms':5000,
        'maximum_cleanup_ms':2000, 'maximum_baseline_bytes':32768,
        'maximum_post_bytes':65536, 'maximum_baseline_reads':256,
        'maximum_post_reads':512}


def canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), allow_nan=False).encode('ascii')


def _time(value):
    return type(value) is int and 0 < value < 2**63


def _number(value):
    return type(value) in (int,float) and abs(value)<=1e6 and math.isfinite(value)


def _validate(raw):
    if type(raw) is not bytes:
        raise ValueError('Immutable commissioning bytes required')
    value = decode_diagnostic_json(raw, maximum=16384)
    fields = {'schema','purpose','attempt_id','usb_identity','references','command',
              'independent_start_interval_deg','distal_radius_mm','limits',
              'issued_monotonic_ns','deadline_monotonic_ns',
              'feedback_freshness_at_entry','physical_authority'}
    if type(value) is not dict or set(value)!=fields or canonical(value)!=raw:
        raise ValueError('Exact canonical commissioning fields required')
    if (value['schema']!=SCHEMA or value['purpose']!='ONE_SUPERVISED_WRIST_RESPONSE_EXPERIMENT'
            or value['feedback_freshness_at_entry']!='UNKNOWN' or value['physical_authority'] is not False):
        raise ValueError('Commissioning must not claim prequalified freshness or authority')
    if type(value['attempt_id']) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}',value['attempt_id']):
        raise ValueError('Exact operation ID required')
    identity = value['usb_identity']
    if (type(identity) is not dict or set(identity)!={'vid','pid','serial_number'}
            or type(identity['vid']) is not int or identity['vid']!=0x10c4
            or type(identity['pid']) is not int or identity['pid']!=0xea60
            or type(identity['serial_number']) is not str
            or not re.fullmatch(r'[A-F0-9]{32}',identity['serial_number'])):
        raise ValueError('Exact expected USB unit required, not a caller-selected COM port')
    refs = value['references']
    if (type(refs) is not dict or set(refs)!=REFERENCES
            or any(type(v) is not str or not re.fullmatch(r'[a-f0-9]{64}',v)
                   or v=='0'*64 for v in refs.values())):
        raise ValueError('Complete nonzero original reference digests required')
    if canonical(value['command'])!=canonical(fixed_command()) or canonical(value['limits'])!=canonical(fixed_limits()):
        raise ValueError('Fixed wrist command and resource limits cannot be widened')
    interval = value['independent_start_interval_deg']
    if (type(interval) is not list or len(interval)!=2 or not all(_number(v) for v in interval)
            or not -5<=interval[0]<interval[1]<=5):
        raise ValueError('Independently reviewed wrist interval must be within [-5,5] degrees')
    radius = value['distal_radius_mm']
    if not _number(radius) or not 0<radius<=200:
        raise ValueError('Independently reviewed distal radius must be at most 200 mm')
    issued, deadline = value['issued_monotonic_ns'],value['deadline_monotonic_ns']
    if not _time(issued) or not _time(deadline) or not 11_000_000_000<=deadline-issued<=30_000_000_000:
        raise ValueError('Bounded execution and cleanup lifetime required')
    return value


@dataclass(frozen=True, slots=True)
class FirstMotionRequest:
    canonical_bytes: bytes

    def __post_init__(self):
        _validate(self.canonical_bytes)

    @property
    def request_sha256(self):
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    @property
    def selection_sha256(self):
        """Stable engineering-review material, excluding only attempt/times."""
        value=self.to_dict()
        for name in ('attempt_id','issued_monotonic_ns','deadline_monotonic_ns'):
            del value[name]
        return hashlib.sha256(canonical(value)).hexdigest()

    def to_dict(self):
        return _validate(self.canonical_bytes)

    def require_start_time(self, now_ns):
        value = self.to_dict()
        if (not _time(now_ns) or now_ns<value['issued_monotonic_ns']
                or now_ns+11_000_000_000>value['deadline_monotonic_ns']):
            raise ValueError('Expired or insufficient execution/cleanup budget')

    def preview(self):
        value = self.to_dict()
        travel = max(abs(1-v) for v in value['independent_start_interval_deg'])
        return {'schema':'rocell.first_motion_request_preview.v1',
            'request_sha256':self.request_sha256, 'request':value,
            'maximum_requested_travel_given_interval_deg':travel,
            'conditional_ideal_path_length_mm':value['distal_radius_mm']*math.radians(travel),
            'independent_measurements_authenticated':False,
            'physical_clearance_verified':False, 'motion_authorized':False,
            'live_execution_implemented':False,
            'limitations':['Reference hashes do not authenticate approvals',
                'Rigid-point geometry excludes overshoot, cables and startup movement',
                'An endpoint permit cannot authorize this different command family']}


def create_first_motion_request(*, attempt_id, usb_identity, references,
        independent_start_interval_deg, distal_radius_mm,
        issued_monotonic_ns, deadline_monotonic_ns):
    return FirstMotionRequest(canonical(dict(schema=SCHEMA,
        purpose='ONE_SUPERVISED_WRIST_RESPONSE_EXPERIMENT',attempt_id=attempt_id,
        usb_identity=usb_identity,references=references,command=fixed_command(),
        independent_start_interval_deg=independent_start_interval_deg,
        distal_radius_mm=distal_radius_mm,limits=fixed_limits(),
        issued_monotonic_ns=issued_monotonic_ns,deadline_monotonic_ns=deadline_monotonic_ns,
        feedback_freshness_at_entry='UNKNOWN',physical_authority=False)))


def review_first_motion_request(text):
    if type(text) is not str:
        raise ValueError('Request review requires JSON text')
    value = decode_diagnostic_json(text.encode('utf-8'),maximum=12000)
    return FirstMotionRequest(canonical(value)).preview()
