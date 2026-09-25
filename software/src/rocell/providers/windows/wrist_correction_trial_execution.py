"""Internal process-claim/permit composition; no public launch registration.

The outer isolated worker must still prove executable ownership and enforce its
deadline. A successful local claim never upgrades that evidence to verified.
"""
from threading import Event
import time

from rocell.application.wrist_correction_owned_trial import _run_wrist_correction_trial
from rocell.application.wrist_correction_worker_claim import WristCorrectionWorkerClaim
from rocell.safety.wrist_correction_admission import WristCorrectionPermit
from .wrist_correction_native_protocol import validate_payload, evidence_manifest, require
from .wrist_correction_serial_api import WindowsWristCorrectionSerialApi
from .wrist_correction_serial_connection import WristCorrectionSerialConnection


def _execute_claimed_correction_trial(payload,permit,api,*,worker_claim,
        current_source_sha256,current_runtime_sha256,cancellation,
        clock_ns=time.monotonic_ns,idle_wait=None):
    require(type(permit) is WristCorrectionPermit,'Exact correction permit required')
    try:
        decoded_request=validate_payload(payload)
        request=permit._request
        require(request==decoded_request,'Correction context differs from permit')
        require(type(api) is WindowsWristCorrectionSerialApi and
            type(worker_claim) is WristCorrectionWorkerClaim and type(cancellation) is Event and
            callable(clock_ns) and (idle_wait is None or callable(idle_wait)),
            'Exact claimed correction dependencies required')
        binding=permit._binding
        reader=binding._reader
        require(api.matches_authorization(request,permit) and reader.request==request and
            cancellation is binding._cancel and worker_claim._root==binding._root and
            worker_claim._authority is reader._authority and
            reader._basis==payload['expected_basis'] and
            evidence_manifest(reader._originals)==payload['originals'],
            'Correction permit differs from claimed selection')
        # Consumption is durable before connection construction/open. Even a
        # cancelled trial cannot replay this process claim later.
        worker_claim.consume(payload,current_source_sha256=current_source_sha256,
            current_runtime_sha256=current_runtime_sha256,now_ns=clock_ns())
        connection=WristCorrectionSerialConnection(request,api,clock_ns=clock_ns)
        result=_run_wrist_correction_trial(connection,permit,cancellation=cancellation,
            clock_ns=clock_ns,idle_wait=idle_wait)
        return dict(schema='rocell.claimed_wrist_correction_trial.v1',
            claim_sha256=worker_claim.claim_sha256,status=result['status'],result=result,
            owned_process_verified=False,physical_authority=False,replay_allowed=False)
    finally:
        permit.revoke()
