"""Real file pins and inert metadata; never invokes a physical worker."""
from dataclasses import replace
from pathlib import Path
import sys
import pytest
from test_wrist_correction_native_protocol import fixture as protocol_fixture
from rocell.application.first_motion_contract import canonical
from rocell.providers.windows import wrist_correction_native_package as package
from rocell.providers.windows import wrist_correction_native_protocol as protocol
from rocell.providers.windows.wrist_correction_native_registration import validate_registration
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,WorkerProcessRegistration,OwnedWorkerRequest,owned_registration_document)


def fixture(tmp_path):
    wire,_,_=protocol_fixture(tmp_path)
    payload=wire['payload'];ctx=payload['context']
    directory=tmp_path/(ctx['attempt_id']+'-wrist-correction-native-child');directory.mkdir()
    archive=package.prepare(directory)
    controller=directory/'controller.original.json';controller.write_bytes(b'{"fixture":"controller"}')
    profile=directory/'protocol.original.json';profile.write_bytes(b'{"fixture":"protocol"}')
    def pin(path): return PinnedWorkerFile(path,protocol.digest(path.read_bytes()))
    pins=tuple(map(pin,(package.CHILD,archive,controller,profile)))
    registration=WorkerProcessRegistration(protocol.WORKER_ID,
        pin(Path(getattr(sys,'_base_executable',sys.executable))),
        ('-I','-S',str(package.CHILD),str(archive),pins[1].sha256,'execute-one'),pins,directory,
        budget=protocol.fixed_budget(),request_schema=protocol.REQUEST_SCHEMA,result_schema=protocol.RESULT_SCHEMA)
    ctx['references']['native_controller_review_sha256']=pins[2].sha256
    ctx['references']['protocol_review_sha256']=pins[3].sha256
    payload['registration']=owned_registration_document(registration)
    ctx['references']['runtime_sha256']=protocol.digest(canonical(payload['registration']))
    outer=OwnedWorkerRequest(ctx['attempt_id'],ctx['session_id'],ctx['references']['source_sha256'],
        protocol.digest(canonical(payload)),protocol.digest(canonical(ctx['usb_identity'])),ctx['deadline_ns'],canonical(payload))
    return registration,outer


def test_exact_registration_pins_and_payload(tmp_path):
    registration,outer=fixture(tmp_path)
    payload=validate_registration(registration,outer)
    assert payload['registration']==owned_registration_document(registration)
    assert registration.composition=='PHYSICAL_UNQUALIFIED'


@pytest.mark.parametrize('fault',['worker','mode','argv','budget','directory','outer','archive','controller','protocol','entry_hash'])
def test_changed_runtime_or_original_rejected(tmp_path,fault):
    registration,outer=fixture(tmp_path)
    if fault=='worker': registration=replace(registration,worker_id='physical-absolute-wrist-trial')
    if fault=='mode': registration=replace(registration,composition='INCAPABLE_PROCESS_FIXTURE')
    if fault=='argv': registration=replace(registration,argv=registration.argv[:-1]+('check-imports',))
    if fault=='budget': registration=replace(registration,budget=replace(registration.budget,process_count=2))
    if fault=='directory': registration=replace(registration,working_directory=tmp_path)
    if fault=='outer': outer=replace(outer,operation_sha256='f'*64)
    if fault in ('archive','controller','protocol'):
        index={'archive':1,'controller':2,'protocol':3}[fault]
        registration.package_files[index].path.write_bytes(b'changed')
    if fault=='entry_hash':
        registration=replace(registration,package_files=(replace(registration.package_files[0],sha256='f'*64),)+registration.package_files[1:])
    with pytest.raises(ValueError): validate_registration(registration,outer)


def test_registration_without_physical_review_cannot_dispatch(tmp_path):
    from threading import Event
    from rocell.providers.windows.owned_worker_process import OwnedWindowsWorker
    registration,outer=fixture(tmp_path)
    def forbidden(*args): raise AssertionError('must not authorize or create backend')
    worker=OwnedWindowsWorker(registration,authorizer=forbidden,_backend_factory=forbidden,_clock=lambda:2_000_000_000)
    result=worker.run(outer,cancellation=Event(),deadline_ns=outer.expires_at_ns)
    assert result.primary_error=='ValueError'
