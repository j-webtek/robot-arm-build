"""Exact registration validation is not activation of physical execution."""
from dataclasses import replace
import hashlib
from pathlib import Path
import sys
from threading import Event

import pytest

from rocell.application.first_motion_contract import canonical
from rocell.application.first_motion_evidence_snapshot import prepare_snapshot,import_build_snapshot
from rocell.application.endpoint_reference_reader import source_fingerprint
from rocell.providers.windows import first_motion_native_registration as module
from rocell.providers.windows import first_motion_native_protocol as protocol
from rocell.providers.windows import first_motion_native_package as package
from rocell.providers.windows.owned_worker_process import (
    PinnedWorkerFile,WorkerProcessRegistration,OwnedWorkerRequest,OwnedWindowsWorker,owned_registration_document,
)
from test_first_motion_reference_reader import prepare
from test_first_motion_measurement_binding import SESSION,OPERATION


def registration(tmp_path):
    workspace=Path(__file__).resolve().parents[3]
    request=prepare(tmp_path,source_fingerprint(workspace),import_build_snapshot(workspace).snapshot_hash)
    body=request.to_dict()
    wd=tmp_path/(body['attempt_id']+'-first-motion-native-child'); wd.mkdir()
    archive=package.prepare(wd)
    evidence=prepare_snapshot(workspace,request,reference_root=tmp_path,directory=wd)
    def pin(path): return PinnedWorkerFile(path,hashlib.sha256(path.read_bytes()).hexdigest())
    pins=(pin(package.CHILD),pin(archive),pin(evidence))
    reg=WorkerProcessRegistration(protocol.WORKER_ID,pin(Path(getattr(sys,'_base_executable',sys.executable))),
        ('-I','-S',str(package.CHILD),str(archive),pins[1].sha256,'execute-one'),pins,wd,
        protocol.fixed_budget(),'PHYSICAL_UNQUALIFIED',protocol.REQUEST_SCHEMA,protocol.RESULT_SCHEMA)
    payload=dict(schema=protocol.PAYLOAD_SCHEMA,root=str(tmp_path),session_id=SESSION,
        measurement_operation_id=OPERATION,first_motion_request=body,launch_sha256='a'*64,
        registration=owned_registration_document(reg),review_authority_id='local-first-motion-review-v1')
    outer=OwnedWorkerRequest(body['attempt_id'],SESSION,body['references']['source_sha256'],
        request.request_sha256,module.identity_hash(request),body['deadline_monotonic_ns'],canonical(payload))
    return reg,outer


def test_fixed_registration_validates_but_cannot_launch(tmp_path):
    reg,outer=registration(tmp_path)
    assert module.validate_registration(reg,outer)['first_motion_request']['physical_authority'] is False
    def forbidden(*a,**kw): pytest.fail('No production launch admitted')
    result=OwnedWindowsWorker(reg,authorizer=forbidden,_backend_factory=forbidden,
        _clock=lambda:2_000_000_000).run(outer,cancellation=Event(),deadline_ns=outer.expires_at_ns)
    assert result.status=='FAILED' and not result.process_created


def test_supervisor_invokes_prelaunch_before_backend_or_authorizer(tmp_path,monkeypatch):
    from rocell.providers.windows import first_motion_prelaunch
    reg,outer=registration(tmp_path)
    calls=[]
    def refuse(payload,**kwargs):
        calls.append(payload['first_motion_request']['attempt_id'])
        raise ValueError('Synthetic prelaunch refusal')
    monkeypatch.setattr(first_motion_prelaunch,'verify_reserved_first_motion_entry',refuse)
    def forbidden(*a,**kw): pytest.fail('Backend/authorizer reached after refusal')
    result=OwnedWindowsWorker(reg,authorizer=forbidden,_backend_factory=forbidden,
        _clock=lambda:2_000_000_000).run(outer,cancellation=Event(),deadline_ns=outer.expires_at_ns)
    assert calls==[outer.attempt_id]
    assert result.status=='FAILED' and not result.process_created and not result.initial_thread_resumed


@pytest.mark.parametrize('fault',['argv','budget','wd','pins','identity','source','evidence'])
def test_changed_registration_or_binding_refused(tmp_path,fault):
    reg,outer=registration(tmp_path)
    if fault=='argv': reg=replace(reg,argv=reg.argv[:-1]+('check-imports',))
    if fault=='budget': reg=replace(reg,budget=replace(reg.budget,process_count=2))
    if fault=='wd': reg=replace(reg,working_directory=tmp_path)
    if fault=='pins': reg=replace(reg,package_files=reg.package_files[:2])
    if fault=='identity': outer=replace(outer,selected_identity_sha256='f'*64)
    if fault=='source': outer=replace(outer,source_sha256='f'*64)
    if fault=='evidence': reg.package_files[2].path.write_bytes(b'{"changed":true}')
    with pytest.raises(ValueError): module.validate_registration(reg,outer)
