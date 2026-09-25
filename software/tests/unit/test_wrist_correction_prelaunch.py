"""Synthetic fixtures labeled as physical metadata; no actual hardware evidence."""
import json
import pytest
from test_wrist_correction_review_authority import setup
from rocell.application.first_motion_contract import canonical
from rocell.application.wizard_diagnostic_coordinator import source_fingerprint
from rocell.application.wrist_correction_worker_claim import reserve_correction_launch
from rocell.application.wrist_correction_reference_reader import WristCorrectionReferenceReader,FrozenWristCorrectionReferences
from rocell.providers.windows import wrist_correction_prelaunch as prelaunch
from rocell.providers.windows import bench_review_key
from rocell.providers.windows.wrist_correction_native_protocol import PAYLOAD_SCHEMA,digest,evidence_manifest
from rocell.providers.windows.wrist_correction_evidence_store import stage_evidence


def fixture(tmp_path,monkeypatch,controller_document=None):
    authority,ctx,review,args=setup()
    workspace=tmp_path/'workspace';(workspace/'software').mkdir(parents=True)
    (workspace/'software/pyproject.toml').write_text('# synthetic source\n')
    (workspace/'rocell.ps1').write_text('# synthetic launcher\n')
    ctx['references']['source_sha256']=source_fingerprint(workspace)
    directory=tmp_path/(ctx['attempt_id']+'-wrist-correction-native-child');directory.mkdir()
    registration={'fixture':'NOT_A_NATIVE_REGISTRATION'}
    for ref,name,value in [('runtime_sha256','runtime.original.json',registration),
        ('protocol_review_sha256','protocol.original.json',{'fixture':'protocol'}),
        ('native_controller_review_sha256','controller.original.json',controller_document or {'fixture':'controller'})]:
        raw=canonical(value);(directory/name).write_bytes(raw);ctx['references'][ref]=digest(raw)
    ctx['deadline_ns']=ctx['issued_ns']+30_000_000_000
    originals=[]
    for request,raw in args['originals']:
        trial=json.loads(raw);trial['basis']='RETAINED_PHYSICAL_CAPTURE'
        originals.append((request,canonical(trial)))
    plan=authority.seal_plan(ctx,review,originals=originals,now_ns=args['now_ns'],expected_basis='RETAINED_PHYSICAL_CAPTURE')
    payload=dict(schema=PAYLOAD_SCHEMA,root=str(tmp_path),context=ctx,registration=registration,
        launch_sha256='c'*64,review_authority_id='local-wrist-correction-review-v1',plan_sha256=digest(plan),
        originals=evidence_manifest(originals),expected_basis='RETAINED_PHYSICAL_CAPTURE')
    stage_evidence(payload,assigned_root=tmp_path,originals=originals,plan_raw=plan)
    payload['launch_sha256']=reserve_correction_launch(payload,root=tmp_path,authority=authority,now_ns=2_000_000_000)
    monkeypatch.setattr(prelaunch,'load_host_wrist_correction_review_authority',lambda _:authority)
    return workspace,payload,directory


def test_prelaunch_and_reference_freeze_without_claim(tmp_path,monkeypatch):
    workspace,payload,_=fixture(tmp_path,monkeypatch)
    request=prelaunch.verify_reserved_correction_entry(payload,workspace=workspace,clock_ns=lambda:3_000_000_000)
    reader=WristCorrectionReferenceReader(request,workspace=workspace,root=tmp_path)
    frozen=FrozenWristCorrectionReferences(reader)
    assert frozen()==reader()
    assert frozen.original('runtime_sha256')==reader.original('runtime_sha256')
    assert not list(tmp_path.glob('*worker-claimed.json'))


@pytest.mark.parametrize('fault',['source','runtime','plan','claimed','expiry','regression','basis','key'])
def test_changed_prelaunch_context_rejected(tmp_path,monkeypatch,fault):
    workspace,payload,directory=fixture(tmp_path,monkeypatch)
    prefix=payload['context']['attempt_id']+'-wrist-correction-'
    if fault=='source': (workspace/'rocell.ps1').write_text('# changed\n')
    if fault=='runtime': (directory/'runtime.original.json').write_bytes(b'{}')
    if fault=='plan': (tmp_path/(prefix+'plan-review.json')).write_bytes(b'{}')
    if fault=='claimed': (tmp_path/(prefix+'worker-claimed.json')).write_bytes(b'{}')
    if fault=='basis': payload['expected_basis']='SYNTHETIC_WIRE_REHEARSAL'
    if fault=='key':
        def missing(_): raise ValueError('fixture missing key')
        monkeypatch.setattr(prelaunch,'load_host_wrist_correction_review_authority',missing)
    ticks=iter([3_000_000_000,2_000_000_000])
    clock=(lambda:next(ticks)) if fault=='regression' else lambda:32_000_000_000 if fault=='expiry' else 3_000_000_000
    with pytest.raises(ValueError): prelaunch.verify_reserved_correction_entry(payload,workspace=workspace,clock_ns=clock)


def test_host_key_derivation_does_not_provision(monkeypatch):
    from rocell.safety.bench_review_authority import BenchReviewAuthority
    from rocell.safety.wrist_correction_review_authority import WristCorrectionReviewAuthority
    monkeypatch.setattr(bench_review_key,'load_host_bench_review_authority',lambda _:BenchReviewAuthority(b'A'*32))
    monkeypatch.setattr(bench_review_key,'provision_bench_review_key',lambda _:pytest.fail('must not provision'))
    assert type(bench_review_key.load_host_wrist_correction_review_authority('fixture')) is WristCorrectionReviewAuthority
