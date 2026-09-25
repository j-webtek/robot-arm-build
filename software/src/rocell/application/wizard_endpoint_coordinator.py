"""One reviewed endpoint attempt through parent supervision and log retention.

Called by a trusted wizard parent service, not the generic diagnostic subprocess.
It accepts an already-reviewed exact request, never free-form motion commands.
"""

from dataclasses import dataclass
from pathlib import Path
from threading import Event
import time

from .endpoint_trial_contract import EndpointTrialRequest
from .endpoint_trial_draft import EndpointTrialDraft
from .endpoint_reference_reader import EndpointReferenceReader, ORIGINAL_REFERENCES, MAX_ORIGINAL_BYTES
from .bench_review_issuance import issue_bench_reviews
from .endpoint_worker_preparation import prepare_endpoint_worker, MINIMUM_PREPARATION_REMAINING_NS
from .physical_onboarding_durability import safe_root, publish_reservation_bytes
from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker,OwnedWorkerResult,owned_request_wire
from rocell.providers.windows.endpoint_result_publication import publish_supervised_endpoint_result


@dataclass(frozen=True)
class EndpointRunOutcome:
    stage: str
    owned: OwnedWorkerResult | None
    report_path: Path | None
    report: dict | None
    error_type: str | None


@dataclass(frozen=True)
class EndpointWizardBinding:
    """Trusted host attachment, never deserialized from browser input.

    Readers supply actual request-bound decisions, including current operator
    evidence; checking the UI acknowledgement does not replace these readers.
    """
    draft: EndpointTrialDraft
    reference_originals: tuple
    operator_reader: object
    engineering_reader: object
    context_factory: object

    def __post_init__(self):
        if (type(self.draft) is not EndpointTrialDraft
                or type(self.reference_originals) is not tuple
                or any(type(pair) is not tuple or len(pair)!=2
                       or type(pair[0]) is not str or type(pair[1]) is not bytes
                       for pair in self.reference_originals)
                or len(self.reference_originals)!=len(ORIGINAL_REFERENCES)
                or set(dict(self.reference_originals))!=ORIGINAL_REFERENCES
                or not all(callable(r) for r in
                           (self.operator_reader,self.engineering_reader,self.context_factory))):
            raise ValueError('Immutable endpoint selection and trusted readers required')


def run_endpoint_draft(workspace,draft,*,expected_draft_sha256,attempt_id,
                       reference_originals,review_root,export_root,session_id,
                       connection_id,operator_reader,engineering_reader,
                       context_factory,cancellation,check_current,
                       clock_ns=time.monotonic_ns,deadline_ns=None,prepared_request=None):
    """Bind a reviewed selection to fresh reviews and the existing one-shot runner.

    All readers, originals and roots are trusted parent dependencies, not browser
    request fields. Review readers must return actual original decisions for the
    newly compiled request; this function never makes decisions on their behalf.
    A retained request reserves the attempt before any reviews are issued. Failed
    attempts and partial evidence remain on disk and cannot be silently retried.
    """
    import hashlib
    from .wizard_diagnostic_coordinator import decode_diagnostic_json

    stage = 'DRAFT_VALIDATION'
    try:
        if (type(draft) is not EndpointTrialDraft or type(cancellation) is not Event
                or not all(callable(reader) for reader in
                           (operator_reader,engineering_reader,context_factory,check_current))):
            raise ValueError('Typed draft and trusted parent dependencies required')
        if cancellation.is_set() or check_current() is not None:
            raise ValueError('Parent current check refused')
        now = clock_ns()
        if deadline_ns is not None and (type(deadline_ns) is not int or deadline_ns<=now):
            raise ValueError('Original parent deadline expired or invalid')
        if prepared_request is None:
            request = draft.create_request(expected_draft_sha256=expected_draft_sha256,
                attempt_id=attempt_id,issued_monotonic_ns=now,
                deadline_monotonic_ns=min(now+30_000_000_000,deadline_ns)
                    if deadline_ns is not None else now+30_000_000_000)
        else:
            # The authenticated final-click handler may already have compiled
            # the request before recording actual operator answers. Preserve
            # those exact bytes/times rather than generating a new request here.
            request = prepared_request
            if (type(request) is not EndpointTrialRequest
                    or expected_draft_sha256 != draft.draft_sha256
                    or EndpointTrialDraft.from_request(request).canonical_bytes != draft.canonical_bytes
                    or request.to_dict()['attempt_id'] != attempt_id
                    or (deadline_ns is not None and request.to_dict()['deadline_monotonic_ns'] > deadline_ns)):
                raise ValueError('Prepared confirmation request changed')
            request.require_start_time(now)
        # Validate the whole set before publishing anything; retain original
        # bytes, not normalized substitutes or caller-asserted digest receipts.
        if type(reference_originals) is not dict or set(reference_originals)!=ORIGINAL_REFERENCES:
            raise ValueError('Complete reference originals required')
        originals = dict(reference_originals)
        expected = request.to_dict()['references']
        for name,raw in originals.items():
            if type(raw) is not bytes:
                raise ValueError('Immutable original bytes required')
            value = decode_diagnostic_json(raw,maximum=MAX_ORIGINAL_BYTES)
            if (type(value) is not dict or not value
                    or hashlib.sha256(raw).hexdigest()!=expected[name]):
                raise ValueError('Reference original mismatch')
        root = safe_root(Path(review_root))
        stage = 'DRAFT_RESERVATION'
        publish_reservation_bytes(root,attempt_id+'-endpoint-draft-request.json',
                                  request.canonical_bytes,maximum_bytes=16384)
        stage = 'REFERENCE_STAGING'
        for name,raw in sorted(originals.items()):
            publish_reservation_bytes(root,attempt_id+'-'+name+'.original.json',raw,
                                      maximum_bytes=MAX_ORIGINAL_BYTES)
        EndpointReferenceReader(request,workspace=workspace,reference_root=root)()
        if cancellation.is_set() or check_current() is not None:
            raise ValueError('Parent current check refused after staging')
        # Reviews cannot consume the native worker's fixed run/cleanup reserve.
        # In particular, do not make an expired interactive review usable by
        # rematerializing the draft or renewing the request deadline here.
        def review_budget():
            now = clock_ns()
            request.require_start_time(now)
            if now+MINIMUM_PREPARATION_REMAINING_NS>request.to_dict()['deadline_monotonic_ns']:
                raise ValueError('Insufficient remaining review-to-worker budget')
        stage = 'REVIEW_BUDGET'
        review_budget()
        stage = 'REVIEW_ISSUANCE'
        issue_bench_reviews(workspace,request,review_root=root,connection_id=connection_id,
            operator_reader=operator_reader,engineering_reader=engineering_reader,
            context_reader=context_factory(request),clock_ns=clock_ns)
        stage = 'REVIEW_BUDGET'
        review_budget()
        return run_reviewed_endpoint(workspace,request,review_root=root,
            export_root=export_root,session_id=session_id,cancellation=cancellation,
            check_current=check_current,clock_ns=clock_ns)
    except Exception as error:
        return EndpointRunOutcome(stage+'_FAILED',None,None,None,type(error).__name__)


def run_reviewed_endpoint(workspace,request,*,review_root,export_root,session_id,
                          cancellation,check_current,clock_ns=time.monotonic_ns):
    """Prepare once, run once, retain both positive and negative observations.

    check_current is the parent service's current session/operator authorization
    check. It must raise on refusal and return None on success. No retries or
    power/pose changes occur on failure or cancellation. Publication failure is
    explicit; the returned owned result still retains original IPC bytes.
    """
    if type(request) is not EndpointTrialRequest or type(cancellation) is not Event or not callable(check_current):
        raise ValueError('Exact request, cancellation and parent current check required')
    destination = safe_root(Path(export_root))
    stage,owned = 'PREPARATION',None
    try:
        def current():
            if cancellation.is_set(): raise ValueError('Endpoint cancelled before dispatch')
            if check_current() is not None: raise ValueError('Parent current check must return None')
            request.require_start_time(clock_ns())
        current()
        prepared = prepare_endpoint_worker(workspace,request,review_root=review_root,
                                           session_id=session_id,clock_ns=clock_ns)
        _,digest = owned_request_wire(prepared.registration,prepared.request,
                                      deadline_ns=prepared.request.expires_at_ns)
        def authorize(reg,outer,actual_digest):
            if reg!=prepared.registration or outer!=prepared.request or actual_digest!=digest:
                raise ValueError('Endpoint parent dispatch inputs changed')
            current()
        current()
        stage = 'SUPERVISION'
        owned = OwnedWindowsWorker(prepared.registration,authorizer=authorize).run(
            prepared.request,cancellation=cancellation,deadline_ns=prepared.request.expires_at_ns)
        # Cancellation after dispatch never skips cleanup evidence or raw logs.
        stage = 'RETENTION'
        path,report = publish_supervised_endpoint_result(destination,
            registration=prepared.registration,request=prepared.request,result=owned)
        return EndpointRunOutcome('RETAINED',owned,path,report,None)
    except Exception as error:
        return EndpointRunOutcome(stage+'_FAILED',owned,None,None,type(error).__name__)
