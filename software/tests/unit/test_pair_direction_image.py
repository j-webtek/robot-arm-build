"""Real LittleFS operations on synthetic images only; never private staging."""
import hashlib
import pytest
from test_pair_settings_image import library, source_image, HOLD, SETTINGS
from rocell.application.held_pair_settings import encode_pair_settings
from rocell.application.diagnostic_provisioning_image import replace_pair_direction_image

NEGATIVE=encode_pair_settings(forward_command_id='forward',return_command_id='return',offset_counts=-6)


def replace(source, library, **changes):
    args=dict(expected_sha256=hashlib.sha256(source).hexdigest(),previous_settings=SETTINGS,
        settings=NEGATIVE,expected_hold_policy=HOLD,littlefs=library,
        validate_settings=lambda raw:raw in (SETTINGS,NEGATIVE),validate_hold_policy=lambda raw:raw==HOLD)
    args.update(changes)
    return replace_pair_direction_image(source,**args)


def test_only_pair_file_replaced(library,monkeypatch):
    source=source_image(library,existing=True)
    writes=[];original=library.LittleFS.open
    def tracked(self,path,mode='r',*a,**k):
        if mode in ('wb','xb'):writes.append(path)
        return original(self,path,mode,*a,**k)
    monkeypatch.setattr(library.LittleFS,'open',tracked)
    candidate,report=replace(source,library)
    assert writes==['/rocell-pair.json']
    assert len(candidate)==len(source) and candidate!=source
    assert report['remount_verified'] and report['existing_key_preserved']
    assert report['settings_sha256']==hashlib.sha256(NEGATIVE).hexdigest()
    assert not report['device_modified'] and not report['provisioning_performed']


@pytest.mark.parametrize('fault',['absent','source','prior','hold','key','native','magnitude','identity'])
def test_wrong_inputs_do_not_produce_candidate(library,fault):
    source=source_image(library,existing=fault!='absent',key=bytes(32) if fault=='key' else b'K'*32)
    changes={}
    if fault=='source':changes['expected_sha256']='0'*64
    if fault=='prior':changes['previous_settings']=NEGATIVE
    if fault=='hold':changes.update(expected_hold_policy=b'changed',validate_hold_policy=lambda raw:True)
    if fault=='native':changes['validate_settings']=lambda raw:False
    if fault=='magnitude':changes['settings']=encode_pair_settings(forward_command_id='forward',return_command_id='return',offset_counts=-8)
    if fault=='identity':changes['settings']=encode_pair_settings(forward_command_id='changed',return_command_id='return',offset_counts=-6)
    with pytest.raises(ValueError):replace(source,library,**changes)
