"""Reconcile correction originals with a fixed attempt store and publish once.

This verifies record consistency, not physical execution or Windows worker
ownership. No command is sent and a stored result cannot authorize a next leg.
"""
import hashlib
import base64

from rocell.arm.protocol import encode_line
from .first_motion_contract import canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wrist_correction_result_review import review_wrist_correction_result
from .physical_onboarding_durability import (
    safe_root, contained_path, read_bounded_regular_file, publish_reservation_bytes,
)


def reconcile_wrist_correction_result(raw, *, root, authority, bundle, context, originals, expected_basis):
    """Read-only reconstruction shared by child publication and parent review."""
    trial=decode_diagnostic_json(raw,maximum=160*1024)
    if type(trial) is dict and trial.get('schema')=='rocell.wrist_correction_trial.v2':
        return _reconcile_final_result(raw,root=root,authority=authority,bundle=bundle,
            context=context,originals=originals,expected_basis=expected_basis)
    report=review_wrist_correction_result(raw,authority=authority,bundle=bundle,
        context=context,originals=originals,expected_basis=expected_basis)
    root=safe_root(root)
    prefix=context['attempt_id']+'-wrist-correction-'
    def read(suffix):
        data=read_bounded_regular_file(contained_path(root,prefix+suffix+'.json',label='correction original'),
                                      maximum_bytes=16384)
        value=decode_diagnostic_json(data,maximum=16384)
        if canonical(value)!=data:
            raise ValueError('Canonical retained correction record required')
        return value,hashlib.sha256(data).hexdigest()
    reservation,rhash=read('reservation')
    claim,chash=read('consumed')
    verified=report['review']
    if (type(reservation) is not dict or set(reservation)!={'schema','intent_sha256','bundle_sha256','owner_pid','motion_authorized'}
            or reservation['schema']!='rocell.wrist_correction_reservation.v1'
            or type(reservation['owner_pid']) is not int or reservation['owner_pid']<=0
            or reservation['motion_authorized'] is not False
            or any(reservation[k]!=verified[k] for k in ('intent_sha256','bundle_sha256'))):
        raise ValueError('Retained correction reservation differs')
    trial=decode_diagnostic_json(raw,maximum=160*1024)
    expected=dict(schema='rocell.wrist_correction_consumption.v1',
        intent_sha256=verified['intent_sha256'],bundle_sha256=verified['bundle_sha256'],
        claimed_ns=claim.get('claimed_ns') if type(claim) is dict else None,
        payload_sha256=hashlib.sha256(encode_line(verified['candidate_command'])).hexdigest(),
        nominal_endpoint_rad=verified['nominal_endpoint_rad'],candidate_command=verified['candidate_command'],
        motion_authorized=False,native_dispatch_implemented=False)
    stamp=expected['claimed_ns']
    # The owned write-call interval includes durable claim/validation before
    # WriteFile. File consistency alone cannot attest the syscall ordering;
    # the exact native permit/facade enforces consumption before submission.
    if (canonical(claim)!=canonical(expected) or type(stamp) is not int or
            not trial['baseline']['finished_ns']<=stamp<=trial['write']['finished_ns']):
        raise ValueError('Retained correction claim differs or follows write')
    # Originals are exclusive publications: partial publication is retained,
    # never overwritten/retried into a successful-looking historical result.
    if read('reservation')[1]!=rhash or read('consumed')[1]!=chash:
        raise ValueError('Correction records changed during reconciliation')
    publication=dict(schema='rocell.wrist_correction_publication.v1',report=report,
        reservation_sha256=rhash,consumed_sha256=chash,trial_sha256=hashlib.sha256(raw).hexdigest(),
        records_consistent=True,owned_process_verified=False,physical_execution_verified=False,
        motion_authorized=False,campaign_advance_allowed=False)
    return publication


def _reconcile_final_result(raw,*,root,authority,bundle,context,originals,expected_basis):
    root=safe_root(root);prefix=context['attempt_id']+'-wrist-correction-';hashes={}
    def read(suffix,maximum=65536):
        name=prefix+suffix+'.json'
        data=read_bounded_regular_file(contained_path(root,name,label='final correction record'),maximum_bytes=maximum)
        value=decode_diagnostic_json(data,maximum=maximum)
        if canonical(value)!=data: raise ValueError('Canonical final correction record required')
        hashes[name]=hashlib.sha256(data).hexdigest()
        return value,data
    if contained_path(root,prefix+'consumed.json',label='legacy consumption').exists():
        raise ValueError('Conflicting legacy consumption with final readback')
    consumed,_=read('final-consumed');reservation,_=read('final-reservation')
    claim,claim_raw=read('final-capture-claim');capture,capture_raw=read('final-capture.original',128*1024)
    if type(consumed) is not dict or type(consumed.get('review_base64')) is not str:
        raise ValueError('Final consumption review missing')
    sealed=base64.b64decode(consumed['review_base64'],validate=True)
    report=review_wrist_correction_result(raw,authority=authority,bundle=bundle,context=context,
        originals=originals,expected_basis=expected_basis,final_evidence=dict(review_raw=sealed,
            claim_raw=claim_raw,capture_raw=capture_raw,owned_process_id=consumed.get('owner_pid')))
    verified=report['final_review'];original=report['review']
    expected=dict(schema='rocell.wrist_correction_final_consumption.v1',request_sha256=verified['request_sha256'],
        review_sha256=verified['review_sha256'],review_base64=base64.b64encode(sealed).decode(),
        claim_sha256=verified['claim_sha256'],capture_sha256=verified['capture_sha256'],
        owner_pid=verified['owner_pid'],claimed_ns=consumed.get('claimed_ns'),last_received_ns=verified['last_received_ns'],
        candidate_command=verified['candidate_command'],nominal_endpoint_rad=verified['nominal_endpoint_rad'],motion_authorized=False)
    expected_reservation=dict(schema='rocell.wrist_correction_final_reservation.v1',review_sha256=verified['review_sha256'],
        owner_pid=verified['owner_pid'],reserved_ns=reservation.get('reserved_ns') if type(reservation) is dict else None)
    trial=decode_diagnostic_json(raw,maximum=160*1024);stamp=expected['claimed_ns'];reserved=expected_reservation['reserved_ns']
    sealed_at=decode_diagnostic_json(sealed,maximum=16384)['sealed_at_ns']
    if (canonical(consumed)!=canonical(expected) or canonical(reservation)!=canonical(expected_reservation)
            or type(stamp) is not int or type(reserved) is not int
            or not trial['baseline']['finished_ns']<=claim['claimed_ns']
            or sealed_at>reserved
            or not capture['capture']['finished_ns']<=reserved<=trial['write']['started_ns']<=stamp<=trial['write']['dispatch_checked_ns']):
        raise ValueError('Final consumption records or ordering differ')
    old,_=read('reservation')
    expected_old=dict(schema='rocell.wrist_correction_reservation.v1',intent_sha256=original['intent_sha256'],
        bundle_sha256=original['bundle_sha256'],owner_pid=verified['owner_pid'],motion_authorized=False)
    if canonical(old)!=canonical(expected_old): raise ValueError('Original reservation differs from final owner/review')
    for name,expected_hash in claim['record_hashes'].items():
        data=read_bounded_regular_file(contained_path(root,name,label='final original selection'),maximum_bytes=65536)
        if hashlib.sha256(data).hexdigest()!=expected_hash: raise ValueError('Final original selection record changed')
        hashes[name]=expected_hash
    for name,expected_hash in hashes.items():
        data=read_bounded_regular_file(contained_path(root,name,label='final original recheck'),maximum_bytes=128*1024)
        if hashlib.sha256(data).hexdigest()!=expected_hash: raise ValueError('Final records changed during reconciliation')
    return dict(schema='rocell.wrist_correction_publication.v2',report=report,
        reservation_sha256=hashes[prefix+'reservation.json'],consumed_sha256=hashes[prefix+'final-consumed.json'],
        record_hashes=hashes,trial_sha256=hashlib.sha256(raw).hexdigest(),records_consistent=True,
        owned_process_verified=False,physical_execution_verified=False,motion_authorized=False,campaign_advance_allowed=False)


def publish_wrist_correction_result(raw, *, root, authority, bundle, context, originals, expected_basis):
    publication=reconcile_wrist_correction_result(raw,root=root,authority=authority,bundle=bundle,
        context=context,originals=originals,expected_basis=expected_basis)
    root=safe_root(root)
    prefix=context['attempt_id']+'-wrist-correction-'
    publish_reservation_bytes(root,prefix+'trial.original.json',raw,maximum_bytes=160*1024)
    records=(publication['record_hashes'] if publication['schema']=='rocell.wrist_correction_publication.v2' else
        {prefix+suffix+'.json':publication[key] for suffix,key in (('reservation','reservation_sha256'),('consumed','consumed_sha256'))})
    for name,expected in records.items():
        data=read_bounded_regular_file(contained_path(root,name,label='correction original'),
            maximum_bytes=128*1024 if publication['schema']=='rocell.wrist_correction_publication.v2' else 16384)
        if hashlib.sha256(data).hexdigest()!=expected:
            raise ValueError('Correction records changed during publication')
    published=canonical(publication)
    publish_reservation_bytes(root,prefix+'result.json',published,maximum_bytes=65536)
    return dict(publication,publication_sha256=hashlib.sha256(published).hexdigest())
