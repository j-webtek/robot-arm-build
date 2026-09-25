"""Pinned Windows metadata and signed correction plan checks; never opens COM."""
from dataclasses import dataclass
import hashlib
import re
import time

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.physical_onboarding_durability import safe_root, contained_path, read_bounded_regular_file
from rocell.safety.wrist_correction_review_authority import WristCorrectionReviewAuthority, CONTEXT_FIELDS
from rocell.safety.observational_review_authority import validate_observational_context
from .endpoint_current_context import EndpointCurrentContextReader


@dataclass(frozen=True,slots=True)
class WristCorrectionContextRequest:
    canonical_bytes: bytes

    def __post_init__(self):
        self.to_dict()

    @property
    def request_sha256(self):
        return hashlib.sha256(self.canonical_bytes).hexdigest()

    def require_start_time(self,now_ns):
        body=self.to_dict()
        validate_observational_context(body,now_ns)
        if now_ns+11_000_000_000>body['deadline_ns']:
            raise ValueError('Insufficient correction connection start budget')

    def runtime_body(self):
        from rocell.application.first_motion_contract import fixed_limits
        body=self.to_dict();limits=fixed_limits()
        limits['maximum_baseline_bytes']=16384
        return dict(body,limits=limits,issued_monotonic_ns=body['issued_ns'],deadline_monotonic_ns=body['deadline_ns'])

    def to_dict(self):
        if type(self.canonical_bytes) is not bytes:
            raise ValueError('Immutable correction context required')
        body=decode_diagnostic_json(self.canonical_bytes,maximum=8192)
        if type(body) is not dict or set(body)!=CONTEXT_FIELDS or canonical(body)!=self.canonical_bytes:
            raise ValueError('Exact canonical correction context required')
        validate_observational_context(body,body['issued_ns'])
        return body


@dataclass(frozen=True,slots=True)
class WristCorrectionCurrentContext:
    connection_id: str
    usb_identity: tuple
    references: tuple
    observed_ns: int
    port_name: str


class WristCorrectionCurrentContextReader(EndpointCurrentContextReader):
    @staticmethod
    def _accept_request(request):
        return type(request) is WristCorrectionContextRequest

    @staticmethod
    def _context_body(request):
        body=request.to_dict()
        return dict(body,issued_monotonic_ns=body['issued_ns'],deadline_monotonic_ns=body['deadline_ns'])

    @staticmethod
    def _make_context(connection,identity,references,observed_ns,port):
        return WristCorrectionCurrentContext(connection,identity,references,observed_ns,port)

    def __init__(self,request,*,connection_id,**kwargs):
        if type(request) is not WristCorrectionContextRequest or connection_id!=request.to_dict()['attempt_id']:
            raise ValueError('Exact correction request/connection required')
        super().__init__(request,connection_id=connection_id,**kwargs)


class AuthenticatedWristCorrectionReader:
    def __init__(self,request,*,root,authority,context_reader,originals,expected_basis,clock_ns=time.monotonic_ns):
        if (type(request) is not WristCorrectionContextRequest or type(authority) is not WristCorrectionReviewAuthority
                or type(context_reader) is not WristCorrectionCurrentContextReader or context_reader._request!=request
                or type(originals) is not list or not callable(clock_ns)):
            raise ValueError('Exact correction reader dependencies required')
        self.request=request
        self._root=safe_root(root)
        self._authority,self._context,self._clock=authority,context_reader,clock_ns
        self._originals,self._basis=list(originals),expected_basis

    def verify_endpoint(self,port_name=None):
        if port_name is not None and (type(port_name) is not str or not re.fullmatch('COM[1-9][0-9]{0,3}',port_name) or int(port_name[3:])>4096):
            raise ValueError('Exact bounded COM endpoint required')
        body=self.request.to_dict()
        raw=read_bounded_regular_file(contained_path(self._root,body['attempt_id']+'-wrist-correction-plan-review.json',label='correction plan'),maximum_bytes=65536)
        current=self._context();now=self._clock()
        if (type(current) is not WristCorrectionCurrentContext or current.connection_id!=body['attempt_id']
                or type(now) is not int or not body['issued_ns']<=current.observed_ns<=now
                or now-current.observed_ns>100_000_000 or (port_name is not None and current.port_name!=port_name)
                or current.usb_identity!=(body['usb_identity']['vid'],body['usb_identity']['pid'],body['usb_identity']['serial_number'])
                or current.references!=tuple(sorted(body['references'].items()))):
            raise ValueError('Correction current context stale or changed')
        result=self._authority.verify_plan(raw,context=body,originals=self._originals,now_ns=now,expected_basis=self._basis)
        return dict(result,connection_id=current.connection_id,port_name=current.port_name,
                    usb_identity=current.usb_identity,native_open_authorized=False)
