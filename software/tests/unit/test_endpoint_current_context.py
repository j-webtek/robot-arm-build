"""Synthetic data exercising physical-context rules; never enumerate or open."""

from dataclasses import replace
import pytest
from rocell.providers.windows.endpoint_current_context import EndpointCurrentContextReader
from rocell.application.endpoint_trial_contract import EndpointTrialRequest
from rocell.application.arm_bench_qualification_contract import _canonical
from rocell.application.physical_connection_contracts import EvidenceOrigin
from rocell.application.physical_device_inventory import InventorySource
from test_endpoint_trial_contract import request as endpoint
from test_arm_controller_resolution import request as reviewed_request, snapshot as synthetic_snapshot


def fixture():
    binding = reviewed_request().controller
    binding = replace(binding,origin=EvidenceOrigin.PHYSICAL_OBSERVATION,
        identity=replace(binding.identity,vid='10c4',pid='ea60',unit_serial='A'*32))
    data = endpoint().to_dict()
    data['references']['native_controller_review_sha256']=binding.binding_sha256
    req = EndpointTrialRequest(_canonical(data))
    sample = synthetic_snapshot()
    candidate = replace(sample.serial_inventory.candidates[0],source=InventorySource.PYSERIAL_LIST_PORTS,
                        vid='10c4',pid='ea60',unit_serial='A'*32)
    batch = replace(sample.serial_inventory,source=InventorySource.PYSERIAL_LIST_PORTS,candidates=(candidate,))
    native = replace(sample.native_observations[0],vid='10c4',pid='ea60')
    sample = replace(sample,serial_inventory=batch,native_observations=(native,),
        origin=EvidenceOrigin.PHYSICAL_OBSERVATION,native_source='WINDOWS_CM_METADATA',
        started_monotonic_ns=1_000_000_000,finished_monotonic_ns=1_010_000_000)
    snapshots = [sample]
    refs = [tuple(sorted(req.to_dict()['references'].items()))]
    times = iter((1_000_000_000,1_020_000_000))
    reader = EndpointCurrentContextReader(req,binding=binding,connection_id='owned-test',
        metadata_reader=lambda:snapshots[0],references_reader=lambda:refs[0],clock_ns=lambda:next(times))
    return reader,snapshots,refs,binding


def test_current_metadata_resolves_reviewed_endpoint():
    reader,_,_,binding = fixture()
    context = reader()
    assert context.port_name==binding.identity.port_name
    assert context.observed_ns==1_000_000_000
    assert context.usb_identity==(0x10c4,0xea60,'A'*32)


@pytest.mark.parametrize('fault',['missing','duplicate','port','stale','refs'])
def test_ambiguous_changed_or_stale_metadata_is_held(fault):
    reader,snapshots,refs,_ = fixture()
    sample = snapshots[0]
    if fault=='missing': sample=replace(sample,native_observations=())
    if fault=='duplicate': sample=replace(sample,native_observations=sample.native_observations*2)
    if fault=='port': sample=replace(sample,native_observations=(replace(sample.native_observations[0],port_name='COM8'),))
    if fault=='stale': sample=replace(sample,started_monotonic_ns=900_000_000)
    if fault=='refs': refs[0]=()
    snapshots[0]=sample
    with pytest.raises(ValueError): reader()
