"""Real LittleFS staging using exclusively synthetic credentials and images."""
import hashlib
import pytest
from test_diagnostic_provisioning_image import library, image
from rocell.application.diagnostic_provisioning_image import stage_pair_settings_image
from rocell.application.held_pair_settings import encode_pair_settings

HOLD=b'{"synthetic":"hold"}'
SETTINGS=encode_pair_settings(forward_command_id='forward',return_command_id='return')


def source_image(library,*,key=b'K'*32,existing=False):
    context=library.UserContext(buffer=bytearray(image(library)))
    fs=library.LittleFS(context=context,mount=False,block_size=4096,block_count=352,read_size=256,prog_size=256)
    fs.mount()
    try:
        for name,data in [('/rocell-hold.json',HOLD),('/rocell-hold.key',key),('/wifiConfig.json',b'synthetic wifi')]:
            with fs.open(name,'xb') as stream:stream.write(data)
        if existing:
            with fs.open('/rocell-pair.json','xb') as stream:stream.write(SETTINGS)
    finally:fs.unmount()
    return bytes(context.buffer)


def stage(source,library,**kwargs):
    args=dict(expected_sha256=hashlib.sha256(source).hexdigest(),settings=SETTINGS,
        expected_hold_policy=HOLD,littlefs=library,validate_settings=lambda raw:raw==SETTINGS,
        validate_hold_policy=lambda raw:raw==HOLD)
    args.update(kwargs)
    return stage_pair_settings_image(source,**args)


def test_add_only_settings_preserving_all_existing_entries(library,monkeypatch):
    source=source_image(library);writes=[];original=library.LittleFS.open
    def tracked(self,path,mode='r',*args,**kwargs):
        if mode in ('xb','wb'):writes.append(path)
        return original(self,path,mode,*args,**kwargs)
    monkeypatch.setattr(library.LittleFS,'open',tracked)
    candidate,report=stage(source,library)
    assert writes==['/rocell-pair.json']
    assert len(candidate)==len(source) and candidate!=source
    assert report['existing_entries_preserved']==5 and report['remount_verified']
    assert report['existing_key_preserved'] and not report['key_generated']
    assert not report['device_modified'] and not report['provisioning_performed']
    assert b'K'*32 not in str(report).encode()


@pytest.mark.parametrize('fault',['existing','invalid_key','hold_mismatch','native_reject','source_hash'])
def test_invalid_sources_never_return_candidate(library,fault):
    source=source_image(library,key=bytes(32) if fault=='invalid_key' else b'K'*32,
                        existing=fault=='existing')
    overrides={}
    if fault=='hold_mismatch':overrides.update(expected_hold_policy=b'other',validate_hold_policy=lambda raw:True)
    if fault=='native_reject':overrides['validate_settings']=lambda raw:False
    if fault=='source_hash':overrides['expected_sha256']='0'*64
    with pytest.raises(ValueError):stage(source,library,**overrides)


def test_settings_write_failure_does_not_return_candidate(library,monkeypatch):
    source=source_image(library);original=library.LittleFS.open
    def failed(self,path,mode='r',*args,**kwargs):
        if mode=='xb':raise OSError('synthetic full image')
        return original(self,path,mode,*args,**kwargs)
    monkeypatch.setattr(library.LittleFS,'open',failed)
    with pytest.raises(OSError):stage(source,library)
