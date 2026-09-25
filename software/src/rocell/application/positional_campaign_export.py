"""Immutable owned-campaign diagnostics; neither authentication nor live authority.

The manifest is published last. A partial publication stays on disk for review
and is never adopted, overwritten or used to resume motion. Reproduction checks
use only originals inside this directory, so exports can be moved off-host.
"""
import hashlib

from .first_motion_contract import canonical
from .physical_onboarding_durability import (
    PublicationMode, contained_path, publish_bytes, read_bounded_regular_file, safe_root,
)
from .positional_campaign_reconstruction import verify_completed_owned_campaign
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent

MAX_RESULT_BYTES = 2_097_152
SCHEMA = 'rocell.owned_positional_campaign_export.v1'


def _decode(raw, maximum):
    value = decode_diagnostic_json(raw, maximum=maximum)
    if type(value) is not dict or canonical(value) != raw:
        raise ValueError('Canonical campaign original required')
    return value


def _manifest(request_raw, result_raw):
    request = PositionalCampaignIntent(request_raw)
    result = _decode(result_raw, MAX_RESULT_BYTES)
    if (result.get('schema') != 'rocell.owned_positional_campaign.v1'
            or result.get('intent_sha256') != request.sha256
            or result.get('basis') != 'SYNTHETIC_WIRE_REHEARSAL'
            or type(result.get('physical_write_count')) is not int
            or result['physical_write_count'] != 0
            or any(result.get(key) is not False for key in (
                'native_execution_released', 'physical_stop_verified', 'replay_allowed'))):
        raise ValueError('Exact nonphysical owned campaign association required')
    # Invalid/incomplete endpoint data remains useful evidence. Save it without
    # promoting its original success label. Only the common verifier decides
    # whether a fully evaluated run can be reconstructed, including held misses.
    try:
        reconstruction = verify_completed_owned_campaign(request, result)
    except (ValueError, TypeError, KeyError, IndexError):
        reconstruction = None
    return dict(schema=SCHEMA, intent_sha256=request.sha256,
        originals={name: dict(bytes=len(raw), sha256=hashlib.sha256(raw).hexdigest())
            for name, raw in (('intent.json', request_raw), ('result.json', result_raw))},
        disposition='RECONSTRUCTED' if reconstruction else 'DIAGNOSTIC_ONLY',
        reconstruction=reconstruction, physical_accuracy_verified=False,
        physical_stop_verified=False, motion_authorized=False, replay_allowed=False)


def publish_owned_campaign_export(root, request, result):
    """Save an exact attempted result once, without running or retrying anything."""
    if type(request) is not PositionalCampaignIntent or type(result) is not dict:
        raise ValueError('Exact owned campaign request/result required')
    request_raw, result_raw = request.canonical_bytes, canonical(result)
    manifest = _manifest(request_raw, result_raw)
    root = safe_root(root)
    directory = contained_path(root, request.to_dict()['campaign_id'] + '-owned-export',
        label='owned campaign export')
    directory.mkdir(exist_ok=False)
    for name, raw, limit in (
            ('intent.json', request_raw, 16384),
            ('result.json', result_raw, MAX_RESULT_BYTES),
            ('manifest.json', canonical(manifest), 16384)):
        publish_bytes(directory, name, raw, mode=PublicationMode.IMMUTABLE, maximum_bytes=limit)
    # A publication receipt means originals were read back and reproduced,
    # never that a physical endpoint or physical stopping was verified.
    verified = verify_owned_campaign_export(directory)
    return dict(path=str(directory), **verified)


def verify_owned_campaign_export(directory):
    """Rebuild all claims from local originals; ignore no extra/missing files."""
    directory = safe_root(directory)
    if {path.name for path in directory.iterdir()} != {'intent.json', 'result.json', 'manifest.json'}:
        raise ValueError('Incomplete or unexpected owned campaign export entries')
    request_raw = read_bounded_regular_file(directory / 'intent.json', maximum_bytes=16384)
    result_raw = read_bounded_regular_file(directory / 'result.json', maximum_bytes=MAX_RESULT_BYTES)
    manifest_raw = read_bounded_regular_file(directory / 'manifest.json', maximum_bytes=16384)
    expected = _manifest(request_raw, result_raw)
    if canonical(expected) != manifest_raw:
        raise ValueError('Campaign export originals or manifest changed')
    return dict(valid=True, manifest_sha256=hashlib.sha256(manifest_raw).hexdigest(),
        **expected)
