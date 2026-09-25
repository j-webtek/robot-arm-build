"""Offline binding tests; synthetic receipts never authorize hardware."""
import copy
import hashlib
import json
from pathlib import Path

import pytest
from rocell.application import observed_pose_pair as module


@pytest.fixture
def setup(tmp_path, monkeypatch):
    policy = json.loads((Path(__file__).resolve().parents[2] /
        'docs/hold-r7-supported-pose-draft.json').read_bytes())['hold_policy']
    policy['joints'] = [[2045,2049],[2485,2489],[1627,1631],[2893,2909],
                        [2033,2037],[2039,2043],[2052,2056]]
    policy['permit_explicit_enable'] = 0
    binding = dict(expected_boot='12'*16, address='192.168.0.225')
    source = dict(preparation_sha256='a'*64, preparation=dict(policy=policy, historical_anchor=2899,
        pair_plan=dict(boot_id='12'*16, forward_command_id='observed-pose-plus10-forward',
            return_command_id='observed-pose-plus10-return',offset_counts=10,tolerance_counts=2)))
    monkeypatch.setattr(module, 'review_observed_startup', lambda *a, **k: binding)
    monkeypatch.setattr(module, 'replay_held_pair_preparation', lambda *a: copy.deepcopy(source))
    (tmp_path/'runs/wizard-exports').mkdir(parents=True)
    return tmp_path, binding, source


@pytest.mark.parametrize('fault', [None,'boot','forward','return','offset','tolerance',
    'policy','anchor','float_anchor','recovery','pair','receipt'])
def test_exact_observed_pair_binding(setup, monkeypatch, fault):
    root, binding, source = setup
    prep = source['preparation']; plan = prep['pair_plan']
    if fault=='boot': plan['boot_id']='34'*16
    if fault=='forward': plan['forward_command_id']='legacy-forward'
    if fault=='return': plan['return_command_id']='legacy-return'
    if fault=='offset': plan['offset_counts']=6
    if fault=='tolerance': plan['tolerance_counts']=1
    if fault=='policy': prep['policy']['speed']=30
    if fault=='anchor': prep['historical_anchor']=2900
    if fault=='float_anchor': prep['historical_anchor']=2899.0
    if fault=='receipt':
        def reject(*a, **k): raise ValueError('Missing installed settings receipt')
        monkeypatch.setattr(module,'review_observed_startup',reject)
        monkeypatch.setattr(module,'replay_held_pair_preparation',
            lambda *a: pytest.fail('Preparation must not precede installation review'))
    if fault in ('recovery','pair'):
        boot=binding['expected_boot']
        name=('supported-recovery-trial-'+boot if fault=='recovery' else
              'held-pair-trial-'+hashlib.sha256(boot.encode('ascii')).hexdigest())
        (root/'runs/wizard-exports'/(name+'.json')).write_text('{}')
    args=dict(startup_export='startup',stage_export='stage',
              installation_export='installed',preparation_export='prep')
    if fault:
        with pytest.raises(ValueError): module.review_observed_pair(root, **args)
    else:
        assert module.review_observed_pair(root, **args)==(binding, source)


@pytest.mark.parametrize('fault', [None,'approval','status','storage','capture','export','trial'])
def test_trial_boundary(setup, monkeypatch, fault):
    root, _, _ = setup
    calls=[]
    def capture(*a, **k):
        calls.append('read')
        if fault=='capture': raise ValueError('Unavailable')
        return dict(export_path=str(root/'baseline'), summary=dict(category='TRANSPORT_CAPTURED',
            status=dict(state='FAULT' if fault=='status' else 'CAPTURED',
                        storage_fault=fault=='storage')))
    def trial(*a, **k):
        calls.append('trial')
        if fault=='trial': raise ValueError('Uncertain delivery')
        return dict(test_only=True)
    monkeypatch.setattr(module,'capture_hold_transport',capture)
    monkeypatch.setattr(module,'run_admitted_pair',trial)
    if fault=='export': monkeypatch.setattr(module,'_read',lambda *a: ({},'b'*64))
    args=dict(startup_export='startup',stage_export='stage',installation_export='installed',
              preparation_export='prep',key=b'k'*32,approved=fault!='approval')
    if fault:
        with pytest.raises(ValueError): module.run_observed_pair(root, **args)
    else:
        assert module.run_observed_pair(root, **args)['trial']==dict(test_only=True)
    assert calls.count('trial')==(1 if fault in (None,'trial') else 0)
    if fault=='approval': assert not calls


def test_preparation_uses_exact_experiment(setup, monkeypatch):
    root, _, _ = setup
    calls=[]
    def prepare(*a, **k):
        calls.append(k)
        return dict(export_path=str(root/'prep'))
    monkeypatch.setattr(module,'prepare_held_pair',prepare)
    module.prepare_observed_pair(root,startup_export='startup',stage_export='stage',
                                 installation_export='installed',hold_export='hold')
    assert calls==[dict(forward_command_id='observed-pose-plus10-forward',
        return_command_id='observed-pose-plus10-return',offset_counts=10,tolerance_counts=2)]
