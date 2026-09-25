"""Reference integrity from bounded originals; no fabricated hardware approval."""

import hashlib
from pathlib import Path
from types import SimpleNamespace
import pytest
from rocell.application import endpoint_reference_reader as module
from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode
from test_endpoint_trial_contract import request


def prepare(root,source,build):
    data = request().to_dict()
    data['references']['source_sha256']=source
    data['references']['build_snapshot_sha256']=build
    for name in module.ORIGINAL_REFERENCES:
        raw = _canonical({'schema':'test.synthetic.reference.v1','name':name})
        data['references'][name]=hashlib.sha256(raw).hexdigest()
        publish_bytes(root,data['attempt_id']+'-'+name+'.original.json',raw,mode=PublicationMode.IMMUTABLE)
    for name in ('source_sha256','configuration_sha256','firmware_review_sha256','geometry_sha256'):
        data['campaign']['evidence'][name]=data['references'][name]
    return EndpointTrialRequest(_canonical(data))


@pytest.mark.parametrize('changed',[None,'source','build','original'])
def test_reconstructs_and_rejects_changed_evidence(tmp_path,monkeypatch,changed):
    req = prepare(tmp_path,'a'*64,'b'*64)
    monkeypatch.setattr(module,'source_fingerprint',lambda _:('f'*64 if changed=='source' else 'a'*64))
    monkeypatch.setattr(module,'import_build_snapshot',lambda _:SimpleNamespace(snapshot_hash='f'*64 if changed=='build' else 'b'*64))
    if changed=='original':
        publish_bytes(tmp_path,req.to_dict()['attempt_id']+'-geometry_sha256.original.json',
                      b'{"changed":true}',mode=PublicationMode.REPLACE)
    reader = module.EndpointReferenceReader(req,workspace=tmp_path,reference_root=tmp_path)
    if changed:
        with pytest.raises(ValueError): reader()
    else: assert reader()==tuple(sorted(req.to_dict()['references'].items()))


def test_real_workspace_source_and_build_are_reconstructed(tmp_path):
    workspace = Path(__file__).resolve().parents[3]
    source = module.source_fingerprint(workspace)
    build = module.import_build_snapshot(workspace).snapshot_hash
    req = prepare(tmp_path,source,build)
    observed = module.EndpointReferenceReader(req,workspace=workspace,reference_root=tmp_path)()
    assert dict(observed)['source_sha256']==source
    assert dict(observed)['build_snapshot_sha256']==build
