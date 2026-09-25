"""Host-side exact-request confirmation and review sealing; never port access."""
import hashlib
import re
import time

from .first_motion_contract import FirstMotionRequest, canonical
from .first_motion_draft import FirstMotionDraft
from .physical_onboarding_durability import publish_reservation_bytes
from rocell.safety.first_motion_review_authority import (
    FirstMotionReviewAuthority, ENGINEERING_CHECKS, OPERATOR_CHECKS, MAX_BUNDLE_BYTES,
)


def operator_originals(request, values, *, recorded_ns):
    """Create records only from explicit final-click checks for this request.

    The trusted wizard supplies request/time; browser input supplies no timestamp,
    evidence hash, command, or approval key. Records remain self-reported facts.
    """
    if type(request) is not FirstMotionRequest or type(values) is not dict:
        raise ValueError('Exact request and explicit confirmation required')
    if (set(values) != OPERATOR_CHECKS | {'operator_id', 'request_sha256'}
            or values['request_sha256'] != request.request_sha256
            or type(values['operator_id']) is not str
            or not re.fullmatch(r'[A-Za-z0-9][A-Za-z0-9_.-]{0,63}', values['operator_id'])
            or any(values[name] is not True for name in OPERATOR_CHECKS)):
        raise ValueError('All explicit operator checks must bind the exact request')
    request.require_start_time(recorded_ns)
    body = request.to_dict()
    return {name: canonical(dict(schema='rocell.first_motion_review.v1',
        scope='ONE_WRIST_RESPONSE_EXPERIMENT', check=name, actor_id=values['operator_id'],
        decision='APPROVED', evidence_kind='EXACT_REQUEST_OPERATOR_ATTESTATION',
        binding_sha256=request.request_sha256, recorded_ns=recorded_ns,
        expires_ns=body['deadline_monotonic_ns'],
        detail='Explicit operator final confirmation of '+name+' for this exact request.'))
        for name in OPERATOR_CHECKS}


def seal_confirmation(request, values, *, engineering_originals, authority,
                      root, check_current, clock_ns=time.monotonic_ns):
    """Publish one authenticated bundle; partial failure never permits replay.

    Caller owns selected engineering originals, protected authority and log root.
    This does not create a native permit, prove physical facts or extend any time.
    """
    if (type(request) is not FirstMotionRequest
            or type(authority) is not FirstMotionReviewAuthority
            or type(engineering_originals) is not dict
            or set(engineering_originals) != ENGINEERING_CHECKS
            or not callable(check_current) or not callable(clock_ns)):
        raise ValueError('Exact host-owned confirmation dependencies required')
    body = request.to_dict()
    previous = body['issued_monotonic_ns']
    def current():
        nonlocal previous
        if check_current() is not None:
            raise ValueError('Final confirmation context changed')
        now = clock_ns()
        if (type(now) is not int or now < previous
                or now+27_000_000_000 > body['deadline_monotonic_ns']):
            raise ValueError('Final confirmation lacks fixed worker preparation budget')
        previous = now
        return now
    recorded = current()
    originals = dict(engineering_originals)
    originals.update(operator_originals(request, values, recorded_ns=recorded))
    # Sealing validates every original, including expired/denied engineering
    # decisions. No reconstructed engineering timestamps replace the originals.
    raw = authority.seal(request, originals, now_ns=current())
    filename = body['attempt_id']+'-first-motion-reviews.json'
    publish_reservation_bytes(root, filename, raw, maximum_bytes=MAX_BUNDLE_BYTES)
    evidence = authority.verify(request, raw, connection_id=body['attempt_id'],
        current_references=tuple(sorted(body['references'].items())), now_ns=current())
    return dict(schema='rocell.first_motion_confirmation.v1',
        request_sha256=request.request_sha256, review_bundle_sha256=hashlib.sha256(raw).hexdigest(),
        filename=filename, checks_authenticated=len(evidence.checks),
        expires_at_ns=evidence.expires_at_ns, physical_authority=False,
        physical_facts_independently_verified=False, motion_authorized=False, replay_allowed=False)


def confirm_draft(draft, values, *, attempt_id, engineering_originals, authority,
                  root, check_current, clock_ns=time.monotonic_ns, accepted_ns=None):
    """Map an explicit selection-bound final click to one timed request.

    The host owns attempt identity and clock. The operator need not review a new
    hash under the 30-second deadline: every material field was already bound by
    the displayed selection digest. Durable click publication burns this attempt
    even when subsequent sealing fails; no automatic retry or time renewal.
    """
    if (type(draft) is not FirstMotionDraft or type(values) is not dict
            or set(values) != OPERATOR_CHECKS | {'operator_id', 'selection_sha256'}
            or values['selection_sha256'] != draft.selection_sha256
            or not callable(check_current) or not callable(clock_ns)):
        raise ValueError('Exact reviewed selection and explicit final click required')
    if check_current() is not None:
        raise ValueError('Final-click context changed')
    now = clock_ns()
    if type(now) is not int or not 0 < now < 2**63-30_000_000_000:
        raise ValueError('Current bounded host clock required')
    issued = now if accepted_ns is None else accepted_ns
    if type(issued) is not int or not 0 < issued <= now or now-issued > 3_000_000_000:
        raise ValueError('Final click is future-dated or too old; do not renew it')
    request = draft.create_request(expected_selection_sha256=values['selection_sha256'],
        attempt_id=attempt_id, issued_monotonic_ns=issued,
        deadline_monotonic_ns=issued+30_000_000_000)
    exact_values = dict(values)
    del exact_values['selection_sha256']
    exact_values['request_sha256'] = request.request_sha256
    # Validate all explicit operator values before retaining a click. The later
    # seal assigns actual recording time and rechecks review validity/budget.
    operator_originals(request, exact_values, recorded_ns=now)
    click = dict(schema='rocell.first_motion_final_click.v1',
        selection_sha256=draft.selection_sha256, request_sha256=request.request_sha256,
        request=request.to_dict(), operator_confirmation=dict(values),
        recorded_ns=now, physical_authority=False, motion_authorized=False)
    publish_reservation_bytes(root, attempt_id+'-first-motion-final-click.json',
                              canonical(click), maximum_bytes=32768)
    report = seal_confirmation(request, exact_values, engineering_originals=engineering_originals,
        authority=authority, root=root, check_current=check_current, clock_ns=clock_ns)
    return request, report
