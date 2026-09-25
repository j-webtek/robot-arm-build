import json
import pytest
from test_wrist_correction_review_authority import setup
from test_endpoint_current_context import fixture as endpoint_fixture
from rocell.application import wrist_correction_worker_preparation as preparation
from rocell.application.first_motion_contract import canonical
from rocell.providers.windows import bench_review_key
from rocell.providers.windows.wrist_correction_current_context import WristCorrectionContextRequest
from rocell.providers.windows.owned_worker_process import owned_registration_document,owned_request_wire
from rocell.providers.windows.wrist_correction_native_protocol import digest,decode_request


def fixture(tmp_path,monkeypatch):
    _,_,_,controller=endpoint_fixture()
    authority,ctx,review,args=setup()
    workspace=tmp_path/'workspace';(workspace/'software').mkdir(parents=True)
    (workspace/'software/pyproject.toml').write_text('# fixture\n');(workspace/'rocell.ps1').write_text('# fixture\n')
    staged=preparation.stage_correction_runtime(workspace,root=tmp_path,attempt_id=ctx['attempt_id'],
        controller_original=canonical(controller.to_dict()),protocol_original=canonical({'fixture':'protocol'}))
    ctx['references']=dict(source_sha256=staged.source_sha256,
        runtime_sha256=digest(canonical(owned_registration_document(staged.registration))),
        native_controller_review_sha256=staged.registration.package_files[2].sha256,
        protocol_review_sha256=staged.registration.package_files[3].sha256)
    ctx['deadline_ns']=ctx['issued_ns']+30_000_000_000
    originals=[]
    for request,raw in args['originals']:
        trial=json.loads(raw);trial['basis']='RETAINED_PHYSICAL_CAPTURE';originals.append((request,canonical(trial)))
    plan=authority.seal_plan(ctx,review,originals=originals,now_ns=args['now_ns'],expected_basis='RETAINED_PHYSICAL_CAPTURE')
    monkeypatch.setattr(bench_review_key,'load_host_wrist_correction_review_authority',lambda _:authority)
    return workspace,staged,WristCorrectionContextRequest(canonical(ctx)),plan,originals


def test_prepare_complete_wire_without_dispatch_and_no_repeat(tmp_path,monkeypatch):
    workspace,staged,request,plan,originals=fixture(tmp_path,monkeypatch)
    prepared=preparation.prepare_correction_worker(workspace,staged,request,plan_original=plan,originals=originals,clock_ns=lambda:2_000_000_000)
    raw,_=owned_request_wire(prepared.registration,prepared.request,deadline_ns=prepared.request.expires_at_ns)
    assert decode_request(raw)['payload']['plan_sha256']==digest(plan)
    from rocell.providers.windows import wrist_correction_prelaunch as prelaunch
    from rocell.providers.windows.wrist_correction_invocation import verify_actual_invocation
    monkeypatch.setattr(prelaunch,'load_host_wrist_correction_review_authority',bench_review_key.load_host_wrist_correction_review_authority)
    assert prelaunch.verify_reserved_correction_entry(decode_request(raw)['payload'],workspace=workspace,
        clock_ns=lambda:2_000_000_000)==request
    reg=prepared.registration
    assert verify_actual_invocation(raw,entry_path=reg.package_files[0].path,executable=reg.executable.path,
        argv=reg.argv,working_directory=reg.working_directory)['attempt_id']==staged.attempt_id
    assert not list(tmp_path.glob('*worker-claimed.json'))
    with pytest.raises((ValueError,RuntimeError,OSError)):
        preparation.prepare_correction_worker(workspace,staged,request,plan_original=plan,originals=originals,clock_ns=lambda:2_000_000_000)


@pytest.mark.parametrize('fault',['source','plan','runtime','expiry','regression'])
def test_changed_preparation_inputs_held(tmp_path,monkeypatch,fault):
    workspace,staged,request,plan,originals=fixture(tmp_path,monkeypatch)
    if fault=='source': (workspace/'rocell.ps1').write_text('# changed\n')
    if fault=='plan': plan=b'{}'
    if fault=='runtime': (staged.registration.working_directory/'runtime.original.json').write_bytes(b'{}')
    ticks=iter([3_000_000_000,2_000_000_000])
    clock=(lambda:next(ticks)) if fault=='regression' else lambda:32_000_000_000 if fault=='expiry' else 2_000_000_000
    with pytest.raises(ValueError):
        preparation.prepare_correction_worker(workspace,staged,request,plan_original=plan,originals=originals,clock_ns=clock)
    assert not list(tmp_path.glob('*-launch.json'))
