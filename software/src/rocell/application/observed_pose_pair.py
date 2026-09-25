"""Receipt-bound preparation and execution of the exact +10/return experiment.

Receipt review is not live-motion authorization. A subsequent runner must still
acquire current same-boot evidence and use the existing one-shot pair protocol.
Never route this experiment through the legacy +/-6 policy by relaxing its pins.
"""
import hashlib
from pathlib import Path

from .first_motion_contract import canonical
from .held_pair_preparation import replay_held_pair_preparation
from .observed_pose_installation import review_observed_startup
from .observed_pose_recovery import HOLD_SHA, PAIR_SHA
from .held_pair_preparation import prepare_held_pair
from .held_pair_trial import run_admitted_pair
from .hold_transport_export import capture_hold_transport
from .hold_transport_snapshot import HoldHTTPReader
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter


def review_observed_pair(software_root, *, startup_export, stage_export,
                         installation_export, preparation_export):
    """Bind replayed ordinary-hold preparation to installed settings and startup."""
    root = Path(software_root).resolve()
    exports = root / 'runs/wizard-exports'
    binding = review_observed_startup(root, startup_export=startup_export,
        stage_export=stage_export, installation_export=installation_export)
    source = replay_held_pair_preparation(exports, preparation_export)
    prep = source['preparation']
    plan = prep['pair_plan']
    config = dict(schema='rocell.controller_hold.v1',
        command_id='observed-pose-elbow-hold-v1', start_port=8081,
        hold_policy=prep['policy'])
    # Derive the complete installed pair document, not merely the offset.
    from .held_pair_settings import encode_pair_settings
    pair = encode_pair_settings(forward_command_id=plan['forward_command_id'],
        return_command_id=plan['return_command_id'], offset_counts=plan['offset_counts'],
        tolerance_counts=plan['tolerance_counts'])
    if (plan['boot_id'] != binding['expected_boot'] or
            hashlib.sha256(canonical(config)).hexdigest() != HOLD_SHA or
            hashlib.sha256(pair).hexdigest() != PAIR_SHA):
        raise ValueError('Observed pair boot/policy/experiment mismatch')
    anchor = prep['historical_anchor']
    low, high = prep['policy']['joints'][3]
    if type(anchor) is not int or not low <= anchor <= anchor + 10 <= high:
        raise ValueError('Observed +10 path does not fit; no clipping or recentering')
    boot = binding['expected_boot']
    for name in ('supported-recovery-trial-' + boot,
                 'held-pair-trial-' + hashlib.sha256(boot.encode('ascii')).hexdigest()):
        if (exports / (name + '.json')).exists():
            raise ValueError('Recovery or pair consumed this boot; no automatic restart')
    return binding, source


def prepare_observed_pair(software_root, *, startup_export, stage_export,
                          installation_export, hold_export):
    """Prepare from a verified ordinary hold, never a recovery handoff."""
    root = Path(software_root).resolve()
    # Reject missing deployment evidence before producing a preparation export.
    review_observed_startup(root, startup_export=startup_export,
        stage_export=stage_export, installation_export=installation_export)
    prepared = prepare_held_pair(root/'runs/wizard-exports', hold_export,
        forward_command_id='observed-pose-plus10-forward',
        return_command_id='observed-pose-plus10-return',offset_counts=10,tolerance_counts=2)
    review_observed_pair(root, startup_export=startup_export,stage_export=stage_export,
        installation_export=installation_export,
        preparation_export=Path(prepared['export_path']).name)
    return prepared


def run_observed_pair(software_root, *, startup_export, stage_export,
                      installation_export, preparation_export, key, approved=False):
    """One explicit trial; shared executor gates return on exported arrival.

    No install, restart, recovery or retry is performed here. The native handoff
    and executor's one-use claim remain authoritative at command time.
    """
    if approved is not True:
        raise ValueError('Explicit bounded powered pair approval required')
    root = Path(software_root).resolve(); exports = root/'runs/wizard-exports'
    binding, source = review_observed_pair(root, startup_export=startup_export,
        stage_export=stage_export, installation_export=installation_export,
        preparation_export=preparation_export)
    current = capture_hold_transport(exports, HoldHTTPReader(binding['address']),
                                      expected_boot=binding['expected_boot'])
    status = current['summary'].get('status', {})
    if (current['summary']['category'] != 'TRANSPORT_CAPTURED' or
            status.get('state') != 'CAPTURED' or status.get('storage_fault') is not False):
        raise ValueError('Fresh same-boot captured ordinary hold required')
    admission = dict(binding=binding, preparation_export_id=preparation_export,
        preparation_sha256=source['preparation_sha256'],
        current_hold_export_id=Path(current['export_path']).name,
        retry_allowed=False, physical_tip_accuracy_verified=False)
    exporter = WizardDiagnosticExporter(exports); exporter.prepare(create=True)
    saved = exporter.export({'mode':'observed-pose-pair-admission'}, [],
        attachments={'pair-admission.json':canonical(admission)})
    retained, _ = _read(exports, Path(saved['path']).name, 'attachment-pair-admission.json')
    if canonical(retained) != canonical(admission):
        raise ValueError('Pair admission export changed; no command sent')
    result = run_admitted_pair(exports, preparation_export, address=binding['address'],
                               key=key, approved=True)
    return dict(admission_export_id=Path(saved['path']).name, trial=result)
