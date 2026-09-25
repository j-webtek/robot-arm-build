"""Trusted host orchestration for one observational trial, not a browser motion API."""
from dataclasses import dataclass
from pathlib import Path
from threading import Event
import time
import hashlib

from rocell.safety.observational_review_authority import ObservationalIntent
from rocell.motion.observational_wrist_plan import ONE_DEGREE_POLICY
from .observational_worker_preparation import StagedObservationalRuntime, prepare_observational_worker
from .physical_onboarding_durability import safe_root
from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker, OwnedWorkerResult, owned_request_wire
from rocell.providers.windows.observational_result_publication import publish_supervised_observational_result


def confirm_observational_run(workspace, staged, *, session_id, usb_identity,
        direction, operator_id, checks, accepted_ns, now_ns, policy=ONE_DEGREE_POLICY):
    """Host final-click compilation. Never renew acceptance after queue delay."""
    from .first_motion_contract import canonical
    from rocell.providers.windows.owned_worker_process import owned_registration_document
    from rocell.providers.windows.bench_review_key import load_host_observational_review_authority
    if type(staged) is not StagedObservationalRuntime:
        raise ValueError('Host-staged observational runtime required')
    pins = staged.registration.package_files
    body = dict(schema='rocell.observational_intent.v1', session_id=session_id,
        attempt_id=staged.attempt_id, usb_identity=dict(usb_identity),
        references=dict(source_sha256=staged.source_sha256,
            runtime_sha256=hashlib.sha256(canonical(owned_registration_document(staged.registration))).hexdigest(),
            native_controller_review_sha256=pins[2].sha256, protocol_review_sha256=pins[3].sha256),
        issued_ns=accepted_ns, deadline_ns=accepted_ns+30_000_000_000, direction=direction,
        policy=policy)
    request = ObservationalIntent(canonical(body))
    request.require_start_time(now_ns)
    if now_ns+27_000_000_000 > body['deadline_ns']:
        raise ValueError('Final click is too old for the supervised trial budget')
    authority = load_host_observational_review_authority(workspace)
    signed = authority.seal(body, dict(operator_id=operator_id, recorded_ns=accepted_ns,
        checks=dict(checks)), now_ns=now_ns)
    return request, signed


@dataclass(frozen=True)
class ObservationalRunOutcome:
    stage: str
    owned: OwnedWorkerResult | None
    report_path: Path | None
    report: dict | None
    error_type: str | None


def run_reviewed_observational(workspace, staged, request, *, review_original,
        export_root, cancellation, check_current, clock_ns=time.monotonic_ns):
    """Prepare once, supervise once, retain even on cancellation or failed motion.

    The wizard host resolves originals, destination and current session state.
    Callbacks and authority records must never be accepted from browser input.
    A retention failure returns the actual owned receipt for recovery, not replay.
    """
    if (type(staged) is not StagedObservationalRuntime or type(request) is not ObservationalIntent
            or type(cancellation) is not Event or not callable(check_current) or not callable(clock_ns)):
        raise ValueError('Exact observational host inputs required')
    stage, owned = 'PREPARATION', None
    try:
        destination = safe_root(Path(export_root))

        def current():
            if cancellation.is_set():
                raise ValueError('Observational trial cancelled before dispatch')
            if check_current() is not None:
                raise ValueError('Observational host context changed')
            request.require_start_time(clock_ns())

        current()
        prepared = prepare_observational_worker(workspace, staged, request,
            review_original=review_original, clock_ns=clock_ns)
        _, digest = owned_request_wire(prepared.registration, prepared.request,
            deadline_ns=prepared.request.expires_at_ns)

        def authorize(registration, outer, actual_digest):
            if (registration != prepared.registration or outer != prepared.request or actual_digest != digest):
                raise ValueError('Observational dispatch inputs changed')
            current()

        current()
        stage = 'SUPERVISION'
        owned = OwnedWindowsWorker(prepared.registration, authorizer=authorize, _clock=clock_ns).run(
            prepared.request, cancellation=cancellation, deadline_ns=prepared.request.expires_at_ns)
        stage = 'RETENTION'
        # No cancellation/current-time gate here: preserve attempted-run evidence.
        path, report = publish_supervised_observational_result(destination,
            registration=prepared.registration, request=prepared.request, result=owned)
        return ObservationalRunOutcome('RETAINED', owned, path, report, None)
    except Exception as error:
        return ObservationalRunOutcome(stage+'_FAILED', owned, None, None, type(error).__name__)
