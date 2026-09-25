"""Host final-click transaction; does not sign reviews or access hardware.

The caller must be the authenticated action handler with the operator's actual
explicit answers to the displayed draft. Historical setup fields or inferred
answers must not be supplied. Compile first, record second, execute the same
request later without renewing its short lifetime.
"""

from dataclasses import dataclass
import time

from .endpoint_trial_draft import EndpointTrialDraft
from .endpoint_trial_contract import EndpointTrialRequest
from .endpoint_review_intake import EndpointReviewIntake
from .physical_onboarding_durability import publish_reservation_bytes
from rocell.safety.bench_review_authority import OPERATOR_CHECKS


@dataclass(frozen=True)
class ConfirmedEndpointRequest:
    request: EndpointTrialRequest
    intake: EndpointReviewIntake
    operator_originals: tuple[bytes, ...]


def record_final_confirmation(*, draft, expected_draft_sha256, attempt_id,
                              actor_id, answers, root, deadline_ns,
                              check_current, clock_ns=time.monotonic_ns):
    """Retain one exact request and its seven explicit current operator records.

    Missing/false answers do not create a request. Once a request is published,
    a partial/expired/failed transaction remains retained and cannot be retried
    under the same attempt ID. A successful return is not a motion permit.
    """
    if (type(draft) is not EndpointTrialDraft or type(answers) is not dict
            or set(answers) != OPERATOR_CHECKS or any(value is not True for value in answers.values())
            or not callable(check_current) or not callable(clock_ns)):
        raise ValueError('Explicit complete operator answers and trusted host context required')
    import re
    if type(actor_id) is not str or re.fullmatch(r'[A-Za-z0-9_.-]{1,64}',actor_id) is None:
        raise ValueError('Identified operator required')
    if check_current() is not None:
        raise ValueError('Operator confirmation context changed')
    now = clock_ns()
    if type(deadline_ns) is not int or deadline_ns <= now:
        raise ValueError('Original action deadline required')
    request = draft.create_request(expected_draft_sha256=expected_draft_sha256,
        attempt_id=attempt_id,issued_monotonic_ns=now,
        deadline_monotonic_ns=min(deadline_ns,now+30_000_000_000))
    publish_reservation_bytes(root,attempt_id+'-endpoint-confirmed-request.json',
        request.canonical_bytes,maximum_bytes=16384)
    intake = EndpointReviewIntake(request,root=root,clock_ns=clock_ns)
    originals = []
    for check in sorted(OPERATOR_CHECKS):
        if check_current() is not None:
            raise ValueError('Operator confirmation context changed during recording')
        originals.append(intake.record(check=check,actor_id=actor_id,decision='APPROVED',
            detail='Explicit operator confirmation submitted for this displayed draft and single attempt.',
            expires_ns=request.to_dict()['deadline_monotonic_ns']))
    if check_current() is not None:
        raise ValueError('Operator confirmation context changed after recording')
    request.require_start_time(clock_ns())
    return ConfirmedEndpointRequest(request,intake,tuple(originals))
