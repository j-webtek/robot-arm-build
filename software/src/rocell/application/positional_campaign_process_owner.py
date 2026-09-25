"""One parent operation joins campaign supervision, retention and verification.

No browser-selected transport, subprocess factory, command or authorizer crosses
this boundary. Native launch remains subject to the supervisor's release gates.
An unsuccessful operation is retained, never automatically retried.
"""
from threading import Event
import time

from .first_motion_contract import canonical
from .physical_onboarding_durability import safe_root, publish_reservation_bytes
from .positional_campaign_native_retention import publish_campaign_process_result
from .positional_campaign_native_export import verify_native_retained_export
from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker
from rocell.providers.windows.positional_campaign_process_codec import prepare_owned_request
from rocell.providers.windows.positional_campaign_native_protocol import validate_payload, decode_request
from rocell.providers.windows.positional_campaign_native_registration import validate_registration
from rocell.providers.windows.positional_campaign_native_package import CHILD
from rocell.providers.windows.positional_campaign_prelaunch import verify_reserved_campaign_entry


def run_campaign_process(registration, payload, *, cancellation, clock_ns=time.monotonic_ns):
    if type(cancellation) is not Event or not callable(clock_ns):
        raise ValueError('Owned campaign cancellation and clock required')
    request, raw = prepare_owned_request(registration, payload)
    validate_registration(registration, raw)
    intent = validate_payload(payload)
    root = safe_root(payload['root'])
    started = clock_ns()
    intent.require_start_time(started)
    # Durable parent admission prevents a repeated Run from launching another
    # worker even when the first never created a child or failed during export.
    publish_reservation_bytes(root, request.attempt_id+'-parent-attempt.json', canonical(dict(
        schema='rocell.positional_parent_attempt.v1', request_sha256=decode_request(raw)['request_sha256'],
        started_ns=started, replay_allowed=False)), maximum_bytes=8192)
    def authorize(observed_registration, observed_request, digest):
        if (observed_registration != registration or observed_request != request
                or digest != decode_request(raw)['request_sha256']):
            raise ValueError('Campaign supervisor handoff changed')
        validate_registration(registration, raw)
        verify_reserved_campaign_entry(CHILD.parents[5], raw,
            cancellation=cancellation, clock_ns=clock_ns)
    worker = OwnedWindowsWorker(registration, authorizer=authorize, _clock=clock_ns)
    receipt = worker.run(request, cancellation=cancellation, deadline_ns=request.expires_at_ns)
    path, retained = publish_campaign_process_result(root, intent, request_original=raw, receipt=receipt)
    checked = verify_native_retained_export(root, path.name)
    return dict(schema='rocell.positional_campaign_operation.v1',
        status='ENDPOINTS_REPORTED_COMPLETE' if retained['endpoint_reported_complete'] else 'HELD',
        process_status=receipt.status, primary_error=receipt.primary_error,
        cleanup_errors=list(receipt.cleanup_errors), process_created=receipt.process_created,
        report_file=path.name, report_sha256=checked['report_sha256'],
        export_verified=checked['valid'], endpoint_diagnostics=checked['endpoint_diagnostics'],
        configuration_references=checked['configuration_references'],
        physical_accuracy_verified=False, physical_stop_verified=False, replay_allowed=False)
