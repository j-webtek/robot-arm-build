import hashlib
import json

import pytest

from rocell.application.physical_settling_review import review_settling


def encoded(doc):
    return json.dumps(doc, separators=(',', ':')).encode()


def sample(event, sequence, start, command='move'):
    return dict(schema='rocell.shoulder_hold_event.v1', boot_id='11'*16,
                command_id=command, sequence=sequence, event=event,
                snapshot_role='OBSERVATION', physical_accuracy_verified=False,
                scan_started_us=start, scan_finished_us=start+1000,
                joints=[[sid, 2000, 1995, 1, (b'\xd0\x07'+bytes(13)).hex()]
                        for sid in range(11, 18)])


@pytest.fixture
def evidence():
    last = sample('SHOULDER_STEP_SAMPLE', 5, 1000)
    fault = encoded(sample('STATE_MISMATCH', 6, 3000))
    records = []
    for index in range(3):
        doc = sample('FAULT_SETTLING_SAMPLE', index, 10000+index*600000, 'settle-move')
        doc.update(parent_command_id='move', original_fault_sha256=hashlib.sha256(fault).hexdigest(),
                   parent_fault_latched=True, movement_authorized=False)
        records.append(encoded(doc))
    return fault, records, dict(last_movement=last, movement_count=6, claimed_state='SETTLED')


def test_valid_read_only_review(evidence):
    fault, records, kwargs = evidence
    result = review_settling(fault, records, **kwargs)
    assert result['stability_verified'] and result['movement_outcome_unchanged']
    assert result['endpoint_error_counts'] == [5, 5]


@pytest.mark.parametrize('field,value', [
    ('boot_id', '22'*16), ('command_id', 'unrelated'), ('sequence', 4),
    ('original_fault_sha256', '00'*32), ('parent_command_id', 'other'),
    ('scan_started_us', 1), ('movement_authorized', True),
])
def test_wrong_correlation_or_stale_sample_rejected(evidence, field, value):
    fault, records, kwargs = evidence
    changed = json.loads(records[1]); changed[field] = value
    records[1] = encoded(changed)
    with pytest.raises(ValueError):
        review_settling(fault, records, **kwargs)


@pytest.mark.parametrize('column,value', [(1, 2001), (2, 1996), (3, 0)])
def test_raw_position_or_goal_or_torque_change_rejected(evidence, column, value):
    fault, records, kwargs = evidence
    changed = json.loads(records[0]); changed['joints'][1][column] = value
    records[0] = encoded(changed)
    with pytest.raises(ValueError):
        review_settling(fault, records, **kwargs)


def test_unproven_settled_state_rejected(evidence):
    fault, records, kwargs = evidence
    with pytest.raises(ValueError, match='stable observations'):
        review_settling(fault, records[:2], **kwargs)


def test_duplicate_sample_rejected(evidence):
    fault, records, kwargs = evidence
    with pytest.raises(ValueError):
        review_settling(fault, [records[0], records[0], records[2]], **kwargs)
