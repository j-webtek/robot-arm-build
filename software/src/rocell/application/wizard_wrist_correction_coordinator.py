"""Trusted host correction review/run flow, not a browser command endpoint."""
from dataclasses import dataclass
from pathlib import Path
from threading import Event
import time
from .first_motion_contract import canonical
from .physical_onboarding_durability import safe_root
from .wrist_correction_worker_preparation import StagedCorrectionRuntime,prepare_correction_worker
from .wrist_correction_export import export_correction_run
from rocell.providers.windows.wrist_correction_current_context import WristCorrectionContextRequest
from rocell.providers.windows.wrist_correction_native_protocol import digest,require
from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker,OwnedWorkerResult,owned_registration_document,owned_request_wire


def confirm_correction_run(workspace,staged,*,session_id,usb_identity,originals,
        operator_id,checks,accepted_ns,now_ns):
    """Seal the host-selected experiment at the original acceptance timestamp."""
    from rocell.providers.windows.bench_review_key import load_host_wrist_correction_review_authority
    require(type(staged) is StagedCorrectionRuntime,'Host-staged correction runtime required')
    pins=staged.registration.package_files
    context=dict(session_id=session_id,attempt_id=staged.attempt_id,usb_identity=dict(usb_identity),
        references=dict(source_sha256=staged.source_sha256,
            runtime_sha256=digest(canonical(owned_registration_document(staged.registration))),
            native_controller_review_sha256=pins[2].sha256,protocol_review_sha256=pins[3].sha256),
        issued_ns=accepted_ns,deadline_ns=accepted_ns+30_000_000_000)
    request=WristCorrectionContextRequest(canonical(context));request.require_start_time(now_ns)
    require(now_ns+27_000_000_000<=context['deadline_ns'],'Correction acceptance too old for supervised budget')
    authority=load_host_wrist_correction_review_authority(workspace)
    signed=authority.seal_plan(context,dict(operator_id=operator_id,recorded_ns=accepted_ns,checks=dict(checks)),
        originals=originals,now_ns=now_ns,expected_basis='RETAINED_PHYSICAL_CAPTURE')
    return request,signed


@dataclass(frozen=True)
class CorrectionRunOutcome:
    stage: str
    owned: OwnedWorkerResult | None
    report_path: Path | None
    report: dict | None
    error_type: str | None


def run_reviewed_correction(workspace,staged,request,*,plan_original,originals,export_root,
        cancellation,check_current,clock_ns=time.monotonic_ns):
    require(type(staged) is StagedCorrectionRuntime and type(request) is WristCorrectionContextRequest
        and type(cancellation) is Event and callable(check_current) and callable(clock_ns),'Exact correction host inputs required')
    stage,owned='PREPARATION',None
    try:
        destination=safe_root(Path(export_root))
        def current():
            require(not cancellation.is_set() and check_current() is None,'Correction cancelled or host context changed')
            request.require_start_time(clock_ns())
        current()
        prepared=prepare_correction_worker(workspace,staged,request,plan_original=plan_original,originals=originals,clock_ns=clock_ns)
        wire,expected=owned_request_wire(prepared.registration,prepared.request,deadline_ns=prepared.request.expires_at_ns)
        def authorize(registration,outer,actual):
            require(registration==prepared.registration and outer==prepared.request and actual==expected,'Correction dispatch inputs changed')
            current()
        current();stage='SUPERVISION'
        owned=OwnedWindowsWorker(prepared.registration,authorizer=authorize,_clock=clock_ns).run(
            prepared.request,cancellation=cancellation,deadline_ns=prepared.request.expires_at_ns)
        stage='EXPORT'
        # Cancellation does not erase evidence after an attempted run.
        path,report=export_correction_run(wire,owned,export_root=destination)
        return CorrectionRunOutcome('EXPORTED',owned,path,report,None)
    except Exception as error:
        return CorrectionRunOutcome(stage+'_FAILED',owned,None,None,type(error).__name__)
