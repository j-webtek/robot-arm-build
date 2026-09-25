"""Public pair-settings bytes, shared by offline staging and admission review.

No key handling, private-image mounting, device access or configuration writes.
Settings describe relative count targets, not physical position or permission.
"""
import hashlib
from pathlib import Path

from .first_motion_contract import canonical
from .servo_diagnostic_contract import _identifier
from .wizard_diagnostic_coordinator import decode_diagnostic_json
from .wizard_diagnostic_export import WizardDiagnosticExporter
from .product_ghost_export_review import _read


def encode_pair_settings(*, forward_command_id, return_command_id, offset_counts=6, tolerance_counts=2):
    _identifier(forward_command_id);_identifier(return_command_id)
    if (forward_command_id==return_command_id or type(offset_counts) is not int
            or type(tolerance_counts) is not int or not 0<=tolerance_counts<=2
            or not 2*tolerance_counts<abs(offset_counts)<=16):
        raise ValueError('Distinct IDs and bounded nonoverlapping count targets required')
    return canonical(dict(schema='rocell.controller_pair.v1',forward_command_id=forward_command_id,
        return_command_id=return_command_id,offset_counts=offset_counts,tolerance_counts=tolerance_counts))


def decode_pair_settings(raw):
    if type(raw) is not bytes or not 1<=len(raw)<=1024:
        raise ValueError('Bounded canonical settings bytes required')
    value=decode_diagnostic_json(raw,maximum=1024)
    if (type(value) is not dict or set(value)!={'schema','forward_command_id','return_command_id',
            'offset_counts','tolerance_counts'} or value['schema']!='rocell.controller_pair.v1'):
        raise ValueError('Unsupported pair settings')
    fields={name:value[name] for name in value if name!='schema'}
    if encode_pair_settings(**fields)!=raw:raise ValueError('Noncanonical pair settings')
    return value


def require_pair_settings_match(raw, preparation):
    """Match all configured fields to a separately replayed pair preparation."""
    settings=decode_pair_settings(raw)
    plan=preparation['pair_plan']
    fields = ('forward_command_id','return_command_id','offset_counts','tolerance_counts')
    # JSON number/bool types matter: Python equality would accept 12.0 as 12.
    if canonical({name:settings[name] for name in fields}) != canonical(
            {name:plan.get(name) for name in fields}):
        raise ValueError('Configured pair differs from prepared commands')
    return hashlib.sha256(raw).hexdigest()


def export_pair_settings(export_root, raw):
    """Export a public draft only. Never create /rocell-pair.json on a device."""
    settings=decode_pair_settings(raw)
    report=dict(schema='rocell.pair_settings_draft.v1',device_path='/rocell-pair.json',
        settings=settings,settings_sha256=hashlib.sha256(raw).hexdigest(),
        hardware_access=False,provisioning_performed=False,motion_authorized=False)
    root=Path(export_root)
    exporter=WizardDiagnosticExporter(root);exporter.prepare(create=True)
    saved=exporter.export({'mode':'pair-settings-draft'},[],
        attachments={'pair-settings-draft.json':canonical(report)})
    retained,_=_read(root,Path(saved['path']).name,'attachment-pair-settings-draft.json')
    if canonical(retained)!=canonical(report):raise ValueError('Settings draft export changed')
    return dict(export_path=saved['path'],report=report)
