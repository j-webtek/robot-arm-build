"""Synthetic signed reviews: tests authenticate bytes, not physical readiness."""

import hashlib
import json
from dataclasses import replace

import pytest

from rocell.safety.bench_review_authority import (
    BenchReviewAuthority, AuthenticatedBenchReviewReader, BenchReviewCurrentContext,
    OPERATOR_CHECKS, _canonical,
)
from rocell.safety.bench_endpoint import REQUIRED_CHECKS, authorize_bench_endpoint
from rocell.application.physical_onboarding_durability import publish_bytes, PublicationMode
from test_endpoint_trial_contract import request


def originals(req):
    return {name:_canonical({
        'schema':'rocell.bench_endpoint_review.v1', 'scope':'ONE_NONCONTACT_BENCH_ENDPOINT',
        'check':name, 'decision':'APPROVED','actor_id':'synthetic-test-reviewer',
        'evidence_kind':'OPERATOR_ATTESTATION' if name in OPERATOR_CHECKS else 'ENGINEERING_REVIEW',
        'request_sha256':req.request_sha256, 'recorded_ns':1_000_000_000,
        'expires_ns':20_000_000_000,'detail':'Synthetic test approval, not actual hardware evidence.',
    }) for name in REQUIRED_CHECKS}


def fixture(tmp_path, req=None):
    req = request() if req is None else req
    authority = BenchReviewAuthority(b'test-only-not-a-production-secret!')
    records = originals(req)
    raw = authority.seal(req, records, now_ns=1_000_000_000)
    filename = req.to_dict()['attempt_id']+'-bench-reviews.json'
    publish_bytes(tmp_path, filename, raw, mode=PublicationMode.IMMUTABLE)
    tick = [1_000_000_000]
    current = [BenchReviewCurrentContext('owned-test', (0x10c4,0xea60,'A'*32),
               tuple(sorted(req.to_dict()['references'].items())), tick[0])]
    reader = AuthenticatedBenchReviewReader(req, authority=authority, review_root=tmp_path,
        connection_id='owned-test', context_reader=lambda:current[0], clock_ns=lambda:tick[0])
    return req, authority, records, raw, filename, reader, tick, current


def test_authenticated_reader_composes_with_bench_permit(tmp_path):
    req, authority, records, raw, filename, reader, tick, current = fixture(tmp_path)
    evidence = reader()
    assert dict(evidence.checks) == {name:hashlib.sha256(value).hexdigest() for name,value in records.items()}
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader,
                                     attempt_root=tmp_path, clock=lambda:tick[0])
    assert permit.consume(req, 'owned-test')
    assert not permit.consume(req, 'owned-test')


def test_presence_expiry_authenticates_without_claiming_current_usb(tmp_path):
    req,authority,records,raw,filename,reader,tick,current = fixture(tmp_path)
    # Expiry alone must not manufacture usable current-context evidence.
    current[0] = None
    assert reader.presence_expiry()==20_000_000_000
    with pytest.raises(ValueError): reader()
    tick[0]=20_000_000_000
    with pytest.raises(ValueError): reader.presence_expiry()


def test_presence_expiry_does_not_cache_modified_bundle(tmp_path):
    req,authority,records,raw,filename,reader,tick,current = fixture(tmp_path)
    assert reader.presence_expiry()==20_000_000_000
    publish_bytes(tmp_path,filename,b'{}',mode=PublicationMode.REPLACE)
    with pytest.raises(ValueError): reader.presence_expiry()


def test_wrong_key_and_modified_authenticated_bytes_refused(tmp_path):
    req, authority, records, raw, filename, reader, tick, current = fixture(tmp_path)
    other = BenchReviewAuthority(b'x'*32)
    for verifier, payload in [(other,raw), (authority,raw.replace(b'"mac":"',b'"mac":"0',1))]:
        with pytest.raises(ValueError):
            verifier.verify(req, payload, connection_id='owned-test',
                current_references=current[0].references, now_ns=tick[0])


@pytest.mark.parametrize('field,value', [
    ('decision','DENIED'),('decision','UNKNOWN'),('scope','PHONE_CONTACT'),
    ('request_sha256','f'*64),('recorded_ns',True),('recorded_ns',2_000_000_000),
    ('expires_ns',1_000_000_000),('expires_ns',22_000_000_000),
    ('actor_id',''),('detail',''),('evidence_kind','SENSOR_CONFIRMED'),
])
def test_sealing_never_converts_invalid_review_to_approval(field,value):
    req = request()
    data = originals(req)
    item = json.loads(data['operator_present'])
    item[field] = value
    data['operator_present'] = _canonical(item)
    with pytest.raises(ValueError):
        BenchReviewAuthority(b't'*32).seal(req, data, now_ns=1_000_000_000)


def test_missing_review_and_noncanonical_duplicate_document_refused():
    req = request()
    authority = BenchReviewAuthority(b't'*32)
    data = originals(req)
    data.pop('operator_present')
    with pytest.raises(ValueError): authority.seal(req,data,now_ns=1_000_000_000)
    data = originals(req)
    data['operator_present'] = b'{"decision":"APPROVED","decision":"DENIED"}'
    with pytest.raises(ValueError): authority.seal(req,data,now_ns=1_000_000_000)


@pytest.mark.parametrize('change', [
    {'connection_id':'another'}, {'usb_identity':(0x10c4,0xea60,'B'*32)},
    {'references':()}, {'observed_ns':1}, {'observed_ns':True},
])
def test_current_identity_and_source_must_be_revalidated(tmp_path,change):
    req, authority, records, raw, filename, reader, tick, current = fixture(tmp_path)
    current[0] = replace(current[0], **change)
    with pytest.raises(ValueError): reader()


def test_expired_reviews_are_not_refreshed_by_reader(tmp_path):
    req, authority, records, raw, filename, reader, tick, current = fixture(tmp_path)
    tick[0] = 20_000_000_000
    current[0] = replace(current[0], observed_ns=tick[0])
    with pytest.raises(ValueError): reader()


def test_record_change_after_permit_issuance_prevents_consumption(tmp_path):
    req, authority, records, raw, filename, reader, tick, current = fixture(tmp_path)
    permit = authorize_bench_endpoint(req, connection_id='owned-test', evidence_reader=reader,
                                     attempt_root=tmp_path, clock=lambda:tick[0])
    publish_bytes(tmp_path, filename, b'{}', mode=PublicationMode.REPLACE)
    assert not permit.consume(req, 'owned-test')
