"""Pure campaign-to-supervisor request mapping; never launches or admits IO."""
import hashlib

from rocell.application.first_motion_contract import canonical
from .owned_worker_process import OwnedWorkerRequest, owned_request_wire
from .positional_campaign_native_protocol import validate_payload, decode_request


def prepare_owned_request(registration, payload):
    """Preserve the campaign intent hash as its operation identity.

    This differs from single-trial handoffs that hash the complete payload.
    Round-trip the actual supervisor wire so deadline, registration, identity
    and operation mismatches are rejected before any caller can launch it.
    File validation, current review and one-use reservation remain separate.
    """
    intent = validate_payload(payload)
    body = intent.to_dict()
    request = OwnedWorkerRequest(body['campaign_id'], body['session_id'],
        body['references']['source_sha256'], intent.sha256,
        hashlib.sha256(canonical(body['usb_identity'])).hexdigest(),
        body['deadline_ns'], canonical(payload))
    wire, digest = owned_request_wire(registration, request, deadline_ns=body['deadline_ns'])
    decoded = decode_request(wire)
    if decoded['request_sha256'] != digest:
        raise ValueError('Campaign supervisor wire digest differs')
    return request, wire
