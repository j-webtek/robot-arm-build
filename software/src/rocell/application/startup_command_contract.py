"""Offline signed startup-mode contract. Not enabled by deployed r3 firmware.

Outer schema and exact local-policy binding prevent a normal plan from silently
acquiring startup privileges. The inner plan preserves exact command bytes and
normal post-command assessment. No networking, key provisioning or motion.
"""
import base64
from dataclasses import dataclass
import hashlib
import hmac
import struct

from .first_motion_contract import canonical
from .servo_session_plan import SessionPlan
from .servo_start_authorization import DOMAIN, MAX_PLAN_BYTES, _key, _challenge_bytes, _validate_plan, _integer
from .servo_diagnostic_contract import _identifier
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def validate_startup_policy(policy):
    limits = {'drift_tolerance': (0,16), 'minimum_separation_us': (1,5000000),
        'maximum_wait_us': (1,5000000), 'maximum_pair_us': (1,1000000),
        'maximum_scan_us': (1,7000000), 'maximum_age_us': (1,1000000),
        'reviewed_mode': (0,255)}
    if type(policy) is not dict or set(policy) != set(limits)|{'policy_id','joints','mode'}:
        raise ValueError('Exact startup policy required')
    if policy['mode'] != 'ZERO_GOAL_TWO_SCAN':raise ValueError('Explicit startup mode required')
    _identifier(policy['policy_id'])
    for key,(low,high) in limits.items():
        if type(policy[key]) is not int or not low<=policy[key]<=high:
            raise ValueError('Startup policy limit invalid')
    if policy['minimum_separation_us']>policy['maximum_wait_us']:
        raise ValueError('Startup observation interval invalid')
    if type(policy['joints']) is not list or len(policy['joints'])!=7:
        raise ValueError('Seven startup joint windows required')
    for window in policy['joints']:
        if (type(window) is not list or len(window)!=2 or
            any(type(value) is not int for value in window) or not 0<=window[0]<=window[1]<=4095):
            raise ValueError('Invalid startup joint window')


@dataclass(frozen=True)
class StartupSessionPlan:
    encoded: bytes


def freeze_startup_plan(normal_plan, policy):
    validate_startup_policy(policy)
    if type(normal_plan) is not SessionPlan:raise ValueError('Frozen normal command contract required')
    doc=normal_plan.to_dict();_validate_plan(normal_plan,doc['command']['boot_id'])
    if doc['schema']!='rocell.session_plan.v3' or doc['schedule']['sample_count']>6:
        raise ValueError('Whole-arm contract and startup evidence capacity required')
    if doc['whole_arm_policy']['joints']!=policy['joints']:
        raise ValueError('Startup and command windows differ')
    payload=canonical(dict(schema='rocell.startup_session_plan.v1',
        startup_policy=policy,session_plan_base64=base64.b64encode(normal_plan.encoded).decode('ascii')))
    if len(payload)>MAX_PLAN_BYTES:raise ValueError('Startup plan byte budget exceeded')
    return StartupSessionPlan(payload)


def validate_startup_plan(plan, boot_id, approved_policy):
    validate_startup_policy(approved_policy)
    if type(plan) is not StartupSessionPlan:raise ValueError('Explicit startup plan required')
    doc=decode_diagnostic_json(plan.encoded,maximum=MAX_PLAN_BYTES)
    if (type(doc) is not dict or set(doc)!={'schema','startup_policy','session_plan_base64'} or
        doc['schema']!='rocell.startup_session_plan.v1' or
        canonical(doc['startup_policy'])!=canonical(approved_policy)):
        raise ValueError('Startup mode or local policy mismatch')
    normal=SessionPlan(base64.b64decode(doc['session_plan_base64'],validate=True))
    inner=_validate_plan(normal,boot_id)
    if freeze_startup_plan(normal,approved_policy).encoded!=plan.encoded:
        raise ValueError('Noncanonical startup contract')
    return inner


def sign_startup(plan,challenge,key,approved_policy):
    _key(key);header=_challenge_bytes(challenge)
    validate_startup_plan(plan,challenge['boot_id'],approved_policy)
    unsigned=DOMAIN+header+struct.pack('>H',len(plan.encoded))+plan.encoded
    return unsigned+hmac.digest(key,unsigned,'sha256')


class StartupAuthorizationGate:
    def __init__(self,challenge,key,approved_policy,*,expected_origin='DEVICE_CAPTURE'):
        _key(key);validate_startup_policy(approved_policy)
        if expected_origin not in ('SIMULATION','DEVICE_CAPTURE'):raise ValueError('Explicit origin required')
        self.prefix=DOMAIN+_challenge_bytes(challenge)
        self.boot=challenge['boot_id'];self.issued=challenge['issued_us'];self.expires=challenge['expires_us']
        self.policy=decode_diagnostic_json(canonical(approved_policy),maximum=4096)
        self.key=key;self.origin=expected_origin;self.used=False

    def consume(self,token,*,now_us):
        if self.used:raise ValueError('Startup authorization consumed')
        self.used=True
        if not self.issued<=_integer(now_us)<self.expires:raise ValueError('Startup authorization expired')
        if type(token) is not bytes or not len(self.prefix)+35<=len(token)<=len(self.prefix)+34+MAX_PLAN_BYTES:
            raise ValueError('Invalid startup token length')
        unsigned,signature=token[:-32],token[-32:]
        if not hmac.compare_digest(signature,hmac.digest(self.key,unsigned,'sha256')):
            raise ValueError('Startup authentication failed')
        if not unsigned.startswith(self.prefix):raise ValueError('Startup challenge mismatch')
        offset=len(self.prefix);length=struct.unpack('>H',unsigned[offset:offset+2])[0]
        encoded=unsigned[offset+2:]
        if length!=len(encoded):raise ValueError('Startup plan length mismatch')
        doc=validate_startup_plan(StartupSessionPlan(encoded),self.boot,self.policy)
        if doc['origin']!=self.origin:raise ValueError('Startup origin mismatch')
        return dict(schema='rocell.startup_authorization_assessment.v1',
            startup_plan_sha256=hashlib.sha256(encoded).hexdigest(),
            command_id=doc['command']['command_id'],boot_id=self.boot,
            authenticated_request=True,progression_authority=False,write_attempted=False)
