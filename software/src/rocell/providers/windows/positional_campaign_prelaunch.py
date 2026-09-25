"""Authenticate an unclaimed campaign reservation; never consume or launch it.

The child still claims atomically. A successful prelaunch check cannot guarantee
another caller will not claim afterward; it is not a replacement for that claim.
Runtime pin validation and physical qualification remain separate requirements.
"""
from threading import Event
import time

from rocell.application.physical_onboarding_durability import safe_root, contained_path
from rocell.application.positional_campaign_launch import _verify_launch
from .positional_campaign_native_protocol import decode_request
from .positional_campaign_bootstrap import prepare_authenticated_campaign_reader
from rocell.safety.positional_campaign_authority import BOUNDED_SCHEMAS


def verify_reserved_campaign_entry(workspace, request_raw, *, cancellation,
        clock_ns=time.monotonic_ns):
    if type(cancellation) is not Event or not callable(clock_ns):
        raise ValueError('Owned campaign cancellation and clock required')
    if cancellation.is_set():
        raise ValueError('Campaign cancelled before prelaunch')
    wire = decode_request(request_raw)
    if wire['payload']['campaign_intent']['schema'] not in BOUNDED_SCHEMAS:
        raise ValueError('Bounded attended v2/v3 risk review required for native launch')
    root = safe_root(wire['payload']['root'])
    claimed = contained_path(root, wire['attempt_id'] + '-positional-claimed.json',
        label='campaign process claim')
    def unclaimed():
        if claimed.exists():
            raise ValueError('Campaign process attempt already claimed')
        if cancellation.is_set():
            raise ValueError('Campaign cancelled during prelaunch')
    unclaimed()
    reader = prepare_authenticated_campaign_reader(workspace, request_raw,
        cancellation=cancellation, clock_ns=clock_ns)
    _verify_launch(root, reader, wire['payload']['launch_sha256'])
    unclaimed()
    reader.request.require_start_time(clock_ns())
    return reader
