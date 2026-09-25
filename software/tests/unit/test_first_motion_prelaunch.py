"""Real signed originals/launch records with synthetic context; no device I/O."""
import hashlib

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.first_motion_worker_claim import reserve_first_motion_launch
from rocell.safety.first_motion_review_authority import FirstMotionReviewAuthority
from rocell.providers.windows import first_motion_prelaunch as module
from rocell.providers.windows.first_motion_native_protocol import PAYLOAD_SCHEMA
from test_first_motion_admission import setup
from test_first_motion_measurement_binding import SESSION,OPERATION


def prepared(tmp_path,monkeypatch):
    request,_,clock,path=setup(tmp_path)
    refs=tuple(sorted(request.to_dict()['references'].items()))
    monkeypatch.setattr(module,'FirstMotionReferenceReader',lambda *a,**kw:lambda:refs)
    monkeypatch.setattr(module,'load_host_first_motion_review_authority',lambda _:FirstMotionReviewAuthority(b'a'*32))
    runtime={'worker':'synthetic-not-qualified'}
    launch=reserve_first_motion_launch(tmp_path,request,runtime_original=canonical(runtime),
        review_bundle_sha256=hashlib.sha256(path.read_bytes()).hexdigest(),now_ns=clock[0])
    payload=dict(schema=PAYLOAD_SCHEMA,root=str(tmp_path),session_id=SESSION,measurement_operation_id=OPERATION,
        first_motion_request=request.to_dict(),launch_sha256=launch,registration=runtime,
        review_authority_id='local-first-motion-review-v1')
    return payload,clock,path


def test_reserved_entry_checks_actual_originals_without_claiming(tmp_path,monkeypatch):
    payload,clock,_=prepared(tmp_path,monkeypatch)
    module.verify_reserved_first_motion_entry(payload,workspace=tmp_path,clock_ns=lambda:clock[0])
    assert not list(tmp_path.glob('*-worker-claimed.json'))
    assert not list(tmp_path.glob('*-first-motion-reserved.json'))


@pytest.mark.parametrize('fault',['reviews','measurement','operation','expiry','key','runtime'])
def test_changed_or_expired_prelaunch_evidence_refused(tmp_path,monkeypatch,fault):
    payload,clock,path=prepared(tmp_path,monkeypatch)
    if fault=='reviews': path.write_bytes(b'{}')
    if fault=='measurement':
        (tmp_path/(OPERATION+'-first-motion-measurement-original.json')).write_bytes(b'{}')
    if fault=='operation': payload['measurement_operation_id']='operation-'+'f'*32
    if fault=='expiry': clock[0]=33_000_000_000
    if fault=='key': monkeypatch.setattr(module,'load_host_first_motion_review_authority',lambda _:FirstMotionReviewAuthority(b'b'*32))
    if fault=='runtime': payload['registration']={'worker':'changed'}
    with pytest.raises(Exception):
        module.verify_reserved_first_motion_entry(payload,workspace=tmp_path,clock_ns=lambda:clock[0])
    assert not list(tmp_path.glob('*-worker-claimed.json'))


@pytest.mark.parametrize('fault', ['source', 'reviews', 'launch', 'clock'])
def test_changes_during_measurement_verification_fail_final_recheck(tmp_path, monkeypatch, fault):
    """Inject after the actual measurement load, before final reconstruction."""
    import rocell.application.first_motion_measurements as measurements
    payload, clock, review_path = prepared(tmp_path, monkeypatch)
    refs = tuple(sorted(payload['first_motion_request']['references'].items()))
    changed = False
    def references():
        if changed and fault == 'source':
            return tuple(sorted(dict(refs, source_sha256='f'*64).items()))
        return refs
    monkeypatch.setattr(module, 'FirstMotionReferenceReader', lambda *a, **kw:references)
    original_load = measurements.load_measurement_for_request
    def load(*args, **kwargs):
        nonlocal changed
        result = original_load(*args, **kwargs)
        changed = True
        if fault == 'reviews': review_path.write_bytes(b'{}')
        if fault == 'launch':
            next(tmp_path.glob('*-first_motion-worker-launch.json')).write_bytes(b'{}')
        if fault == 'clock': clock[0] -= 1
        return result
    monkeypatch.setattr(module, 'load_measurement_for_request', load)
    with pytest.raises(ValueError):
        module.verify_reserved_first_motion_entry(payload, workspace=tmp_path, clock_ns=lambda:clock[0])
    assert changed
    assert not list(tmp_path.glob('*-first_motion-worker-claimed.json'))
