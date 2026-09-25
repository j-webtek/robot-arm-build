"""One-use correction worker records; not executable or motor approval.

The launcher separately verifies its executable/package and owns the process.
These records bind the full evidence-bearing handoff to one process and one
consumption. A failed claim/consumption is never repaired or retried.
"""
import os
from threading import Lock

from .first_motion_contract import canonical
from .physical_onboarding_durability import (
    safe_root, contained_path, publish_reservation_bytes, read_bounded_regular_file)
from rocell.providers.windows.wrist_correction_native_protocol import (
    validate_payload, digest, require)
from rocell.providers.windows.wrist_correction_evidence_store import authenticate_evidence
from rocell.providers.windows.owned_worker_process import decode_owned_json

_ISSUER = object()


def _name(payload, stage):
    require(stage in ('launch','worker-claimed','worker-consumed'), 'Invalid correction record stage')
    return payload['context']['attempt_id']+'-wrist-correction-'+stage+'.json'


def _read(root, payload, stage):
    raw = read_bounded_regular_file(contained_path(root,_name(payload,stage),label='correction worker'),
        maximum_bytes=65536)
    body = decode_owned_json(raw,maximum=65536)
    require(canonical(body)==raw, 'Canonical correction worker record required')
    return raw,body


def _selection(payload):
    # The launch hash is returned by reservation; excluding it avoids a
    # self-referential digest. Every other handoff field remains bound.
    return {k:v for k,v in payload.items() if k!='launch_sha256'}


def reserve_correction_launch(payload, *, root, authority, now_ns):
    request = validate_payload(payload)
    request.require_start_time(now_ns)
    require(now_ns+27_000_000_000<=request.to_dict()['deadline_ns'], 'Insufficient supervisor launch time')
    authenticate_evidence(payload,assigned_root=root,authority=authority,now_ns=now_ns)
    raw = canonical(dict(schema='rocell.wrist_correction_launch.v1',selection=_selection(payload),
        reserved_ns=now_ns,process_may_have_started=True,replay_allowed=False,physical_authority=False))
    publish_reservation_bytes(root,_name(payload,'launch'),raw,maximum_bytes=65536)
    require(_read(root,payload,'launch')[0]==raw,'Correction launch readback mismatch')
    return digest(raw)


def _verify(payload, root, authority, source, runtime, now_ns):
    request = validate_payload(payload)
    request.require_start_time(now_ns)
    context = request.to_dict()
    require(source==context['references']['source_sha256'] and
        runtime==context['references']['runtime_sha256'],'Correction worker references changed')
    raw,body = _read(root,payload,'launch')
    require(set(body)=={'schema','selection','reserved_ns','process_may_have_started','replay_allowed','physical_authority'}
        and body['schema']=='rocell.wrist_correction_launch.v1' and digest(raw)==payload['launch_sha256']
        and body['selection']==_selection(payload) and type(body['reserved_ns']) is int
        and context['issued_ns']<=body['reserved_ns']<=now_ns
        and body['process_may_have_started'] is True and body['replay_allowed'] is False
        and body['physical_authority'] is False,'Correction launch association changed')
    authenticate_evidence(payload,assigned_root=root,authority=authority,now_ns=now_ns)


class WristCorrectionWorkerClaim:
    def __init__(self,issuer,payload,root,authority,raw):
        require(issuer is _ISSUER,'Correction claim issuer required')
        self._payload=canonical(payload)
        self._root,self._authority,self._raw=root,authority,raw
        self._pid,self._used,self._lock=os.getpid(),False,Lock()

    @property
    def claim_sha256(self):
        return digest(self._raw)

    def consume(self,payload,*,current_source_sha256,current_runtime_sha256,now_ns):
        with self._lock:
            require(not self._used,'Correction worker claim already used')
            self._used=True
            require(os.getpid()==self._pid and canonical(payload)==self._payload,
                'Correction worker process or operation changed')
            claimed=decode_owned_json(self._raw,maximum=8192)
            require(type(now_ns) is int and now_ns>=claimed['claimed_ns'],
                'Correction consumption clock predates claim')
            _verify(payload,self._root,self._authority,current_source_sha256,current_runtime_sha256,now_ns)
            require(_read(self._root,payload,'worker-claimed')[0]==self._raw,'Correction claim original changed')
            raw=canonical(dict(schema='rocell.wrist_correction_worker_consumed.v1',
                claim_sha256=self.claim_sha256,operation_sha256=digest(self._payload),
                pid=self._pid,consumed_ns=now_ns,replay_allowed=False,physical_authority=False))
            publish_reservation_bytes(self._root,_name(payload,'worker-consumed'),raw,maximum_bytes=8192)
            require(_read(self._root,payload,'worker-consumed')[0]==raw,'Correction consumption readback mismatch')


def claim_correction_worker(payload,*,root,authority,current_source_sha256,current_runtime_sha256,now_ns):
    root=safe_root(root)
    _verify(payload,root,authority,current_source_sha256,current_runtime_sha256,now_ns)
    raw=canonical(dict(schema='rocell.wrist_correction_worker_claim.v1',
        operation_sha256=digest(canonical(payload)),launch_sha256=payload['launch_sha256'],
        pid=os.getpid(),claimed_ns=now_ns,replay_allowed=False,physical_authority=False))
    publish_reservation_bytes(root,_name(payload,'worker-claimed'),raw,maximum_bytes=8192)
    require(_read(root,payload,'worker-claimed')[0]==raw,'Correction claim readback mismatch')
    return WristCorrectionWorkerClaim(_ISSUER,payload,root,authority,raw)


def verify_correction_worker_receipt(payload,*,root,authority,claim_sha256,
        owned_process_id,process_started_ns,process_finished_ns):
    """Reconcile records against parent observations, not child-supplied PID.

    This proves record association only. The caller must supply observations
    from its actual process owner and separately qualify cleanup and endpoint.
    Late process completion may be diagnosed but never treated as on-time.
    """
    request=validate_payload(payload)
    context=request.to_dict()
    require(type(owned_process_id) is int and 0<owned_process_id<2**32,
        'Bounded parent-observed PID required')
    require(type(process_started_ns) is int and type(process_finished_ns) is int and
        context['issued_ns']<=process_started_ns<=process_finished_ns<2**63,
        'Ordered parent process timestamps required')
    root=safe_root(root)
    raw,claim=_read(root,payload,'worker-claimed')
    require(set(claim)=={'schema','operation_sha256','launch_sha256','pid','claimed_ns',
        'replay_allowed','physical_authority'} and claim['schema']=='rocell.wrist_correction_worker_claim.v1'
        and digest(raw)==claim_sha256 and claim['operation_sha256']==digest(canonical(payload))
        and claim['launch_sha256']==payload['launch_sha256'] and type(claim['pid']) is int
        and claim['pid']==owned_process_id and type(claim['claimed_ns']) is int
        and process_started_ns<=claim['claimed_ns']<=process_finished_ns
        and claim['replay_allowed'] is False and claim['physical_authority'] is False,
        'Correction claim differs from parent observation')
    consumed_raw,consumed=_read(root,payload,'worker-consumed')
    require(set(consumed)=={'schema','claim_sha256','operation_sha256','pid','consumed_ns',
        'replay_allowed','physical_authority'} and consumed['schema']=='rocell.wrist_correction_worker_consumed.v1'
        and consumed['claim_sha256']==claim_sha256 and consumed['operation_sha256']==digest(canonical(payload))
        and type(consumed['pid']) is int and consumed['pid']==owned_process_id
        and type(consumed['consumed_ns']) is int
        and claim['claimed_ns']<=consumed['consumed_ns']<=process_finished_ns
        and consumed['replay_allowed'] is False and consumed['physical_authority'] is False,
        'Correction consumption differs from parent observation')
    for stamp in (claim['claimed_ns'],consumed['consumed_ns']):
        _verify(payload,root,authority,context['references']['source_sha256'],
            context['references']['runtime_sha256'],stamp)
    _,launch=_read(root,payload,'launch')
    require(launch['reserved_ns']<=process_started_ns,'Correction reservation postdates process launch')
    # Detect replacement during reconciliation; immutable storage is still
    # required by the owner for the complete trial lifetime.
    require(_read(root,payload,'worker-claimed')[0]==raw and
        _read(root,payload,'worker-consumed')[0]==consumed_raw,'Correction receipt changed during verification')
    return dict(schema='rocell.wrist_correction_worker_receipt.v1',claim_sha256=claim_sha256,
        consumption_sha256=digest(consumed_raw),owned_process_id=owned_process_id,
        claimed_ns=claim['claimed_ns'],consumed_ns=consumed['consumed_ns'],
        records_consistent=True,finished_within_deadline=process_finished_ns<=context['deadline_ns'],
        process_containment_verified=False,endpoint_verified=False,physical_authority=False,replay_allowed=False)
