"""Disjoint host review signature for an exact correction preview, not IO admission.

Only the trusted coordinator holds the key. No route accepts uploaded keys or
unsigned approvals. Native one-use consumption/worker ownership remains separate.
"""
import hashlib
import hmac

from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.application.wrist_correction_preview import preview_wrist_correction
from .observational_review_authority import validate_observational_context, _review

DOMAIN = b'rocell.wrist-correction-review.v1\x00'
SCHEMA = 'rocell.wrist_correction_review_bundle.v1'
CONTEXT_FIELDS = {'session_id','attempt_id','usb_identity','references','issued_ns','deadline_ns'}
PLAN_DOMAIN = b'rocell.wrist-correction-plan-review.v1\x00'
FINAL_DOMAIN = b'rocell.wrist-correction-final-readback.v1\x00'


def _plan(context, originals, now_ns, basis):
    from rocell.application.wrist_correction_proposal import propose_wrist_correction
    if type(context) is not dict or set(context)!=CONTEXT_FIELDS:
        raise ValueError('Exact correction plan context required')
    validate_observational_context(context,now_ns)
    if now_ns+11_000_000_000>context['deadline_ns']:
        raise ValueError('Insufficient correction plan time budget')
    proposal=propose_wrist_correction(originals,expected_basis=basis)
    if proposal['status']!='OFFLINE_EXPERIMENT_CANDIDATE' or context['usb_identity']!=proposal['supplied_usb_identities'][0]:
        raise ValueError('Correction plan held or wrong USB unit')
    return dict(context=context,proposal=proposal,basis=basis)


def _intent(context, originals, samples, now_ns, basis):
    if type(context) is not dict or set(context) != CONTEXT_FIELDS:
        raise ValueError('Exact correction host context required')
    validate_observational_context(context, now_ns)
    if now_ns+11_000_000_000 > context['deadline_ns']:
        raise ValueError('Insufficient correction review start/cleanup budget')
    preview = preview_wrist_correction(originals, expected_basis=basis, samples=samples,
        now_ns=now_ns, usb_identity=context['usb_identity'])
    return dict(schema='rocell.wrist_correction_review_intent.v1',
                context=context, preview=preview, basis=basis)


class WristCorrectionReviewAuthority:
    def __init__(self, key):
        if type(key) is not bytes or len(key) != 32:
            raise ValueError('Derived protected 32-byte key required')
        self._key = key

    def seal_final_readback(self, **evidence):
        """Authenticate distinct new readback, without renewing original review."""
        from rocell.application.wrist_correction_final_review import final_readback_intent
        intent=final_readback_intent(self,**evidence)
        body=dict(schema='rocell.wrist_correction_final_review.v1',intent=intent,sealed_at_ns=evidence['now_ns'])
        body['mac']=hmac.new(self._key,FINAL_DOMAIN+canonical(body),hashlib.sha256).hexdigest()
        return canonical(body)

    def verify_final_readback(self, raw, **evidence):
        from rocell.application.wrist_correction_final_review import final_readback_intent
        body=decode_diagnostic_json(raw,maximum=16384)
        if (type(raw) is not bytes or type(body) is not dict or canonical(body)!=raw
                or set(body)!={'schema','intent','sealed_at_ns','mac'}
                or body['schema']!='rocell.wrist_correction_final_review.v1'):
            raise ValueError('Exact final-readback review required')
        mac=body.pop('mac')
        expected=hmac.new(self._key,FINAL_DOMAIN+canonical(body),hashlib.sha256).hexdigest()
        if type(mac) is not str or not hmac.compare_digest(mac,expected):
            raise ValueError('Final-readback authentication failed')
        if (type(body['sealed_at_ns']) is not int
                or not evidence['context']['issued_ns']<=body['sealed_at_ns']<=evidence['now_ns']):
            raise ValueError('Final-readback review time invalid')
        intent=final_readback_intent(self,**evidence)
        if canonical(intent)!=canonical(body['intent']):
            raise ValueError('Final-readback evidence association changed')
        return dict(intent,review_sha256=hashlib.sha256(raw).hexdigest(),verified_at_ns=evidence['now_ns'],
            motion_authorized=False,one_use_dispatch_implemented=False)

    def seal_plan(self, context, review, *, originals, now_ns, expected_basis):
        """Review fixed targets before acquisition; not permission to open USB."""
        plan=_plan(context,originals,now_ns,expected_basis)
        _review(review,context,now_ns)
        body=dict(schema='rocell.wrist_correction_plan_bundle.v1',plan=plan,review=review)
        body['mac']=hmac.new(self._key,PLAN_DOMAIN+canonical(body),hashlib.sha256).hexdigest()
        return canonical(body)

    def bind_review_from_capture(self, plan_raw, *, context, originals, raw, windows,
                                 started_ns, finished_ns, now_ns, expected_basis):
        """Condition the original review on a new raw baseline, without renewal.

        Returns (exact-baseline review bytes, normalized samples, framing).
        No acquisition is performed here. The native worker must independently
        establish ownership, reserve opening and consume dispatch once.
        """
        from rocell.arm.first_motion_analysis import _window, JOINTS
        self.verify_plan(plan_raw,context=context,originals=originals,now_ns=now_ns,expected_basis=expected_basis)
        body=decode_diagnostic_json(plan_raw,maximum=65536)
        if (type(raw) is not bytes or len(raw)>16384 or
                any(type(t) is not int for t in (started_ns,finished_ns,now_ns)) or
                not context['issued_ns']<=started_ns<finished_ns<=now_ns or
                started_ns<body['review']['recorded_ns'] or
                finished_ns-started_ns>1_000_000_000 or now_ns-finished_ns>100_000_000):
            raise ValueError('New bounded post-review baseline required')
        rows,issues,framing=_window(raw,windows,started_ns,finished_ns)
        if issues:
            raise ValueError('Correction baseline invalid: '+', '.join(sorted(issues)))
        samples=[dict(host_received_ns=end,joints_rad=dict(zip(JOINTS,joints))) for begin,end,joints in rows]
        sealed=self.seal(context,body['review'],originals=originals,samples=samples,
                         now_ns=now_ns,expected_basis=expected_basis)
        return sealed,samples,framing

    def verify_plan(self, raw, *, context, originals, now_ns, expected_basis):
        """Read-only plan authentication for a current-context boundary check."""
        if type(raw) is not bytes:
            raise ValueError('Immutable reviewed plan required')
        body=decode_diagnostic_json(raw,maximum=65536)
        if (type(body) is not dict or set(body)!={'schema','plan','review','mac'} or
                body['schema']!='rocell.wrist_correction_plan_bundle.v1' or canonical(body)!=raw):
            raise ValueError('Exact canonical correction plan required')
        mac=body.pop('mac')
        if type(mac) is not str or not hmac.compare_digest(mac,hmac.new(self._key,PLAN_DOMAIN+canonical(body),hashlib.sha256).hexdigest()):
            raise ValueError('Correction plan authentication failed')
        if canonical(body['plan'])!=canonical(_plan(context,originals,now_ns,expected_basis)):
            raise ValueError('Current correction plan context changed')
        _review(body['review'],context,now_ns)
        return dict(plan_sha256=hashlib.sha256(raw).hexdigest(),verified_at_ns=now_ns,
                    deadline_ns=context['deadline_ns'],motion_authorized=False)

    def seal(self, context, review, *, originals, samples, now_ns, expected_basis):
        intent = _intent(context, originals, samples, now_ns, expected_basis)
        _review(review, context, now_ns)
        body = dict(schema=SCHEMA, intent=intent, review=review)
        body['mac'] = hmac.new(self._key, DOMAIN+canonical(body), hashlib.sha256).hexdigest()
        return canonical(body)

    def verify(self, raw, *, expected_context, originals, samples, now_ns, expected_basis):
        if type(raw) is not bytes:
            raise ValueError('Immutable original correction review required')
        body = decode_diagnostic_json(raw, maximum=16384)
        if (type(body) is not dict or set(body) != {'schema','intent','review','mac'}
                or body['schema'] != SCHEMA or canonical(body) != raw):
            raise ValueError('Exact canonical correction bundle required')
        mac = body.pop('mac')
        expected_mac = hmac.new(self._key, DOMAIN+canonical(body), hashlib.sha256).hexdigest()
        if type(mac) is not str or not hmac.compare_digest(mac, expected_mac):
            raise ValueError('Correction review authentication failed')
        intent = _intent(expected_context, originals, samples, now_ns, expected_basis)
        if canonical(body['intent']) != canonical(intent):
            raise ValueError('Correction evidence, baseline, command or context changed')
        _review(body['review'], expected_context, now_ns)
        return dict(schema='rocell.wrist_correction_review_verification.v1',
            intent_sha256=hashlib.sha256(canonical(intent)).hexdigest(),
            bundle_sha256=hashlib.sha256(raw).hexdigest(), verified_at_ns=now_ns,
            deadline_ns=expected_context['deadline_ns'],
            operator_id=body['review']['operator_id'],
            evidence_kind='HOST_AUTHENTICATED_OPERATOR_REPORT',
            nominal_endpoint_rad=intent['preview']['nominal_endpoint_rad'],
            candidate_command=intent['preview']['candidate_command'],
            physical_truth_verified=False, motion_authorized=False,
            native_admission_implemented=False, one_use_consumption_implemented=False)
