"""Read-only HTTP observation of a previously sent hold; never starts a trial.

Host-observed HTTP is not authenticated device provenance. Reuse the deterministic
record validator, but report its result as controller evidence, not simulated
motion or measured physical-tip arrival. No result authorizes another command.
"""
from pathlib import Path

from .first_motion_contract import canonical
from .hold_collected_review import _assessment
from .hold_started_review import _prepared
from .hold_transport_snapshot import HoldHTTPReader
from .hold_transport_export import capture_hold_transport, replay_hold_transport_bundle
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter


def _observed_assessment(summary, plan, policy, challenge):
    result = _assessment(summary, plan, policy, challenge, include_endpoint=True)
    # Success describes agreement of reported native counts only. It cannot
    # establish external coordinates, wire-level observation, or device identity.
    if result['category'] == 'SIMULATED_HOLD_VERIFIED':
        result['category'] = 'CONTROLLER_REPORTED_HOLD_VERIFIED'
    result.update(schema='rocell.observed_hold_assessment.v1', origin='HOST_HTTP_OBSERVATION',
                  provenance_verified=False, physical_tip_accuracy_verified=False,
                  progression_authority=False, whole_arm_ready=False)
    return result


def collect_prepared_hold_observation(root, prepared_export_id, *, address, port=80):
    """Collect bounded GETs from an explicit endpoint after validating the attempt.

    No injectable sender, challenge, reset, retries, or torque/motion operations.
    Export storage is prepared by capture_hold_transport before its first GET.
    """
    root = Path(root).resolve()
    _, prepared_digest, plan, policy, challenge = _prepared(root, prepared_export_id)
    reader = HoldHTTPReader(address, port)
    transport = capture_hold_transport(root, reader, expected_boot=plan['boot_id'])
    transport_id = Path(transport['export_path']).name
    _, transport_digest = _read(root, transport_id, 'attachment-hold-transport.json')
    report = dict(schema='rocell.collected_hold_observation.v1',
                  endpoint=dict(address=reader.address, port=reader.port),
                  prepared_export_id=prepared_export_id, prepared_sha256=prepared_digest,
                  transport_export_id=transport_id, transport_sha256=transport_digest,
                  assessment=_observed_assessment(transport['summary'], plan, policy, challenge),
                  retry_allowed=False, progression_authority=False)
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'collected-hold-observation'}, [],
        attachments={'observed-hold.json': canonical(report)})
    replay = replay_hold_observation(root, Path(saved['path']).name)
    return dict(export_path=saved['path'], replay_verified=replay['matches'],
                assessment=replay['assessment'], delivery=replay['delivery'],
                retry_allowed=False, progression_authority=False)


def replay_hold_observation(root, export_id):
    """Offline replay checks hashes, attempt linkage, timing, and count criteria."""
    root = Path(root).resolve()
    report, _ = _read(root, export_id, 'attachment-observed-hold.json')
    fields = {'schema', 'endpoint', 'prepared_export_id', 'prepared_sha256',
              'transport_export_id', 'transport_sha256', 'assessment',
              'retry_allowed', 'progression_authority'}
    if (type(report) is not dict or set(report) != fields or
            report['schema'] != 'rocell.collected_hold_observation.v1' or
            report['retry_allowed'] is not False or report['progression_authority'] is not False or
            type(report['endpoint']) is not dict or set(report['endpoint']) != {'address', 'port'}):
        raise ValueError('Invalid observed hold linkage')
    # Construction validates the destination without opening a connection.
    HoldHTTPReader(**report['endpoint'])
    prepared, digest, plan, policy, challenge = _prepared(root, report['prepared_export_id'])
    bundle, transport_digest = _read(root, report['transport_export_id'], 'attachment-hold-transport.json')
    if (digest != report['prepared_sha256'] or transport_digest != report['transport_sha256'] or
            bundle['expected_boot'] != plan['boot_id']):
        raise ValueError('Changed observed capture or prepared attempt')
    replay = replay_hold_transport_bundle(bundle)
    assessed = _observed_assessment(replay['summary'], plan, policy, challenge)
    if canonical(assessed) != canonical(report['assessment']):
        raise ValueError('Observed hold assessment does not replay')
    return dict(matches=True, assessment=assessed, delivery=prepared['delivery'],
                controller_status=replay['summary'].get('status'),
                stable_status_observed=replay['summary'].get('stable_status_observed') is True,
                retry_allowed=False, progression_authority=False)
