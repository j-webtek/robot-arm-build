import copy
import json
from pathlib import Path

import pytest

from rocell.application import elbow_displacement_experiment as experiment


def preparation(anchor):
    policy = json.loads((Path(__file__).resolve().parents[2] /
        'docs/hold-r7-supported-pose-draft.json').read_bytes())['hold_policy']
    return dict(policy=policy, historical_anchor=anchor,
        pair_plan=json.loads(experiment.settings_bytes()))


@pytest.mark.parametrize('anchor', range(2880, 2922))
def test_actual_positive_path_not_unused_negative_target(anchor):
    result = experiment.review_preparation(preparation(anchor))
    assert (result['category']=='ILLUSTRATIVE_PATH_FITS') == (2893 <= anchor <= 2897)
    assert result['illustrative_targets'] == [anchor+12, anchor]
    assert result['progression_authority'] is result['retry_allowed'] is False
    assert result['maximum_position_commands']==2
    assert result['verified_export_before_return_required'] is True


@pytest.mark.parametrize('fault', ['offset', 'id', 'tolerance', 'speed', 'window', 'bool', 'float', 'float_offset', 'float_tolerance'])
def test_rejects_changed_experiment(fault):
    prep = copy.deepcopy(preparation(2897))
    if fault=='offset': prep['pair_plan']['offset_counts']=-6
    if fault=='id': prep['pair_plan']['forward_command_id']='r10-elbow-forward'
    if fault=='tolerance': prep['pair_plan']['tolerance_counts']=3
    if fault=='speed': prep['policy']['speed']=40
    if fault=='window': prep['policy']['joints'][3][1]=2920
    if fault=='bool': prep['historical_anchor']=True
    if fault=='float': prep['historical_anchor']=2897.0
    if fault=='float_offset': prep['pair_plan']['offset_counts']=12.0
    if fault=='float_tolerance': prep['pair_plan']['tolerance_counts']=2.0
    with pytest.raises(ValueError): experiment.review_preparation(prep)


@pytest.mark.parametrize('valid', [True, False])
def test_public_review_requires_replayed_evidence(monkeypatch, tmp_path, valid):
    from rocell.application import held_pair_preparation
    calls = []
    def replay(root, ident):
        calls.append((root,ident))
        if not valid: raise ValueError('Changed source evidence')
        return dict(preparation=preparation(2897), preparation_sha256='a'*64)
    monkeypatch.setattr(held_pair_preparation, 'replay_held_pair_preparation', replay)
    if valid:
        result=experiment.review_export(tmp_path, 'source')
        assert result['preparation_sha256']=='a'*64
        assert result['progression_authority'] is False
    else:
        with pytest.raises(ValueError, match='Changed source'):
            experiment.review_export(tmp_path, 'source')
    assert calls==[(tmp_path,'source')]
