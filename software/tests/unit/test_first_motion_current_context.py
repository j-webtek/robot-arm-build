"""Synthetic metadata only: no native enumeration, open or motion."""
from dataclasses import replace

import pytest

from rocell.application.first_motion_contract import FirstMotionRequest, canonical
from rocell.providers.windows.first_motion_current_context import FirstMotionCurrentContextReader
from rocell.providers.windows.endpoint_current_context import EndpointCurrentContextReader
from rocell.safety.first_motion_review_authority import FirstMotionCurrentContext
from test_endpoint_current_context import fixture as endpoint_fixture
from test_first_motion_measurement_binding import setup


def fixture(tmp_path):
    _, snapshots, _, binding = endpoint_fixture()
    _, request = setup(tmp_path)
    data = request.to_dict()
    data['references']['native_controller_review_sha256'] = binding.binding_sha256
    request = FirstMotionRequest(canonical(data))
    snapshots[0] = replace(snapshots[0],started_monotonic_ns=2_000_000_000,
                           finished_monotonic_ns=2_010_000_000)
    refs = [tuple(sorted(request.to_dict()['references'].items()))]
    tick = iter((2_000_000_000,2_020_000_000))
    kwargs = dict(binding=binding,connection_id=request.to_dict()['attempt_id'],
        metadata_reader=lambda:snapshots[0],references_reader=lambda:refs[0],clock_ns=lambda:next(tick))
    return request,kwargs,snapshots,refs


def test_distinct_context_resolves_exact_reviewed_identity(tmp_path):
    request,kwargs,_,_ = fixture(tmp_path)
    context = FirstMotionCurrentContextReader(request,**kwargs)()
    assert type(context) is FirstMotionCurrentContext
    assert context.connection_id == request.to_dict()['attempt_id']
    assert context.usb_identity == (0x10c4,0xea60,'A'*32)
    assert context.port_name == kwargs['binding'].identity.port_name


@pytest.mark.parametrize('fault',['missing','duplicate','port','stale','refs'])
def test_ambiguous_stale_or_changed_metadata_refused(tmp_path,fault):
    request,kwargs,snapshots,refs = fixture(tmp_path)
    sample = snapshots[0]
    if fault=='missing': sample=replace(sample,native_observations=())
    if fault=='duplicate': sample=replace(sample,native_observations=sample.native_observations*2)
    if fault=='port': sample=replace(sample,native_observations=(replace(sample.native_observations[0],port_name='COM8'),))
    if fault=='stale': sample=replace(sample,started_monotonic_ns=1_900_000_000)
    if fault=='refs': refs[0]=()
    snapshots[0]=sample
    with pytest.raises(ValueError): FirstMotionCurrentContextReader(request,**kwargs)()


def test_other_connection_id_and_endpoint_reader_reject_request(tmp_path):
    request,kwargs,_,_ = fixture(tmp_path)
    with pytest.raises(ValueError): EndpointCurrentContextReader(request,**kwargs)
    kwargs['connection_id']='other-attempt'
    with pytest.raises(ValueError): FirstMotionCurrentContextReader(request,**kwargs)
