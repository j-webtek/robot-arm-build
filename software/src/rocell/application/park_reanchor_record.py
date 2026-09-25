"""Decode the fixed return record without turning a fault into success."""

from __future__ import annotations

from pathlib import Path

from .cartesian_export_review import validate_export_id
from .first_motion_contract import canonical
from .park_reanchor_plan import OFFSET_GOALS, OFFSET_POSITIONS
from .park_step_plan import REFERENCE_GOALS, REFERENCE_POSITIONS
from .visible_shoulder_step_plan import (
    EXPECTED_POSITIONS as VISIBLE_EXPECTED_POSITIONS,
    SOURCE_GOALS as VISIBLE_SOURCE_GOALS,
    SOURCE_POSITIONS as VISIBLE_SOURCE_POSITIONS,
    TARGET_GOALS as VISIBLE_TARGET_GOALS,
)
from .park_step_record import _pose_valid, _stable
from .physical_onboarding_durability import read_bounded_regular_file
from .product_ghost_export_review import _read
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export


DOMAIN = b'RCRTN00001'
RECORD_BYTES = 10 + 16 + 1 + 1 + 8 + 1 + 7 * (16 + 7 * 20)
OUTCOMES = {
    1: 'SETTLED', 2: 'TIMEOUT', 3: 'OUT_OF_BOUNDS',
    4: 'FEEDBACK_FAILED', 5: 'EVIDENCE_FAILED',
    6: 'ADMISSION_LOST', 7: 'CLOCK_FAILED', 8: 'WRITE_UNCERTAIN',
}


def _profile(plan):
    """Return frozen decoder values for one reviewed fixed-target plan."""
    if (plan.get('schema') == 'rocell.park_reanchor_plan.v1' and
            plan.get('target_goals') == [2389, 1725] and
            plan.get('source_goals') == list(OFFSET_GOALS)):
        return (OFFSET_GOALS, OFFSET_POSITIONS,
                (REFERENCE_GOALS[1], REFERENCE_GOALS[2]),
                (REFERENCE_POSITIONS[1], REFERENCE_POSITIONS[2]),
                8, 'MEASURED_RETURN')
    if (plan.get('schema') == 'rocell.visible_shoulder_step_plan.v1' and
            plan.get('target_goals') == list(VISIBLE_TARGET_GOALS) and
            plan.get('source_goals') == list(VISIBLE_SOURCE_GOALS) and
            plan.get('expected_encoder_positions') == list(VISIBLE_EXPECTED_POSITIONS)):
        return (VISIBLE_SOURCE_GOALS, VISIBLE_SOURCE_POSITIONS,
                VISIBLE_TARGET_GOALS, VISIBLE_EXPECTED_POSITIONS,
                28, 'MEASURED_VISIBLE_STEP')
    raise ValueError('Park-return identity or plan mismatch')


def decode_park_reanchor_record(raw):
    if type(raw) is not bytes or len(raw) != RECORD_BYTES or raw[:10] != DOMAIN:
        raise ValueError('Invalid park-return framing')
    offset = 10

    def take(count):
        nonlocal offset
        value = raw[offset:offset + count]
        offset += count
        return value

    boot = take(16).hex()
    outcome = int.from_bytes(take(1), 'big')
    sample_count = int.from_bytes(take(1), 'big')
    sent_us = int.from_bytes(take(8), 'big')
    writes = int.from_bytes(take(1), 'big')
    poses = []
    for _ in range(7):
        started_us = int.from_bytes(take(8), 'big')
        finished_us = int.from_bytes(take(8), 'big')
        joints = []
        for servo_id in range(11, 18):
            joints.append({
                'servo_id': servo_id,
                'position': int.from_bytes(take(2), 'big'),
                'goal': int.from_bytes(take(2), 'big'),
                'torque': int.from_bytes(take(1), 'big'),
                'feedback': take(15),
            })
        poses.append({'started_us': started_us, 'finished_us': finished_us,
                      'joints': joints})
    if (offset != len(raw) or outcome not in OUTCOMES or writes != 1 or
            not sent_us or sample_count > 3 or
            (outcome == 1 and sample_count != 3)):
        raise ValueError('Invalid park-return record body')
    # A missing postwrite slot must be all zero; it is not an observation.
    blank = {'started_us': 0, 'finished_us': 0,
             'joints': [{'servo_id': i, 'position': 0, 'goal': 0, 'torque': 0,
                         'feedback': bytes(15)} for i in range(11, 18)]}
    if any(pose != blank for pose in poses[4 + sample_count:]):
        raise ValueError('Nonblank missing postwrite sample')
    return {
        'boot': boot, 'outcome': OUTCOMES[outcome],
        'postwrite_samples': sample_count, 'sent_us': sent_us,
        'writes_attempted': writes, 'start': poses[:3],
        'prewrite': poses[3], 'endpoint': poses[4:4 + sample_count],
    }


def assess_park_reanchor_record(raw, *, expected_boot, plan):
    record = decode_park_reanchor_record(raw)
    if record['boot'] != expected_boot:
        raise ValueError('Park-return identity or plan mismatch')
    source_goals, source_positions, target_goals, expected_positions, maximum_travel, success_status = _profile(plan)
    before, prewrite, after = record['start'], record['prewrite'], record['endpoint']
    sent = record['sent_us']
    _stable(before)
    _pose_valid(prewrite)
    if (prewrite['started_us'] <= before[-1]['finished_us'] or
            sent < prewrite['finished_us'] or sent - prewrite['finished_us'] > 100000):
        raise ValueError('Invalid prewrite timing')
    for index, (joint, goal, position) in enumerate(zip(
            before[-1]['joints'], source_goals, source_positions)):
        tolerance = 1 if index in (1, 2) else 2
        immediate = prewrite['joints'][index]
        if (joint['goal'] != goal or abs(joint['position'] - position) > tolerance or
                immediate['goal'] != joint['goal'] or
                abs(immediate['position'] - joint['position']) > 1):
            raise ValueError('Start or prewrite changed')
    if record['outcome'] != 'SETTLED':
        return {
            'schema': 'rocell.park_reanchor_assessment.v1',
            'boot': expected_boot, 'status': 'FAULT_RECORDED',
            'fault': record['outcome'],
            'postwrite_samples': record['postwrite_samples'],
            'writes_attempted': 1, 'reference_pose_verified': False,
            'physical_clearance_proven': False, 'continuation_authorized': False,
        }
    _stable(after, after_us=sent)
    if after[-1]['finished_us'] - sent > 8000000:
        raise ValueError('Settled endpoint exceeded deadline')
    initial = before[-1]['joints']
    for sample in after:
        for index, (joint, source) in enumerate(zip(sample['joints'], initial)):
            if index in (1, 2):
                target = target_goals[index - 1]
                travel = (1 if index == 1 else -1) * (
                    joint['position'] - source['position'])
                if joint['goal'] != target or not -1 <= travel <= maximum_travel:
                    raise ValueError('Selected joint exceeded return envelope')
            elif (joint['goal'] != source['goal'] or
                  abs(joint['position'] - source['position']) > 2):
                raise ValueError('Neighbor changed during return')
    final = after[-1]['joints']
    endpoint_tolerance = 2 if success_status == 'MEASURED_RETURN' else 3
    if any(abs(final[index]['position'] - expected_positions[index - 1]) > endpoint_tolerance or
           abs(final[index]['position'] - target_goals[index - 1]) > endpoint_tolerance
           for index in (1, 2)):
        raise ValueError('Return did not settle at reference')
    return {
        'schema': 'rocell.park_reanchor_assessment.v1',
        'boot': expected_boot, 'status': success_status,
        'actual_position_delta': [final[i]['position'] - initial[i]['position']
                                  for i in (1, 2)],
        'endpoint_error_counts': [final[i]['position'] - target_goals[i - 1]
                                  for i in (1, 2)],
        'writes_attempted': 1, 'reference_pose_verified': True,
        'physical_clearance_proven': False, 'continuation_authorized': False,
    }


def export_park_reanchor_record(root, raw, *, expected_boot, plan,
                                mode='park-return-offline-fixture'):
    """Persist the raw result and independently replay it before returning."""
    assessment = assess_park_reanchor_record(raw, expected_boot=expected_boot,
                                             plan=plan)
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': mode}, [], attachments={
        'park-return.hex.txt': raw.hex().encode('ascii'),
        'park-return-assessment.json': canonical(assessment),
    })
    folder = Path(saved['path'])
    if replay_park_reanchor_record(root, folder.name, expected_boot=expected_boot,
                                   plan=plan) != assessment:
        raise ValueError('Park-return export failed replay')
    return saved['path']


def replay_park_reanchor_record(root, export_id, *, expected_boot, plan):
    folder = Path(root).resolve() / validate_export_id(export_id)
    if not verify_export(folder)['valid']:
        raise ValueError('Invalid park-return export')
    encoded = read_bounded_regular_file(folder / 'attachment-park-return.hex.txt',
                                        maximum_bytes=2 * RECORD_BYTES)
    if len(encoded) != 2 * RECORD_BYTES:
        raise ValueError('Invalid park-return hex length')
    try:
        raw = bytes.fromhex(encoded.decode('ascii'))
    except (UnicodeError, ValueError) as error:
        raise ValueError('Invalid park-return hex') from error
    if raw.hex().encode('ascii') != encoded:
        raise ValueError('Noncanonical park-return hex')
    assessment, _ = _read(Path(root).resolve(), export_id,
                          'attachment-park-return-assessment.json')
    calculated = assess_park_reanchor_record(raw, expected_boot=expected_boot,
                                             plan=plan)
    if canonical(assessment) != canonical(calculated):
        raise ValueError('Park-return assessment changed')
    return calculated
