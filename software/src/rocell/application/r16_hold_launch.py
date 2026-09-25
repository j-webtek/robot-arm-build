"""Receipt-bound ordinary hold admission for r16; never resets or recovers.

Startup evidence is historical. The existing trial runner separately requires a
fresh same-boot idle response before reserving and sending a single hold.
"""
import hashlib
import json
from pathlib import Path

from .first_motion_contract import canonical
from .hold_first_trial_run import run_first_hold
from .product_ghost_export_review import _read
from .r10_provisioned_evidence import POLICY
from .supported_recovery_installation import review_recovery_startup
from .wizard_diagnostic_export import WizardDiagnosticExporter


def review_r16_hold_launch(software_root, startup_export_id):
    root = Path(software_root).resolve()
    # Both paths use the same strict r16 installation/startup validator. A
    # recovery result is not a startup export and cannot satisfy this contract.
    binding = review_recovery_startup(root, startup_export_id)
    boot = binding['expected_boot']
    exports = root / 'runs/wizard-exports'
    for name in ('first-hold-trial-', 'supported-recovery-trial-'):
        if (exports / (name + boot + '.json')).exists():
            raise ValueError('Boot already consumed by hold or recovery; no automatic restart')
    configuration = json.loads((root / 'docs/hold-r7-supported-pose-draft.json').read_bytes())
    if hashlib.sha256(canonical(configuration)).hexdigest() != POLICY:
        raise ValueError('Reviewed ordinary hold configuration changed')
    return binding, configuration


def run_r16_hold(software_root, *, startup_export_id, key, authorized_powered_hold=False):
    if authorized_powered_hold is not True:
        raise ValueError('Explicit powered hold authorization required')
    root = Path(software_root).resolve()
    binding, configuration = review_r16_hold_launch(root, startup_export_id)
    exports = root / 'runs/wizard-exports'
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    intent = exporter.export({'mode': 'r16-ordinary-hold-binding'}, [], attachments={
        'hold-launch-binding.json': canonical(binding),
        'hold-launch-configuration.json': canonical(configuration)})
    intent_id = Path(intent['path']).name
    for name, expected in (('binding', binding), ('configuration', configuration)):
        retained, _ = _read(exports, intent_id, f'attachment-hold-launch-{name}.json')
        if canonical(retained) != canonical(expected):
            raise ValueError('Hold launch intent changed; no command sent')
    result = run_first_hold(exports, configuration=configuration,
        expected_boot=binding['expected_boot'], key=key, address=binding['address'],
        authorized_powered_hold=True)
    return dict(binding_export_id=intent_id, observation=result)
