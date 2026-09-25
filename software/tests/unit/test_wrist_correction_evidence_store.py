"""Temporary disk evidence, synthetic plan signatures, no serial access."""
import pytest
from rocell.providers.windows import wrist_correction_evidence_store as store
from rocell.safety.bench_review_authority import BenchReviewAuthority
from test_wrist_correction_native_protocol import fixture


def staged(tmp_path):
    wire, originals, plan = fixture(tmp_path)
    payload = wire['payload']
    store.stage_evidence(payload, assigned_root=tmp_path, originals=originals, plan_raw=plan)
    return payload, originals, plan


def test_roundtrip_and_signature(tmp_path):
    payload, originals, plan = staged(tmp_path)
    evidence = store.authenticate_evidence(payload, assigned_root=tmp_path,
        authority=BenchReviewAuthority(b'A'*32).for_wrist_correction_review(),
        now_ns=payload['context']['issued_ns']+1_000_000_000)
    assert evidence.originals == tuple(originals) and evidence.plan_raw == plan


@pytest.mark.parametrize('fault',['trial','request','plan','missing','oversize','directory'])
def test_bad_stored_originals_rejected(tmp_path, fault):
    payload, _, _ = staged(tmp_path)
    names, plan_name = store._names(payload)
    path = tmp_path / (plan_name if fault=='plan' else names[0][0] if fault=='request' else names[0][1])
    if fault == 'missing': path.unlink()
    elif fault == 'directory': path.unlink(); path.mkdir()
    else: path.write_bytes(b'x'*(512*1024+1) if fault=='oversize' else b'{}')
    with pytest.raises((ValueError,RuntimeError)): store.load_evidence(payload, assigned_root=tmp_path)


def test_root_and_republication_rejected(tmp_path):
    payload, originals, plan = staged(tmp_path)
    other = tmp_path/'other'; other.mkdir()
    with pytest.raises(ValueError): store.load_evidence(payload, assigned_root=other)
    before = {p.name:p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}
    with pytest.raises((OSError,RuntimeError)):
        store.stage_evidence(payload, assigned_root=tmp_path, originals=originals, plan_raw=plan)
    assert before == {p.name:p.read_bytes() for p in tmp_path.iterdir() if p.is_file()}


def test_wrong_key_cannot_authenticate_hash_consistent_store(tmp_path):
    payload, _, _ = staged(tmp_path)
    with pytest.raises(ValueError):
        store.authenticate_evidence(payload, assigned_root=tmp_path,
            authority=BenchReviewAuthority(b'B'*32).for_wrist_correction_review(),
            now_ns=payload['context']['issued_ns']+1_000_000_000)


def test_partial_staging_is_preserved_not_repaired(tmp_path, monkeypatch):
    wire, originals, plan = fixture(tmp_path)
    payload = wire['payload']
    publish = store.publish_reservation_bytes
    calls = []
    def fail_second(*args, **kwargs):
        calls.append(args[1])
        if len(calls) == 2:
            raise OSError('synthetic storage failure')
        return publish(*args, **kwargs)
    monkeypatch.setattr(store, 'publish_reservation_bytes', fail_second)
    with pytest.raises(OSError):
        store.stage_evidence(payload, assigned_root=tmp_path, originals=originals, plan_raw=plan)
    assert len(list(tmp_path.iterdir())) == 1
    with pytest.raises((ValueError,RuntimeError)):
        store.load_evidence(payload, assigned_root=tmp_path)
    monkeypatch.setattr(store, 'publish_reservation_bytes', publish)
    with pytest.raises((OSError,RuntimeError)):
        store.stage_evidence(payload, assigned_root=tmp_path, originals=originals, plan_raw=plan)
    assert len(list(tmp_path.iterdir())) == 1
