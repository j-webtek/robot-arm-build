"""One-use final capture on an existing correction connection; never dispatch.

This path leaves the permit held even on success. A separate authenticated
dispatch integration must consume the retained evidence; no legacy baseline-age
check is refreshed and no selected command can be sent through this helper.
"""
import os
from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes,contained_path,read_bounded_regular_file
from .wrist_correction_preview import preview_wrist_correction
from .wrist_correction_final_capture import capture_final_readback,validate_final_capture
from rocell.providers.windows.wrist_correction_native_protocol import digest,require


def retain_owned_final_capture(connection,permit,*,idle_wait=None):
    from rocell.providers.windows.wrist_correction_serial_connection import WristCorrectionSerialConnection
    from rocell.safety.wrist_correction_admission import WristCorrectionPermit
    require(type(connection) is WristCorrectionSerialConnection and type(permit) is WristCorrectionPermit,
        'Exact existing correction connection and permit required')
    binding=permit._binding;request=permit._request
    require(connection._request is request and connection._api.matches_authorization(request,permit)
        and connection._phase=='OPEN' and not connection._write_attempted,
        'Final capture requires the same open, unwritten correction connection')
    with binding._lock:
        require(binding._state=='BOUND' and os.getpid()==binding._pid,'Unconsumed same-process selection required')
        # Hold before any durable operation or read. Failure cannot fall back to
        # dispatch using the old baseline, even if retention itself fails.
        binding._state='HELD'
        for name,expected in binding._records:
            raw=read_bounded_regular_file(contained_path(binding._root,name,label='final capture selection'),maximum_bytes=65536)
            require(digest(raw)==expected,'Correction selection changed before final capture')
        samples=binding._scope._samples
        preview=preview_wrist_correction(binding._reader._originals,expected_basis=binding._reader._basis,
            samples=samples,now_ns=samples[-1]['host_received_ns'],usb_identity=binding._body['usb_identity'])
        clock=binding._reader._clock
        started=clock();request.require_start_time(started)
        claim=dict(schema='rocell.wrist_correction_final_capture_claim.v1',request_sha256=request.request_sha256,
            selection_sha256=digest(canonical(preview)),connection_id=connection._api.connection_id,
            owner_pid=binding._pid,claimed_ns=started,record_hashes=dict(binding._records),motion_authorized=False)
        prefix=binding._body['attempt_id']+'-wrist-correction-final-'
        claim_raw=canonical(claim)
        publish_reservation_bytes(binding._root,prefix+'capture-claim.json',claim_raw,maximum_bytes=65536)
    # read() retains its existing cumulative baseline byte/read limits and uses
    # only handles owned by this exact connection. No new handle is created.
    capture=capture_final_readback(request,read_once=connection.read,cancellation=binding._cancel,
        clock_ns=clock,idle_wait=idle_wait)
    result=dict(schema='rocell.wrist_correction_owned_final_capture.v1',claim_sha256=digest(claim_raw),
        capture=capture,validation=None,status='HELD_FINAL_CAPTURE',error_type=None,motion_authorized=False)
    try:
        result['validation']=validate_final_capture(request,capture,binding._reader._originals,
            basis=binding._reader._basis,baseline_samples=samples,selection_sha256=claim['selection_sha256'],now_ns=clock())
        result['status']='FINAL_CAPTURE_RETAINED_NOT_ADMITTED'
    except Exception as error:
        result['error_type']=type(error).__name__
    raw=canonical(result)
    name=prefix+'capture.original.json'
    publish_reservation_bytes(binding._root,name,raw,maximum_bytes=128*1024)
    if result['status']=='FINAL_CAPTURE_RETAINED_NOT_ADMITTED':
        with binding._lock:
            # Only the owned collector can attach this exact connection/evidence
            # association. A standalone report is not accepted by preparation.
            binding._final_capture_proof=(connection,digest(claim_raw),digest(raw))
    return dict(result,retention=dict(file=name,bytes=len(raw),sha256=digest(raw)))
