"""Durable open/baseline/dispatch selection for a single correction attempt.

No COM calls or native permits. The future exact serial facade must consume
this binding through its own owned-open/write boundaries, not accept JSON.
"""
import base64
import hashlib
import os
from threading import Event, Lock

from rocell.arm.protocol import encode_line
from rocell.providers.windows.wrist_correction_current_context import AuthenticatedWristCorrectionReader
from .first_motion_contract import canonical
from .physical_onboarding_durability import safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file
from .wrist_correction_consumption import WristCorrectionConsumption


class WristCorrectionCommandBinding:
    def __init__(self, *, reader, root, cancellation):
        if type(reader) is not AuthenticatedWristCorrectionReader or not isinstance(cancellation,Event):
            raise ValueError('Exact correction reader and cancellation signal required')
        self._reader,self._root,self._cancel=reader,safe_root(root),cancellation
        if self._root!=reader._root:
            raise ValueError('Correction binding must use the original review store')
        self._body=reader.request.to_dict()
        self._state,self._lock,self._records='HELD',Lock(),[]
        self._revoked=False
        self._pid,self._last=os.getpid(),0
        evidence=self._check()
        self._port,self._plan=evidence['port_name'],evidence['plan_sha256']
        self._save('opening-reservation',dict(plan_sha256=self._plan,port_name=self._port,owner_pid=self._pid))
        self._state='RESERVED'

    def _save(self,suffix,body):
        name=self._body['attempt_id']+'-wrist-correction-'+suffix+'.json'
        data=canonical(body)
        publish_reservation_bytes(self._root,name,data,maximum_bytes=65536)
        self._records.append((name,hashlib.sha256(data).hexdigest()))

    def _check(self):
        if self._cancel.is_set() or os.getpid()!=self._pid:
            raise ValueError('Correction cancelled or process owner changed')
        for name,digest in self._records:
            raw=read_bounded_regular_file(contained_path(self._root,name,label='correction binding'),maximum_bytes=65536)
            if hashlib.sha256(raw).hexdigest()!=digest:
                raise ValueError('Correction binding record changed')
        evidence=self._reader.verify_endpoint(getattr(self,'_port',None))
        now=evidence['verified_at_ns']
        if now<self._last or evidence['plan_sha256']!=getattr(self,'_plan',evidence['plan_sha256']):
            raise ValueError('Correction plan changed or clock regressed')
        self._last=now
        return evidence

    def claim_open(self):
        with self._lock:
            if self._state!='RESERVED': raise ValueError('Correction open already claimed or held')
            self._state='HELD'
            self._check()
            self._save('open-claim',dict(plan_sha256=self._plan,claimed_ns=self._last))
            self._check()
            self._state='OPEN_CLAIMED'

    def validate_open_claim(self):
        with self._lock:
            if self._state!='OPEN_CLAIMED': raise ValueError('No correction open claim')
            try: self._check()
            except BaseException:
                self._state='HELD'
                raise

    def bind_baseline(self,raw,windows,*,started_ns,finished_ns):
        with self._lock:
            if self._state!='OPEN_CLAIMED': raise ValueError('Correction open claim required')
            self._state='HELD'
            self._check()
            plan=read_bounded_regular_file(contained_path(self._root,self._body['attempt_id']+'-wrist-correction-plan-review.json',label='correction plan'),maximum_bytes=65536)
            if hashlib.sha256(plan).hexdigest()!=self._plan:
                raise ValueError('Correction plan changed before baseline binding')
            bundle,samples,framing=self._reader._authority.bind_review_from_capture(plan,
                context=self._body,originals=self._reader._originals,raw=raw,windows=windows,
                started_ns=started_ns,finished_ns=finished_ns,now_ns=self._last,expected_basis=self._reader._basis)
            self._save('owned-selection',dict(raw_base64=base64.b64encode(raw).decode(),read_windows=windows,
                started_ns=started_ns,finished_ns=finished_ns,review_base64=base64.b64encode(bundle).decode(),framing=framing))
            self._check()
            self._scope=WristCorrectionConsumption(authority=self._reader._authority,bundle=bundle,
                context=self._body,originals=self._reader._originals,samples=samples,
                basis=self._reader._basis,root=self._root,clock_ns=self._reader._clock)
            reviewed=self._reader._authority.verify(bundle,expected_context=self._body,
                originals=self._reader._originals,samples=samples,now_ns=self._last,expected_basis=self._reader._basis)
            self._payload=encode_line(reviewed['candidate_command'])
            self._acquired=samples[-1]['host_received_ns']
            self._state='BOUND'
            return framing

    def selected_payload(self):
        """Token construction only; dispatch must still consume and revalidate."""
        with self._lock:
            if self._state not in ('BOUND','FINAL_BOUND'): raise ValueError('No bound correction payload')
            return self._payload

    def prepare_final_dispatch(self,connection):
        """Prepare only the collector-owned final evidence, not arbitrary JSON."""
        from .wrist_correction_final_consumption import FinalReadbackConsumption
        with self._lock:
            proof=getattr(self,'_final_capture_proof',None)
            if self._revoked or self._state!='HELD' or proof is None or proof[0] is not connection:
                raise ValueError('Owned final capture required for this exact connection')
            del self._final_capture_proof  # a failed preparation cannot be retried
            if self._cancel.is_set() or os.getpid()!=self._pid or connection._phase!='OPEN' or connection._write_attempted:
                raise ValueError('Final dispatch preparation context changed')
            prefix=self._body['attempt_id']+'-wrist-correction-final-'
            claim=read_bounded_regular_file(contained_path(self._root,prefix+'capture-claim.json',label='final capture claim'),maximum_bytes=65536)
            capture=read_bounded_regular_file(contained_path(self._root,prefix+'capture.original.json',label='final capture'),maximum_bytes=128*1024)
            if (hashlib.sha256(claim).hexdigest(),hashlib.sha256(capture).hexdigest())!=proof[1:]:
                raise ValueError('Owned final capture originals changed')
            evidence=dict(original_bundle=self._scope._bundle,context=self._body,
                originals=self._reader._originals,samples=self._scope._samples,basis=self._reader._basis,
                claim_raw=claim,capture_raw=capture,owned_process_id=self._pid,now_ns=self._reader._clock())
            sealed=self._reader._authority.seal_final_readback(**evidence)
            owned_api=connection._api
            def current():
                if (connection._request is not self._reader.request or connection._phase!='OPEN'
                        or connection._api is not owned_api
                        or connection._api.connection_id!=self._body['attempt_id']
                        or self._cancel.is_set() or os.getpid()!=self._pid):
                    raise ValueError('Final dispatch connection/owner changed')
            self._final_scope=FinalReadbackConsumption(root=self._root,authority=self._reader._authority,
                review_raw=sealed,evidence=evidence,cancellation=self._cancel,
                clock_ns=self._reader._clock,check_current=current)
            self._state='FINAL_BOUND'

    def consume_command(self):
        with self._lock:
            if self._state=='FINAL_BOUND':
                self._state='HELD'
                self._check()  # same first native identity check as legacy dispatch
                claim=self._final_scope.consume()
                if encode_line(claim['candidate_command'])!=self._payload:
                    raise ValueError('Final consumed command differs from selected payload')
                self._check()  # same second identity check; no extra inventory budget
                now=self._reader._clock()
                if now<self._last or now-claim['last_received_ns']>100_000_000 or now>=self._body['deadline_ns']:
                    raise ValueError('Final readback expired before native dispatch')
                self._final_dispatch_checked_ns=now
                self._state='CONSUMED'
                return self._payload
            if self._state!='BOUND': raise ValueError('No unconsumed correction command')
            self._state='HELD'
            self._check()
            if self._last-self._acquired>100_000_000:
                raise ValueError('Selected correction baseline expired')
            claim=self._scope.consume()
            if encode_line(claim['candidate_command'])!=self._payload:
                raise ValueError('Consumed correction differs from selected payload')
            self._check()
            if self._last-self._acquired>100_000_000:
                raise ValueError('Correction baseline expired after consumption')
            self._state='CONSUMED'
            return encode_line(claim['candidate_command'])

    def revoke(self):
        with self._lock:
            self._revoked=True
            self._state='HELD'
            if hasattr(self,'_scope'): self._scope.revoke()
            if hasattr(self,'_final_scope'): self._final_scope.revoke()
            if hasattr(self,'_final_capture_proof'): del self._final_capture_proof
