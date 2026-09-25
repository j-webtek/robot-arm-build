"""Reconstruct campaign references from fixed, retained host-owned originals.

Hashes associate reviewed bytes; they do not establish their physical truth.
The bootstrap must separately validate runtime invocation, controller binding,
and release evidence. No caller-selected original path is accepted here.
"""
import hashlib
from pathlib import Path

from rocell.safety.positional_campaign_authority import PositionalCampaignIntent, BOUNDED_SCHEMAS
from .wizard_diagnostic_coordinator import source_fingerprint, decode_diagnostic_json
from .physical_onboarding_durability import safe_root, contained_path, read_bounded_regular_file

ORIGINAL_FILES = {
    'runtime_sha256': 'runtime.original.json',
    'protocol_review_sha256': 'protocol.original.json',
    'native_controller_review_sha256': 'controller.original.json',
    'configuration_sha256': 'configuration.original.json',
    'workcell_sha256': 'workcell.original.json',
    'tool_payload_sha256': 'tool-payload.original.json',
    'stop_qualification_sha256': 'stop-qualification.original.json',
    'owned_baseline_sha256': 'owned-baseline.original.json',
}


class PositionalCampaignReferenceReader:
    def __init__(self, request, *, workspace, root):
        if type(request) is not PositionalCampaignIntent:
            raise ValueError('Exact campaign intent required')
        self._request = request
        self._files = dict(ORIGINAL_FILES)
        if request.to_dict()['schema'] in BOUNDED_SCHEMAS:
            self._files.pop('stop_qualification_sha256')
            self._files['bounded_motion_risk_sha256'] = 'bounded-motion-risk.original.json'
        self._workspace = safe_root(Path(workspace))
        self._directory = contained_path(safe_root(root), request.to_dict()['campaign_id']
            + '-positional-native-child', label='campaign original directory')

    def original(self, reference):
        if reference not in self._files:
            raise ValueError('Unknown campaign original reference')
        # Baseline telemetry may be larger than the compact review documents.
        limit = 2_097_152 if reference == 'owned_baseline_sha256' else 131072
        raw = read_bounded_regular_file(contained_path(safe_root(self._directory),
            self._files[reference], label='campaign reference original'), maximum_bytes=limit)
        value = decode_diagnostic_json(raw, maximum=limit)
        if type(value) is not dict or not value:
            raise ValueError('Structured campaign original required')
        if hashlib.sha256(raw).hexdigest() != self._request.to_dict()['references'][reference]:
            raise ValueError('Campaign reference original changed')
        if reference == 'bounded_motion_risk_sha256':
            checks = {'operator_present', 'entire_accepted_motion_clear', 'no_contact',
                'no_added_payload', 'accepted_goal_may_finish', 'software_cancel_is_not_physical_stop'}
            if (set(value) != checks | {'schema'}
                    or value['schema'] != 'rocell.attended_bounded_motion_risk.v1'
                    or any(value[name] is not True for name in checks)):
                raise ValueError('Explicit bounded attended completion-risk review required')
        return raw

    def __call__(self):
        refs = {'source_sha256': source_fingerprint(self._workspace)}
        for name in self._files:
            refs[name] = hashlib.sha256(self.original(name)).hexdigest()
        if refs != self._request.to_dict()['references']:
            raise ValueError('Campaign source/reference mismatch')
        return tuple(sorted(refs.items()))


class FrozenPositionalCampaignReferences:
    """Immutable startup snapshot, not a fresh USB or physical-state observation.

    Freeze after pinned runtime verification. Repeated endpoint checks can use
    this snapshot without rehashing the complete workspace inside each leg.
    Any new campaign must reconstruct a new snapshot and receive a new review.
    """
    def __init__(self, reader):
        if type(reader) is not PositionalCampaignReferenceReader:
            raise ValueError('Exact campaign original reader required')
        refs = reader()
        originals = tuple((name, reader.original(name)) for name in sorted(reader._files))
        if reader() != refs:
            raise ValueError('Campaign references changed during freeze')
        self._references, self._originals = refs, originals

    def __call__(self):
        return self._references

    def original(self, name):
        if name not in dict(self._originals):
            raise ValueError('Unknown frozen campaign original')
        return dict(self._originals)[name]
