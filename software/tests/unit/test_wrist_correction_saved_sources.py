import base64
import pytest
import test_absolute_wrist_native_result as fixture_module
from test_observational_native_protocol import rehash
from rocell.application.first_motion_contract import canonical
from rocell.application.wrist_correction_saved_sources import load_saved_absolute_trial,assess_saved_correction_sources
from rocell.providers.windows.absolute_wrist_native_result import encode_result
from rocell.safety.absolute_wrist_review_authority import AbsoluteWristIntent


def saved(root,monkeypatch,fault=None):
    base=fixture_module.wire;attempts=[]
    for index in range(2):
        with monkeypatch.context() as patch:
            def wire(path):
                value=base(path);body=value['payload']['absolute_wrist_intent']
                body['attempt_id']='operation-'+str(index+1)*32
                value['attempt_id']=body['attempt_id']
                value['operation_sha256']=AbsoluteWristIntent(canonical(body)).request_sha256
                return rehash(value)
            patch.setattr(fixture_module,'wire',wire)
            child,value=fixture_module.fixture(root,patch,fault=fault)
            attempt=value['attempt_id'];attempts.append(attempt)
            for kind,raw in (('request',canonical(value)),('stdout',encode_result(child,wire=value))):
                (root/(attempt+'-absolute-wrist-'+kind+'.original.json')).write_bytes(
                    canonical(dict(bytes=len(raw),base64=base64.b64encode(raw).decode())))
    return attempts


def test_saved_pair_reconstructs_and_reports_hypothesis_only(tmp_path,monkeypatch):
    attempts=saved(tmp_path,monkeypatch)
    original,receipt=load_saved_absolute_trial(tmp_path,attempts[0])
    assert original[0].to_dict()['attempt_id']==attempts[0]
    report=assess_saved_correction_sources(tmp_path,attempts)
    assert len(report['selected_originals'])==2 and not report['motion_authorized']
    assert not report['physical_provenance_verified']


@pytest.mark.parametrize('attempts',[[],['../escape','operation-'+'a'*32],['operation-'+'a'*32]*2])
def test_invalid_selection_refused(tmp_path,attempts):
    with pytest.raises(ValueError): assess_saved_correction_sources(tmp_path,attempts)


def test_changed_byte_wrapper_is_rejected(tmp_path,monkeypatch):
    attempts=saved(tmp_path,monkeypatch)
    (tmp_path/(attempts[0]+'-absolute-wrist-request.original.json')).write_bytes(b'{"bytes":1,"base64":"e30="}')
    with pytest.raises(ValueError): assess_saved_correction_sources(tmp_path,attempts)
