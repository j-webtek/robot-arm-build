"""Freeze a measured encoder checkpoint; never label it physical park/home."""
import hashlib
from pathlib import Path

from .fixed_pair_reanchor_record import (
    decode_fixed_pair_reanchor_record, replay_fixed_pair_reanchor_fixture,
)
from .physical_onboarding_durability import read_bounded_regular_file
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from .first_motion_contract import canonical


def freeze_standard_start_reference(export_root, record_export_id, *, boot, plan):
    root = Path(export_root).resolve()
    assessment = replay_fixed_pair_reanchor_fixture(root, record_export_id,
                                                     expected_boot=boot, plan=plan)
    if assessment['result']['status'] != 'GOAL_AND_ENDPOINT_VERIFIED':
        raise ValueError('Verified re-anchor endpoint required')
    source = root / record_export_id / 'attachment-fixed-pair-reanchor.hex.txt'
    hex_bytes = read_bounded_regular_file(source, maximum_bytes=2254)
    raw = bytes.fromhex(hex_bytes.decode('ascii'))
    record = decode_fixed_pair_reanchor_record(raw)
    final = record['endpoint'][-1]
    joints = [dict(servo_id=j['servo_id'], goal=j['goal'], position=j['position'],
                   torque=j['torque']) for j in final['joints']]
    reference = dict(schema='rocell.standard_start_encoder_reference.v1',
                     label='REFERENCE_A', boot=boot,
                     source_export_id=record_export_id,
                     source_record_sha256=hashlib.sha256(raw).hexdigest(),
                     sampled_at_us=final['finished_us'], joints=joints,
                     encoder_reference_verified=True,
                     physical_tip_position_measured=False,
                     physical_park_verified=False,
                     safe_to_replay_without_fresh_capture=False)
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'standard-start-encoder-reference'}, [],
                            attachments={'standard-start-reference.json': canonical(reference)})
    if not verify_export(Path(saved['path']))['valid']:
        raise ValueError('Reference export failed')
    return saved['path'], reference
