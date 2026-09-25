"""Decode and independently assess retained one-write native evidence.

The record does not authenticate its sender. A future transport must verify the
response and bind the boot ID before using this assessment for a receipt.
"""
from __future__ import annotations

from pathlib import Path

from .first_motion_contract import canonical
from .fixed_pair_reanchor import verify_reanchor_endpoint
from .cartesian_export_review import validate_export_id
from .physical_onboarding_durability import read_bounded_regular_file
from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export
from .wizard_diagnostic_coordinator import decode_diagnostic_json


DOMAIN = b'RCRANCH001'
RECORD_BYTES = 10 + 16 + 8 + 1 + 7 * (16 + 7 * 20)


def decode_fixed_pair_reanchor_record(raw):
    if type(raw) is not bytes or len(raw) != RECORD_BYTES or raw[:10] != DOMAIN:
        raise ValueError('Invalid fixed reanchor record framing')
    offset = 10

    def take(count):
        nonlocal offset
        value = raw[offset:offset+count]
        offset += count
        return value

    boot = take(16).hex()
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
                               torque=torque, feedback_hex=feedback.hex(),
                               moving=any(feedback[i] for i in (2, 3, 10))))
        poses.append(dict(started_us=started_us, finished_us=finished_us, joints=joints))
    if offset != len(raw) or writes != 1 or not sent_us:
        raise ValueError('Invalid fixed reanchor record body')
    return dict(schema='rocell.fixed_pair_reanchor_record.v1', boot=boot,
                sent_us=sent_us, writes_attempted=writes,
                start=poses[:3], prewrite=poses[3], endpoint=poses[4:])


def _validate_pose(pose):
    if (not pose['started_us'] or pose['finished_us'] < pose['started_us'] or
            pose['finished_us']-pose['started_us'] > 300000):
        raise ValueError('Invalid sample timestamp')
    for joint in pose['joints']:
        if (joint['position'] > 4095 or joint['goal'] > 4095 or
                joint['torque'] != 1 or joint['moving'] or
                int.from_bytes(bytes.fromhex(joint['feedback_hex'])[:2], 'little') != joint['position']):
            raise ValueError('Invalid or moving servo feedback')


def _summary(poses):
    first, last = poses[0], poses[-1]
    if (last['finished_us']-first['started_us'] < 200000 or
            last['finished_us']-first['started_us'] > 1500000):
        raise ValueError('Capture duration outside bounds')
    for index, pose in enumerate(poses):
        _validate_pose(pose)
        if index and pose['started_us']-poses[index-1]['finished_us'] < 100000:
            raise ValueError('Sample spacing too short')
    joints = []
    for i in range(7):
        rows = [pose['joints'][i] for pose in poses]
        span = max(row['position'] for row in rows)-min(row['position'] for row in rows)
        unchanged = all((row['goal'], row['torque']) ==
                        (rows[0]['goal'], rows[0]['torque']) for row in rows)
        joints.append(dict(servo_id=11+i, last_goal=rows[-1]['goal'],
                           last_position=rows[-1]['position'], torque=rows[-1]['torque'],
                           position_span=span, controls_unchanged=unchanged))
    return dict(category='STABLE_SAMPLED_POSE', origin='DEVICE_CAPTURE', joints=joints)


def assess_fixed_pair_reanchor_record(raw, *, expected_boot, plan):
    record = decode_fixed_pair_reanchor_record(raw)
    if record['boot'] != expected_boot:
        raise ValueError('Reanchor boot mismatch')
    before, prewrite, after = record['start'], record['prewrite'], record['endpoint']
    sent = record['sent_us']
    if (sent < before[-1]['finished_us'] or sent-before[-1]['finished_us'] > 1000000 or
            prewrite['started_us'] <= before[-1]['finished_us'] or
            sent < prewrite['finished_us'] or sent-prewrite['finished_us'] > 100000 or
            after[0]['started_us'] <= sent or
            after[-1]['finished_us']-sent > 8000000):
        raise ValueError('Reanchor samples not bound to write time')
    baseline = _summary(before)
    endpoint = _summary(after)
    # The immediate prewrite reading is also required, not merely the earlier
    # three-sample reference. Its controls and position must match that reference.
    _validate_pose(prewrite)
    for i in range(7):
        first = baseline['joints'][i]
        current = prewrite['joints'][i]
        if (current['goal'] != first['last_goal'] or current['torque'] != 1 or
                current['moving'] or
                abs(current['position']-first['last_position']) > 1):
            raise ValueError('Prewrite reading changed')
    result = verify_reanchor_endpoint(plan, baseline, endpoint)
    return dict(schema='rocell.fixed_pair_reanchor_assessment.v1', boot=expected_boot,
                writes_attempted=1, result=result, physical_tip_accuracy_verified=False,
                movement_authorized=False)


def export_fixed_pair_reanchor_fixture(root, raw, *, expected_boot, plan):
    """Retain/replay offline fixture bytes; never attest a live controller."""
    assessment = assess_fixed_pair_reanchor_record(raw, expected_boot=expected_boot, plan=plan)
    root = Path(root).resolve()
    exporter = WizardDiagnosticExporter(root)
    exporter.prepare(create=True)
    saved = exporter.export({'mode': 'fixed-pair-reanchor-offline-fixture'}, [], attachments={
        'fixed-pair-reanchor.hex.txt': raw.hex().encode('ascii'),
        'fixed-pair-reanchor-assessment.json': canonical(assessment),
    })
    if replay_fixed_pair_reanchor_fixture(root, Path(saved['path']).name,
                                          expected_boot=expected_boot, plan=plan) != assessment:
        raise ValueError('Reanchor fixture replay differs')
    return saved['path']


def replay_fixed_pair_reanchor_fixture(root, export_id, *, expected_boot, plan):
    folder = Path(root).resolve()/validate_export_id(export_id)
    verified = verify_export(folder)
    if not verified['valid']:
        raise ValueError('Invalid reanchor fixture export')
    names = {item['name'] for item in verified['files']}
    if not {'attachment-fixed-pair-reanchor.hex.txt',
            'attachment-fixed-pair-reanchor-assessment.json'} <= names:
        raise ValueError('Missing reanchor fixture attachments')
    hex_bytes = read_bounded_regular_file(folder/'attachment-fixed-pair-reanchor.hex.txt',
                                          maximum_bytes=2*RECORD_BYTES)
    if len(hex_bytes) != 2*RECORD_BYTES:
        raise ValueError('Invalid reanchor hex length')
    try:
        raw = bytes.fromhex(hex_bytes.decode('ascii'))
    except (UnicodeError, ValueError) as error:
        raise ValueError('Invalid reanchor hex bytes') from error
    if raw.hex().encode('ascii') != hex_bytes:
        raise ValueError('Noncanonical reanchor hex')
    saved = decode_diagnostic_json(read_bounded_regular_file(
        folder/'attachment-fixed-pair-reanchor-assessment.json', maximum_bytes=4095),
        maximum=4095)
    rebuilt = assess_fixed_pair_reanchor_record(raw, expected_boot=expected_boot, plan=plan)
    if canonical(saved) != canonical(rebuilt):
        raise ValueError('Reanchor assessment replay differs')
    return rebuilt
