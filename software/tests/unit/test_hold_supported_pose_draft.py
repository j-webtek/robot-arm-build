"""The proposed pose revision must not silently loosen unrelated controls."""
import copy
import json
from pathlib import Path

from rocell.application.first_motion_contract import canonical
from rocell.application.hold_bound_replay import _policy
from rocell.application.hold_command_contract import freeze_hold_plan


def test_only_reviewed_pose_and_command_identity_change():
    docs = Path(__file__).resolve().parents[2]/'docs'
    old = json.loads((docs/'hold-r7-policy-draft.json').read_bytes())
    proposed = json.loads((docs/'hold-r7-supported-pose-draft.json').read_bytes())
    expected = copy.deepcopy(old)
    expected['command_id'] = 'r7-supported-hold-20260918'
    expected['hold_policy']['joints'][3] = [2893, 2909]
    assert proposed == expected
    policy = proposed['hold_policy']
    _policy(policy)
    assert policy['joints'][3][0] <= 2901 <= policy['joints'][3][1]
    assert not policy['joints'][3][0] <= 2723 <= policy['joints'][3][1]
    assert policy['drift'] == 2 and policy['servo_id'] == 14
    frozen = freeze_hold_plan(policy, boot_id='11'*16, command_id=proposed['command_id'])
    assert frozen.policy_encoded == canonical(policy)
