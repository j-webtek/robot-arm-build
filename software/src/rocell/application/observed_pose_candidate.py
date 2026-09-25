"""Public, evidence-linked pose/settings proposal; no device or private staging.

Neither sampled stability nor these register windows establish physical clearance.
The installed policy stays untouched until separately reviewed provisioning.
"""
import copy
import hashlib
import json
from pathlib import Path

from .first_motion_contract import canonical
from .held_pair_settings import encode_pair_settings
from .pose_observation_export import replay_pose_observation
from .product_ghost_export_review import _read
from .r10_provisioned_evidence import POLICY
from .wizard_diagnostic_export import WizardDiagnosticExporter


def draft_settings(previous, assessment):
    """Derive narrow admission windows, retaining the original elbow envelope."""
    if hashlib.sha256(canonical(previous)).hexdigest() != POLICY:
        raise ValueError('Reviewed predecessor policy required')
    if (assessment.get('origin') != 'DEVICE_CAPTURE' or
            assessment.get('category') != 'STABLE_SAMPLED_POSE'):
        raise ValueError('Replayed stable device evidence required')
    rows = assessment['joints']
    if [r['servo_id'] for r in rows] != list(range(11, 18)):
        raise ValueError('Seven ordered joint observations required')
    candidate = copy.deepcopy(previous)
    candidate['command_id'] = 'observed-pose-elbow-hold-v1'
    policy = candidate['hold_policy']
    # This test uses an already enabled elbow, never enables passive neighbors.
    # Explicit-enable was permitted in the predecessor; tighten that permission.
    policy['permit_explicit_enable'] = 0
    for i, row in enumerate(rows):
        position = row['last_position']
        if (type(position) is not int or not 2 <= position <= 4093 or
                row['controls_unchanged'] is not True or row['position_span'] > 2):
            raise ValueError('Valid stable joint position required')
        if i == 3:
            low, high = policy['joints'][i]
            if row['torque'] != 1 or not low <= position <= position + 10 <= high:
                raise ValueError('Enabled elbow and unmodified +10 path must fit')
        else:
            if row['torque'] != 0:
                raise ValueError('Unexpected neighbor torque state')
            policy['joints'][i] = [position - 2, position + 2]
    pair = json.loads(encode_pair_settings(
        forward_command_id='observed-pose-plus10-forward',
        return_command_id='observed-pose-plus10-return', offset_counts=10))
    return candidate, pair


def _build_report(software_root, pose_export):
    root = Path(software_root).resolve()
    exports = root / 'runs/wizard-exports'
    replay = replay_pose_observation(exports, pose_export)
    previous = json.loads((root / 'docs/hold-r7-supported-pose-draft.json').read_bytes())
    hold, pair = draft_settings(previous, replay['assessment'])
    return dict(schema='rocell.observed_pose_candidate.v1', source_export=pose_export,
        source_raw_sha256=replay['raw_bundle_sha256'], previous_hold_sha256=POLICY,
        hold_settings=hold, pair_settings=pair,
        hold_sha256=hashlib.sha256(canonical(hold)).hexdigest(),
        pair_sha256=hashlib.sha256(canonical(pair)).hexdigest(),
        hardware_access=False, private_staging_performed=False,
        provisioning_performed=False, motion_authorized=False,
        physical_clearance_verified=False, native_parser_verified=False)


def replay_candidate(software_root, candidate_export):
    """Re-derive the entire public proposal; a valid manifest alone is insufficient."""
    root = Path(software_root).resolve()
    report, digest = _read(root/'runs/wizard-exports', candidate_export,
                          'attachment-observed-pose-candidate.json')
    rebuilt = _build_report(root, report['source_export'])
    if canonical(report) != canonical(rebuilt):
        raise ValueError('Candidate does not reproduce from pose evidence')
    return dict(report=rebuilt, candidate_report_sha256=digest, replay_verified=True)


def export_candidate(software_root, pose_export):
    root = Path(software_root).resolve()
    exports = root/'runs/wizard-exports'
    report = _build_report(root, pose_export)
    exporter = WizardDiagnosticExporter(exports)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'observed-pose-public-draft'}, [], attachments={
        'observed-pose-candidate.json': canonical(report)})
    replay_candidate(root, Path(saved['path']).name)
    return dict(export_path=saved['path'], report=report)
