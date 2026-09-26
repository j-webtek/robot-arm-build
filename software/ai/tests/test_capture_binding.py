from dataclasses import replace
from datetime import datetime, timezone
from pathlib import Path
import sys
import pytest
AI=Path(__file__).resolve().parents[1]
sys.path[:0]=[str(AI),str(AI.parent/'src'),str(AI.parent/'tests/unit')]
import test_model_motion_ingress_v2 as arm
from rocell_ai.capture_binding import bind_capture
from rocell_ai.scene_observation import FrameEvidence, canonical_hash


def fixture():
    stamp=datetime.fromtimestamp(arm.T0/1000,timezone.utc).isoformat().replace('+00:00','Z')
    frame=FrameEvidence('frame-001',stamp,b'fixture-image-bytes')
    evidence=replace(arm._evidence(),image_sha256=frame.image_sha256)
    receipt={k:getattr(evidence,k) for k in ('capture_id','frame_id','image_sha256',
        'camera_identity_sha256','capture_clock_domain_id','captured_at_epoch_ms')}
    receipt.update(schema='rocell.ai_capture_receipt.v0',issuer_id='fixture-capture-service')
    digest=canonical_hash(receipt);receipt['receipt_sha256']=digest
    return frame,evidence,dict(receipt_sha256=digest,trusted_receipts={digest:receipt},expected_issuer_id='fixture-capture-service')


def test_binds_exact_capture_without_authority():
    f,e,args=fixture();result=bind_capture(f,e,**args)
    assert result['status']=='BOUND_TO_CALLER_TRUSTED_RECEIPT'
    assert result['hardware_writes']==result['physical_movements']==0


def test_no_installed_registry():
    f,e,args=fixture();args.pop('trusted_receipts')
    assert bind_capture(f,e,**args) is None


@pytest.mark.parametrize('field',['capture_id','frame_id','image_sha256','camera_identity_sha256','capture_clock_domain_id','captured_at_epoch_ms'])
def test_wrong_evidence(field):
    f,e,args=fixture()
    value=arm.T0-1 if field=='captured_at_epoch_ms' else ('0'*64 if field.endswith('sha256') else 'different')
    with pytest.raises(ValueError,match='mismatch'):
        bind_capture(f,replace(e,**{field:value}),**args)


@pytest.mark.parametrize('mutation',['bytes','time','issuer','hash','extra'])
def test_capture_mutations(mutation):
    f,e,args=fixture()
    if mutation=='bytes': f=replace(f,image_bytes=b'changed')
    if mutation=='time': f=replace(f,captured_at_utc='2026-01-01T00:00:00Z')
    if mutation=='issuer': args['expected_issuer_id']='other'
    if mutation=='hash': args['trusted_receipts'][args['receipt_sha256']]['issuer_id']='altered'
    if mutation=='extra': args['trusted_receipts'][args['receipt_sha256']]['extra']=1
    with pytest.raises(ValueError): bind_capture(f,e,**args)
