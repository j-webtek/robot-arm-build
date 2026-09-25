"""Dedicated micro transport component; NOT registered as a wizard action.

Construction sends nothing. The future commissioning composition must own the
real transport lease continuously and explicitly invoke the one-use runner.
Existing discrete transport accepts none of these binding types.
"""
import base64
import hashlib
import json
import math
import os
import time
from urllib.parse import quote_from_bytes

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import safe_root,publish_reservation_bytes
from rocell.safety.micro_command_admission import MicroCommandAdmission
from rocell.safety.micro_control_session import MicroControlSession
from rocell.arm.feedback import parse_feedback_1051,KNOWN_1051_FIELDS
from .arm_wifi_deadline import DeadlineFeedbackConnection,bounded_probe
from .arm_wifi_feedback import ADDRESS,MAC,neighbor_mac,unique_object


class MicroNativeBinding:
    """Separate one-use native latch; slow persistence cannot extend freshness."""
    def __init__(self,admission,session,*,root):
        if type(admission) is not MicroCommandAdmission or type(session) is not MicroControlSession:
            raise ValueError('Exact staged admission and cooperative session required')
        self.admission=admission;self.session=session;self.root=safe_root(root)
        self.used=False;self.pid=os.getpid()

    def claim(self,payload):
        if self.used:raise ValueError('Micro native boundary already attempted')
        self.used=True
        if os.getpid()!=self.pid or neighbor_mac()!=MAC:
            raise ValueError('Micro native identity mismatch')
        context=self.admission.snapshot()
        boundary=self.session.claim_staged_boundary(payload)
        if boundary['attempt_id']!=context['attempt_id'] or payload!=canonical(context['command']):
            raise ValueError('Micro session/admission binding mismatch')
        publish_reservation_bytes(self.root,context['attempt_id']+'-micro-native-send.json',
            canonical(dict(attempt_id=context['attempt_id'],boundary=boundary,
                           payload_sha256=hashlib.sha256(payload).hexdigest())))
        if not context['created_ns']<=time.perf_counter_ns()<=context['expires_ns'] or neighbor_mac()!=MAC:
            raise ValueError('Micro native identity changed or expired during persistence')


class _MicroConnection(DeadlineFeedbackConnection):
    _minimum_body_length=0

    def request(self,*args,**kwargs):
        raise ValueError('Exact micro dispatch only')

    def dispatch(self,binding,payload):
        if type(binding) is not MicroNativeBinding:raise ValueError('Exact micro binding required')
        self._check()
        binding.claim(payload)
        self._check()
        self._send_path('/js?json='+quote_from_bytes(payload,safe=''))


class NativeMicroTransport:
    def __init__(self,binding):
        if type(binding) is not MicroNativeBinding:raise ValueError('Exact micro binding required')
        self.binding=binding;self.receipt=None

    def identity(self):return neighbor_mac()

    def send_once(self,payload,*,deadline_ns,cancelled):
        connection=_MicroConnection(ADDRESS,cancelled=cancelled,deadline=deadline_ns/1e9)
        self.receipt=dict(status='UNCERTAIN',payload_sha256=hashlib.sha256(payload).hexdigest(),
                          cleanup_confirmed=False,receipt_used_as_endpoint=False)
        try:
            connection.dispatch(self.binding,payload)
            response=connection.getresponse()
            raw=response.read1(2049)
            if response.status!=200 or len(raw)>2048:raise ValueError('Bounded HTTP 200 required')
            data=json.loads(raw,object_pairs_hook=unique_object) if raw else None
            accepted=not raw or type(data) is dict and (not data or set(data)=={'ok'} and type(data['ok']) is int and data['ok']==1)
            if type(data) is dict and data.get('T')==1051:
                parse_feedback_1051(data)
                accepted=(set(data)<=KNOWN_1051_FIELDS and all(k in data for k in ('b','s','e','t','r','g'))
                          and all(type(v) in (int,float) and math.isfinite(v) for v in data.values()))
            if not accepted or neighbor_mac()!=MAC:raise ValueError('Receipt or identity rejected')
            self.receipt.update(status='HTTP_RECEIPT_ONLY',http_status=200,
                response_base64=base64.b64encode(raw).decode(),response_sha256=hashlib.sha256(raw).hexdigest(),
                controller_execution_acknowledged=False)
            return True
        finally:
            connection.close()
            self.receipt['cleanup_confirmed']=True

    def feedback(self,*,deadline_ns,cancelled):
        return bounded_probe(cancelled=cancelled,retain_response=True,deadline=deadline_ns/1e9)
