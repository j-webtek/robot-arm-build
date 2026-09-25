"""Explicit retained-result retrieval, never acquisition or movement.

Separate from the failed capture workflow: preserve its original outcome and
allow only one explicitly requested GET, bound to its saved POST and boot.
"""
import base64
from pathlib import Path
from .elbow_gain_capture import gain_exchange
from .elbow_gain_review import assess_gain
from .first_motion_contract import canonical
from .physical_onboarding_durability import publish_reservation_bytes
from .product_ghost_export_review import _read
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


def prepare_retained_gain(root, source_id):
    report, digest = _read(Path(root), source_id, 'attachment-gain-transport.json')
    if (report.get('schema') != 'rocell.gain_capture_transport.v1' or
            report.get('category') != 'INCONCLUSIVE' or
            report.get('address') != '192.168.0.225' or
            report.get('retry_allowed') is not False or len(report.get('responses', [])) != 1):
        raise ValueError('A saved single-POST inconclusive capture is required')
    row = report['responses'][0]
    if set(row) != {'method', 'raw_base64'} or row['method'] != 'POST':
        raise ValueError('Exact POST response required')
    raw = base64.b64decode(row['raw_base64'], validate=True)
    if not 0 < len(raw) <= 4095 or base64.b64encode(raw).decode() != row['raw_base64']:
        raise ValueError('Invalid saved response')
    assessment = assess_gain(decode_diagnostic_json(raw, maximum=4095), **report['subject'])
    if assessment['category'] != 'CONTROLLER_REPORTED_GAINS':
        raise ValueError('Complete saved POST required')
    return report, raw, digest


def retrieve_retained_gain(root, source_id, *, authorized=False, exchange=gain_exchange):
    if authorized is not True:
        raise ValueError('Explicit one-GET retrieval required; never auto-retry capture')
    root = Path(root)
    source, post, digest = prepare_retained_gain(root, source_id)
    exporter = WizardDiagnosticExporter(root);exporter.prepare(create=True)
    boot = source['subject']['expected_boot']
    publish_reservation_bytes(root, 'elbow-gain-retention-'+boot+'.json',
        canonical(dict(source_export_id=source_id, source_sha256=digest)), maximum_bytes=2048)
    result = dict(schema='rocell.gain_retention_review.v1', source_export_id=source_id,
        source_sha256=digest, subject=source['subject'], category='INCONCLUSIVE',
        acquisition_repeated=False, servo_commands_sent=False, reset_performed=False,
        retry_allowed=False, retained_copy_verified=False)
    try:
        # This is the ONLY permitted network operation. No capabilities/challenge,
        # POST fallback, automatic reconnect loop or second attempt.
        raw = exchange(source['address'], 'GET')
        if type(raw) is not bytes or not 0 < len(raw) <= 4095:
            raise ValueError('Response budget')
        result['raw_base64'] = base64.b64encode(raw).decode()
        assessment = assess_gain(decode_diagnostic_json(raw, maximum=4095), **source['subject'])
        if raw != post:
            raise ValueError('Retained response differs from saved POST')
        result.update(category='RETAINED_GAIN_COPY_VERIFIED', retained_copy_verified=True,
                      assessment=assessment)
    except (OSError, ValueError, TypeError, KeyError) as error:
        result['error_type'] = type(error).__name__
        if hasattr(error, 'gain_exchange_diagnostic'):
            result['exchange_diagnostic'] = error.gain_exchange_diagnostic
    saved = exporter.export({'mode':'gain-retention-review'}, [],
        attachments={'gain-retention.json':canonical(result)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Retention export failed')
    retained, _ = _read(root, Path(saved['path']).name, 'attachment-gain-retention.json')
    if canonical(retained) != canonical(result):
        raise ValueError('Retention export changed')
    replay_retained_gain(root, Path(saved['path']).name)
    return dict(export_path=saved['path'], report=result)


def replay_retained_gain(root, export_id):
    """Recompute comparison from retained bytes, not a saved success flag."""
    result, _ = _read(Path(root), export_id, 'attachment-gain-retention.json')
    if result.get('schema') != 'rocell.gain_retention_review.v1' or any(
            result.get(field) is not False for field in
            ('acquisition_repeated','servo_commands_sent','reset_performed','retry_allowed')):
        raise ValueError('Invalid retention report contract')
    source, post, digest = prepare_retained_gain(root, result['source_export_id'])
    if (result.get('source_sha256') != digest or
            canonical(result.get('subject')) != canonical(source['subject'])):
        raise ValueError('Retention source binding changed')
    verified = False
    assessment = None
    if 'raw_base64' in result:
        raw = base64.b64decode(result['raw_base64'], validate=True)
        if not 0 < len(raw) <= 4095 or base64.b64encode(raw).decode() != result['raw_base64']:
            raise ValueError('Retention response encoding changed')
        if raw == post:
            assessment = assess_gain(decode_diagnostic_json(raw, maximum=4095), **source['subject'])
            verified = assessment['category'] == 'CONTROLLER_REPORTED_GAINS'
    category = 'RETAINED_GAIN_COPY_VERIFIED' if verified else 'INCONCLUSIVE'
    if result.get('retained_copy_verified') is not verified or result.get('category') != category:
        raise ValueError('Retention outcome does not follow from saved bytes')
    if verified:
        if 'error_type' in result or canonical(result.get('assessment')) != canonical(assessment):
            raise ValueError('Retention assessment changed')
    elif 'assessment' in result or type(result.get('error_type')) is not str:
        raise ValueError('Inconclusive retention must not imply measured gains')
    return dict(category=category, retained_copy_verified=verified,
                source_export_id=result['source_export_id'], hardware_access=False)
