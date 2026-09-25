"""Review issuance with test-only authority and explicitly synthetic originals."""

from dataclasses import replace
import os
import pytest
from rocell.application import bench_review_issuance as module
from rocell.safety.bench_review_authority import BenchReviewAuthority, BenchReviewCurrentContext, OPERATOR_CHECKS
from test_bench_review_authority import originals
from test_endpoint_trial_contract import request


def prepared(tmp_path,monkeypatch):
    req = request()
    raw = originals(req)
    context = BenchReviewCurrentContext('owned-test',(0x10c4,0xea60,'A'*32),
              tuple(sorted(req.to_dict()['references'].items())),1_000_000_000)
    monkeypatch.setattr(module,'load_host_bench_review_authority',
                        lambda _:BenchReviewAuthority(b'test-only-not-production-key-12345'))
    kwargs = dict(review_root=tmp_path,connection_id='owned-test',
        operator_reader=lambda r:{k:v for k,v in raw.items() if k in OPERATOR_CHECKS},
        engineering_reader=lambda r:{k:v for k,v in raw.items() if k not in OPERATOR_CHECKS},
        context_reader=lambda:context,clock_ns=lambda:1_000_000_000)
    return req,kwargs,context


def test_issue_preserves_originals_and_refuses_duplicate(tmp_path,monkeypatch):
    req,kwargs,_ = prepared(tmp_path,monkeypatch)
    result = module.issue_bench_reviews(tmp_path,req,**kwargs)
    assert result['expires_ns']==20_000_000_000 and result['physical_authority'] is False
    path = tmp_path/(req.to_dict()['attempt_id']+'-bench-reviews.json')
    original = path.read_bytes()
    with pytest.raises(Exception): module.issue_bench_reviews(tmp_path,req,**kwargs)
    assert path.read_bytes()==original


@pytest.mark.parametrize('reader', ['operator_reader','engineering_reader'])
def test_missing_reviews_do_not_issue_bundle(tmp_path,monkeypatch,reader):
    req,kwargs,_ = prepared(tmp_path,monkeypatch)
    kwargs[reader]=lambda r:{}
    with pytest.raises(ValueError): module.issue_bench_reviews(tmp_path,req,**kwargs)
    assert list(tmp_path.iterdir())==[]


def test_changed_identity_after_publication_is_held_without_erasing_record(tmp_path,monkeypatch):
    req,kwargs,context = prepared(tmp_path,monkeypatch)
    kwargs['context_reader']=lambda:replace(context,usb_identity=(0x10c4,0xea60,'B'*32))
    with pytest.raises(ValueError): module.issue_bench_reviews(tmp_path,req,**kwargs)
    assert len(list(tmp_path.glob('*-bench-reviews.json')))==1


def test_expired_review_not_refreshed(tmp_path,monkeypatch):
    req,kwargs,_ = prepared(tmp_path,monkeypatch)
    kwargs['clock_ns']=lambda:20_000_000_000
    with pytest.raises(ValueError): module.issue_bench_reviews(tmp_path,req,**kwargs)
    assert list(tmp_path.iterdir())==[]


@pytest.mark.skipif(os.name!='nt',reason='Windows protected-key integration')
def test_issuance_loads_host_protected_key(tmp_path,monkeypatch):
    from rocell.providers.windows import bench_review_key as keys
    req,kwargs,_ = prepared(tmp_path,monkeypatch)
    base,workspace,reviews = tmp_path/'host',tmp_path/'workspace',tmp_path/'reviews'
    for path in (base,workspace,reviews): path.mkdir()
    monkeypatch.setattr(keys,'_local_base',lambda:base)
    keys.provision_bench_review_key(keys.host_key_root(workspace,create=True))
    monkeypatch.setattr(module,'load_host_bench_review_authority',keys.load_host_bench_review_authority)
    kwargs['review_root']=reviews
    result = module.issue_bench_reviews(workspace,req,**kwargs)
    bundle = (reviews/(req.to_dict()['attempt_id']+'-bench-reviews.json')).read_bytes()
    evidence = keys.load_host_bench_review_authority(workspace).verify(req,bundle,
        connection_id='owned-test',current_references=tuple(sorted(req.to_dict()['references'].items())),
        now_ns=1_000_000_000)
    assert evidence.request_sha256==result['request_sha256']
