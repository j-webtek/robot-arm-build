"""Independently decode and assess the native one-step shoulder record."""

from __future__ import annotations

from pathlib import Path

from .first_motion_contract import canonical
from .park_step_plan import REFERENCE_GOALS, REFERENCE_POSITIONS
from .cartesian_export_review import validate_export_id
from .physical_onboarding_durability import read_bounded_regular_file
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from .product_ghost_export_review import _read


DOMAIN = b'RCPARK0001'
RECORD_BYTES = 10 + 16 + 4 + 8 + 1 + 7 * (16 + 7 * 20)


def decode_park_step_record(raw):
    if type(raw) is not bytes or len(raw) != RECORD_BYTES or raw[:10] != DOMAIN:
        raise ValueError('Invalid park-step record framing')
    offset = 10

    def take(count):
        nonlocal offset
        value = raw[offset:offset+count]
        offset += count
        return value

    boot = take(16).hex()
    targets = [int.from_bytes(take(2), 'big') for _ in range(2)]
    sent_us = int.from_bytes(take(8), 'big')
    writes = int.from_bytes(take(1), 'big')
    poses = []
    for _ in range(7):
        started_us = int.from_bytes(take(8), 'big')
        finished_us = int.from_bytes(take(8), 'big')
        joints = []
        for servo_id in range(11, 18):
            position = int.from_bytes(take(2), 'big')
            goal = int.from_bytes(take(2), 'big')
            torque = int.from_bytes(take(1), 'big')
            feedback = take(15)
            joints.append(dict(servo_id=servo_id, position=position, goal=goal,
                               torque=torque, feedback=feedback))
        poses.append(dict(started_us=started_us, finished_us=finished_us,
                          joints=joints))
    if offset != len(raw) or writes != 1 or sent_us == 0:
        raise ValueError('Invalid park-step record body')
    return dict(boot=boot, target_goals=targets, sent_us=sent_us,
                writes_attempted=writes, start=poses[:3], prewrite=poses[3],
                endpoint=poses[4:])


def _pose_valid(pose):
    if (not pose['started_us'] or pose['finished_us'] < pose['started_us'] or
            pose['finished_us'] - pose['started_us'] > 300000):
        raise ValueError('Invalid sample time')
    for joint in pose['joints']:
        if (joint['position'] > 4095 or joint['goal'] > 4095 or
                joint['torque'] != 1 or any(joint['feedback'][i] for i in (2, 3, 10)) or
                int.from_bytes(joint['feedback'][:2], 'little') != joint['position']):
            raise ValueError('Invalid or moving servo feedback')


def _stable(poses, *, after_us=0):
    if (poses[0]['started_us'] <= after_us or
            not 200000 <= poses[-1]['finished_us'] - poses[0]['started_us'] <= 1500000):
        raise ValueError('Invalid sample window')
    for index, pose in enumerate(poses):
        _pose_valid(pose)
        if index and pose['started_us'] - poses[index-1]['finished_us'] < 100000:
            raise ValueError('Samples insufficiently spaced')
        for joint, first in zip(pose['joints'], poses[0]['joints']):
            if (joint['goal'] != first['goal'] or
                    abs(joint['position'] - first['position']) > 1):
                raise ValueError('Unstable sampled pose')


def assess_park_step_record(raw, *, expected_boot, plan):
    """Assess sampled joint action; never infer physical clearance or park."""
    record = decode_park_step_record(raw)
    if record['boot'] != expected_boot or plan.get('schema') != 'rocell.first_park_step_plan.v1':
        raise ValueError('Park-step identity mismatch')
    if (plan.get('target_goals') != record['target_goals'] or
            plan.get('target_goals') != [2377, 1737] or
            plan.get('source_goals') != list(REFERENCE_GOALS)):
        raise ValueError('Unexpected first-step target')
    before, prewrite, after = record['start'], record['prewrite'], record['endpoint']
    sent = record['sent_us']
    _stable(before)
    _pose_valid(prewrite)
    if (prewrite['started_us'] <= before[-1]['finished_us'] or
            sent < prewrite['finished_us'] or sent-prewrite['finished_us'] > 100000 or
            after[0]['started_us'] <= sent or after[-1]['finished_us']-sent > 8000000):
        raise ValueError('Prewrite or endpoint not bound to send time')
    _stable(after, after_us=sent)
    initial = before[-1]['joints']
    for index, (joint, expected_goal, expected_position) in enumerate(zip(
            initial, REFERENCE_GOALS, REFERENCE_POSITIONS)):
        if (joint['goal'] != expected_goal or
                abs(joint['position']-expected_position) > 2):
            raise ValueError('Start differs from reference')
        immediate = prewrite['joints'][index]
        if (immediate['goal'] != joint['goal'] or
                abs(immediate['position']-joint['position']) > 1):
            raise ValueError('Prewrite changed')
    for sample in after:
        for index, (joint, source) in enumerate(zip(sample['joints'], initial)):
            if index in (1, 2):
                selected = index-1
                expected_target = record['target_goals'][selected]
                sign = -1 if index == 1 else 1
                travel = sign*(joint['position']-source['position'])
                if (joint['goal'] != expected_target or
                        not -1 <= travel <= 14):
                    raise ValueError('Selected joint exceeded envelope')
            elif (joint['goal'] != source['goal'] or
                  abs(joint['position']-source['position']) > 2):
                raise ValueError('Neighbor changed')
    final = after[-1]['joints']
    travel = [initial[1]['position']-final[1]['position'],
              final[2]['position']-initial[2]['position']]
    if min(travel) < 2:
        raise ValueError('No clear paired response')
    endpoint_error = [final[1]['position']-record['target_goals'][0],
                      final[2]['position']-record['target_goals'][1]]
    return dict(schema='rocell.park_step_assessment.v1', boot=expected_boot,
                status='MEASURED_FIRST_STEP', target_goals=record['target_goals'],
                actual_position_delta=[-travel[0], travel[1]],
                endpoint_error_counts=endpoint_error,
                all_goals_read_back=True, physical_rise_proven=False,
                physical_park_verified=False, continuation_authorized=False)


def export_park_step_record(root, raw, *, expected_boot, plan,
                            mode='park-step-offline-fixture'):
    assessment = assess_park_step_record(raw, expected_boot=expected_boot, plan=plan)
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': mode}, [], attachments={
        'park-step.hex.txt': raw.hex().encode('ascii'),
        'park-step-assessment.json': canonical(assessment),
    })
    folder = Path(saved['path'])
    if replay_park_step_record(root, folder.name, expected_boot=expected_boot,
                               plan=plan) != assessment:
        raise ValueError('Park-step export failed replay')
    return saved['path']


def replay_park_step_record(root, export_id, *, expected_boot, plan):
    folder = Path(root).resolve() / validate_export_id(export_id)
    if not verify_export(folder)['valid']:
        raise ValueError('Invalid park-step export')
    encoded = read_bounded_regular_file(folder/'attachment-park-step.hex.txt',
                                        maximum_bytes=2*RECORD_BYTES)
    if len(encoded) != 2*RECORD_BYTES:
        raise ValueError('Invalid park-step hex length')
    try:
        raw = bytes.fromhex(encoded.decode('ascii'))
    except (UnicodeError, ValueError) as error:
        raise ValueError('Invalid park-step hex') from error
    if raw.hex().encode('ascii') != encoded:
        raise ValueError('Noncanonical park-step hex')
    assessment, _ = _read(Path(root).resolve(), export_id,
                          'attachment-park-step-assessment.json')
    calculated = assess_park_step_record(raw, expected_boot=expected_boot, plan=plan)
    if canonical(assessment) != canonical(calculated):
        raise ValueError('Park-step assessment changed')
    return calculated
