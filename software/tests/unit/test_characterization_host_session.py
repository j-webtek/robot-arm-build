import hashlib
import hmac
import pytest
from test_characterization_result_codec import artifact, native
from rocell.application.characterization_result_codec import decode_result
from rocell.application.characterization_host_session import CharacterizationHostSession


def session(tmp_path, artifact):
    record = decode_result(artifact)
    manifest = {name: record[name] for name in ('goals','bounds','maximum_us')}
    return CharacterizationHostSession(tmp_path/'exports',manifest,key=bytes(range(32)),
                                      boot='11'*16,campaign='33'*32,reference='44'*32)


def test_export_before_sign_and_replay_stops(tmp_path, artifact):
    owner=session(tmp_path,artifact)
    result=owner.export_and_sign(artifact,source_boot='11'*16,source_campaign='33'*32)
    token=result['receipt']
    assert token[60:92]==hashlib.sha256(artifact).digest()
    assert token[-32:]==hmac.digest(bytes(range(32)),token[:-32],'sha256')
    assert result['assessment']['status']=='SETTLED_MISS'
    assert not result['controller_acceptance_confirmed']
    with pytest.raises(ValueError,match='sequence'):
        owner.export_and_sign(artifact,source_boot='11'*16,source_campaign='33'*32)
    with pytest.raises(ValueError,match='stopped'):
        owner.export_and_sign(artifact,source_boot='11'*16,source_campaign='33'*32)


@pytest.mark.parametrize('failure',['export','identity','manifest','outcome','stop_outcome','legacy_small'])
def test_failure_never_signs(tmp_path,artifact,monkeypatch,failure):
    from rocell.application import characterization_host_session as module
    owner=session(tmp_path,artifact);boot='11'*16
    if failure=='export':
        monkeypatch.setattr(module,'export_result',lambda *a: (_ for _ in ()).throw(ValueError('export failure')))
    if failure=='identity':boot='22'*16
    if failure=='manifest':owner._manifest['maximum_us']-=1
    if failure in ('outcome','stop_outcome','legacy_small'):
        data=bytearray(artifact)
        data[len(b'RCCRESULT01\0')+2+8+12*4+7*4]=4 if failure=='legacy_small' else 3 if failure=='stop_outcome' else 1
        artifact=bytes(data)
    monkeypatch.setattr(module.hmac,'digest',lambda *a: pytest.fail('must not sign'))
    with pytest.raises(ValueError):owner.export_and_sign(artifact,source_boot=boot,source_campaign='33'*32)
