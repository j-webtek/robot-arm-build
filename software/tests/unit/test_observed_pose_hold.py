import json
from pathlib import Path
import pytest
from rocell.application import observed_pose_hold as module


@pytest.mark.parametrize('fault',[None,'approval','receipt','policy','hold_claim','recovery_claim','export','trial'])
def test_observed_hold_boundaries(tmp_path,monkeypatch,fault):
    config=json.loads((Path(__file__).resolve().parents[2]/'docs/hold-r7-supported-pose-draft.json').read_bytes())
    config['command_id']='observed-pose-elbow-hold-v1'
    config['hold_policy']['permit_explicit_enable']=0
    config['hold_policy']['joints']=[[2045,2049],[2485,2489],[1627,1631],[2893,2909],
                                    [2033,2037],[2039,2043],[2052,2056]]
    if fault=='policy':config['hold_policy']['speed']=30
    binding=dict(expected_boot='12'*16,address='192.168.0.225',
                 observed_pose_installation=dict(public_candidate_export='candidate'))
    def review(*a,**k):
        if fault=='receipt':raise ValueError('Bad receipt')
        return binding
    monkeypatch.setattr(module,'review_observed_startup',review)
    monkeypatch.setattr(module,'replay_candidate',lambda *a:dict(report=dict(hold_settings=config)))
    exports=tmp_path/'runs/wizard-exports';exports.mkdir(parents=True)
    if fault in ('hold_claim','recovery_claim'):
        prefix='first-hold-trial-' if fault=='hold_claim' else 'supported-recovery-trial-'
        (exports/(prefix+binding['expected_boot']+'.json')).write_text('{}')
    calls=[]
    def run(*a,**k):
        calls.append(k)
        if fault=='trial':raise ValueError('Uncertain')
        return dict(test_only=True)
    monkeypatch.setattr(module,'run_first_hold',run)
    if fault=='export':monkeypatch.setattr(module,'_read',lambda *a:({},'a'*64))
    args=dict(startup_export='startup',stage_export='stage',installation_export='installed',
              key=b'k'*32,approved=fault!='approval')
    if fault:
        with pytest.raises(ValueError):module.run_observed_hold(tmp_path,**args)
    else:
        assert module.run_observed_hold(tmp_path,**args)['observation']==dict(test_only=True)
        assert calls[0]['configuration']==config
    assert len(calls)==(1 if fault in (None,'trial') else 0)
