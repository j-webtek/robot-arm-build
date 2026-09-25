"""Exact installed observed-pose ordinary hold; no recovery, reset or pair."""
import hashlib
from pathlib import Path
from .first_motion_contract import canonical
from .observed_pose_installation import review_observed_startup
from .observed_pose_candidate import replay_candidate
from .observed_pose_recovery import HOLD_SHA
from .hold_first_trial_run import run_first_hold
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter


def review_observed_hold(root, *, startup_export, stage_export, installation_export):
    root = Path(root).resolve()
    binding = review_observed_startup(root, startup_export=startup_export,
        stage_export=stage_export, installation_export=installation_export)
    boot = binding['expected_boot']; exports = root/'runs/wizard-exports'
    for prefix in ('first-hold-trial-', 'supported-recovery-trial-'):
        if (exports/(prefix+boot+'.json')).exists():
            raise ValueError('Boot consumed by hold or recovery; no automatic restart')
    source = replay_candidate(root, binding['observed_pose_installation']['public_candidate_export'])
    config = source['report']['hold_settings']
    if hashlib.sha256(canonical(config)).hexdigest() != HOLD_SHA:
        raise ValueError('Exact observed-pose hold configuration required')
    return binding, config


def run_observed_hold(root, *, startup_export, stage_export, installation_export,
                      key, approved=False):
    if approved is not True:
        raise ValueError('Explicit ordinary hold approval required')
    root = Path(root).resolve()
    binding, config = review_observed_hold(root, startup_export=startup_export,
        stage_export=stage_export, installation_export=installation_export)
    exports = root/'runs/wizard-exports'
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({'mode':'observed-pose-ordinary-hold'}, [], attachments={
        'hold-launch-binding.json':canonical(binding),
        'hold-launch-configuration.json':canonical(config)})
    ident = Path(saved['path']).name
    for name, expected in (('binding',binding),('configuration',config)):
        retained, _ = _read(exports, ident, f'attachment-hold-launch-{name}.json')
        if canonical(retained) != canonical(expected):
            raise ValueError('Hold intent export differs; no command sent')
    result = run_first_hold(exports, configuration=config,expected_boot=binding['expected_boot'],
        key=key,address=binding['address'],authorized_powered_hold=True)
    return dict(binding_export_id=ident,observation=result)
