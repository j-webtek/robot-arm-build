import importlib.util
from pathlib import Path
import sys
import pytest
import json
import hashlib


def load_script(tmp_path, monkeypatch):
    path=Path(__file__).resolve().parents[2]/'scripts/run_pose_observation.py'
    spec=importlib.util.spec_from_file_location('pose_cli_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'__file__',str(tmp_path/'scripts/run_pose_observation.py'))
    return module


@pytest.mark.parametrize('revision',[20,21,24,53])
def test_preflight_offline_and_execution_binding(tmp_path,monkeypatch,capsys,revision):
    module=load_script(tmp_path,monkeypatch)
    calls=[]
    binding=dict(expected_boot='ab'*16,address='192.168.0.225')
    def review(*a,**k):
        calls.append(k)
        return binding
    monkeypatch.setattr(module,'review_recovery_startup',review)
    monkeypatch.setattr(module,'review_observed_startup',review)
    args=['--startup-export','startup']
    if revision in (24,53):args+=['--revision',str(revision)]
    if revision==21:args+=['--stage-export','stage','--installation-export','installed']
    monkeypatch.setattr(module,'capture_hold_transport',lambda *a,**k:pytest.fail('Offline preflight'))
    monkeypatch.setattr(module,'capture_pose',lambda *a,**k:pytest.fail('Offline preflight'))
    module.main(args+['--preflight-only'])
    result=json.loads(capsys.readouterr().out)
    assert result['hardware_access'] is False and result['current_pose_verified'] is False
    assert calls==[dict(revision=revision) if revision!=21 else
        dict(startup_export='startup',stage_export='stage',installation_export='installed')]
    monkeypatch.setattr(module,'capture_hold_transport',lambda *a,**k:dict(summary=dict(
        category='TRANSPORT_CAPTURED',status=dict(state='IDLE',reason='NOT_CONFIGURED',records=0,storage_fault=False))))
    captures=[]
    monkeypatch.setattr(module,'capture_pose',lambda *a,**k:captures.append(k) or {})
    module.main(args+['--authorized-observation'])
    assert captures==[dict(address=binding['address'],expected_boot=binding['expected_boot'],
        scan_id=f'r{revision}-pose-1',authorized=True)]


@pytest.mark.parametrize('claim_name',[
    'r53-capture-{boot}.json',
    'r53-session-1-capture-{boot}.json',
])
def test_r53_rejects_claimed_boot_before_network(tmp_path,monkeypatch,claim_name):
    module=load_script(tmp_path,monkeypatch);boot='ab'*16
    monkeypatch.setattr(module,'review_recovery_startup',lambda *a,**k:
        dict(expected_boot=boot,address='192.168.0.225'))
    monkeypatch.setattr(module,'capture_hold_transport',lambda *a,**k:
        pytest.fail('Network called on claimed boot'))
    exports=tmp_path/'runs/wizard-exports';exports.mkdir(parents=True)
    (exports/claim_name.format(boot=boot)).write_text('{}')
    with pytest.raises(ValueError,match='already claimed'):
        module.main(['--startup-export','startup','--revision','53','--authorized-observation'])


@pytest.mark.parametrize('fault',['missing_pair','receipt','consumed','hold','recovery','pair','shoulder','not_idle'])
def test_r21_rejects_before_capture(tmp_path,monkeypatch,fault):
    module=load_script(tmp_path,monkeypatch);boot='ab'*16
    def review(*a,**k):
        if fault=='receipt':raise ValueError('Invalid receipt')
        return dict(expected_boot=boot,address='192.168.0.225')
    monkeypatch.setattr(module,'review_observed_startup',review)
    monkeypatch.setattr(module,'capture_pose',lambda *a,**k:pytest.fail('Capture forbidden'))
    def status(*a,**k):
        if fault!='not_idle':pytest.fail('No network before local checks')
        return dict(summary=dict(category='TRANSPORT_CAPTURED',status=dict(state='FAULT')))
    monkeypatch.setattr(module,'capture_hold_transport',status)
    names=dict(consumed='pose-observation-'+boot,shoulder='shoulder-session-'+boot,hold='first-hold-trial-'+boot,
        recovery='supported-recovery-trial-'+boot,
        pair='held-pair-trial-'+hashlib.sha256(boot.encode('ascii')).hexdigest())
    if fault in names:
        exports=tmp_path/'runs/wizard-exports';exports.mkdir(parents=True)
        (exports/(names[fault]+'.json')).write_text('{}')
    args=['--startup-export','startup','--stage-export','stage','--authorized-observation']
    if fault!='missing_pair':args+=['--installation-export','installed']
    with pytest.raises(SystemExit if fault=='missing_pair' else ValueError):module.main(args)


def test_missing_installation_blocks_all_network(monkeypatch):
    path=Path(__file__).resolve().parents[2]/'scripts/run_pose_observation.py'
    spec=importlib.util.spec_from_file_location('pose_cli_test',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    def receipt(*args,**kwargs):
        assert kwargs=={'revision':20}
        raise ValueError('Missing r20 installation')
    def forbidden(*args,**kwargs):pytest.fail('Network called before installation binding')
    monkeypatch.setattr(module,'review_recovery_startup',receipt)
    monkeypatch.setattr(module,'capture_hold_transport',forbidden)
    monkeypatch.setattr(module,'capture_pose',forbidden)
    monkeypatch.setattr(sys,'argv',['pose','--startup-export','unused','--authorized-observation'])
    with pytest.raises(ValueError,match='Missing r20'):module.main()
