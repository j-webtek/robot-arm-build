"""Exact-byte leg archives and replay. Simulation only; no signing or transport.

Preserve raw bytes separately from parsed assessment inputs. Hardware provenance
must come from a future concrete collector, never an origin supplied by a caller.
"""
import base64
from pathlib import Path

from .first_motion_contract import canonical
from .held_evidence_digest import held_evidence_digest
from .held_leg_replay import assess_simulated_held_leg
from .product_ghost_export_review import _read
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter

SCHEMAS = {'held_leg_scan': 'rocell.held_leg_snapshot.v1',
           'held_leg_action': 'rocell.hold_action.v1',
           'held_leg_end': 'rocell.held_leg_terminal.v1'}


def _assess(rows, plan, policy):
    digest = held_evidence_digest(rows)
    parsed = []
    for kind, raw in rows:
        value = decode_diagnostic_json(raw, maximum=4095)
        if type(value) is not dict or value.get('schema') != SCHEMAS[kind]:
            raise ValueError('Storage kind and JSON schema differ')
        parsed.append(value)
    return digest, assess_simulated_held_leg(parsed, plan=plan, policy=policy)


def export_raw_simulated_held_leg(root, rows, *, plan, policy):
    """Save, reopen, verify manifest and replay before reporting success."""
    digest, assessment = _assess(rows, plan, policy)
    bundle = dict(schema='rocell.raw_simulated_held_leg.v1', origin='SIMULATION',
                  progression_authority=False, evidence_sha256=digest,
                  plan=plan, policy=policy, assessment=assessment,
                  records=[dict(kind=kind, raw_base64=base64.b64encode(raw).decode('ascii'))
                           for kind, raw in rows])
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'raw-simulated-held-leg'}, [],
                            attachments={'raw-held-leg.json': canonical(bundle)})
    result = replay_raw_simulated_held_leg(root, Path(saved['path']).name)
    return dict(export_path=saved['path'], **result)


def replay_raw_simulated_held_leg(root, export_id):
    bundle, export_digest = _read(Path(root).resolve(), export_id, 'attachment-raw-held-leg.json')
    if (type(bundle) is not dict or set(bundle) != {'schema', 'origin',
            'progression_authority', 'evidence_sha256', 'plan', 'policy', 'assessment', 'records'} or
            bundle['schema'] != 'rocell.raw_simulated_held_leg.v1' or
            bundle['origin'] != 'SIMULATION' or bundle['progression_authority'] is not False or
            type(bundle['records']) is not list or not 1 <= len(bundle['records']) <= 34):
        raise ValueError('Invalid raw simulation archive')
    rows = []
    for record in bundle['records']:
        if (type(record) is not dict or set(record) != {'kind', 'raw_base64'} or
                type(record['raw_base64']) is not str or len(record['raw_base64']) > 5460):
            raise ValueError('Invalid raw record envelope')
        try:
            raw = base64.b64decode(record['raw_base64'], validate=True)
        except (ValueError, UnicodeError) as exc:
            raise ValueError('Invalid raw base64') from exc
        if base64.b64encode(raw).decode('ascii') != record['raw_base64']:
            raise ValueError('Noncanonical base64')
        rows.append((record['kind'], raw))
    digest, assessment = _assess(rows, bundle['plan'], bundle['policy'])
    if digest != bundle['evidence_sha256'] or canonical(assessment) != canonical(bundle['assessment']):
        raise ValueError('Raw evidence or assessment replay mismatch')
    return dict(origin='SIMULATION', progression_authority=False, replay_verified=True,
                evidence_sha256=digest, export_sha256=export_digest, assessment=assessment)
