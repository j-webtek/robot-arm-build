"""Strict offline decoder for controller-owned RCCRESULT01 artifacts.

Decoding proves framing consistency, not authenticity or physical accuracy.
No transport, receipt signing or movement is performed here.
"""


def decode_result(raw: bytes) -> dict:
    if type(raw) is not bytes or not 0 < len(raw) <= 11000:
        raise ValueError('Bounded result bytes required')
    magic = b'RCCRESULT01\0'
    if not raw.startswith(magic):
        raise ValueError('Unknown result format')
    offset = len(magic)

    def take(width):
        nonlocal offset
        if offset + width > len(raw):
            raise ValueError('Truncated result')
        value = raw[offset:offset + width]
        offset += width
        return value

    def number(width):
        return int.from_bytes(take(width), 'big')

    leg, legs, budget = number(1), number(1), number(8)
    if not 1 <= legs <= 12 or not 0 <= leg < legs or not 0 < budget <= 60000000:
        raise ValueError('Invalid manifest limits')
    goals = [[number(2), number(2)] for _ in range(legs)]
    bounds = [[number(2), number(2)] for _ in range(7)]
    if any(not 0 <= lo <= hi <= 4095 for lo, hi in bounds):
        raise ValueError('Invalid bounds')
    for index, pair in enumerate(goals):
        if sum(pair) != 4114 or any(not bounds[j+1][0] <= pair[j] <= bounds[j+1][1] for j in range(2)):
            raise ValueError('Invalid paired goal')
        if index and not 1 <= abs(pair[0] - goals[index-1][0]) <= 24:
            raise ValueError('Invalid leg delta')
    outcome, count = number(1), number(1)
    if outcome not in (1, 2, 3, 4) or not 3 <= count <= 64:
        raise ValueError('Invalid outcome or sample count')
    poses = []
    last_finished = 0
    for _ in range(count + 1):
        started, finished = number(8), number(8)
        if not last_finished < started <= finished or finished-started > 300000:
            raise ValueError('Invalid sample timestamps')
        joints = []
        for joint in range(7):
            position, goal, torque = number(2), number(2), number(1)
            feedback = take(15)
            if (not bounds[joint][0] <= position <= bounds[joint][1]
                    or goal > 4095 or torque != 1
                    or int.from_bytes(feedback[:2], 'little') != position):
                raise ValueError('Invalid joint evidence')
            joints.append(dict(id=joint+11, position=position, goal=goal,
                               torque=torque, feedback_hex=feedback.hex()))
        poses.append(dict(started_us=started, finished_us=finished, joints=joints))
        last_finished = finished
    if offset != len(raw):
        raise ValueError('Trailing result bytes')
    return dict(schema='rocell.characterization_result.v1', leg=leg, legs=legs,
                maximum_us=budget, goals=goals, bounds=bounds,
                outcome={1:'SETTLED_ACCURATE',2:'SETTLED_MISS',3:'STOP',4:'SETTLED_SMALL_RESPONSE'}[outcome],
                baseline=poses[0], observations=poses[1:],
                physical_accuracy_verified=False)


def export_result(root, raw: bytes) -> dict:
    """Persist a readable result and lossless raw hex; never issue motion authority."""
    from pathlib import Path
    import json
    from .wizard_diagnostic_export import WizardDiagnosticExporter, verify_export

    decoded = decode_result(raw)
    exporter = WizardDiagnosticExporter(Path(root).resolve())
    exporter.prepare(create=True)
    decoded['motion_summary'] = motion_summary(decoded)
    saved = exporter.export({'mode': 'characterization-result-review'}, [], attachments={
        'characterization-result.json': json.dumps(decoded, indent=2).encode('utf-8'),
        'characterization-result.hex.txt': raw.hex().encode('ascii'),
    })
    path = Path(saved['path'])
    if not verify_export(path)['valid']:
        raise ValueError('Export verification failed')
    retained = (path / 'attachment-characterization-result.hex.txt').read_text().strip()
    if retained != raw.hex():
        raise ValueError('Export bytes differ')
    return dict(export_path=str(path), leg=decoded['leg'], outcome=decoded['outcome'],
                movement_authorized=False, receipt_issued=False)


def motion_summary(record):
    """Sampled peaks are lower bounds: movement between acquisitions may be missed."""
    rows=[]
    for index in (1,2):
        initial=record['baseline']['joints'][index]['position']
        deltas=[p['joints'][index]['position']-initial for p in record['observations']]
        rows.append(dict(servo_id=index+11,final_net_counts=deltas[-1],
                         sampled_peak_absolute_counts=max(map(abs,deltas)),
                         sampled_min_delta=min(deltas),sampled_max_delta=max(deltas)))
    return dict(joints=rows,sample_count=len(record['observations']),
                observation_span_us=record['observations'][-1]['finished_us']-
                                    record['observations'][0]['started_us'],
                continuous_motion_verified=False)
