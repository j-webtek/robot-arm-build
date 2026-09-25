"""Durably consume one authenticated final readback; never opens or writes COM.

The exact native binding must separately admit the returned command. Failures
hold this object; an existing durable consumption prevents reconstruction/replay.
"""
import base64
import json
import os
from threading import Event,Lock
from .first_motion_contract import canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .physical_onboarding_durability import safe_root,contained_path,read_bounded_regular_file,publish_reservation_bytes
from rocell.safety.wrist_correction_review_authority import WristCorrectionReviewAuthority
from rocell.providers.windows.wrist_correction_native_protocol import digest,require


class FinalReadbackConsumption:
    def __init__(self,*,root,authority,review_raw,evidence,cancellation,clock_ns,check_current):
        require(type(authority) is WristCorrectionReviewAuthority and type(review_raw) is bytes
            and type(evidence) is dict and type(cancellation) is Event and callable(clock_ns)
            and callable(check_current),'Exact final consumption inputs required')
        self._root=safe_root(root);self._authority=authority;self._review=review_raw
        self._args=dict(evidence)
        self._args['context']=json.loads(canonical(evidence['context']))
        self._args['samples']=json.loads(canonical(evidence['samples']))
        self._args['originals']=list(evidence['originals'])
        self._cancel=cancellation;self._clock=clock_ns;self._current=check_current
        self._pid=os.getpid();self._last=0;self._lock=Lock();self._state='HELD';self._consumed=None;self._reservation=None
        self._prefix=evidence['context']['attempt_id']+'-wrist-correction-'
        self._name=self._prefix+'final-consumed.json'
        require(not self._path(self._name).exists(),'Final readback already consumed')
        self._verify()
        reservation=canonical(dict(schema='rocell.wrist_correction_final_reservation.v1',
            review_sha256=digest(review_raw),owner_pid=self._pid,reserved_ns=self._last))
        publish_reservation_bytes(self._root,self._prefix+'final-reservation.json',reservation,maximum_bytes=65536)
        self._reservation=reservation
        self._verify()
        self._state='READY'

    def _path(self,name):
        return contained_path(self._root,name,label='final consumption original')

    def _read(self,name,maximum=65536):
        return read_bounded_regular_file(self._path(name),maximum_bytes=maximum)

    def _verify(self):
        require(not self._cancel.is_set() and os.getpid()==self._pid
            and self._args['owned_process_id']==self._pid and self._current() is None,
            'Final consumption cancelled or current owner/context changed')
        now=self._clock()
        require(type(now) is int and now>=self._last,'Final consumption clock regressed')
        self._last=now
        args=dict(self._args,now_ns=now)
        verified=self._authority.verify_final_readback(self._review,**args)
        require(not self._path(self._prefix+'consumed.json').exists(),'Legacy command consumption already exists')
        require(self._read(self._prefix+'final-capture-claim.json')==args['claim_raw']
            and self._read(self._prefix+'final-capture.original.json',128*1024)==args['capture_raw'],
            'Retained final capture changed')
        claim=decode_diagnostic_json(args['claim_raw'],maximum=65536)
        selection_raw=None
        for name,expected in claim['record_hashes'].items():
            raw=self._read(name)
            require(digest(raw)==expected,'Retained original selection changed')
            if name==self._prefix+'owned-selection.json': selection_raw=raw
        # Parse the same bytes whose hash was just checked, rather than opening
        # the selection a second time. Every verification rereads all records.
        selection=decode_diagnostic_json(selection_raw,maximum=65536)
        require(base64.b64decode(selection['review_base64'],validate=True)==args['original_bundle'],
            'Final consumption original review differs from owned selection')
        if self._consumed is not None:
            require(self._read(self._name)==self._consumed,'Final consumption record changed')
        if self._reservation is not None:
            require(self._read(self._prefix+'final-reservation.json')==self._reservation,'Final reservation changed')
        # File verification can itself consume the remaining freshness budget.
        # Do not return an age measured only before those reads completed.
        finished=self._clock()
        require(type(finished) is int and finished>=now and finished<verified['deadline_ns']
            and finished-verified['last_received_ns']<=100_000_000,
            'Final readback expired during retained-record verification')
        require(not self._cancel.is_set() and os.getpid()==self._pid,'Final consumption owner changed during verification')
        self._last=finished
        verified['verified_at_ns']=finished
        return verified

    def consume(self):
        with self._lock:
            require(self._state=='READY','Final consumption already attempted or held')
            self._state='HELD'
            before=self._verify()
            record=dict(schema='rocell.wrist_correction_final_consumption.v1',
                request_sha256=before['request_sha256'],review_sha256=digest(self._review),
                review_base64=base64.b64encode(self._review).decode(),claim_sha256=before['claim_sha256'],
                capture_sha256=before['capture_sha256'],owner_pid=self._pid,claimed_ns=before['verified_at_ns'],
                last_received_ns=before['last_received_ns'],candidate_command=before['candidate_command'],
                nominal_endpoint_rad=before['nominal_endpoint_rad'],motion_authorized=False)
            raw=canonical(record)
            publish_reservation_bytes(self._root,self._name,raw,maximum_bytes=65536)
            self._consumed=raw
            after=self._verify()  # includes the unchanged 100 ms final-age gate
            require(after['candidate_command']==before['candidate_command']
                and after['review_sha256']==before['review_sha256'],'Final command changed during consumption')
            self._state='CONSUMED'
            return dict(record,record_sha256=digest(raw),native_dispatch_implemented=False)

    def revoke(self):
        with self._lock: self._state='HELD'
