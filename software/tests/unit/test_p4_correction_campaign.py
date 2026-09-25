from pathlib import Path
import shutil
import subprocess
import pytest

from rocell.application.p4_correction_campaign import assess_leg, P4CorrectionHost
from rocell.application.wizard_diagnostic_export import verify_export

ROOT=Path(__file__).resolve().parents[2]


@pytest.fixture(scope='module')
def native(tmp_path_factory):
    compiler=shutil.which('clang++')
    if not compiler: pytest.skip('Native compiler unavailable')
    target=tmp_path_factory.mktemp('repeat-native')/'owner.exe'
    result=subprocess.run([compiler,'-std=c++17','-I'+str(ROOT/'firmware/diagnostics'),
        '-I'+str(ROOT/'.firmware-tools/configured-diagnostic-candidate-r71/RoArm-M3_example'),
        str(ROOT/'firmware/diagnostics/test_p4_correction_owner.cpp'),'-o',str(target)],capture_output=True,text=True)
    assert result.returncode==0,result.stderr
    return target


@pytest.fixture(scope='module')
def records(native):
    result=subprocess.run([str(native),'success'],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,result.stderr
    return [bytes.fromhex(s) for s in result.stdout.splitlines()]


@pytest.mark.parametrize('mode',['delivery','drift','evidence','expired','source','prewrite','timeout'])
@pytest.mark.parametrize('leg',range(1,17))
def test_native_failure_at_every_leg(native,mode,leg):
    result=subprocess.run([str(native),mode,str(leg)],capture_output=True,text=True,timeout=10)
    assert result.returncode==0,(mode,leg,result.returncode,result.stderr)


def test_native_records_independently_verified(records):
    previous=None
    assert len(records)==16
    for leg,raw in enumerate(records,1):
        previous=assess_leg(raw,boot='ab'*16,leg=leg,previous=previous)
        assert previous['endpoint_error_counts']==(-3 if leg % 2 == 0 else 3)
    with pytest.raises(ValueError,match='record or leg'):
        assess_leg(records[0],boot='ab'*16,leg=2)
    with pytest.raises(ValueError,match='boot'):
        assess_leg(records[0],boot='cd'*16,leg=1)


def test_simulated_correction_scoring(records):
    from rocell.application.p4_correction_scoring import score_records
    result=score_records(records,boot='ab'*16)
    assert result['result']=='LOCAL_SCREEN_PASS'
    assert result['metrics']['baseline']['errors_counts']==[3]*4
    assert result['metrics']['candidate']['errors_counts']==[0]*4
    assert result['mae_improvement_counts']==3
    assert result['physical_accuracy_verified'] is False
    with pytest.raises(ValueError,match='inconclusive'):
        score_records(records[:-1],boot='ab'*16)
    with pytest.raises(ValueError):score_records(list(reversed(records)),boot='ab'*16)


def test_verified_motion_does_not_imply_correction_success(native):
    from rocell.application.p4_correction_scoring import score_records
    run=subprocess.run([str(native),'no_benefit'],capture_output=True,text=True,timeout=10)
    assert run.returncode==0,run.stderr
    result=score_records([bytes.fromhex(s) for s in run.stdout.splitlines()],boot='ab'*16)
    assert result['verified_legs']==16
    assert result['screening_criteria_met'] is False
    assert result['result']=='REVIEW_REQUIRED'
    assert result['mae_improvement_counts']==0


class Transport:
    def __init__(self,records,bad_leg=0):
        self.records=records;self.leg=1;self.receipts=[];self.bad_leg=bad_leg
    def __call__(self,method,path,body=b''):
        suffix=path.rsplit('/',1)[-1]
        if suffix=='start': assert body==b'P4C16';return b'CAPTURING_START'
        if suffix=='status': return f'AWAITING_EXPORT|{self.leg}'.encode()
        if suffix=='record': return self.records[self.leg-1].hex().encode()
        if suffix=='next':
            assert body==str(self.leg).encode()
            return b'CAPTURING_START'
        if suffix=='receipt':
            import hashlib
            assert body==f'{self.leg}:{hashlib.sha256(self.records[self.leg-1]).hexdigest()}'.encode()
            self.receipts.append(self.leg)
            if self.leg==self.bad_leg: raise TimeoutError('Receipt response lost')
            self.leg+=1
            return b'COMPLETE' if self.leg==17 else f'READY|{self.leg}'.encode()
        raise AssertionError(path)


def test_full_host_campaign(records,tmp_path):
    transport=Transport(records);host=P4CorrectionHost(transport,boot='ab'*16,export_root=tmp_path)
    result=host.run_once()
    assert result['status']=='CAMPAIGN_COMPLETE'
    assert transport.receipts==list(range(1,17))
    assert all(verify_export(Path(p))['valid'] for p in result['exports'])
    from rocell.application.p4_correction_scoring import score_exported_campaign
    source_ids=[Path(p).name for p in result['exports']]
    scored=score_exported_campaign(tmp_path,source_ids,boot='ab'*16,source_kind='unverified')
    assert scored['verified_legs']==16
    assert scored['source_kind']=='unverified'
    with pytest.raises(ValueError,match='distinct'):
        score_exported_campaign(tmp_path,source_ids[:-1]+source_ids[:1],boot='ab'*16)
    with pytest.raises(ValueError,match='consumed'):host.run_once()


@pytest.mark.parametrize('leg',range(1,17))
def test_lost_receipt_stops_without_retry(records,tmp_path,leg):
    transport=Transport(records,bad_leg=leg)
    host=P4CorrectionHost(transport,boot='ab'*16,export_root=tmp_path)
    with pytest.raises(ValueError,match='Campaign stopped'):host.run_once()
    assert transport.receipts==list(range(1,leg+1))
    with pytest.raises(ValueError,match='consumed'):host.run_once()


@pytest.mark.parametrize('leg',range(1,17))
def test_export_failure_never_receipts(records,tmp_path,monkeypatch,leg):
    from rocell.application import p4_correction_campaign as module
    verify=module.verify_export;calls=0
    def injected(path):
        nonlocal calls
        calls+=1
        return {'valid':False} if calls==leg else verify(path)
    monkeypatch.setattr(module,'verify_export',injected)
    transport=Transport(records)
    with pytest.raises(ValueError,match='Campaign stopped'):
        P4CorrectionHost(transport,boot='ab'*16,export_root=tmp_path).run_once()
    assert transport.receipts==list(range(1,leg))


@pytest.mark.parametrize('leg',range(2,17))
def test_next_command_uncertainty_never_retried(records,tmp_path,leg):
    delegate=Transport(records);next_calls=[]
    def transport(method,path,body=b''):
        if path.endswith('/next'):
            next_calls.append(int(body))
            if int(body)==leg: raise TimeoutError('Next response lost')
        return delegate(method,path,body)
    with pytest.raises(ValueError,match='Campaign stopped'):
        P4CorrectionHost(transport,boot='ab'*16,export_root=tmp_path).run_once()
    assert next_calls==list(range(2,leg+1))
    assert delegate.receipts==list(range(1,leg))
