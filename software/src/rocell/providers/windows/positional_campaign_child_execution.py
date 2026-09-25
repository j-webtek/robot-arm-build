"""Internal claimed-child composition; not a registered executable entry.

The future bootstrap must verify its actual executable/package invocation and
construct the authenticated reader from host-owned originals. Neither reader
callbacks nor serial factories are accepted from IPC. This function does not
qualify physical stop behavior or grant unattended release.
"""
from threading import Event
import time

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import safe_root
from rocell.application.positional_campaign_launch import claim_campaign_worker
from rocell.application.positional_campaign_native_retention import retain_native_trial
from rocell.safety.positional_campaign_admission import admit_positional_campaign
from .positional_current_context import AuthenticatedPositionalReader
from .positional_campaign_native_protocol import decode_request
from .positional_campaign_serial_api import WindowsPositionalCampaignSerialApi
from .positional_campaign_serial_connection import PositionalCampaignSerialConnection
from .positional_campaign_execution import run_native_campaign


def _execute_authenticated_campaign_child(request_raw, reader, *, cancellation,
        clock_ns=time.monotonic_ns):
    """Return a compact retained-result receipt, never a second motion attempt.

    Preparation failures propagate to the future bootstrap's error receipt.
    Once IO starts, the runner closes its owned connection and retains partial
    outcomes. A retention error cannot rearm the consumed process/leg claims.
    """
    if (type(reader) is not AuthenticatedPositionalReader
            or type(cancellation) is not Event or not callable(clock_ns)):
        raise ValueError('Exact internal reader, cancellation and clock required')
    payload = decode_request(request_raw)['payload']
    root = safe_root(payload['root'])
    request = reader.request
    if (root != reader._root
            or canonical(payload['campaign_intent']) != request.canonical_bytes):
        raise ValueError('Campaign child reader/request/root mismatch')
    if cancellation.is_set():
        raise ValueError('Campaign cancelled before child claim')
    request.require_start_time(clock_ns())
    claim = claim_campaign_worker(root, reader, launch_sha256=payload['launch_sha256'])
    permit = admit_positional_campaign(request, reader=reader, root=root)
    try:
        if cancellation.is_set():
            raise ValueError('Campaign cancelled before native composition')
        evidence = reader.verify_endpoint()
        api = WindowsPositionalCampaignSerialApi.from_campaign_claim(request, permit, claim,
            port_name=evidence['port_name'], connection_id=request.to_dict()['campaign_id'],
            cancellation=cancellation, clock_ns=clock_ns)
        connection = PositionalCampaignSerialConnection(request, api, clock_ns=clock_ns)
        result = run_native_campaign(request, permit, connection,
            cancellation=cancellation, clock_ns=clock_ns)
        return retain_native_trial(root, request, result, claim_sha256=claim.claim_sha256)
    finally:
        permit.revoke()
