"""Prepared-attempt -> bounded GET transcript -> assessment, simulation origin.

No sender is accepted here. Caller supplies a reader; firmware compatibility and
permission for any real read remain the caller's responsibility. The review stays
SIMULATION until the live provenance/commissioning path is separately integrated.
"""
from pathlib import Path

from .first_motion_contract import canonical
from .hold_bound_replay import assess_bound_simulation
from .hold_started_review import _prepared, _challenge_window
from .hold_transport_export import capture_hold_transport, replay_hold_transport_bundle
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter


def _assessment(summary, plan, policy, challenge, *, include_endpoint=False):
    unknown = dict(origin='SIMULATION', category='INCONCLUSIVE', progression_authority=False,
                   endpoint_verified=False, reason='TRANSPORT_NOT_COMPLETE_CAPTURE')
    if summary['category'] != 'TRANSPORT_CAPTURED' or summary.get('status', {}).get('state') != 'CAPTURED':
        return unknown
    try:
        _challenge_window(summary['records'], challenge)
    except (ValueError, TypeError, KeyError, IndexError):
        unknown['reason'] = 'CAPTURE_OUTSIDE_CHALLENGE_OR_INVALID'
        return unknown
    return assess_bound_simulation(summary['records'], expected_plan=plan, expected_policy=policy,
                                   include_endpoint=include_endpoint)


def collect_prepared_hold_simulation(root, prepared_export_id, get_bytes):
    root = Path(root).resolve()
    _, prepared_digest, plan, policy, challenge = _prepared(root, prepared_export_id)
    transport = capture_hold_transport(root, get_bytes, expected_boot=plan['boot_id'])
    transport_id = Path(transport['export_path']).name
    _, transport_digest = _read(root, transport_id, 'attachment-hold-transport.json')
    assessed = _assessment(transport['summary'], plan, policy, challenge)
    report = dict(schema='rocell.collected_hold_simulation.v1', prepared_export_id=prepared_export_id,
                  prepared_sha256=prepared_digest, transport_export_id=transport_id,
                  transport_sha256=transport_digest, assessment=assessed,
                  retry_allowed=False, progression_authority=False)
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'collected-hold-simulation'}, [],
        attachments={'collected-hold.json': canonical(report)})
    replay = replay_collected_hold_simulation(root, Path(saved['path']).name)
    return dict(export_path=saved['path'], export_verified=True, replay_verified=replay['matches'],
                assessment=replay['assessment'], delivery=replay['delivery'],
                retry_allowed=False, progression_authority=False)


def replay_collected_hold_simulation(root, export_id):
    root = Path(root).resolve()
    report, _ = _read(root, export_id, 'attachment-collected-hold.json')
    fields = {'schema', 'prepared_export_id', 'prepared_sha256', 'transport_export_id',
              'transport_sha256', 'assessment', 'retry_allowed', 'progression_authority'}
    if (type(report) is not dict or set(report) != fields or
            report['schema'] != 'rocell.collected_hold_simulation.v1' or
            report['retry_allowed'] is not False or report['progression_authority'] is not False):
        raise ValueError('Invalid collected hold linkage')
    prepared, prepared_digest, plan, policy, challenge = _prepared(root, report['prepared_export_id'])
    bundle, transport_digest = _read(root, report['transport_export_id'], 'attachment-hold-transport.json')
    if (prepared_digest != report['prepared_sha256'] or transport_digest != report['transport_sha256'] or
            bundle['expected_boot'] != plan['boot_id']):
        raise ValueError('Changed capture or prepared attempt')
    replay = replay_hold_transport_bundle(bundle)
    assessed = _assessment(replay['summary'], plan, policy, challenge)
    if canonical(assessed) != canonical(report['assessment']):
        raise ValueError('Collected hold assessment does not replay')
    return dict(matches=True, assessment=assessed, delivery=prepared['delivery'],
                endpoint_review=_assessment(replay['summary'], plan, policy, challenge, include_endpoint=True),
                retry_allowed=False, progression_authority=False)
