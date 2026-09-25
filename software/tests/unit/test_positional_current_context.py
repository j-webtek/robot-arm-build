from dataclasses import replace
import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.safety.positional_campaign_authority import PositionalCampaignIntent, PositionalCampaignReviewAuthority
from rocell.providers.windows.positional_current_context import PositionalCurrentContextReader, AuthenticatedPositionalReader
from test_endpoint_current_context import fixture as endpoint_fixture
from test_positional_campaign_authority import body,review
from rocell.safety.bench_review_authority import BenchReviewAuthority


def fixture(tmp_path, runtime_original=None):
    _,snapshots,_,binding=endpoint_fixture()
    value=body()
    if runtime_original is not None:
        import hashlib
        value['references']['runtime_sha256'] = hashlib.sha256(runtime_original).hexdigest()
    value['references']['native_controller_review_sha256']=binding.binding_sha256
    request=PositionalCampaignIntent(canonical(value))
    snapshots[0]=replace(snapshots[0],started_monotonic_ns=2_000_000_000,finished_monotonic_ns=2_010_000_000)
    refs=[tuple(sorted(value['references'].items()))]
    clock=iter((2_000_000_000,2_020_000_000))
    context=PositionalCurrentContextReader(request,binding=binding,connection_id=value['campaign_id'],
        metadata_reader=lambda:snapshots[0],references_reader=lambda:refs[0],clock_ns=lambda:next(clock))
    authority=BenchReviewAuthority(b'k'*32).for_positional_campaign()
    raw=authority.seal(request,review(),now_ns=1_000_000_000)
    publish_reservation_bytes(tmp_path,value['campaign_id']+'-positional-review.json',raw)
    reader=AuthenticatedPositionalReader(request,root=tmp_path,authority=authority,
        context_reader=context,clock_ns=lambda:2_030_000_000)
    return reader,snapshots,refs,binding


def test_current_controller_resolver_and_signed_review_agree(tmp_path):
    reader,_,_,binding=fixture(tmp_path)
    result=reader.verify_endpoint(binding.identity.port_name)
    assert result['connection_id']==body()['campaign_id']
    assert result['usb_identity']==(0x10c4,0xea60,'A'*32)
    assert not result['motion_authorized']


@pytest.mark.parametrize('fault',['missing','duplicate','port','stale','references','bundle','expected_port'])
def test_changed_current_evidence_is_rejected(tmp_path,fault):
    reader,snapshots,refs,binding=fixture(tmp_path)
    snapshot=snapshots[0]
    expected=binding.identity.port_name
    if fault=='missing': snapshot=replace(snapshot,native_observations=())
    if fault=='duplicate': snapshot=replace(snapshot,native_observations=snapshot.native_observations*2)
    if fault=='port': snapshot=replace(snapshot,native_observations=(replace(snapshot.native_observations[0],port_name='COM8'),))
    if fault=='stale': snapshot=replace(snapshot,started_monotonic_ns=1_800_000_000)
    if fault=='references': refs[0]=()
    if fault=='bundle': (tmp_path/(body()['campaign_id']+'-positional-review.json')).write_bytes(b'{}')
    if fault=='expected_port': expected='COM4096'
    snapshots[0]=snapshot
    with pytest.raises(ValueError): reader.verify_endpoint(expected)
