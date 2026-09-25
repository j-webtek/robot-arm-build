from dataclasses import replace

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.safety.observational_review_authority import ObservationalIntent
from rocell.safety.bench_review_authority import BenchReviewAuthority
from rocell.providers.windows.observational_current_context import (
    ObservationalCurrentContextReader, AuthenticatedObservationalReader,
)
from test_endpoint_current_context import fixture as endpoint_fixture
from test_observational_review_authority import intent, review


def fixture(tmp_path):
    _, snapshots, _, binding = endpoint_fixture()
    body = intent()
    body['references']['native_controller_review_sha256'] = binding.binding_sha256
    request = ObservationalIntent(canonical(body))
    snapshots[0] = replace(snapshots[0], started_monotonic_ns=2_000_000_000,
                           finished_monotonic_ns=2_010_000_000)
    references = [tuple(sorted(body['references'].items()))]
    clock = iter((2_000_000_000, 2_020_000_000))
    context = ObservationalCurrentContextReader(request, binding=binding,
        connection_id=body['attempt_id'], metadata_reader=lambda: snapshots[0],
        references_reader=lambda: references[0], clock_ns=lambda: next(clock))
    authority = BenchReviewAuthority(b'Z'*32).for_observational_motion()
    raw = authority.seal(body, review(), now_ns=1_000_000_002)
    publish_reservation_bytes(tmp_path, body['attempt_id']+'-observational-reviews.json', raw,
                              maximum_bytes=8192)
    reader = AuthenticatedObservationalReader(request, root=tmp_path, authority=authority,
        context_reader=context, clock_ns=lambda: 2_030_000_000)
    return reader, snapshots, references, binding


def test_signed_record_matches_actual_resolver_output(tmp_path):
    reader, _, _, binding = fixture(tmp_path)
    evidence = reader.verify_endpoint(binding.identity.port_name)
    assert evidence['motion_authorized'] is False
    assert evidence['usb_identity'] == (0x10c4, 0xea60, 'A'*32)
    assert evidence['connection_id'] == intent()['attempt_id']


@pytest.mark.parametrize('fault', ['missing', 'duplicate', 'port', 'stale', 'references', 'bundle', 'expected_port'])
def test_changes_rejected_before_native_admission(tmp_path, fault):
    reader, snapshots, refs, binding = fixture(tmp_path)
    snapshot = snapshots[0]
    expected = binding.identity.port_name
    if fault == 'missing': snapshot = replace(snapshot, native_observations=())
    if fault == 'duplicate': snapshot = replace(snapshot, native_observations=snapshot.native_observations*2)
    if fault == 'port': snapshot = replace(snapshot, native_observations=(replace(snapshot.native_observations[0], port_name='COM8'),))
    if fault == 'stale': snapshot = replace(snapshot, started_monotonic_ns=1_800_000_000)
    if fault == 'references': refs[0] = ()
    if fault == 'bundle':
        (tmp_path/(intent()['attempt_id']+'-observational-reviews.json')).write_bytes(b'{}')
    if fault == 'expected_port': expected = 'COM4096'
    snapshots[0] = snapshot
    with pytest.raises(ValueError): reader.verify_endpoint(expected)
