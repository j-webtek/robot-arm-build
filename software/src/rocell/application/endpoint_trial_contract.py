"""Bounded endpoint-trial request codec, not a live authorization capability.

One request selects exactly one trial from immutable campaign bytes. A future
native admission boundary must authenticate referenced originals and operator
presence; merely knowing their hashes cannot authorize an open or a write.
This module imports no serial provider and cannot mint or consume live claims.
"""

from dataclasses import dataclass
import hashlib
import json
import re

from rocell.arm.protocol import CartesianGoal, encode_line
from rocell.motion.characterization_plan import AXES, FrozenCampaign, freeze_campaign
from .wizard_diagnostic_coordinator import decode_diagnostic_json

SCHEMA = 'rocell.endpoint_trial_request.v1'
PURPOSE = 'ONE_SUPERVISED_NONCONTACT_ENDPOINT_TRIAL'
MAX_REQUEST_BYTES = 16384
LIMITS = {
    'maximum_open_attempts': 1, 'maximum_motion_write_attempts': 1,
    'maximum_retry_count': 0, 'maximum_command_bytes': 512,
    'maximum_open_ms': 2000, 'maximum_baseline_ms': 1000, 'maximum_write_ms': 1000,
    'maximum_post_observation_ms': 5000, 'maximum_cleanup_ms': 2000,
    'maximum_baseline_bytes': 32768, 'maximum_post_bytes': 65536,
    'maximum_baseline_reads': 256, 'maximum_post_reads': 512,
}
REFERENCE_NAMES = frozenset({
    'source_sha256', 'configuration_sha256', 'firmware_review_sha256', 'geometry_sha256',
    'build_snapshot_sha256', 'received_unit_review_sha256', 'native_controller_review_sha256',
    'operator_presence_sha256', 'shutdown_review_sha256', 'baseline_qualification_sha256',
})


def _canonical(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=True, allow_nan=False).encode('ascii')


def _sha(value):
    return type(value) is str and re.fullmatch(r'[a-f0-9]{64}', value) is not None


def _time(value):
    return type(value) is int and 0 < value < 2**63


def _validate(raw):
    if type(raw) is not bytes:
        raise ValueError('Immutable request bytes required')
    value = decode_diagnostic_json(raw, maximum=MAX_REQUEST_BYTES)
    expected = {'schema', 'purpose', 'attempt_id', 'campaign', 'trial_id', 'references',
                'usb_identity', 'issued_monotonic_ns', 'deadline_monotonic_ns', 'limits',
                'observation_contract', 'physical_authority'}
    if type(value) is not dict or set(value) != expected or _canonical(value) != raw:
        raise ValueError('Request fields/canonical bytes mismatch')
    if (value['schema'] != SCHEMA or value['purpose'] != PURPOSE
            or value['observation_contract'] != 'SUPERVISED_ENDPOINT_ONLY'
            or value['physical_authority'] is not False):
        raise ValueError('Unsupported trial purpose or authority claim')
    if type(value['attempt_id']) is not str or re.fullmatch(r'operation-[a-f0-9]{32}', value['attempt_id']) is None:
        raise ValueError('Exact operation ID required')
    if type(value['limits']) is not dict or _canonical(value['limits']) != _canonical(LIMITS):
        raise ValueError('Fixed one-trial limits cannot be changed')
    references = value['references']
    if type(references) is not dict or set(references) != REFERENCE_NAMES or not all(_sha(v) for v in references.values()):
        raise ValueError('Complete bounded reference hashes required')
    identity = value['usb_identity']
    if (type(identity) is not dict or set(identity) != {'vid', 'pid', 'serial_number'}
            or type(identity['vid']) is not int or identity['vid'] != 0x10C4
            or type(identity['pid']) is not int or identity['pid'] != 0xEA60
            or type(identity['serial_number']) is not str
            or re.fullmatch(r'[A-F0-9]{32}', identity['serial_number']) is None):
        raise ValueError('Expected CP210x identity with exact serial number; COM paths are not identities')
    issued, deadline = value['issued_monotonic_ns'], value['deadline_monotonic_ns']
    if not _time(issued) or not _time(deadline) or not 11_000_000_000 <= deadline-issued <= 30_000_000_000:
        raise ValueError('Request must reserve bounded execution/cleanup time')
    plan = freeze_campaign(value['campaign'])
    data = plan.to_dict()
    if data['frame'] != 'R_ctrl':
        raise ValueError('Explicit controller frame required')
    if data['evidence']['usb_identity'] != identity['serial_number']:
        raise ValueError('Campaign USB identity must match the request serial number')
    for name in ('source_sha256', 'configuration_sha256', 'firmware_review_sha256', 'geometry_sha256'):
        if references[name] != data['evidence'][name]:
            raise ValueError('Campaign/reference binding mismatch')
    if type(value['trial_id']) is not str:
        raise ValueError('Selected trial ID required')
    selected = [trial for trial in data['trials'] if trial['trial_id'] == value['trial_id']]
    if len(selected) != 1 or selected[0]['timeout_s'] > LIMITS['maximum_post_observation_ms']/1000:
        raise ValueError('One known trial within the capture window is required')
    trial = selected[0]
    goal = CartesianGoal(*(trial['target'][axis] for axis in AXES), trial['spd'])
    if len(encode_line(goal.to_message())) > LIMITS['maximum_command_bytes']:
        raise ValueError('Typed command exceeds fixed byte limit')
    return value, plan, goal


@dataclass(frozen=True, slots=True)
class EndpointTrialRequest:
    """Canonical request data only; never a permit accepted by any transport."""

    canonical_bytes: bytes

    def __post_init__(self):
        _validate(self.canonical_bytes)

    @property
    def request_sha256(self):
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def to_dict(self):
        return _validate(self.canonical_bytes)[0]

    def goal(self):
        return _validate(self.canonical_bytes)[2]

    def require_start_time(self, now_monotonic_ns):
        value = self.to_dict()
        if (not _time(now_monotonic_ns) or now_monotonic_ns < value['issued_monotonic_ns']
                or now_monotonic_ns + 11_000_000_000 > value['deadline_monotonic_ns']):
            raise ValueError('Expired request or insufficient execution/cleanup budget')


def create_endpoint_request(plan: FrozenCampaign, trial_id, *, attempt_id, references,
                            usb_identity, issued_monotonic_ns, deadline_monotonic_ns):
    """Compile data for future admission; does not validate physical approval."""
    if type(plan) is not FrozenCampaign:
        raise ValueError('Exact frozen campaign required')
    return EndpointTrialRequest(_canonical({
        'schema': SCHEMA, 'purpose': PURPOSE, 'attempt_id': attempt_id,
        'campaign': plan.to_dict(), 'trial_id': trial_id, 'references': references,
        'usb_identity': usb_identity, 'issued_monotonic_ns': issued_monotonic_ns,
        'deadline_monotonic_ns': deadline_monotonic_ns, 'limits': LIMITS,
        'observation_contract': 'SUPERVISED_ENDPOINT_ONLY', 'physical_authority': False,
    }))
