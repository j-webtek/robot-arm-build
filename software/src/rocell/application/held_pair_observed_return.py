"""Read-only return observation and paired endpoint review; no motion authority."""
import base64
import hashlib
from pathlib import Path

from .first_motion_contract import canonical
from .held_pair_observed_forward import replay_observed_pair_forward, replay_pair_responses, _assessment
from .held_pair_return_authorization import replay_pair_return_authorization
from .held_pair_transport import HeldPairHTTPReader, collect_held_pair_snapshot
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter


def _source(root, context_id):
    authorization = replay_pair_return_authorization(root, context_id)
    context = authorization['context']
    forward = replay_observed_pair_forward(root, context['forward_export_id'])
    if forward['export_sha256'] != context['payload']['export_sha256']:
        raise ValueError('Forward archive changed during return review')
    prepared = forward['authorization']['preparation']
    pair = prepared['pair_plan']
    plan = dict(schema='rocell.held_leg_plan.v1', boot_id=pair['boot_id'],
                command_id=pair['return_command_id'], target_count=prepared['historical_anchor'],
                tolerance_counts=pair['tolerance_counts'], policy_sha256=pair['policy_sha256'])
    expected = dict(expected_boot=pair['boot_id'], expected_session=prepared['pair_plan_sha256'],
                    expected_plan=hashlib.sha256(canonical(plan)).hexdigest(), leg='return')
    return authorization, forward, plan, expected


def _review(capture, forward, plan):
    reverse = _assessment(capture, forward['authorization'], plan)
    reverse.pop('historical_anchor_matches', None)  # Return starts at forward endpoint.
    outbound = forward['assessment']
    delta = (reverse['start_position'] - outbound['final_position']
             if 'start_position' in reverse else None)
    # Count-space elbow endpoint continuity only, not Cartesian/tool-tip proof.
    continuity = delta is not None and abs(delta) <= plan['tolerance_counts']
    category = 'INCONCLUSIVE'
    if continuity and reverse['stable_status_observed']:
        if (reverse['category'] == 'CONTROLLER_REPORTED_ARRIVAL' and
                reverse.get('controller_state') == 'COMPLETE'):
            category = 'CONTROLLER_REPORTED_PAIR_ARRIVAL'
        elif reverse['category'] == 'CONTROLLER_REPORTED_NON_ARRIVAL':
            category = 'CONTROLLER_REPORTED_RETURN_NON_ARRIVAL'
    return dict(schema='rocell.observed_pair_review.v1', origin='HOST_HTTP_OBSERVATION',
                category=category, forward=outbound, reverse=reverse,
                endpoint_continuity_verified=continuity, between_leg_delta_counts=delta,
                continuity_scope='ELBOW_SERVO_COUNTS',
                progression_authority=False, provenance_verified=False,
                physical_tip_accuracy_verified=False, wire_observation_verified=False)


def collect_authorized_pair_return(root, context_export_id, *, address, port=80):
    """Collect only return GET endpoints and reopen the exported pair report."""
    root = Path(root).resolve()
    authorization, forward, plan, expected = _source(root, context_export_id)
    reader = HeldPairHTTPReader(address, port)
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    capture = collect_held_pair_snapshot(reader, **expected)
    bundle = dict(schema='rocell.observed_pair_return.v1', origin='HOST_HTTP_OBSERVATION',
        context_export_id=context_export_id, context_sha256=authorization['context_sha256'],
        progression_authority=False, review=_review(capture, forward, plan),
        responses=[dict(path=r['path'], sha256=r['sha256'],
                        raw_base64=base64.b64encode(r['raw']).decode('ascii'))
                   for r in capture['responses']])
    saved = exporter.export({'mode': 'observed-pair-return'}, [],
        attachments={'observed-pair-return.json': canonical(bundle)})
    return dict(export_path=saved['path'],
                **replay_observed_pair_return(root, Path(saved['path']).name))


def replay_observed_pair_return(root, export_id):
    root = Path(root).resolve()
    bundle, digest = _read(root, export_id, 'attachment-observed-pair-return.json')
    if (type(bundle) is not dict or set(bundle) != {'schema', 'origin', 'context_export_id',
            'context_sha256', 'progression_authority', 'review', 'responses'} or
            bundle['schema'] != 'rocell.observed_pair_return.v1' or
            bundle['origin'] != 'HOST_HTTP_OBSERVATION' or bundle['progression_authority'] is not False):
        raise ValueError('Invalid observed return archive')
    authorization, forward, plan, expected = _source(root, bundle['context_export_id'])
    if authorization['context_sha256'] != bundle['context_sha256']:
        raise ValueError('Return authorization context changed')
    capture = replay_pair_responses(bundle['responses'], expected)
    review = _review(capture, forward, plan)
    if canonical(review) != canonical(bundle['review']):
        raise ValueError('Paired endpoint review replay mismatch')
    return dict(replay_verified=True, review=review, export_sha256=digest,
                progression_authority=False, provenance_verified=False)
