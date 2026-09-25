"""Key-free review of historical post-fault records; never signs progression.

Unlike the online exporter, this reviewer binds the first fault to the last
accepted movement sample as well as binding every settling sample to that fault.
"""
import hashlib
import re

from .wizard_diagnostic_coordinator import decode_diagnostic_json


def _sample(raw, *, boot, command, sequence, event, after):
    doc = decode_diagnostic_json(raw, maximum=4095)
    if (not isinstance(doc, dict) or doc.get('schema') != 'rocell.shoulder_hold_event.v1'
            or doc.get('boot_id') != boot or doc.get('command_id') != command
            or type(doc.get('sequence')) is not int or doc['sequence'] != sequence
            or doc.get('event') != event or doc.get('snapshot_role') != 'OBSERVATION'
            or doc.get('physical_accuracy_verified') is not False):
        raise ValueError('Settling record identity mismatch')
    start, finish = doc.get('scan_started_us'), doc.get('scan_finished_us')
    if (type(start) is not int or type(finish) is not int or start <= after
            or not 0 <= finish-start <= 300000):
        raise ValueError('Settling timing invalid')
    rows = doc.get('joints')
    if not isinstance(rows, list) or len(rows) != 7:
        raise ValueError('Seven settling joints required')
    for sid, row in enumerate(rows, 11):
        if (not isinstance(row, list) or len(row) != 5
                or any(type(v) is not int for v in row[:4]) or row[0] != sid
                or not 0 <= row[1] <= 4095 or not 0 <= row[2] <= 4095
                or row[3] not in (0, 1) or not isinstance(row[4], str)
                or not re.fullmatch('[0-9a-f]{30}', row[4])
                or int.from_bytes(bytes.fromhex(row[4])[:2], 'little') != row[1]):
            raise ValueError('Invalid settling joint feedback')
    return doc


def review_settling(original, samples, *, last_movement, movement_count, claimed_state):
    """Return separate post-fault measurements without changing the motion outcome."""
    if not isinstance(samples, list) or not 1 <= len(samples) <= 12:
        raise ValueError('Bounded nonempty settling records required')
    if claimed_state not in ('SETTLED', 'EXHAUSTED', 'FAILED', 'STOPPED', 'IN_PROGRESS'):
        raise ValueError('Unknown settling state')
    boot, parent = last_movement['boot_id'], last_movement['command_id']
    fault = _sample(original, boot=boot, command=parent, sequence=movement_count,
                    event='STATE_MISMATCH', after=last_movement['scan_finished_us'])
    reference = [(row[2], row[3]) for row in last_movement['joints']]
    if [(row[2], row[3]) for row in fault['joints']] != reference:
        raise ValueError('Fault target or torque differs from movement')
    digest = hashlib.sha256(original).hexdigest()
    previous = fault['scan_finished_us']
    stable = 0
    anchor = None
    for index, raw in enumerate(samples):
        doc = _sample(raw, boot=boot, command='settle-'+parent, sequence=index,
                      event='FAULT_SETTLING_SAMPLE', after=previous)
        if (doc.get('parent_command_id') != parent or doc.get('original_fault_sha256') != digest
                or doc.get('parent_fault_latched') is not True
                or doc.get('movement_authorized') is not False
                or (index and doc['scan_started_us']-previous < 500000)):
            raise ValueError('Settling fault linkage or spacing invalid')
        rows = doc['joints']
        if [(row[2], row[3]) for row in rows] != reference:
            raise ValueError('Settling target or torque changed')
        positions = [row[1] for row in rows]
        still = all(not any(bytes.fromhex(row[4])[i] for i in (2, 3, 10)) for row in rows)
        if not still:
            stable = 0
        elif stable and all(abs(a-b) <= 1 for a, b in zip(positions, anchor)):
            stable += 1
        else:
            stable, anchor = 1, positions
        previous = doc['scan_finished_us']
    if claimed_state == 'SETTLED' and stable < 3:
        raise ValueError('Claimed settling lacks stable observations')
    return dict(state=claimed_state, validated_records=len(samples), stable_tail_samples=stable,
                stability_verified=stable >= 3, final_positions=positions,
                endpoint_error_counts=[positions[i]-reference[i][0] for i in (1, 2)],
                change_from_movement_counts=[positions[i]-last_movement['joints'][i][1] for i in (1, 2)],
                elapsed_after_fault_us=previous-fault['scan_finished_us'],
                original_fault_sha256=digest, movement_outcome_unchanged=True)
