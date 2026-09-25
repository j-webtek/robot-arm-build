"""Offline correction result reconstruction from bounded original wire evidence.

Authenticates the exact reviewed command, but cannot attest physical provenance
or native process ownership. No caller summary supplies the endpoint verdict.
"""
import base64
import hashlib

from rocell.arm.first_motion_analysis import _window, JOINTS
from rocell.arm.protocol import encode_line
from rocell.arm.wrist_endpoint_verification import verify_reported_wrist
from rocell.safety.wrist_correction_review_authority import WristCorrectionReviewAuthority
from .first_motion_contract import canonical
from .wizard_diagnostic_coordinator import decode_diagnostic_json


def _capture(value, *, maximum):
    if type(value) is not dict or set(value) != {'raw_base64','read_windows','started_ns','finished_ns'}:
        raise ValueError('Exact raw correction capture required')
    encoded = value['raw_base64']
    if type(encoded) is not str or len(encoded) > 4*((maximum+2)//3):
        raise ValueError('Bounded capture encoding required')
    raw = base64.b64decode(encoded,validate=True)
    begin,end=value['started_ns'],value['finished_ns']
    if len(raw)>maximum or any(type(t) is not int for t in (begin,end)) or not 0<begin<end<2**63:
        raise ValueError('Bounded capture bytes/times required')
    rows,issues,framing=_window(raw,value['read_windows'],begin,end)
    return rows,issues,framing


def review_wrist_correction_result(raw, *, authority, bundle, context, originals, expected_basis,final_evidence=None):
    if type(authority) is not WristCorrectionReviewAuthority or type(raw) is not bytes:
        raise ValueError('Exact correction authority and immutable trial required')
    trial=decode_diagnostic_json(raw,maximum=160*1024)
    final_mode=type(trial) is dict and trial.get('schema')=='rocell.wrist_correction_trial.v2'
    fields={'schema','basis','baseline','post','write','cleanup'}
    if final_mode: fields.add('final_readback')
    if (type(trial) is not dict or set(trial)!=fields
            or canonical(trial)!=raw or trial['schema'] not in ('rocell.wrist_correction_trial.v1','rocell.wrist_correction_trial.v2')
            or expected_basis not in ('SYNTHETIC_WIRE_REHEARSAL','RETAINED_PHYSICAL_CAPTURE')
            or trial['basis']!=expected_basis):
        raise ValueError('Exact correction trial and evidence basis required')
    if (final_mode and (type(final_evidence) is not dict or set(final_evidence)!=
            {'review_raw','claim_raw','capture_raw','owned_process_id'})) or (not final_mode and final_evidence is not None):
        raise ValueError('Exact final-readback evidence required only for v2 trial')
    before,bi,bf=_capture(trial['baseline'],maximum=16384)
    after,pi,pf=_capture(trial['post'],maximum=65536)
    write,cleanup=trial['write'],trial['cleanup']
    write_fields={'payload_base64','started_ns','finished_ns','confirmed_bytes','completion_uncertain'}
    if final_mode: write_fields.add('dispatch_checked_ns')
    if type(write) is not dict or set(write)!=write_fields:
        raise ValueError('Exact command write accounting required')
    if type(cleanup) is not dict or set(cleanup)!={'finished_ns','all_handles_closed','pending_io_count'}:
        raise ValueError('Exact cleanup accounting required')
    b0,b1=trial['baseline']['started_ns'],trial['baseline']['finished_ns']
    p0,p1=trial['post']['started_ns'],trial['post']['finished_ns']
    w0,w1,c1=write['started_ns'],write['finished_ns'],cleanup['finished_ns']
    if (any(type(t) is not int for t in (w0,w1,c1)) or
            not context['issued_ns']<=b0<b1<=w0<=w1<=p0<p1<=c1<context['deadline_ns'] or
            b1-b0>1_000_000_000 or (not final_mode and w0-b1>100_000_000) or w1-w0>1_000_000_000 or
            p0-w1>100_000_000 or p1-p0!=5_000_000_000):
        raise ValueError('Correction baseline/write/post/cleanup ordering or duration invalid')
    if bi:
        raise ValueError('Correction baseline invalid: '+', '.join(sorted(bi)))
    samples=[dict(host_received_ns=finish,joints_rad=dict(zip(JOINTS,joints))) for begin,finish,joints in before]
    verified=authority.verify(bundle,expected_context=context,originals=originals,
        samples=samples,now_ns=w0,expected_basis=expected_basis)
    final_review=None
    if final_mode:
        checked=write['dispatch_checked_ns']
        if type(checked) is not int or not w0<=checked<=w1:
            raise ValueError('Final dispatch check outside owned write interval')
        evidence=final_evidence
        final_review=authority.verify_final_readback(evidence['review_raw'],original_bundle=bundle,
            context=context,originals=originals,samples=samples,basis=expected_basis,
            claim_raw=evidence['claim_raw'],capture_raw=evidence['capture_raw'],
            owned_process_id=evidence['owned_process_id'],now_ns=checked)
        expected=dict(review_sha256=hashlib.sha256(evidence['review_raw']).hexdigest(),
            claim_sha256=hashlib.sha256(evidence['claim_raw']).hexdigest(),
            capture_sha256=hashlib.sha256(evidence['capture_raw']).hexdigest(),owner_pid=evidence['owned_process_id'])
        if trial['final_readback']!=expected or type(trial['final_readback']) is not dict:
            raise ValueError('Trial final-readback reference differs')
        retained=decode_diagnostic_json(evidence['capture_raw'],maximum=128*1024)['capture']
        if not b1<=retained['started_ns']<retained['finished_ns']<=w0:
            raise ValueError('Final capture does not precede write')
    payload=encode_line(verified['candidate_command'])
    if (write['payload_base64']!=base64.b64encode(payload).decode('ascii') or
            type(write['confirmed_bytes']) is not int or not 0<=write['confirmed_bytes']<=len(payload) or
            type(write['completion_uncertain']) is not bool or
            type(cleanup['all_handles_closed']) is not bool or
            type(cleanup['pending_io_count']) is not int or cleanup['pending_io_count']<0):
        raise ValueError('Correction command or transport accounting changed')
    clean=(write['confirmed_bytes']==len(payload) and not write['completion_uncertain']
           and cleanup['all_handles_closed'] and cleanup['pending_io_count']==0)
    endpoint=verify_reported_wrist(after,start=before[-1][2],target=verified['nominal_endpoint_rad'],
                                   capture_issues=pi,transport_clean=clean)
    report=dict(schema='rocell.wrist_correction_result_review.v1',basis=expected_basis,
        trial_sha256=hashlib.sha256(raw).hexdigest(),review=verified,endpoint=endpoint,
        baseline_framing=bf,post_framing=pf,post_samples=len(after),
        capture_issues=sorted(pi),transport_clean=clean,
        owned_process_verified=False,consumption_verified=False,
        physical_accuracy_verified=False,motion_authorized=False,campaign_advance_allowed=False)
    if final_mode:
        report['schema']='rocell.wrist_correction_result_review.v2'
        report['final_review']=final_review
    return report
