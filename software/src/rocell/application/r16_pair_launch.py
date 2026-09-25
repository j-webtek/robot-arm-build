"""Ordinary r16 hold-to-pair binding; no recovery handoff or restart."""
import hashlib
from pathlib import Path
from .first_motion_contract import canonical
from .held_pair_preparation import prepare_held_pair, replay_held_pair_preparation
from .held_pair_trial import run_admitted_pair
from .hold_transport_export import capture_hold_transport
from .hold_transport_snapshot import HoldHTTPReader
from .product_ghost_export_review import _read
from .r10_provisioned_evidence import POLICY
from .supported_recovery_installation import review_recovery_startup
from .wizard_diagnostic_export import WizardDiagnosticExporter


def review_r16_pair(software_root, startup_export_id, preparation_id, negative_installation_id=None):
    root = Path(software_root).resolve()
    exports = root / 'runs/wizard-exports'
    binding = review_recovery_startup(root, startup_export_id)
    offset=6
    if negative_installation_id is not None:
        from .negative_pair_provisioning import review_negative_installation
        binding['negative_settings']=review_negative_installation(root,negative_installation_id)
        offset=-6
    source = replay_held_pair_preparation(exports, preparation_id)
    prep = source['preparation']
    plan = prep['pair_plan']
    boot = binding['expected_boot']
    config = dict(schema='rocell.controller_hold.v1',
        command_id='r7-supported-hold-20260918', start_port=8081, hold_policy=prep['policy'])
    if (plan['boot_id'] != boot or
        plan['forward_command_id'] != 'r10-elbow-forward' or
        plan['return_command_id'] != 'r10-elbow-return' or
        type(plan['offset_counts']) is not int or plan['offset_counts'] != offset or
        plan['tolerance_counts'] != 2 or
        hashlib.sha256(canonical(config)).hexdigest() != POLICY):
        raise ValueError('Pair differs from reviewed r16 boot/policy/experiment')
    # Matched-direction coverage must fit without clipping either side.
    anchor = prep['historical_anchor']
    low, high = prep['policy']['joints'][3]
    if not low <= anchor-6 <= anchor+6 <= high:
        raise ValueError('Matched-direction targets do not fit the reviewed envelope')
    for name in ('supported-recovery-trial-' + boot,
                 'held-pair-trial-' + hashlib.sha256(boot.encode('ascii')).hexdigest()):
        if (exports / (name + '.json')).exists():
            raise ValueError('Recovery or pair consumed this boot; no automatic restart')
    return binding, source


def prepare_r16_pair(software_root, *, startup_export_id, hold_export_id, offset_counts=6, negative_installation_id=None):
    if type(offset_counts) is not int or offset_counts != (-6 if negative_installation_id else 6):
        raise ValueError('Offset must match installed settings receipt')
    root = Path(software_root).resolve()
    prepared = prepare_held_pair(root / 'runs/wizard-exports', hold_export_id,
        forward_command_id='r10-elbow-forward', return_command_id='r10-elbow-return',
        offset_counts=offset_counts, tolerance_counts=2)
    review_r16_pair(root, startup_export_id, Path(prepared['export_path']).name,negative_installation_id)
    return prepared


def run_r16_pair(software_root, *, startup_export_id, preparation_id, key, approved=False, negative_installation_id=None):
    if approved is not True:
        raise ValueError('Explicit bounded powered pair approval required')
    root = Path(software_root).resolve()
    exports = root / 'runs/wizard-exports'
    binding, source = review_r16_pair(root, startup_export_id, preparation_id,negative_installation_id)
    current = capture_hold_transport(exports, HoldHTTPReader(binding['address']),
                                      expected_boot=binding['expected_boot'])
    status = current['summary'].get('status', {})
    if (current['summary']['category'] != 'TRANSPORT_CAPTURED' or
        status.get('state') != 'CAPTURED' or status.get('storage_fault') is not False):
        raise ValueError('Fresh same-boot captured ordinary hold required')
    admission = dict(binding=binding, preparation_export_id=preparation_id,
        preparation_sha256=source['preparation_sha256'],
        current_hold_export_id=Path(current['export_path']).name,
        retry_allowed=False, physical_tip_accuracy_verified=False)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'r16-pair-admission'}, [],
        attachments={'pair-admission.json': canonical(admission)})
    retained, _ = _read(exports, Path(saved['path']).name, 'attachment-pair-admission.json')
    if canonical(retained) != canonical(admission):
        raise ValueError('Pair admission export changed; no command sent')
    result = run_admitted_pair(exports, preparation_id, address=binding['address'],
                               key=key, approved=True)
    return dict(admission_export_id=Path(saved['path']).name, trial=result)
