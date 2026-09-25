import copy
import hashlib
import json
from pathlib import Path
import pytest
from rocell.application import r16_pair_launch as module


@pytest.fixture
def setup(tmp_path, monkeypatch):
    policy = json.loads((Path(__file__).resolve().parents[2] /
        'docs/hold-r7-supported-pose-draft.json').read_bytes())['hold_policy']
    binding = dict(expected_boot='12'*16, address='192.168.0.225')
    source = dict(preparation_sha256='a'*64, preparation=dict(policy=policy,
        historical_anchor=2902, pair_plan=dict(boot_id='12'*16,
        forward_command_id='r10-elbow-forward', return_command_id='r10-elbow-return',
        offset_counts=6, tolerance_counts=2)))
    monkeypatch.setattr(module, 'review_recovery_startup', lambda *a: binding)
    monkeypatch.setattr(module, 'replay_held_pair_preparation', lambda *a: copy.deepcopy(source))
    (tmp_path / 'runs/wizard-exports').mkdir(parents=True)
    return tmp_path, binding, source


@pytest.mark.parametrize('fault', [None, 'boot', 'command', 'offset', 'tolerance', 'policy', 'anchor', 'recovery', 'pair'])
def test_bound_preparation(setup, fault):
    root, binding, source = setup
    prep = source['preparation'];plan = prep['pair_plan']
    if fault == 'boot': plan['boot_id']='34'*16
    if fault == 'command': plan['forward_command_id']='other'
    if fault == 'offset': plan['offset_counts']=8
    if fault == 'tolerance': plan['tolerance_counts']=5
    if fault == 'policy': prep['policy']['speed']=30
    if fault == 'anchor': prep['historical_anchor']=2907
    if fault in ('recovery', 'pair'):
        boot = binding['expected_boot']
        name = ('supported-recovery-trial-'+boot if fault=='recovery' else
                'held-pair-trial-'+hashlib.sha256(boot.encode()).hexdigest())
        (root/'runs/wizard-exports'/(name+'.json')).write_text('{}')
    if fault:
        with pytest.raises(ValueError): module.review_r16_pair(root, 'startup', 'prep')
    else:
        assert module.review_r16_pair(root, 'startup', 'prep')[0] == binding
        plan['offset_counts']=-6
        with pytest.raises(ValueError): module.review_r16_pair(root, 'startup', 'prep')


@pytest.mark.parametrize('fault', [None, 'approval', 'fresh_status', 'export', 'trial'])
def test_live_boundary_single_delegation(setup, monkeypatch, fault):
    root, _, _ = setup
    calls=[]
    def capture(*a, **k):
        calls.append('read')
        return dict(export_path=str(root/'baseline'), summary=dict(category='TRANSPORT_CAPTURED',
            status=dict(state='FAULT' if fault=='fresh_status' else 'CAPTURED',storage_fault=False)))
    def trial(*a, **k):
        calls.append('trial')
        if fault=='trial': raise ValueError('injected')
        return {'test_only':True}
    monkeypatch.setattr(module, 'capture_hold_transport', capture)
    monkeypatch.setattr(module, 'run_admitted_pair', trial)
    if fault=='export': monkeypatch.setattr(module, '_read', lambda *a: ({}, 'a'*64))
    args=dict(startup_export_id='startup',preparation_id='prep',key=b'k'*32,approved=fault!='approval')
    if fault:
        with pytest.raises(ValueError): module.run_r16_pair(root, **args)
    else:
        assert module.run_r16_pair(root, **args)['trial']=={'test_only':True}
    assert calls.count('trial') == (1 if fault in (None,'trial') else 0)
    if fault=='approval': assert calls==[]


def test_negative_offset_requires_verified_installation(setup, monkeypatch):
    from rocell.application import negative_pair_provisioning
    root,_,source=setup
    source['preparation']['pair_plan']['offset_counts']=-6
    calls=[]
    def review(root,ident):
        calls.append(ident)
        if ident!='installed': raise ValueError('Unverified installation')
        return dict(offset_counts=-6)
    monkeypatch.setattr(negative_pair_provisioning,'review_negative_installation',review)
    with pytest.raises(ValueError):module.review_r16_pair(root,'startup','prep')
    with pytest.raises(ValueError):module.review_r16_pair(root,'startup','prep','bad')
    result=module.review_r16_pair(root,'startup','prep','installed')
    assert result[0]['negative_settings']['offset_counts']==-6
    assert calls==['bad','installed']
    source['preparation']['pair_plan']['offset_counts']=6
    with pytest.raises(ValueError):module.review_r16_pair(root,'startup','prep','installed')
