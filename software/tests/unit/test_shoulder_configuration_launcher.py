import importlib.util
from pathlib import Path
import pytest
from rocell.application.held_pair_installation_evidence import _profile


@pytest.fixture
def launcher(tmp_path, monkeypatch):
    path=Path(__file__).resolve().parents[2]/'scripts/run_shoulder_configuration.py'
    spec=importlib.util.spec_from_file_location('shoulder_launcher',path)
    module=importlib.util.module_from_spec(spec);spec.loader.exec_module(module)
    monkeypatch.setattr(module,'__file__',str(tmp_path/'scripts/launcher.py'))
    calls=[]
    def review(root, export, *, revision):
        assert revision==22 and export=='startup'
        calls.append('review')
        return dict(expected_boot='ab'*16,address='192.168.0.225')
    monkeypatch.setattr(module,'review_recovery_startup',review)
    def observe(*args,**kwargs):
        calls.append('idle')
        return {'summary':{'category':'TRANSPORT_CAPTURED','status':{
            'state':'IDLE','reason':'NOT_CONFIGURED','records':0,'storage_fault':False}}}
    monkeypatch.setattr(module,'capture_hold_transport',observe)
    def capture(*args,**kwargs):
        assert kwargs['authorized'] is True and kwargs['expected_boot']=='ab'*16
        calls.append('capture');return {'test':True}
    monkeypatch.setattr(module,'capture_shoulders',capture)
    return module,calls,tmp_path


def test_preflight_never_communicates(launcher):
    module,calls,_=launcher
    module.main(['--startup-export','startup','--preflight-only'])
    assert calls==['review']


def test_capture_follows_verified_idle(launcher):
    module,calls,_=launcher
    module.main(['--startup-export','startup','--authorized-observation'])
    assert calls==['review','idle','capture']


def test_invalid_installation_prevents_communication(launcher,monkeypatch):
    module,calls,_=launcher
    def fail(*args,**kwargs): raise ValueError('not r22')
    monkeypatch.setattr(module,'review_recovery_startup',fail)
    with pytest.raises(ValueError):
        module.main(['--startup-export','startup','--authorized-observation'])
    assert calls==[]


def test_nonidle_prevents_capture(launcher,monkeypatch):
    module,calls,_=launcher
    monkeypatch.setattr(module,'capture_hold_transport',lambda *a,**k:{'summary':{'category':'INCONCLUSIVE'}})
    with pytest.raises(ValueError,match='idle'):
        module.main(['--startup-export','startup','--authorized-observation'])
    assert calls==['review']


@pytest.mark.parametrize('name',['pose-observation-','shoulder-configuration-','first-hold-trial-'])
def test_reserved_boot_prevents_communication(launcher,name):
    module,calls,root=launcher
    exports=root/'runs/wizard-exports';exports.mkdir(parents=True)
    (exports/(name+'ab'*16+'.json')).touch()
    with pytest.raises(ValueError,match='reserved'):
        module.main(['--startup-export','startup','--authorized-observation'])
    assert calls==['review']


def test_r22_profile_matches_actual_offline_artifact():
    import hashlib
    root=Path(__file__).resolve().parents[2]
    raw=(root/'.firmware-tools/build-configured-diagnostic-candidate-r22--default-4mb-no-psram/RoArm-M3_example.ino.bin').read_bytes()
    digest,length,journal,_=_profile(22)
    assert digest==hashlib.sha256(raw).hexdigest() and length==len(raw)
    assert journal=='app-r22-deployment-events.jsonl'
