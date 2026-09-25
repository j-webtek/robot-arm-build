import hashlib
from dataclasses import replace
from threading import Event

import pytest
from rocell.application.first_motion_contract import canonical
from rocell.application import positional_campaign_reference_reader as references
from rocell.providers.windows import positional_campaign_bootstrap as bootstrap
from rocell.providers.windows.positional_campaign_native_protocol import decode_request
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent
from rocell.safety.bench_review_authority import BenchReviewAuthority
from test_positional_campaign_native_protocol import fixture, seal
from test_positional_campaign_authority import review
from test_endpoint_current_context import fixture as endpoint_fixture


def prepared(tmp_path, monkeypatch, *, bounded=False):
    _, snapshots, _, binding = endpoint_fixture()
    wire = fixture(tmp_path)
    body = wire['payload']['campaign_intent']
    files = dict(references.ORIGINAL_FILES)
    if bounded:
        body['schema'] = 'rocell.attended_positional_intent.v2'
        body['references'].pop('stop_qualification_sha256')
        files.pop('stop_qualification_sha256')
        files['bounded_motion_risk_sha256'] = 'bounded-motion-risk.original.json'
    directory = tmp_path / (body['campaign_id']+'-positional-native-child')
    directory.mkdir()
    for name, filename in files.items():
        value = {'fixture_only': name}
        if name == 'runtime_sha256': value = wire['payload']['registration']
        if name == 'native_controller_review_sha256': value = binding.to_dict()
        if name == 'bounded_motion_risk_sha256':
            value = dict(schema='rocell.attended_bounded_motion_risk.v1', operator_present=True,
                entire_accepted_motion_clear=True, no_contact=True, no_added_payload=True,
                accepted_goal_may_finish=True, software_cancel_is_not_physical_stop=True)
        raw = canonical(value)
        (directory/filename).write_bytes(raw)
        body['references'][name] = hashlib.sha256(raw).hexdigest()
    monkeypatch.setattr(references, 'source_fingerprint', lambda workspace: body['references']['source_sha256'])
    authority = BenchReviewAuthority(b'k'*32).for_positional_campaign()
    monkeypatch.setattr(bootstrap, 'load_host_positional_campaign_review_authority', lambda workspace: authority)
    snapshots[0] = replace(snapshots[0], started_monotonic_ns=2_000_000_000, finished_monotonic_ns=2_000_000_000)
    acquisitions = []
    def factory(**kwargs):
        acquisitions.append(kwargs)
        return lambda: snapshots[0]
    monkeypatch.setattr(bootstrap, 'WindowsControllerMetadataAcquirer', factory)
    request = PositionalCampaignIntent(canonical(body))
    reviewed = review()
    if bounded:
        from rocell.safety.positional_campaign_authority import BOUNDED_CHECKS
        reviewed['checks'] = dict.fromkeys(BOUNDED_CHECKS, True)
    (tmp_path/(body['campaign_id']+'-positional-review.json')).write_bytes(authority.seal(request, reviewed, now_ns=1_000_000_000))
    wire.update(operation_sha256=request.sha256, registration_sha256=body['references']['runtime_sha256'])
    return seal(wire), acquisitions, snapshots


def test_actual_reference_signature_and_binding_composition(tmp_path, monkeypatch):
    raw, acquisitions, _ = prepared(tmp_path, monkeypatch)
    reader = bootstrap.prepare_authenticated_campaign_reader(tmp_path, raw,
        cancellation=Event(), clock_ns=lambda: 2_000_000_000)
    assert reader.request.sha256 == decode_request(raw)['operation_sha256']
    assert not reader.verify_endpoint()['motion_authorized']
    assert acquisitions[0]['maximum_acquisitions'] == 32
    assert not list(tmp_path.glob('*-claimed.json'))


@pytest.mark.parametrize('fault', ['cancel', 'signature', 'identity', 'original', 'expired'])
def test_bootstrap_does_not_return_reader_for_invalid_context(tmp_path, monkeypatch, fault):
    raw, acquisitions, snapshots = prepared(tmp_path, monkeypatch)
    cancellation = Event()
    if fault == 'cancel': cancellation.set()
    if fault == 'signature': next(tmp_path.glob('*-positional-review.json')).write_bytes(b'{}')
    if fault == 'identity': snapshots[0] = replace(snapshots[0], native_observations=())
    if fault == 'original': next(tmp_path.glob('*-positional-native-child/workcell.original.json')).write_bytes(b'{}')
    with pytest.raises(ValueError):
        bootstrap.prepare_authenticated_campaign_reader(tmp_path, raw, cancellation=cancellation,
            clock_ns=lambda: 50_000_000_000 if fault == 'expired' else 2_000_000_000)
    if fault in ('cancel', 'original', 'expired'): assert acquisitions == []
