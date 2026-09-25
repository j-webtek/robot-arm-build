from dataclasses import replace
import pytest
from test_endpoint_current_context import fixture as endpoint_fixture
from test_wrist_correction_review_authority import setup
from rocell.application.first_motion_contract import canonical
from rocell.application.physical_onboarding_durability import publish_reservation_bytes
from rocell.providers.windows.wrist_correction_current_context import (
    WristCorrectionContextRequest,WristCorrectionCurrentContextReader,AuthenticatedWristCorrectionReader)


def fixture(tmp_path):
    _,snapshots,_,binding=endpoint_fixture()
    auth,ctx,review,args=setup()
    ctx['references']['native_controller_review_sha256']=binding.binding_sha256
    request=WristCorrectionContextRequest(canonical(ctx))
    clock=[2_000_000_000]
    refs=[tuple(sorted(ctx['references'].items()))]
    stale=[False]
    def metadata():
        stamp=clock[0]-200_000_000 if stale[0] else clock[0]
        return replace(snapshots[0],started_monotonic_ns=stamp,finished_monotonic_ns=stamp)
    current=WristCorrectionCurrentContextReader(request,binding=binding,connection_id=ctx['attempt_id'],
        metadata_reader=metadata,references_reader=lambda:refs[0],clock_ns=lambda:clock[0])
    raw=auth.seal_plan(ctx,review,originals=args['originals'],now_ns=args['now_ns'],expected_basis=args['expected_basis'])
    name=ctx['attempt_id']+'-wrist-correction-plan-review.json'
    publish_reservation_bytes(tmp_path,name,raw,maximum_bytes=65536)
    reader=AuthenticatedWristCorrectionReader(request,root=tmp_path,authority=auth,context_reader=current,
        originals=args['originals'],expected_basis=args['expected_basis'],clock_ns=lambda:clock[0])
    return reader,clock,refs,snapshots,stale,tmp_path/name


def test_current_metadata_and_plan_without_native_open_authority(tmp_path):
    reader,*_=fixture(tmp_path)
    first=reader.verify_endpoint()
    assert reader.verify_endpoint(first['port_name'])['plan_sha256']==first['plan_sha256']
    assert not first['motion_authorized'] and not first['native_open_authorized']


@pytest.mark.parametrize('fault',['stale','refs','missing','duplicate','expired','plan','port'])
def test_changed_or_ambiguous_context_is_held(tmp_path,fault):
    reader,clock,refs,snapshots,stale,path=fixture(tmp_path)
    if fault=='stale': stale[0]=True
    if fault=='refs': refs[0]=()
    if fault=='missing': snapshots[0]=replace(snapshots[0],native_observations=())
    if fault=='duplicate': snapshots[0]=replace(snapshots[0],native_observations=snapshots[0].native_observations*2)
    if fault=='expired': clock[0]=30_000_000_000
    if fault=='plan': path.write_bytes(b'{}')
    with pytest.raises(ValueError): reader.verify_endpoint('COM4096' if fault=='port' else None)
