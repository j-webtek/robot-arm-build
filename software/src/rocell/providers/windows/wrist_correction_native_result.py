"""Small correction result reference, never a child-supplied success verdict.

The bounded original stays in the assigned store. Loading verifies byte
identity and process-record association only; endpoint/lifecycle reconstruction
is a separate required step before accepting any physical result.
"""
from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import (
    safe_root,contained_path,read_bounded_regular_file)
from rocell.application.wrist_correction_worker_claim import verify_correction_worker_receipt
from .wrist_correction_native_protocol import decode_request,digest,require,RESULT_SCHEMA
from .owned_worker_process import decode_owned_json,_hash

SCHEMA=RESULT_SCHEMA
MAX_BYTES=8192
MAX_OUTCOME_BYTES=512*1024


def decode_outcome(raw):
    # Retained outcomes contain both collector envelopes and trial projections:
    # up to 256 baseline + 512 post read windows, repeated twice, plus final
    # capture and fixed summaries. The small IPC reference keeps its 4096-node
    # default; only this bounded retained artifact needs the larger budget.
    return decode_owned_json(raw,maximum=MAX_OUTCOME_BYTES,maximum_nodes=16384)


def _name(wire):
    return wire['attempt_id']+'-wrist-correction-outcome.original.json'


def decode_result(raw,*,request_raw):
    wire=decode_request(request_raw)
    result=decode_owned_json(raw,maximum=MAX_BYTES)
    require(type(result) is dict and set(result)=={'schema','request_sha256','attempt_id',
        'claim_sha256','outcome','physical_authority','replay_allowed'},'Exact correction result reference required')
    require(result['schema']==SCHEMA and result['request_sha256']==wire['request_sha256']
        and result['attempt_id']==wire['attempt_id'] and result['physical_authority'] is False
        and result['replay_allowed'] is False,'Correction result association mismatch')
    _hash(result['claim_sha256'])
    outcome=result['outcome']
    require(type(outcome) is dict and set(outcome)=={'file','bytes','sha256'}
        and outcome['file']==_name(wire) and type(outcome['bytes']) is int
        and 0<outcome['bytes']<=MAX_OUTCOME_BYTES,'Exact bounded outcome reference required')
    _hash(outcome['sha256'])
    return result


def encode_result(child,*,request_raw):
    wire=decode_request(request_raw)
    require(type(child) is dict and child.get('schema')=='rocell.claimed_wrist_correction_trial.v1'
        and child.get('owned_process_verified') is False and child.get('physical_authority') is False
        and child.get('replay_allowed') is False,'Non-authorizing claimed child result required')
    owned=child.get('result')
    receipt=owned.get('outcome_retention') if type(owned) is dict else None
    require(type(receipt) is dict and set(receipt)=={'status','file','bytes','sha256'}
        and receipt['status']=='RETAINED','Retained outcome required for result reference')
    raw=canonical(dict(schema=SCHEMA,request_sha256=wire['request_sha256'],attempt_id=wire['attempt_id'],
        claim_sha256=child['claim_sha256'],outcome={k:receipt[k] for k in ('file','bytes','sha256')},
        physical_authority=False,replay_allowed=False))
    decode_result(raw,request_raw=request_raw)
    return raw


def load_result_original(raw,*,request_raw,assigned_root,authority,
        owned_process_id,process_started_ns,process_finished_ns):
    """Resolve fixed filename and reconcile receipt using actual owner inputs.

    Returned bytes still require semantic reconstruction, not JSON status trust.
    Parent time/PID observations must come from the process owner, never the wire.
    """
    result=decode_result(raw,request_raw=request_raw)
    wire=decode_request(request_raw)
    root=safe_root(assigned_root)
    # Receipt verification also enforces root equality via evidence loading.
    receipt=verify_correction_worker_receipt(wire['payload'],root=root,authority=authority,
        claim_sha256=result['claim_sha256'],owned_process_id=owned_process_id,
        process_started_ns=process_started_ns,process_finished_ns=process_finished_ns)
    original=read_bounded_regular_file(contained_path(root,_name(wire),label='correction outcome'),
        maximum_bytes=MAX_OUTCOME_BYTES)
    require(len(original)==result['outcome']['bytes'] and digest(original)==result['outcome']['sha256'],
        'Retained correction outcome changed')
    decoded=decode_outcome(original)
    require(type(decoded) is dict and canonical(decoded)==original
        and decoded.get('schema')=='rocell.owned_wrist_correction_trial.v1',
        'Canonical correction outcome required')
    return dict(original_bytes=original,worker_receipt=receipt,
        endpoint_verified=False,process_containment_verified=False,campaign_advance_allowed=False)
