"""Temporary DPAPI test keys only; no production provisioning or arm access."""

import os
import pytest
from rocell.providers.windows import bench_review_key as module
from test_bench_review_authority import originals
from test_endpoint_trial_contract import request
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode


@pytest.mark.skipif(os.name!='nt',reason='Windows known-folder lookup')
def test_private_base_does_not_depend_on_inherited_home_environment(monkeypatch):
    expected = module._local_base()
    for name in ('USERPROFILE', 'HOMEDRIVE', 'HOMEPATH', 'LOCALAPPDATA', 'APPDATA'):
        monkeypatch.delenv(name, raising=False)
    monkeypatch.setattr(module.Path, 'home', lambda: pytest.fail('No home/environment lookup'))
    assert module._local_base() == expected


def test_load_missing_does_not_provision(tmp_path,monkeypatch):
    monkeypatch.setattr(module,'_crypt',lambda *a,**k:pytest.fail('No key generation/load'))
    with pytest.raises(Exception): module.load_bench_review_authority(tmp_path)
    assert list(tmp_path.iterdir())==[]


@pytest.mark.skipif(os.name!='nt',reason='Current-user Windows DPAPI')
def test_protected_key_loads_same_authority_without_plaintext_export(tmp_path):
    report = module.provision_bench_review_key(tmp_path)
    assert report['physical_authority'] is False
    first = module.load_bench_review_authority(tmp_path)
    second = module.load_bench_review_authority(tmp_path)
    req = request()
    signed = first.seal(req,originals(req),now_ns=1_000_000_000)
    evidence = second.verify(req,signed,connection_id='owned-test',
        current_references=tuple(sorted(req.to_dict()['references'].items())),now_ns=1_000_000_000)
    assert evidence.request_sha256==req.request_sha256
    stored = (tmp_path/module.FILENAME).read_bytes()
    assert module._DOMAIN not in stored and first._key not in stored
    with pytest.raises(ValueError): module.provision_bench_review_key(tmp_path)
    assert (tmp_path/module.FILENAME).read_bytes()==stored


@pytest.mark.parametrize('original',[b'',b'wrong-domain'+b'x'*32,module._DOMAIN+b'x'*31])
def test_invalid_plaintext_never_becomes_authority(tmp_path,monkeypatch,original):
    module.publish_reservation_bytes(tmp_path,module.FILENAME,b'fake-protected-test-blob')
    monkeypatch.setattr(module,'_crypt',lambda *a,**k:original)
    with pytest.raises(ValueError): module.load_bench_review_authority(tmp_path)


@pytest.mark.skipif(os.name!='nt',reason='Current-user Windows DPAPI')
def test_corrupt_protected_blob_is_not_regenerated(tmp_path):
    module.provision_bench_review_key(tmp_path)
    publish_bytes(tmp_path,module.FILENAME,b'invalid-protected-blob',mode=PublicationMode.REPLACE)
    with pytest.raises(RuntimeError): module.load_bench_review_authority(tmp_path)
    assert (tmp_path/module.FILENAME).read_bytes()==b'invalid-protected-blob'
