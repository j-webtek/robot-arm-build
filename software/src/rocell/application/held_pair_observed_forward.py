"""Read-only forward capture linked to saved authorization; never admits return.

HTTP observations are controller reports, not authenticated servo provenance or
physical tool-tip measurements. Installed endpoint compatibility is a caller
precondition. Neither collection nor replay signs, sends motion, or retries.
"""
import base64
import hashlib
from pathlib import Path

from .first_motion_contract import canonical
from .held_pair_prepared_authorization import replay_initial_pair_authorization
from .held_pair_transport import HeldPairHTTPReader, collect_held_pair_snapshot
from .held_leg_raw_export import _assess
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter


def _expectations(source):
    prepared = source['preparation']
    pair = prepared['pair_plan']
    plan = dict(schema='rocell.held_leg_plan.v1', boot_id=pair['boot_id'],
                command_id=pair['forward_command_id'],
                target_count=prepared['historical_anchor'] + pair['offset_counts'],
                tolerance_counts=pair['tolerance_counts'], policy_sha256=pair['policy_sha256'])
    expected = dict(expected_boot=pair['boot_id'],
                    expected_session=prepared['pair_plan_sha256'],
                    expected_plan=hashlib.sha256(canonical(plan)).hexdigest(), leg='forward')
    return plan, expected


def _assessment(capture, source, plan):
    result = dict(category='INCONCLUSIVE', origin='HOST_HTTP_OBSERVATION',
                  progression_authority=False, provenance_verified=False,
                  physical_tip_accuracy_verified=False, wire_observation_verified=False,
                  stable_status_observed=capture['stable_status_observed'])
    if capture['category'] != 'TRANSPORT_CAPTURED':
        result['reason'] = capture.get('reason', 'INVALID_PAIR_TRANSPORT')
        return result
    digest, assessed = _assess(capture['records'], plan, source['preparation']['policy'])
    # Retain independent endpoint details, but do not inherit simulation origin.
    result.update(assessed)
    result.update(origin='HOST_HTTP_OBSERVATION', progression_authority=False,
                  provenance_verified=False, evidence_sha256=digest,
                  stable_status_observed=True)
    result['category'] = {'VERIFIED_ARRIVAL': 'CONTROLLER_REPORTED_ARRIVAL',
                         'VERIFIED_NON_ARRIVAL': 'CONTROLLER_REPORTED_NON_ARRIVAL'}.get(
                             assessed['category'], 'INCONCLUSIVE')
    result['historical_anchor_matches'] = (
        assessed.get('start_position') == source['preparation']['historical_anchor'])
    result['controller_state'] = capture['status']['state']
    # Even ARRIVED records in a subsequently STOPPED session grant no return.
    return result


def collect_authorized_pair_forward(root, context_export_id, *, address, port=80):
    """Save exact bounded GET responses, reopen and replay before reporting."""
    root = Path(root).resolve()
    source = replay_initial_pair_authorization(root, context_export_id)
    plan, expected = _expectations(source)
    reader = HeldPairHTTPReader(address, port)
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)  # Fail storage setup before any network reads.
    capture = collect_held_pair_snapshot(reader, **expected)
    bundle = dict(schema='rocell.observed_pair_forward.v1', origin='HOST_HTTP_OBSERVATION',
        context_export_id=context_export_id, context_sha256=source['context_sha256'],
        progression_authority=False, assessment=_assessment(capture, source, plan),
        responses=[dict(path=r['path'], sha256=r['sha256'],
                        raw_base64=base64.b64encode(r['raw']).decode('ascii'))
                   for r in capture['responses']])
    saved = exporter.export({'mode': 'observed-pair-forward'}, [],
        attachments={'observed-pair-forward.json': canonical(bundle)})
    replay = replay_observed_pair_forward(root, Path(saved['path']).name)
    return dict(export_path=saved['path'], **replay)


def replay_observed_pair_forward(root, export_id):
    """Reconstruct the same bounded reader from saved bytes, with no I/O to arm."""
    root = Path(root).resolve()
    bundle, digest = _read(root, export_id, 'attachment-observed-pair-forward.json')
    if (type(bundle) is not dict or set(bundle) != {'schema', 'origin',
            'context_export_id', 'context_sha256', 'progression_authority', 'assessment', 'responses'} or
            bundle['schema'] != 'rocell.observed_pair_forward.v1' or
            bundle['origin'] != 'HOST_HTTP_OBSERVATION' or
            bundle['progression_authority'] is not False or
            type(bundle['responses']) is not list or len(bundle['responses']) > 36):
        raise ValueError('Invalid observed forward archive')
    source = replay_initial_pair_authorization(root, bundle['context_export_id'])
    if source['context_sha256'] != bundle['context_sha256']:
        raise ValueError('Forward authorization context changed')
    plan, expected = _expectations(source)
    capture = replay_pair_responses(bundle['responses'], expected)
    assessment = _assessment(capture, source, plan)
    if canonical(assessment) != canonical(bundle['assessment']):
        raise ValueError('Forward observation replay mismatch')
    return dict(replay_verified=True, assessment=assessment, export_sha256=digest,
                authorization=source, forward_plan=plan,
                progression_authority=False, provenance_verified=False)


def replay_pair_responses(responses, expected):
    """Shared exact-byte archive reader for either leg; never accesses hardware."""
    if type(responses) is not list or len(responses) > 36:
        raise ValueError('Invalid response collection')
    rows = []
    for row in responses:
        if (type(row) is not dict or set(row) != {'path', 'sha256', 'raw_base64'} or
                type(row['raw_base64']) is not str or len(row['raw_base64']) > 12288):
            raise ValueError('Invalid saved HTTP response')
        raw = base64.b64decode(row['raw_base64'], validate=True)
        if (base64.b64encode(raw).decode('ascii') != row['raw_base64'] or
                hashlib.sha256(raw).hexdigest() != row['sha256']):
            raise ValueError('Saved response bytes changed')
        rows.append((row['path'], raw))
    cursor = 0
    def read(path, **kwargs):
        nonlocal cursor
        if cursor == len(rows):
            raise OSError('Retained capture ended before completion')
        saved_path, raw = rows[cursor]
        if saved_path != path:
            raise ValueError('Saved response order mismatch')
        cursor += 1
        return raw
    capture = collect_held_pair_snapshot(read, **expected)
    if cursor != len(rows):
        raise ValueError('Unexpected trailing responses')
    return capture
