"""Trusted wizard-parent commissioning orchestration, not a public motion API.

The caller must supply already authenticated staged reviews and the exact selected
measurement. Browser input cannot supply check callbacks or execution authority.
"""
from dataclasses import dataclass
from pathlib import Path
from threading import Event
import time

from .first_motion_contract import FirstMotionRequest
from .first_motion_worker_preparation import prepare_first_motion_worker
from .physical_onboarding_durability import safe_root
from .first_motion_draft import FirstMotionDraft
from .first_motion_confirmation import confirm_draft
from .first_motion_review_intake import load_selected_reviews
from .first_motion_measurements import load_measurement_for_request
from .first_motion_staging import stage_first_motion_originals
from rocell.providers.windows.bench_review_key import load_host_first_motion_review_authority
from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker,OwnedWorkerResult,owned_request_wire
from rocell.providers.windows.first_motion_result_publication import publish_supervised_first_motion_result


@dataclass(frozen=True)
class FirstMotionRunOutcome:
    stage: str
    owned: OwnedWorkerResult | None
    report_path: Path | None
    report: dict | None
    error_type: str | None


def run_confirmed_first_motion(workspace, draft, values, *, attempt_id,
        reference_originals, review_selections, review_root, export_root,
        session_id, measurement_operation_id, cancellation, check_current,
        clock_ns=time.monotonic_ns, accepted_ns=None):
    """Trusted host final-click pipeline; no browser-supplied execution authority.

    Receipt hashes, original bytes, roots and attempt identity must be resolved
    by the wizard host. All physical admission checks remain in the supervised
    executor. Any failure ends this attempt without automatic return or retry.
    """
    if (type(draft) is not FirstMotionDraft or type(cancellation) is not Event
            or not callable(check_current) or not callable(clock_ns)):
        raise ValueError('Exact draft and host lifecycle dependencies required')
    stage = 'REVIEW_SELECTION'
    try:
        def current():
            if cancellation.is_set():
                raise ValueError('Commissioning cancelled before dispatch')
            if check_current() is not None:
                raise ValueError('Commissioning host context changed')
        current()
        # Validate destinations before consuming the final click. Never create
        # an alternate export location silently when the assigned root fails.
        destination = safe_root(Path(export_root))
        root = safe_root(Path(review_root))
        engineering = load_selected_reviews(root=root, draft=draft,
            selections=review_selections,
            source_sha256=draft.preview()['selection']['references']['source_sha256'],
            check_current=current, clock_ns=clock_ns)
        stage = 'CONFIRMATION'
        authority = load_host_first_motion_review_authority(workspace)
        current()
        request, _confirmation = confirm_draft(draft, values, attempt_id=attempt_id,
            engineering_originals=engineering, authority=authority, root=root,
            check_current=current, clock_ns=clock_ns, accepted_ns=accepted_ns)
        stage = 'MEASUREMENT_SELECTION'
        raw, _association = load_measurement_for_request(request, root=root,
            session_id=session_id, operation_id=measurement_operation_id,
            check_current=current, clock_ns=clock_ns)
        stage = 'EVIDENCE_STAGING'
        stage_first_motion_originals(workspace, request, root=root,
            reference_originals=reference_originals, measurement_raw=raw,
            session_id=session_id, operation_id=measurement_operation_id,
            check_current=current, clock_ns=clock_ns)
        current()
        # Return the actual outcome unchanged, especially owned bytes on a
        # retention failure. Cancellation after dispatch must not discard them.
        return run_reviewed_first_motion(workspace, request, review_root=root,
            export_root=destination, session_id=session_id,
            measurement_operation_id=measurement_operation_id,
            cancellation=cancellation, check_current=current, clock_ns=clock_ns)
    except Exception as error:
        return FirstMotionRunOutcome(stage+'_FAILED', None, None, None, type(error).__name__)


def run_reviewed_first_motion(workspace,request,*,review_root,export_root,session_id,
                              measurement_operation_id,cancellation,check_current,
                              clock_ns=time.monotonic_ns):
    """Prepare once, supervise once, retain results including cancellation/failure.

    Does not fabricate measurements/reviews or renew the final-confirmation
    request. A failed publication leaves the original owned-process result in
    the outcome for diagnostic recovery; never rerun the physical attempt.
    """
    if (type(request) is not FirstMotionRequest or type(cancellation) is not Event
            or not callable(check_current) or not callable(clock_ns)):
        raise ValueError('Exact commissioning request and parent dependencies required')
    destination=safe_root(Path(export_root))
    stage,owned='PREPARATION',None
    try:
        def current():
            if cancellation.is_set(): raise ValueError('Commissioning cancelled before dispatch')
            if check_current() is not None: raise ValueError('Parent current check must return None')
            request.require_start_time(clock_ns())
        current()
        prepared=prepare_first_motion_worker(workspace,request,review_root=review_root,
            session_id=session_id,measurement_operation_id=measurement_operation_id,clock_ns=clock_ns)
        _,digest=owned_request_wire(prepared.registration,prepared.request,deadline_ns=prepared.request.expires_at_ns)
        def authorize(reg,outer,actual_digest):
            if reg!=prepared.registration or outer!=prepared.request or actual_digest!=digest:
                raise ValueError('Commissioning parent dispatch inputs changed')
            current()
        current()
        stage='SUPERVISION'
        owned=OwnedWindowsWorker(prepared.registration,authorizer=authorize).run(
            prepared.request,cancellation=cancellation,deadline_ns=prepared.request.expires_at_ns)
        stage='RETENTION'
        path,report=publish_supervised_first_motion_result(destination,
            registration=prepared.registration,request=prepared.request,result=owned)
        return FirstMotionRunOutcome('RETAINED',owned,path,report,None)
    except Exception as error:
        return FirstMotionRunOutcome(stage+'_FAILED',owned,None,None,type(error).__name__)
