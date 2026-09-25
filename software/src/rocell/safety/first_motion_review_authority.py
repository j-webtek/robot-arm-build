"""Domain-separated authentication of commissioning reviews, never port access.

Engineering originals may predate the final request but bind all selection
material. Operator originals bind the exact timed request. No unknown decision
is promoted to approval and no timestamp is renewed during sealing.
"""
import base64
from dataclasses import dataclass
import hashlib
import hmac
import re
import time
from pathlib import Path

from rocell.application.first_motion_contract import FirstMotionRequest, canonical
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.physical_onboarding_durability import safe_root, contained_path, read_bounded_regular_file

OPERATOR_CHECKS=frozenset(('secured_installation','full_arm_and_cable_clearance',
    'gravity_drop_envelope','reachable_power_shutdown','operator_present',
    'exact_wrist_target_and_speed_approved','unknown_freshness_experiment_acknowledged'))
ENGINEERING_CHECKS=frozenset(('received_unit_and_usb_association',
    'installed_unit_command_compatibility','independent_starting_geometry_review',
    'independent_observation_method_ready','owned_connection_and_cleanup_ready'))
REQUIRED_CHECKS=OPERATOR_CHECKS|ENGINEERING_CHECKS
MAX_BUNDLE_BYTES=80*1024
MAX_ENGINEERING_LIFETIME_NS=300_000_000_000
_DOMAIN=b'rocell.first-motion-review-bundle.v1\x00'


def _reviews(request, originals, now_ns):
    if (type(request) is not FirstMotionRequest or type(now_ns) is not int
            or not 0<now_ns<2**63):
        raise ValueError('Exact commissioning request and current monotonic time required')
    body=request.to_dict()
    if not body['issued_monotonic_ns']<=now_ns<body['deadline_monotonic_ns']:
        raise ValueError('Commissioning request expired or not yet issued')
    if type(originals) is not dict or set(originals)!=REQUIRED_CHECKS:
        raise ValueError('All distinct commissioning review originals required')
    fields={'schema','scope','check','actor_id','decision','evidence_kind',
            'binding_sha256','recorded_ns','expires_ns','detail'}
    hashes=[]
    expiry=body['deadline_monotonic_ns']
    selection_sha=request.selection_sha256
    for name,raw in sorted(originals.items()):
        if type(raw) is not bytes or not 0<len(raw)<=4096:
            raise ValueError('Bounded immutable review original required')
        value=decode_diagnostic_json(raw,maximum=4096)
        engineering=name in ENGINEERING_CHECKS
        binding=selection_sha if engineering else request.request_sha256
        kind='ENGINEERING_SELECTION_REVIEW' if engineering else 'EXACT_REQUEST_OPERATOR_ATTESTATION'
        if (type(value) is not dict or set(value)!=fields or canonical(value)!=raw
                or value['schema']!='rocell.first_motion_review.v1'
                or value['scope']!='ONE_WRIST_RESPONSE_EXPERIMENT'
                or value['check']!=name or value['decision']!='APPROVED'
                or value['evidence_kind']!=kind or value['binding_sha256']!=binding):
            raise ValueError('Review scope, decision or request/selection binding mismatch')
        if (type(value['actor_id']) is not str
                or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}',value['actor_id'])
                or type(value['detail']) is not str or not 1<=len(value['detail'].strip())<=1024):
            raise ValueError('Explicit reviewer identity and rationale required')
        recorded,expires=value['recorded_ns'],value['expires_ns']
        if (type(recorded) is not int or type(expires) is not int
                or not 0<recorded<=now_ns<expires<2**63):
            raise ValueError('Invalid or expired original review times')
        if engineering:
            if expires-recorded>MAX_ENGINEERING_LIFETIME_NS:
                raise ValueError('Engineering review lifetime exceeds five minutes')
        elif recorded<body['issued_monotonic_ns'] or expires>body['deadline_monotonic_ns']:
            raise ValueError('Operator review must belong to the current exact request window')
        expiry=min(expiry,expires)
        hashes.append((name,hashlib.sha256(raw).hexdigest()))
    return tuple(hashes),expiry


@dataclass(frozen=True, slots=True)
class FirstMotionReviewEvidence:
    """Authenticated record association; neither a native permit nor truth proof."""
    request_sha256: str
    connection_id: str
    references: tuple
    checks: tuple
    verified_at_ns: int
    expires_at_ns: int


class FirstMotionReviewAuthority:
    """Host-only authority from a derived protected key, never uploaded key data."""
    def __init__(self,key):
        if type(key) is not bytes or len(key)!=32:
            raise ValueError('Protected commissioning-derived 32-byte key required')
        self._key=key

    def seal(self,request,originals,*,now_ns):
        _reviews(request,originals,now_ns)
        body={'schema':'rocell.first_motion_review_bundle.v1',
              'request_sha256':request.request_sha256,
              'originals':{name:base64.b64encode(raw).decode('ascii') for name,raw in originals.items()}}
        body['mac']=hmac.new(self._key,_DOMAIN+canonical(body),hashlib.sha256).hexdigest()
        raw=canonical(body)
        if len(raw)>MAX_BUNDLE_BYTES: raise ValueError('Commissioning bundle exceeds byte budget')
        return raw

    def verify(self,request,raw,*,connection_id,current_references,now_ns):
        """Context arguments must be independently resolved by the owned host."""
        if type(request) is not FirstMotionRequest or type(raw) is not bytes:
            raise ValueError('Commissioning types required, not Cartesian endpoint types')
        body=decode_diagnostic_json(raw,maximum=MAX_BUNDLE_BYTES)
        if (type(body) is not dict or set(body)!={'schema','request_sha256','originals','mac'}
                or body['schema']!='rocell.first_motion_review_bundle.v1'
                or canonical(body)!=raw or body['request_sha256']!=request.request_sha256):
            raise ValueError('Commissioning bundle does not match request')
        mac=body.pop('mac')
        if (type(mac) is not str or not re.fullmatch(r'[a-f0-9]{64}',mac)
                or not hmac.compare_digest(mac,hmac.new(self._key,_DOMAIN+canonical(body),hashlib.sha256).hexdigest())):
            raise ValueError('Commissioning review authentication failed')
        encoded=body['originals']
        if (type(encoded) is not dict or set(encoded)!=REQUIRED_CHECKS
                or any(type(v) is not str or len(v)>5464 for v in encoded.values())):
            raise ValueError('Exact bounded original set required')
        originals={name:base64.b64decode(value,validate=True) for name,value in encoded.items()}
        checks,expiry=_reviews(request,originals,now_ns)
        refs=tuple(sorted(request.to_dict()['references'].items()))
        if (type(connection_id) is not str or not re.fullmatch(r'operation-[a-f0-9]{32}',connection_id)
                or connection_id!=request.to_dict()['attempt_id'] or current_references!=refs):
            raise ValueError('Owned connection or current reference mismatch')
        return FirstMotionReviewEvidence(request.request_sha256,connection_id,refs,checks,now_ns,expiry)


@dataclass(frozen=True, slots=True)
class FirstMotionCurrentContext:
    """Owned provider observations; this data type is not physical attestation."""
    connection_id: str
    usb_identity: tuple
    references: tuple
    observed_ns: int
    port_name: str


class AuthenticatedFirstMotionReviewReader:
    """Re-read originals before each admission/open/write check; no cached permit.

    The host owns the context provider, root, selected measurement and protected
    key. A future native composition must implement current context from actual
    supervised metadata and original reconstruction, not browser declarations.
    """
    def __init__(self,request,*,authority,root,measurement_session_id,
                 measurement_operation_id,context_reader,clock_ns=time.monotonic_ns):
        if (type(request) is not FirstMotionRequest or type(authority) is not FirstMotionReviewAuthority
                or not callable(context_reader) or not callable(clock_ns)):
            raise ValueError('Exact commissioning host dependencies required')
        self.request=request
        self._authority=authority
        self._root=safe_root(Path(root))
        self._session=measurement_session_id
        self._operation=measurement_operation_id
        self._context=context_reader
        self._clock=clock_ns

    def __call__(self):
        return self.verify_endpoint(None)

    def verify_endpoint(self,port_name):
        from rocell.application.first_motion_measurements import load_measurement_for_request
        body=self.request.to_dict()
        if port_name is not None and (type(port_name) is not str
                or not re.fullmatch(r'COM[1-9][0-9]{0,3}',port_name) or int(port_name[3:])>4096):
            raise ValueError('Exact bounded Windows endpoint required')
        raw=read_bounded_regular_file(contained_path(self._root,
            body['attempt_id']+'-first-motion-reviews.json',label='commissioning reviews'),
            maximum_bytes=MAX_BUNDLE_BYTES)
        # Perform file/measurement work before metadata so it cannot consume the
        # 100 ms current-observation window. Context must reconstruct all refs.
        load_measurement_for_request(self.request,root=self._root,session_id=self._session,
            operation_id=self._operation,check_current=lambda:None,clock_ns=self._clock)
        context=self._context()
        now=self._clock()
        identity=body['usb_identity']
        if (type(now) is not int or not 0<now<2**63 or type(context) is not FirstMotionCurrentContext
                or context.connection_id!=body['attempt_id']
                or context.usb_identity!=(identity['vid'],identity['pid'],identity['serial_number'])
                or type(context.port_name) is not str
                or not re.fullmatch(r'COM[1-9][0-9]{0,3}',context.port_name)
                or int(context.port_name[3:])>4096
                or (port_name is not None and context.port_name!=port_name)
                or type(context.observed_ns) is not int
                or not body['issued_monotonic_ns']<=context.observed_ns<=now
                or now-context.observed_ns>100_000_000):
            raise ValueError('Current commissioning identity/port context missing or stale')
        return self._authority.verify(self.request,raw,connection_id=context.connection_id,
            current_references=context.references,now_ns=now)
