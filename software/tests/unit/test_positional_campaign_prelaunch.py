from threading import Event

import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application.positional_campaign_launch import reserve_campaign_launch, claim_campaign_worker
from rocell.providers.windows import positional_campaign_prelaunch as prelaunch
from rocell.providers.windows.positional_campaign_bootstrap import prepare_authenticated_campaign_reader
from rocell.providers.windows.positional_campaign_native_protocol import decode_request
from test_positional_campaign_native_protocol import seal
from test_positional_campaign_bootstrap import prepared


def reserved(tmp_path, monkeypatch):
    raw, acquisitions, snapshots = prepared(tmp_path, monkeypatch, bounded=True)
    reader = prepare_authenticated_campaign_reader(tmp_path, raw, cancellation=Event(), clock_ns=lambda: 2_000_000_000)
    wire = decode_request(raw)
    wire['payload']['launch_sha256'] = reserve_campaign_launch(tmp_path, reader,
        runtime_original=canonical(wire['payload']['registration']))
    return seal(wire), reader, acquisitions


def test_unclaimed_original_and_review_match_without_consumption(tmp_path, monkeypatch):
    raw, _, _ = reserved(tmp_path, monkeypatch)
    reader = prelaunch.verify_reserved_campaign_entry(tmp_path, raw,
        cancellation=Event(), clock_ns=lambda: 2_000_000_000)
    assert reader.request.sha256 == decode_request(raw)['operation_sha256']
    assert not list(tmp_path.glob('*-positional-claimed.json'))
    claim_campaign_worker(tmp_path, reader, launch_sha256=decode_request(raw)['payload']['launch_sha256'])
    with pytest.raises(ValueError, match='already claimed'):
        prelaunch.verify_reserved_campaign_entry(tmp_path, raw,
            cancellation=Event(), clock_ns=lambda: 2_000_000_000)


@pytest.mark.parametrize('fault', ['launch', 'digest', 'review', 'cancel', 'claim_during_check'])
def test_changed_or_cancelled_reservation_cannot_pass(tmp_path, monkeypatch, fault):
    raw, original_reader, _ = reserved(tmp_path, monkeypatch)
    cancellation = Event()
    if fault == 'launch': next(tmp_path.glob('*-positional-launch.json')).write_bytes(b'{}')
    if fault == 'digest':
        wire = decode_request(raw)
        wire['payload']['launch_sha256'] = 'f'*64
        raw = seal(wire)
    if fault == 'review': next(tmp_path.glob('*-positional-review.json')).write_bytes(b'{}')
    if fault == 'cancel': cancellation.set()
    if fault == 'claim_during_check':
        actual = prelaunch._verify_launch
        def concurrent(root, reader, digest):
            evidence = actual(root, reader, digest)
            claim_campaign_worker(root, original_reader, launch_sha256=digest)
            return evidence
        monkeypatch.setattr(prelaunch, '_verify_launch', concurrent)
    with pytest.raises(ValueError):
        prelaunch.verify_reserved_campaign_entry(tmp_path, raw,
            cancellation=cancellation, clock_ns=lambda: 2_000_000_000)
