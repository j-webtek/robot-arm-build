"""Re-resolve campaign identity and review originals without opening serial.

Uses the existing persistent-controller resolver. Metadata is not proof of
firmware, power, clearance, physical stop behavior, or a subsequent open handle.
"""
from dataclasses import dataclass
import re
import time

from .endpoint_current_context import EndpointCurrentContextReader
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent, PositionalCampaignReviewAuthority
from rocell.application.physical_onboarding_durability import safe_root, contained_path, read_bounded_regular_file


@dataclass(frozen=True,slots=True)
class PositionalCurrentContext:
    connection_id: str
    usb_identity: tuple
    references: tuple
    observed_ns: int
    port_name: str


class PositionalCurrentContextReader(EndpointCurrentContextReader):
    @staticmethod
    def _accept_request(request):
        return type(request) is PositionalCampaignIntent

    @staticmethod
    def _context_body(request):
        body = request.to_dict()
        return dict(body,issued_monotonic_ns=body['issued_ns'],deadline_monotonic_ns=body['deadline_ns'])

    @staticmethod
    def _make_context(connection,identity,references,observed_ns,port):
        return PositionalCurrentContext(connection,identity,references,observed_ns,port)

    def __init__(self,request,*,connection_id,**kwargs):
        if type(request) is not PositionalCampaignIntent or connection_id != request.to_dict()['campaign_id']:
            raise ValueError('Exact campaign and owned connection required')
        super().__init__(request,connection_id=connection_id,**kwargs)


class AuthenticatedPositionalReader:
    """Internal composition only: no browser-supplied callbacks or review paths."""
    def __init__(self,request,*,root,authority,context_reader,clock_ns=time.monotonic_ns):
        if (type(request) is not PositionalCampaignIntent
                or type(authority) is not PositionalCampaignReviewAuthority
                or type(context_reader) is not PositionalCurrentContextReader
                or context_reader._request != request or not callable(clock_ns)):
            raise ValueError('Exact campaign authority and context reader required')
        self.request,self._authority,self._context,self._clock = request,authority,context_reader,clock_ns
        self._root = safe_root(root)

    def verify_endpoint(self,port_name=None):
        if port_name is not None and (type(port_name) is not str
                or not re.fullmatch('COM[1-9][0-9]{0,3}',port_name) or int(port_name[3:])>4096):
            raise ValueError('Bounded pinned COM endpoint required')
        body = self.request.to_dict()
        raw = read_bounded_regular_file(contained_path(self._root,
            body['campaign_id']+'-positional-review.json',label='campaign review'),maximum_bytes=24576)
        context = self._context()
        now = self._clock()
        if (type(context) is not PositionalCurrentContext
                or context.connection_id != body['campaign_id'] or type(now) is not int
                or not body['issued_ns']<=context.observed_ns<=now
                or now-context.observed_ns>100_000_000
                or (port_name is not None and context.port_name != port_name)):
            raise ValueError('Campaign context stale or changed')
        evidence = self._authority.verify(raw,intent=self.request,
            current_usb_identity=dict(zip(('vid','pid','serial_number'),context.usb_identity)),
            current_references=dict(context.references),now_ns=now)
        return dict(evidence,connection_id=context.connection_id,port_name=context.port_name,
            usb_identity=context.usb_identity)
